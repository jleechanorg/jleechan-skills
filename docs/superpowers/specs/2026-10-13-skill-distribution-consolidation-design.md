# Design: consolidate skill-distribution mechanisms (reconciliation-first)

Date: 2026-10-13 · Repo: jleechanorg/jleechan-skills · Status: corrected after review

## Context (verified 2026-10-13, reproduced by `scripts/report_skill_inventory_divergence.py`)
| Mechanism | Payload |
|---|---|
| `.claude/skills/` | 239 skills (README: source of truth) |
| `shared-skills.json` (`jleechan-shared-skills-v1`) | 4 reconciled skills, sha256-pinned; the flow `SHARED-SKILLS.md` names current |
| `portable/manifest.json` (`jleechan-portable-skills-v1`) | 29 skills / 32 files + `portable/skills/**` |
| marketplace manifests | `.claude-plugin/marketplace.json` **and** `.agents/plugins/marketplace.json` |
| `install-claude-commands.sh` | whole-home installer (docs say do not use) |
| live trees | `~/.claude/skills` 643 · `~/.agents/skills` 645 · `~/.codex/skills` 469 |

### Corrected finding 1 - the portable tree is NOT a duplicate
**Whole-package** comparison (every file in each skill dir; build junk excluded) of the 29
portable skills against `.claude/skills/**`:
- **7 portable-only** (no `.claude/skills` counterpart): `cmux-restore, diagnosing-bugs, er, es, harness, p, sq`
- **20 divergent packages**: `advice, cmux-backup, cmux-goal, cmux-steer, conversation-history-sparse, evidence-review, evidence-standards, harness-engineering, history, llm-first, memory-search, ms, nextsteps, parallel, parallelize-to-ceiling, ready, redgreen, research, superpowers-quick, web-advice`
- **2 byte-identical**: `backend-first, root-cause-first`

A SKILL.md-only comparison had reported 19/3; widening to the whole package moved `llm-first`
into the divergent set (a non-SKILL.md file differs) - the understated divergence a reviewer flagged.

Therefore any plan that deletes `portable/**` as "duplicates" would **destroy 7 unique skills and choose 20 bodies arbitrarily**. Deletion is blocked until per-skill reconciliation decides which body wins.

### Corrected finding 2 - the marketplace manifests are not interchangeable
They differ materially: `.agents/plugins/marketplace.json` uses name `jleechan-skills-marketplace` and source `{"source":"github","repo":"jleechanorg/jleechan-skills"}`; `.claude-plugin/marketplace.json` uses name `jleechan-skills`, source `"./"`, version `1.0.1`, plus a description/author. A symlink is a **semantic change** for whichever consumer reads the `.agents` file, so single-sourcing requires consumer validation and a format mapping, not a blind symlink.

## Problem
Five distribution channels, two bundle formats/verifiers, two marketplaces with different schemas, three live discovery trees, and four sync/verify checkers. The genuine defect is **ambiguity + hidden divergence**, not simple duplication.

## Assumptions and Recommended Defaults (auto-picked; /sq invocation authorizes)
| Question | Auto-picked answer | Rationale |
|---|---|---|
| Is `portable/**` duplicate content? | **No** - divergent variant set (7 unique, 20 differing, 2 identical) | measured; `scripts/report_skill_inventory_divergence.py` |
| Which manifest should survive? | `shared-skills.json` **for the reconciled bundle**, with `.claude/skills/**` remaining the content source; the portable set must be reconciled INTO it, never deleted wholesale | SHARED-SKILLS.md names it current; the portable set holds unreconciled variants |
| Delete or regenerate portable now? | **Neither yet** - ship the whole-package divergence tool + a **per-skill disposition ledger**; reconcile per skill; then collapse | deletion is irreversibly destructive of unique bodies |
| What guard replaces count-pinning? | A fail-closed **disposition ledger** (`docs/superpowers/skill-inventory-dispositions.json`): every portable skill needs a `keep-claude / keep-portable / merge / drop` disposition, and `portable/**` may only be deleted when every row is resolved | pinning 7/19/3 freezes a snapshot every reconciliation PR must edit; it does not stop a bad collapse (both reviewers) |
| Marketplace single-sourcing | Deferred behind consumer validation + format mapping (no symlink) | the two files encode different source formats |
| Live trees | Target: `~/.claude/skills` canonical, other runtimes as generated links | `/up` skill: "Do not add .codex user projections" |
| Sequencing | S1 inventory+contract+decision (this PR, non-destructive) → S2 per-skill reconciliation → S3 collapse bundle/verifier → S4 marketplace single-source after validation → S5 retire dead installer | each stage independently testable and reversible |

## Alternatives rejected
1. **Delete `portable/**` as duplicates** - rejected: destroys 7 unique skills, picks 20 bodies arbitrarily (verified numbers above).
2. **Symlink the marketplace manifests** - rejected: different name/source schema; silent semantic change for the `.agents` consumer.
3. **Adopt the 29-skill portable set as the single bundle** - rejected: `shared-skills.json` is the flow the repo's docs/installer designate current, and the portable bodies are stale variants of most overlaps.

## Chosen design (reconciliation-first)
- **S1 (this PR)**: ship `scripts/report_skill_inventory_divergence.py` (whole-package compare + `--write-ledger`), the evidence-derived `docs/superpowers/skill-inventory-dispositions.json` (29 rows, unresolved), `tests/test_skill_inventory_dispositions_contract.py` (fail-closed: every manifest entry needs a disposition; deletion requires all rows resolved), correct this spec/plan, and record the target architecture. **No deletions, no symlinks.**

### Review verdicts (2026-10-13, /advice document review at e64129d)
- **Codex**: *"Proceed with reconciliation-first S1 and zero deletions, after strengthening its guard and mapping installer consumers."* - pinning counts is the wrong lasting contract; the report must cover whole packages, not SKILL.md alone; map installers first.
- **Opus**: *"Keep reconciliation-first with zero deletions, but change the S1 guard from pinned counts to a per-skill disposition ledger, and widen the tool before S2 starts."* - even the byte-identical skills carry no deletion benefit until S3, since other scripts still reference `portable/`.
Both are incorporated in this revision.
- **S2**: per-skill reconciliation of the 7 portable-only and 20 divergent entries with an explicit decision record (which body wins and why); add reconciled skills to `shared-skills.json`.
- **S3**: after S2, collapse to the single manifest + one verifier; delete `portable/**` only when its content is fully represented.
- **S4**: validate each marketplace consumer, then single-source with a mapping that preserves both schemas.
- **S5**: retire `install-claude-commands.sh` (precondition: no launchd/cron invocation).

## Implementation Preconditions
- S2 requires semantic review of each divergent skill (not mechanical), producing a disposition per name in the ledger.
- **Installer consumers must be mapped before S2/S5** (reviewer finding): `scripts/install_shared_catalog.py` reads both skill trees **without** consulting `shared-skills.json`, and `install-claude-commands.sh` still serves documented-and-tested installation paths. Retiring either requires migrating those callers first.
- S4 requires identifying the consumer of `.agents/plugins/marketplace.json` and its expected schema.
- S5 requires confirming no live invocation of the whole-home installer **and** migrating its documented/tested paths.

## Out of scope
Changing which skills exist; reconciling the remaining 210 `.claude/skills/**` entries.
