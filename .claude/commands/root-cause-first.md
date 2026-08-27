---
description: /root-cause-first - diagnose and route an LLM/backend boundary failure
type: orchestration
execution_mode: immediate
---

# /root-cause-first

Resolve Claude home as `${CLAUDE_HOME:-$HOME/.claude}`. Read
**`${CLAUDE_HOME:-$HOME/.claude}/skills/root-cause-first/SKILL.md`** completely
and execute it according to `$ARGUMENTS`.

This command diagnoses the first divergence. In direct diagnostic mode it may
hand the task to `/llm-first` or `/backend-first` after the route verdict; the
router itself does not edit prompt/schema or backend behavior. When loaded by
a review or audit consumer, it runs in review-only mode and stops after the
verdict and findings. `UNDER-INSTRUMENTED` always fails closed.
