---
name: pr-owner-nudger
description: "Operate the headless PR-owner nudger: one-time scheduler setup, enrolling Codex or agy PR owners, starting the first tick, independent Stage 5 verification, and retiring rounds."
---

# Headless PR-Owner Nudger

Enroll, kick, verify, and retire headless Codex or `agy` PR-owner sessions using the nudger scripts and reference runbook in `docs/pr-owner-nudger.md` inside the `jleechan-skills` source checkout (or an extracted `pr-owner-nudger.tar` seat workspace).

## Locating the nudger files

Keep the scripts where they live in the `jleechan-skills` repository (`scripts/pr_owner_nudger.py`, `scripts/pr_nudger_routes.py`, `scripts/pr_nudger_intake.py`, `scripts/pr_nudger_discovery.py`, `scripts/pr_nudger_round.py`, `scripts/render_pr_owner_nudger.py`, `scripts/run_pr_owner_nudger.sh`), along with `docs/pr-owner-nudger.md`, `launchd/org.prw.pr-owner-nudger.plist.template`, and `systemd/pr-owner-nudger.{service,timer}.template`.

When running from another repository after installing skills alone, resolve the `jleechan-skills` source checkout (or the extracted seat archive described in `docs/pr-owner-nudger.md`) first; if those files are not present locally, report the missing nudger source directory and stop rather than inventing scripts.

## Operator-only actions

Two actions belong strictly to the human operator and are never performed autonomously by an agent:

1. **Enabling dispatch:** setting `"enabled": true` in `~/.config/pr-owner-nudger/config.json` and rendering the scheduler unit with `--apply`.
2. **Merging:** merging any enrolled PR after Stage 5 `FINAL_READY`.

## One-time scheduler install

From the `jleechan-skills` source root (or seat archive), render and install the 10-minute scheduler once per host (add `--apply` only when the operator explicitly enables dispatch):

- **macOS (`launchd`):** render `launchd/org.prw.pr-owner-nudger.plist.template` with `scripts/render_pr_owner_nudger.py launchd`, lint with `plutil -lint`, and bootstrap into `~/Library/LaunchAgents/`. The template sets `ProcessType` to `Interactive` so `launchd` does not throttle `cmux` inventory calls into timeouts.
- **Linux (`systemd` user timer):** render `systemd/pr-owner-nudger.service.template` and `systemd/pr-owner-nudger.timer.template` with `scripts/render_pr_owner_nudger.py systemd`, verify with `systemd-analyze --user verify`, install into `${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user`, and enable `pr-owner-nudger.timer`. Requires lingering for logged-out ticks.

Full copy-paste install, check, release-link, and reconciliation commands live in `docs/pr-owner-nudger.md`.

## Round runbook

Run these commands from the resolved `jleechan-skills` source root (or seat workspace):

1. **Dedicated checkout:** give each PR a dedicated clean checkout on its exact PR head branch (`git switch --detach` any stale duplicate checkout when clean, or create a separate worktree).
2. **Write per-PR scope:** capture the PR's `/ironclad` exit criteria and proof expectations in a temporary scope file.
3. **Enroll:** run `scripts/pr_nudger_round.py` to write the profile (`AGENTS.md` and `scope.md`), deadline wrapper, and managed enrollment:
   ```bash
   python3 scripts/pr_nudger_round.py enroll \
     --repo <owner/repo> --pr <N> --cwd <checkout> \
     --hours <hours> --scope-file <scope.md>
   ```
   `--cli` and `--model` both inherit from the calling agent, so the PR owner runs as the agent
   that dispatched it: the caller's model comes from `PR_NUDGER_MODEL`, `PI_MODEL`,
   `CLAUDEWA_MODEL`, `CLAUDE_MODEL`, `CODEX_MODEL`, `AGY_MODEL` or `GEMINI_MODEL`, and its family
   chooses the CLI (`gemini-*` → `agy`, else `codex`). An explicit `--model` derives the CLI; an
   explicit `--cli` keeps the caller model only when it fits, else `agy` falls back to
   `gemini-3.8-flash-high` and `codex` refuses. Both flags given are used as-is.

   Pass `--headless-only` when enrolling on a headless host without `cmux` (such as Linux). Point `state_dir` in `~/.config/pr-owner-nudger/config.json` at a fresh directory per round. For `agy`, bootstrap runs in print mode (`-p ... --output-format stream-json --model <model> --dangerously-skip-permissions`) and binds `conversation_id` from the final `{"event":"result"}` line; later wakes resume with `--conversation <id> -p` with `--add-dir <profile>` and the per-PR scope included in the wake prompt.
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
