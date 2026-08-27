---
name: callpath
description: General read-only execution tracer. Profiles automate known systems; without a profile the LLM must fresh-investigate entry→hops→blocker from live evidence. Triggers on /callpath, trace execution, where stuck.
---
# /callpath — execution tracer (general)

Trace where work entered, which components handled it, and where it stalled — **any repo or multi-service stack**.

## Two modes (pick one)

### A) Profile exists → run saved probes

```bash
callpath list
callpath run <profile> [args...]
```

Profiles automate recurring multi-hop checks (`dark-factory`, future `hermes-request`, etc.). Run the profile, interpret stdout, extend only if gaps remain.

### B) No profile → **fresh LLM investigation** (required)

**Do not** skip to `callpath trace` with guessed hops. **Do not** reuse prior chat conclusions, memory, or “usual” paths without re-verifying in **this** session.

The agent must **investigate from scratch**:

1. **Discover entry** — find how work entered *right now* (PR/issue, request id, session id, log `trace_id`, bead id, webhook, cron, user action). Read configs, code paths, recent logs, `gh`, `ao`, health endpoints as needed.
2. **Derive hops from evidence** — list components **in order** based on what you find (not a template). Follow the actual call stack / request path for this target.
3. **Probe each hop read-only** — run commands, read logs, inspect state. Every PASS/FAIL must cite **fresh output** from this investigation.
4. **Roll up** — verdict GREEN/AMBER/RED; name **first FAIL hop** as blocker + one next action.

Optional: after investigating, document probes with:

```bash
callpath trace --title "..." --hop 'id:component:cmd' ...
```

That command **records** hops you already validated — it does **not** replace investigation.

## Model

`entry → hop₁ → hop₂ → … → outcome` — see `schema/trace-model.md`.

## Profiles

`profiles/<name>/profile.yaml` + `run.sh`. Copy `profiles/_template/` for new systems.

**dark-factory** (one profile among many):

```bash
callpath run dark-factory --prs 8058,8060
```

## Output format (agent reply)

```markdown
# /callpath — <timestamp> — verdict=<GREEN|AMBER|RED>
entry: <correlation id + how you found it>

## Hops
  <id>   <status>  [<component>] <one-line fresh evidence>

blocker: <first FAIL hop or "none">
next: <one concrete read-only or operator step>
```

## NEVER

- Mutate state during `/callpath`
- Treat dark-factory as the only callpath
- **No-profile path:** fabricate hops, skip live probes, or paraphrase old session results as evidence
