---
description: Switch the main thread to the Fable (latest Claude) model with strict token-economy discipline. Heavily use Haiku/Sonnet subagents; reserve the main model for hardest reasoning only.
type: workflow
execution_mode: immediate
---

# /fable [args]

Activate Fable session mode: main thread = Fable, reserved for the hardest
reasoning (novel architecture, root-cause analysis, ZFC/RCF/leveling
reviews, cross-PR synthesis, multi-step planning). Subagents default to
Haiku-first, Sonnet for implementation. Token economy is a first-class
constraint for the rest of the session.

Read `~/.claude/skills/zero-framework-cognition/SKILL.md` (section: "Related
session mode: /fable") and execute the full routing + token-economy contract
described there.

## Quick reference

| Aspect | Rule |
|---|---|
| Main thread | Fable — "figure out what to do" work only |
| Subagents | Haiku-first; Sonnet for implementation/refactor/pair-coder |
| Config | Session-level only — never edits `~/.claude/settings.json` |
| Safety | Fail-closed, `/es`, `/green`, evidence standards still required |

## Invocation

```
Genesis Coder, Prime Mover,

[/fable active] Main thread = Fable. Subagents = Haiku-first, Sonnet for implementation. Fable reserved for: novel architecture, RCF, ZFC/leveling, cross-PR synthesis, multi-step planning. Token economy rules in effect. No re-reads, no re-sweeps, no file-whole reads, parallel-where-independent.

<resume prior work or begin new task>
```

If `$ARGUMENTS` follows `/fable`, treat them as the task to begin.
