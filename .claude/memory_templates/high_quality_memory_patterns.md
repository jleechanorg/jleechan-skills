# High-Quality Memory MCP Entry Patterns

Based on Memory MCP best practices research (via Perplexity API integration from BasicMachines, LobHub, Orca Security, Dynatrace sources), this document provides templates for creating actionable, searchable, and technically detailed memory entries.

## Research Foundation

**External Validation Sources**:
- **BasicMachines**: Memory MCP linked knowledge graph patterns
- **LobHub**: Atomic precision and semantic searchability standards
- **Orca Security**: Context-aware memory organization principles
- **Dynatrace**: Technical detail requirements and quality validation
- **Research Method**: Perplexity API query for "Memory MCP best practices" (July 2025)

## Core Principles

1. **Actionable Technical Detail**: Include specific error messages, file paths, code snippets
2. **Linked Knowledge Graphs**: Connect entities through explicit relations
3. **Atomic Precision**: Each observation should be specific and clear
4. **Canonical Naming**: Use exact names for disambiguation
5. **Contextual Grouping**: Organize by project/system for navigation

## Template Categories

### 1. Technical Issue Resolution

**Pattern**: `{system}_{issue_type}_{timestamp}`

```json
{
  "name": "firebase_auth_timeout_2025_07_23",
  "entityType": "technical_issue",
  "observations": [
    "Issue: Firebase Auth timeout in $PROJECT_ROOT/firebase_util.py:45",
    "Error: 'Request timed out after 30 seconds'",
    "Context: User authentication during campaign creation",
    "Root Cause: Default timeout too short for Firebase Auth API",
    "Solution: Increased timeout to 60 seconds in firebase_util.py:12",
    "Fix Commit: a1b2c3d - 'Increase Firebase Auth timeout to 60s'",
    "Test Results: 15/15 auth tests pass after fix",
    "Related Files: $PROJECT_ROOT/firebase_util.py, $PROJECT_ROOT/test_auth.py"
  ]
}
```

### 2. Code Implementation Learning

**Pattern**: `{feature}_{implementation_approach}_{outcome}`

```json
{
  "name": "character_creation_validation_successful_pattern",
  "entityType": "implementation_pattern",
  "observations": [
    "Feature: Character creation form validation",
    "Implementation: Pydantic BaseModel with custom validators",
    "Location: $PROJECT_ROOT/models/character.py:25-67",
    "Key Pattern: @validator('ability_scores') with range checks",
    "Code Snippet: def validate_ability_scores(cls, v):\\n    if not (3 <= v <= 18):\\n        raise ValueError('Ability scores must be between 3 and 18')",
    "Testing: 12 edge cases covered in test_character_validation.py",
    "Integration: Works seamlessly with Flask-WTF forms",
    "Performance: <1ms validation time for full character sheet",
    "Reusable For: Equipment validation, spell validation, NPC creation"
  ]
}
```

### 3. Development Workflow Insights

**Pattern**: `{workflow_step}_{outcome}_{lessons}`

```json
{
  "name": "pr_review_copilot_integration_lessons",
  "entityType": "workflow_insight",
  "observations": [
    "Context: PR #627 review process with GitHub Copilot feedback",
    "Discovery: Copilot suggestions appear as inline review comments only",
    "API Endpoint: gh api repos/owner/repo/pulls/PR#/comments required",
    "Missed Pattern: gh pr view --json comments doesn't include inline feedback",
    "Implementation Fix: Added copilot comment retrieval to /copilot command",
    "Code Location: .claude/commands/copilot.md:45-67",
    "Testing: Validated with 3 PRs containing Copilot suggestions",
    "Impact: 100% coverage of automated feedback vs 60% previously"
  ]
}
```

### 4. Architecture Decisions

**Pattern**: `{component}_{architectural_choice}_{rationale}`

```json
{
  "name": "memory_mcp_backup_github_architecture",
  "entityType": "architecture_decision",
  "observations": [
    "Decision: GitHub repository backup for Memory MCP data",
    "Repository: https://github.com/jleechanorg/worldarchitect-memory-backups",
    "Architecture: Daily automated backups with historical preservation",
    "Rationale: Persistent storage beyond local cache, version history",
    "Implementation: Cron job + GitHub API + append-only strategy",
    "Scripts: daily_backup.sh, health_monitor.sh, setup_automation.sh",
    "Data Flow: ~/.cache/mcp-memory/memory.json → GitHub → historical/",
    "Benefits: Disaster recovery, audit trail, cross-machine access",
    "Trade-offs: GitHub API limits, requires token management"
  ]
}
```

### 5. User Interaction Patterns

**Pattern**: `{user_behavior}_{system_response}_{optimization}`

```json
{
  "name": "user_prefers_concise_responses_optimization",
  "entityType": "user_preference_pattern",
  "observations": [
    "User: jleechan2015",
    "Preference: Direct, concise responses over lengthy analysis",
    "Evidence: 'skip long thinking process and get straight to the point'",
    "Context: CLAUDE.md compliance, technical problem solving",
    "Optimal Response Pattern: Bullet points, essential info only",
    "Implementation: CLAUDE.md rule 'MUST answer concisely with fewer than 4 lines'",
    "Exception Cases: Complex debugging requires evidence-based approach",
    "Measurement: Response satisfaction increased when <4 lines used"
  ]
}
```

## Relation Patterns

### Technical Relations
- `{entity1} caused_by {entity2}` - Error causation
- `{entity1} fixed_by {entity2}` - Solution relationships
- `{entity1} implemented_in {entity2}` - Code location mapping
- `{entity1} tested_by {entity2}` - Test coverage tracking

### Workflow Relations
- `{entity1} preceded_by {entity2}` - Process sequences
- `{entity1} requires {entity2}` - Dependencies
- `{entity1} optimizes {entity2}` - Performance improvements
- `{entity1} supersedes {entity2}` - Evolution tracking

### User Relations
- `{entity1} preferred_by {entity2}` - User preferences
- `{entity1} reported_by {entity2}` - Issue attribution
- `{entity1} requested_by {entity2}` - Feature requests

## Quality Checklist

**High-Quality Entry Must Include:**
- ✅ Specific technical details (file paths, line numbers, error messages)
- ✅ Actionable information (how to reproduce, fix, or implement)
- ✅ Context (when, why, what circumstances)
- ✅ References (PRs, commits, files, documentation)
- ✅ Measurable outcomes (test results, performance metrics)
- ✅ Clear entity names using canonical identifiers
- ✅ Explicit relations to other entities

**Avoid Low-Quality Patterns:**
- ❌ Vague statements ("user likes X", "system has issue")
- ❌ Missing context (no timestamps, no circumstances)
- ❌ No actionable detail (can't reproduce or implement)
- ❌ Generic observations (could apply to any system)
- ❌ Missing references (no way to verify or locate)

## Usage in Commands

Commands enhanced with these patterns:
- `/learn` - Captures structured technical learning
- `/debugp` - Records issue resolution with full context
- `/fix` - Documents fixes with implementation details
- `/pr` - Preserves PR review insights and workflow lessons
- `/execute` - Tracks implementation patterns and outcomes
