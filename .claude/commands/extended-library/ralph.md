---
description: Run Ralph automation portably across repositories with workspace targeting
type: llm-orchestration
argument-hint: '[run|status|dashboard] [max_iterations] [--workspace /path/to/repo] [--tool claude|minimax|codex|amp]'
execution_mode: llm-driven
---

# /ralph - Ralph Automation (portable across repositories)

Use this command when you need autonomous multi-iteration execution with the
portable Ralph toolkit. Ralph can target **any repository**.

## Run Ralph against any repository

1. Ensure Ralph toolkit is exported locally (from `/localexportcommands`):
   ```bash
   test -x ~/ralph/ralph.sh
   ```
2. Choose a target repository and confirm it is a git checkout:
   ```bash
   cd /path/to/target-repo
   git rev-parse --is-inside-work-tree
   ```
3. Create or customize runtime files in `~/ralph/`:
   - `~/ralph/prd.json` — If missing, `ralph.sh run` creates a minimal skeleton
     and exits; edit it with your task/branch/goal, then re-run.
   - `~/ralph/progress.txt` — Auto-created on first run if missing.
   - These state files are currently global/shared in `~/ralph`, so run one
     workspace at a time unless you intentionally swap state between runs.
4. Run Ralph and point it to the target repository via `--workspace`:
   ```bash
   # Default tool from RALPH_TOOL (default: claude)
   ~/ralph/ralph.sh run --workspace /path/to/target-repo 10

   # Explicit tools
   ~/ralph/ralph.sh run --tool claude --workspace /path/to/target-repo 10
   ~/ralph/ralph.sh run --tool codex --workspace /path/to/target-repo 10
   ~/ralph/ralph.sh run --tool amp --workspace /path/to/target-repo 10
   ```
5. Monitor status:
   ```bash
   ~/ralph/ralph.sh status --watch
   ```

## Optional: run from this repo directly

If you specifically want to run the in-repo copy:

```bash
./ralph/ralph.sh run --workspace "$PWD" 10
```

Unlike the portable `~/ralph` workflow, the in-repo copy keeps runtime state with
that repository's own Ralph directory.

## Sanity check before handoff

- Confirm the target repo is on a dedicated branch for the task.
- Confirm `progress.txt` is present (or create as needed).
- After completion, verify iteration result and return final PR/story status.
