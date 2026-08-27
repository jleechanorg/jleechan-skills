---
name: code-standards
description: User-scope code/diff/PR review against the user-wide standards — ZFC, ZFC leveling, root-cause-first, and the ponytail (lazy senior dev) ladder. Dispatched by the /code-standards command.
---

# Code Standards Dispatch

Reviews code, diffs, PRs, or proposed implementations against four
independent, user-wide standards. This skill is the source of truth for the
four-lane workflow; `~/.claude/commands/code-standards.md` is a thin
dispatcher that points here.

## Source skills (loaded by this workflow)

| Skill | Path |
|-------|------|
| Ponytail — lazy senior dev mode | `~/.claude/skills/ponytail/SKILL.md` |
| Zero-Framework Cognition (ZFC) | `~/.claude/skills/zero-framework-cognition/SKILL.md` |
| ZFC Leveling Roadmap | `~/.claude/skills/zfc-leveling-roadmap/SKILL.md` |
| Root-cause-first engineering | `~/.claude/skills/root-cause-first/SKILL.md` |

`~/.claude/skills/ponytail/SKILL.md` is the canonical mirror of
[ponytail/.github/copilot-instructions.md](https://github.com/DietrichGebert/ponytail/blob/main/.github/copilot-instructions.md).
The same skill is mirrored at `~/.codex/skills/ponytail/SKILL.md` for Codex.

## Lanes dispatched

1. **Ponytail** — the lazy-senior-dev seven-rung ladder. Stops you from
   writing code that already exists in-tree, from adding a new dependency
   when stdlib or installed packages cover it, and from chasing abstractions
   that weren't requested. Mark intentional simplifications with a
   `ponytail:` comment.
2. **ZFC** — no keyword/regex/heuristic routing in application code. Delegate
   semantic decisions to a model.
3. **ZFC leveling** — for level-up work, the model picks the target level (do
   not derive primary availability from XP thresholds).
4. **Root-cause-first** — run the skill in review-only mode: check that the
   upstream prompt/schema/agent was considered first and accept backend
   enforcement only as a narrow, logged invariant with proof. Report findings;
   do not launch `/llm-first`, `/backend-first`, experiments, or edits.

## Workflow

When invoked as `/code-standards <scope>` (or with no argument, against the
current diff/PR):

1. **Load ponytail first.** It is the *do* discipline. Read it, apply the
   seven-rung ladder to the proposed diff before any of the *check* lanes
   run.
2. **Define the review scope** from the command argument, or use the current
   diff / active PR context if no argument was supplied.
3. **Load the four source skills** by path and treat them as authoritative.
   Do not duplicate the standards into the command file — this skill file is
   the only place the standards content should live.
4. **Dispatch or emulate the four independent review lanes.** Invoke the
   root-cause-first lane in review-only mode. Each lane must return either PASS
   with file/line evidence or FAIL with the exact location and required fix.
   Rationalizations are not evidence.
5. **Reconcile** the lane results into the report format below.
6. **Do not mark any lane skipped** unless this is the explicit `smoke-test`
   mode (see below). A repo-local command may add its own `smoke-test`
   argument that proves the command file loaded without dispatching reviews.

## Report format

Reconcile the four lanes into one report:

| Lane | Verdict | Evidence (file:line) | Required fix |
|---|---|---|---|
| Ponytail | PASS/FAIL | | |
| ZFC | PASS/FAIL | | |
| ZFC leveling | PASS/FAIL/N-A | | |
| Root-cause-first | PASS/FAIL | | |

## Smoke-test mode

If the argument contains `smoke-test`, do not dispatch review lanes and do
not edit files. Instead, report:

- that the command file loaded,
- the command file path (`~/.claude/commands/code-standards.md`),
- this skill file path (`~/.claude/skills/code-standards/SKILL.md`),
- the ponytail skill path (`~/.claude/skills/ponytail/SKILL.md`),
- the marker for this revision.

This is the same convention used by repo-local `.claude/commands/code-standards.md`
files (e.g. `CODEX_CODE_STANDARDS_COMMAND_V1`). It lets a runner confirm the
command is on PATH and loadable without paying for a real review.

## Bidirectional pointer contract

The user-scope command at `~/.claude/commands/code-standards.md` is
**project-agnostic**: it applies to every repo, including ones without a
repo-local `.claude/commands/code-standards.md`. Any repo-local
`.claude/commands/code-standards.md` (for example at
`$GITHUB_REPOSITORY/.claude/commands/code-standards.md`) MUST:

1. **Load BOTH files.** State that the user-scope command at
   `~/.claude/commands/code-standards.md` / this skill are the source of
   truth for the four-lane workflow (ponytail, ZFC, ZFC leveling,
   root-cause-first).
2. **Always reference `~/.claude/skills/ponytail/SKILL.md`** so the
   lazy-senior-dev ladder is always part of the review, not a per-repo
   choice.
3. **Define repo-specific behavior** (e.g. an extra `/thermo` lane, a
   `/es` evidence rule, or a `smoke-test` marker like
   `WORLDARCHITECT_CODE_STANDARDS_COMMAND_V1`) WITHOUT forking the four
   user-scope lanes.
4. **Stay loadable in codex debug smoke-test mode** by honoring the same
   `smoke-test` argument convention.
5. **Reciprocal pointer** — the repo-local file MUST contain a
   bidirectional pointer back to `~/.claude/commands/code-standards.md`
   and document which lanes are added vs. inherited.

When invoked inside a repo with a local copy, both files load. When invoked
inside a repo without a local copy, the user-scope file is the complete
implementation. The two are intentionally designed to co-exist; do not
delete either one.

## For Codex callers

`~/.codex/commands/code-standards.md` is a thin Codex-side dispatcher that
references the same four user-scope source skills. If a repo-local
`.codex/commands/code-standards.md` exists, prefer it; otherwise the
`~/.codex` copy is the entry point.
