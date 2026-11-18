---
name: cwd-safety
description: "Use BEFORE `mv`/`rm -rf` on any directory. Verifies pwd does not match target; session cwd cannot recover once its directory is gone."
---

# Directory replacement safety — never move your own cwd


**Before `mv` or `rm -rf` on any directory**, run `pwd` and verify it does not match the target path. The Bash tool's cwd persists across all calls in a session — moving your own cwd breaks every subsequent command with "path does not exist."

**Protocol for replacing the working directory (e.g. recloning `~/.hermes/`):**
1. Do NOT use the Bash tool for this operation at all
2. Give the user all commands as `! <cmd>` blocks to run in their terminal
3. The session cwd cannot recover once its directory is gone — hand off immediately

**Broken cwd recovery**: If Bash commands start failing with "path does not exist" after a directory move, the shell cwd is gone. Stop retrying. Instruct the user to run remaining steps via `! <cmd>` in the prompt. Do not attempt further Bash tool calls.

## Destructive-path guard & `cc-safety-net` (`standard`) idioms

Canonical rule: `~/.codex/AGENTS.md` § "Destructive-path guard". Never aim `rm -r`, `rsync --delete*`/`--del`, `find -delete`, or `mv` onto an unvalidated computed path:
- `set -u`, prove `[ -n "$D" ] && [ "$D" != / ] || { echo "unsafe dest: '$D'" >&2; exit 1; }`, use `${D:?unset}`, and validate tool outputs (such as `xcrun simctl get_app_container ...`) for non-empty, non-root, expected prefix before copying or deleting.
- Self-check commands via `~/.claude/hooks/lib/destructive_path_guard.py --check '<cmd>'`.
- **`cc-safety-net` (`standard` level) operational idioms**:
  - `rm -r` on variable targets (`rm -rf "$D"`) is denied (`rm.recursive-force-dynamic-target`) — pass literal paths.
  - `rsync --delete` is allowed only into explicit paths inside cwd, `/tmp`, `/var/tmp`, `$TMPDIR`, or remote `user@host:/path` (`rsync.delete`) — drop `--delete` and remove stale files explicitly when syncing elsewhere in `$HOME`.
  - `prog - <<'PY'` heredocs are denied (`analysis.unsupported-heredoc`) — write `STEP_PY="$(~/.claude/skills/scratch-space/scripts/scratch-dir.sh tmp)/step.py"` via `cat > "$STEP_PY" <<'PY'` then run `python3 "$STEP_PY"` (`cat`, `tee`, `git apply`, `git commit`, `gh pr create`, `gh issue create` heredocs stay allowed).
  - Never run `pkill`/`killall` with multiple patterns, `<6`-char patterns, or `-f` without `-u` — use `pgrep -f -- '<6+ char anchored pattern>'` then `kill <PID>`.
