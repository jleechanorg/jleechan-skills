# LLM Prompt Engineering - System Instruction Best Practices

**Purpose**: Guidelines for writing effective system instructions that LLMs actually follow, based on real debugging experiences.

## Core Principle

**When LLMs ignore instructions, it's usually the prompt's fault, not the LLM's.**

LLMs are excellent at following clear, explicit instructions but will apply reasoning and judgment to ambiguous ones. This guide shows how to write prompts that remove ambiguity.

## The Five Critical Rules

### 1. Use Unconditional Language for Critical Instructions

**Problem**: Conditional language gives LLMs room to apply judgment and override instructions.

**Real Example from CharacterCreationAgent Bug**:

❌ **Conditional (LLM overrode this)**:
```markdown
If `character_creation_in_progress` is true, clear it.
```

**LLM's Response**:
> "Character creation flag 'character_creation_in_progress' is still true. Since we are still in the setup phase, I am maintaining it until the user is actually ready to enter story mode."

The LLM applied judgment: "I think we're still setting up" → overrode instruction.

✅ **Unconditional (LLM followed this)**:
```markdown
## 🎭 CRITICAL: Character Creation Flag - CLEAR IT NOW

IF YOU SEE `custom_campaign_state.character_creation_in_progress` ANYWHERE IN YOUR INPUT, IT MUST BE FALSE IN YOUR OUTPUT.

NO EXCEPTIONS. NO JUDGMENT. NO "BUT WE'RE STILL SETTING UP".

YOU ARE STORY MODE. FLAG MUST BE FALSE. ALWAYS.
```

**LLM's Response**: ✅ Cleared the flag without judgment.

**When to Use Each**:
- **Conditional**: Instructions where LLM reasoning is desired (narrative choices, character suggestions)
- **Unconditional**: Critical state management, flag clearing, mandatory fields

### 2. Document INPUT and OUTPUT Schemas Explicitly

**Problem**: LLMs can't follow instructions about data structures they don't understand.

**MANDATORY for every system prompt:**

```markdown
## Input Schema: What You Receive

You receive a `GAME STATE` section with this structure:
```json
{
  "custom_campaign_state": {
    "flag_name": true/false,  ← Document exact path
    "nested_field": {
      "value": "..."
    }
  },
  "player_character_data": {...}
}
```

**CHECK `custom_campaign_state.flag_name` to understand current status.**

## Output Schema: What You Must Return

Your response MUST include:
```json
{
  "state_updates": {
    "custom_campaign_state": {
      "flag_name": false  ← Show exact structure
    }
  }
}
```

**MANDATORY FIELDS:**
- `state_updates.custom_campaign_state.flag_name` - Always update this
- `state_updates.player_character_data` - Update as choices are made
```

**Why This Works**:
- Shows exact field paths (no ambiguity about nesting)
- Labels mandatory vs optional fields
- Provides copy-pasteable JSON structure
- Uses visual cues (← arrows, bold text)

### 3. Position Critical Instructions in Top 50 Lines

**Problem**: Instruction compliance degrades with position in long prompts.

**Compliance by Position** (observed in real debugging):
- **Lines 1-50**: High compliance
- **Lines 51-500**: Medium compliance
- **Lines 500+**: Low compliance (LLM often ignores)

**Real Example**:

❌ **Failed (line 525 in 2064-line file)**:
```markdown
### 🎭 Character Creation Flag Management
(line 525 of 2064)
```
Result: LLM ignored instruction

✅ **Succeeded (line 22 in same file)**:
```markdown
## 🎭 CRITICAL: Character Creation Flag - CLEAR IT NOW
(line 22 of 2064)
```
Result: LLM followed instruction

**How to Position**:
1. Place critical instructions at lines 1-50
2. Use clear visual separators (`## CRITICAL`, `---`)
3. Use emojis for visual anchors (🎭, 🚨, ⚠️)
4. Repeat critical instructions before related sections

### 4. Enforce Prompt Size Budgets

**Problem**: Prompt bloat causes LLMs to ignore instructions.

**Target Token Counts per Agent Type**:

| Agent Type | Target Lines | Max Lines | Current Status |
|------------|--------------|-----------|----------------|
| Character Creation | 600-800 | 1000 | ✅ 607 (after removing mechanics) |
| Story Mode | 1500-2000 | 2500 | ⚠️ 2064 (at limit) |
| Combat Mode | 1200-1800 | 2000 | - |
| Info Mode | 500-800 | 1000 | - |
| God Mode | 400-600 | 800 | - |

**How “Current Status” is measured**:
- Count lines for the prompt files actually loaded by the agent (see `REQUIRED_PROMPT_ORDER` / `OPTIONAL_PROMPTS` in `$PROJECT_ROOT/agents.py` and prompt mapping in `$PROJECT_ROOT/agent_prompts.py`), then sum `wc -l` across that set.
- Treat the result as directional (line-count is a proxy for token count).

**Red Flags**:
- >50% of token budget used = LLM starts making judgment calls
- >75% of token budget used = LLM ignores critical instructions
- >90% of token budget used = unpredictable behavior

**Real Example**:

❌ **Before (1236 lines)**:
- CharacterCreationAgent loaded mechanics_system_instruction.md (629 lines)
- LLM applied judgment to flag clearing instruction
- Test failed

✅ **After (607 lines, 50% reduction)**:
- Removed mechanics bloat (combat/rewards not needed for creation)
- LLM followed flag clearing instruction
- Test passed

**How to Cut Bloat**:
1. Remove cross-domain content (combat from creation, narrative from info)
2. Consolidate redundant sections
3. Move reference tables to appendix
4. Use shorter examples
5. Cut explanatory text that repeats obvious points

### 5. Debug via Log Evidence

**Problem**: When instructions fail, you need to see WHY the LLM ignored them.

**Debugging Checklist**:

1. **Check LLM's thinking logs** (if available):
   ```
   "Character creation flag 'character_creation_in_progress' is still true.
   Since we are still in the setup phase, I am maintaining it..."
   ```
   This reveals judgment override behavior.

2. **Verify instruction position**:
   ```bash
   grep -n "critical instruction text" prompt_file.md
   ```
   If line number > 500 in long file → reposition to top

3. **Count prompt lines**:
   ```bash
   wc -l $PROJECT_ROOT/prompts/*.md
   ```
   If total >1500 lines → identify bloat to cut

4. **Test conditional vs unconditional**:
   - Change "if X, do Y" → "X MUST BE Y. ALWAYS."
   - Rerun test
   - Check if behavior changes

5. **Add explicit schemas**:
   - Add INPUT schema section
   - Add OUTPUT schema section
   - Show exact field paths
   - Rerun test

## Checklist for New System Prompts

Before deploying any system prompt, verify:

- [ ] Critical instructions in lines 1-50
- [ ] INPUT schema documented with exact field paths
- [ ] OUTPUT schema documented with mandatory field list
- [ ] Unconditional language for critical state changes
- [ ] Total lines < budget for agent type
- [ ] No cross-domain content (combat in creation, etc.)
- [ ] Visual separators around critical sections
- [ ] Tested with actual LLM calls (not just reading prompt)

## Common Failure Patterns

### Pattern 1: "I think..." Override

**Symptom**: LLM says "I think we're still..." and ignores instruction.

**Diagnosis**: Conditional language gave room for judgment.

**Fix**: Change to unconditional ("MUST BE X. NO EXCEPTIONS.")

### Pattern 2: Silent Non-Compliance

**Symptom**: LLM doesn't mention instruction, just doesn't follow it.

**Diagnosis**: Instruction buried too deep in prompt (line 500+).

**Fix**: Move to top 50 lines with visual separator.

### Pattern 3: Field Path Confusion

**Symptom**: LLM updates wrong field or nesting level.

**Diagnosis**: Schema not documented explicitly.

**Fix**: Add INPUT/OUTPUT schemas with exact paths.

### Pattern 4: Intermittent Compliance

**Symptom**: Instruction followed sometimes, ignored other times.

**Diagnosis**: Prompt too long, LLM attention drifting.

**Fix**: Cut bloat to reduce prompt size by 30-50%.

## Examples: Before and After

### Example 1: Flag Clearing

**Before (Failed)**:
```markdown
### Character Creation Flag Management
(line 525 of 2064-line file)

If `character_creation_in_progress` is true, clear it when user is done.
```

**After (Succeeded)**:
```markdown
## 🎭 CRITICAL: Character Creation Flag - CLEAR IT NOW
(line 22 of 2064-line file)

IF YOU SEE `custom_campaign_state.character_creation_in_progress` ANYWHERE, IT MUST BE FALSE.

NO EXCEPTIONS. NO JUDGMENT. FLAG MUST BE FALSE. ALWAYS.
```

**Result**: 100% compliance vs 0% compliance.

### Example 2: Schema Documentation

**Before (Ambiguous)**:
```markdown
Update the character creation flag when done.
```

**After (Explicit)**:
```markdown
## Input Schema
```json
{
  "custom_campaign_state": {
    "character_creation_in_progress": true/false  ← CHECK THIS
  }
}
```

## Output Schema
```json
{
  "state_updates": {
    "custom_campaign_state": {
      "character_creation_in_progress": false  ← MUST SET THIS
    }
  }
}
```
```

**Result**: LLM knows exact field paths and structure.

## Token Budget Calculation

**Rough estimation** (for planning):
- 1 line of markdown ≈ 10-20 tokens
- 1000 lines ≈ 10,000-20,000 tokens
- Most models: 128K-200K input token limit
- Reserve 50-75% for story history and game state

**Example Budget** (200K token limit):
- Story history: 100K tokens (story entries, game state)
- System prompt: 20K tokens (~1500-2000 lines)
- Output buffer: 60K tokens (LLM response)
- Safety margin: 20K tokens

**Red line**: If system prompt >25K tokens (>2000 lines), cut bloat immediately.

## Validation Testing

**Test every system prompt change**:

```python
# Create test that validates instruction compliance
def test_critical_instruction():
    # Set up scenario where instruction should trigger
    game_state = {"custom_campaign_state": {"flag": True}}

    # Call LLM with prompt
    response = call_llm(prompt, game_state, user_input)

    # Verify compliance
    assert response["state_updates"]["custom_campaign_state"]["flag"] == False, \
        f"CRITICAL INSTRUCTION IGNORED: flag should be False, got {response}"
```

Run this test BEFORE merging prompt changes.

## Real-World Case Study

**Problem**: CharacterCreationAgent not clearing `character_creation_in_progress` flag.

**Symptoms**:
- Agent transitioned correctly (CharacterCreationAgent → StoryModeAgent)
- But flag remained True
- Next turn incorrectly looped back to CharacterCreationAgent

**Root Cause Analysis**:
1. ❌ Instruction at line 525 of 2064-line file (buried)
2. ❌ Conditional language: "If flag is true, clear it"
3. ❌ No explicit INPUT/OUTPUT schemas
4. ❌ Prompt bloat: 1236 lines (included irrelevant mechanics)

**Fixes Applied**:
1. ✅ Moved instruction to line 22 (top 50)
2. ✅ Changed to unconditional: "FLAG MUST BE FALSE. ALWAYS."
3. ✅ Added explicit INPUT/OUTPUT schemas
4. ✅ Cut prompt to 607 lines (removed mechanics bloat)

**Result**: Test went from 0% → 100% pass rate.

## Summary

**The Three Laws of Prompt Engineering**:

1. **Be Unconditional**: "MUST BE X. ALWAYS." beats "if Y, do X"
2. **Be Explicit**: Document INPUT/OUTPUT schemas with exact field paths
3. **Be Concise**: Shorter prompts = higher compliance

**When in doubt**: Make it shorter, simpler, and more aggressive.

## References

- Evidence bundle: `/tmp/worktree_worker12/claude/character-creation-agent-i9xyR/character_creation_flag_clearing_fix/20260109T072437Z`
- Commit: `bc9dbc29b36204e914bd4b54a2731812c6ddabfc`
- Related: `.claude/skills/evidence-standards.md`
