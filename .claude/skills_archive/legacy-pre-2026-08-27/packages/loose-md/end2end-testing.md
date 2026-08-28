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

### Available Fakes (fake_firestore.py)

- `FakeFirestoreClient` - Mimics Firestore client behavior
- `FakeFirestoreDocument` - Returns real dictionaries
- `FakeFirestoreCollection` - Handles nested collections
- `FakeLLMResponse` - Simple response with text attribute

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

- `$PROJECT_ROOT/tests/README_END2END_TESTS.md` - Full E2E philosophy
- `$PROJECT_ROOT/tests/README.md` - Test coverage overview
- `.claude/commands/teste.md` - Mock mode command
- `.claude/commands/tester.md` - Real mode command
- `.claude/commands/4layer.md` - Four-layer TDD protocol
