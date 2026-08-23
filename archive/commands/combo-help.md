---
description: Combo Help Command
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

# Combo Help Command

**Usage**: `/combo-help [commands]`

**Description**: Explains what a specific command combination does and provides usage examples.

## Examples

### Get help for specific combinations

```
/combo-help arch plan
/combo-help think brief
/combo-help arch plan think
```

## Implementation

This command analyzes the requested command combination and:
1. Shows the resulting transformed command
2. Explains the combined behavior
3. Provides usage examples
4. Lists related combinations

## Available for Help

All combinations defined in `.claude/command-compositions.json`:
- arch + plan
- arch + think
- plan + think
- arch + plan + think
- brief + think
- brief + plan
- brief + arch
- debug + think
- test + plan

## Sample Output

**Input**: `/combo-help arch plan`

**Output**:
```
Command Combination: /arch /planexec
Transforms to: /execute Create detailed architectural plan with implementation strategy: {your_text}

Description: Combines architectural thinking with detailed planning
Tags: architecture, planning, design

Example Usage:
  /arch /planexec build microservices platform
  → Creates comprehensive architectural plan for microservices platform

Related Combinations:
  - /arch /planexec /think (adds deep reasoning)
  - /brief /arch /planexec (adds concise output)
```
