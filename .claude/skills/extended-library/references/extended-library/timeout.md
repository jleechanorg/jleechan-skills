---
description: /timeout Command - Performance Optimizer
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

# /timeout Command - Performance Optimizer

Automatically applies timeout mitigation strategies to prevent Claude Code CLI timeouts.

## Usage

```
/timeout              # Standard optimization mode
/timeout strict       # Maximum performance restrictions
/timeout emergency    # Crisis mode - absolute minimum
/timeout off          # Disable timeout optimizations
```

## Purpose

Prevents response timeouts by enforcing efficient patterns:
- Limits response verbosity
- Batches operations aggressively
- Constrains thinking steps
- Optimizes file operations
- Forces concise output format

## Automatic Optimizations

### 1. Tool Usage (All Modes)

- **MultiEdit**: Enforced for >2 edits, with exact limits per mode:
  - Standard Mode: Max 4 operations
  - Strict Mode: Max 3 operations
  - Emergency Mode: Max 2 operations
- **Batching**: All tool calls in single message
- **Search**: Task tool for >3 files, Grep/Glob preferred
- **Reads**: Max 100 lines default, use offset/limit

### 2. Response Format

**Standard Mode**:
- Bullet points for lists
- No unsolicited explanations
- File:line references > code quotes
- 3-line max context per item

**Strict Mode**:
- Single-line responses preferred
- No code blocks unless essential
- Abbreviations acceptable
- Zero explanatory text

**Emergency Mode**:
- Actions only, no explanations
- Tool invocations + results
- Single word confirmations
- No formatting

### 3. Thinking Limits

- **Standard**: 5 thoughts max
- **Strict**: 3 thoughts max
- **Emergency**: 2 thoughts max
- No branching/revision thoughts

### 4. Context Management

- Aggressive pruning after each operation
- Summarize > quote
- Reference > content
- Warning at 80% context usage

## Mode Indicators

```
🚀 TIMEOUT MODE: STANDARD
Optimizations: Batching ON | Brevity ON | Think-limit 5

⚡ TIMEOUT MODE: STRICT
Optimizations: Max-batching | Min-output | Think-limit 3

🚨 TIMEOUT MODE: EMERGENCY
Crisis-mode: Actions-only | No-explain | Think-limit 2
```

## Examples

### Standard Mode

```
User: /timeout /execute refactor authentication
Claude: 🚀 TIMEOUT MODE: STANDARD
Task: Refactor auth
- Scan files with Task tool
- Batch edits with MultiEdit
- Test changes
- Commit results
[Executes with optimizations]
```

### Strict Mode

```
User: /timeout strict fix all import errors
Claude: ⚡ TIMEOUT MODE: STRICT
Fix imports:
- Grep errors
- MultiEdit fixes
- Verify
[Minimal output]
```

### Emergency Mode

```
User: /timeout emergency server is down fix now
Claude: 🚨 EMERGENCY MODE
[Direct tool calls only]
MultiEdit main.py [3 fixes]
Bash: restart server
✓ Done
```

## Chainable with Other Commands

```
/timeout /think analyze performance bottlenecks
/timeout strict /execute large refactoring task
/timeout emergency /debug production issue
```

## What Changes

### File Operations

- ❌ Read entire files → ✅ Read sections (100 lines)
- ❌ Sequential reads → ✅ Batched reads
- ❌ Re-read after edit → ✅ Trust edit success

### Responses

- ❌ "Let me explain..." → ✅ Direct actions
- ❌ Code walkthroughs → ✅ File:line refs
- ❌ Verbose errors → ✅ Key info only

### Thinking

- ❌ Exploring options → ✅ Direct solutions
- ❌ 10+ thoughts → ✅ 5 thought limit
- ❌ Revisions → ✅ Linear progress

## Performance Impact

For detailed performance metrics and analysis, see [Timeout Analysis Document](../../../roadmap/scratchpad_memory-backup-2025-07-18.md).

**Summary**:
- Response time: -40-60% (from avg 60s to 24-36s)
- Timeout rate: 10% → <2%
- Token usage: -50-70%
- Same task quality

## Best Practices

1. **Use for**: Large refactors, multi-file changes, exploration tasks
2. **Combine with**: Task tool, MultiEdit, smart search
3. **Monitor**: Context usage warnings
4. **Disable**: When detailed explanations needed

## Integration

Timeout mode modifies behavior for entire session until disabled. Works seamlessly with all other commands and maintains task quality while optimizing performance.
