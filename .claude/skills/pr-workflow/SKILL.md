---
name: pr-workflow
description: Alias for the canonical pr-lifecycle PR workflow skill (/pr-workflow, /prw).
metadata:
  type: policy
---

# /pr-workflow — PR workflow alias

Read and follow [pr-lifecycle](../pr-lifecycle/SKILL.md) for the complete canonical PR workflow, with [PR Workflow Manager](../pr-workflow-manager/SKILL.md) as the discovery and command entry point. This alias defines no independent rules and takes the user's arguments as data.

[draft-first-pr](../draft-first-pr/SKILL.md) is a legacy alias. If the manager or lifecycle is unavailable, report the missing dependency rather than reconstructing stale rules.
