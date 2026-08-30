---
description: Plan-Execute Command - Execute with Approval
type: llm-orchestration
execution_mode: immediate
aliases: [plan]
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

**Guidelines Consultation**: Calls `/guidelines` for systematic mistake prevention and protocol compliance.

**MANDATORY Skills Consultation** (before any implementation):
1. **Code Centralization** (`.claude/skills/code-centralization.md`):
   - Search for existing similar code BEFORE writing new code
   - Document search results and justify new code only if reuse impossible
   - Prove you investigated existing implementations
2. **File Justification** (`.claude/skills/file-justification.md`):
   - For each file touched, document GOAL/MODIFICATION/NECESSITY/INTEGRATION PROOF
   - New files require extreme scrutiny - prove integration impossible
3. **Integration Verification** (`.claude/skills/integration-verification.md`):
   - For any integration claims, provide Three Evidence Rule
   - Configuration + Trigger + Log evidence required
4. **SOLID Skills** (`.claude/skills/solid/SKILL.md`):
   - Apply TDD Red-Green-Refactor cycle for all code changes
   - Verify SOLID principles (SRP, OCP, LSP, ISP, DIP) during design
   - Use pre-code, during-code, and post-code checklists
   - Ensure clean code standards (naming, structure, readability)
   - Detect and refactor code smells before completion

**Tool Selection Hierarchy** (Context-Optimized):
1. **Serena MCP** - Semantic analysis for efficient context usage
2. **Targeted Reads** - Limited file reads based on context capacity
3. **Focused Implementation** - Claude direct based on task size
4. **Context Preservation** - Reserve capacity for execution and validation

### Phase 1.5: Beads Creation (Conditional)

**Action Steps:**
**🎯 Create Beads for Work Items**: Apply judgment to determine if beads are needed:

**Create Beads When:**
- Task complexity is **Medium** or **Large** (multi-step, architectural changes, feature implementation)
- Context remaining is **< 35%** (limited context requires external tracking)
- Work items exceed **3+ discrete tasks** in TodoWrite checklist
- User explicitly requests bead tracking

**Skip Beads When:**
- Simple, single-step tasks (e.g., "fix typo", "update variable name")
- Context remaining is **> 35%** AND task is trivial
- Only 1-2 quick tasks in the plan

**Bead Creation Hierarchy**: For each work item identified in the plan, create a bead using the following explicit fallback chain:

```bash
# Try Beads MCP first (preferred), then BD CLI, then direct file creation
if mcp-cli list-tools 2>/dev/null | grep -q beads; then
  # Use Beads MCP (via printf to avoid newline issues)
  printf '{"title":"[TASK] Work item title","description":"Detailed description","status":"open","priority":1,"issue_type":"task"}' | mcp-cli call beads/create -
elif command -v bd >/dev/null 2>&1; then
  # Fallback to BD CLI
  bd create "Work item title" --description "Detailed description" --priority 1
else
  # Fallback to direct file creation
  mkdir -p .beads
  printf '{"id":"unique-id","title":"[TASK] Work item title","description":"Detailed description","status":"open","priority":1,"issue_type":"task","created_at":"%s","updated_at":"%s"}\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> .beads/issues.jsonl
fi
```

**Bead Structure**:
- **id**: Unique identifier (e.g., `session-id-task-name` or auto-generated)
- **title**: `[TASK]` prefix + concise work item title (max 60 chars)
- **description**: Full description of the work item from the plan
- **status**: `open` (initial status) - valid values: `open`, `in_progress`, `closed`
- **priority**: 1-5 (1 = highest, 5 = lowest)
- **issue_type**: `task`, `bug`, `feature`, or `enhancement`
- **created_at**: ISO 8601 timestamp
- **updated_at**: ISO 8601 timestamp

**Note**: If a bead is blocked by dependencies, keep status as `open` or `in_progress` and add blocking information in the description or notes field rather than using a separate "blocked" status.

**Critical Rules**:
- Create ONE bead per discrete work item in the TodoWrite checklist
- Use descriptive titles that indicate the specific work (not generic "Implement feature")
- Include the bead IDs in the execution plan output so they can be tracked
- Always include `.beads/` changes in git commits/PRs per CLAUDE.md rules

### Phase 2: Execution Plan Presentation

**Action Steps:**
**📋 CONTEXT-ADAPTIVE PLAN FORMAT**:

**🧠 Context Status**: _____% remaining → **[High/Medium/Low]** complexity planning

**🎯 Universal Composition Strategy**:
1. **Primary Command**: `/planexec` (this command)
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
14. **Parallel ceiling (mandatory for any fan-out):** Load `/parallel` → `~/.claude/skills/parallelize-to-ceiling/SKILL.md` before sizing workers, shards, or agent lanes. **LLM vs tool parallelism:** see [parallel-vs-subagents.md](./parallel-vs-subagents.md) for when to use subagents vs batched tool calls.

**🚀 Execution Sequence** (Context-Optimized):
15. **Quick Discovery**: Use Serena MCP for targeted analysis
16. **Smart Generation**: Claude for code generation and integration
17. **Efficient Validation**: Context-appropriate testing and verification
18. **Clean Integration**: Minimal overhead for final steps

**📋 Beads Tracking** (Work Item Management):
19. **Created Beads**: List bead IDs created for this work
   - Format: `[TASK] bead-id-1: Work item title`
   - Status: All beads start as `open`
   - Updates: Use beads MCP/CLI to update status during execution
20. **Bead Updates**: Throughout execution, update bead status:
   - `open` → `in_progress` (when starting work)
   - `in_progress` → `closed` (when completed)
   - If blocked: Keep as `open` or `in_progress`, add blocking info to description/notes

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

### Phase 5: Simplify (MANDATORY FINAL STEP)

**Action Steps:**
**After execution completes, ALWAYS run `/simplify` to review changed code:**
1. Invoke the `/simplify` skill automatically — do NOT skip this step
2. `/simplify` reviews all changed code for reuse opportunities, code quality, and efficiency
3. Any issues found by `/simplify` must be fixed before considering the plan complete
4. This phase ensures every `/plan` and `/planexec` execution produces clean, efficient, deduplicated code

## 📋 REFERENCE DOCUMENTATION

# Plan Command - Execute with Approval

**Purpose**: Context-aware planning that requires user approval before implementation. **CONTEXT-AWARE PLANNING** with intelligent tool selection and universal composition.

**Usage**: `/planexec` - Present context-aware execution plan with approval workflow

## 🧠 CONTEXT-AWARE PLANNING PROTOCOL

# Check remaining context capacity to inform planning approach

/context
```

**Context-Informed Planning Strategy**:
- **High Context (60%+ remaining)**: Comprehensive analysis and detailed planning
- **Medium Context (30-60% remaining)**: Targeted analysis with efficient tool selection
- **Low Context (< 30% remaining)**: Lightweight planning with essential tasks only

## 🔗 UNIVERSAL COMPOSITION PRINCIPLES

**Command Integration**: `/planexec` naturally composes with:
- `/think` - Strategic analysis and problem solving
- `/guidelines` - Mistake prevention and protocol compliance
- `/context` - Continuous context monitoring
- `/simplify` - **MANDATORY** final step: code reuse, quality, and efficiency review
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

**Context-Aware `/planexec` Flow**:
```
User: /planexec implement user authentication
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
