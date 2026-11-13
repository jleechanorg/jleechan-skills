# Enhanced Memory MCP Integration Patterns

This document defines how commands should integrate with Memory MCP to create high-quality, actionable memory entries.

## Core Integration Principle

**Before any enhanced command execution**:
1. ✅ Search Memory MCP for relevant context
2. ✅ Extract specific technical terms from command arguments
3. ✅ Log search results transparently
4. ✅ Integrate found memories naturally into response
5. ✅ Capture new learnings with structured, detailed entries

## Enhanced Commands Memory Integration

### /learn Command Enhancement

**Current State**: Generic observations like "Values evidence-based development"
**Enhanced Pattern**:

```markdown
## /learn Enhanced Implementation

**Pre-execution**:
- Extract technical terms: error messages, file names, PR numbers, technologies
- Search memory: `mcp__memory-server__search_nodes(technical_terms)`
- Log: "🔍 Memory searched: X relevant memories found"

**Memory Capture Pattern**:
```json
{
  "name": "{specific_learning_identifier}",
  "entityType": "technical_learning",
  "observations": [
    "Context: {specific situation with timestamp}",
    "Technical Detail: {exact error/solution/code}",
    "Location: {file:line or command or environment}",
    "Solution Applied: {specific steps taken}",
    "Outcome: {measurable result}",
    "Reusable Pattern: {how to apply elsewhere}",
    "References: {PR links, commits, files}"
  ]
}
```

**Example Enhanced /learn**:
```bash
User: /learn the Firebase timeout issue was fixed by increasing timeout
Enhanced Capture:
{
  "name": "firebase_auth_timeout_fix_2025_07_23",
  "entityType": "technical_solution",
  "observations": [
    "Issue: Firebase Auth timeout in user authentication flow",
    "Error: 'firebase.auth().signInWithEmailAndPassword() timed out'",
    "Location: $PROJECT_ROOT/firebase_util.py:45",
    "Root Cause: Default 30s timeout insufficient for Auth API",
    "Solution: Increased timeout to 60s via firebase.auth().timeout = 60000",
    "Code Change: Line 12 firebase_util.py timeout parameter",
    "Test Result: 15/15 auth tests now pass",
    "Performance: Average auth time 2.3s, max observed 45s",
    "Commit: a1b2c3d 'Increase Firebase Auth timeout for reliability'"
  ]
}
```

### /debugp Command Enhancement

**Memory Pattern**: Capture complete debugging journey

```json
{
  "name": "{system}_{issue}_{resolution_date}",
  "entityType": "debug_session",
  "observations": [
    "Initial Symptom: {exact error message or behavior}",
    "Investigation Steps: {specific debugging actions taken}",
    "Key Discovery: {root cause finding with evidence}",
    "Failed Attempts: {what didn't work and why}",
    "Working Solution: {exact fix with code/config}",
    "Verification: {how solution was confirmed}",
    "Prevention: {how to avoid this issue future}"
  ]
}
```

### /fix Command Enhancement

**Memory Pattern**: Document fix implementation and validation

```json
{
  "name": "{component}_{fix_type}_{implementation_date}",
  "entityType": "fix_implementation",
  "observations": [
    "Problem Statement: {specific issue description}",
    "Impact Analysis: {who/what was affected}",
    "Fix Strategy: {approach chosen and why}",
    "Implementation: {exact code changes made}",
    "Testing Protocol: {how fix was validated}",
    "Rollback Plan: {how to undo if needed}",
    "Related Issues: {other similar problems this addresses}"
  ]
}
```

### /pr Command Enhancement

**Memory Pattern**: Preserve PR insights and workflow learnings

```json
{
  "name": "pr_{pr_number}_{insight_type}_{date}",
  "entityType": "pr_workflow_insight",
  "observations": [
    "PR: #{pr_number} {github_url}",
    "Changes Summary: {what was implemented}",
    "Review Insights: {valuable feedback received}",
    "Automated Feedback: {Copilot/bot suggestions}",
    "Resolution Strategy: {how issues were addressed}",
    "Workflow Lesson: {process improvement identified}",
    "Code Quality Impact: {metrics or observations}"
  ]
}
```

### /execute Command Enhancement

**Memory Pattern**: Track implementation patterns and outcomes

```json
{
  "name": "{feature}_{implementation_approach}_{outcome}",
  "entityType": "implementation_pattern",
  "observations": [
    "Task: {specific implementation goal}",
    "Approach: {technical strategy chosen}",
    "Key Decisions: {important choices made and rationale}",
    "Implementation Details: {specific code patterns used}",
    "Challenges Encountered: {obstacles and solutions}",
    "Performance Metrics: {measurable outcomes}",
    "Reusability: {how pattern applies to other contexts}"
  ]
}
```

## Memory Search Enhancement

**Enhanced Search Pattern**:
```markdown
🔍 **Searching memory for: "{extracted_terms}"**

**Search Strategy**:
- Primary terms: {technical_keywords}
- Related concepts: {semantic_expansions}
- Historical context: {timeline_relevance}

**Results Integration**:
- Found {X} relevant memories
- Key insights: {summarized_learnings}
- Applied context: {how_memories_informed_response}
```

## Relation Building

**Automatic Relation Creation**:
- Link new entries to existing technical entities
- Connect fixes to original problems
- Associate patterns with user preferences
- Build implementation genealogies

**Example Relations**:
```json
[
  {
    "from": "firebase_auth_timeout_fix_2025_07_23",
    "to": "firebase_auth_timeout_2025_07_23",
    "relationType": "fixes"
  },
  {
    "from": "firebase_auth_timeout_fix_2025_07_23",
    "to": "mvp_site_firebase_util",
    "relationType": "implemented_in"
  }
]
```

## Quality Validation

**Pre-storage Validation**:
- ✅ Contains specific technical details
- ✅ Includes actionable information
- ✅ References external artifacts
- ✅ Uses canonical entity names
- ✅ Provides measurable outcomes
- ✅ Links to related memories

**Enhancement Triggers**:
- If entry lacks specifics → Prompt for technical details
- If no references → Ask for PR/commit/file links
- If vague outcome → Request measurable results
- If isolated → Search for related entities to link

## Implementation Guidelines

**For Command Authors**:
1. **Always search first**: Use relevant terms to find existing context
2. **Extract specifics**: Pull out file names, error messages, PR numbers
3. **Structure observations**: Use the patterns defined above
4. **Build relations**: Connect to existing memories explicitly
5. **Validate quality**: Ensure entries meet high-quality criteria

**Memory Enhancement Workflow**:
```bash
# 1. Search for context
search_terms = extract_technical_terms(command_args)
existing_memories = mcp__memory-server__search_nodes(search_terms)

# 2. Process with context
response = process_command_with_context(existing_memories)

# 3. Capture new learnings
new_learning = structure_memory_entry(response, patterns)
mcp__memory-server__create_entities([new_learning])

# 4. Build relations
relations = identify_relations(new_learning, existing_memories)
mcp__memory-server__create_relations(relations)
```
