---
name: prw
description: Alias for the canonical pr-lifecycle PR workflow skill (/pr-workflow, /prw).
metadata:
  type: policy
---

# /prw — PR workflow alias

For Codex, applicable automatic AI review runs for up to three rounds per PR by default; evidence and self-review still run. An explicitly set `PRW_CODEX_AI_REVIEW_COUNT` applies a separate assignment ceiling, with `0` opting out. See [Codex review dispatch](../pr-lifecycle/review-routing.md#codex-review-dispatch) for round, quorum, authorization and required-gate rules. Claude and agy retain their existing routes.

Read and follow [PR Workflow Manager](../pr-workflow-manager/SKILL.md) first; it inspects repository rules and directs readers to [pr-lifecycle](../pr-lifecycle/SKILL.md) as the sole shared lifecycle contract. Apart from the Codex review-count setting above, this alias adds no independent rules and takes the user's arguments as data.

[draft-first-pr](../draft-first-pr/SKILL.md) is a legacy alias. If the manager or lifecycle is unavailable, report the missing dependency rather than reconstructing stale rules.
