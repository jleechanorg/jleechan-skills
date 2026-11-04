---
name: ui-bug-proof
description: "Use BEFORE claiming a UI bug fix is complete. Enforces RED-before-GREEN: reproduce the bug, verify the broken element, disclose environment gaps."
---

# UI bug fix proof — reproduce the bug before claiming the fix


**RED before GREEN — see `~/.claude/skills/evidence-standards/SKILL.md#ui-changes-require-a-genuine-implementation-beforeafter-comparison` for the full checklist.** Key rule: prove the bug is reproducible in the test environment first; verify the exact broken element (not its parent container); disclose any environment gaps (auth bypass, empty cache, JS-applied theme). "Tool compliant" (Playwright headless) ≠ "proof adequate" — the question is whether the test environment could reproduce the reported failure.
