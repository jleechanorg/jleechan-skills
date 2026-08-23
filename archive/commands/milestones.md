---
description: Milestones Command
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

# Milestones Command

**Purpose**: Break tasks into N phases or suggest optimal milestone count

**Action**: Create milestones, update scratchpad, commit each phase

**Usage**:
- `/milestones N` - Break into N phases
- `/milestones suggest` - Suggest optimal count

**Implementation**:
- For `/milestones N`: Create N milestone phases, update scratchpad, commit each
- For `/milestones suggest`: Analyze complexity, suggest 3-7 milestones with rationale
- Each milestone should be a discrete, testable deliverable
