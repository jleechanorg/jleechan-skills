---
description: Parallel Tasks vs Subagents Reference Guide
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

# Parallel Tasks vs Subagents Reference Guide

**Purpose**: Central reference for deciding between parallel tasks and subagents to optimize token usage

## Quick Decision Guide

### 🚀 Use Parallel Tasks (0 extra tokens)

**When**: Simple, independent operations < 30 seconds each
**How**: Background processes, GNU parallel, xargs, or batched tool calls

### 🤖 Use Subagents (~50k+ tokens each)

**When**: Complex workflows, different directories, or operations > 5 minutes
**Cost**: 100x more expensive than parallel tasks

## Implementation Methods

### 1. Background Processes (Bash &)

```bash

# Best for: 2-10 simple commands

(command1) &
(command2) &
(command3) &
wait
```
**Pros**: Simple, built-in, error handling possible
**Cons**: Manual PID management, limited scaling

### 2. GNU Parallel

```bash

# Best for: Structured parallel execution

parallel -j 4 ::: "cmd1" "cmd2" "cmd3" "cmd4"

# With input files

parallel -a files.txt process_file {}
```
**Pros**: Advanced job control, progress bars, automatic load balancing
**Cons**: Requires installation, learning curve

### 3. xargs Parallel

```bash

# Best for: Processing file lists

find . -name "*.py" | xargs -P 8 -I {} python lint.py {}
```
**Pros**: Standard Unix tool, efficient for file operations
**Cons**: Limited error handling, basic job control

### 4. Batched Tool Calls

```python

# Best for: Multiple Claude tool calls

# Execute multiple searches/reads in one response

```
**Pros**: Most efficient for Claude operations, atomic execution
**Cons**: Limited to tool capabilities

## Decision Criteria

| Factor | Parallel Tasks | Subagents |
|--------|---------------|-----------|
| Token Cost | ~0 additional | ~50k+ each |
| Execution Time | < 30 seconds | > 5 minutes |
| Complexity | Simple, independent | Complex, multi-step |
| Directory | Same working dir | Different branches/dirs |
| Failure Handling | Basic | Advanced isolation |
| Context Needed | Shared | Independent |

## Common Scenarios

### ✅ Perfect for Parallel Tasks

- Search codebase for patterns
- Run test suites
- Check multiple PR statuses
- Lint multiple files
- Aggregate data from APIs
- Build multiple components

### ✅ Requires Subagents

- Implement new features
- Fix complex bugs
- Create/update PRs
- Multi-branch operations
- Architectural changes
- Long-running migrations

## Token Cost Examples

```
10 file searches:
- Parallel: 0 additional tokens
- Subagents: 500,000+ tokens (10 × 50k)
- Savings: 100%

Feature implementation:
- Parallel: Not suitable (complex workflow)
- Subagent: 50k tokens (justified by complexity)
```

## Monitoring Success

```bash

# Before optimization

ccusage daily --instances

# After switching to parallel

ccusage daily --instances --since 2025-07-29

# Expected: 90%+ reduction in token usage

```

## Integration with Commands

This guide is referenced by:
- `/parallel` — parallelize-to-ceiling (resource-bound sizing for any fan-out)
- `/planexec` — Planning execution strategy
- `/execute` - Choosing execution method
- `/arch` - Architectural task distribution
- `/test` - Test execution strategy
- CLAUDE.md - Core operating guidelines

---

**Remember**: Default to parallel tasks. Only use subagents when truly needed for complexity or isolation.
