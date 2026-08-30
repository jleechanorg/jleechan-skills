---
description: Breadth-first research on a topic and ingest results into the LLM wiki. Usage: /wiki-bfs <topic> [--layers N] [--ingest]. Wiki path resolves from .wiki-default in CWD, then ~/.wiki-default, then ~/llm_wiki/wiki. --wiki flag always wins.
type: skill
execution_mode: immediate
---

Read `${CLAUDE_HOME:-$HOME/.claude}/skills/extended-library/SKILL.md` and `references/extended-library/wiki-bfs.md` completely, then execute it with `$ARGUMENTS`.
