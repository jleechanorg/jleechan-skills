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
  - "Runner names, counts, architectures, and label policy come from the org's API response and runner config, never from this file"
  - "Always verify current state at query time — do not embed runner counts or status in context"
---

# org-runner-audit — GitHub Actions Org Runner Audit

## Purpose

Query and audit all org-level self-hosted runners for `$GITHUB_ORG`. Avoids the common mistake of querying repo-level runners which only shows a subset.

## Trigger Detection

Any user message containing: `runner`, `self-hosted`, `org runners`, `see runners`, `query runners`, `list runners`, `check runners`, `audit runners`, `runner status`

## Audit Procedure

**Step 0: Resolve the org**

```bash
GITHUB_ORG="${GITHUB_ORG:-${GITHUB_REPOSITORY%%/*}}"
[ -n "$GITHUB_ORG" ] || GITHUB_ORG="$(gh repo view --json owner -q .owner.login 2>/dev/null || true)"
[ -n "$GITHUB_ORG" ] || { echo "GITHUB_ORG not configured: GitHub org that owns the runners. Example: export GITHUB_ORG=my-org" >&2; exit 1; }
```

**Step 1: Query org-level runners (NOT repo-level)**

```bash
gh api --paginate "orgs/$GITHUB_ORG/actions/runners" --jq '.runners[] | {name, status, os, labels: [.labels[].name]}'
```

**Step 2: Identify stale/offline runners**

Every runner whose `status` is not `online` needs investigation. Compare
architecture labels against the org's own runner policy rather than a fleet
list remembered from an earlier audit:

```bash
gh api --paginate "orgs/$GITHUB_ORG/actions/runners" --jq '.runners[] | select(.status != "online") | .name' | LC_ALL=C sort
```

**Step 3: Report in table format**

```
| Runner | Arch | Status | Labels |
|--------|------|--------|--------|
```

## Common Failure Mode

- `gh api repos/$GITHUB_REPOSITORY/actions/runners` → only 2 repo runners
- `gh api "orgs/$GITHUB_ORG/actions/runners"` → all org runners (correct; `.total_count` is the fleet size)

## Files Referenced

- `.claude/skills/org-runner-audit/SKILL.md` (this file)
