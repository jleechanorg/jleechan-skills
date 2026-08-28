# PR Green Definition — Skill

Design integrity is the mandatory prerequisite. 7-green is the minimum bar. These are not equal — a PR that achieves 7-green while violating the design doc or architecture contract is a regression, not a success. **You must fail such a PR at the design gate, before checking 7-green.**

---

## The Hierarchy (in force, highest to lowest)

```
1. Design Gate        ← prerequisite, must pass first
2. Regression Gate    ← no new boundary violations
3. 7-Green            ← minimum merge bar (CI + CR + Bugbot + comments + evidence + skeptic)
```

If Design Gate fails → **do not check 7-green, do not merge**.

---

## Step 0: Design Decision Gate

**Applies when: PR has >50 non-test production delta lines.**

The PR description MUST contain a `## Design Decision` section with:
1. **What this PR does** — one paragraph
2. **Architectural boundaries affected** — which files/modules, how
3. **Linked artifact** — a bead ID (`rev-xxxx`) OR a `.md` doc in `~/roadmap/` or `docs/design/`
4. **What this PR does NOT do** — explicit out-of-scope (prevents creep)

**If the linked artifact exists and describes invariants or boundaries:**
- READ the artifact
- Verify the diff respects stated boundaries
- FAIL if the diff changes files the design doc said wouldn't be touched
- FAIL if the diff violates an invariant the design doc said would be preserved

**Failure message:**
```
Design gate FAIL:
- PR exceeds 50 non-test production delta lines but lacks ## Design Decision section
OR
- Design doc [link] exists but diff violates its stated boundaries:
  * [specific violation]
Do not merge. Fix the design doc or the diff.
```

---

## Step 1: Regression Gate

After design gate passes, run these checks before touching 7-green.

### 1a. Non-regression check
Does this PR undo or weaken a previously merged architectural gate (e.g., `design-doc-gate.yml`)? Check `design-doc-gate.yml` for current grep gates and verify the diff does not violate them.

### 1b. Evidence quality check
If the PR has a `## Evidence` section in the description:
- Reject fabricated/placeholder patterns (`simulated`, `example.com`, `<screenshot path>`, `TODO`, `TBD`)
- Require real URLs, terminal output, or structured test output
- If evidence section is empty or contains fabrication → FAIL

### 1c. Architectural drift check
If the PR modifies `$PROJECT_ROOT/world_logic.py`, `$PROJECT_ROOT/agents.py`, or `$PROJECT_ROOT/rewards_engine.py`:
- Verify changes respect the file-responsibility table in `zfc-leveling-roadmap/SKILL.md` (or the relevant domain skill)
- Flag any change that adds logic to a "MUST NOT DO" column
- Flag any change that creates a second canonicalization path

---

## Step 1.5: API Pre-flight (MANDATORY — run TWICE: before any gate check AND after Skeptic Gate)

**RECURRING FAILURE (3x in 30 days):** False 7-green declarations on PRs with CONFLICTING merge state and no CR APPROVAL. This pre-flight prevents both.

```bash
gh pr view <PR> --json headRefOid,mergeable,reviewDecision | python3 -m json.tool
```

| Field | Required value | If wrong → |
|-------|---------------|-----------|
| `mergeable` | `true` | STOP: branch needs rebase. Gate 2 FAIL. Do not proceed. |
| `reviewDecision` | `APPROVED` | STOP: CR has not approved (unless CodeRabbit check is success). Gate 3 FAIL. Do not proceed. |

Also: find the latest Skeptic VERDICT comment on the PR and confirm its SHA matches `headRefOid`.  
If SHA differs → stale verdict → Gate 7 unverified. Do not cite it.

**⚠️ MUST RUN TWICE (3rd failure was here):**
1. **Before starting gate checks** — initial pre-flight
2. **AFTER Skeptic Gate completes, immediately before verbal report** — Skeptic Gate Gate-2 (mergeable check) runs at the START of its ~8-min eligibility run. A concurrent merge can make the PR CONFLICTING after Gate-2 passes. "Skeptic PASS" does NOT mean skip this check.

This check takes 3 seconds. Skip it and you will produce false 7-green claims.

---

## Step 2: 7-Green Checks

Only run these AFTER Steps 0, 1, and 1.5 all pass.

| # | Gate | Command / Check |
|---|------|----------------|
| 1 | CI green | All core check runs pass (`Staging Canary Gate`, `find-openclaw-json`, `Full canary (6/6)`) |
| 2 | No conflicts | `mergeable=true`, `merge_state=CLEAN` (verified in Step 1.5) |
| 3 | CR APPROVED | `reviewDecision=APPROVED` or CodeRabbit check is success |
| 4 | Bugbot clean | `cursor[bot]` check-run conclusion is not `failure` |
| 5 | Comments resolved | Zero unresolved non-nit inline review comments |
| 6 | Evidence pass | Evidence review verdict is `PASS`, OR `evidence-gate.yml` CI passed |
| 7 | Skeptic PASS | `github-actions[bot]` posted `VERDICT: PASS` on the PR — SHA must match `headRefOid` |

For detailed command syntax for each gate, see `7green.md` in `~/.hermes/procedures/` or run `gh pr checks --repo <owner/repo> <pr>`.

---

## Stop Conditions

**STOP and do not proceed to 7-green when:**
- Design Decision section is missing or linked artifact does not exist
- Diff violates stated design boundaries
- Evidence section contains fabrication
- A grep gate in `design-doc-gate.yml` would fail

**STOP and escalate (do not keep iterating) when:**
- You have made 3+ commits attempting to fix the same failing check
- You are uncertain whether the fix creates a new architectural violation
- The PR description's design doc says X but the code does Y and you cannot reconcile them

Escalation is a success, not a failure. Report what you found, what you're uncertain about, and what decision is needed.

---

## Related

- `.claude/skills/zfc-leveling-roadmap/SKILL.md` — file-responsibility table for level-up/XP work
- `.claude/skills/field-ownership-contracts.md` — field writer registry for shared dicts
- `design-doc-gate.yml` — automated grep gates for architectural boundaries
- `skeptic-cron.yml` — LLM-based skeptic gate (condition 7)
