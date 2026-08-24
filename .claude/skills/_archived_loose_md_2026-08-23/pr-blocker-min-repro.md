---
description: "PR blocker minimal repro ladder for BYOK and related regressions"
type: "workflow"
scope: "github"
---

## Overview

The four-layer minimal repro protocol provides a fast escalation ladder for PR blockers:
1) `unit` -> 2) `end2end` -> 3) `testing_mcp` -> 4) `testing_ui` browser.

Use this when a PR has unresolved blocker beads and you need evidence-backed status updates quickly.

## Rules
- Run from repo root.
- Keep provider/user isolation for parallel runs.
- Stop climbing the ladder only when the blocker is conclusively reproduced.
- If lower layers pass but browser fails, classify as UI/integration-specific.
- Always attach concrete evidence paths and log lines to bead notes.

## Blocker Discovery
If `beads list` is unstable, query the JSONL database directly (requires `.beads/` to be initialized in the repo):

```bash
[ -f .beads/issues.jsonl ] && \
jq -r 'select(.labels // [] | index("pr-blocker")) | [.id, .title, .status, .priority] | @tsv' \
  .beads/issues.jsonl | sort -t$'\t' -k4 -n
```

## Quick Start Commands

### 1) Unit
```bash
./vpython -m pytest \
  $PROJECT_ROOT/tests/test_settings_api.py::TestSettingsAPI::test_update_and_clear_byok_key_reflects_has_custom_flag \
  $PROJECT_ROOT/tests/test_settings_api.py::TestSettingsAPI::test_update_settings_allows_openrouter_provider -q
```

### 2) End-to-End
```bash
./vpython -m pytest \
  $PROJECT_ROOT/tests/test_end2end/test_faction_settings_end2end.py::TestFactionSettingsEndToEnd::test_byok_api_key_clear_roundtrip \
  $PROJECT_ROOT/tests/test_end2end/test_llm_provider_end2end.py::TestLLMProviderSettingsEndToEnd::test_round_trips_openrouter_and_gemini_preferences -q
```

### 3) MCP / HTTP Local Server
```bash
./vpython testing_mcp/faction/test_faction_settings_real.py \
  --byok-providers gemini,openrouter,cerebras \
  --byok-parallel-workers 1
```

### 4) Browser (Final Escalation)
```bash
BYOK_CASES=1,2 \
BYOK_PARALLEL=true \
BYOK_PROVIDERS=gemini,openrouter,cerebras \
BYOK_TEST_PORT=8088 \
./vpython testing_ui/streaming/test_streaming_byok_browser.py
```

## Evidence Review Checklist
- Confirm each worker reports `TEST PASSED` or explicit failure.
- Grep worker logs for blocker signatures:
```bash
rg -n "status: 400|Failed to create campaign|non-stream|invalid-key validation message|did not update state|Traceback" \
  /tmp/$PROJECT_NAME/browser/byok-parallel-*/**/worker.log
```
- Verify screenshot + log consistency (no false screenshot claims).
- Record exact evidence directory and critical lines per bead.

## Advanced Patterns
- If a layer passes but the bug seems environmental, jump to browser to verify full stack behavior.
- When multiple providers are involved, isolate failures one provider at a time.
- Use specific tests, not full suites, to reduce noise.
- Capture first failure signatures; later errors can be cascading.

## Bead Update Template
Use this pattern in bead notes:
- `Repro ladder results:` unit=`pass|fail`, end2end=`pass|fail`, mcp=`pass|fail`, browser=`pass|fail`.
- `Classification:` backend, mcp, ui, or external-provider.
- `Evidence:` absolute path(s) + key log line(s).
- `Decision:` keep open, close, or downgrade priority.

