# Callpath trace model

A **callpath** is an ordered list of **hops** through components/services. Each hop
answers: did the request/work reach this component, and what evidence proves it?

## Hop

| Field | Meaning |
|-------|---------|
| `id` | Short hop name (e.g. `gateway`, `intake`, `ao-spawn`) |
| `component` | Service/system (e.g. `hermes-gateway`, `go-ao`, `github-api`) |
| `status` | `PASS` \| `FAIL` \| `SKIP` \| `AMBER` |
| `detail` | One-line evidence (HTTP code, process pid, log line, error) |
| `correlation` | Optional trace/request id linking to next hop |

## Verdict rollup

- **GREEN** — all critical hops PASS (SKIP ok for optional stages)
- **AMBER** — degraded but partially working
- **RED** — critical hop FAIL or missing entry evidence

## Profiles vs no profile

| Situation | Who builds the path |
|-----------|----------------------|
| **Profile** (`callpath run <name>`) | Saved `run.sh` runs fixed probes; agent interprets |
| **No profile** | **LLM fresh investigation** — discover entry + hops from code, logs, and read-only probes in the current session |

`callpath trace --hop ...` is a **recorder** for hops the agent already validated. It is not a substitute for investigation.

## Fresh investigation workflow (no profile)

1. Identify **entry** from live sources (not memory)
2. Derive **expected hops** from the actual architecture for this target
3. Gather **read-only evidence** per hop (commands, log tails, API reads)
4. Mark PASS/FAIL/SKIP; roll up verdict
5. First FAIL hop = blocker + recommended next action

Profiles automate steps 2–3 for known systems only.
