---
description: /generatetest - Evidence-Based Test Generator (Real Mode Only)
type: skill
execution_mode: immediate
---

# /generatetest [free-form description]

Generates a self-contained `testing_mcp/` E2E test (MCPTestBase, real server,
real database, real Gemini LLM — no mocks) with a built-in evidence bundle.

Read the `generatetest` skill and execute the full workflow
with the provided context. Also read the `evidence-standards` skill
(repo-level) and the `evidence-standards` skill (user-scope)
before generating any test code.

## Quick reference

| Aspect | Rule |
|---|---|
| Base class | `MCPTestBase` (mandatory, never standalone scripts) |
| Mode | Real server, real DB, real LLM — no mocks, no `TESTING=true` |
| Libraries | `testing_mcp/lib/*` only — never reimplement |
| Output | Test file → `testing_mcp/`; evidence → `/tmp/<repo>/<branch>/<work>/iteration_NNN/` |

## Example

```
/generatetest for this PR make sure the equipment logic works
/generatetest validate dice roll integrity in combat
```
