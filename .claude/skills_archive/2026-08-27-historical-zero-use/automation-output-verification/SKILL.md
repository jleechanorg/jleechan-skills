---
name: automation-output-verification
description: "Use BEFORE running any automation loop. Requires stating the observable success output (PR, fixed test, push); rejects prediction-only loops."
---

# Automation output verification — output must be human-useful

- Before running any automation loop or pipeline, **state what success looks like** as an observable output (a PR, a fixed test, a pushed commit).
- If the output of the automation is not directly useful to a human (e.g. predictions without real code, evaluations without fixes), **the approach is wrong** — do not run it.
- If a user corrects an approach, **do not over-correct to the opposite extreme**. When in doubt, confirm the intended direction before proceeding rather than guessing.
- This rule exists because: the auto-research loop ran 26 cycles producing predictions (not PRs), and when corrected, the agent over-corrected to "no real PRs" — both wrong.
