---
name: prw
description: Alias for the canonical pr-lifecycle PR workflow skill (/pr-workflow, /prw).
metadata:
  type: policy
---

# /prw — PR workflow alias

**Before any other action, including reading the manager:** run `python3 -I ~/.claude/skills/cmux-goal/bin/self_goal.py set '<repo> PR <N> at <the endpoint the user requested, default FINAL_READY>, or stopped with the exact blocker only the user can clear'` (one line, no backslashes; an earlier or read-only endpoint such as "stop after Stage 0" replaces FINAL_READY; a runtime with a native goal tool uses that instead) and print its `Goal:` line verbatim.

Then read and follow [PR Workflow Manager](../pr-workflow-manager/SKILL.md) first; it inspects repository rules and directs readers to [pr-lifecycle](../pr-lifecycle/SKILL.md) as the sole shared lifecycle contract. Apart from the goal step above, this alias adds no independent rules and takes the user's arguments as data.

[draft-first-pr](../draft-first-pr/SKILL.md) is a legacy alias. If the manager or lifecycle is unavailable, report the missing dependency rather than reconstructing stale rules.
