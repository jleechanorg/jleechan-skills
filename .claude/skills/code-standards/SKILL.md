---
name: code-standards
description: User-scope code/diff/PR review against the user-wide standards — ZFC, ZFC leveling, root-cause-first, and the ponytail (lazy senior dev) ladder. Dispatched by the /code-standards command.
---

# Code Standards Dispatch

Reviews code, diffs, PRs or proposed implementations against four independent,
user-wide standards. This skill is the source of truth for the four-lane
workflow; `${CLAUDE_HOME:-$HOME/.claude}/commands/code-standards.md` is a thin dispatcher.

## Source skills (loaded by this workflow)

| Skill | Path |
|-------|------|
| Ponytail — lazy senior dev mode | `${CLAUDE_HOME:-$HOME/.claude}/skills/ponytail/SKILL.md` |
| Zero-Framework Cognition (ZFC) | `${CLAUDE_HOME:-$HOME/.claude}/skills/zero-framework-cognition/SKILL.md` |
| ZFC Leveling Roadmap | Optional: if an installed product plugin provides a companion `zfc-leveling-roadmap` skill, read it |
| Root-cause-first engineering | `${CLAUDE_HOME:-$HOME/.claude}/skills/root-cause-first/SKILL.md` |

`${CLAUDE_HOME:-$HOME/.claude}/skills/ponytail/SKILL.md` is the canonical mirror of
[ponytail/.github/copilot-instructions.md](https://github.com/DietrichGebert/ponytail/blob/main/.github/copilot-instructions.md).
The same skill is mirrored at `~/.codex/skills/ponytail/SKILL.md` for Codex.

## Lanes dispatched

1. **Ponytail** — the lazy-senior-dev seven-rung ladder: no rewriting code that
   exists in-tree, no new dependency when stdlib or installed packages cover
   it, no unrequested abstractions. Mark intentional simplifications with a
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

1. **Load ponytail first.** It is the *do* discipline: apply its seven-rung
   ladder to the proposed diff before any *check* lane runs.
2. **Define the review scope** from the command argument, or use the current
   diff / active PR context if no argument was supplied.
3. **Load the four source skills** by path and treat them as authoritative.
   Never duplicate the standards into the command file; they live only here.
4. **Dispatch or emulate the four independent review lanes**, root-cause-first
   in review-only mode. Each lane returns PASS with file/line evidence or FAIL
   with the exact location and required fix; rationalizations are not evidence.
5. **Reconcile** the lane results into the report format below.
6. **Do not skip a lane** outside the explicit `smoke-test` mode below. A
   lane whose row allows `N-A` may report it only with a one-line reason in
   the Evidence column.

## Report format

| Lane | Verdict | Evidence (file:line) | Required fix |
|---|---|---|---|
| Ponytail | PASS/FAIL | | |
| ZFC | PASS/FAIL | | |
| ZFC leveling | PASS/FAIL/N-A | | |
| Root-cause-first | PASS/FAIL | | |

## Smoke-test mode

If the argument is exactly `smoke-test` (not a substring match), do not
dispatch review lanes and do not edit files. Instead, report:

- that the command file loaded,
- the command file path (`${CLAUDE_HOME:-$HOME/.claude}/commands/code-standards.md`),
- this skill file path (`${CLAUDE_HOME:-$HOME/.claude}/skills/code-standards/SKILL.md`),
- the ponytail skill path (`${CLAUDE_HOME:-$HOME/.claude}/skills/ponytail/SKILL.md`),
- the marker for this revision.

Repo-local `.claude/commands/code-standards.md` files use the same convention
(e.g. `CODEX_CODE_STANDARDS_COMMAND_V1`), so a runner can confirm the command
is on PATH and loadable without paying for a real review.

## Bidirectional pointer contract

The user-scope command at `${CLAUDE_HOME:-$HOME/.claude}/commands/code-standards.md` is
**project-agnostic** and applies to every repo. Any repo-local
`.claude/commands/code-standards.md` (for example at
`$GITHUB_REPOSITORY/.claude/commands/code-standards.md`) MUST:

1. **Load BOTH files**, stating that the user-scope command / this skill are the
   source of truth for the four-lane workflow (ponytail, ZFC, ZFC leveling,
   root-cause-first).
2. **Always reference `${CLAUDE_HOME:-$HOME/.claude}/skills/ponytail/SKILL.md`** so the
   ladder is never a per-repo choice.
3. **Define repo-specific behavior** (e.g. an extra `/thermo` lane, a
   `/es` evidence rule, or a `smoke-test` marker like
   `WORLDARCHITECT_CODE_STANDARDS_COMMAND_V1`) WITHOUT forking the four
   user-scope lanes.
4. **Stay loadable in codex debug smoke-test mode** by honoring the same
   `smoke-test` argument convention.
5. **Reciprocal pointer** — the repo-local file MUST contain a
   bidirectional pointer back to `${CLAUDE_HOME:-$HOME/.claude}/commands/code-standards.md`
   and document which lanes are added vs. inherited.

With a repo-local copy, both files load; without one, the user-scope file is
the complete implementation. They are designed to co-exist; delete neither.

## For Codex callers

`~/.codex/commands/code-standards.md` is a thin Codex-side dispatcher to the
same four source skills. Prefer a repo-local `.codex/commands/code-standards.md`
when one exists; otherwise the `~/.codex` copy is the entry point.
