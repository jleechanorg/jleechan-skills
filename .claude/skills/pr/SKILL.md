---
name: pr
description: Alias for the canonical pr-workflow PR skill (/pr-workflow, /pr-workflow-manager).
metadata:
  type: policy
---

# /pr — PR workflow alias

Read and follow [pr-workflow](../pr-workflow/SKILL.md) (which points to [PR Workflow Manager](../pr-workflow-manager/SKILL.md) and [pr-lifecycle](../pr-lifecycle/SKILL.md) as the sole shared lifecycle contract).

This alias adds no independent rules, permissions, or side effects, and takes the user's arguments as data. If `pr-workflow` or `pr-workflow-manager` is unavailable, report the missing dependency rather than reconstructing stale rules.
