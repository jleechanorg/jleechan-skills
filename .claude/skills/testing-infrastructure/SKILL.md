---
name: testing-infrastructure
description: Use shared testing utilities, debug protocols, and CI/local parity for WorldArchitect.AI.
---

# Testing Infrastructure

**Purpose**: Centralized testing utilities, debug protocols, and CI/local parity guidelines.

## Test Utilities (MANDATORY)

Use the shared utilities owned by the test layer being exercised. For tests under
`testing_mcp/`, reuse its `lib/` utilities; for other directories, use their
scoped utilities instead of importing a service harness that does not own them.

### Available Shared Utilities

| Module | Functions |
|--------|-----------|
| `lib/evidence_utils.py` | `get_evidence_dir()`, `capture_provenance()`, `save_evidence()`, `write_with_checksum()`, `create_evidence_bundle()`, `save_request_responses()` |
| `lib/mcp_client.py` | `MCPClient(base_url, timeout)`, `client.tools_call(tool_name, args)` |
| `lib/campaign_utils.py` | `create_campaign()`, `process_action()`, `get_campaign_state()`, `ensure_game_state_seed()` |
| `lib/server_utils.py` | `start_local_mcp_server()`, `pick_free_port()`, `DEFAULT_EVIDENCE_ENV` |
| `lib/model_utils.py` | `settings_for_model()`, `update_user_settings()` |
| `lib/narrative_validation.py` | `validate_narrative_quality()`, `extract_dice_notation()` |

### `testing_mcp/` Pattern
```python
# Import from lib modules
from testing_mcp.lib.evidence_utils import get_evidence_dir, capture_provenance
from testing_mcp.lib.mcp_client import MCPClient
from testing_mcp.lib.campaign_utils import create_campaign, process_action

# NEVER reimplement these functions
```

### Anti-Pattern
For a test under `testing_mcp/`, writing custom evidence, server, client, or
campaign helpers that duplicate its `lib/` functionality. Outside that directory,
follow the local test-layer owner; do not force MCP-specific utilities onto unit,
HTTP, or browser suites.

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

For deterministic tests outside `testing_mcp/` and `testing_ui/`, mock external
dependencies when the test's claim is offline and isolated:

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

Triage CI failures against the tested SHA and change scope. Fix failures caused
by the change and follow the inherited-failure policy for failures proven outside
the change.

**LOCAL TESTING:** Do not run an unfiltered full suite locally. Run the targeted
checks selected by the repository's test owner. CI is authoritative for its
required checks; when a check is queued or pending beyond the repository's
backlog threshold, follow `/green` for its local equivalent and applicable
documentation-only exception.

## README-aligned Runner Selection (Critical)

### `testing_mcp` suites
- Resolve the project root and follow its `testing_mcp/AGENTS.md` for exact
  invocation, authentication, provider, server, and evidence requirements.
- Do not use `vpython`, change into `testing_mcp/`, collect these scripts with
  pytest, or use mock/bypass mode there. The scoped owner documents the supported
  direct `python3` + explicit-`PYTHONPATH` invocation and dedicated real account.

### `testing_ui` authentication
- Resolve the project root and follow its `testing_ui/CLAUDE.md` and linked
  `testing_mcp/AGENTS.md`. Browser acceptance uses a dedicated real account,
  real Firebase Auth, and a bypass-disabled server. Do not use `TESTING_AUTH_BYPASS`,
  `ALLOW_TEST_AUTH_BYPASS`, `?test_mode=true`, synthetic identity headers, or a
  mocked browser route for acceptance evidence. Missing credentials or account
  access is a reported blocker, not a reason to enable bypass.

## MCP Smoke Tests

```bash
MCP_SERVER_URL="https://..." MCP_TEST_MODE=real node scripts/mcp-smoke-tests.mjs
```
- Hard-fails on any non-200 response
- Results saved to `/tmp/repo/branch/smoke_tests/`

## Local test selection and runner

Resolve the current project root with `git rev-parse --show-toplevel` and follow
its `AGENTS.md`, the relevant testing-layer owner, and the current runner's help.
For this repository, use the documented targeted `./run_tests.sh <path-or-filter>`
contract; never substitute an unfiltered local full suite when CI owns it. For
`testing_mcp/` and `testing_ui/`, follow their stricter scoped owners for Python,
authentication, account, provider, server, and evidence requirements. Do not
carry forward historical home-directory interpreter paths or assume that a
shell-level `vpython` function is available inside another process.

## Related Skills
- Resolve the current evidence-standards and end-to-end testing owners through the active skill catalog.
