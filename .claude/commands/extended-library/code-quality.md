---
description: Metric-driven PR code quality review (Short variant for small PRs, Long variant for important/architectural/AI-generated PRs) — invokes the code-quality skill.
type: quality
execution_mode: immediate
---
# /code-quality

Thin slash command. Loads `.claude/skills/code-quality/SKILL.md` and runs that skill against the supplied scope (PR number, diff, or active branch).

**Usage**:
- `/code-quality` — review current diff / active branch (variant inferred from size)
- `/code-quality #<PR>` — review a specific PR (e.g. `/code-quality #6625`)
- `/code-quality path/to/file.py` — review a specific file or function
- `/code-quality <scope> --short` — force Short variant (fast, small-PR mode)
- `/code-quality <scope> --long` — force Long variant (full deep review)
- `/code-quality <scope> --pr=<owner>/<repo>/<num>` — review against an explicit PR

## Action

1. Read `.claude/skills/code-quality/SKILL.md` in full and follow it strictly.
2. Resolve scope from the command argument. If none given, use the current working diff / active PR context.
3. **Pick the variant** (Short vs Long) using the variant-selection table in the skill, unless the user passed `--short` / `--long` to force it.
4. Gather full context: pull the full functions/files for anything that appears in the diff — never compute metrics from diff hunks alone.
5. Produce the exact report format defined in the skill for the chosen variant, with `file:line` evidence for every finding.
6. If `$PROJECT_ROOT/` production code is touched, **explicitly note** that `/es` evidence is still required — this skill is supporting, not primary.

## Companion dispatch

`/code-standards` runs `/code-quality` as one of its lanes alongside `/zfc`, `/zfclevel`, `/root-cause-first`, and `/thermo`. To run just this lane, use `/code-quality` directly. `/cq` is the short alias.
