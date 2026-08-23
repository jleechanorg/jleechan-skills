---
description: /copilotl - Copilot Lite Alias
type: llm-orchestration
execution_mode: immediate
---
## ⚡ EXECUTION INSTRUCTIONS FOR CLAUDE
**When this command is invoked, YOU (Claude) must execute these steps immediately:**
**This is NOT documentation - these are COMMANDS to execute right now.**

## 🚨 EXECUTION WORKFLOW

### Phase 1: Execute /copilot-lite

**Action Steps:**
1. This command is an alias for `/copilot-lite`
2. Execute the full `/copilot-lite` workflow immediately
3. All functionality is defined in `copilot-lite.md`

**Delegate to**: `/copilot-lite`

## 📋 REFERENCE DOCUMENTATION

# /copilotl - Copilot Lite Alias

**Purpose**: Shorthand alias for `/copilot-lite` - Atomic single-pass PR comment processor

**Action**: Delegates all functionality to `/copilot-lite`

**Usage**: `/copilotl` → executes `/copilot-lite`

---

## Quick Reference

**What it does:**
1. Fetches ALL PR comments (human + bot)
2. Processes EACH comment atomically with ground truth verification
3. Generates truthful responses based on actual outcomes
4. Posts ALL responses with proper GitHub threading
5. Verifies 100% coverage
6. Pushes committed fixes

**Key Features:**
- Single-pass atomic processing (no multi-phase state loss)
- Ground truth verification (tries fixes before claiming outcomes)
- LLM-generated responses (no hardcoded Python templates)
- Proper comment threading via `in_reply_to`

**Response Types:**
- `FIXED`: Change made and verified (includes commit hash)
- `NOT_DONE`: Attempted but failed (includes real error)
- `ACKNOWLEDGED`: Style suggestion noted
- `ALREADY_IMPLEMENTED`: Code evidence shown

---

**See**: `/copilot-lite` for complete workflow documentation
