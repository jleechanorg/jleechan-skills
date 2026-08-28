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
