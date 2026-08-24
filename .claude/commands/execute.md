---
description: Execute Command - Plan-Approve-Execute Composition
type: llm-orchestration
execution_mode: immediate
---
## ⚡ EXECUTION INSTRUCTIONS FOR CLAUDE
**When this command is invoked, YOU (Claude) must execute these steps immediately:**
**This is NOT documentation - these are COMMANDS to execute right now.**
**Use TodoWrite to track progress through multi-phase workflows.**

## 🚨 EXECUTION WORKFLOW

### Phase 1: Planning (/extended-library:planexec)

**Action Steps:**
**Executes `/extended-library:planexec` command**: Follows the complete planning protocol documented in [`planexec.md`](./extended-library/planexec.md)
1. **Guidelines Consultation**: `/extended-library:planexec` calls `/extended-library:guidelines` directly for comprehensive consultation
2. **Comprehensive Context**: CLAUDE.md reading + base guidelines + PR/branch-specific guidelines via direct command composition
3. Creates TodoWrite checklist with specific steps including guidelines validation
4. Presents execution plan using the [Standard Plan Display Format](./extended-library/planexec.md#📋-standard-plan-display-format)
5. Shows complexity, execution method, tools, timeline, and parallelization strategy
6. **Tool Selection**: Follows guidelines hierarchy (Serena MCP → Read tool → Bash commands)
7. Provides full visibility into the execution approach before auto-approval

### Phase 2: Approval Chain

**Action Steps:**
**Full Approval Workflow**:
1. **`/extended-library:preapprove`**: Prepare approval context, validate plan completeness
2. **`/extended-library:autoapprove`**: Trigger automatic approval mechanism (proceeds silently)
3. **Key difference from `/extended-library:planexec`**: Built-in auto-approval eliminates manual approval requirement
4. Proceed directly to execution phase with approval satisfied

### Phase 3: Implementation

**Action Steps:**
**Execution**: Implements the approved plan from Phase 1
1. Updates TodoWrite status as tasks complete
2. **Updates Beads status** as work progresses (using MCP/CLI/direct file updates):
   - Mark bead as `open` when it is created and not yet started
   - Mark bead as `in_progress` when starting active work on it
   - Mark bead as `closed` when work is completed
   - If work is blocked by dependencies, keep the bead in `open` or `in_progress` and add a note/label indicating "blocked" and the specific dependency
   - Use only `open`, `in_progress`, or `closed` for the `status` field
   - Example: `br update <bead-id> --status in_progress`
   - Direct-file fallback: append the corresponding JSONL update in `.beads/issues.jsonl` per `docs/beads_creation_manual.md`
3. Uses systematic tool progression and the execution method determined in planning
4. Executes tasks as planned (parallel Task tool agents or sequential based on plan decision)
5. 🚨 **PARALLEL TASK EXECUTION**: Can use multiple Task tool calls in single message for up to 10 concurrent subagents
6. Validates and commits when complete
7. **Includes `.beads/` changes** in git commits per CLAUDE.md beads tracking rule

## 📋 REFERENCE DOCUMENTATION

# Execute Command - Plan-Approve-Execute Composition

> **Summary**: `/execute` runs `/extended-library:planexec`, auto-approves the generated plan,
> then performs execution with TodoWrite progress tracking in a single
> uninterrupted workflow.

**Purpose**: Execute tasks by composing `/extended-library:planexec` → auto-approve → execute workflow

**Usage**: `/execute` (or `/extended-library:e`) - Plan, auto-approve, then execute immediately

## 🚨 COMPOSITION PROTOCOL

### Command Flow

**The `/execute` command is a composition of**:
1. **`/extended-library:planexec`** - Create detailed implementation plan with TodoWrite
2. **`/extended-library:preapprove`** - Prepare approval context and validation
3. **`/extended-library:autoapprove`** - Automatic approval mechanism (proceeds silently with execution)
4. **Execute** - Proceed with planned implementation

## Example Flows

**Simple task**:
```
User: /execute fix the login button styling
Assistant:
Phase 0 - Context Assessment:
Context Status: 65% remaining → Low context pressure

Phase 1 - Planning (/extended-library:planexec):
✅ CLAUDE.md read: Current rules, constraints, and protocols understood
✅ Guidelines consultation: `/extended-library:guidelines` command completed - mistake prevention patterns applied
✅ Anti-patterns avoided: Using Edit tool for existing files, no _v2 or _backup files
Creating implementation plan with TodoWrite...
[Creates checklist: Check styles, Update CSS, Test changes, Commit]
Evaluating bead creation need...
⏭️ Skipping beads - Simple task with sufficient context (65% remaining > 35% threshold)

[Displays execution plan using standard format from extended-library/planexec.md]
Execution Plan:
- Task complexity: Simple (direct execution)
- **Execution method: Direct execution** - Simple file edits, no parallelization needed
- Tool requirements: Read, Edit, Bash (guidelines-validated tool selection)
- Implementation approach: Check current styling → Update CSS → Test → Commit
- Beads Tracking: N/A (simple task, context available)
- Expected timeline: ~10 minutes

Phase 2 - Approval Chain:
/extended-library:preapprove - Validating plan completeness and context
/extended-library:autoapprove - Proceeding with execution

Phase 3 - Implementation:
[Follows plan: Read current styles, Edit CSS, Test, Commit]
```

**Complex task**:
```
User: /execute implement user authentication system
Assistant:
Phase 0 - Context Assessment:
Context Status: 32% remaining → High context pressure (< 35% threshold)

Phase 1 - Planning (/extended-library:planexec):
✅ CLAUDE.md read: Current rules, constraints, and security protocols understood
✅ Guidelines consultation: Applied security patterns from docs/pr-guidelines/{current}/guidelines.md + docs/pr-guidelines/base-guidelines.md
✅ Anti-patterns avoided: No subprocess shell=True, proper timeout enforcement, explicit error handling
Creating comprehensive implementation plan...
[Creates detailed TodoWrite with multiple subtasks]
Evaluating bead creation need...
✅ Creating beads - Large/complex task + limited context (32% remaining < 35%)
✅ Created bead: auth-research-patterns (priority 1)
✅ Created bead: auth-core-implementation (priority 2)
✅ Created bead: auth-session-management (priority 3)
✅ Created bead: auth-testing (priority 4)

[Displays execution plan using standard format from extended-library/planexec.md]
Execution Plan:
- Task complexity: Complex (coordination needed)
- **Execution method: Sequential Tasks** - Security implementation requiring coordination
- Tool requirements: Read, Write, Edit, Bash, Task (guidelines-validated)
- Implementation approach: Research patterns → Core auth → Session management → Testing
- Guidelines applied: Subprocess safety, explicit error handling, 100% test coverage
- Beads Tracking:
  - [TASK] auth-research-patterns (status: open)
  - [TASK] auth-core-implementation (status: open)
  - [TASK] auth-session-management (status: open)
  - [TASK] auth-testing (status: open)
- Expected timeline: ~45 minutes

Sequential Task Plan:
- Main task: Implement core authentication system
- Task 1: Research existing auth patterns in codebase (using Serena MCP first) [bead: auth-research-patterns]
- Task 2: Create security tests and documentation [bead: auth-testing]
- Integration: Apply patterns to implementation with test validation

Phase 2 - Approval Chain:
/extended-library:preapprove - Validating comprehensive plan and dependencies
/extended-library:autoapprove - Proceeding with implementation

Phase 3 - Implementation:
[Updates bead auth-research-patterns to in_progress]
[Research: Auth patterns across codebase using Serena MCP]
[Updates bead auth-research-patterns to closed]
[Updates bead auth-core-implementation to in_progress]
[Implement: Core authentication system systematically]
[Updates bead auth-core-implementation to closed]
[Updates TodoWrite and beads progress throughout]
[Integrates findings with implementation]
[Includes .beads/ changes in final commit]
```

## Key Characteristics

- ✅ **Planned execution** - `/extended-library:planexec` creates structured approach with detailed display
- ✅ **Plan presentation** - Shows complexity, execution method, tools, timeline, and strategy
- ✅ **Parallelization strategy** - Displays parallel vs sequential decision with reasoning
- ✅ **Full approval chain** - `/extended-library:preapprove` + `/extended-library:autoapprove` sequence
- ✅ **TodoWrite integration** - progress tracking built-in
- ✅ **Composition pattern** - combines 3 commands seamlessly
- ✅ **User approval message** - clear indication of auto-approval
- ✅ **Structured workflow** - plan → approval chain → execute phases

## Relationship to Other Commands

- **`/extended-library:planexec`** - Just planning, requires manual approval, defines standard plan display format
- **`/execute`** - Planning + built-in auto-approval + execution (no manual approval needed), uses same display format as `/extended-library:planexec`
- **`/extended-library:preapprove`** - Prepare approval context and validation
- **`/extended-library:autoapprove`** - Automatic approval mechanism that satisfies the approval requirement internally. When invoked, `/extended-library:autoapprove` treats the plan as if the user explicitly approved it and proceeds directly to the execution phase. This command is integral to the `/execute` workflow, enabling seamless transitions from planning to implementation without user intervention.

**Format Consistency**: Both `/extended-library:planexec` and `/execute` use the centralized plan display format documented in `extended-library/planexec.md` to ensure consistent presentation of execution strategies and parallelization decisions.
