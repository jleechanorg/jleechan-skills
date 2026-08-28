# File Justification Protocol

**Purpose**: Before creating or modifying ANY file, you MUST document the justification to prevent unnecessary file creation and ensure changes are well-reasoned.

## When This Protocol Applies

- Creating a NEW file (highest scrutiny)
- Modifying an EXISTING file
- All PR changes (each file touched needs justification)

## Justification Template

For EACH file you touch, document:

```
### File: <filename>

**GOAL**: What are you trying to achieve?
**MODIFICATION**: What specific change are you making?
**NECESSITY**: Why is this change required? Why can't it be done differently?
**INTEGRATION PROOF**: How does this integrate with existing code?
```

## New File Creation - Extreme Scrutiny

**Default: NO NEW FILES** - You must prove why integration into existing files is impossible.

### Pre-Write Checklist (MANDATORY before creating any new file)

1. **Assume existing files can handle it** - Search for similar functionality
2. **Identify integration targets** - Which existing files could contain this code?
3. **Attempt integration first** - Try adding to existing file before creating new
4. **Document why integration failed** - Concrete reason, not "cleaner this way"

### Integration Hierarchy (try in order)

1. Existing file with similar functionality
2. Existing utility/helper file
3. Existing `__init__.py`
4. Existing test file (for test code)
5. Existing class as a method
6. Config file
7. **LAST RESORT**: New file (with full justification)

## Examples

### Good Justification (Modifying Existing)
```
### File: $PROJECT_ROOT/llm_response.py

**GOAL**: Add backward compatibility for outcome_resolution field
**MODIFICATION**: Add property that falls back to outcome_resolution when action_resolution is missing
**NECESSITY**: API clients already use action_resolution; changing the field name would break them
**INTEGRATION PROOF**: Property pattern matches existing properties in this class (lines 45-67)
```

### Good Justification (New File - Justified)
```
### File: $PROJECT_ROOT/action_resolution_utils.py (NEW)

**GOAL**: Centralize action_resolution/outcome_resolution fallback logic
**MODIFICATION**: Create helper module with get_action_resolution() function
**NECESSITY**: Same logic duplicated in llm_response.py (22 lines) and world_logic.py (13 lines)
**INTEGRATION PROOF**:
- Could not add to llm_response.py - world_logic.py would create circular import
- Could not add to world_logic.py - llm_response.py would create circular import
- New utils file breaks the dependency cycle
```

### Bad Justification (Rejected)
```
### File: $PROJECT_ROOT/new_helper.py (NEW)

**GOAL**: Add helper function
**MODIFICATION**: Create new file with helper
**NECESSITY**: Cleaner to have it separate  <-- NOT VALID
**INTEGRATION PROOF**: None attempted  <-- MUST ATTEMPT
```

## File Placement Rules

If a new file is justified, place it correctly:

| Code Type | Location |
|-----------|----------|
| Python module | `$PROJECT_ROOT/` or appropriate submodule |
| Scripts | `scripts/` |
| Tests | `$PROJECT_ROOT/tests/` |
| Commands | `.claude/commands/` |
| Skills | `.claude/skills/` |

**NEVER** create new files in project root.

## Banned Patterns

- `*_v2.py` - Edit existing file
- `*_new.py` - Edit existing file
- `*_backup.py` - Use git
- `*_old.py` - Delete and replace

## Quick Reference

Before ANY file operation:
1. What existing file could contain this? (Search first)
2. Why can't I add this to that file? (Valid reason required)
3. Have I documented GOAL/MODIFICATION/NECESSITY/INTEGRATION PROOF?

**If you cannot answer these questions, do not create the file.**
