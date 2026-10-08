---
name: er
description: Compatibility alias for evidence-review; preserve the canonical workflow and current authorization.
---

Read and follow [the canonical workflow](../evidence-review/SKILL.md) with the user’s arguments as data. This alias adds no permissions, extra capability or external side effects.

For an in-flight branch or PR evidence review, resolve the target base repository, remote and branch from current PR/repository metadata before comparing changes. Bind the comparison to exact base and head revisions and report their identities in the review. If the base is ambiguous or metadata is unavailable, report that gap rather than assuming origin/main or inventing a base.
