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

For WorldArchitect-specific backend ownership, this summary defers to the
repository overlay `.claude/skills/worldai-zfc/SKILL.md`, the portable
`~/.claude/skills/zero-framework-cognition/SKILL.md`, and
`.claude/skills/backend-justified/SKILL.md`. Do not infer permission to alter
model-owned domain state from schema validity, determinism, or this file alone.

> **"LLM Owns Domain Decisions; Backend Preserves and Executes"** — the model owns gameplay interpretation, progression, rewards, and choices. The server owns authorization, storage, transport, concurrency, and modal/session control. A backend transformation of model-owned fields is an exception only when the active repository policy explicitly authorizes that named exception and its required evidence is recorded; preserving a valid player turn is the UX default.

> **Correction Exception Boundary**: This guide does not authorize backend correction of gameplay meaning. Follow the local ZFC/backend-justification contract for each proposed transformation. A registered adjustment is necessary only where that active contract requires it; registration or determinism alone does not authorize a domain transformation. Name the exact field, function, policy basis, necessity, and required evidence. Do not add defaults, clamps, suppressions, or normalization to model-owned domain fields based only on contradiction, UX, or determinism.

> **Opaque Choice Boundary**: Planning choice IDs are opaque handles, not semantic signals. `level_up_now`, `finish_level_up_return_to_game`, and `custom_action` are migration/compatibility handles only. Level-up choice meaning must come from explicit model/schema fields on the resolved choice object, not from ID text, prefixes, labels, or backend allowlists.

---

## File Responsibility Table (Mandatory)

Before modifying ANY file for level-up/rewards/XP work, verify against this table.
**If your change puts logic in a "MUST NOT DO" column → STOP and redesign.**

| File | OWNS | MUST NOT DO |
|------|------|-------------|
| `rewards_engine.py` | Format and project explicit model signals; keep transport/payload atomicity handling limited to preserving complete supplied representations and server-owned transaction/control invariants. Any transformation of model-owned gameplay fields requires its own named, policy-authorized exception and evidence. | Model calls, Firestore writes, text interpretation, primary XP/level calculation, threshold-derived level-up decisions, or unregistered correction/normalization/suppression of gameplay meaning |
| `world_logic.py` | Modal locks and consumption of model-authored finish choices; wrap payloads only where its contract permits | Inject or synthesize choices; recompute model-owned progression; call `canonicalize_level_up_signal()` directly |
| `game_state.py` | State storage, deterministic mechanical primitives (`xp_needed_for_level`, `level_from_xp`, `coerce_int`) | Decide level-up from state, replace model choices, own level-up decisions, contain level-up dataclasses or resolvers |
| `agents.py` | Route to correct agent using `rewards_engine.is_level_up_active()` | Inline flag interpretation, XP extraction, stale-flag recovery logic |
| `llm_parser.py` | Parse model output, call the pipeline **once** via `canonicalize_rewards()`, persist/deliver | Duplicate rewards formatting, inline false-positive mutations, call canonicalization separately |
| `narrative_response_schema.py` | Preserve model output losslessly and validate structural/schema requirements without deciding gameplay meaning | Class feature synthesis, state mutation, building UI payloads, or rejecting a turn because model-authored progression fields appear contradictory |
| `llm_service.py` | LLM request/response pipeline, retry on `SchemaRejectionError` | Rewards formatting, level-up flag interpretation, modal state mutation |
| `structured_fields_utils.py` | Extract non-empty structured fields | Semantic validation, alias normalization, UI formatting |
| `prompts/level_up_instruction.md` | Class-AGNOSTIC contracts only — generic enumeration ("enumerate ALL subclass options as separate clickable choices"), generic announce-all-gains rules. The model owns the D&D 5e SRD. | Hardcode subclass names (oaths/circles/patrons/archetypes/domains), feature names (Divine Health, Channel Divinity, Second Wind…), spell names, or per-class numeric gains as named rules/HARD INVARIANTs. Class names allowed ONLY inside `e.g.`/`for example` illustrations. |

---

## Authorized Public API Surface

These are the **only** `rewards_engine` functions that external files may call:

| Function | Callers | Purpose |
|----------|---------|---------|
| `canonicalize_rewards(structured_fields, game_state, original_state)` | `llm_parser.py` (1 call), `world_logic.py` (polling paths) | Single convergence point for all rewards/level-up UI |
| `is_level_up_active(game_state)` | `agents.py`, `world_logic.py` | Read explicit progression signals and server-owned modal control; any domain transformation follows the Correction Exception Boundary |
| `project_level_up_ui(game_state, original_state)` | `world_logic.py` (via `_project_level_up_ui_locally()`) | Polling/projection path (transitional — delete when callers migrate) |
| `sync_level_up_signals(game_state, original_state)` | `world_logic.py` (via `ensure_level_up_rewards_pending()` shim) | Idempotent rewards_pending sync |
| `format_model_level_up_signal(signal)` | `llm_parser.py` (fallback path) | Explicit signal formatter (should become private `_format_...`) |

**All other functions are private implementation details.** Do not call `_canonicalize_core()`, `_enforce_atomicity()`, `_apply_contradiction_guard()`, `resolve_level_up_signal()`, or `ensure_rewards_box()` from outside `rewards_engine.py`.

---

## API Contract Freeze

- `canonicalize_rewards()` returns `(rewards_box, planning_block)` — a **2-tuple**. **Do NOT change this return signature.** Use `out_meta` dict parameter to pass additional data out (e.g., canonical signal, false-positive flags).
- `canonicalize_level_up_signal()` is called **inside** `rewards_engine.py` only. External files consume precomputed results.
- `is_level_up_active()` returns `bool`. It reads explicit progression signals and server-owned modal control. This API shape does not authorize contradiction suppression or XP-threshold decisions; any transformation of a model-owned field requires the named active-policy exception and evidence in the Correction Exception Boundary.
- `ensure_rewards_box()` returns `tuple[dict | None, dict | None]` (rewards_box, signal_metadata). Internal only.

---

## Common Boundary Violations

These are the most frequently observed agent drift patterns. If you catch yourself doing any of these, STOP:

| If you're about to... | WRONG file | RIGHT approach |
|----------------------|------------|----------------|
| Call `canonicalize_level_up_signal()` | `world_logic.py`, `llm_parser.py` | Only inside `rewards_engine.py` (via `_canonicalize_core`) |
| Build a `level_up_signal` dict | `world_logic.py` | Build in `rewards_engine.py`, pass via return or `out_meta` |
| Compute XP progress, thresholds, target level, or level-up availability as the primary path | any backend file | Ask the LLM for explicit calculated fields; preserve them unless the exact transformation satisfies the Correction Exception Boundary |
| Check `level_up_pending` / `level_up_in_progress` flags directly | `world_logic.py`, `agents.py` | Call `rewards_engine.is_level_up_active()` |
| Call `resolve_level_progression()` | anywhere | **Deleted.** Use `rewards_engine.is_level_up_active()` or `rewards_engine.project_level_up_ui()` |
| Use `build_level_up_rewards_box()` | anywhere | **Deleted.** Use `rewards_engine.ensure_rewards_box()` (internal) or `project_level_up_ui()` |
| Change `canonicalize_rewards()` return type | anywhere | **Don't.** Use `out_meta` dict instead |
| Add signal normalization aliases | `structured_fields_utils.py` | First establish the exact active-policy exception and evidence under the Correction Exception Boundary; this table alone grants no normalization authority |
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
├── YES → Model-owned gameplay meaning belongs in the prompt/schema
│   ├── Server execution or transport? Follow the ownership table and active contract
│   ├── Does world_logic.py need the result?
│   │   └── Pass via return value or out_meta dict
│   ├── Does agents.py need to know if level-up is active?
│   │   └── Call rewards_engine.is_level_up_active() — never inline flag checks
│   └── Does llm_parser.py need the result?
│       └── Call canonicalize_rewards() once; don't call internal functions directly
├── Is my change about model output?
│   └── Diagnose the prompt/schema at the root cause first
│       └── Preserve valid player turns; no contradiction-repair retry is authorized here
└── NO → Normal file protocol applies
```

---

## Historical Milestone Snapshot

The statuses and implementation notes below are a snapshot from [source commit `04afb7f1b93af731240f1298a1234237e4e608da`](https://github.com/jleechanorg/jleechan-skills/commit/04afb7f1b93af731240f1298a1234237e4e608da), dated 2026-05-13. They do not establish current project status or grant permission to add a transformation; verify current source and owner instructions before acting. In particular, the “fail-closed” semantic SSE wording describes that historical implementation report and does not authorize rejecting player turns.

| Milestone | Status | Description |
|-----------|--------|-------------|
| M0 | ✅ Complete | Delete legacy paths, net LOC ≤ 0 |
| M1 | ✅ Complete | Model compliance probe — prompt contract + streaming evidence |
| M1b | ✅ Complete | Repeated-run reliability harness (Wilson score intervals) |
| M2 | 🟡 Near Complete | Legacy resolver deletion done; formatter narrowing partially done |
| M3 | 🟢 Partially Started | Snapshot reported CI grep gates active via `design-doc-gate.yml` (8 gates reported enforced) |

### M2 Work Reported Complete at Snapshot (via [PR #6641](https://github.com/jleechanorg/worldarchitect.ai/pull/6641))
- ✅ `game_state.py` — all legacy resolvers and dataclasses deleted (422 LOC)
- ✅ `world_logic.py` — `build_level_up_rewards_box()` deleted, all `resolve_level_progression()` calls removed
- ✅ `agents.py` — `_is_stale_level_up_pending()` deleted, all routing uses `is_level_up_active()`
- ✅ `rewards_engine.sync_level_up_signals()` replaces 200-line `ensure_level_up_rewards_pending()`
- At the snapshot, `_enforce_atomicity()` was reported rewritten for semantic SSE validation (fail-closed); this is a historical implementation note, not current permission to reject turns.
- ✅ Canonical XP field names enforced: `current_turn_exp`, `total_exp_for_next_level`
- ✅ `ensure_rewards_box()` returns `tuple[dict|None, dict|None]`, field `resolved_target_level` → `new_level`

### M2 Remaining Work as Reported at Snapshot
The snapshot listed these follow-ups; verify current callers and ownership before using them as a plan:
- `format_model_level_up_signal()` → make private (`_format_model_level_up_signal`)
- `project_level_up_ui()` → delete when no remaining callers (reported then as used by `_project_level_up_ui_locally()`)

### M3 Snapshot — CI Enforcement Gates (Reported Active)
At the snapshot, `design-doc-gate.yml` was reported to enforce 8 grep-based boundary checks. Verify the workflow and its current scope before relying on this historical status.

| Gate | Rule | Status at snapshot |
|------|------|--------|
| `world_logic 0 rewards_engine public API imports` | No direct `from rewards_engine import` in world_logic | Reported enforced at snapshot |
| `world_logic 0 resolve_level_up_signal calls` | No direct resolver calls | Reported enforced at snapshot |
| `constants get_xp_for_level` | No duplicate XP helpers in constants | Reported enforced at snapshot |
| `constants get_level_from_xp` | No duplicate level helpers in constants | Reported enforced at snapshot |
| `_is_state_flag_true 2 files` | Helper exists in exactly 2 files | Reported enforced at snapshot |
| `world_logic ≤1 project_level_up_ui` | At most 1 non-wrapper call | Reported enforced at snapshot |
| `non-rewards 0 direct level-up pair builders` | No external pair builders | Reported enforced at snapshot |
| `llm_parser canonicalize_rewards=1` | Exactly 1 canonicalize call | Reported enforced at snapshot |

### M3 Remaining Work as Reported at Snapshot
The snapshot listed these planned checks; verify current code and workflow ownership before implementing them:
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
| `rewards_pending.xp_gained` | LLM via state_updates; any transitional transformation requires the named active-policy exception and evidence | Int: model-calculated XP delta for rewards box |
| `rewards_pending.new_level` | Backend-derived compatibility/display field from `level_up_signal.target_level` | Int: deterministic UI alias; do not ask the model to emit it |
| `player_character_data.experience.current` | Active repository field-specific contract | Int: cumulative accepted XP; writer and projection are owned by the current prompt/schema and ZFC contract |
| `custom_campaign_state.level_up_in_progress` | Server-owned modal/session control state | Bool: level-up modal active; model must not write this on story/rewards turns |
| `custom_campaign_state.level_up_pending` | Backend-derived compatibility/control field from accepted level-up signal or modal state | Bool: modal routing compatibility; model must not write this on story/rewards turns |
| `custom_campaign_state.level_up_complete` | Server-owned level-up flow state | Bool: level-up flow finished (suppresses `is_level_up_active()`) |
| `custom_campaign_state.level_up_cancelled` | Server-owned level-up flow state | Bool: level-up deferred (suppresses `is_level_up_active()`) |

For the full field registry, see `.claude/skills/field-ownership-contracts.md`.

---

## Key Architectural Invariants (Post-M2)

1. **Model-owned progression; server-owned modal control**: `is_level_up_active()` may read explicit model-authored progression fields and server-owned modal/session fields, but it must not adjudicate progression from XP thresholds or other game mechanics. Suppressing `level_up_pending=True` because a model-owned signal is “mechanically impossible” is a gameplay decision and is not authorized here. A correction to a model-owned field requires an exact active-policy exception, named field/function, concrete necessity, and that policy's evidence. Server-owned completion/cancellation state may control modal activity without rewriting the model's progression decision.

2. **Streaming preservation**: Preserve supplied stream fields and their representation aliases. Missing one field is not a reason to drop the other or reject the turn. Stream/payload atomicity enforcement may protect complete transport representations or server-owned transaction invariants; it must not validate gameplay semantics or discard a valid player turn over metadata/representation mismatch. Reject only when committing would corrupt server-owned storage.

3. **Completion/cancellation precedence**: `level_up_complete=True` or `level_up_cancelled=True` always returns `False` from `is_level_up_active()`, regardless of other flags.

4. **Progression limits**: Follow the active campaign progression contract; do not add a hardcoded cap or threshold-based fallback to this helper.

5. **Single delegation**: `world_logic._project_level_up_ui_locally()` is a 1-line call to `rewards_engine.project_level_up_ui()`. No independent computation.

---

## Canonical References
For any WorldArchitect backend or progression change, read the local overlay `.claude/skills/worldai-zfc/SKILL.md` together with `~/.claude/skills/zero-framework-cognition/SKILL.md`, `.claude/skills/backend-justified/SKILL.md`, and `.claude/skills/root-cause-first/SKILL.md`. Prompt/schema correction comes before backend protection. Preserve model-owned gameplay meaning and unknown fields; server-owned storage, authorization, transport, concurrency, and modal/session control remain server responsibilities. Any domain-field transformation must identify its exact active-policy exception, field and function, concrete necessity, and required evidence; where that policy requires registration, register it. This guide does not authorize finish-choice injection, paired payload dropping, gameplay defaults, clamps, semantic suppression, or rejection of a valid turn.

## Related Skills

- `.claude/skills/field-ownership-contracts.md` — full field writer/reader registry
- `~/.claude/skills/evidence-standards.md` — evidence requirements for production PRs
- `~/.claude/skills/pr-green-definition.md` — canonical `/green` (CI green + no merge conflicts) definition; quality gates live in the draft phase
