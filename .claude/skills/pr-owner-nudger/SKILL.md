---
name: pr-owner-nudger
description: "Operate the headless PR-owner nudger: one-time scheduler setup, enrolling Codex or agy PR owners, starting the first tick, independent Stage 5 verification, and retiring rounds."
---

# Headless PR-Owner Nudger

Enroll, kick, verify, and retire headless Codex or `agy` PR-owner sessions using the existing nudger scripts in `scripts/` and the full configuration reference in [docs/pr-owner-nudger.md](../../../docs/pr-owner-nudger.md).

## Operator-only actions

Two actions belong strictly to the human operator and are never performed autonomously by an agent:

1. **Enabling dispatch:** setting `"enabled": true` in `~/.config/pr-owner-nudger/config.json` and rendering the scheduler unit with `--apply`.
2. **Merging:** merging any enrolled PR after Stage 5 `FINAL_READY`.

## One-time scheduler install

Render and install the 10-minute scheduler once per host (add `--apply` only when the operator explicitly enables dispatch):

- **macOS (`launchd`):** render `launchd/org.prw.pr-owner-nudger.plist.template` with [scripts/render_pr_owner_nudger.py](../../../scripts/render_pr_owner_nudger.py) (`launchd`), lint with `plutil -lint`, and bootstrap into `~/Library/LaunchAgents/`. The template sets `ProcessType` to `Interactive` so `launchd` does not throttle `cmux` inventory calls into timeouts.
- **Linux (`systemd` user timer):** render `systemd/pr-owner-nudger.service.template` and `systemd/pr-owner-nudger.timer.template` with [scripts/render_pr_owner_nudger.py](../../../scripts/render_pr_owner_nudger.py) (`systemd`), verify with `systemd-analyze --user verify`, install into `${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user`, and enable `pr-owner-nudger.timer`. Requires lingering for logged-out ticks.

Full copy-paste install, check, release-link, and reconciliation commands live in [docs/pr-owner-nudger.md](../../../docs/pr-owner-nudger.md).

## Round runbook

Keep the nudger scripts where they live (`scripts/pr_owner_nudger.py`, `scripts/pr_nudger_routes.py`, `scripts/pr_nudger_intake.py`, `scripts/pr_nudger_discovery.py`, `scripts/pr_nudger_round.py`, `scripts/render_pr_owner_nudger.py`, `scripts/run_pr_owner_nudger.sh`).

1. **Dedicated checkout:** give each PR a dedicated clean checkout on its exact PR head branch (`git switch --detach` any stale duplicate checkout when clean, or create a separate worktree).
2. **Write per-PR scope:** capture the PR's `/ironclad` exit criteria and proof expectations in a temporary scope file.
3. **Enroll:** run [scripts/pr_nudger_round.py](../../../scripts/pr_nudger_round.py) to write the profile, deadline wrapper, and managed enrollment:
   ```bash
   python3 scripts/pr_nudger_round.py enroll \
     --repo <owner/repo> --pr <N> --cwd <checkout> \
     --cli <codex|agy> --model <model> --hours <hours> \
     --scope-file <scope.md>
   ```
   Point `state_dir` in `~/.config/pr-owner-nudger/config.json` at a fresh directory per round. For `agy`, bootstrap runs in print mode (`-p ... --output-format stream-json --model <model> --dangerously-skip-permissions`) and binds the `conversation_id` from the final `{"event":"result"}` line; later wakes resume with `--conversation <id> -p`.
4. **First tick:** start the first tick immediately (works on a fresh `state_dir` even before `receipts.sqlite3` exists):
   ```bash
   python3 scripts/pr_nudger_round.py retry-now --repo <owner/repo> --pr <N> --kick
   ```
5. **Independent Stage 5 verification:** keep this session read-only on the PR branch as the independent verifier. Before counting Stage 5 `FINAL_READY`, verify directly against GitHub and the artifacts:
   - head SHA matches the verified commit;
   - `stage:5-final-approval` label and `## PR Stage` / `## Execution Record` agree;
   - required checks pass on the current head;
   - no unreviewed code changes landed since the tested commit;
   - base-vs-head proof is read directly from its published artifact.
6. **Retire:** when the round ends or the PR is ready for the operator, return it to observe-only:
   ```bash
   python3 scripts/pr_nudger_round.py retire --repo <owner/repo> --pr <N>
   ```
