---
description: /llm-testing - Real-LLM, zero-mock testing layer (testing_mcp / testing_ui)
type: testing
execution_mode: immediate
---
## ⚡ EXECUTION INSTRUCTIONS FOR CLAUDE
**When this command is invoked, YOU (Claude) must execute these steps immediately:**
**This is NOT documentation — these are COMMANDS to execute right now.**

1. Display the ZERO-MOCKS core principle (no `TEST_MODE=mock`, `MOCK_SERVICES_MODE`,
   `USE_MOCK_FIREBASE`, `USE_MOCK_GEMINI`, `FORCE_TEST_MODEL=true`, or any fake flag).
2. Locate the matching `testing_mcp/<domain>/test_*.py` (or `testing_ui/`) driver for the
   feature/blocker argument.
3. Run it with the real-services env (`TESTING_AUTH_BYPASS=true`,
   `GOOGLE_APPLICATION_CREDENTIALS=$HOME/serviceAccountKey.json`) against a real local
   server, or `--preview-url <url>` for a remote GCP preview. `testing_mcp/` runs with `vpython`
   **directly, never pytest**; `testing_ui/` runs via `python3 $PROJECT_ROOT/main.py testui`.
4. Print the full absolute evidence bundle path
   (`/tmp/your-project.com/<branch>/<test_name>/latest/`) and confirm streaming artifacts exist.
5. Review the complete rules at `.claude/skills/llm-testing.md`.

## 📋 REFERENCE DOCUMENTATION

# /llm-testing — Real-LLM Zero-Mock Testing

**Purpose**: Prove behavior that depends on the LLM's judgment. The opposite of
`/end2end-testing` (which fakes externals): real LLM, real Firestore, real server, **zero mocks**.
This is the execution mechanism behind `/es` evidence for `$PROJECT_ROOT/**` changes.

See the full authoritative skill at: `.claude/skills/llm-testing.md`

## Usage
```bash
/llm-testing [feature_or_blocker]
```

## Quick Directory Map
- **MCP API (Layer 3)**: `testing_mcp/` — `vpython testing_mcp/<domain>/test_*.py` (direct, not pytest)
- **Browser/UI (Layer 5)**: `testing_ui/` — `python3 $PROJECT_ROOT/main.py testui` (`TESTING_AUTH_BYPASS=true`)

## Zero-Mock Contract (a run is VOID if any are set)
`TEST_MODE=mock` · `MOCK_SERVICES_MODE` · `USE_MOCK_FIREBASE` · `USE_MOCK_GEMINI` ·
`FORCE_TEST_MODEL=true` · any mock-server/fake-LLM/fake-firestore flag.

## Relationship
- `/end2end-testing` = Layer 2, faked externals (iterate cheap).
- `/llm-testing` = Layers 3 & 5, real LLM + services (prove it).
- `/4layer` ladder uses `/llm-testing` for Layers 3–4. `/testing-layers` is the decision guide.
- `/es` is the evidence gate; `/llm-testing` generates the evidence that passes it.
