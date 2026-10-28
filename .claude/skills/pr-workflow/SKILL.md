---
name: pr-workflow
description: Alias for the canonical pr-lifecycle PR workflow skill (/pr-workflow, /prw).
metadata:
  type: policy
---

# /pr-workflow — PR workflow alias

Read and follow [PR Workflow Manager](../pr-workflow-manager/SKILL.md) first; it inspects repository rules and directs readers to [pr-lifecycle](../pr-lifecycle/SKILL.md) as the sole shared lifecycle contract. This alias adds no independent rules and takes the user's arguments as data.

[draft-first-pr](../draft-first-pr/SKILL.md) is a legacy alias. If the manager or lifecycle is unavailable, report the missing dependency rather than reconstructing stale rules.
