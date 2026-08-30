---
description: Ingest a file into the local LLM wiki — creates source/entity/concept pages. Wiki path resolves from .wiki-default in CWD, then ~/.wiki-default, then ~/llm_wiki/wiki. --wiki flag always wins.
type: skill
execution_mode: immediate
---

Read `${CLAUDE_HOME:-$HOME/.claude}/skills/extended-library/SKILL.md` and `references/extended-library/wiki-ingest.md` completely, then execute it with `$ARGUMENTS`.
