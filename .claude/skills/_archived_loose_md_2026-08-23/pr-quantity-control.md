# PR Quantity Control (Harness Fix 2026-04-25)

## Overview
To prevent agent-led PR proliferation and ensure efficient feature iteration, the following rules and procedures are enforced for all Your Project development.

## Pre-Branching Check
Before creating any new PR branch (`git checkout -b`), you MUST verify the current open PR count for the relevant feature scope.

### Procedure
1. Identify the `<feature-scope>` (e.g., "zfc", "harness", "ui", "mcp").
2. Run the quantity check:
```bash
gh pr list --state open --search "<feature-scope> in:title" --json number,title --jq length
```

### Action Logic
- **If count ≥ 3**: **STOP**. You are at the concurrency limit for this scope.
  - Do NOT create a new branch or PR.
  - Find the oldest open PR for the same goal and iterate on it instead.
  - If the goals are different but the scope is the same, coordinate with the user or resolve/close an existing PR first.
- **If a prior PR was closed** for the same goal: reuse its branch or cherry-pick its commits. Do not start fresh if work has already been started elsewhere.

## PR Classification & Review Tracks
Not all PRs carry the same review/evidence bar.

- **Docs/Evidence/Test-only PRs**:
  - Lighter review track.
  - Evidence sections may be marked N/A (per PR description gate).
  - Single reviewer approval is sufficient for merge readiness.
- **Production Code Changes**:
  - Full `/green` track required (CI green + no merge conflicts; see pr-green-definition.md) plus draft-phase quality gates (`/es`, `/er`, `/advice`) before leaving DRAFT.
  - Full evidence sections required, human MERGE APPROVED before merge.

## Efficiency Targets
All agents should aim for the following performance metrics:
- **Merge Rate**: >60% (PRs merged vs. PRs opened).
- **LOC Efficiency**: >15% (lines of code meaningfully contributing to features vs. churn/boilerplate).
- **Duplicate Detection**: 0% (no redundant PRs for the same issue).

Use the `/efficiency` command to audit these targets:
```bash
# /efficiency [scope|days]
# Example: Audit zfc efficiency for the last 7 days
/efficiency zfc 7
```

## Related
- `CLAUDE.md`: Brief reference and registration of `/efficiency`.
- `.claude/commands/efficiency.md`: Executable implementation of the audit.
