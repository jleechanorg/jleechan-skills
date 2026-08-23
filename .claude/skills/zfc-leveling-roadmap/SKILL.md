---
name: zfc-leveling-roadmap
description: ZFC Level-Up architecture alignment — file boundaries, API contracts, pre-flight checks, and milestone status. Read this BEFORE any level-up/rewards/XP code change.
scope: your-project.com/mvp_site
---

# ZFC Leveling Roadmap Alignment

## Design Principle

This skill is the level-up/rewards specialization of the general ZFC contract.
Before applying these file boundaries, read
`.claude/skills/zero-framework-cognition/SKILL.md` for the repository-wide
rules: models make semantic decisions, new regex/keyword/heuristic semantic
routing is banned, and model contracts should request minimal semantic fields
instead of redundant aliases.
Before accepting a backend correction guard, also apply
`.claude/skills/root-cause-first/SKILL.md`: prove the selected model path
received the right prompt/schema, fix missing or ambiguous prompt/schema
instructions first, and treat backend correction as a last resort.

> **"Model Computes, Backend Formats"** — the LLM decides level-up; `rewards_engine.py` formats it; `world_logic.py` wraps the formatted result with modal semantics.

> **"LLM Calculates, Backend Corrects"** — the LLM owns XP arithmetic, target-level math, level-up availability, and choice/benefit selection. Backend code must not independently calculate those facts from thresholds as a primary path. It may only correct or suppress mechanically contradictory explicit model/state payloads.

> **Correction Exception Boundary**: Correction guards that prevent degraded UX (stale-flag time-freeze, SSE soft-lock, already-applied level-up residue) are permitted **only** within `rewards_engine.py`. These guards must be correction-only: compare explicit model/state fields for contradictions, suppress or normalize invalid payloads, and avoid creating a competing backend level-up decision. Scattered heuristics across multiple files are strictly forbidden.

> **Opaque Choice Boundary**: Planning choice IDs are opaque handles, not semantic signals. `level_up_now`, `finish_level_up_return_to_game`, and `custom_action` are migration/compatibility handles only. Level-up choice meaning must come from explicit model/schema fields on the resolved choice object, not from ID text, prefixes, labels, or backend allowlists.

---

## File Responsibility Table (Mandatory)

Before modifying ANY file for level-up/rewards/XP work, verify against this table.
**If your change puts logic in a "MUST NOT DO" column → STOP and redesign.**

| File | OWNS | MUST NOT DO |
|------|------|-------------|
| `rewards_engine.py` | Format explicit model signals, correction-only contradiction guards, `canonicalize_level_up_signal()`, XP/reward field normalization from explicit values, `sync_level_up_signals()`, SSE atomicity enforcement (`_enforce_atomicity()`) | Model calls, Firestore writes, text interpretation, primary XP/level calculation, threshold-derived level-up decisions |
| `world_logic.py` | Modal locks, finish choice injection, wrap **precomputed** payloads only, thin delegation to `rewards_engine.project_level_up_ui()` | Recompute XP, synthesize choices, call `canonicalize_level_up_signal()` directly, build `level_up_signal` dicts, call `resolve_level_progression()` |
| `game_state.py` | State storage, deterministic mechanical primitives (`xp_needed_for_level`, `level_from_xp`, `coerce_int`) | Decide level-up from state, replace model choices, own level-up decisions, contain level-up dataclasses or resolvers |
| `agents.py` | Route to correct agent using `rewards_engine.is_level_up_active()` | Inline flag interpretation, XP extraction, stale-flag recovery logic |
| `llm_parser.py` | Parse model output, call the pipeline **once** via `canonicalize_rewards()`, persist/deliver | Duplicate rewards formatting, inline false-positive mutations, call canonicalization separately |
| `narrative_response_schema.py` | Preserve model output losslessly, contradiction detection on model output boundary (e.g., `level_up=true` but `current_turn_exp < total_exp_for_next_level`) | Class feature synthesis, state mutation, building UI payloads |
| `llm_service.py` | LLM request/response pipeline, retry on `SchemaRejectionError` | Rewards formatting, level-up flag interpretation, modal state mutation |
| `structured_fields_utils.py` | Extract non-empty structured fields | Semantic validation, alias normalization, UI formatting |
| `prompts/level_up_instruction.md` | Class-AGNOSTIC contracts only — generic enumeration ("enumerate ALL subclass options as separate clickable choices"), generic announce-all-gains rules. The model owns the D&D 5e SRD. | Hardcode subclass names (oaths/circles/patrons/archetypes/domains), feature names (Divine Health, Channel Divinity, Second Wind…), spell names, or per-class numeric gains as named rules/HARD INVARIANTs. Class names allowed ONLY inside `e.g.`/`for example` illustrations. |

---

## Authorized Public API Surface

These are the **only** `rewards_engine` functions that external files may call:

| Function | Callers | Purpose |
|----------|---------|---------|
| `canonicalize_rewards(structured_fields, game_state, original_state)` | `llm_parser.py` (1 call), `world_logic.py` (polling paths) | Single convergence point for all rewards/level-up UI |
| `is_level_up_active(game_state)` | `agents.py`, `world_logic.py` | Correction-guarded modal activity check over explicit state/model fields |
| `project_level_up_ui(game_state, original_state)` | `world_logic.py` (via `_project_level_up_ui_locally()`) | Polling/projection path (transitional — delete when callers migrate) |
| `sync_level_up_signals(game_state, original_state)` | `world_logic.py` (via `ensure_level_up_rewards_pending()` shim) | Idempotent rewards_pending sync |
| `format_model_level_up_signal(signal)` | `llm_parser.py` (fallback path) | Explicit signal formatter (should become private `_format_...`) |

**All other functions are private implementation details.** Do not call `_canonicalize_core()`, `_enforce_atomicity()`, `_apply_contradiction_guard()`, `resolve_level_up_signal()`, or `ensure_rewards_box()` from outside `rewards_engine.py`.

---

## API Contract Freeze

- `canonicalize_rewards()` returns `(rewards_box, planning_block)` — a **2-tuple**. **Do NOT change this return signature.** Use `out_meta` dict parameter to pass additional data out (e.g., canonical signal, false-positive flags).
- `canonicalize_level_up_signal()` is called **inside** `rewards_engine.py` only. External files consume precomputed results.
- `is_level_up_active()` returns `bool`. It performs correction-only stale-flag/contradiction suppression internally. It must not become a primary XP-threshold calculator. Callers must not second-guess its result.
- `ensure_rewards_box()` returns `tuple[dict | None, dict | None]` (rewards_box, signal_metadata). Internal only.

---

## Common Boundary Violations

These are the most frequently observed agent drift patterns. If you catch yourself doing any of these, STOP:

| If you're about to... | WRONG file | RIGHT approach |
|----------------------|------------|----------------|
| Call `canonicalize_level_up_signal()` | `world_logic.py`, `llm_parser.py` | Only inside `rewards_engine.py` (via `_canonicalize_core`) |
| Build a `level_up_signal` dict | `world_logic.py` | Build in `rewards_engine.py`, pass via return or `out_meta` |
| Compute XP progress, thresholds, target level, or level-up availability as the primary path | any backend file | Ask the LLM for explicit calculated fields; `rewards_engine.py` may only correct/suppress contradictions in those explicit fields |
| Check `level_up_pending` / `level_up_in_progress` flags directly | `world_logic.py`, `agents.py` | Call `rewards_engine.is_level_up_active()` |
| Call `resolve_level_progression()` | anywhere | **Deleted.** Use `rewards_engine.is_level_up_active()` or `rewards_engine.project_level_up_ui()` |
| Use `build_level_up_rewards_box()` | anywhere | **Deleted.** Use `rewards_engine.ensure_rewards_box()` (internal) or `project_level_up_ui()` |
| Change `canonicalize_rewards()` return type | anywhere | **Don't.** Use `out_meta` dict instead |
| Add signal normalization aliases | `structured_fields_utils.py` | Add in `rewards_engine.canonicalize_level_up_signal()` |
| Classify or scrub choices by ID text/prefix, label, enum name, or CSS class | any backend file | Resolve the submitted handle against persisted `planning_block.choices`, then read explicit structured fields; keep `level_up_now`, `finish_level_up_return_to_game`, and `custom_action` exact checks migration-only |
| Add a new feature to a level-up PR | the same PR | Open a separate PR — scope creep is the #1 cause of spin |
| Access `rewards_engine._is_state_flag_true()` from outside | `agents.py`, `world_logic.py` | Use the public helpers or import from `game_state.py` |

---

## Pre-Flight Checklist

Run this **before writing any code** for a PR that touches level-up, rewards, XP, or canonicalization logic.

### 1. File boundary check
For each file you plan to modify, check the table above:
- [ ] Is the change in the "OWNS" column? → Proceed
- [ ] Is it in the "MUST NOT DO" column? → **STOP. Redesign.**

### 2. API contract check
- [ ] Am I changing the return signature of `canonicalize_rewards()`? → **Don't.** Use `out_meta`.
- [ ] Am I calling `rewards_engine.*` from `world_logic.py` outside the authorized API surface table? → Check boundary table.
- [ ] Am I directly reading `level_up_pending` / `level_up_in_progress` flags instead of calling `is_level_up_active()`? → Use the centralized function.
- [ ] Am I adding or expanding a choice-ID allowlist, prefix check, or text/label check for level-up behavior? → **STOP.** First prove the selected choice is resolved from persisted structured state and that the model/schema exposes the needed semantic field. Exact legacy handles (`level_up_now`, `finish_level_up_return_to_game`, `custom_action`) require a migration note and must not become the pattern for new behavior.

### 3. Deleted function check
- [ ] Am I calling any of these **deleted** functions? → **They no longer exist:**
  - `game_state.resolve_level_progression_state()`
  - `game_state.resolve_level_progression()`
  - `game_state.ensure_level_up_rewards_pending()`
  - `game_state.LevelProgressionState`
  - `game_state.PendingRewardsState`
  - `world_logic.build_level_up_rewards_box()`
  - `agents._is_stale_level_up_pending()`

### 4. Scope check
- [ ] Does a task spec exist in `~/roadmap/zfc-pr-task-specs-2026-04-22.md`?
- [ ] If yes, is every file I'm touching in the "Likely files" list?
- [ ] Am I adding unrelated features to this PR? → Open a separate PR.

### 5. PR hygiene check
- [ ] Does an open PR already cover this scope? → Fix that PR instead of creating a new one.
- [ ] Is this PR over 15 commits? → Consider splitting it.

---

## Decision Flowchart

```
Is my change about level-up/XP/rewards logic?
├── YES → Put the logic in rewards_engine.py
│   ├── Does world_logic.py need the result?
│   │   └── Pass via return value or out_meta dict
│   ├── Does agents.py need to know if level-up is active?
│   │   └── Call rewards_engine.is_level_up_active() — never inline flag checks
│   └── Does llm_parser.py need the result?
│       └── Call canonicalize_rewards() once; don't call internal functions directly
├── Is my change about validating LLM output?
│   └── Contradiction detection → narrative_response_schema.py
│       └── Schema retry → llm_service.py SchemaRejectionError
└── NO → Normal file protocol applies
```

---

## Milestone Status

| Milestone | Status | Description |
|-----------|--------|-------------|
| M0 | ✅ Complete | Delete legacy paths, net LOC ≤ 0 |
| M1 | ✅ Complete | Model compliance probe — prompt contract + streaming evidence |
| M1b | ✅ Complete | Repeated-run reliability harness (Wilson score intervals) |
| M2 | 🟡 Near Complete | Legacy resolver deletion done; formatter narrowing partially done |
| M3 | 🟢 Partially Started | CI grep gates active via `design-doc-gate.yml` (8 gates enforced) |

### M2 Completed Work (via PR #6641)
- ✅ `game_state.py` — all legacy resolvers and dataclasses deleted (422 LOC)
- ✅ `world_logic.py` — `build_level_up_rewards_box()` deleted, all `resolve_level_progression()` calls removed
- ✅ `agents.py` — `_is_stale_level_up_pending()` deleted, all routing uses `is_level_up_active()`
- ✅ `rewards_engine.sync_level_up_signals()` replaces 200-line `ensure_level_up_rewards_pending()`
- ✅ `_enforce_atomicity()` rewritten for semantic SSE validation (fail-closed)
- ✅ Canonical XP field names enforced: `current_turn_exp`, `total_exp_for_next_level`
- ✅ `ensure_rewards_box()` returns `tuple[dict|None, dict|None]`, field `resolved_target_level` → `new_level`

### M2 Remaining Work
- `format_model_level_up_signal()` → make private (`_format_model_level_up_signal`)
- `project_level_up_ui()` → delete when no remaining callers (currently used by `_project_level_up_ui_locally()`)

### M3 Status — CI Enforcement Gates (Active)
The `design-doc-gate.yml` workflow enforces 8 grep-based boundary checks on every PR:

| Gate | Rule | Status |
|------|------|--------|
| `world_logic 0 rewards_engine public API imports` | No direct `from rewards_engine import` in world_logic | ✅ Enforced |
| `world_logic 0 resolve_level_up_signal calls` | No direct resolver calls | ✅ Enforced |
| `constants get_xp_for_level` | No duplicate XP helpers in constants | ✅ Enforced |
| `constants get_level_from_xp` | No duplicate level helpers in constants | ✅ Enforced |
| `_is_state_flag_true 2 files` | Helper exists in exactly 2 files | ✅ Enforced |
| `world_logic ≤1 project_level_up_ui` | At most 1 non-wrapper call | ✅ Enforced |
| `non-rewards 0 direct level-up pair builders` | No external pair builders | ✅ Enforced |
| `llm_parser canonicalize_rewards=1` | Exactly 1 canonicalize call | ✅ Enforced |

### M3 Remaining Work
- Centralization ratchet: no new `def` in `world_logic.py` whose name exists in `rewards_engine.py`
- Architecture test: `level_up_signal` formatting stays in `rewards_engine.py`

---

## Field Ownership Quick Reference

**Every shared dict field must have exactly ONE authoritative writer.**

| Dict / Field | Writer | Semantic |
|--------------|--------|----------|
| `level_up_signal.current_level` | LLM | Int: level before applying the level-up |
| `level_up_signal.target_level` | LLM | Int: target level now available; `target_level > current_level` is the model-owned level-up signal |
| `rewards_pending.level_up_available` | Backend-derived compatibility/display field from accepted `level_up_signal` | Bool: deterministic UI alias; do not ask the model to emit it |
| `rewards_pending.xp_gained` | LLM via state_updates; `rewards_engine.sync_level_up_signals()` only for transitional correction | Int: model-calculated XP delta for rewards box |
| `rewards_pending.new_level` | Backend-derived compatibility/display field from `level_up_signal.target_level` | Int: deterministic UI alias; do not ask the model to emit it |
| `player_character_data.experience.current` | LLM via state_updates | Int: cumulative XP (backend NEVER writes) |
| `custom_campaign_state.level_up_in_progress` | Server-owned modal/session control state | Bool: level-up modal active; model must not write this on story/rewards turns |
| `custom_campaign_state.level_up_pending` | Backend-derived compatibility/control field from accepted level-up signal or modal state | Bool: modal routing compatibility; model must not write this on story/rewards turns |
| `custom_campaign_state.level_up_complete` | Server-owned level-up flow state | Bool: level-up flow finished (suppresses `is_level_up_active()`) |
| `custom_campaign_state.level_up_cancelled` | Server-owned level-up flow state | Bool: level-up deferred (suppresses `is_level_up_active()`) |

For the full field registry, see `.claude/skills/field-ownership-contracts.md`.

---

## Key Architectural Invariants (Post-M2)

1. **Correction-only validation**: `is_level_up_active()` validates explicit flags against explicit model/state fields only to suppress contradictions. A stale `level_up_pending=True` can be rejected when the persisted state proves the model-owned level-up signal is already applied or mechanically impossible, but this must not become a backend threshold-derived level-up decision.

2. **SSE atomicity**: `_enforce_atomicity()` enforces that level-up `rewards_box` and `planning_block` always ship together. If either is missing, both are dropped (fail-closed). This prevents UI soft-locks.

3. **Completion/cancellation precedence**: `level_up_complete=True` or `level_up_cancelled=True` always returns `False` from `is_level_up_active()`, regardless of other flags.

4. **Level cap**: Level 20 characters always return `False` from `is_level_up_active()` for pending flags, preventing stale signals at max level.

5. **Single delegation**: `world_logic._project_level_up_ui_locally()` is a 1-line call to `rewards_engine.project_level_up_ui()`. No independent computation.

---

## Canonical References

- **Design doc**: `roadmap/zfc-level-up-model-computes-2026-04-19.md` (repo) / `~/roadmap/zfc-level-up-model-computes-2026-04-19.md` (local) (1,725 lines — read lines 219-241 for the file-responsibility table)
- **Task specs**: `roadmap/zfc-pr-task-specs-2026-04-22.md` (repo) / `~/roadmap/zfc-pr-task-specs-2026-04-22.md` (local) (per-PR scope locks)
- **Postmortem**: `roadmap/2026-04-21-level-up-zfc-loop-postmortem.md` (repo) / `~/roadmap/2026-04-21-level-up-zfc-loop-postmortem.md` (local)

---

## ZFC Leveling Compliance Worker Prompt

When delegating PR refactors (such as PRs #6718, #6725, #6736, #6756, #6758) to autonomous workers, **provide them with this exact prompt** to prevent common architectural drift:

```markdown
# ZFC Leveling Compliance Redesign Prompt

**Objective**: Refactor and redesign existing level-up, streaming orchestration, and infinite progression logic to strictly comply with the new Zero-Framework Cognition (ZFC) mandate: **"LLM Calculates, Backend Corrects."**

---

## 🛑 Core Architectural Mandate
The backend is no longer the source of truth for gameplay math. You must enforce the following invariant across your PR:
**The LLM owns all XP arithmetic, target-level math, and level-up availability.** 
The backend code must **never** independently calculate these facts from thresholds as a primary path. 

### 1. The "Backend Just Fixes" Rule (Correction Exception Boundary)
The backend is ONLY permitted to apply *correction guards* to prevent degraded UX (e.g., stale-flag time-freezes, SSE soft-locks, or already-applied level-up residues).
*   **Where**: These guards are permitted **ONLY** within `$PROJECT_ROOT/rewards_engine.py`.
*   **How**: Guards must be "correction-only." They may compare explicit model/state fields for contradictions and suppress or normalize invalid payloads.
*   **Forbidden**: Guards must *never* synthesize a competing backend level-up decision or trigger a level-up prompt because backend XP math crossed a threshold. Scattered heuristics across multiple files are strictly forbidden.

### 2. Strict File Boundaries
Before modifying any file, verify your changes against these boundaries. If your logic violates these rules, **STOP and redesign.**

*   **`rewards_engine.py`**
    *   **Owns**: Formatting explicit model signals, correction-only contradiction guards, `canonicalize_level_up_signal()`, and SSE atomicity enforcement.
    *   **Must NOT Do**: Primary XP/level calculations, threshold-derived level-up decisions, or model calls.
*   **`world_logic.py`**
    *   **Owns**: Modal locks, injecting finish choices, wrapping precomputed payloads.
    *   **Must NOT Do**: Recomputing XP, synthesizing choices, directly calling `canonicalize_level_up_signal()`, or making threshold-based level-up decisions.
*   **`game_state.py`**
    *   **Owns**: State storage and deterministic mechanical primitives (`xp_needed_for_level`, `level_from_xp`).
    *   **Must NOT Do**: Deciding level-ups from state, replacing model choices, or containing level-up resolvers.
*   **`agents.py`**
    *   **Owns**: Routing to the correct agent using `rewards_engine.is_level_up_active()`.
    *   **Must NOT Do**: Inline flag interpretation, XP extraction, or stale-flag recovery logic.

### 3. Infinite Leveling & Streaming Parity Specifics
*   If you are removing the Level 20 hard-cap or fixing streaming parity, you must ensure that the progression relies on the LLM's explicit `level_up_signal` (including `previous_turn_exp`, `current_turn_exp`, `new_level`, etc.).
*   Do not fallback to having the backend detect `current_turn_exp > threshold` to trigger the level-up modal. The LLM must emit `level_up: true`. If the LLM misses it, the backend fails closed (suppresses the level-up), it does *not* fix it by synthesizing the level-up itself.

### 4. Required Action Items for Your PR
1.  **Audit your diff**: Search your PR for any instances where the backend calculates XP progress, checks thresholds to trigger events, or builds level-up choices independently. 
2.  **Remove backend inference**: Delete any code that tries to act as a "competing source of truth" against the LLM's `level_up_signal`.
3.  **Refactor to correction-only**: If your PR fixes a stale state bug, ensure the fix is a contradiction guard placed *only* in `rewards_engine.py` that suppresses the stale payload, rather than recalculating the correct state.
4.  **Grep for rogue flag checks**: You must not check `level_up_pending` or `level_up_in_progress` directly in `world_logic.py` or `agents.py`. You must replace these with calls to `rewards_engine.is_level_up_active()`, which contains the centralized correction guards.
5.  **Do NOT change the API contract**: `rewards_engine.canonicalize_rewards()` returns a 2-tuple `(rewards_box, planning_block)`. Do not change this signature. Use the `out_meta` dict parameter to pass out additional flags (like false-positives).

> **Failure to adhere to the "LLM Calculates, Backend Corrects" mandate will result in immediate rejection of the PR.** Consult `roadmap/zfc-level-up-model-computes-2026-04-19.md` and `.claude/skills/zfc-leveling-roadmap/SKILL.md` if you are unsure about a specific file boundary.
```

## Related Skills

- `.claude/skills/field-ownership-contracts.md` — full field writer/reader registry
- `~/.claude/skills/evidence-standards.md` — evidence requirements for production PRs
- `~/.claude/skills/pr-green-definition.md` — canonical `/green` (CI green + no merge conflicts) definition; quality gates live in the draft phase
