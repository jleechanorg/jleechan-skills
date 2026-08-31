---
description: Parallelize independent work to its real resource ceiling — not an arbitrary worker count or one-at-a-time
type: skill
execution_mode: immediate
scope: user
---
# /parallel — parallelize to ceiling

Load and follow `~/.claude/skills/parallelize-to-ceiling/SKILL.md` (Skill tool: `parallelize-to-ceiling`). Apply the decision procedure, resource-bound table, isolation invariants, and diagnostics to the work described in the argument.

**Provenance:** [Slack thread](https://jleechanai.slack.com/archives/C09GRLXF9GR/p1785477543929339?thread_ts=1785477466.893429&cid=C09GRLXF9GR) (Parallelize to Ceiling principle, landed via `/up` 2026-07-30).

## Coding and verification lane routing

For implementation and review lanes, prefer the installed AGY CLI pair before
falling back to `codexs`, `claudem`, or an own cheap agent. Use the canonical
profiles for the complete launch, logging, isolation, and signaling contracts:

- Coder: `~/.claude/agents/agy-pair-coder.md`
- Verifier: `~/.claude/agents/agy-pair-verifier.md`

### Two-agent pair template

```text
PAIR TASK: <bounded task and explicit file scope>
CODER: follow ~/.claude/agents/agy-pair-coder.md; implement and signal IMPLEMENTATION_READY.
VERIFIER: follow ~/.claude/agents/agy-pair-verifier.md; independently execute focused checks and signal VERIFICATION_COMPLETE or VERIFICATION_FAILED.
FALLBACK: if an AGY lane concretely fails, retry that lane with codexs, claudem, or an own cheap agent while preserving isolation and independent verification.
```

## Fallback precedence

The `FALLBACK` template above is governed by this order:

1. Start with the AGY pair as the primary implementation and verification lanes.
2. After a concrete AGY lane failure, retry the same bounded lane with `codexs`, starting at Spark, then advance to Luna, Terra, Sol only after concrete failure in that lane.
3. Use `claudem` or an own cheap agent only when the ordered Codex route is unavailable; preserve the same bounded scope and verification requirements.

## Isolation contract

Coder and verifier remain distinct lanes and contexts. Every retry uses a
disjoint workspace/output from the other lane, and the verifier must
independently rerun focused checks before signaling completion.

## Codex model routing

For Codex parallel lanes, use this ordered fallback and advance only after a
concrete per-lane failure:

`gpt-5.3-codex-spark` → `gpt-5.6-luna` → `gpt-5.6-terra` → `gpt-5.6-sol`

Record the rejection and retry the same bounded lane on the next model. Never
skip directly from Spark to Sol.

## Input

$ARGUMENTS
