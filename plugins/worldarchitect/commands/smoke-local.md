---
description: /smoke-local - REAL local server + agy LLM smoke: new campaign → level 4 + combat/spell/inventory/dialog
type: testing
execution_mode: immediate
---
## ⚡ EXECUTION INSTRUCTIONS FOR CLAUDE
**When this command is invoked, YOU (Claude) must execute these steps immediately.**
**This is NOT documentation — these are COMMANDS to run right now, in order.**

`/smoke-local` boots the REAL local MCP backend through the test harness's
`start_local_mcp_server` helper, activates the **agy CLI LLM provider** (NOT mock,
NOT direct Gemini SDK), plays a NEW campaign through to
**character level 4**, and probes several more core-game prompts. It writes an
evidence bundle and reports PASS/FAIL.

### NO-MOCK CONTRACT (a run is VOID if violated)
Real local server + real **agy** LLM + real Firestore only. NEVER set
`MOCK_SERVICES_MODE`, `TEST_MODE=mock`, `USE_MOCK_FIREBASE`, `USE_MOCK_GEMINI`,
`FORCE_TEST_MODEL=true`, or `SMOKE_TOKEN`. Auth uses `TESTING_AUTH_BYPASS=true` +
`ALLOW_TEST_AUTH_BYPASS=true` only. The agy provider MUST be the active LLM path —
verify `is_agy_provider_mode()` is True (it is DEFAULT-ON for local dev, but only
activates when `AGY_RUNTIME_HOME` points at a valid existing dir, which is exactly
what the sourced env file guarantees).

### RUN THESE STEPS
```bash
cd "$(git rev-parse --show-toplevel)"   # session worktree root

# Step 1 — build the sanitized agy HOME + env file (add --no-validate to skip the
# live agy auth check for a fast setup; omit it for full validation).
bash $PROJECT_ROOT/install.sh --no-validate

# Step 2 — activate the agy provider (exports AGY_PROVIDER_ENABLED=1,
# AGY_RUNTIME_HOME=/tmp/agy-clean-home-v1, AGY_BINARY, AGY_TIMEOUT_SECONDS=900,
# WORLDAI_FIRESTORE_TRANSPORT=rest, WAITLIST_MODE_ENABLED=false).
source /tmp/agy-clean-home-v1/worldai-agy.env

# Step 3 — run the smoke test. It AUTO-STARTS its own REAL local server (the same
# mvp_site backend local.sh runs, via start_local_mcp_server, on a free port),
# inheriting the agy env from Step 2, and tears the server down on exit. Do NOT
# pass --server: an external local.sh server never receives the provider-capture
# env, so no agy evidence trace is written and the run cannot pass (bead rev-siu48).
TESTING_AUTH_BYPASS=true ALLOW_TEST_AUTH_BYPASS=true \
  GOOGLE_APPLICATION_CREDENTIALS="$HOME/serviceAccountKey.json" \
  PYTHONPATH="$(pwd):$(pwd)/mvp_site" \
  python3 testing_mcp/core/test_smoke_local.py
```

To eyeball the interactive dev UI while iterating, you can separately run
`./local.sh --force-default-port --no-log-stream` (backend :8081, React :3002) —
but the smoke test's own auto-started server is what produces the evidence bundle.

### Step 4 — what the test does (real agy LLM, real Firestore)
Creates a NEW campaign, proves the character reaches **level 4** (US-005/006),
then submits combat, spell, inventory, and NPC-dialog prompts and requires a real,
non-trivial agy narrative for each. Those follow-up checks are provider-path
liveness coverage; they do not assert the deeper mechanics of US-001/009/010/017.

Evidence bundle → `/tmp/<repo>/<branch>/test_smoke_local/latest/`.

### Step 5 — report
Report **PASS/FAIL** with the full absolute evidence bundle path. The test tears
down its own auto-started server on exit, so no manual teardown is needed. (If you
also started `local.sh` interactively in Step 3's note, stop it with
`lsof -ti :8081 -sTCP:LISTEN | xargs kill 2>/dev/null || true`.)

### Cadence (automatic, not this command's job)
`/smoke-local` is ALSO run on a cadence — after **5 new main commits OR one hour**,
whichever fires first — via a machine-local launchd job + wrapper
(`scripts/smoke_local_cadence.sh`, installed from a git-tracked plist template).
That automation is built separately; this command is the manual/on-demand entry point.

### Full rules
See the authoritative skill: `.claude/skills/smoke-local/SKILL.md`
