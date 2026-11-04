---
name: user-story-worldai
description: Resolve WorldArchitect-specific user-story guidance from the target repository and pair it with the portable general user-story skill.
---

# WorldArchitect user-story resolver

This exported skill is a portable entry point, not a copy of WorldArchitect's
product rules or historical evidence. The target WorldArchitect repository owns
those details; the general `user-story` skill owns shared story, visual, and
design-system practice.

## Resolve the target repository

1. Identify the target product checkout from the current working directory or
   other verified repository context for this task. Confirm its repository root
   before resolving local instructions. Do not infer the target from this
   exported skill's own location, a hardcoded machine path, or a remembered
   checkout path.
2. In that target repository, look for
   `.claude/skills/user-story-worldai/SKILL.md`. Read that companion when it
   exists. It is the source for product-specific document locations, evidence
   sources, historical findings, and known traps.
3. Read the portable `user-story` skill from the active skill catalog as well.
   Apply its general story and visual rules together with the target
   repository's companion; neither replaces the other.
4. If the target repository or its companion cannot be verified or found,
   report that scoped discovery gap. Continue only with guidance available from
   the general `user-story` skill, and do not invent WorldArchitect product
   paths, evidence requirements, history, or behavior.

The companion must be resolved inside the target product repository, not by
following this exported resolver back to itself. If more than one plausible
target checkout is present and the active task context does not identify one,
state the ambiguity instead of selecting a machine-specific path.
