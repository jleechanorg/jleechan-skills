---
name: level-up-validation
description: Validate that level-up flows are complete, auto-selected, editable, and evidenced with real LevelUpAgent output.
scope: your-project.com level-up evidence
---

# Level-Up Validation

Use this skill when judging whether a level-up flow works correctly for any
D&D 5e class, subclass, multiclass, or campaign-defined custom class.

This is an evaluation protocol. Do not repair code from this skill unless the
user explicitly asks for implementation.

## Required Inputs

- Campaign URL or campaign id.
- Current PR head SHA.
- Raw model request/response or `testing_mcp/core/test_level_up_organic.py`
  evidence bundle.
- Exported `game_state.json`, story transcript, server logs, and checksums.
- The active LevelUpAgent prompt stack, including
  `$PROJECT_ROOT/prompts/level_up_instruction.md` and the LevelUpAgent final modal
  override in `$PROJECT_ROOT/agents.py`.

## Pass/Fail Standard

Fail closed. A level-up flow passes only when all of these are proven by real
artifacts, not agent claims.

### 1. Availability Entry

- Normal story output shows level-up availability when the model-owned signal
  says `target_level > current_level`.
- Before the modal starts, the player can choose `level_up_now`.
- `level_up_now` opens the modal AND commits the new level atomically: the model
  MUST emit `state_updates.player_character_data.level = target_level` on this
  turn; the server calls `apply_level_up` which writes `pcd.level = to_level`
  together with `level_up_session.status = in_progress`. It does not advance
  time, roll HP, award rewards, or resolve story actions.

### 2. Complete Recommended Package

The first modal response after `level_up_now` must visibly include
`Recommended package:` and must be finalizable immediately.

The package must audit the character's class/subclass/custom class, current
level, target level, campaign mechanics, and prior character sheet. It must
account for every automatic gain and every player-selectable decision, including
when applicable:

- HP method and HP gain.
- Class, subclass, multiclass, or custom-class features.
- Resource pools, uses, recharge cadence, action economy, and derived stats.
- Proficiencies, skills, expertise, languages, tools, and saves.
- ASI, feat, fighting style, maneuvers, invocations, metamagic, infusions,
  wild shape, rage improvements, companions, summons, or other class options.
- Spell slots, spells known, spells prepared, cantrips, rituals, spellcasting
  ability, save DC, and spell attack bonus.
- Subclass, lineage, domain, oath, patron, bloodline, circle, custom origin, or
  feature-granted spells.

For prepared casters, always-prepared or feature-granted spells are additive.
They do not satisfy the ordinary prepared-spell decision unless the class rules
explicitly say so.

For custom classes, the model must use the custom class description and
campaign rules. If a required custom-class rule is genuinely absent, the modal
must stay active and ask for that missing mechanical input instead of silently
skipping it.

### 3. Auto-Selection

Every required decision category must have a pre-selected recommendation before
the player finishes. The visible text must distinguish:

- Automatic gains.
- Recommended defaults the player can accept.
- Player-selectable categories the player can change.

`finish_level_up_return_to_game` must be present as the final accept option
once the recommended package is complete.

### 4. Click Editing

Every player-selectable recommendation must be editable through planning-block
choices.

Acceptable patterns:

- The first modal response exposes a concrete `level_up_*` choice for the
  category.
- A category-level `level_up_*` change choice opens a follow-up modal with
  concrete legal options for that category.

Unacceptable patterns:

- Only `finish_level_up_return_to_game` appears while unresolved decisions
  remain.
- A selectable category is described in prose but has no planning-block edit
  path.
- The modal closes or resumes story before the changed selection is confirmed.
- Choices are ordinary story/combat/dialog choices instead of level-up choices
  before finish.

### 5. Free-Form Editing

Free-form text must work for every selectable category while the level-up modal
is active.

Validate at least one free-form edit in evidence, such as:

- "Change my prepared spells to ..."
- "Use fixed HP instead."
- "Pick a different subclass option."
- "Change the skill/proficiency choice."

The response must remain in LevelUpAgent, preserve modal state, reflect the
updated pending selection, and keep `finish_level_up_return_to_game` available
when all required decisions are complete.

### 6. Finish Commit

On `finish_level_up_return_to_game`:

- Commit the target level exactly once.
- Clear modal scratch state such as pending selections.
- Preserve selected/recommended mechanics in `player_character_data`.
- Resume the interrupted story with real gameplay choices.
- Do not return only generic placeholders such as "Continue Story" or
  "Custom Action" when concrete scene choices are available.

### 7. Persisted Reload / Orphan Session Boundary

For regressions involving stuck `LevelUpAgent` routing, stale modal flags, GOD
MODE promotions, or alternate level commits, evidence must include a reload case
from persisted Firestore state:

- Capture direct Firestore pre-state before any app get-state/export/UI call.
- Include `player_character_data.level`, `level_up_session.status`,
  `level_up_session.current_level`, `level_up_session.target_level`,
  `level_up_session.review_open`, `custom_campaign_state.level_up_in_progress`,
  and `custom_campaign_state.level_up_pending`.
- If `player_character_data.level >= level_up_session.target_level` and
  `level_up_session.status == "available"`, the first gameplay streaming turn
  must seal the session before routing.
- Post-state must show `level_up_session.status` is terminal (`complete`) or
  `is_session_active(...) is false`, and the response must route to normal
  gameplay rather than LevelUpAgent.
- Passing modal/reducer tests alone do not satisfy this boundary; the proof must
  cover persisted reload -> cleanup -> routing.

## Evidence Procedure

1. Run the canonical real test when real LLM proof is requested:

   ```bash
   cd testing_mcp && ../vpython core/test_level_up_organic.py --server http://127.0.0.1:8001
   ```

2. Do not use pytest collection for `testing_mcp/` script suites.
3. Do not set mock-mode toggles for evidence-bearing `testing_mcp/` runs.
4. Record the evidence bundle path, PR head SHA, server URL, model/provider,
   and pass/fail result.
5. Inspect raw artifacts, not just summary prose:
   - `metadata.json`
   - `run.json`
   - story transcript
   - `game_state.json`
   - server logs
   - screenshots or video if UI/browser behavior is claimed
6. Compare the evidence bundle SHA to the live PR head. If stale, declare
   exactly which later diffs are behavior-neutral before accepting it.
7. For stuck-agent or orphan-session claims, verify the persisted reload boundary
   in section 7 with direct Firestore pre/post snapshots and selected-agent/routing
   evidence.

## Verdict Template

Use this structure:

```text
Verdict: PASS | FAIL | PARTIAL
Evidence bundle:
PR head:
Model/provider:

Availability:
Recommended package completeness:
Auto-selection:
Click editing:
Free-form editing:
Finish commit:
Persisted reload/orphan boundary:

Blocking gaps:
```
