---
name: smoke-test-local
description: Reproduce WorldArchitect.AI CI smoke-test failures in a clean local environment.
---

# Running Smoke Tests Locally

**Purpose**: Reproduce CI smoke test failures locally, especially for `mcp_smoke_test.sh` / SCENARIO 7 streaming contracts.

## Why tests pass locally but fail in CI

GitHub Actions runners are **ephemeral** — fresh VM, empty cache on every job. The main traps:

| Difference | Local | CI (GitHub Actions) |
|---|---|---|
| fastembed ONNX model | Cached in `/tmp/fastembed_cache/` from prior runs | Not cached → download fails → classifier falls back to `MODE_CHARACTER` |
| OS | macOS (`/var/folders/…`) | Ubuntu Linux (`/tmp/…`) |
| Services | Real service test or an offline-only harness check | Use the current `testing_mcp/AGENTS.md` contract for `testing_mcp/`; mocks belong in permitted offline test directories |
| Secrets | Existing process environment or an approved secure credential store | GitHub Secrets injected by workflow |

The `$PROJECT_ROOT/Dockerfile` pre-downloads the fastembed model at build time (line 12) so Cloud Run containers always have it. The CI smoke runner starts plain gunicorn — no Docker, no pre-downloaded model.

---

## Option 1: Nuke fastembed cache (fastest, classifier-specific)

Do not run the historical `scripts/mcp_smoke_test.sh` mock invocation as
acceptance evidence. For an offline classifier/cache check, locate a deterministic
test in a permitted offline test directory and follow that directory's runner
instructions; do not use mock mode for tests under `testing_mcp/` or `testing_ui/`.
Resolve the project root and follow `testing_mcp/AGENTS.md` before any test whose
entrypoint or helper lives under `testing_mcp/`.

---

## Option 2: Reproduce the CI environment

Inspect the current workflow file and use its actual container image, commands,
and test target. The former generic Docker recipe invoked a mocked `testing_mcp`
smoke path and is not valid acceptance evidence; do not reuse it. When the claim
is an offline deterministic classifier/cache behavior, use an allowed offline
test target. For service, auth, provider, or UI claims, use the scoped
`testing_mcp/AGENTS.md` or `testing_ui/CLAUDE.md` contract and preserve its real
service requirements.

---

## Option 3: `act` (run the actual workflow YAML locally)

```bash
act issue_comment -e .github/test-events/smoke-comment.json
```

**When to use**: Debugging the workflow YAML itself — `if:` conditions, step ordering, output passing between steps. NOT for debugging test logic (too much setup friction).

**Limitations**:
- If the workflow requires secrets, supply them only through an existing approved secure credential store or process environment supported by the tool. Never create, read, or use a `.env` file for secrets. If no supported secure input is available, use the authorized CI workflow or report this local route unavailable.
- Use an already available `act` binary; this workflow does not authorize installing tools.
- Pulls large runner image (~1-18GB)
- Complex event payloads needed to hit the right trigger branch in `mcp-smoke-tests.yml`

---

## Historical CI failure patterns — verify before applying

The examples below preserve prior incident context; they are not current
implementation instructions or permission to add a mock path. Recheck the current
source and follow root-cause-first guidance before proposing a fix. Any mock-based
test located under `testing_mcp/` or `testing_ui/` is not valid acceptance proof;
offline mocks belong in allowed deterministic test directories.

| Symptom | Root cause | Fix |
|---|---|---|
| `god_streaming_contract: FAIL - god mode stream done payload missing god_mode_response` | Streaming endpoint bypasses `_load_campaign_and_continue_story` mock check → calls real Gemini API → no `god_mode_response` in response | Add `MOCK_SERVICES_MODE` short-circuit in `continue_story_streaming` (fixed in `5b2cccb79`) |
| `CLASSIFIER: Initialization failed after 3 attempts: NO_SUCHFILE model_optimized.onnx` | fastembed model not cached; downloads to ephemeral `/tmp` | Use `FASTEMBED_CACHE_PATH=~/.cache/fastembed` + pre-warm step (fixed in `ac2965ef3`) |
| All streaming contracts: `expected at least 2 chunk events, saw 0` | Entity tracking list-vs-dict bug causes `client_error` SSE event before any chunks | `_coerce_npc_entry_to_dict` guard in `_tier_entities` |
| Auth 401 on remote preview | Real test-account authentication is missing or invalid | Verify the dedicated test account and server logs. For `testing_mcp/` runs, keep `TESTING_AUTH_BYPASS=false` and `ALLOW_TEST_AUTH_BYPASS=false`; report missing real-auth prerequisites instead of enabling bypass |

---

## Relevant files

- `scripts/mcp_smoke_test.sh` — main orchestrator; starts local Flask server if no `MCP_SERVER_URL`
- `.github/workflows/mcp-smoke-tests.yml` — CI workflow; mock + fallback jobs
- `testing_mcp/test_smoke.py` — SCENARIO 7: streaming chunk timing contracts
- `$PROJECT_ROOT/mocks/mock_llm_service.py` — mock LLM responses for `MOCK_SERVICES_MODE=true`
- `$PROJECT_ROOT/intent_classifier.py` — FastEmbed classifier; `_FASTEMBED_CACHE_DIR` constant
- `$PROJECT_ROOT/Dockerfile` — pre-downloads fastembed model at build time (line 12)
- `$PROJECT_ROOT/llm_service.py:_build_mock_streaming_text` — mock response for streaming path in mock mode
- `$PROJECT_ROOT/llm_service.py:continue_story_streaming` — streaming path; has `MOCK_SERVICES_MODE` check before provider selection

## Architecture: mock mode and streaming endpoints

The non-streaming endpoint (`/api/campaigns/<id>/interaction`) calls `world_logic._load_campaign_and_continue_story` which checks `MOCK_SERVICES_MODE` and redirects to `continue_story` (non-streaming) when true.

The streaming endpoint (`/api/campaigns/<id>/interaction/stream`) calls `streaming_orchestrator.stream_story_with_game_state` → `llm_service.continue_story_streaming` **directly**, bypassing the `_load_campaign_and_continue_story` mock check. So `MOCK_SERVICES_MODE` must also be checked inside `continue_story_streaming`.
