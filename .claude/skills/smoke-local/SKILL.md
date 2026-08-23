---
name: smoke-local
description: Run /smoke-local — boot the real local MCP backend through the test harness, route all LLM calls through the agy CLI provider (never mock, never direct Gemini), play a new campaign to character level 4, and probe combat/spell/inventory/NPC-dialog narrative liveness. Use when the user says /smoke-local, "run the local smoke", "smoke the agy path locally", or wants an on-demand local provider-path proof against the real agy LLM.
---

# /smoke-local — Real Local Server + agy Provider Smoke

## Purpose

Prove the full local game path works against the **real agy CLI LLM provider** — not
mocks, not the direct Gemini SDK. A single `/smoke-local` run:

1. Starts a REAL local dev server (auto-started by the test on a free port, same
   `mvp_site` backend `local.sh` runs).
2. Activates the agy provider so every LLM call is routed through the `agy` binary.
3. Creates a NEW campaign and drives the character to **level 4**.
4. Probes several more core-game prompts beyond leveling (combat, spells,
   inventory, NPC dialog) and requires a real narrative for each.
5. Writes an evidence bundle and reports PASS/FAIL.

This is the on-demand entry point. The same flow also runs automatically on a cadence
(see [Cadence](#cadence-automatic)).

## NO-MOCK CONTRACT (a run is VOID if any of these hold)

Real server + real **agy** LLM + real Firestore, always. The run is invalid if any of
these env vars are set: `MOCK_SERVICES_MODE`, `TEST_MODE=mock`, `USE_MOCK_FIREBASE`,
`USE_MOCK_GEMINI`, `FORCE_TEST_MODEL=true`, or `SMOKE_TOKEN`. Auth is via
`TESTING_AUTH_BYPASS=true` + `ALLOW_TEST_AUTH_BYPASS=true` only.

The LLM path MUST be agy. `$PROJECT_ROOT/llm_providers/provider_gateway.py ::
is_agy_provider_mode()` is DEFAULT-ON for local dev, but it only returns `True` when
`AGY_RUNTIME_HOME` is a valid existing directory — otherwise it falls back to the
Gemini SDK. Sourcing the env file (Step 2) is what makes that directory exist and
turns agy on. If you skip the `source`, you silently test Gemini, not agy.

## The exact flow

Run from the session worktree root (which can be resolved via `git rev-parse --show-toplevel`).

### Step 1 — build the sanitized agy HOME + env file

```bash
bash $PROJECT_ROOT/install.sh --no-validate   # fast: skips the live agy auth probe
# or, for full validation including a live agy call:
bash $PROJECT_ROOT/install.sh
```

`install.sh` creates the sanitized `HOME` at `/tmp/agy-clean-home-v1` and writes
`/tmp/agy-clean-home-v1/worldai-agy.env`. That env file exports:

| Var | Value | Meaning |
|-----|-------|---------|
| `AGY_PROVIDER_ENABLED` | `1` | agy provider on |
| `AGY_RUNTIME_HOME` | `/tmp/agy-clean-home-v1` | sanitized HOME (gates `is_agy_provider_mode()`) |
| `AGY_BINARY` | `$HOME/.local/bin/agy` | the agy CLI |
| `AGY_TIMEOUT_SECONDS` | `900` | per-call LLM timeout (agy is slower than SDK) |
| `WORLDAI_FIRESTORE_TRANSPORT` | `rest` | Firestore over REST |
| `WAITLIST_MODE_ENABLED` | `false` | no waitlist gate locally |

Use `--no-validate` for a quick setup that skips the live agy auth check; omit it for a
full validation that includes a real agy round-trip.

### Step 2 — activate the agy provider

```bash
source /tmp/agy-clean-home-v1/worldai-agy.env
```

The test (Step 3) inherits these env vars and passes them to the real local server
it auto-starts, so the entire game path routes LLM calls through agy.

### Step 3 — run the smoke test (it auto-starts its own real local server)

```bash
TESTING_AUTH_BYPASS=true ALLOW_TEST_AUTH_BYPASS=true \
  GOOGLE_APPLICATION_CREDENTIALS="$HOME/serviceAccountKey.json" \
  PYTHONPATH="$(pwd):$(pwd)/mvp_site" \
  python3 testing_mcp/core/test_smoke_local.py
```

`MCPTestBase` auto-starts a REAL local server on a free port using the same
`mvp_site` backend `start_local_mcp_server` the rest of the suite uses, inheriting
the agy env so LLM calls route through the agy CLI, and tears it down on exit.

**Do NOT pass `--server`.** An external server started by `local.sh` never receives
`MCP_TEST_PROVIDER_HTTP_CAPTURE_PATH` (only the auto-started server does), so no agy
provider transport trace is written and the strict evidence bundle cannot be produced
— see **bead rev-siu48**. `local.sh --force-default-port --no-log-stream` is still the
way to eyeball the interactive dev UI (backend `8081` / React `3002`); it just is not
the evidence path.

Per `testing_mcp/CLAUDE.md`, `testing_mcp` tests run with `python3` and an explicit
`PYTHONPATH` (`<root>:<root>/mvp_site`) — **never `vpython`**, never `pytest`, never
mock mode. The runtime guard (`testing_mcp/lib/server_utils.py`
`_assert_no_mock_services()`) hard-fails if any mock flag is set.

### Step 4 — what the test proves (real agy LLM, real Firestore)

The test creates a NEW campaign and uses prompts oriented toward these user stories from
`docs/user-stories-general.md`:

| User story | Behavior exercised |
|-----------|--------------------|
| **US-005 / US-006** | Level up the character all the way to **level 4** (primary anchor). |
| **US-001 prompt** | Submit a combat action and require a non-trivial real agy narrative. |
| **US-009 prompt** | Submit a spell action and require a non-trivial real agy narrative. |
| **US-010 prompt** | Submit an inventory action and require a non-trivial real agy narrative. |
| **US-017 prompt** | Submit an NPC-dialog action and require a non-trivial real agy narrative. |

Only the level-4 transition is a mechanics assertion. The four follow-up scenarios
are provider-path liveness probes; the dedicated suites own their deeper mechanics.

Evidence bundle is written to `/tmp/<repo>/<branch>/test_smoke_local/latest/`
(e.g. `/tmp/your-project.com/smoke-local-command/test_smoke_local/latest/`).

### Step 5 — report PASS/FAIL

Report the overall verdict with the full absolute evidence bundle path. The test tears
down its own auto-started server on exit — no manual teardown needed. (If you also ran
`local.sh` interactively, stop it with `lsof -ti :8081 -sTCP:LISTEN | xargs kill`.)

### agy reliability notes (why the test retries)

The agy CLI intermittently prepends async task-orchestration noise
(`**SYSTEM NOTE:** Waiting for command execution completion…`) ahead of the gameplay
JSON on character code-execution turns, which the provider's normalizer rejects
(0 chunks, streaming transport error). The test recovers this with bounded retries
(`_ACTION_MAX_ATTEMPTS`) — each gameplay turn ends in a real agy response. It also sets
`REQUIRE_AGY_SUCCESS = False` so the strict agy evidence validator tolerates those
retry-recovered per-turn errors (the trace must still carry real agy request+response
traffic). The `rewards_box` structured field on the level-up turn is a soft observation
(agy structured output is weaker than Gemini); reaching **level 4** is the hard bar.
Underlying findings: beads **rev-v7lfb** (agy invalid output) and **rev-siu48** (strict
validator + `--server` capture gap).

## Cadence (automatic)

`/smoke-local` also runs unattended on a cadence — after **5 new main commits OR one hour**,
whichever fires first. That is driven by a machine-local launchd job plus a wrapper
script `scripts/smoke_local_cadence.sh`, installed from a git-tracked plist template
(per the `launchd-plist-template` skill: the plist template lives in this repo). The
wrapper runs the same Steps 1–6 above. This skill and the `/smoke-local` command are
the manual/on-demand path; the cadence automation is built separately and is not
invoked by this command.

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| Test silently uses Gemini, not agy | Step 2 `source` skipped, or `/tmp/agy-clean-home-v1` missing | Re-run `install.sh` then `source` the env file; confirm `AGY_RUNTIME_HOME` exists |
| `_assert_no_mock_services` aborts the run | A mock env var is set | Unset `MOCK_SERVICES_MODE` / `TEST_MODE` / `USE_MOCK_*` / `SMOKE_TOKEN` |
| Auto-started server never becomes healthy | A stale test server / port collision | `pkill -f "mvp_site.main serve"`, then re-run the test |
| `AGY provider transport trace` / `Missing provider transport trace` bundle error | Ran with `--server` (external) — capture env not wired | Drop `--server`; let the test auto-start its server (bead rev-siu48) |
| agy calls time out | agy is slower than the SDK | `AGY_TIMEOUT_SECONDS=900` from the env file must be active; keep the source in scope |
| 401 on interaction | Auth bypass not set | Ensure `TESTING_AUTH_BYPASS=true` + `ALLOW_TEST_AUTH_BYPASS=true` |

## Relevant files

- `.claude/commands/smoke-local.md` — the `/smoke-local` command (this skill backs it).
- `$PROJECT_ROOT/install.sh` — builds `/tmp/agy-clean-home-v1` + `worldai-agy.env`.
- `$PROJECT_ROOT/llm_providers/provider_gateway.py` — `is_agy_provider_mode()` (agy gate).
- `testing_mcp/core/test_smoke_local.py` — the smoke driver (built in a sibling lane).
- `testing_mcp/lib/server_utils.py` — local backend launcher and no-mock runtime guard.
- `scripts/smoke_local_cadence.sh` — cadence wrapper (built in a sibling lane).
- `docs/user-stories-general.md` — US-001/005/006/009/010/017 definitions.
