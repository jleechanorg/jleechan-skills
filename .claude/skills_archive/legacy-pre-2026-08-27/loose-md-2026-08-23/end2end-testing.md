---
description: End-to-end testing architecture, philosophy, and patterns for Your Project
type: usage
scope: project
---

# End-to-End Testing Guide

## Purpose

Provide Claude with a comprehensive reference for writing and understanding end-to-end tests in Your Project. This skill covers the testing philosophy, fake implementations, file locations, and patterns for multi-phase function testing.

## Activation Cues

- Writing or modifying E2E tests
- Adding test coverage for LLM provider functions
- Testing functions with external API dependencies
- Debugging test failures in integration tests

## Core Philosophy

**Key Principle**: Mock only **external APIs**, NOT internal service functions.

| Mock | Do NOT Mock |
|------|-------------|
| `firebase_admin.firestore.client()` | `firestore_service.py` functions |
| `google.genai.Client()` | `llm_service.py` functions |
| `requests.post()` (API calls) | `main.py` route handlers |

## Mandatory Coverage for Multi-File `mvp_site` Changes

When a PR creates or updates multiple non-test files under `$PROJECT_ROOT/**`, it must add or update at least one end-to-end test unless the PR explicitly justifies why the changed code is unreachable through an end-to-end application path.

The E2E test must:

- Exercise every newly introduced or modified production code path in the PR.
- Drive the application through the real in-process route/service flow instead of calling each helper directly.
- Assert the observable response, persisted state, emitted structured fields, or other user/server-visible effect from each changed path.
- Fail if any changed path is skipped, bypassed, or only imported.
- Remain deterministic with fake external APIs for Layer 2; add MCP/Browser `/es` evidence separately when real services or UI behavior must be proven.

Unit tests can support the change, but they do not satisfy this multi-file E2E requirement by themselves.

## Tests Are Mandatory, Not Optional

Every `/end2end-testing` invocation MUST add a new test or update an existing one. Running existing tests and reporting the results does NOT satisfy this — the agent must actually change test code.

The agent must name, in its final report:

- The exact test file path touched (e.g. `$PROJECT_ROOT/tests/test_end2end/test_god_mode_end2end.py`).
- The specific assertion added or changed (e.g. the exact `self.assertEqual(...)` / `assert ...` line).

**Anti-pattern (explicit ban):** invoking `/end2end-testing`, running `run_end2end_tests.py` or an existing suite, and reporting "N passed" as the deliverable. A green run of pre-existing tests proves nothing changed; it is not evidence the invocation did its job.

## Environment Configuration

**TESTING=true Bypass**: The `clock_skew_credentials.py` module provides unconditional bypass of all validation checks when `TESTING=true` is set. This allows hermetic test environments to run without requiring `WORLDAI_*` environment variables or triggering deployment config validation. All tests should use `TESTING=true` to ensure consistent, isolated test execution.

## Test File Locations

```
$PROJECT_ROOT/tests/
├── test_end2end/                           # Primary E2E directory (14 test files + runner)
│   ├── run_end2end_tests.py                # Test runner script
│   ├── test_continue_story_end2end.py      # Story continuation flow
│   ├── test_create_campaign_end2end.py     # Campaign creation flow
│   ├── test_debug_mode_end2end.py          # Debug mode functionality
│   ├── test_embedded_json_narrative_end2end.py  # JSON embedded in narratives
│   ├── test_entity_tracking_budget_end2end.py   # Entity tracking with budget limits
│   ├── test_god_mode_end2end.py            # God mode (DM powers) testing
│   ├── test_llm_provider_end2end.py        # LLM provider switching tests
│   ├── test_mcp_error_handling_end2end.py  # MCP error scenarios
│   ├── test_mcp_integration_comprehensive.py # Comprehensive MCP integration
│   ├── test_mcp_protocol_end2end.py        # MCP protocol compliance
│   ├── test_npc_death_state_end2end.py     # NPC death state persistence
│   ├── test_timeline_log_budget_end2end.py # Timeline logging with budgets
│   ├── test_visit_campaign_end2end.py      # Campaign visit/load flow
│   └── test_world_loader_e2e.py            # World loader with file caching
├── test_code_execution_dice_rolls.py       # Dice/tool loop tests
├── fake_firestore.py                       # Fake implementations
└── integration/
    └── test_real_browser_settings_game_integration.py
```

### Test Descriptions

| Test File | Purpose |
|-----------|---------|
| `run_end2end_tests.py` | Test runner script for executing all E2E tests |
| `test_continue_story_end2end.py` | Validates story continuation with LLM responses, state updates |
| `test_create_campaign_end2end.py` | Tests full campaign creation flow from API to Firestore |
| `test_debug_mode_end2end.py` | Debug mode UI and logging functionality |
| `test_embedded_json_narrative_end2end.py` | JSON data embedded within narrative text parsing |
| `test_entity_tracking_budget_end2end.py` | Entity tracking system with token budget constraints |
| `test_god_mode_end2end.py` | DM/God mode features - override dice, spawn entities |
| `test_llm_provider_end2end.py` | Switching between LLM providers (Gemini, OpenAI) |
| `test_mcp_error_handling_end2end.py` | Error handling in MCP tool execution |
| `test_mcp_integration_comprehensive.py` | Full MCP server integration testing |
| `test_mcp_protocol_end2end.py` | MCP JSON-RPC protocol compliance |
| `test_npc_death_state_end2end.py` | NPC death persistence across sessions |
| `test_timeline_log_budget_end2end.py` | Timeline/event logging with budget limits |
| `test_visit_campaign_end2end.py` | Loading existing campaigns from Firestore |
| `test_world_loader_e2e.py` | World loader integration with file cache system |

## Claude Commands

| Command | Mode | Description |
|---------|------|-------------|
| `/teste` | Mock | Fast E2E tests with fake services |
| `/tester` | Real | Full E2E with real Firestore + Gemini |
| `/testerc` | Real + Capture | Real mode with data capture |
| `/4layer` | TDD | Four-layer testing protocol |

## Fake Implementations

### Why Fake Instead of Mock?

Using `Mock()` or `MagicMock()` causes JSON serialization errors when mocked data flows through the application. Use fake implementations that return real Python data structures.

```python
# BAD: Returns Mock objects - will cause JSON serialization errors
mock_doc = Mock()
mock_doc.to_dict.return_value = {"name": "test"}

# GOOD: Returns real dictionaries
fake_doc = FakeFirestoreDocument()
fake_doc.set({"name": "test"})
```

### Available Fakes

- `FakeFirestoreClient` — Mimics Firestore client behavior (`fake_firestore.py`)
- `FakeFirestoreDocument` — Returns real dictionaries
- `FakeFirestoreCollection` — Handles nested collections
- `FakeLLMResponse` — Shallow SDK stub, legacy tests (`fake_llm.py`)
- `RealisticFakeLLMResponse` — SDK-faithful structure, new tests (`fake_llm_realistic.py`)

## Response Fidelity Levels

The two LLM fakes differ in how faithfully they mirror the real `google.genai` SDK response shape.
Choose based on what the test is verifying.

### Level 1 — `FakeLLMResponse` (legacy, shallow)

```python
from mvp_site.tests.fake_llm import FakeLLMResponse
mock_gemini_generate.return_value = FakeLLMResponse(json.dumps(payload))
```

**Structure shortcut:** `candidates = [self]` — the response object IS also the candidate
AND the content. Duck-typing means `candidates[0].content.parts` accidentally resolves
to `self.parts` via `self.content = self`, so `_get_text_from_response()` works, but:

- `usage_metadata` has **wrong field names**: `input_tokens`/`output_tokens` instead of
  `prompt_token_count`/`candidates_token_count`/`total_token_count`
- No `finish_reason` attribute on the candidate
- `FakePart` has no `executable_code` or `code_execution_result` attrs (code_execution path)

**Use when**: the test only needs a valid JSON response to flow through — it does not
inspect usage metadata, finish reason, or code_execution parts.

### Level 2 — `RealisticFakeLLMResponse` (SDK-faithful)

```python
from mvp_site.tests.fake_llm_realistic import RealisticFakeLLMResponse, make_realistic_fake

# Default fixture (real prod Gemini 3 Flash response, truncated):
mock_gemini_generate.return_value = make_realistic_fake()

# Custom payload + realistic token counts:
mock_gemini_generate.return_value = RealisticFakeLLMResponse(
    json.dumps(payload),
    prompt_token_count=45_000,
    candidates_token_count=800,
)

# Code_execution path (stub dice parts prepended):
mock_gemini_generate.return_value = make_realistic_fake(
    json_text=json.dumps(payload), with_dice=True
)
```

**Correct structure:**

```
response.candidates[0]                       ← _FakeCandidate
    .content                                 ← _FakeContent
        .parts[0]                            ← _FakePart (optional: executable_code)
        .parts[1]                            ← _FakePart (optional: code_execution_result)
        .parts[-1].text                      ← JSON string (the game response)
    .finish_reason = "STOP"
response.usage_metadata.prompt_token_count
response.usage_metadata.candidates_token_count
response.usage_metadata.total_token_count
```

**Fixture provenance:** `FIXTURE_STORY_RESPONSE_TEXT` was extracted from a real
Gemini 3 Flash prod response captured in
`/tmp/your-project.com/unknown/test_level_up_organic/iteration_001/llm_request_responses.jsonl`.
The keys (narrative, session_header, entities_mentioned, location_confirmed,
state_updates, planning_block) match the live production schema.

**Use when**: the test verifies code that reads `usage_metadata.prompt_token_count`,
`finish_reason`, or iterates `candidates[0].content.parts` (e.g. code_execution
result extraction in `gemini_code_execution.py`).

## Realistic Fake LLM Responses Must Come From Real BQ Traffic

**Scope**: this section governs fixtures under `$PROJECT_ROOT/mocks/*`
(`mock_llm_service.py`, `data_fixtures.py`, `structured_fields_fixtures.py`,
and any `RealisticFakeLLMResponse`/`make_realistic_fake()` payload used in
Layer 1/2 mock-mode tests). It does **NOT** license mocks in `testing_mcp/`
or `testing_ui/` — those stay real-services-only per the repo `CLAUDE.md`
Operations Guide (mock-mode env vars are forbidden there; see
`.claude/skills/testing-infrastructure.md` and `testing_mcp/CLAUDE.md`).

### Why real BQ traffic

Hand-written fake LLM JSON drifts from what the model actually emits — field
sets, string lengths, nesting — and tests built on drifted fixtures pass
against production regressions they should catch. Sourcing fixtures from
real forensic traffic keeps mock-mode tests honest.

### Verified recipe

Dataset: `worldarchitecture-ai.llm_forensics` (project
`worldarchitecture-ai`, NOT `ai-universe-2025`). Two tables: `llm_payloads`
(raw request/response, used here) and `log_events` (structured events). A
0-row result from one table is not proof the data doesn't exist in the
other.

```bash
bq --project_id=worldarchitecture-ai --quiet --headless query --nouse_legacy_sql \
  --format=json --max_rows=5 'SELECT agent, model, event_type, output_tokens,
  SUBSTR(response_text,1,400) AS sample FROM
  `worldarchitecture-ai.llm_forensics.llm_payloads` WHERE
  event_type="gameplay_streaming" AND finish_reason="FinishReason.STOP"
  ORDER BY ingested_at DESC LIMIT 5'
```

Parse the JSON output (skip the `bq` CLI's leading status text):

```python
raw = open(output_file).read()
i = raw.find('[{')
rows = json.loads(raw[i:])
```

`request_json` parses to top-level keys `model`, `contents`, `config`.
`contents[0]` is itself a **JSON string** (not a dict) — `json.loads()` it a
second time to get the real request payload. Verified fields on a
`GodModeAgent` row (checked 2026-07-25): `game_mode`, `user_id`,
`selected_prompts`, `use_default_world`, `story_history`, `core_memories`,
`sequence_ids`, `checkpoint_block`, `current_turn`, `user_scene_number`,
`entity_tracking`, `game_state`, `user_action`, `dynamic_instructions`,
`priority_instruction`, `message_type`.

### Mandatory PII scrubbing

Before any BQ-sourced payload is committed as a fixture:

- **Strip**: `user_id`, real player names appearing in
  `story_history`/`narrative` text, email addresses.
- **May keep**: `campaign_id` (not personally identifying on its own).
- Replace stripped values with clearly-fake placeholders
  (`"user_id": "test-user-fixture-001"`) — never leave a field in a shape
  that no longer matches what real traffic looks like.

### Fixture completeness rule

A fixture must populate **every field** that real traffic for that agent
populates — not a trimmed-down subset. An incomplete fixture (missing
`entity_tracking`, `checkpoint_block`, etc.) lets code that reads those
fields pass tests it should fail against. Use the verified field list above
(or re-run the recipe for a different agent) to check completeness before
committing a fixture.

### Worked example — GodModeAgent

```python
# $PROJECT_ROOT/mocks/data_fixtures.py (illustrative — use placeholders, never
# paste a real user's campaign prose into the repo)
GODMODE_FIXTURE_REQUEST = {
    "game_mode": "god",
    "user_id": "test-user-fixture-001",  # scrubbed from a real user_id
    "selected_prompts": ["narrative", "mechanics"],
    "use_default_world": False,
    "story_history": [
        {"text": "Placeholder story beat consistent with a real story_history entry."}
    ],
    "core_memories": [],
    "sequence_ids": [],
    "checkpoint_block": "Placeholder checkpoint summary text.",
    "current_turn": 1,
    "user_scene_number": 1,
    "entity_tracking": {"active_entities": []},
    "game_state": {"world_data": {"world_time": {"year": 1, "time_of_day": "morning"}}},
    "user_action": "GOD MODE: placeholder directive text",
    "dynamic_instructions": "placeholder",
    "priority_instruction": "placeholder",
    "message_type": "god_mode_turn",
}
```

### Three measurement traps (verified 2026-07-25)

When querying `llm_payloads` to build or validate fixtures, or to compute
any defect-rate/frequency claim from it:

1. **Every real turn writes TWO rows** — `event_type` `gameplay_streaming`
   AND `stream_story_with_game_state`. Filter to exactly one `event_type`,
   or every count silently doubles.
2. **`finish_reason` splits one `event_type` into incompatible payload
   shapes** — `'FinishReason.STOP'` vs `'success'` carry different fields.
   Do not pool rows across `finish_reason` values.
3. **The `is_test` column is UNRELIABLE**: 499 obviously-synthetic turns
   were found flagged `is_test=FALSE`. Also exclude `user_id` matching
   `^(lean_lu_|browser-test-|test-|e2e)` when selecting "real" traffic for a
   fixture.

## Firestore Structure

The app uses nested collections - tests must replicate this:

```
users/
  {user_id}/
    campaigns/
      {campaign_id}
```

## Multi-Phase Function Testing

For functions like `generate_content_with_tool_requests()` that make multiple API calls:

### Pattern: Use `side_effect` for Sequential Responses

```python
@patch('requests.post')
def test_two_phase_flow(self, mock_post):
    # Phase 1 response: JSON with tool_requests
    phase1_response = Mock()
    phase1_response.status_code = 200
    phase1_response.json.return_value = {
        "choices": [{"message": {"content": json.dumps({
            "narrative": "...",
            "tool_requests": [{"tool": "roll_dice", "args": {"dice_notation": "1d20"}}]
        })}}]
    }

    # Phase 2 response: Final JSON without tool_requests
    phase2_response = Mock()
    phase2_response.status_code = 200
    phase2_response.json.return_value = {
        "choices": [{"message": {"content": json.dumps({
            "narrative": "You rolled a 15!",
            "planning_block": {"thinking": "..."}
        })}}]
    }

    # Sequential responses
    mock_post.side_effect = [phase1_response, phase2_response]

    # Call the function - it will make 2 API calls
    result = generate_content_with_tool_requests(...)

    # Verify both calls were made
    assert mock_post.call_count == 2

    # Verify Phase 2 received tool results
    phase2_call_args = mock_post.call_args_list[1]
    messages = json.loads(phase2_call_args.kwargs['json']['messages'])
    assert 'roll_dice result' in str(messages)
```

### Test Coverage Paths

For multi-phase functions, test each path:

1. **No tool_requests** - Returns Phase 1 directly
2. **With tool_requests** - Executes tools, makes Phase 2 call
3. **Invalid JSON** - Returns response as-is
4. **Tool execution errors** - Errors captured in results
5. **Helper functions** - Test `execute_tool_requests()` separately

## Running Tests

```bash
# All E2E tests (mock mode)
./claude_command_scripts/teste.sh

# Specific test file
TESTING=true python3 -m pytest $PROJECT_ROOT/tests/test_code_execution_dice_rolls.py -v

# Specific test class
TESTING=true python3 -m pytest $PROJECT_ROOT/tests/test_code_execution_dice_rolls.py::TestToolRequestsFlow -v

# With coverage
./run_tests_with_coverage.sh
```

## Runner Split: pytest vs script entrypoints

`testing_mcp/README.md` defines many MCP suites as direct-run scripts. Use this split:

- Use `pytest` for:
  - `$PROJECT_ROOT/tests/...`
  - `tests/test_end2end/...`
  - Regular unit/integration modules designed for pytest collection
- Use direct script execution (`vpython <file>.py`) for:
  - `testing_mcp/test_*_real_*.py`
  - `testing_mcp/schema/test_schema_*.py`
  - Other `testing_mcp` files that implement CLI `argparse` + `main()`

Examples:

```bash
# MCP script-style suite (correct)
cd testing_mcp
../vpython test_social_encounter_real_api.py --start-local

# Schema script-style suite (correct)
cd $PROJECT_ROOT
./vpython testing_mcp/schema/test_schema_enforcement_journey_real_api.py --work-name schema_enforcement_run
```

## Flask API End2End Test Pattern (MANDATORY)

**All API-level end2end tests MUST follow this pattern.** Located in `$PROJECT_ROOT/tests/test_end2end/`.

### Required Environment Variable

```python
# CORRECT - Use TESTING_AUTH_BYPASS
os.environ["TESTING_AUTH_BYPASS"] = "true"

# WRONG - Don't use just TESTING
os.environ["TESTING"] = "true"  # ❌ Not sufficient for API tests
```

### Required Imports and Base Class

Use the shared base class in `$PROJECT_ROOT/tests/test_end2end/__init__.py` to avoid duplicating
Flask app + auth setup. Subclasses must set `CREATE_APP` and `AUTH_PATCH_TARGET` and can
override `TEST_USER_ID` when needed.

```python
import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ["TESTING_AUTH_BYPASS"] = "true"
os.environ.setdefault("GEMINI_API_KEY", "test-api-key")

# Path setup
PROJECT_ROOT = Path(__file__).resolve().parents[3]
MVP_SITE_ROOT = PROJECT_ROOT / "mvp_site"
for path in (PROJECT_ROOT, MVP_SITE_ROOT):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

from main import create_app  # noqa: E402
from tests.fake_firestore import FakeFirestoreClient  # noqa: E402
from tests.test_end2end import End2EndBaseTestCase  # noqa: E402
```

### Required Test Class Pattern

```python
class TestFeatureEndToEnd(End2EndBaseTestCase):
    """Descriptive docstring for the test class."""

    CREATE_APP = create_app
    AUTH_PATCH_TARGET = "main.auth.verify_id_token"
    TEST_USER_ID = "feature-e2e-user"

    def setUp(self):
        super().setUp()

        # Use FakeFirestore (MANDATORY)
        self.fake_firestore = FakeFirestoreClient()
        self._db_patcher = patch(
            "firestore_service.get_db", return_value=self.fake_firestore
        )
        self._db_patcher.start()
        self.addCleanup(self._db_patcher.stop)

        # Headers for API requests
        self.headers = self.test_headers

    def test_feature_roundtrip(self):
        """Test the feature saves and retrieves correctly."""
        # POST to save
        save_resp = self.client.post(
            "/api/endpoint", data=json.dumps({"field": "value"}), headers=self.headers
        )
        assert save_resp.status_code == 200, f"Save failed: {save_resp.data}"

        # GET to retrieve
        get_resp = self.client.get("/api/endpoint", headers=self.headers)
        assert get_resp.status_code == 200
        data = json.loads(get_resp.data)
        assert data.get("field") == "value"
```

### Pattern Checklist

| Requirement | Status |
|-------------|--------|
| `TESTING_AUTH_BYPASS=true` env var | ✅ Required |
| `unittest.TestCase` base class | ✅ Required |
| `FakeFirestoreClient` for database | ✅ Required |
| `patch("main.auth.verify_id_token")` | ✅ Required |
| `create_app()` + `test_client()` | ✅ Required |
| `addCleanup()` for patchers | ✅ Required |
| Debug info in assertions | ✅ Required |

## Best Practices

### DO:
- Mock at the external API boundary (`requests.post`, `firestore.client()`)
- Use `side_effect` for sequential mock responses
- Test all code paths (success, error, edge cases)
- Verify intermediate data passed between phases
- Check call arguments to ensure context is preserved

### DON'T:
- Mock internal service functions (`generate_content_with_tool_requests`)
- Use `Mock()` for data that will be JSON serialized
- Skip testing error paths
- Assume LLM responses are deterministic

## Related Documentation

- `.claude/skills/testing-layers/SKILL.md` — Layer decision framework: when to use E2E (Layer 2) vs Unit (Layer 1) vs MCP/Browser (Layer 3+)
- `$PROJECT_ROOT/tests/README_END2END_TESTS.md` - Full E2E philosophy
- `$PROJECT_ROOT/tests/README.md` - Test coverage overview
- `.claude/commands/teste.md` - Mock mode command
- `.claude/commands/tester.md` - Real mode command
- `.claude/commands/4layer.md` - Four-layer TDD protocol
