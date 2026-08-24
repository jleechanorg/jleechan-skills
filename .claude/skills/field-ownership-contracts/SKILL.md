---
name: field-ownership-contracts
description: Prevent the undefined field semantic failure mode where multiple writers assume different meanings for the same dict field.
---

# Field Ownership Contracts — Harness Skill

**Purpose**: Prevent the "undefined field semantic" failure mode where multiple writers (agents, LLM, backend) assume different meanings for the same dict field, causing cascading fix-on-fix churn.

## When This Skill Applies

**ALWAYS use this skill when:**
- Modifying any field in `rewards_pending`, `game_state`, `player_character_data`, or `custom_campaign_state`
- Adding a new field to a shared dict
- Changing what a field means or who writes it
- Debugging a test failure involving unexpected field values

## The Rule

**Every shared dict field must have exactly ONE authoritative writer.**

If you're about to write to a field, check who the current writer is. If it's not you, STOP — you're creating a multi-writer conflict.

## Contract Registry: rewards_pending

| Field | Authoritative Writer | Semantic | Readers |
|-------|---------------------|----------|---------|
| `level_up_available` | `_check_and_set_level_up_pending` | Bool: XP crossed level threshold | agents.py, world_logic.py UI functions |
| `new_level` | `_check_and_set_level_up_pending` | Int: target level after level-up | world_logic.py builder, agents.py |
| `xp_gained` | `ensure_level_up_rewards_pending` | Int: XP delta visible in the rewards box | rewards resolver/builder, tests |
| `gold` | `_check_and_set_level_up_pending` (merge) | Int: gold to award | builder |
| `items` | `_check_and_set_level_up_pending` (merge) | List: items to award | builder |
| `processed` | LLM via state_updates, `_check_and_set_level_up_pending` | Bool: has the reward been shown to user | agents.py routing |
| `source` | `_check_and_set_level_up_pending` | String: "level_up", "combat", etc. | builder |
| `source_id` | `_check_and_set_level_up_pending` | String: "level_up_1_to_2" etc. | dedup logic |

## Contract Registry: player_character_data.experience

| Field | Authoritative Writer | Semantic | Readers |
|-------|---------------------|----------|---------|
| `current` | LLM via state_updates | Int: cumulative XP (D&D 5e style) | `_extract_xp_robust`, `level_from_xp` |

**Note:** The LLM sets `experience.current` directly in its response. The backend NEVER modifies this field — it only reads it to detect level-up thresholds.

## Contract Registry: custom_campaign_state level-up flags

| Field | Authoritative Writer | Semantic |
|-------|---------------------|----------|
| `level_up_in_progress` | LLM via state_updates | Bool: level-up modal is active |
| `level_up_pending` | LLM via state_updates | Bool: level-up notification shown |
| `level_up_complete` | LLM via state_updates | Bool: level-up flow finished |
| `level_up_cancelled` | LLM via state_updates | Bool: user chose "continue adventuring" |

## Pre-Modification Checklist

Before writing ANY field in a shared dict:

1. **Check this contract** — is the field listed? Who is the authoritative writer?
2. **If you're not the authoritative writer** — STOP. You need to change the contract first.
3. **If the field is CONTESTED** — there's a bead for it. Fix the contest before adding more code.
4. **If adding a new field** — add it to this contract with authoritative writer, semantic, and readers.

## Code Smell: Multi-Writer Field

```python
# BAD — field written by multiple functions with different meanings
# In one writer:
rewards_pending["xp"] = preserved_xp  # means: "XP from prior pending reward"

# In another writer:
rewards_pending["xp"] = xp_delta      # means: "XP gained this turn"

# In builder:
xp_gained = rewards_pending.get("xp")  # reads: assumes one meaning, gets the other
```

```python
# GOOD — single writer, clear semantic
# In ensure_level_up_rewards_pending (the ONLY writer):
rewards_pending["xp_gained"] = max(0, current_xp - original_xp)  # delta at detection time

# In builder (reader only):
xp_gained = rewards_pending.get("xp_gained", 0)  # always means "the delta"
```

## Related Skills

- `/solid` — SRP: each field has one reason to change (one writer)
- `code-centralization/SKILL.md` — duplicate logic across writers is a centralization gap
- `code-smells.md` — "Shotgun Surgery" (one change touches many writers)

## Related Beads

- `rev-revj5l` — Separate LLM-owned vs backend-owned fields
- `bd-z4kfr` — Fix xp double-counting (legacy `rewards_pending.xp`)
- `bd-1xckb` — Extract rewards module from world_logic.py
