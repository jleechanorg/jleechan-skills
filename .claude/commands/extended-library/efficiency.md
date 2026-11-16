---
description: Audit PR throughput, creation-to-merge duration, and stage dwell
---

# /efficiency — PR Pipeline Audit

**Skill (owner)**: `.claude/skills/pr-efficiency-audit/SKILL.md`

## Usage

- `/efficiency` — all PRs, last 7 days
- `/efficiency <scope>` — filter to scope (e.g., "zfc", "level-up")
- `/efficiency <days>` — custom time window

Follow the skill's workflow: exact UTC windows, full pagination, cohort throughput, creation-to-merge duration, and stage dwell. The skill defines the metrics and reporting format; this command carries no targets or script of its own.
