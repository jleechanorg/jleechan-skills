# Closure report — jleechan-skills top-20/top-20 (max-40) command archival

**Bead:** `bd-cmdtop40-closure-report-owt` (evidence bead, TDD-exempt)
**Generated:** 2026-08-24T01:06:17Z (frozen snapshot timestamp — see below)
**HEAD SHA at generation:** `1d10a813` (branch `cmd-top40-archival-2026-08-23`)

## EXCEEDS max-40 by 54

**Final closure-adjusted count: 94 commands out of 239 currently-active commands vs. the literal "max 40" ask — EXCEEDS max-40 by 54.**

This is not a rounding or a soft estimate: `len(closure) == 94`, computed by literally invoking `scripts/rank_commands_repo_scoped.py` then `scripts/compute_command_closure.py`, verified byte-identical across repeated runs (see reproducibility below).

## Why this number, not the earlier 80

During this session, the closure computation was run twice against **live** re-scans of usage history and produced two different numbers 15 minutes apart: **80**, then **94**. Root cause: the underlying usage scanner (`count_command_usage_unified.py`) reads `~/.hermes/state.db`, `~/.claude/projects/*.jsonl`, and `~/.codex/state_5.sqlite` — and this very archival session was itself generating `/web-advice`, `/research`, `/plan-micro` invocations that got logged into that same history in real time. Re-scanning mid-session shifted the top-20 human/agent lists, which shifted the 27 seeds, which shifted the closure. The 80 number is **stale** and superseded; **94 is the number that matters** for this decision.

**Fix applied:** froze one usage snapshot (`archive/usage_snapshot_frozen_2026-08-23.json`, generated `2026-08-24T010617Z` via `count_command_usage_unified.py --days 0 --json`) and reran ranking + closure exclusively against that frozen file via `--input`/`--seed-from`. All numbers in this report are derived from the frozen snapshot, not a fresh live scan. Any future re-run of this report must use the same frozen snapshot (or freeze a new one and document why) — never a bare live rescan — to stay reproducible.

## Reproduction

```bash
python3 scripts/rank_commands_repo_scoped.py --input archive/usage_snapshot_frozen_2026-08-23.json --json > /tmp/ranking.json
python3 scripts/compute_command_closure.py --seed-from /tmp/ranking.json --json > /tmp/closure.json
diff <(python3 -m json.tool --sort-keys archive/CLOSURE-REPORT-2026-08-23.json) <(python3 -m json.tool --sort-keys /tmp/closure.json)
```

Empty diff confirms the committed report matches a fresh re-run against the frozen snapshot. Verified twice during generation (byte-identical, `iterations: 8`).

## The 27-command seed union (top-20 human ∪ top-20 agent, repo-scoped)

`advice`, `green`, `repro`, `research`, `ms`, `claw`, `history`, `er`, `linux`, `f`, `es`, `web-advice`, `browser`, `skillify`, `browserclaw`, `auto`, `wiki-search`, `smoke`, `roadmap`, `levelup`, `execute`, `copilot`, `fixpr`, `nextsteps`, `harness`, `learn`, `end2end-testing`

## The 67 commands pulled in beyond the 27-seed union

Every command below is traced to the command that referenced it (a seed directly, or transitively through another closure member) — see `archive/CLOSURE-REPORT-2026-08-23.json`'s `edges` field for the full raw reference graph.

| # | Command | Pulled in via | Source type |
|---|---|---|---|
| 1 | `arch` | `research` | direct seed reference |
| 2 | `archreview` | `arch` | transitive (chained) reference |
| 3 | `bq` | `es` | direct seed reference |
| 4 | `c` | `cerebras` | transitive (chained) reference |
| 5 | `cereb` | `cerebras` | transitive (chained) reference |
| 6 | `cerebras` | `c` | transitive (chained) reference |
| 7 | `code-standards` | `goal_harness` | transitive (chained) reference |
| 8 | `commentcheck` | `copilot` | direct seed reference |
| 9 | `commentfetch` | `copilot` | direct seed reference |
| 10 | `commentreply` | `copilot` | direct seed reference |
| 11 | `cons` | `auto` | direct seed reference |
| 12 | `consensus` | `cons` | transitive (chained) reference |
| 13 | `converge` | `goal_harness` | transitive (chained) reference |
| 14 | `debug` | `exportcommands` | transitive (chained) reference |
| 15 | `deploy` | `smoke` | direct seed reference |
| 16 | `e` | `execute` | direct seed reference |
| 17 | `evidence_review` | `er` | direct seed reference |
| 18 | `exportcommands` | `localexportcommands` | transitive (chained) reference |
| 19 | `f-pr` | `f` | direct seed reference |
| 20 | `factory` | `f` | direct seed reference |
| 21 | `factory-evolve` | `integrate` | transitive (chained) reference |
| 22 | `factory-spec` | `fs` | transitive (chained) reference |
| 23 | `fake` | `exportcommands` | transitive (chained) reference |
| 24 | `fakel` | `fake` | transitive (chained) reference |
| 25 | `fs` | `f` | direct seed reference |
| 26 | `goal_harness` | `h` | transitive (chained) reference |
| 27 | `goalexec` | `goal_harness` | transitive (chained) reference |
| 28 | `gstatus` | `copilot` | direct seed reference |
| 29 | `guidelines` | `auto` | direct seed reference |
| 30 | `h` | `factory` | transitive (chained) reference |
| 31 | `handoff` | `roadmap` | direct seed reference |
| 32 | `header` | `status` | transitive (chained) reference |
| 33 | `integrate` | `testserver` | transitive (chained) reference |
| 34 | `localexportcommands` | `second_opinion` | transitive (chained) reference |
| 35 | `mac` | `linux` | direct seed reference |
| 36 | `memory` | `archreview` | transitive (chained) reference |
| 37 | `memory_search` | `ms` | direct seed reference |
| 38 | `newbranch` | `handoff` | transitive (chained) reference |
| 39 | `orch` | `converge` | transitive (chained) reference |
| 40 | `orchestrate` | `roadmap` | direct seed reference |
| 41 | `pair` | `copilot` | direct seed reference |
| 42 | `parallel` | `planexec` | transitive (chained) reference |
| 43 | `perp` | `research` | direct seed reference |
| 44 | `plan` | `planexec` | transitive (chained) reference |
| 45 | `planexec` | `execute` | direct seed reference |
| 46 | `pr` | `exportcommands` | transitive (chained) reference |
| 47 | `push` | `exportcommands` | transitive (chained) reference |
| 48 | `pushl` | `auto` | direct seed reference |
| 49 | `pushlite` | `pushl` | transitive (chained) reference |
| 50 | `qwen` | `cerebras` | transitive (chained) reference |
| 51 | `r` | `roadmap` | direct seed reference |
| 52 | `review-enhanced` | `guidelines` | transitive (chained) reference |
| 53 | `reviewd` | `reviewdeep` | transitive (chained) reference |
| 54 | `reviewdeep` | `auto` | direct seed reference |
| 55 | `reviewe` | `review-enhanced` | transitive (chained) reference |
| 56 | `second_opinion` | `secondo` | transitive (chained) reference |
| 57 | `secondo` | `advice` | direct seed reference |
| 58 | `status` | `converge` | transitive (chained) reference |
| 59 | `test` | `smoke` | direct seed reference |
| 60 | `testhttp` | `smoke` | direct seed reference |
| 61 | `testhttpf` | `smoke` | direct seed reference |
| 62 | `testserver` | `push` | transitive (chained) reference |
| 63 | `thermo` | `code-standards` | transitive (chained) reference |
| 64 | `think` | `roadmap` | direct seed reference |
| 65 | `thinku` | `research` | direct seed reference |
| 66 | `up` | `parallel` | transitive (chained) reference |
| 67 | `usage` | `header` | transitive (chained) reference |

30 of 67 are direct seed references; 37 are transitive (chained through another already-kept command). Zero untraced members — every one of the 67 has a concrete source edge in `archive/CLOSURE-REPORT-2026-08-23.json`.

## Precision vs. the naive proxy

The naive unfiltered regex proxy measured during planning was ~93-100 commands (session-dependent, before the frozen-snapshot fix). The precision-filtered closure algorithm (`scripts/compute_command_closure.py`, false-positive denylist reused from `tests/test_swarm_references.py`'s pattern) rejected 49 candidate tokens as non-command false positives (path fragments, prose words, TUI modal names — e.g. `EXECUTE`, `ao-operator-discipline`, `browser-control`, `dice`, `context` — none of which resolve to a real `.claude/commands/<name>.md` file in this repo). Full rejection list is in `archive/CLOSURE-REPORT-2026-08-23.json`'s `rejected` field.

## Determinism

Two consecutive runs against the same frozen snapshot produced byte-identical JSON (`diff` empty, `iterations: 8` both times).

## Open question (flagged, not resolved here)

The 94-command closure includes commands merely *mentioned* by a kept command's documentation, not only ones the kept command actually *delegates to* at runtime. A tighter closure would need to distinguish "delegates to" from "merely references" — this distinction was not built into `compute_command_closure.py` (out of scope for this bead; the ironclad contract's precision bar was "genuine delegation reference" per its documented pattern list, which this script implements literally). This tension is carried forward explicitly into `archive/ARCHIVE-DECISION-2026-08-23.md` rather than silently resolved here.
