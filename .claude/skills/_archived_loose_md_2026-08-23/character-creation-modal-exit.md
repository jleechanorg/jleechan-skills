# Character Creation Modal Exit Protocol

## Overview
This skill documents the mandatory exit protocol for CharacterCreationAgent modal mode to prevent premature story mode transitions.

## Critical Principle

**CHARACTER CREATION IS A MODAL DIALOG** - The user CANNOT exit until they select a specific planning_block choice.

## Modal Lock Mechanism

### Entry Conditions
CharacterCreationAgent modal lock activates when:
```python
custom_campaign_state.character_creation_in_progress == True
AND
custom_campaign_state.character_creation_completed == False
```

### Lock Behavior
While locked:
- **Classifier is BYPASSED** - all user input routes to CharacterCreationAgent
- **Other agents BLOCKED** - StoryModeAgent, DialogAgent, CombatAgent cannot activate
- **User input interpretation DISABLED** - "Let's fight!" still goes to character creation
- **Planning block choices MANDATORY** - every response must include choices

### Exit Conditions (ONLY)

Character creation modal can ONLY exit via these specific planning_block choice selections:

**1. God Mode Review Stage:**
```json
{
  "planning_block": {
    "choices": {
      "start_adventure": {
        "text": "Start Adventure",
        "description": "Confirm this character and begin the story"
      }
    }
  }
}
```

**2. Manual Creation Complete:**
```json
{
  "planning_block": {
    "choices": {
      "play_character": {
        "text": "PlayCharacter",
        "description": "Finish character creation and start adventure"
      }
    }
  }
}
```

**3. Character Creation Cancellation:**
```json
{
  "planning_block": {
    "choices": {
      "cancel_creation": {
        "text": "Cancel Character Creation",
        "description": "Exit without saving character"
      }
    }
  }
}
```

### State Transition on Exit

When user selects an exit choice:
```python
custom_campaign_state.character_creation_in_progress = False
custom_campaign_state.character_creation_completed = True
custom_campaign_state.character_creation_stage = "complete"
```

## God Mode Review Stage Bug (FIXED)

### The Bug
**Symptom**: God mode template campaigns skipped character review and went straight to story mode.

**Root Cause**: LLM was ignoring `character_creation_stage: "review"` and resetting to "concept" when user said "Let's create my character!"

**Example Failure**:
```
Initial state: character_creation_stage = "review"
User: "Let's create my character!"
LLM (WRONG): "Let me reset to concept stage..."
Result: Offered AIGenerated/StandardDND/CustomClass menu instead of review
```

### The Fix
Enhanced `character_creation_instruction.md` with explicit protocol:

**Key Changes**:
1. **Mandatory stage check** - ALWAYS check `character_creation_stage` first
2. **Forbidden actions** - Explicitly list what NOT to do in review stage
3. **Required choices** - Must provide exactly "Start Adventure" and "Edit Character"
4. **Clear semantics** - "review" means character is ALREADY CREATED, just needs approval

**Prompt Enhancement**:
```markdown
**🚨 DO NOT RESET TO "concept" OR "mechanics" STAGES 🚨**
- Even if user says "Let's create my character!" or "I want to create my character"
- The character IS ALREADY CREATED - they just need to REVIEW and CONFIRM it

**MANDATORY BEHAVIOR IN REVIEW STAGE**:
1. ALWAYS check `character_creation_stage` FIRST before deciding what to do
2. IF stage == "review":
   - Present the PRE-POPULATED character for review
   - Use narrative tag: `[CHARACTER CREATION - Review]` (NOT "Concept")
   - Show character stats from `player_character_data`
3. REQUIRED CHOICES (exactly these two):
   - start_adventure: "Start Adventure"
   - edit_character: "Edit Character"
```

### Verification
Created test: `testing_mcp/creation/test_god_mode_skip_bug.py`

**Before fix**: 0/1 passed (LLM reset to concept stage)
**After fix**: 1/1 passed (LLM stays in review stage with correct choices)

**Evidence**: `/tmp/your-project.com/worktree_creation/god_mode_character_skip_bug/iteration_002/`

## Testing Protocol

### Test Creation Review Flow
```bash
cd ~/projects/worktree_creation
python testing_mcp/creation/test_god_mode_skip_bug.py
```

**Expected Result**:
```
✅ Has [CHARACTER CREATION] tag: True
✅ character_creation_stage: review (NOT concept!)
✅ Planning block choices: ['start_adventure', 'edit_character']
✅ Has finish character choice: True
```

### Test Manual Creation Flow
```bash
python testing_mcp/creation/test_character_creation_three_flows_real.py
```

**Expected Result**:
- AIGenerated flow: character created → review → PlayCharacter choice → story
- StandardDND flow: race → class → abilities → background → PlayCharacter → story
- CustomClass flow: custom class design → PlayCharacter → story

## Firestore Investigation Protocol

### Check if Campaign is in Character Creation
```python
custom_state = game_state.get("custom_campaign_state", {})
in_progress = custom_state.get("character_creation_in_progress")
completed = custom_state.get("character_creation_completed")
stage = custom_state.get("character_creation_stage")

if in_progress and not completed:
    print(f"🔒 Modal locked in stage: {stage}")
elif completed:
    print(f"✅ Character creation complete")
else:
    print(f"❓ Ambiguous state - check for bugs")
```

### Check Story Entries for Planning Block
```python
# Get first LLM response
story_ref = campaign_ref.collection('story')
entries = story_ref.order_by('timestamp').stream()

for entry in entries:
    data = entry.to_dict()
    if data.get('actor') == 'gemini':
        debug_info = data.get('debug_info', {})
        raw_response = debug_info.get('raw_response_text', '')
        if raw_response:
            parsed = json.loads(raw_response)
            planning_block = parsed.get('planning_block', {})
            choices = planning_block.get('choices', {})

            # Check for exit choices
            has_start_adventure = 'start_adventure' in choices
            has_play_character = 'play_character' in choices

            if has_start_adventure or has_play_character:
                print("✅ Exit choice available")
            else:
                print("⚠️ No exit choice - user is stuck!")
        break
```

## Common Mistakes to Avoid

### Mistake 1: Assuming User Input Means Exit
```python
# WRONG
if "let's start" in user_input.lower():
    character_creation_completed = True  # NO!
```

User saying "Let's start" is ambiguous - they might mean:
- "Let's start creating my character" (enter creation)
- "Let's start reviewing" (god mode)
- "Let's start the adventure" (exit creation)

**CORRECT**: Only exit when user SELECTS the planning_block exit choice.

### Mistake 2: Skipping Review for God Mode
```python
# WRONG
if god_mode_template and character_data:
    character_creation_completed = True  # NO!
    # User never saw the character!
```

**CORRECT**: Always show review step, even for god mode templates.

### Mistake 3: No Planning Block Choices
```python
# WRONG - No way for user to exit!
{
  "narrative": "[CHARACTER CREATION] Your character is ready!",
  "planning_block": {
    "thinking": "Character is complete",
    "choices": {}  # EMPTY!
  }
}
```

**CORRECT**: ALWAYS provide at least one exit choice when character is ready.

## Related Files

- `$PROJECT_ROOT/prompts/character_creation_instruction.md` - Character creation prompt (lines 97-141)
- `$PROJECT_ROOT/agents.py` - Modal lock logic (lines 2793-2805)
- `testing_mcp/creation/test_god_mode_skip_bug.py` - Bug reproduction test
- `testing_mcp/creation/test_character_creation_three_flows_real.py` - Comprehensive flow test

## CLAUDE.md Integration

Added to project CLAUDE.md:

```markdown
## Character Creation Modal Exit

Character creation is a MODAL DIALOG - user cannot exit until selecting specific planning_block choice:
- God Mode Review: "Start Adventure" choice
- Manual Creation: "PlayCharacter" choice
- Cancellation: "Cancel Character Creation" choice

See `.claude/skills/character-creation-modal-exit.md` for complete protocol.
```

## Evidence Locations

**Bug Reproduction Evidence**:
- Before fix: `/tmp/your-project.com/worktree_creation/god_mode_character_skip_bug/iteration_001/`
  - Pass rate: 0/1 (LLM reset to concept stage)
- After fix: `/tmp/your-project.com/worktree_creation/god_mode_character_skip_bug/iteration_002/`
  - Pass rate: 1/1 (LLM stays in review stage)

**Production Campaign with Bug**:
- URL: `https://mvp-site-app-s7-i6xf2p72ka-uc.a.run.app/game/Wf1OZ1E6UYxP1kRFRpps`
- Campaign ID: `Wf1OZ1E6UYxP1kRFRpps`
- Owner: $USER@gmail.com (UID: vnLp2G3m21PJL6kxcuAqmWSOtm73)
- Issue: Character creation completed immediately without review
- Root cause: Pre-PR #5225 code without explicit review stage protocol
