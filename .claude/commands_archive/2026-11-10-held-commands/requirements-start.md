---
description: Start Requirements Gathering
type: llm-orchestration
execution_mode: immediate
---
## ⚡ EXECUTION INSTRUCTIONS FOR CLAUDE
**When this command is invoked, YOU (Claude) must execute these steps immediately:**
**This is NOT documentation - these are COMMANDS to execute right now.**
**Use TodoWrite to track progress through multi-phase workflows.**

## 🚨 EXECUTION WORKFLOW

### Phase 1: Full Workflow:

**Action Steps:**
1. Review the reference documentation below and execute the detailed steps.

### Phase 1: Initial Setup & Codebase Analysis

**Action Steps:**
1. Create timestamp-based folder: requirements/YYYY-MM-DD-HHMM-[slug]
2. Extract slug from $ARGUMENTS (e.g., "add user profile" → "user-profile")
3. Create initial files:
   - 00-initial-request.md with the user's request
   - metadata.json with status tracking
4. Read and update requirements/.current-requirement with folder name
5. Use mcp__RepoPrompt__get_file_tree (if available) to understand overall structure:
   - Get high-level architecture overview
   - Identify main components and services
   - Understand technology stack
   - Note patterns and conventions

### Phase 2: Context Discovery Questions

**Action Steps:**
1. Generate the five most important yes/no questions to understand the problem space:
   - Questions informed by codebase structure
   - Questions about user interactions and workflows
   - Questions about similar features users currently use
   - Questions about data/content being worked with
   - Questions about external integrations or third-party services
   - Questions about performance or scale expectations
   - Write all questions to 01-discovery-questions.md with smart defaults
   - **ASK ALL QUESTIONS AT ONCE** in a single message with numbered list
   - Record all answers immediately in 02-discovery-answers.md and update metadata.json

### Phase 3: Targeted Context Gathering (Autonomous with Parallel Execution)

**Action Steps:**
1. After all discovery questions answered:
   - **USE PARALLEL TASK AGENTS** via Task tool for deep investigation
   - Launch agents for: file analysis, pattern matching, similar feature comparison
   - Use WebSearch and Context7 MCP for best practices and library documentation
   - Agents should investigate specific file paths and implementation details
   - Document findings in 03-context-findings.md including:
     - Specific files that need modification
     - Exact patterns to follow
     - Similar features analyzed in detail
     - Technical constraints and considerations
     - Integration points identified

### Phase 4: Expert Requirements Questions

**Action Steps:**
1. Now ask questions like a senior developer who knows the codebase:
   - Write the top 5 most pressing unanswered detailed yes/no questions to 04-detail-questions.md
   - Questions should be as if you were speaking to the product manager who knows nothing of the code
   - These questions are meant to to clarify expected system behavior now that you have a deep understanding of the code
   - Include smart defaults based on codebase patterns
   - **ASK ALL EXPERT QUESTIONS AT ONCE** in a single message
   - Record all answers immediately in 05-detail-answers.md as received

### Phase 5: Requirements Documentation

**Action Steps:**
1. Generate comprehensive requirements spec in 06-requirements-spec.md:
   - Problem statement and solution overview
   - Functional requirements based on all answers
   - Technical requirements with specific file paths
   - Implementation hints and patterns to follow
   - Acceptance criteria
   - Assumptions for any unanswered questions

### Discovery Questions (Phase 2):

**Action Steps:**
```

### Expert Questions (Phase 4):

**Action Steps:**
```

### Phase Transitions:

**Action Steps:**
1. After each phase, announce: "Phase complete. Starting [next phase]..."
2. Save all work before moving to next phase
3. User can check progress anytime with /requirements-status

## 📋 REFERENCE DOCUMENTATION

# Start Requirements Gathering

*Taken from the excellent requirements gathering system by [rizethereum](https://github.com/rizethereum/claude-code-requirements-builder). Thank you for sharing this thoughtful approach!*

Begin gathering requirements for: $ARGUMENTS

## Question Formats:

## Q1: Will users interact with this feature through a visual interface?

**Default if unknown:** Yes (most features have some UI component)

## Q2: Does this feature need to work on mobile devices?

**Default if unknown:** Yes (mobile-first is standard practice)

## Q3: Will this feature handle sensitive or private user data?

**Default if unknown:** Yes (better to be secure by default)

## Q4: Do users currently have a workaround for this problem?

**Default if unknown:** No (assuming this solves a new need)

## Q5: Will this feature need to work offline?

**Default if unknown:** No (most features require connectivity)
```

## Q7: Should we extend the existing UserService at services/UserService.ts?

**Default if unknown:** Yes (maintains architectural consistency)

## Q8: Will this require new database migrations in db/migrations/?

**Default if unknown:** No (based on similar features not requiring schema changes)
```

## Important Rules:

- ONLY yes/no questions with smart defaults
- **ASK ALL QUESTIONS AT ONCE** for faster iteration
- Write ALL questions to file BEFORE asking any
- Stay focused on requirements (no implementation)
- Use actual file paths and component names in detail phase
- Document WHY each default makes sense
- **USE PARALLEL TASK AGENTS** for investigation phases
- Use tools available if recommended ones aren't installed or available

## Metadata Structure:

```json
{
  "id": "feature-slug",
  "started": "ISO-8601-timestamp",
  "lastUpdated": "ISO-8601-timestamp",
  "status": "active",
  "phase": "discovery|context|detail|complete",
  "progress": {
    "discovery": { "answered": 0, "total": 5 },
    "detail": { "answered": 0, "total": 0 }
  },
  "contextFiles": ["paths/of/files/analyzed"],
  "relatedFeatures": ["similar features found"]
}
```
