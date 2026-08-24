---
name: org-runner-audit
description: Query org-level self-hosted runners to audit runner health, labels, and registration count
type: skill
scope: repo
owner: $USER
version: 1.0.0
triggers:
  - "check runners"
  - "list runners"
  - "audit runners"
  - "runner status"
  - "org runners"
  - "self-hosted runners"
  - "see runners"
  - "query runners"
allowed-tools:
  - Bash
  - Read
  - Grep
context:
  - "gh api repos/.../actions/runners only returns REPO-level runners (insufficient for org-wide audit)"
  - "gh api orgs/.../actions/runners returns ALL org-level self-hosted runners — always use this for org runner queries"
  - "Confusion: using repo API instead of org API causes 'only 2 runners visible' problem"
  - "Memory: memory/MEMORY.md has 3 prior incidents of org-runner visibility failures (mem IDs: 0.73, 0.77, 0.78)"
  - "Current fleet (mac-1..mac-6) use ARM64 label — X64 runners are legacy and should be removed"
  - "Always verify current state at query time — do not embed runner counts or status in context"
---

# org-runner-audit — GitHub Actions Org Runner Audit

## Purpose

Query and audit all org-level self-hosted runners for jleechanorg. Avoids the common mistake of querying repo-level runners which only shows a subset.

## Trigger Detection

Any user message containing: `runner`, `self-hosted`, `org runners`, `see runners`, `query runners`, `list runners`, `check runners`, `audit runners`, `runner status`

## Audit Procedure

**Step 1: Query org-level runners (NOT repo-level)**

```bash
gh api orgs/jleechanorg/actions/runners --jq '.runners[] | {name, status, labels: [.labels[].name]}'
```

**Step 2: Identify stale/offline runners**

Offline runners (org-runner-3, org-runner-4 = X64) need investigation.

**Step 3: Report in table format**

```
| Runner | Arch | Status | Labels |
|--------|------|--------|--------|
```

## Common Failure Mode

- `gh api repos/$GITHUB_REPOSITORY/actions/runners` → only 2 repo runners
- `gh api orgs/jleechanorg/actions/runners` → all 8 org runners (correct)

## Files Referenced

- `.claude/skills/org-runner-audit.md` (this file)
- `memory/MEMORY.md` — prior incidents of org-runner visibility failures (mem IDs: 0.73, 0.77, 0.78)
