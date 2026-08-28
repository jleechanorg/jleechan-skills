---
name: llm-json-schema-documentation
description: Document both INPUT and OUTPUT JSON schemas for LLM-driven features to prevent data flow confusion
---

# LLM JSON Schema Documentation

**Purpose:** Ensure LLM-driven features have complete schema documentation covering both input (what LLM receives) and output (what LLM returns).

## The Core Principle

**JSON Schema Over Text Instructions** - Tell the LLM what data structures exist, not how to write the content.

## Critical Requirements

### 1. Document BOTH Input and Output Schemas

**Common Mistake:** Documenting only OUTPUT schema while assuming LLM "just knows" what INPUT fields are available.

**✅ CORRECT Approach:**
```markdown
### Input Schema
When `npc_data` is present in your input, each NPC entry contains:
- `tier`: (string) Social HP tier - commoner | merchant | noble | god
- `name`: (string) NPC display name
- `role`: (string) NPC role/title

### Output Schema
When Social HP is active, populate:
- `social_hp_challenge.npc_tier`: (string) **Extract from npc_data.tier**
- `social_hp_challenge.npc_name`: (string) **Extract from npc_data.name**
```

**❌ WRONG Approach:**
```markdown
### Output Schema
- `social_hp_challenge.npc_tier`: (string) NPC tier
- `social_hp_challenge.npc_name`: (string) NPC name
# Missing: Where does the LLM get this data from?
```

### 2. Link Input to Output with Extraction Notes

**Pattern:**
- **Input field:** `npc_data.tier`
- **Output field:** `social_hp_challenge.npc_tier`
- **Extraction note:** "Extract from npc_data.tier"

This prevents "where does this data come from?" confusion.

### 3. Show Examples, Not Templates

**✅ Examples** (Reference - show good patterns):
```markdown
**Example Output:**
```
[SOCIAL SKILL CHALLENGE: Lady Ashwood]
Objective: Access family archives
Social HP: 5/5 | Status: RESISTING
```
```

**❌ Templates** (Prescription - constrains LLM):
```markdown
**Required Format:**
[SOCIAL SKILL CHALLENGE: {npc_name}]
Objective: {objective}
Social HP: {hp}/{max} | Status: {status}
# This tells LLM HOW to write, reducing autonomy
```

### 4. Server-Side Validation

**Pattern:** LLM Decides, Server Executes
```python
def validate_output(self):
    """Server validates LLM output structure."""
    # Check required fields exist
    if not self.social_hp_challenge.get("npc_name"):
        logging_util.warning("Missing required field: npc_name")

    # Cross-validate JSON with narrative
    if self.social_hp_challenge and not self.narrative_contains_box():
        logging_util.warning("JSON exists but narrative missing box")
```

## Implementation Checklist

When adding LLM-driven features:

- [ ] **Document INPUT schema** - What data does the LLM receive?
  - [ ] List all available input fields
  - [ ] Document field types and valid values
  - [ ] Show example input data structure

- [ ] **Document OUTPUT schema** - What data must the LLM return?
  - [ ] List all required output fields
  - [ ] Document field types and constraints
  - [ ] Show example output data structure

- [ ] **Link Input to Output** - How does data flow?
  - [ ] Add extraction notes: "Extract from input_field.name"
  - [ ] Show mapping between input and output fields
  - [ ] Document any transformations or calculations

- [ ] **Provide Examples** - Show good patterns (not templates)
  - [ ] Include narrative examples demonstrating natural integration
  - [ ] Show JSON alongside narrative (both required)
  - [ ] Avoid prescriptive templates that constrain LLM

- [ ] **Server Validation** - Enforce structure post-generation
  - [ ] Validate required fields exist
  - [ ] Type coercion for numeric/boolean fields
  - [ ] Cross-validation between JSON and narrative
  - [ ] Log warnings for missing/inconsistent data

## Example: Social HP System

**Problem:** LLM didn't know where to get `npc_tier` for output.

**Solution:**
1. **INPUT schema:** Documented `npc_data.tier` field exists
2. **OUTPUT schema:** Added `social_hp_challenge.npc_tier` field
3. **Link:** "Extract from npc_data.tier"
4. **Validation:** Server validates both JSON and narrative exist

**Files Updated:**
- `$PROJECT_ROOT/prompts/game_state_instruction.md`: INPUT/OUTPUT schemas
- `$PROJECT_ROOT/narrative_response_schema.py`: Server validation
- `CLAUDE.md`: Architectural principle documentation

## Why This Matters

**Prevents Confusion:**
- LLM knows what input fields are available to read
- LLM knows what output fields are expected
- Clear data flow from input → LLM → output

**Preserves Autonomy:**
- Schema defines WHAT data exists, not HOW to write content
- LLM decides narrative format based on context
- Examples show patterns, not rigid templates

**Enables Validation:**
- Server can validate structure post-generation
- Type coercion handles edge cases
- Cross-validation catches inconsistencies

## Anti-Patterns to Avoid

**❌ Template-Based Instructions**
```markdown
Write exactly this format:
[SOCIAL SKILL CHALLENGE: {npc_name}]
```
*Problem: Reduces LLM autonomy, constrains creativity*

**❌ Undocumented Input Fields**
```markdown
Return npc_tier in your output.
```
*Problem: LLM doesn't know where to get this data*

**❌ Missing Extraction Notes**
```markdown
- `output.tier`: (string) NPC tier
```
*Problem: No link to input field source*

**❌ Pure Text Instructions**
```markdown
When an NPC resists persuasion, describe their resistance narratively.
```
*Problem: No schema - server can't validate or track state*

## Related Documentation

- **CLAUDE.md**: "JSON Schema Over Text Instructions" principle
- **LLM Architecture Principles**: "LLM Decides, Server Executes"
- **Example Implementation**: Social HP PR #2915

---

**Last Updated:** 2025-01-07 (Social HP all-tiers PR)
