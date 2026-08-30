---
description: /handoff Command
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

# /handoff Command

Creates a structured handoff for another worker with PR, scratchpad, and worker prompt.

## Usage

```
/handoff [task_name] [description]
```

## What it does

1. **Creates Clean Branch**: Uses `/newbranch handoff-[task_name]` to create fresh branch from latest main
2. **Generates Scratchpad**: `roadmap/scratchpad_handoff_[task_name].md` with:
   - Problem statement
   - Analysis completed
   - Implementation plan
   - Files to modify
   - Testing requirements
3. **Creates PR**: With detailed description and ready-to-implement status
4. **Auto-Updates Roadmap**: Automatically uses `/r` command logic to add entry to `roadmap/roadmap.md`
5. **Generates Worker Prompt**: Copy-paste prompt for next worker
6. **Creates Clean Branch**: Uses `/newbranch` to ensure clean main-based branch for continued work

## Example

```
/handoff logging_fix "Add file logging configuration to main application"
```

Creates:
- Branch: `handoff-logging_fix`
- Scratchpad: `roadmap/scratchpad_handoff_logging_fix.md`
- PR with implementation details
- Roadmap entry
- Worker prompt
- New clean branch for you

## Requirements

- Current work should be analyzed/planned
- Key files and implementation approach identified
- Testing strategy defined

## Output Format

**Primary Output**: Copy-paste ready worker prompt with:
- Setup instructions (worktree navigation, branch checkout)
- Task context and goals
- Implementation plan and timeline
- Success criteria and testing requirements
- File locations and specifications

**Example Output**:
```
🎯 WORKER PROMPT (Copy-paste ready)

TASK: [task_name]
SETUP:
1. Switch to worktree: cd /path/to/worktree_roadmap
2. Checkout handoff branch: git checkout handoff-[task_name]
3. Read specification: roadmap/scratchpad_handoff_[task_name].md

GOAL: [clear objective]
IMPLEMENTATION: [detailed steps]
SUCCESS CRITERIA: [measurable outcomes]
TIMELINE: [estimated hours]
FILES: [key files to create/modify]

START: Read the handoff scratchpad for complete details
```

**Additional Outputs**:
- Handoff branch with complete specification
- PR with implementation details
- Updated roadmap entry
- Clean branch for continued work

## Implementation Details

### Automatic Roadmap Update Process

After creating the PR, the command automatically invokes `/r` logic with PR workflow:

1. **Record current branch** for restoration
2. **Switch to main branch**: `git checkout main`
3. **Pull latest**: `git pull origin main`
4. **Create clean roadmap branch**: `git checkout -b roadmap-handoff-[task_name]`
5. **Add handoff entry** to `roadmap/roadmap.md` in "Active WIP Tasks" section:
   ```
   - **HANDOFF-[TASK_NAME]** 🟢 [description] - PR #[number] READY FOR HANDOFF
   ```
6. **Commit changes**: `git commit -m "docs(roadmap): Add handoff task [task_name]"`
7. **Push branch**: `git push -u origin roadmap-handoff-[task_name]`
8. **Create roadmap PR**: `gh pr create --title "docs(roadmap): Add handoff task [task_name]" --body "Roadmap update for handoff task"`
9. **Switch back**: `git checkout [original-branch]`

### Task Name Format

- Convert to uppercase: `logging_fix` → `LOGGING_FIX`
- Prefix with `HANDOFF-`: `HANDOFF-LOGGING_FIX`

### Error Handling

- If roadmap update fails, continue with handoff but notify user
- Validate PR number exists before adding to roadmap
- Ensure clean git state before main branch operations

## Copy-Paste Instructions

The command generates a formatted prompt that can be directly copied and pasted to hand off work to another developer or AI assistant. The prompt includes all necessary context, setup steps, and implementation guidance for immediate task continuation.
