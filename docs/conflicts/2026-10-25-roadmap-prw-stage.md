# Merge resolution: roadmap-prw-stage-20261025 — 2026-10-25

Merged `origin/roadmap-prw-stage-20261025` into the local roadmap skill branch.

## `.claude/skills/roadmap/SKILL.md`

- Hunk group 1 (workflow discovery and invocation contract): **Combined** — kept the
  upstream relative `../pr-workflow-manager/SKILL.md` discovery and verified-alias
  wording, then retained the local task's mandatory `/prw` requirement for every
  invocation, status-only owner preservation, proof-gated advancement, and explicit
  earliest-unmet mismatch reporting.

## Tests

- Before: `python3 ~/.codex/skills/.system/skill-creator/scripts/quick_validate.py .claude/skills/roadmap` → `Skill is valid!` after merge resolution.
- After: `python3 ~/.codex/skills/.system/skill-creator/scripts/quick_validate.py .claude/skills/roadmap` → `Skill is valid!`; focused contract assertions and `git diff --check` also passed.
