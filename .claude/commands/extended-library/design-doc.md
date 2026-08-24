---
description: /design-doc — Product & Engineering Design Documentation (consolidated home of the retired /design command)
type: skill
execution_mode: immediate
---

# /design-doc <feature-name> [--type=feature|bugfix|migration|refactor]

Load the `design-doc` skill (Skill tool, skill name `design-doc`) and follow it exactly.

Key contract (details live in the skill — do not duplicate here):
- Run the skill's **AUTHORITATIVE ENTRY CONTRACT** first: Phase-0 exit-criteria-first via
  superpowers:brainstorming, **batch-decision mode** (answer every question yourself, present ALL
  decisions in one review table — zero one-by-one questioning).
- Then the three-doc set (no-code spec → design doc → TDD impl plan) with adversarial review
  between stages.
- If the repo has a `docs/design/*.html` style, also emit the HTML+MD pair (markdown remains the
  source of truth).

Consolidated 2026-07-11 from `~/.claude/commands/design.md` (newest source, authoritative) and the
retired `design` HTML skill; backup at `~/.claude/backups/design-consolidation-20260711-192832/`.
