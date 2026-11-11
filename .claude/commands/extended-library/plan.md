---
description: Plan Command - Execute with Approval
type: llm-orchestration
execution_mode: immediate
---
## ⚡ EXECUTION INSTRUCTIONS FOR CLAUDE
**When this command is invoked, YOU (Claude) must execute these steps immediately:**
**This is NOT documentation - these are COMMANDS to execute right now.**
**Use TodoWrite to track progress through multi-phase workflows.**

## 🚨 EXECUTION WORKFLOW

### Phase 0: Context Assessment (MANDATORY FIRST STEP)

**Action Steps:**
**🔍 Context Assessment**: Every planning session MUST begin with context assessment:
```bash

### Phase 1: Strategic Analysis

**Action Steps:**
**Memory Integration**: Automatically consults Memory MCP for relevant patterns, corrections, and user preferences.

**Guidelines Consultation**: Before planning, read `CLAUDE.md`, `docs/pr-guidelines/base-guidelines.md` and any `docs/pr-guidelines/{PR_NUMBER}/guidelines.md`, and apply the mistake-prevention patterns they list.

**Tool Selection Hierarchy** (Context-Optimized):
1. **Serena MCP** - Semantic analysis for efficient context usage
2. **Targeted Reads** - Limited file reads based on context capacity
3. **Focused Implementation** - Claude direct based on task size
4. **Context Preservation** - Reserve capacity for execution and validation

### Phase 2: Execution Plan Presentation

**Action Steps:**
**📋 CONTEXT-ADAPTIVE PLAN FORMAT**:

**🧠 Context Status**: _____% remaining → **[High/Medium/Low]** complexity planning

**🎯 Universal Composition Strategy**:
1. **Primary Command**: `/plan` (this command)
2. **Composed Commands**: List of commands that will be naturally integrated
3. **Tool Selection**: Context-aware hierarchy (Serena MCP → Read → Claude → Bash)

**⚡ Implementation Approach**:
4. **Analysis Tasks**: Minimal context consumption using Serena MCP
5. **Generation Tasks**: Claude handles code generation tasks
6. **Integration Tasks**: Efficient tool selection based on remaining context
7. **Validation**: Context-appropriate testing depth

**🔀 Execution Method Decision** (Context-Optimized):
8. **Parallel Tasks** (0 additional tokens): For simple, independent operations <30 seconds
  9. Method: Background processes (&), GNU parallel, xargs, or batched tool calls
  10. Best for: File searches, test runs, lint operations, data aggregation
11. **Sequential Tasks**: For complex workflows requiring coordination >5 minutes
  12. Method: Step-by-step with context monitoring
  13. Best for: Feature implementation, architectural changes, complex integrations
14. **Reference**: See [parallel-vs-subagents.md](./parallel-vs-subagents.md) for full decision criteria

**🚀 Execution Sequence** (Context-Optimized):
15. **Quick Discovery**: Use Serena MCP for targeted analysis
16. **Smart Generation**: Claude for code generation and integration
17. **Efficient Validation**: Context-appropriate testing and verification
18. **Clean Integration**: Minimal overhead for final steps

**Timeline**: _____ minutes (context-optimized approach)

### Phase 3: Approval Requirement

**Action Steps:**
**❌ NEVER proceed without explicit user approval**

User must respond with "APPROVED" or specific modifications before execution begins.

### Phase 4: Execute Protocol

**Action Steps:**
**After approval, implements the plan directly with context awareness**:
1. Monitor context usage throughout execution
2. Apply context-saving strategies when needed
3. Use universal composition with other commands naturally
4. Preserve context for testing and validation

## 📋 REFERENCE DOCUMENTATION

# Plan Command - Execute with Approval

**Purpose**: Context-aware planning that requires user approval before implementation. **CONTEXT-AWARE PLANNING** with intelligent tool selection and universal composition.

**Usage**: `/plan` - Present context-aware execution plan with approval workflow

## 🧠 CONTEXT-AWARE PLANNING PROTOCOL

# Check remaining context capacity to inform planning approach

/context
```

**Context-Informed Planning Strategy**:
- **High Context (60%+ remaining)**: Comprehensive analysis and detailed planning
- **Medium Context (30-60% remaining)**: Targeted analysis with efficient tool selection
- **Low Context (< 30% remaining)**: Lightweight planning with essential tasks only

## 🔗 UNIVERSAL COMPOSITION PRINCIPLES

**Command Integration**: `/plan` naturally composes with:
- `/thinku` - Strategic analysis and problem solving
- `/context` - Continuous context monitoring
- Memory MCP - Pattern recognition and preference application

**Adaptive Workflow**: The planning process adapts based on:
- Available context capacity
- Task complexity and scope
- User preferences from memory
- Guidelines and protocol requirements

## 📊 TOOL SELECTION CRITERIA

**Context-Efficient Tools** (Prioritized):
- ✅ **Serena MCP**: Semantic operations with minimal context consumption
- ✅ **Targeted Reads**: Specific file sections rather than full files
- ✅ **MultiEdit**: Batch edits to minimize tool overhead
- ✅ **Smart Search**: Grep/Glob before reading files

**High-Performance Generation** (When Appropriate):
- ✅ **Claude Direct**: For code generation and integration work
- ✅ **Universal Composition**: Natural command integration

**Context Preservation**:
- ❌ Avoid unnecessary file reads
- ❌ Minimize redundant operations
- ❌ Skip verbose output when planning
- ✅ Reserve context for execution and validation

## Example Flow

**Context-Aware `/plan` Flow**:
```
User: /plan implement user authentication
Assistant:

Phase 0 - Context Assessment:
/context → 45% remaining → Medium Context Strategy

Phase 1 - Strategic Analysis:
[Memory consultation for auth patterns]
[Guidelines check for security requirements]
[Serena MCP discovery for efficient analysis]

Phase 2 - Execution Plan:
Context Status: 45% remaining → Medium complexity planning
- Analysis: Use Serena MCP for efficient codebase understanding
- Generation: Claude for new auth classes and integration
- Context preservation: Strategic tool selection

Seeking approval to proceed...

User: APPROVED
Assistant: [Executes context-optimized implementation]
```

## Key Characteristics

- ✅ **Context assessment mandatory first step**
- ✅ **Universal composition with other commands**
- ✅ **Context-adaptive planning depth**
- ✅ **Intelligent tool selection hierarchy**
- ✅ **User approval required before execution**
- ✅ **Memory and guidelines integration**
- ✅ **Efficient execution with context preservation**
