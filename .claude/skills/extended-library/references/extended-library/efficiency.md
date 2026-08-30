---
description: Audit PR merge rate, LOC efficiency, and duplicate detection
---

# /efficiency — PR Pipeline Audit

**Skill**: `.claude/skills/pr-efficiency-audit.md`

## Usage

- `/efficiency` — all PRs, last 7 days
- `/efficiency <scope>` — filter to scope (e.g., "zfc", "level-up")
- `/efficiency <days>` — custom time window

Run the audit script:

```bash
./scripts/efficiency_audit.sh "$SCOPE" "$DAYS"
```

Report as table with pass/fail against targets:

| Metric | Target | Actual | Status |
|--------|--------|--------|--------|
| Merge rate | >60% | | |
| LOC efficiency | >15% | | |
| Duplicate rate | <10% | | |
| Production ratio | >40% | | |
| Open queue depth | ≤3 | | |

End with actionable recommendations if any target is missed.
