# Schedule PR owner inspection

Enroll each PR on one owning host. Keep its mode-0600 config at `~/.config/pr-owner-nudger/config.json`, for example `{"enabled":false,"owners":[{"cwd":"/absolute/worktree","repo":"owner/repo","cli":"codex","session":"<original-session-id>"}]}`. Install Python 3, Git, `gh` (authenticated for the scheduler account), and the owner's CLI. The wrapper loads that account's Bash profile.

From the reviewed repository, make a seat package. Transfer the archive through the authorized channel and extract with `tar -xf pr-owner-nudger.tar` in the seat's workspace. Keep the extracted path stable and create the seat's own config.

```bash
git archive --output=pr-owner-nudger.tar "$reviewed_sha" scripts/{pr_owner_nudger.py,pr_nudger_routes.py,pr_nudger_discovery.py,run_pr_owner_nudger.sh,render_pr_owner_nudger.py} \
  .claude/skills/dot/{SKILL.md,scripts/dot.sh,scripts/dot_chrome.mjs} \
  launchd/org.prw.pr-owner-nudger.plist.template systemd/pr-owner-nudger.{service,timer}.template docs/pr-owner-nudger.md
# In the extracted workspace on the seat
config="$HOME/.config/pr-owner-nudger/config.json"
stage="$(mktemp -d)"
python3 scripts/pr_owner_nudger.py --config "$config"
```

Use `worktree_roots` for discovery and `"headless_only": true` on an explicit owner that runs without cmux. Dot enrollments require an `account`, its `identity_sha256` (lowercase SHA-256 of the exact authenticated email), and a lowercase canonical `session` UUID. Set `destination` to that exact private chat's `https://chatgpt.com/c/<session>` URL or its `https://chatgpt.com/g/g-<gpt-id>/c/<session>` form. See the packaged Dot skill for its browser prerequisites.

Both schedules run every five minutes. To dispatch, set `"enabled": true` and add `--apply` when rendering. Skip the disable or bootout step on first install.

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

Stop scheduling and inspect the original owner. In `receipts.sqlite3` in the configured state directory, update only the reconciled lowercase repo and PR. `UPDATE delivery SET status='no_delivery' WHERE repo='owner/repo' AND number=123 AND status IN ('pending_delivery','attempted_delivery');`. If delivery occurred, record `delivered` and its verified Unix timestamp in `time` instead. Restart scheduling and check GitHub independently for advancement. A detached owner can finish after the timer stops.
