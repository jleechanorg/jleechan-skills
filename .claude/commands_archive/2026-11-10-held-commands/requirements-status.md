---
description: Check Requirements Status
type: llm-orchestration
execution_mode: immediate
---
## ⚡ EXECUTION INSTRUCTIONS FOR CLAUDE
**When this command is invoked, YOU (Claude) must execute these steps immediately:**
**This is NOT documentation - these are COMMANDS to execute right now.**
**Use TodoWrite to track progress through multi-phase workflows.**

## 🚨 EXECUTION WORKFLOW

### Phase Transitions:

**Action Steps:**
1. Discovery complete → Run context gathering → Generate detail questions
2. Detail complete → Generate final requirements spec

## 📋 REFERENCE DOCUMENTATION

# Check Requirements Status

*Taken from the excellent requirements gathering system by [rizethereum](https://github.com/rizethereum/claude-code-requirements-builder). Thank you for sharing this thoughtful approach!*

Show current requirement gathering progress and continue.

## Instructions:

1. Read requirements/.current-requirement
2. If no active requirement:
   - Show message: "No active requirement gathering"
   - Suggest /requirements-start or /requirements-list
   - Exit

3. If active requirement exists:
   - Read metadata.json for current phase and progress
   - Show formatted status
   - Load appropriate question/answer files
   - Continue from last unanswered question

## Status Display Format:

```
📋 Active Requirement: [name]
Started: [time ago]
Phase: [Discovery/Detail]
Progress: [X/Y] questions answered

[Show last 3 answered questions with responses]

Next Question:
[Show next unanswered question with default]
```

## Continuation Flow:

1. Read next unanswered question from file
2. Present to user with default
3. Accept yes/no/idk response
4. Update answer file
5. Update metadata progress
6. Move to next question or phase
