---
description: Total Failure Protocol
type: llm-orchestration
execution_mode: immediate
---
## ⚡ EXECUTION INSTRUCTIONS FOR CLAUDE
**When this command is invoked, YOU (Claude) must execute these steps immediately:**
**This is NOT documentation - these are COMMANDS to execute right now.**
**Use TodoWrite to track progress through multi-phase workflows.**

## 🚨 EXECUTION WORKFLOW

### Phase 1: Execute Documented Workflow

**Action Steps:**
1. Review the reference documentation below and execute the detailed steps sequentially.

## 📋 REFERENCE DOCUMENTATION

# Total Failure Protocol

**Usage**: `/total_failure` or referenced by other commands

**Purpose**: Define zero tolerance success criteria for all tasks, debugging, and testing operations.

## 🚨 TOTAL FAILURE PROTOCOL

### ⚡ ZERO TOLERANCE FOR PARTIAL SUCCESS

**ABSOLUTE RULE: NO CELEBRATIONS UNTIL ORIGINAL PROBLEM IS 100% SOLVED**
- ❌ NO "partial success" acknowledgments
- ❌ NO "mostly working" statements until SPECIFIC issue is resolved
- ❌ NO "good progress" claims until ORIGINAL REQUEST is complete
- ❌ NO stopping early with "this tells us valuable information" - THAT IS FAILURE
- ❌ NO claiming progress until exact issue is resolved

### 🎯 BRUTAL SUCCESS CRITERIA

**ONLY SUCCESS:** The exact user request or test specification is completely fulfilled
- **ANYTHING LESS IS TOTAL FAILURE:** No exceptions, no excuses, no partial credit
- **BE RUTHLESSLY HONEST:** If original problem isn't solved, the task FAILED
- **BUILD MUST WORK:** If code doesn't compile or tests fail, it's complete failure
- **USER REQUEST MUST BE 100% COMPLETE:** Anything working less than 100% = TOTAL FAILURE

### 🚨 BINARY OUTCOME ENFORCEMENT

- **100% Working = SUCCESS**
- **99% Working = TOTAL FAILURE**
- **No middle ground, no partial credit**
- **Zero tolerance for "almost there" or "mostly fixed"**

### 📋 APPLICATION AREAS

This protocol applies to:
- **All testing operations** (`/testllm`, `/test`, browser automation)
- **All debugging tasks** (`/debug`, `/debugp`, issue resolution)
- **All user requests** (feature implementation, bug fixes, code changes)
- **All build operations** (compilation, deployment, CI/CD)
- **All validation steps** (code review, quality checks, integration tests)

### 🔧 ENFORCEMENT MECHANISMS

- **Pre-completion checkpoint**: "Is the original problem 100% solved?"
- **Binary evaluation**: No scoring, no percentages - only PASS/FAIL
- **Evidence requirement**: Concrete proof of 100% functionality required
- **Zero exceptions**: No circumstances justify partial success declaration

### 🚨 FORBIDDEN LANGUAGE PATTERNS

❌ **NEVER SAY:**
- "Mostly working"
- "Almost there"
- "Good progress"
- "Partial success"
- "99% complete"
- "Just need to fix one small thing"
- "This tells us valuable information" (without solving original problem)

✅ **ONLY ACCEPTABLE:**
- "100% WORKING" (with evidence)
- "TOTAL FAILURE" (when anything less than 100%)

### 📖 COMMAND INTEGRATION

Commands that enforce Total Failure Protocol:
- `/testllm` - Testing operations
- `/debugp` - Debug protocol
- `/debug-protocol` - Forensic debugging
- All commands in `.claude/commands/` that declare success/failure

## Meta-Protocol

This Total Failure Protocol is the foundational success criteria for all operations. Commands reference this document rather than duplicating the language.

**Reference Format (for use in other files):**
```markdown
🚨 **TOTAL FAILURE PROTOCOL**: Apply [Total Failure Protocol](.claude/commands/total_failure.md) - 100% working or TOTAL FAILURE
```
