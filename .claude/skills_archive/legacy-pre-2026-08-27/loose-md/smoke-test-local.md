# Running Smoke Tests Locally

**Purpose**: Reproduce CI smoke test failures locally, especially for `mcp_smoke_test.sh` / SCENARIO 7 streaming contracts.

## Why tests pass locally but fail in CI

GitHub Actions runners are **ephemeral** — fresh VM, empty cache on every job. The main traps:

| Difference | Local | CI (GitHub Actions) |
|---|---|---|
| fastembed ONNX model | Cached in `/tmp/fastembed_cache/` from prior runs | Not cached → download fails → classifier falls back to `MODE_CHARACTER` |
| OS | macOS (`/var/folders/…`) | Ubuntu Linux (`/tmp/…`) |
| Services | Real Gemini / Firebase OR manual mock | `MOCK_SERVICES_MODE=true` + local Flask server |
| Secrets | From shell env or `~/.zshrc` | GitHub Secrets injected by workflow |

The `$PROJECT_ROOT/Dockerfile` pre-downloads the fastembed model at build time (line 12) so Cloud Run containers always have it. The CI smoke runner starts plain gunicorn — no Docker, no pre-downloaded model.

---

## Option 1: Nuke fastembed cache (fastest, classifier-specific)

```bash
rm -rf ~/.cache/fastembed
FASTEMBED_CACHE_PATH=~/.cache/fastembed TEST_MODE=mock ./scripts/mcp_smoke_test.sh
```

Simulates a cold CI runner. Confirms the download + pre-warm path works before trusting the cache.

---

## Option 2: Docker (closest to CI — use this for real debugging)

Runs everything inside a clean Ubuntu container — same OS, same filesystem state, no local artifacts:

```bash
docker run --rm -it \
  -e TEST_MODE=mock \
  -e MOCK_SERVICES_MODE=true \
  -e TESTING_AUTH_BYPASS=true \
  -e ALLOW_TEST_AUTH_BYPASS=true \
  -e FASTEMBED_CACHE_PATH=/root/.cache/fastembed \
  -v $(pwd):/app -w /app \
  python:3.11-slim bash -c "
    apt-get update -q && apt-get install -y -q curl git &&
    pip install -r $PROJECT_ROOT/requirements.txt -q &&
    python3 -c \"from fastembed import TextEmbedding; TextEmbedding(model_name='BAAI/bge-small-en-v1.5', cache_dir='/root/.cache/fastembed'); print('fastembed ready')\" &&
    ./scripts/mcp_smoke_test.sh
  "
```

**When to use**: Any time the CI fails but you can't repro locally. OS path differences, missing dependencies, env var issues all show up here.

---

## Option 3: `act` (run the actual workflow YAML locally)

```bash
brew install act
act issue_comment -e .github/test-events/smoke-comment.json --secret-file .env.secrets
```

**When to use**: Debugging the workflow YAML itself — `if:` conditions, step ordering, output passing between steps. NOT for debugging test logic (too much setup friction).

**Limitations**:
- Needs real secrets (GCP_SA_KEY, Gemini API key) from `.env.secrets` — not stored locally
- Pulls large runner image (~1-18GB)
- Complex event payloads needed to hit the right trigger branch in `mcp-smoke-tests.yml`

---

## Common CI failure patterns

| Symptom | Root cause | Fix |
|---|---|---|
| `god_streaming_contract: FAIL - god mode stream done payload missing god_mode_response` | Streaming endpoint bypasses `_load_campaign_and_continue_story` mock check → calls real Gemini API → no `god_mode_response` in response | Add `MOCK_SERVICES_MODE` short-circuit in `continue_story_streaming` (fixed in `5b2cccb79`) |
| `CLASSIFIER: Initialization failed after 3 attempts: NO_SUCHFILE model_optimized.onnx` | fastembed model not cached; downloads to ephemeral `/tmp` | Use `FASTEMBED_CACHE_PATH=~/.cache/fastembed` + pre-warm step (fixed in `ac2965ef3`) |
| All streaming contracts: `expected at least 2 chunk events, saw 0` | Entity tracking list-vs-dict bug causes `client_error` SSE event before any chunks | `_coerce_npc_entry_to_dict` guard in `_tier_entities` |
| Auth 401 on remote preview | `TESTING_AUTH_BYPASS` not set when `MCP_SERVER_URL` is set and `TEST_MODE=real` | Force `TESTING_AUTH_BYPASS=true` when `MCP_SERVER_URL` is set (fixed in `2b5040483`) |

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
