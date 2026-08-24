---
description: /testing-layers - Show testing layer principles and test paths
type: documentation
execution_mode: immediate
---
## ⚡ EXECUTION INSTRUCTIONS FOR CLAUDE
**When this command is invoked, YOU (Claude) must execute these steps immediately:**

1. Display a brief summary of the 6 testing layer decision principles.
2. Display the correct test directory paths for the repo.
3. Review the complete rules at `.claude/skills/testing-layers/SKILL.md`.

## 📋 REFERENCE DOCUMENTATION

# /testing-layers - Testing Layers and Directory Paths

**Purpose**: Quickly lookup the principles for deciding which test layer to use and verify test directory paths.

See the full authoritative skill at: `.claude/skills/testing-layers/SKILL.md`

## Quick Directory Map
- **1. Unit**: `$PROJECT_ROOT/tests/` or `tests/`
- **2. End-to-End**: `$PROJECT_ROOT/tests/test_end2end/`
- **3. MCP API**: `testing_mcp/`
- **4. HTTP API**: `testing_http/`
- **5. Browser**: `testing_ui/`

## Key Principles for Test Selection
1. **Does the LLM's judgment affect the outcome?** (Yes = Layer 3+, No = Layer 1/2)
2. **Are you testing the LLM↔Server boundary?** (Yes = Layer 3+, No = Layer 1/2)
3. **Is there an integration seam mocks hide?** (Yes = Layer 3+, No = Layer 1/2)
4. **Is it a multi-function or multi-file flow of execution?** (Yes = Layer 2 by default, No = Layer 1)
5. **Is the cost proportional to risk?** (Real Gemini calls cost time/money. Don't burn tokens to test `dict.pop()`)
6. **Can the test pass vacuously?** (Ensure LLM diagnostics are verified via server logs)
