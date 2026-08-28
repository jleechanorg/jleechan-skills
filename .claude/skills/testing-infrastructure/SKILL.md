---
name: testing-infrastructure
description: Use shared testing utilities, debug protocols, and CI/local parity for WorldArchitect.AI.
---

# Testing Infrastructure

**Purpose**: Centralized testing utilities, debug protocols, and CI/local parity guidelines.

## Test Utilities (MANDATORY)

**Always use `testing_mcp/lib/` utilities - NEVER reimplement test infrastructure.**

### Available Shared Utilities

| Module | Functions |
|--------|-----------|
| `lib/evidence_utils.py` | `get_evidence_dir()`, `capture_provenance()`, `save_evidence()`, `write_with_checksum()`, `create_evidence_bundle()`, `save_request_responses()` |
| `lib/mcp_client.py` | `MCPClient(base_url, timeout)`, `client.tools_call(tool_name, args)` |
| `lib/campaign_utils.py` | `create_campaign()`, `process_action()`, `get_campaign_state()`, `ensure_game_state_seed()` |
| `lib/server_utils.py` | `start_local_mcp_server()`, `pick_free_port()`, `DEFAULT_EVIDENCE_ENV` |
| `lib/model_utils.py` | `settings_for_model()`, `update_user_settings()` |
| `lib/narrative_validation.py` | `validate_narrative_quality()`, `extract_dice_notation()` |

### Required Pattern
```python
# Import from lib modules
from testing_mcp.lib.evidence_utils import get_evidence_dir, capture_provenance
from testing_mcp.lib.mcp_client import MCPClient
from testing_mcp.lib.campaign_utils import create_campaign, process_action

# NEVER reimplement these functions
```

### Anti-Pattern
Writing custom `capture_provenance()`, `get_evidence_dir()`, `save_evidence()`, or any function that duplicates `testing_mcp/lib/` functionality.

## Browser Testing Tools

**MANDATORY GUIDANCE: Choose the right tool for the task**

### chrome-superpower (MCP Tool)
**Use for**: Exploratory manual browsing and interactive testing
- Quick browser exploration during development
- Manual testing workflows that need human guidance
- Inspecting page state and debugging UI issues
- Taking screenshots and reading page content

**DON'T use for**: Deterministic automated tests (async operations don't complete reliably)

### Playwright
**Use for**: Deterministic browser tests with validation
- Automated end-to-end test suites
- Tests that submit forms and verify streaming responses
- Tests that need to wait for async operations to complete
- CI-ready browser automation

**Pattern**:
```python
from playwright.sync_api import sync_playwright

playwright = sync_playwright().start()
browser = playwright.chromium.launch(headless=True)
context = browser.new_context()
page = context.new_page()

# Navigate and interact
page.goto(url)
page.fill("#input", "text")
page.click("button[type='submit']")

# Validate results
elements = page.query_selector_all(".story-entry")
assert len(elements) > 0, "Expected story content"
```

**Why this matters**: chrome-superpower returns immediately from async JavaScript operations (shows `[object Promise]`), making it unsuitable for tests that need to validate streaming responses. Playwright properly waits for events and async operations.

## CI/Local Parity

Mock external dependencies to ensure tests pass in both CI and local environments:

```python
with patch('shutil.which', return_value='/usr/bin/command'):
    with patch('subprocess.run') as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        # test code here
```

**Rules:**
- Mock `shutil.which()`, `subprocess.run()`, file ops
- Never rely on system state in tests
- Test files (`$PROJECT_ROOT/tests/*`) may use direct logging

## Debug Protocol

### Test Failure Debugging
- Embed debug info in assertions, not print statements
- Debugging order: Environment -> Function -> Logic -> Assertions
- Test most basic assumption first: "Does the function actually work?"

```python
# CORRECT - Debug info in assertion
debug_info = f"function_result={result}, context={context}"
self.assertTrue(result, f"FAIL DEBUG: {debug_info}")

# WRONG - Print statements (lost in CI)
print(f"Debug: {result}")
```

## Testing Protocol

**ZERO TOLERANCE:** Fix ALL test failures in CI

**LOCAL TESTING:** Don't run full test suite locally - rely on GitHub CI
- Run only SPECIFIC tests: `TESTING=true python $PROJECT_ROOT/tests/test_<specific>.py`
- GitHub CI is the authoritative source for test results

## README-aligned Runner Selection (Critical)

### `testing_mcp` suites
- Treat many `testing_mcp/*.py` files as **script entrypoints**, not pytest-collected test modules.
- Prefer direct execution:
  - `cd testing_mcp && ../vpython test_<name>.py --server http://127.0.0.1:8001`
  - `cd testing_mcp && ../vpython test_<name>.py --start-local`
  - Schema scripts: `./vpython testing_mcp/schema/test_schema_<name>.py`
- Avoid `pytest testing_mcp/...` for script-style files that parse CLI args or expect script runtime setup.

### `testing_ui` browser auth bypass
- Follow `$PROJECT_ROOT/testing_ui/README_TEST_MODE.md` exactly:
  - Start backend with `TESTING_AUTH_BYPASS=true`.
  - Open UI with `?test_mode=true&test_user_id=<id>`.
  - Verify browser flow sets/uses:
    - `window.testAuthBypass.enabled`
    - `X-Test-Bypass-Auth: true`
    - `X-Test-User-ID: <id>`
- This is mandatory for browser E2E runs that cannot inject custom auth headers directly.

## MCP Smoke Tests

```bash
MCP_SERVER_URL="https://..." MCP_TEST_MODE=real node scripts/mcp-smoke-tests.mjs
```
- Hard-fails on any non-200 response
- Results saved to `/tmp/repo/branch/smoke_tests/`

## Local-run command contract (your-project.com repo)

Moved here from `~/.claude/CLAUDE.md` and `~/.codex/AGENTS.md` on 2026-07-25 — it is repo-specific, so it does not belong in the user-global "applies to all repos" files.

When CI is stalled and you fall back to local tests, use this exact invocation contract to avoid three recurring footguns:

1. **Run via `python -m unittest`, NOT `python $PROJECT_ROOT/tests/<file>.py` directly.** Direct-file execution causes module-level `from mvp_site.rewards_engine import (_private_func_a, _private_func_b, ...)` (line 19 of `$PROJECT_ROOT/tests/test_rewards_engine.py` and similar files) to bind local names. Subsequent tests do `setattr(rewards_engine, "_private_func_a", mock)`, which updates the module attribute but NOT the test module's local binding, producing spurious `TypeError: ... got an unexpected keyword argument 'cc_finish_authorized'` failures on tests that reference the private helpers indirectly. `python -m unittest mvp_site.tests.<file>` runs each test method in isolation and avoids this pollution. Observed: PR #7888 session 2026-07-05.

   ```bash
   # CORRECT — reliable
   TESTING_AUTH_BYPASS=true vpython -m unittest mvp_site.tests.test_rewards_engine

   # WRONG — produces 14 spurious TypeError failures in TestLevelMutationGuards
   TESTING_AUTH_BYPASS=true vpython $PROJECT_ROOT/tests/test_rewards_engine.py
   ```

2. **`vpython` is a bash function, not on `$PATH`** — it lives at `~/.bashrc:677` and activates `~/projects/your-project.com/venv/`. When wrapping with `timeout` or `bash -c` the function is invisible, so use the venv python directly:

   ```bash
   PY="$HOME/projects/your-project.com/venv/bin/python"
   TESTING_AUTH_BYPASS=true timeout 90 $PY -m unittest mvp_site.tests.test_end2end.test_xxx
   ```

   The `timeout` external binary cannot see bash functions, and the embedded PATH has spaces in cmux-cli-shim directories that break `export PATH=...` inside `bash -c`.

3. **Module-level `def test_xxx` (not class methods) needs explicit discovery** — `$PROJECT_ROOT/tests/test_conclude_signal_detection.py` defines top-level `def test_*` functions instead of `class TestXxx(unittest.TestCase)`. `python -m unittest mvp_site.tests.test_conclude_signal_detection` runs 0 tests (rc=5). Use `python -m unittest -t . discover -p 'test_*.py'` to pick these up, or restructure to a class.

## Related Skills
- `evidence-standards/SKILL.md` - Evidence capture standards
- `end2end-testing/SKILL.md` - E2E test patterns
