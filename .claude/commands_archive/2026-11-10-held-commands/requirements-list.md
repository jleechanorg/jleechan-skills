---
description: List All Requirements
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

# List All Requirements

*Taken from the excellent requirements gathering system by [rizethereum](https://github.com/rizethereum/claude-code-requirements-builder). Thank you for sharing this thoughtful approach!*

Display all requirements with their status and summaries.

## Instructions:

1. Check requirements/.current-requirement for active requirement
2. List all folders in requirements/ directory
3. For each requirement folder:
   - Read metadata.json
   - Extract key information
   - Format for display

4. Sort by:
   - Active first (if any)
   - Then by status: complete, incomplete
   - Then by date (newest first)

## Display Format:

```
📚 Requirements Documentation

🔴 ACTIVE: profile-picture-upload
   Phase: Discovery (3/5) | Started: 30m ago
   Next: Q4 about file restrictions

✅ COMPLETE:
2025-01-26-0900-dark-mode-toggle
   Status: Ready for implementation | 15 questions answered
   Summary: Full theme system with user preferences
   Linked PR: #234 (merged)

2025-01-25-1400-export-reports  
   Status: Implemented | 22 questions answered
   Summary: PDF/CSV export with filtering
   
⚠️ INCOMPLETE:
2025-01-24-1100-notification-system
   Status: Paused at Detail phase (2/8) | Last: 2 days ago
   Summary: Email/push notifications for events
   
📈 Statistics:
- Total: 4 requirements
- Complete: 2 (13 avg questions)
- Active: 1
- Incomplete: 1
```

## Additional Features:

1. Show linked artifacts:
   - Development sessions
   - Pull requests
   - Implementation status

2. Highlight stale requirements:
   - Mark if incomplete > 7 days
   - Suggest resuming or ending

3. Quick actions:
   - "View details: /requirements-show [id]"
   - "Resume incomplete: /requirements-status"
   - "Start new: /requirements-start [description]"
