---
description: /llm-testing - Real-LLM, zero-mock testing layer (testing_mcp / testing_ui)
type: testing
execution_mode: immediate
---
## ⚡ EXECUTION INSTRUCTIONS FOR CLAUDE
**When this command is invoked, YOU (Claude) must execute these steps immediately:**
**This is NOT documentation — these are COMMANDS to execute right now.**

1. State that this command proves real model/service behavior. Keep deterministic or mocked
   unit checks outside `testing_mcp/` and `testing_ui/`; those checks do not satisfy this
   command's acceptance claims.
2. Locate the matching `testing_mcp/<domain>/test_*.py` (or `testing_ui/`) driver for the
   feature/blocker argument.
3. Read the owning `testing_mcp/CLAUDE.md` or `testing_ui/CLAUDE.md` before running. Use its
   real-service account, provider, server, authentication, and runner instructions. Do not
   enable authentication bypass. For `testing_mcp/`, use `python3` with the explicit
   `PYTHONPATH` required by its owner; do not use `vpython` or pytest there. For `testing_ui/`,
   use its approved real-application runner and services.
4. Record the full absolute evidence path produced by the owning test workflow and confirm
   the artifacts required for this claim exist. Use its unique `/tmp` path; do not invent a
   repository evidence directory.
5. Review the complete rules at `~/.claude/skills/llm-testing/SKILL.md`.

## 📋 REFERENCE DOCUMENTATION

# /llm-testing — Real-LLM Zero-Mock Testing

**Purpose**: Prove behavior that depends on the LLM's judgment. The opposite of
`/end2end-testing` (which fakes externals): real LLM, real services, and a real server.
This is the execution mechanism behind `/es` evidence for `$PROJECT_ROOT/**` changes.

See the full authoritative skill at: `.claude/skills/llm-testing.md`

## Usage
```bash
/llm-testing [feature_or_blocker]
```

## Quick Directory Map
- **MCP API (Layer 3)**: `testing_mcp/` — follow `testing_mcp/CLAUDE.md` for its direct `python3` runner and explicit `PYTHONPATH`.
- **Browser/UI (Layer 5)**: `testing_ui/` — follow `testing_ui/CLAUDE.md` for the real application, services, account, and runner.

## Real-Service Acceptance Contract

For acceptance runs in `testing_mcp/` and `testing_ui/`, use the real provider,
database, server, browser, and account required by their owners. A bypassed-auth
or mocked-services run does not prove those boundaries. Deterministic mocked
unit checks remain valid outside those real-service acceptance directories.

## Mock flags that invalidate a real-service acceptance run
`TEST_MODE=mock` · `MOCK_SERVICES_MODE` · `USE_MOCK_FIREBASE` · `USE_MOCK_GEMINI` ·
`FORCE_TEST_MODEL=true` · any mock-server/fake-LLM/fake-firestore flag.

## Relationship
- `/end2end-testing` = Layer 2, faked externals (iterate cheap).
- `/llm-testing` = Layers 3 & 5, real LLM + services (prove it).
- `/4layer` ladder uses `/llm-testing` for Layers 3–4. `/testing-layers` is the decision guide.
- `/es` is the evidence gate; `/llm-testing` generates the evidence that passes it.
