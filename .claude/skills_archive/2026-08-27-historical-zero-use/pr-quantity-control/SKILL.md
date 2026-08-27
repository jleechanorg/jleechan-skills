---
name: pr-quantity-control
description: "Use BEFORE creating a new PR. Checks existing open PRs in same scope; stops at ≥3; rebase/cherry-pick from closed PRs instead of duplicating."
---

# PR quantity control — iterate, don't proliferate


Before creating any new PR branch, check for existing open PRs in the same scope:
```bash
gh pr list --state open --search "<scope> in:title" --json number --jq length
```

**Rules:**
- If **≥3 open PRs** exist for the same feature scope: **STOP**. Update the oldest open PR instead of creating a new one.
- If a prior PR was closed for the same logical goal: rebase/cherry-pick from it, don't start from scratch.
- If you are about to create a PR with a title very similar to an existing open or recently-closed PR, that is a **duplicate** — work on the existing one.
- **Docs/evidence/test-only PRs**: separate from production review pipeline where possible.

**Efficiency targets** (run `/efficiency` to check):
- Merge rate: >60%
- LOC efficiency (net production LOC on main / total LOC written): >15%
- Open PR queue per feature scope: ≤3

**Why**: 7-day audit (2026-04-25) showed 3.3% LOC efficiency, 49% merge rate on ZFC PRs. Same change attempted 2-3 times across different PRs. Quality gates × uncontrolled PR volume = review bottleneck → abandonment → more PRs.
