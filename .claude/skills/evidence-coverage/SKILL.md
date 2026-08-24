---
name: evidence-coverage
description: Build a Logic x Evidence Matrix mapping every production logic change in a PR to its required testing layer and current evidence status.
---

# Evidence Coverage Analysis — Living World & PR Scope

When invoked (via `/evidence-coverage`), build a **Logic × Evidence Matrix** that maps every
production logic change in the current PR to its required testing layer and current evidence status.

## Procedure

### 1. Identify all production file changes

```bash
git diff origin/main...HEAD --name-only -- $PROJECT_ROOT/ | grep -v tests/
```

For each file, extract the logical changes (new functions, modified behavior, prompt changes,
schema changes). Group them by **domain** (e.g., trigger gate, prompt contract, backlog pruning,
sanctuary mode, turn counters, streaming dispatch).

### 2. Classify each logical change into a testing layer

Use the testing-layers skill (`.claude/skills/testing-layers/SKILL.md`) decision matrix:

| Layer | Name | Characteristics | When Required |
|-------|------|----------------|---------------|
| L1 | Unit / Deterministic | No server, no LLM, pure function | Math, parsing, schema validation, prompt-contract string checks |
| L2 | Integration (mock LLM) | Server running, mock LLM | Route wiring, middleware, auth, state merge |
| L3 | Real LLM (MCP) | Real server + real Gemini | Model compliance, prompt effectiveness, behavioral contracts |
| L5 | Browser E2E | Full stack + browser | UI rendering, player-visible behavior |

**Key rule**: Any claim about LLM compliance (event frequency, sanctuary activation, prompt
obedience) MUST have L3 evidence. L1 prompt-contract tests prove the prompt *says* the right
thing; L3 proves the model *does* the right thing.

### 3. Locate existing evidence

Search evidence directories:
```bash
ls /tmp/your-project.com/<branch>/  # evidence bundles
find /tmp/your-project.com/<branch>/ -maxdepth 3 -name "evidence.md"
```

For each bundle, extract:
- Git HEAD SHA from `evidence.md` or `metadata.json`
- Pass rate
- Scenario names
- Timestamp

### 4. Check evidence freshness

Evidence is **STALE** if production files changed since the evidence SHA:
```bash
git diff <evidence_sha>..HEAD --name-only -- $PROJECT_ROOT/ | grep -v tests/
```

If any non-test production file changed, the evidence must be re-run.

### 5. Build the matrix

Output a markdown table with these columns:

| ID | Domain | Logic Change | File(s) | Layer | Test File | Evidence Status | Gap? |
|----|--------|-------------|---------|-------|-----------|----------------|------|

**Evidence Status values:**
- `FRESH (SHA xxx, N/N pass)` — evidence exists at current HEAD, all scenarios pass
- `STALE (SHA xxx, N/N pass)` — evidence exists but production files changed since
- `MISSING` — no evidence bundle found
- `N/A` — layer doesn't require evidence (e.g., L1 unit tests run in CI)

**Gap values:**
- Empty — covered
- `STALE` — needs re-run
- `MISSING` — needs first run
- `CRITICAL` — L3 evidence missing for LLM compliance claim

### 6. Identify Domain-Specific Behavioral Contracts

For the logical changes identified, define the key behavioral contracts that need L3 proof. For example, if a PR introduces a new "Sanctuary Mode", the contracts might include:
- Autonomous completion detection
- Duration scaling by arc scale
- Sanctuary breaks on player-initiated major aggression

List these contracts for the current PR and ensure each has corresponding L3 evidence.

### 7. Report format

After the matrix, include:

**Summary statistics:**
- Total logic changes: N
- Covered (fresh): N
- Stale: N
- Missing: N
- Critical gaps: N

**Recommended action** for each gap — which test to run, expected command, estimated time.

## Evidence bundle locations

- MCP tests: `/tmp/your-project.com/<branch>/<test_name>/latest/`
- Unit tests: CI (no local evidence needed)
- Antagonism prompt contract: `testing_mcp/test_living_world_antagonism_prompt_contract.py` (L1, standalone)
- Sanctuary mode: `testing_mcp/test_sanctuary_mode.py` (L3, real LLM)
- LW trigger gate: `testing_mcp/test_lw_trigger_gate.py` (L3, real LLM)
- Multi-turn frequency: `testing_mcp/test_living_world_real_e2e.py` (L3, multi-turn)
- Corrupt recovery: `testing_mcp/test_living_world_corrupt_recovery.py` (L3, real LLM)

## Cross-references

- Testing layers: `.claude/skills/testing-layers/SKILL.md`
- E2E testing: `.claude/skills/end2end-testing.md`
- Evidence standards: `~/.claude/skills/evidence-standards.md` (user-scope) and `.claude/skills/evidence-standards.md` (repo-scope)
- Root-cause first: `.claude/skills/root-cause-first/SKILL.md`
