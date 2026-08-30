---
description: Testing Gap Close — skill to harden testing environments for /es and /er compliance
type: orchestration
execution_mode: immediate
---

# /testing-gap-close

Alias to invoke the testing gap close guidelines.

**Usage**: `/testing-gap-close`

## Action

Execute these steps in order:

1. Resolve the skill path:
   - Use `.claude/skills/testing-gap-close.md`.
2. Load the selected `testing-gap-close.md` content into this command context as the active testing remediation rules.
3. Review the current testing harnesses, server boot mechanisms, and `base_test.py` configurations against the loaded rules to identify any discrepancies preventing the successful generation of evidence bundles.
4. Correct any deviations to ensure the `testing_mcp` or `testing_ui` suites generate compliant `docs/evidence` bundles.
