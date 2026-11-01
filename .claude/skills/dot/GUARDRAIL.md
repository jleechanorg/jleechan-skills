# Dot Coordinator Guardrail — Thin Pointer Budget

The dot skill is a **thin pointer**: mechanical transport between coding agents
and the ChatGPT "dot" assistant. Scripts type, read, submit, clear, and verify —
nothing else. All judgment (what to send, when to submit vs. clear a peer draft,
how to coordinate) lives in `SKILL.md` and the calling agent, never in code.

## Enforced budgets (CI-checked; see jleechan-skills `.github/workflows/tests.yml`)

| Surface | Current | Budget (hard cap) |
|---|---|---|
| `dot-coordinator/scripts/ping-dots.py` + `dot-coordinator-wrapper.sh` + `pi-lunaroute-adapter.sh` (canonical launcher plus temporary legacy wrapper/adapter/launcher forwarding files, combined) | 150 LOC | **≤ 150** |
| `dot-coordinator/SKILL.md` (coordinator prompts & policy) | candidate | **≤ 400** |
| `scripts/dot.sh` | 479 LOC | **≤ 520** |
| `scripts/dot_chrome.mjs` | 843 LOC | **≤ 900** |
| Transport scripts combined (`dot.sh` + `dot_chrome.mjs`) | 1322 LOC | **≤ 1400** |
| `SKILL.md` (policy layer — grows freely, this is where behavior belongs) | 174 LOC | **≤ 400** |
| `tests/` (excluded — tests guard behavior, they are not transport) | 417 LOC | no cap |

## Rules

1. **New behavior goes in `SKILL.md` first.** If a change adds judgment,
   decision logic, or policy to `dot.sh`/`dot_chrome.mjs`, it is in the wrong
   place — rewrite it as an agent instruction here or in `SKILL.md`.
2. **New script code must be mechanical**: launcher validation and process
   lifecycle only. Agent judgment belongs in the coordinator skill. Combined
   launcher glue must stay within 150 physical lines; do not hide code in a
   generated file or compress statements to evade the count.
3. **Raising a cap requires the operator** (`jleechan`). Any PR that exceeds a
   cap fails CI; fixing it means either shrinking the scripts or getting the
   operator to bump the cap in this file with a stated reason.
4. **CI** (jleechan-skills `.github/workflows/tests.yml`): on PRs and pushes touching
   `.claude/skills/dot/**`, `scripts/check_budget.sh` recomputes the LOC counts
   and fails if any cap in this table is exceeded, plus `bash -n` / `node --check`
   syntax gates and the transport unit tests.

## History

- 2026-10-14: canonical home is `jleechanorg/jleechan-skills` `.claude/skills/dot/`;
   the interim `jleechanorg/dot-skill` repo was archived after consolidation.
   Budgets set at current size + headroom after the peer-draft contention incident
   (45+ min stuck draft); policy moved from a code default (auto-clear) to SKILL.md
   (check back ≤5 min, then submit sensible drafts / clear half-typed junk) with
   `submit-draft`/`clear-draft` as thin primitives.
