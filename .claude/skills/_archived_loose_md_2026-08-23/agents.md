# Agent Routing & Modal Lock Patterns

**COMPACTNESS RULE**: Keep this file under 200 lines. Link to code instead of duplicating implementation details.

**Error Handling**: Warnings only - no assertions, retries, or default content. Log issues explicitly and let validation catch failures rather than silently backfilling missing data.

## Agent Routing Priority ($PROJECT_ROOT/agents.py)

Routing order in `get_agent_for_input()`:
1. **GodModeAgent** - Manual override (`GOD MODE:` prefix)
2. **Character Creation Completion Override** - Forced exit from modal
3. **MODAL LOCKS** - CharacterCreationAgent, LevelUpAgent (highest priority active state)
4. **CampaignUpgradeAgent** - State-based (ascension ceremonies)
5. **CharacterCreationAgent** - State-based (new character or level-up)
6. **Active Combat** - State-based (in_combat=True)
7. **Semantic Intent Classifier** - Primary routing brain (FastEmbed)
8. **Explicit Mode Override** - API parameter
9. **StoryModeAgent** - Default fallback

## Modal Lock Enforcement

### Critical Pattern: Stale Flag Guards

**Problem**: Leftover flags (e.g., `level_up_pending=True`) from previous modal sessions can incorrectly reactivate modals.

**Solution**: Check for explicit `False` flags that indicate intentional deactivation:

```python
# In agents.py get_agent_for_input():
level_up_in_progress = custom_state.get("level_up_in_progress")
if level_up_in_progress is False:  # Explicit False = stale guard
    level_up_modal_active = False

level_up_pending_flag = custom_state.get("level_up_pending")
if level_up_pending_flag is False and not bool(level_up_in_progress):
    level_up_modal_active = False
```

**Why**: `None` (unset) vs `False` (explicit guard) distinction prevents modal reactivation from stale data.

### Modal Scoping: Cross-Modal Flag Isolation

**Problem**: Character creation lock was protecting ALL custom_state flags, including level-up flags.

**Solution**: Scoped protection per modal type (world_logic.py `_should_protect_field()`):
- Character creation modal: Only protects character creation flags
- Level-up modal: Only protects level-up flags
- Prevents cross-modal interference (char creation forcing `level_up_in_progress=True`)

### Level-Up Activation Triggers

Modal activates when ANY of these are true:
1. `level_up_in_progress=True` (explicit in-progress flag)
2. `level_up_pending=True` (pending flag from rewards)
3. `rewards_pending.level_up_available=True` (rewards system signal)

**Prevented by stale guards**: If `level_up_in_progress=False` or `level_up_pending=False` explicitly set, modal won't activate.

## Finish Choice Injection (world_logic.py)

Modal exit enforcement via server-side choice injection:

```python
# In _inject_modal_finish_choice_if_needed():
# 1. Uses pre-update state (not post-update) to prevent race conditions
# 2. Checks modal is active (no stale guards blocking)
# 3. Adds canonical finish choice as LAST item in planning_block.choices
# 4. Uses structured_fields["planning_block"] not structured_response (preserves injection)
```

**Key fix**: Use `current_game_state_dict` (pre-update) instead of `updated_game_state_dict` to avoid race condition where LLM sets `level_up_in_progress=False` in same turn.

## Time Freezing During Modals

Level-up and character creation modals freeze game time:

```python
# In world_logic.py should_freeze_time():
is_char_creation = not custom_state.get("character_creation_completed", False)
is_level_up_mode = custom_state.get("level_up_in_progress", False) or \
                   custom_state.get("level_up_pending", False)
return is_char_creation or is_level_up_mode
```

## Common Issues & Fixes

| Issue | Root Cause | Fix Location | Fix |
|-------|-----------|--------------|-----|
| Modal bypass | `level_up_pending=True` didn't activate lock | agents.py:2871-2876 | Added pending flag to activation logic |
| Routing inconsistency | Injection used different detection logic than routing | agents.py + world_logic.py | Unified stale flag guards |
| Cross-modal interference | Char creation protected level-up flags | world_logic.py `_should_protect_field()` | Scoped protection per modal |
| Finish choice position | LLM response overwrote server injection | world_logic.py:5414 | Use structured_fields not structured_response |
| Stale reactivation | Old flags reactivated completed modals | agents.py:2864-2876 | Check explicit False flags |

## Testing Patterns

**Unit Tests** ($PROJECT_ROOT/tests/):
- `test_rev_439p_modal_bypass.py` - Activation with `level_up_pending=True`
- `test_rev_0g1y_inconsistent_detection.py` - Stale flag guard consistency
- `test_world_logic.py::TestModalLockFlagScoping` - Cross-modal isolation

**E2E Tests** (testing_mcp/creation/):
- `test_level_up_modal_flow_real.py` - Full modal lifecycle with real LLM
- `test_character_creation_agent_real_e2e.py` - Character creation flows

## Quick Reference

**Agent matching check order**:
1. State-based: `matches_game_state(game_state)`
2. Intent-based: Semantic classifier or `matches_input(user_input)`
3. Explicit: Mode parameter override

**Modal debugging**:
- Check `level_up_in_progress`, `level_up_pending`, `rewards_pending.level_up_available`
- Look for stale flags: explicit `False` values blocking activation
- Verify `character_creation_completed` not interfering with level-up

**See also**:
- `.claude/skills/character-creation-modal-exit.md` - Character creation specific patterns
- `$PROJECT_ROOT/agents.py` - Full implementation (lines 2739-3200)
- `$PROJECT_ROOT/world_logic.py` - Modal injection and protection (lines 1800-1900, 5400-5500)
