---
description: /root-cause-first - diagnose and route an LLM/backend boundary failure
type: orchestration
execution_mode: immediate
---

# /root-cause-first

Resolve Claude home as `${CLAUDE_HOME:-$HOME/.claude}`. Read
**`${CLAUDE_HOME:-$HOME/.claude}/skills/root-cause-first/SKILL.md`** completely
and execute it according to `$ARGUMENTS`.

This command diagnoses the first divergence. It routes the work to
`/llm-first`, `/backend-first`, or a fail-closed `UNDER-INSTRUMENTED` report. It
does not edit prompt/schema or backend behavior.
