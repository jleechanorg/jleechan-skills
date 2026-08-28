# Modal Agent Pattern - Strict Character Creation & Level-Up

**Purpose:** Design specification for "modal" agents that cannot be exited until the user explicitly chooses to exit. This prevents accidental escapes from character creation and level-up flows.

## Problem Statement

### Current Behavior (Problematic)
1. **Character Creation can be bypassed**: Users can start a campaign and immediately begin the story without creating a character
2. **Classifier interference**: The intent classifier can route away from CharacterCreationAgent to other agents (dialog, combat, etc.) based on user input
3. **No explicit exit mechanism**: No forced "Exit Character Creation" choice that must be selected
4. **Level-up escapes**: Users can exit level-up flows without completing ability score improvements, feat selection, or spell choices

### Root Cause
- `get_agent_for_input()` routing logic allows semantic classification to override character creation/level-up state
- Priority 5 (semantic classifier) can route to Dialog, Combat, Rewards agents EVEN when Priority 4 (CharacterCreationAgent state check) should be active
- No enforcement of completion choices in the LLM prompt

## Solution: Modal Agent Pattern

### Core Principles

**1. MODAL AGENTS**
Agents that implement the modal pattern:
- **CharacterCreationAgent** (for new character creation AND level-ups)
- **LevelUpAgent** (new dedicated agent for level-up flows)

**2. MODAL CONSTRAINTS**
When a modal agent is active:
- User CANNOT leave until they explicitly select an "Exit" choice
- Semantic classifier is DISABLED (bypassed entirely)
- Only two agents can be accessed:
  - The modal agent itself (CharacterCreationAgent or LevelUpAgent)
  - GodModeAgent (always accessible via "GOD MODE:" prefix)

**3. EXIT MECHANISM**
Two ways to exit modal agents:
- **LLM-generated choice**: Modal agent MUST include "Exit Character Creation" / "Exit Level-Up" as a choice in `planning_block.choices`
- **Python-side injection**: If LLM forgets to include exit choice, Python backend injects it automatically

**4. ROUTING PRIORITY OVERRIDE**
When modal agent is active (based on game state):
- Priority 1: GodModeAgent (unchanged)
- **Priority 2: MODAL AGENT CHECK (NEW - BLOCKS ALL OTHER ROUTING)**
  - If `character_creation_in_progress == true`, ONLY route to CharacterCreationAgent or GodModeAgent
  - If `level_up_in_progress == true`, ONLY route to LevelUpAgent or GodModeAgent
- Priority 3+: All other routing (SKIPPED during modal flows)

## Implementation Design

### 1. State Flags

**Character Creation Modal State:**
```json
"custom_campaign_state": {
  "character_creation_in_progress": true,  // MODAL LOCK - prevents exit
  "character_creation_stage": "mechanics", // Current stage
  "character_creation_completed": false    // Final completion flag
}
```

**Level-Up Modal State:**
```json
"custom_campaign_state": {
  "level_up_in_progress": true,           // MODAL LOCK - prevents exit
  "level_up_stage": "asi_selection",      // Current stage
  "level_up_from_level": 3,               // Level before level-up
  "level_up_to_level": 4                  // Target level
}
```

### 2. Agent Routing Logic (`get_agent_for_input`)

**NEW Priority 2: Modal Agent Lock**

```python
def get_agent_for_input(
    user_input: str,
    game_state: GameState | None = None,
    mode: str | None = None,
    last_ai_response: str | None = None,
) -> tuple[BaseAgent, dict[str, Any]]:
    """
    Priority:
    1. GodModeAgent (Manual override)
    2. MODAL AGENT LOCK (NEW - CharacterCreation/LevelUp active)
    3. Character Creation Completion Override
    4. CampaignUpgradeAgent (State-based)
    5. Semantic Intent Classification
    6. API Explicit Mode
    7. StoryModeAgent (Default)
    """

    # 1. God Mode (always accessible)
    if GodModeAgent.matches_input(user_input, mode):
        return GodModeAgent(game_state), {...}

    # 2. MODAL AGENT LOCK (NEW)
    # This check MUST come before ALL other routing (except God Mode)
    if game_state is not None:
        custom_state = get_custom_state(game_state)

        # Check for modal agent lock flags
        if custom_state.get("character_creation_in_progress", False):
            logging_util.info("🔒 MODAL_LOCK: CharacterCreationAgent locked - ignoring classifier")
            return CharacterCreationAgent(game_state), {
                "intent": constants.MODE_CHARACTER_CREATION,
                "classifier_source": "modal_lock",
                "confidence": 1.0,
                "routing_priority": "2_modal_char_creation"
            }

        if custom_state.get("level_up_in_progress", False):
            logging_util.info("🔒 MODAL_LOCK: LevelUpAgent locked - ignoring classifier")
            return LevelUpAgent(game_state), {
                "intent": constants.MODE_LEVEL_UP,
                "classifier_source": "modal_lock",
                "confidence": 1.0,
                "routing_priority": "2_modal_level_up"
            }

    # 3. Character Creation Completion (check if user explicitly exited)
    # ... existing completion logic ...

    # 4-7. All other routing continues as normal
    # ... existing routing logic ...
```

### 3. LLM Prompt Instructions

**Updated `character_creation_instruction.md`:**

Add new section after "Core Principle":

```markdown
## CRITICAL: Modal Agent Constraints

**YOU ARE IN A MODAL DIALOG - USER CANNOT LEAVE WITHOUT EXPLICIT EXIT**

While character creation is in progress:
1. **CLASSIFIER IS DISABLED**: User input will NOT be routed to other agents
2. **ONLY TWO AGENTS ACCESSIBLE**:
   - CharacterCreationAgent (you)
   - GodModeAgent (via "GOD MODE:" prefix only)
3. **REQUIRED EXIT CHOICE**: You MUST provide an explicit exit choice in EVERY response:
   - "Exit Character Creation" (complete and return to story)
   - OR "Continue Creating Character" (stay in this mode)

**MANDATORY CHOICE FORMAT:**
```json
"planning_block": {
  "choices": {
    "option_1": {
      "text": "Finish Character Creation",
      "description": "Complete character and start the adventure"
    },
    "option_2": {
      "text": "Continue Editing",
      "description": "Make more changes to the character"
    }
  }
}
```

**If you forget to include the exit choice, the Python backend will inject it automatically.**

### Why This Matters
- Users cannot accidentally escape character creation by saying things like "let's start the adventure" before character is ready
- Semantic classifier cannot route dialog-like queries ("tell me about my character") to DialogAgent
- Combat-like queries ("what weapons do I have?") stay in character creation context
- Level-up flows cannot be interrupted mid-ASI selection
```

**New dedicated prompt: `level_up_instruction.md`:**

```markdown
# Level-Up Mode - Strict Modal Flow

**Purpose:** Process level-ups with full D&D 5e rule compliance. User CANNOT leave until level-up is complete.

## CRITICAL: Modal Agent Constraints

**YOU ARE IN A MODAL DIALOG - USER CANNOT LEAVE WITHOUT EXPLICIT EXIT**

[Same modal constraints as character creation]

## Level-Up Flow

### Step 1: Announce Level-Up
Present level increase, XP totals, and what will be gained.

### Step 2: Hit Points
- Roll hit die OR take average
- Add Constitution modifier
- Update hp_max

### Step 3: Class Features
Present new features gained at this level.

### Step 4: Ability Score Improvement (ASI) or Feat
**MODAL CHECKPOINT**: User MUST make a choice:
- Increase ability scores (+2 to one, or +1 to two)
- Select a feat

**REQUIRED CHOICES:**
```json
"planning_block": {
  "choices": {
    "option_1": {"text": "Increase Ability Scores", "description": "..."},
    "option_2": {"text": "Choose a Feat", "description": "..."},
    "option_3": {"text": "Exit Level-Up", "description": "Complete level-up and return to story"}
  }
}
```

### Step 5: Spellcasting (if applicable)
Process new spell slots, spells known, cantrips.

### Step 6: Completion
Once all choices made, present summary and REQUIRE exit choice:
```json
"planning_block": {
  "choices": {
    "option_1": {"text": "Complete Level-Up", "description": "Finish and return to adventure"},
    "option_2": {"text": "Review Changes", "description": "Double-check selections"}
  }
}
```
```

### 4. Python-Side Exit Choice Injection

**New utility: `$PROJECT_ROOT/modal_agent_utils.py`**

```python
"""
Modal Agent Utilities - Exit Choice Injection

This module ensures modal agents (CharacterCreation, LevelUp) always
provide explicit exit choices, even if the LLM forgets to include them.
"""

from mvp_site import logging_util

EXIT_CHOICE_CHAR_CREATION = {
    "text": "Exit Character Creation",
    "description": "Complete character creation and start the adventure"
}

EXIT_CHOICE_LEVEL_UP = {
    "text": "Exit Level-Up",
    "description": "Complete level-up and return to the story"
}

def inject_exit_choice_if_missing(
    response_dict: dict,
    agent_type: str  # "character_creation" or "level_up"
) -> dict:
    """
    Inject exit choice into LLM response if missing.

    Args:
        response_dict: LLM response dictionary with planning_block
        agent_type: Type of modal agent ("character_creation" or "level_up")

    Returns:
        Modified response_dict with exit choice guaranteed
    """
    # Get planning_block
    planning_block = response_dict.get("planning_block", {})
    choices = planning_block.get("choices", {})

    # Determine which exit choice to use
    exit_choice = (
        EXIT_CHOICE_CHAR_CREATION
        if agent_type == "character_creation"
        else EXIT_CHOICE_LEVEL_UP
    )

    # Check if any choice matches exit intent
    has_exit_choice = False
    exit_keywords = ["exit", "finish", "complete", "done", "return"]

    for choice_key, choice_data in choices.items():
        if isinstance(choice_data, dict):
            text = choice_data.get("text", "").lower()
            if any(keyword in text for keyword in exit_keywords):
                has_exit_choice = True
                break

    # Inject exit choice if missing
    if not has_exit_choice:
        logging_util.warning(
            f"🔒 MODAL_AGENT_INJECTION: LLM forgot exit choice for {agent_type}, "
            f"injecting automatically"
        )

        # Find next available option number
        existing_keys = [k for k in choices.keys() if k.startswith("option_")]
        if existing_keys:
            max_num = max(int(k.split("_")[1]) for k in existing_keys)
            new_key = f"option_{max_num + 1}"
        else:
            new_key = "option_1"

        # Inject exit choice
        choices[new_key] = exit_choice
        planning_block["choices"] = choices
        response_dict["planning_block"] = planning_block

    return response_dict
```

**Integration point in `world_logic.py` or response handler:**

```python
# After LLM response parsing, before returning to user
if current_agent_type == "character_creation":
    response_dict = inject_exit_choice_if_missing(
        response_dict,
        "character_creation"
    )
elif current_agent_type == "level_up":
    response_dict = inject_exit_choice_if_missing(
        response_dict,
        "level_up"
    )
```

### 5. Frontend Changes (Optional Enhancement)

**UI-level enforcement:**
- When `character_creation_in_progress == true`, disable "Send" button unless:
  - Input matches exit choice text, OR
  - Input is "GOD MODE:" prefix
- Show modal dialog backdrop to indicate locked state
- Display "You are in Character Creation Mode" banner

## Edge Cases & Handling

### Case 1: User tries to escape with dialog-like input
**Input:** "I want to talk to the bartender"
**Current behavior:** Classifier routes to DialogAgent
**New behavior:** Modal lock returns CharacterCreationAgent, responds with:
```
[CHARACTER CREATION MODE - Active]

You're currently creating your character. Before you can interact with the world,
we need to finish building your character.

Would you like to:
1. Continue Character Creation
2. Exit Character Creation (if character is ready)
```

### Case 2: User tries combat-like action
**Input:** "I attack the goblin"
**Current behavior:** Classifier routes to CombatAgent
**New behavior:** Modal lock returns CharacterCreationAgent, responds with:
```
[CHARACTER CREATION MODE - Active]

You're eager to jump into action! But first, let's finish creating your character
so you have the stats and abilities you'll need in combat.

Current Progress: [stage summary]

Ready to exit character creation?
1. Finish Character Creation (if ready)
2. Continue Building Character
```

### Case 3: LLM forgets exit choice
**LLM response:** Only provides character customization choices, no exit option
**Python injection:** Automatically adds "Exit Character Creation" as final choice
**User sees:** All LLM choices + injected exit choice

### Case 4: Level-up with multiple stages
**Scenario:** Level 4 → Level 5 requires ASI + new spell selection
**Behavior:**
- Turn 1: ASI selection (choices: +2 to one, +1 to two, choose feat, exit)
- Turn 2: Spell selection (choices: spell A, spell B, spell C, exit)
- Turn 3: Review summary (choices: confirm, review again, exit)
- Modal lock persists until user selects exit choice

### Case 5: God Mode Override
**Input:** "GOD MODE: skip character creation and start at level 5"
**Behavior:** GodModeAgent takes over (Priority 1), can bypass modal lock
**Justification:** God Mode is admin/debugging tool and should have full override

## Benefits

1. **Prevents accidental bypasses**: Campaign ARrfJ39LhNEi5rcGq1c7 issue would be impossible
2. **Clear UX**: Users know they're in a modal flow and how to exit
3. **Classifier isolation**: Semantic classifier doesn't interfere with creation flows
4. **LLM safety net**: Python injection ensures exit choice always exists
5. **Consistent pattern**: Same approach for character creation AND level-ups

## Implementation Phases

### Phase 1: Core Modal Lock (Minimum Viable)
- [ ] Add `character_creation_in_progress` check at Priority 2 in `get_agent_for_input`
- [ ] Update `character_creation_instruction.md` with modal constraints
- [ ] Test that classifier is bypassed during character creation

### Phase 2: Exit Choice Injection
- [ ] Create `modal_agent_utils.py` with `inject_exit_choice_if_missing`
- [ ] Integrate injection into response handler
- [ ] Test LLM responses with/without exit choices

### Phase 3: Level-Up Agent
- [ ] Create dedicated `LevelUpAgent` class
- [ ] Add `level_up_instruction.md` prompt
- [ ] Implement `level_up_in_progress` modal lock
- [ ] Update routing logic for level-up flows

### Phase 4: Enhanced UX (Optional)
- [ ] Frontend modal dialog backdrop
- [ ] "Character Creation Mode" banner
- [ ] Disable irrelevant UI actions during modal flow

## Testing Strategy

### Unit Tests
- `test_modal_agent_routing.py`: Verify Priority 2 modal lock
- `test_exit_choice_injection.py`: Verify Python injection logic
- `test_character_creation_modal.py`: End-to-end character creation with modal lock

### Integration Tests
- Create campaign → Verify cannot escape char creation with dialog input
- Level-up flow → Verify cannot escape mid-ASI selection
- God Mode override → Verify can bypass modal lock

### Edge Case Tests
- LLM forgets exit choice → Verify injection works
- Multiple level-up stages → Verify modal lock persists
- Campaign with pre-populated character → Verify review mode works

## Related Files

**Agent routing:**
- `/Users/$USER/projects/worktree_worker8/$PROJECT_ROOT/agents.py` (lines 2552-3164)

**Character creation:**
- `/Users/$USER/projects/worktree_worker8/$PROJECT_ROOT/agents.py` (lines 830-1151, CharacterCreationAgent)
- `/Users/$USER/projects/worktree_worker8/$PROJECT_ROOT/prompts/character_creation_instruction.md`

**Intent classifier:**
- `/Users/$USER/projects/worktree_worker8/$PROJECT_ROOT/intent_classifier.py`

**State management:**
- `/Users/$USER/projects/worktree_worker8/$PROJECT_ROOT/game_state.py`

## References

- CLAUDE.md: LLM decides, server executes (lines 10-30)
- Intent classifier architecture (intent_classifier.py lines 1-176)
- Agent routing priority (agents.py lines 2552-2585)
