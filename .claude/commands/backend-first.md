---
description: /backend-first - prove deterministic backend behavior with an exact realistic LLM fixture
type: orchestration
execution_mode: immediate
---

# /backend-first

Resolve Claude home as `${CLAUDE_HOME:-$HOME/.claude}`. Read
**`${CLAUDE_HOME:-$HOME/.claude}/skills/backend-first/SKILL.md`** completely and
execute it according to `$ARGUMENTS`.

This command tests backend execution. It does not tune prompts or claim live
provider compliance.
