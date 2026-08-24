---
name: pr-efficiency-audit
description: Audit PR merge rate, LOC efficiency, and duplicate detection for a feature area over a time window
---

# /efficiency — PR Efficiency Audit

Measures merge rate, LOC landing rate, and duplicate PR detection for a given scope.

## Usage

- `/efficiency` — audit all PRs in last 7 days
- `/efficiency zfc` or `/efficiency level-up` — audit a specific feature scope
- `/efficiency 14` — audit last 14 days

## Protocol

### Step 1: Gather data

```bash
# All PRs (excluding autor benchmarks) in time window
gh pr list --state all --search "created:>=<DATE> <SCOPE>" --limit 200 \
  --json number,state,title,mergedAt,additions,deletions,changedFiles

# Production-only merged PRs (fix/feat/refactor prefix)
# Filter for files matching $PROJECT_ROOT/ excluding tests/
```

### Step 2: Compute metrics

| Metric | Formula | Target |
|--------|---------|--------|
| Merge rate | merged / (merged + closed + open) | >60% |
| LOC efficiency | net production lines on main / total LOC written | >15% |
| Duplicate rate | PRs closed for same goal as a merged PR / total | <10% |
| Production ratio | production PRs merged / total PRs merged | >40% |
| Open queue depth | currently open PRs for scope | ≤3 |

### Step 3: Detect duplicates

Group closed PRs by similar title/scope. Flag when 2+ PRs target the same logical change and only one merged.

### Step 4: Report

Output a table with:
- Headline numbers (merge rate, LOC efficiency, duplicate rate)
- Top 5 wasted PRs by LOC (closed without merge, highest additions)
- Currently open PR queue with overlap detection
- Comparison to targets (pass/fail)

### Step 5: Recommend

If any target is missed:
- Merge rate <60%: identify why PRs are being abandoned (duplicates? review bottleneck? scope creep?)
- LOC efficiency <15%: identify where LOC is going (docs? tests? abandoned code?)
- Duplicate rate >10%: list the duplicate groups and recommend closing the older/smaller ones
- Open queue >3: recommend which to close or consolidate

## Baseline (2026-04-25)

First audit established these baseline numbers for ZFC level-up:
- Merge rate: 49% (target: 60%)
- LOC efficiency: 3.3% (target: 15%)
- Duplicate rate: ~15% (target: 10%)
- Production ratio: 23/61 = 38% (target: 40%)
- Open queue: 6 real + 4 CodeRabbit auto (target: ≤3)
