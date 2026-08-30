---
description: /llm-first - isolate and prove real-provider contract compliance
type: orchestration
execution_mode: immediate
---

# /llm-first

Resolve Claude home as `${CLAUDE_HOME:-$HOME/.claude}`. Read
**`${CLAUDE_HOME:-$HOME/.claude}/skills/llm-first/SKILL.md`** completely and
execute it according to `$ARGUMENTS`.

All workflow policy lives in the skill; this command only resolves and invokes
that canonical owner.
