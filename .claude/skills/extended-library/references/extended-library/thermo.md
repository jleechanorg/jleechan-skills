---
description: Run a strict, high-conviction maintainability and structural code quality review on files, PRs, or branches using the thermo-nuclear rubric.
aliases: [thermo-nuclear-review, thermonuclear]
type: skill
execution_mode: immediate
---

# /thermo [path | branch | pr]

Run an extremely strict maintainability and structural review for abstraction quality, giant files, and spaghetti-condition growth using the thermo-nuclear rubric.

Read `~/.claude/skills/thermo-nuclear-code-quality-review/SKILL.md` and execute the full workflow with the provided target.

## Usage

| Command | Reviews |
|---------|---------|
| `/thermo <path-to-file>` | Specific file |
| `/thermo <branch-or-pr>` | Changes in a branch or PR |
| `/thermo .` | Current directory/workspace changes |

## Rubric highlights

1. **Code Judo**: prefer solutions that make code dramatically simpler — delete whole branches, helpers, or layers.
2. **Decompose files over 1k lines**: no PR should push a file from under 1k to over 1k lines without a compelling structural reason.
3. **No random spaghetti growth**: reject ad-hoc conditionals, nullable flags, special cases, one-off branches in unrelated flows.
4. **Boundary and type cleanliness**: flag casts, `any`, `unknown`, and ad-hoc object shapes that obscure real invariants.
5. **Canonical layers and modularity**: feature logic must not leak into shared paths; details must not leak through APIs.

Provide direct, serious, demanding feedback on structural quality, ordering findings strictly as specified in the rubric.
