---
description: Assess wiki structure and ratios against Karpathy pattern standards. Wiki path resolves from .wiki-default in CWD, then ~/.wiki-default, then ~/llm_wiki/wiki. --wiki flag always wins.
type: skill
execution_mode: immediate
---

Read `${CLAUDE_HOME:-$HOME/.claude}/skills/extended-library/SKILL.md` and `references/extended-library/wiki-assess.md` completely, then execute it with `$ARGUMENTS`.
