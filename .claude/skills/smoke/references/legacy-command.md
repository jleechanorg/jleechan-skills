---
description: Run MCP smoke tests against preview server or local instance
type: tool
scope: project
---

# /smoke - MCP Smoke Tests Command

## Purpose
Execute MCP smoke tests against deployed preview servers or local instances. Supports both mock and real API modes.

## Activation
User types `/smoke` or explicitly requests MCP smoke tests to be run.

## Usage Modes

### 1. Against Preview Server (Real APIs)

**CORRECTION (2026-07-18): an earlier version of this doc wrongly claimed the
`/smoke` PR-comment trigger was removed. It was not — it was moved to a
central router, `.github/workflows/comment-router.yml`, which listens for
`/smoke`, `/dice`, `/levelup` etc. and dispatches the matching workflow via
`workflow_dispatch`.** Verify the dispatch actually fired (`gh run list
--workflow mcp-smoke-tests.yml`, filter `event=workflow_dispatch` +
`actor=github-actions[bot]`) before assuming a `/smoke` comment was a no-op —
as of 2026-07-18 the router's own ack-comment step was failing with `403
Resource not accessible by integration` (missing `issues: write` — fixed in
[PR #8434](https://github.com/$GITHUB_REPOSITORY/pull/8434)), so a
`/smoke` comment could dispatch the real run successfully while LOOKING like
nothing happened (no confirmation comment posted). **Do not re-dispatch via
`workflow_dispatch` just because no ack comment appeared** — check for an
existing `mcp-smoke-tests.yml` run for the PR's head SHA first; a duplicate
dispatch burns a second real-Gemini-API smoke run for no reason (confirmed
real incident: 3 duplicate real-mode runs, PRs #8265/#8292/#8328, same day).

There is also no `manual-mcp-smoke-tests.yml` file; the real workflow is
`.github/workflows/mcp-smoke-tests.yml`.

Direct `workflow_dispatch` remains available as a fallback/explicit path when
you specifically want `test_mode=real` and don't want to wait on the comment
router, or need to target a `pr_number` a comment can't cleanly express.
`gh workflow run` needs a working GraphQL bucket to resolve the default
branch — if GraphQL is rate-limited, dispatch via REST directly instead:

```bash
# Preferred (needs GraphQL headroom):
gh workflow run mcp-smoke-tests.yml --repo $GITHUB_REPOSITORY \
  -f pr_number=<PR_NUMBER> -f test_mode=real

# REST fallback (works even when GraphQL is exhausted):
gh api repos/$GITHUB_REPOSITORY/actions/workflows/mcp-smoke-tests.yml/dispatches \
  -X POST -f ref=main -f "inputs[pr_number]=<PR_NUMBER>" -f "inputs[test_mode]=real"
```

This:
- Detects the deployed preview service for the PR
- Runs MCP smoke tests against live APIs (Gemini + Firebase) when `test_mode=real`
- Posts results back to the PR

Real-mode smoke tests run against live APIs (Gemini + Firebase) to provide advisory evidence and preview verification during the draft phase. Note that real-mode execution is an advisory evidence/review signal and not a deterministic `/green` gate (which requires only Gate 1: CI green and Gate 2: no merge conflicts per `~/.claude/commands/green.md`). When live preview verification is needed, dispatch a real-mode run per above and check the workflow output or PR comment once complete.

### 2. Against Local Server (Mock Mode)
Run smoke tests locally against a mock MCP server:
```bash
# Run with mock/test mode (default)
./scripts/mcp_smoke_test.sh
```

### 3. Against Local Server (Real APIs)
Run smoke tests locally against real APIs:
```bash
# Set environment variables for real mode
export TESTING=false
export FLASK_ENV=production
export TEST_MODE=real
export MOCK_SERVICES_MODE=false

# Run smoke tests
./scripts/mcp_smoke_test.sh
```

## Workflow Integration

### GitHub Workflow (for PRs with preview deployments)
The `/smoke` command in a PR comment triggers:
1. **Workflow**: `.github/workflows/manual-mcp-smoke-tests.yml`
2. **Determines** deployed preview URL from GCP
3. **Runs** MCP smoke tests against the preview server
4. **Posts** results as PR comment

### Environment Variables
- `TESTING`: Set to `false` for real mode, `true` for mock mode
- `FLASK_ENV`: Set to `production` for real mode, `testing` for mock mode
- `TEST_MODE`: Set to `real` or `mock`
- `MOCK_SERVICES_MODE`: Set to `false` for real APIs, `true` for mocks

## Test Coverage
The smoke tests verify:
- ✅ MCP server health endpoint
- ✅ MCP initialization and handshake
- ✅ Tool listing and discovery (8 D&D campaign tools)
- ✅ Campaign creation (basic and custom configurations)
- ✅ Campaign state retrieval (with D&D 5e attribute system validation - warning-level check)
- ✅ Campaign list retrieval and verification
- ✅ Multiple gameplay actions with dice mechanics (search, combat, persuasion)
- ✅ State persistence across actions
- ✅ Comprehensive error handling:
  - Invalid campaign IDs
  - Missing required parameters
  - Invalid user access attempts
  - Empty user inputs
- ✅ Response format validation
- ✅ Real API integration (Gemini + Firebase)

## Expected Output

### Success (Mock Mode)
```
🚀 Starting MCP server on http://localhost:8000...
Server PID: 12345
✓ Server is ready

Running smoke tests...
✅ Health check passed
✅ MCP initialization passed
✅ Tool listing passed
✅ Tool execution passed

✅ All smoke tests passed!
```

### Success (Real Mode - on PR)
```
✅ Smoke Tests Passed (Real Mode)

All MCP smoke tests against live APIs completed successfully!

Tests Passed:
- ✅ MCP health check
- ✅ MCP initialization
- ✅ Tool discovery (8 D&D tools)
- ✅ Basic campaign creation
- ✅ Custom campaign creation
- ✅ Campaign state retrieval (D&D 5e attribute system – warning-level check)
- ✅ Campaign list verification
- ✅ Gameplay action #1 (search with dice rolls)
- ✅ Gameplay action #2 (combat with dice rolls)
- ✅ Gameplay action #3 (persuasion with dice rolls)
- ✅ State persistence verification
- ✅ Error handling (4 scenarios tested)

Service URL: https://mvp-site-app-pr-123-xxx.run.app
```

### Failure
```
❌ Smoke Tests Failed (Real Mode)

Some MCP smoke tests against live APIs failed.

Test Results:
- ✅ MCP health check
- ❌ Tool execution (timeout)

Service URL: https://mvp-site-app-pr-123-xxx.run.app
[View workflow run →](link)
```

## Implementation Protocol

When user requests `/smoke`:

1. **Determine Context**:
   - Are we in a PR with a deployed preview?
   - Are we running locally?
   - Mock or real mode?

2. **PR Context** (deployed preview exists):
   ```bash
   # Post comment on PR to trigger workflow
   # The manual-mcp-smoke-tests.yml workflow handles execution
   echo "Triggering smoke tests via PR comment: /smoke"
   ```

3. **Local Context**:
   ```bash
   # Run smoke tests locally
   cd /home/user/your-project.com

   # Mock mode (default)
   ./scripts/mcp_smoke_test.sh

   # Real mode (if user requests)
   TESTING=false FLASK_ENV=production TEST_MODE=real MOCK_SERVICES_MODE=false ./scripts/mcp_smoke_test.sh
   ```

4. **Report Results**:
   - Show test execution output
   - Report pass/fail status for each test
   - Provide links to detailed logs
   - Suggest next steps if failures occur

## Success Criteria
✅ Smoke tests complete without errors
✅ All core MCP endpoints respond correctly
✅ Tools can be discovered and executed
✅ Error messages are clear and actionable
✅ Results are posted to PR (if applicable)

## Error Handling

### Common Issues
1. **Preview server not found**: PR may not have a deployed preview yet
   - Solution: Wait for PR preview deployment to complete first

2. **Server startup timeout**: Local server failed to start
   - Solution: Check `tmp/your-project.com/test/mcp-server-smoke.log` for errors

3. **API rate limits**: Real mode tests hitting API limits
   - Solution: Use mock mode or wait before retrying

4. **Authentication errors**: Missing or invalid API credentials
   - Solution: Verify API keys in environment/secrets

## Files Involved
- `.github/workflows/manual-mcp-smoke-tests.yml` - GitHub workflow for PR smoke tests
- `scripts/mcp_smoke_test.sh` - Local smoke test script
- `$PROJECT_ROOT/mcp_api.py` - MCP server implementation
- Test logs: `tmp/your-project.com/test/mcp-*.log`

## Related Commands
- `/extended-library:testhttp` - Run HTTP integration tests (mock mode)
- `/extended-library:testhttpf` - Run HTTP integration tests (full/real mode)
- `/extended-library:test` - Run full test suite
- `/extended-library:deploy` - Deploy to production/staging

## Notes
- Smoke tests are designed to be fast (< 2 minutes)
- Mock mode uses no external API calls (safe for CI)
- Real mode tests against actual Gemini and Firebase APIs
- PR preview deployments are ephemeral (cleaned up after PR merge/close)
- Each PR gets a unique preview URL: `https://mvp-site-app-pr-{number}-xxx.run.app`
