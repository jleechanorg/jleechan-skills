---
description: /callpath — trace execution across hops, services, and call stacks (read-only)
type: skill
execution_mode: immediate
---

# /callpath [profile|target] [args]

Read-only execution tracer. Two paths — never mix them up.

### 1. Profile matches the target

```bash
callpath list
callpath run <profile> $ARGUMENTS
```

Run saved probes; interpret stdout. Example: `callpath run dark-factory --prs 8058,8060`.

### 2. No matching profile → **fresh investigation** (mandatory)

**You** must discover the path in **this** session. Do **not**:

- Reuse prior conversation verdicts without re-probing
- Run `callpath trace` with invented/guessed hops before investigating
- Copy hop lists from SKILL examples without validating them for this target

**Do:**

1. Find **entry** (PR, session, request id, logs, config, code) — cite how
2. Map **actual hops** from live evidence (code + logs + read-only CLI)
3. Probe each hop; every status line needs **fresh command/log output**
4. Report verdict, first FAIL blocker, next action

Optionally record validated hops: `callpath trace --hop 'id:component:cmd' ...`

Full rules: `~/.claude/skills/callpath/SKILL.md`
