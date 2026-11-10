---
name: prw
description: Alias for the canonical pr-lifecycle PR workflow skill (/pr-workflow, /prw).
metadata:
  type: policy
---

# /prw — PR workflow alias

**After composing the one-line condition (read-only inspection and clause probes may come first), and before any push, label, comment or other PR-mutating action:** run `python3 -I ~/.claude/skills/cmux-goal/bin/self_goal.py set '<repo> PR <N> at <the endpoint the user requested, default FINAL_READY>, or stopped with the exact blocker only the user can clear'` (one line, no backslashes; an earlier or read-only endpoint such as "stop after Stage 0" replaces FINAL_READY; a runtime with a native goal tool uses that instead) and print its `Goal:` line verbatim.

For Codex, automatic AI review defaults to zero; evidence and self-review still run. To opt into up to two automatic reviewer assignments for a CLI session, start it with `PRW_CODEX_AI_REVIEW_COUNT=2 codex`, then invoke `/prw` inside that session. Set another non-negative integer for a different limit. See [Codex review dispatch](../pr-lifecycle/review-routing.md#codex-review-dispatch) for authorization, explicit requests and required-gate handling. Claude and agy retain their existing routes.

Then read and follow [PR Workflow Manager](../pr-workflow-manager/SKILL.md) first; it inspects repository rules and directs readers to [pr-lifecycle](../pr-lifecycle/SKILL.md) as the sole shared lifecycle contract. Apart from the goal step above, this alias adds no independent rules and takes the user's arguments as data.

[draft-first-pr](../draft-first-pr/SKILL.md) is a legacy alias. If the manager or lifecycle is unavailable, report the missing dependency rather than reconstructing stale rules.
