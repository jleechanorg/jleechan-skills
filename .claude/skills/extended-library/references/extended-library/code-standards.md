---
description: "Project-agnostic /code-standards — review code, diffs, PRs, or proposed implementations against the user-wide standards (ZFC, ZFC leveling, root-cause-first, ponytail). The repo-local command at .claude/commands/code-standards.md (when present in the working repo) ADDS repo-specific behavior and MUST be loaded alongside this one."
type: quality
execution_mode: immediate
---

# /code-standards [scope]

> This is the **project-agnostic** `/code-standards` command, at
> `~/.claude/commands/code-standards.md`. It applies to every repo — including
> ones without a repo-local `.claude/commands/code-standards.md`.
>
> **Bidirectional pointer contract:**
> 1. If the working repo has its own `.claude/commands/code-standards.md`,
>    load **BOTH** this file AND the repo-local one. The repo-local file is
>    allowed to add repo-specific lanes (e.g. `/thermo`, repo-specific smoke
>    markers, repo-specific example scopes) but MUST NOT redefine the four
>    user-scope lanes — those live here.
> 2. The repo-local file MUST contain a reciprocal pointer back to this file
>    so the two stay synchronized.
> 3. If a repo-local file is absent, this file is the complete implementation.

Read `~/.claude/skills/code-standards/SKILL.md` and execute the four-lane
workflow (ponytail, ZFC, ZFC leveling, root-cause-first) against `<scope>`,
or the current diff/PR if no scope is given.

## Quick reference (lanes are user-scope, NOT repo-specific)

| Lane | Skill |
|---|---|
| Ponytail (do discipline) | `~/.claude/skills/ponytail/SKILL.md` |
| ZFC | `~/.claude/skills/zero-framework-cognition/SKILL.md` |
| ZFC leveling | `~/.claude/skills/zfc-leveling-roadmap/SKILL.md` |
| Root-cause-first | `~/.claude/skills/root-cause-first/SKILL.md` |

If a repo-local command adds extra lanes (e.g. `/thermo`), they layer on top
of the four above — they do not replace them.

## Flags

- `smoke-test` — load-only check; reports command/skill paths and revision
  marker without dispatching review lanes or editing files. The repo-local
  command may define its own marker, but `smoke-test` mode semantics are
  shared.

## Examples

```
/code-standards
/code-standards <relative/path/to/file>
/code-standards <branch-or-pr>
/code-standards smoke-test
```

Always pair this command with the repo-local `.claude/commands/code-standards.md`
when one exists in the working repo. The two are intentionally designed to
co-exist; do not delete either one.

## For Codex callers

`~/.codex/commands/code-standards.md` is the Codex-side dispatcher. If a
repo-local `.codex/commands/code-standards.md` exists, prefer it; otherwise
load `~/.codex/commands/code-standards.md` and follow the same bidirectional
contract above.