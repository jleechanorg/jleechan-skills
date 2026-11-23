# Schedule PR owner inspection

Enroll each PR on one owning host. Keep its mode-0600 config at `~/.config/pr-owner-nudger/config.json`, for example `{"enabled":false,"owners":[{"cwd":"/absolute/worktree","repo":"owner/repo","cli":"codex","session":"<original-session-id>"}]}`. Install Python 3, Git, `gh` (authenticated for the scheduler account), and the owner's CLI. The wrapper loads that account's Bash profile. For inspection of a public repository, an installed but signed-out GitHub CLI is sufficient. The inspector uses the public GitHub API when the CLI reports that login is required. Live dispatch still uses the scheduler account.

From the reviewed repository, make a seat package. Transfer the archive through the authorized channel and extract with `tar -xf pr-owner-nudger.tar` in the seat's workspace. Keep the extracted path stable and create the seat's own config.

```bash
git archive --output=pr-owner-nudger.tar "$reviewed_sha" scripts/{pr_owner_nudger.py,pr_nudger_intake.py,pr_nudger_routes.py,pr_nudger_discovery.py,pr_nudger_round.py,run_pr_owner_nudger.sh,render_pr_owner_nudger.py} \
  .claude/skills/dot/{SKILL.md,scripts/dot.sh,scripts/dot_chrome.mjs,scripts/dot_reply.mjs} \
  launchd/org.prw.pr-owner-nudger.plist.template systemd/pr-owner-nudger.{service,timer}.template docs/pr-owner-nudger.md
# In the extracted workspace on the seat
config="$HOME/.config/pr-owner-nudger/config.json"
stage="$(mktemp -d)"
python3 scripts/pr_owner_nudger.py --config "$config"
```

Use `worktree_roots` for discovery. A configured CLI owner is remembered only
after its canonical session transcript matches the actionable PR checkout. The
binding records the host, profile, verification time, and source. An explicitly
tracked PR can still resolve that binding if its owner is removed from config.
Conflicting config cannot replace a verified live binding.

Set `"headless_only": true` only for an owner on a known headless host. On such an
enrolled Linux host, writer checks still apply if cmux inventory is unreachable.
An inaccessible GUI inventory blocks resume. Set `"headless_resume": false` in
the config or owner to disable fallback.

For a Dot owner, set `cli` to `dot`, select its `account`, and set `identity_sha256` to the lowercase SHA-256 of its exact authenticated email. See the Dot skill for browser prerequisites. Both exact transports use the archived `dot_reply.mjs` companion. Bind the owner to one of these destinations.

- For a private ChatGPT conversation, set `session` to its canonical lowercase UUID and `destination` to its exact `https://chatgpt.com/c/<session>` or `https://chatgpt.com/g/g-<gpt-id>/c/<session>` URL.
- For a Dot reply, set `session` to the account's configured seat UUID from `https://chatgpt.com/dots/<session>`. Set `destination` to the verified resolved `https://chatgpt.com/dots/<uuid>~<thread-token>` URL and `parent_message_id` to the observed parent article's complete `data-message-id`. The timer starts from the configured seat URL and only submits in the bound parent’s Replies panel.

Both schedules run every ten minutes. To dispatch, set `"enabled": true` and add `--apply` when rendering. Skip the disable or bootout step on first install.


## Durable targets and recovery

Add exact targets to the same config. For example,
`"targets":[{"repo":"owner/repo","number":123,"observe_only":true}]`.
An enabled `--apply` tick persists all target rows before its first remote
read. Observe-only targets refresh without sending messages or launching an
owner. Inspection without `--apply` leaves SQLite and owner sessions untouched.

A target can set `pickup_after_seconds` to `3600` when the operator requires
one hour of inactivity on its exact remote branch. The activity must match the
refreshed head. GitHub throttling pauses reads until the recorded reset. Target
refresh runs independently of launch backoff. The exact-head CI rollup is
recorded separately. Empty, stale, or unavailable rollups cannot establish CI
success. Due failures retry after 10, 20,
40, then 60 minutes. New CLI or browser launches require at least 5% measured
idle CPU and applicable memory admission.

The cooldown begins at confirmed delivery and does not accumulate retry
backoff. A same-head stage change or a transition from failing or pending
checks to reported success can wake an existing owner on the next tick.
This event still goes through owner, checkout, and receipt verification.

A target's optional `enrollment` names its `head_repo`, `branch`, canonical
absolute `cwd`, owning `host` (the local hostname), `cli`, canonical absolute
`cli_bin` and `profile_dir`, and `model`. The profile's `AGENTS.md` must start with the shared global policy; append run-specific scope below it. Fresh bootstrap requires
`launch_authorized: true` and `managed_exclusive: true`. Use that declaration
only for a dedicated checkout reserved for the managed owner. The local tick
lock serializes the timer's writes. Runtime checks still verify the branch and
look for an existing writer. Fresh bootstrap supports Codex and `agy`.

Unresolved starts persist in the target's `bootstrap` field with a private event
file. The next tick checks that file and the exact session transcript before
binding an acknowledged owner. If the outcome remains uncertain, stop
scheduling and verify the original host, checkout, event file, and transcript.
Only after establishing that no process or delivery exists, clear the
`bootstrap` column for that exact repo and PR to allow another attempt. Keep
the attempt file for reconciliation. Changing hosts requires the same positive
handoff. An unreachable host leaves the attempt pending.

## Running a round

1. Give each PR a dedicated checkout whose local branch is the PR's head branch; the nudger compares that name. If a stale checkout already holds the branch, detach it at the same commit (`git switch --detach`) when it is clean, or use a separate clone when it has work in progress.
2. Enroll each PR. The command writes the profile (shared policy, then a pilot-scope block and your per-PR scope), links `auth.json` for Codex, writes a deadline wrapper and sets the managed enrollment (add `--headless-only` on a Linux host without `cmux`):
   `python3 scripts/pr_nudger_round.py enroll --repo owner/repo --pr N --cwd <checkout> --cli <codex|agy> --model <model> --hours 2 --scope-file <scope.md>`
   Point `state_dir` at a fresh directory per round, and `retire` every PR you are not driving.
3. Start the first tick: `python3 scripts/pr_nudger_round.py retry-now --repo owner/repo --pr N --kick`. On a fresh `state_dir`, `--kick` starts the first tick even before `receipts.sqlite3` exists.
4. Verify each Stage 5 claim yourself before counting it: the head SHA, the stage label and block agree, the required checks (or the repository's own gate), any change since the tested commit, and the base-versus-head proof read from its artifact.
5. When the window ends, run `retire` for each PR. Merging is the operator's decision.

Changing an enrolled PR's model, wrapper or profile is safe: the nudger retires the session it started (`enrollment_changed`) and bootstraps a fresh one after the usual writer checks. It measures launch capacity once per tick, before its own launches. The LaunchAgent runs as `ProcessType` `Interactive`, because launchd throttles `Standard` jobs and the cmux inventory then times out. Keep extra PR polling on GraphQL; the nudger's REST reads share the account's hourly budget.

To install a new version, extract the nudger scripts from the merged commit into a release directory and switch the job's link between ticks, for example `git archive <commit> scripts | tar -x -C "$releases/<commit>"`, then `ln -sfn "$releases/<commit>" "$active"` while `launchctl print` shows the job not running.

## Linux user timer

```bash
python3 scripts/render_pr_owner_nudger.py systemd --config "$config" --output "$stage"
systemd-analyze --user verify "$stage"/pr-owner-nudger.{service,timer}
systemctl --user disable --now pr-owner-nudger.timer
units="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
install -D -t "$units" -m 644 "$stage"/pr-owner-nudger.{service,timer}
systemctl --user daemon-reload
systemctl --user enable --now pr-owner-nudger.timer
```

Linux requires a reachable user manager and lingering to run while logged out. Check the timer with `systemctl --user list-timers pr-owner-nudger.timer` and ticks with `journalctl --user -u pr-owner-nudger.service`. Run the disable command to stop scheduling.

## macOS LaunchAgent

```bash
python3 scripts/render_pr_owner_nudger.py launchd --config "$config" --output "$stage"
label=org.prw.pr-owner-nudger
domain="gui/$(id -u)"
plutil -lint "$stage/$label.plist"
/bin/launchctl bootout "$domain/$label"
mkdir -p "$HOME/Library/LaunchAgents" "$HOME/Library/Logs"
install -m 644 "$stage/$label.plist" "$HOME/Library/LaunchAgents/"
/bin/launchctl bootstrap "$domain" "$HOME/Library/LaunchAgents/$label.plist"
```

macOS requires a GUI login. Check the job with `/bin/launchctl print "$domain/$label"`. Logs are in `~/Library/Logs/pr-owner-nudger{,.error}.log`. To stop scheduling across logins, boot out the job and move its plist out of LaunchAgents.

## Interrupted delivery

For Codex and Claude, the sender records the original transcript and byte
position before issuing the prompt. Later ticks can verify a late matching
receipt in that session and resume the normal cooldown. Uncertain receipts
that cannot be verified stay held for reconciliation.

Stop scheduling and inspect the original owner. In `receipts.sqlite3` in the configured state directory, update only the reconciled lowercase repo and PR. `UPDATE delivery SET status='no_delivery' WHERE repo='owner/repo' AND number=123 AND status IN ('pending_delivery','attempted_delivery');`. If delivery occurred, record `delivered` and its verified Unix timestamp in `time` instead. Restart scheduling and check GitHub independently for advancement. A detached owner can finish after the timer stops.

After the PR head moves, an authorized managed checkout on the same repository
and branch can receive a catch-up reminder through its saved owner. The owner
verifies the head and updates a clean checkout by fast-forward before working
on the next PR obligation. A stale checkout cannot start a fresh owner.
