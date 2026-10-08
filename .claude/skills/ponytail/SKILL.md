---
name: ponytail
description: Lazy senior-dev mode — the seven-rung ladder that decides whether to write code at all, whether to reuse code that already exists, and whether to prefer stdlib/platform/installed deps over a new dependency. Use before writing any code, every PR diff, every fix, every feature. Source attribution included.
metadata:
  source: https://github.com/DietrichGebert/ponytail/blob/main/.github/copilot-instructions.md
---

# Ponytail

Understand the request and trace the affected flow before choosing an implementation.
Use the first sufficient option in this ladder:

1. Avoid building something the task does not need.
2. Reuse the codebase's existing implementation or pattern.
3. Use a standard-library facility.
4. Use a native platform capability.
5. Use a dependency already installed.
6. Prefer a simple expression when it handles the relevant cases correctly.
7. Add only the remaining necessary code.

For bugs, trace callers and fix the shared cause. Keep the diff small without
sacrificing correctness, security, accessibility, or protection against data loss.
Avoid unnecessary dependencies, abstractions, and boilerplate. Document meaningful
limitations when deliberately simplifying a solution. Verify nontrivial behavior
with the smallest runnable check that would detect a failure; trivial changes do
not need a new testing framework.

This is the canonical user-scope skill; repository pointers and the Codex symlink
resolve here. Adapted from [DietrichGebert's Ponytail instructions](https://github.com/DietrichGebert/ponytail/blob/main/.github/copilot-instructions.md).
