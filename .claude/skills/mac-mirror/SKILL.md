---
name: mac-mirror
description: "Mirror the current git dir/worktree/branch onto a Mac and continue the work session there instead of locally. Pushes the branch, checks it out remotely via SSH, and drops into a tmux session. Falls back to Slack if SSH is unreachable. Use when asked to move/continue work on a Mac, hand off to it, or mirror this session to Mac from Linux or elsewhere."
---

# Mac Mirror — hand this branch off to a Mac

Companion to [linux-mirror](../linux-mirror/SKILL.md) (same flow, opposite direction). Unlike a plain SSH-steering skill, this mirrors the **current repo's committed state** onto the target Mac and resumes work there in a persistent tmux session.

If you're already running locally on the target Mac, there's nothing to mirror — say so and stop.

## Setup (once, per pair of machines)

This skill assumes you've already got:
- An SSH host alias for the Mac in `~/.ssh/config` (LAN), e.g.:
  ```
  Host mymac
      HostName 192.168.1.60
      User myusername
      IdentityFile ~/.ssh/id_mymac
  ```
  (`ssh_config` does not expand environment variables — write your actual username literally, not `$USER`.)
- SSH enabled on the Mac (System Settings → General → Sharing → Remote Login), with the other machine's public key added.
- Your repo lives under `$HOME` on the source machine (any relative path). This skill mirrors it onto the target Mac under `$HOME/mirror/<same relative path>` — a dedicated namespace so every mirrored checkout is easy to find on either machine and never collides with (or silently overwrites) a normal checkout that happens to already exist at that same path. A repo outside `$HOME` on the source side isn't supported — step 1 below checks for this and stops rather than silently producing a wrong path.
- (Optional, for off-LAN/travel use) Both machines joined to the same Tailscale tailnet — same caveat as linux-mirror: the bare alias won't fail over to Tailscale automatically, target the Tailscale IP + explicit `-i` when off-LAN.
- (Optional, for SSH-fully-down fallback) A messaging-gateway agent running on the Mac, watching a Slack channel (or similar) you can post to.

Substitute your own host alias / IP / key path / username everywhere `mymac` / `myusername` appears below.

## What this carries over

Only **committed and pushed** state — the current branch's HEAD. Uncommitted/staged local edits are NOT transferred; commit or stash first if you need them.

## Steps

### 1. Detect local state

```bash
REPO_ROOT=$(git rev-parse --show-toplevel)
BRANCH=$(git -C "$REPO_ROOT" branch --show-current)
REMOTE_URL=$(git -C "$REPO_ROOT" remote get-url origin)
DIRTY=$(git -C "$REPO_ROOT" status --porcelain)

case "$REPO_ROOT" in
  "$HOME"/*) REL_PATH=${REPO_ROOT#"$HOME/"} ;;
  *) echo "ERROR: repo root ($REPO_ROOT) is not under \$HOME ($HOME) — this skill mirrors by \$HOME-relative path on both machines. Move or symlink the repo under \$HOME first." >&2; exit 1 ;;
esac
```

Also prepare `$CONTEXT`: a short, self-contained summary (1-3 sentences) of what should actually continue on the Mac — the real next action, not just "resume work." This isn't optional bookkeeping: step 4 types it as the first message to a freshly-launched coding agent on the target machine, which has no access to this conversation. Write it as if briefing a colleague who just walked in cold.

If `$BRANCH` is empty (detached HEAD) or `$DIRTY` is non-empty, stop and tell the user — commit/name the branch first.

If `$REMOTE_URL` is an HTTPS URL with an embedded credential (`https://<token>@host/...`), warn the user before continuing: that URL gets written verbatim into the remote clone's `.git/config` in step 4, so the credential ends up live on the target Mac too. Prefer an SSH remote, or a credential helper that doesn't embed the token in the URL. (Step 4's base64 encoding is not a confidentiality measure for this value — it only prevents argv re-tokenization/injection. A trivially-decodable token is still visible in the remote host's `ps` output during the mirror.)

### 2. Push the branch

```bash
git -C "$REPO_ROOT" push -u origin "$BRANCH"
```

Confirm with the user first if the branch has no upstream yet or diverges from origin.

### 3. Pick a connectivity tier — try in order, stop at first success. Carry the resolved connection forward into `SSH_ARGS`/`SSH_TARGET` for step 4 — don't just check reachability and then reconnect a different way.

See [cross-machine-ssh-tier](../cross-machine-ssh-tier/SKILL.md) for the Tier 1→2→3 connectivity ladder (LAN SSH → SSH over Tailscale → messaging-gateway fallback), its debugging caveats, and the key-naming convention. Run that skill's ladder block with `PEER_LAN_ALIAS="mymac"` (and the matching `PEER_TS_PATTERN`/`PEER_KEY`/`PEER_USER`) to resolve `SSH_ARGS`/`SSH_TARGET` before continuing to step 4. If `$SSH_TARGET` comes back empty, both Tier 1 and Tier 2 failed — fall through to that skill's Tier 3 (messaging-gateway handoff): post the exact repo/branch/commit and the steps from §4 to a channel a reactive gateway agent on the Mac is watching, asking it to execute them locally and reply when the tmux session is ready.

### 4. Remote checkout + tmux (Tier 1/2 only — skip if `$SSH_TARGET` is empty, that means Tier 3 applies instead)

Arguments are base64-encoded before crossing the wire — `ssh host command args...` does not preserve argv separation, the remote shell re-tokenizes the command line, so an unencoded branch name with a space or shell metacharacter (`;`, `` ` ``, `$()`, `&&`, `|` — all valid in a git branch name) can misdirect arguments or execute commands on the remote host. Base64 output contains none of those characters.

```bash
REL_PATH_B64=$(printf '%s' "$REL_PATH" | base64 | tr -d '\n')
BRANCH_B64=$(printf '%s' "$BRANCH" | base64 | tr -d '\n')
REMOTE_URL_B64=$(printf '%s' "$REMOTE_URL" | base64 | tr -d '\n')
CONTEXT_B64=$(printf '%s' "$CONTEXT" | base64 | tr -d '\n')

ssh "${SSH_ARGS[@]}" "$SSH_TARGET" bash -s -- "$REL_PATH_B64" "$BRANCH_B64" "$REMOTE_URL_B64" "$CONTEXT_B64" << 'EOF'
set -e
REL_PATH=$(printf '%s' "$1" | base64 -d)
BRANCH=$(printf '%s' "$2" | base64 -d)
REMOTE_URL=$(printf '%s' "$3" | base64 -d)
CONTEXT=$(printf '%s' "$4" | base64 -d)
TARGET="$HOME/mirror/$REL_PATH"

if [ ! -e "$TARGET/.git" ]; then
  mkdir -p "$(dirname "$TARGET")"
  git clone "$REMOTE_URL" "$TARGET"
fi

cd "$TARGET"

ORIGIN_URL=$(git remote get-url origin 2>/dev/null || echo "")
if [ -n "$ORIGIN_URL" ] && [ "$ORIGIN_URL" != "$REMOTE_URL" ]; then
  echo "ERROR:$TARGET already has a different origin ($ORIGIN_URL) — not touching it, resolve manually" >&2
  exit 1
fi

if [ -n "$(git status --porcelain --untracked-files=no)" ]; then
  echo "ERROR:$TARGET has uncommitted changes on the remote side — not overwriting them, resolve manually" >&2
  exit 1
fi

git fetch origin "$BRANCH"
if git show-ref --verify --quiet "refs/heads/$BRANCH"; then
  git checkout "$BRANCH"
else
  git checkout -b "$BRANCH" "origin/$BRANCH"
fi

if ! git pull --ff-only origin "$BRANCH"; then
  echo "DIVERGED:$TARGET — local $BRANCH has diverged from origin/$BRANCH, resolve manually before continuing" >&2
  exit 1
fi

# A stable checksum suffix disambiguates branches that sanitize to the same
# session name (e.g. "feat/a" and "feat-a" both become "mirror-feat-a" via
# tr alone) — cksum is portable everywhere (macOS + Linux), unlike
# sha256sum/shasum which aren't guaranteed on both.
BRANCH_SAFE=$(printf '%s' "$BRANCH" | tr -c 'a-zA-Z0-9_-' '-')
BRANCH_HASH=$(printf '%s' "$BRANCH" | cksum | cut -d' ' -f1)
SESSION="mirror-${BRANCH_SAFE}-${BRANCH_HASH}"
# tmux has-session prefix-matches by default — the leading "=" forces an
# exact match so a shorter branch name doesn't false-match a longer one.
if tmux has-session -t "=$SESSION" 2>/dev/null; then
  echo "RESUMED:$SESSION:$TARGET:$(git rev-parse HEAD)"
else
  # A bare shell in a checked-out repo is not "continuing the work session"
  # — launch the coding agent as the session's actual command, with
  # $CONTEXT as its argv, instead of `new-session` + a bare shell +
  # `send-keys` typed in after a fixed sleep. tmux execs trailing words
  # directly (no shell re-tokenization), so this also closes the injection
  # window a typed-and-Entered $CONTEXT would open if the CLI weren't at
  # its prompt yet: a `send-keys`-typed string lands in whatever the pane's
  # foreground process is at that moment, so a starting-vs-prompt-not-ready
  # race can dump $CONTEXT straight into an interactive shell and execute
  # it. Passing it as an argv element never touches a shell at all — this
  # only ever fires on a session that didn't already exist (the branch
  # above), so a resumed session never gets a replayed prompt injected on
  # top of work already in progress.
  #
  # `--dangerously-skip-permissions` and `--` are both required. `--`
  # stops `claude` from treating a `$CONTEXT` that happens to start with
  # `-`/`--` as a flag instead of the prompt. `--dangerously-skip-permissions`
  # skips tool-permission prompts, but — confirmed live, 2026-09-18 — it
  # does NOT suppress the first-run workspace-trust dialog for a git
  # repository specifically (it does for a plain non-git directory, which
  # is what made an earlier version of this fix look sufficient before
  # testing against an actual mirrored clone). That dialog's *default*
  # selection is "No, exit"; a bare `claude "$CONTEXT"` on a fresh mirror
  # clone sits there, and the session vanishes the instant anything —
  # including an unrelated Enter — accepts the default and exits `claude`.
  #
  # remain-on-exit is set in the same tmux invocation (not a separate
  # call) so a session that dies immediately — missing `claude` binary,
  # PATH not resolving it under a non-login tmux shell, a crash — leaves a
  # dead-but-inspectable pane instead of vanishing outright.
  if [ -n "$CONTEXT" ]; then
    tmux new-session -d -s "$SESSION" -c "$TARGET" claude --dangerously-skip-permissions -- "$CONTEXT" \; set-option -t "$SESSION" remain-on-exit on
    # Poll for the trust dialog and accept it with fixed navigation keys
    # (Down, Enter) — never $CONTEXT — so this carries none of the
    # injection risk the original send-keys-typed-$CONTEXT bug had. This
    # only fires the first time a given target directory is mirrored (the
    # dialog only appears once claude.json records the directory as
    # trusted); a no-op loop on an already-trusted directory is safe.
    for _ in $(seq 1 20); do
      if tmux capture-pane -p -t "$SESSION" 2>/dev/null | grep -q "Yes, I trust this folder"; then
        tmux send-keys -t "$SESSION" Down
        sleep 0.3
        tmux send-keys -t "$SESSION" Enter
        break
      fi
      sleep 0.5
    done
  else
    tmux new-session -d -s "$SESSION" -c "$TARGET" \; set-option -t "$SESSION" remain-on-exit on
  fi
  # tmux new-session exits 0 even when the launched command can't be
  # exec'd, and with remain-on-exit set, has-session alone can't tell a
  # genuinely running session from a dead one either — remain-on-exit
  # keeps the session entry around specifically so it doesn't vanish, so
  # has-session still returns success. #{pane_dead} is the actual signal
  # (confirmed live: 1 immediately after an exec failure, 0 while running).
  if tmux has-session -t "=$SESSION" 2>/dev/null && [ "$(tmux display-message -p -t "$SESSION" '#{pane_dead}')" = "0" ]; then
    echo "READY:$SESSION:$TARGET:$(git rev-parse HEAD)"
  else
    echo "FAILED:$SESSION:$TARGET — session did not survive launch (check that \`claude\` is on the remote PATH); pane retained by remain-on-exit for inspection: tmux capture-pane -p -t $SESSION" >&2
    exit 1
  fi
fi
EOF
```

Note: `printf` (not `echo`) for the session-name sanitizing is deliberate — piping `echo`'s output through `tr -c '...' '-'` turns the trailing newline into a literal `-`, corrupting the session name.

### 5. Hand off

Report the session name, target path, and commit SHA from the `READY:`/`RESUMED:` line — cross-check that SHA against your local `git rev-parse HEAD`. `READY` means a fresh session was created and the agent was just launched with `$CONTEXT`; `RESUMED` means an existing session was found as-is and nothing was typed into it — check on that work directly (attach or send a follow-up) rather than assuming it's idle. This check isn't optional: `--ff-only` only guards against a genuinely diverged remote branch — if the remote already has local commits sitting *ahead* of `origin/$BRANCH` (not diverged, just ahead), the pull succeeds as a silent no-op and `READY` reports that ahead-of-origin SHA, not the one you just pushed. The SHA cross-check is what actually catches that case. Then give the attach command:

```bash
ssh -t "${SSH_ARGS[@]}" "$SSH_TARGET" "tmux attach -t <SESSION>"
```

### 6. Push discipline while mirrored

```bash
git add -A && git commit -m "..." && git push
```

If a PR is open for `$BRANCH`, pushes update its head automatically. Otherwise plain `git push` keeps the remote branch current so work isn't stranded on the Mac alone.

## Caveats

- Committed-state-only mirror — see "What this carries over" above.
- Source repo must live under `$HOME` (see Setup) — step 1 fails loudly rather than silently mirroring to the wrong place. The target-side checkout always lands under `$HOME/mirror/`, not at the identical path as the source.
- Step 4 auto-launches `claude` (hardcoded) and types `$CONTEXT` into it, but only on a freshly created session — edit the hardcoded command if you use a different CLI. Never assume a `RESUMED` session is idle just because this skill didn't type anything into it.
- macOS SSH keychain may prompt on first connection; `ssh-add --apple-use-keychain ~/.ssh/id_mymac` caches it.
- A bare host alias is typically LAN-only; off-LAN, target the Tailscale IP + explicit `-i` per Tier 2 — and make sure step 4 actually uses the resolved `$SSH_ARGS`/`$SSH_TARGET`, not a re-hardcoded alias.
- Never pass unencoded user-controlled values (repo path, branch name, remote URL) as literal SSH command arguments — base64-encode first (see step 4).
- Tier 3 hands off to a *different* agent/process with no shared context — see the debugging priority above before assuming it's broken vs. just needing a genuinely human-originated test or a missing permission grant.
- If your remote origin URL embeds a credential (HTTPS + PAT), that credential gets written to the target machine's `.git/config` in cleartext the first time this clones there — prefer an SSH remote or an external credential helper.
