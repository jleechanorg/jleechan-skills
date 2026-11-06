---
name: human-review-brief
description: Standardized end-of-turn human review brief (## What Was Done and ## What to Review as a Human) grounded in empirical Mac and Linux agent blind spots. Enforces the LLM-verifiability gate (If the LLM Can Verify It, Do It Yourself) and requires a specific reason why the LLM cannot execute the next step now on every human review item.
---

# Human Review Brief (`human-review-brief` / `/what-to-review`)

## Core Gate: "If the LLM Can Verify It, Do It Yourself (Never Put It in `What to Review as a Human`)"

Before placing ANY bullet into `## What to Review as a Human`, ask:
> *"Can an LLM, unit test, headless browser, DOM measurement (`getBoundingClientRect` / `getComputedStyle`), `gh` CLI check, `git merge-tree`, `grep`, `shasum` / `SHA-256` check, or cross-model review (`advice`) verify this autonomously?"*

- **If YES -> DO IT NOW yourself** and record the verified proof under `## What Was Done`.
- **NEVER ask the human to confirm LLM-verifiable facts**, including:
  - `grep` / token counts (e.g., *"Confirm `scan.py` has 0 occurrences of `re.compile`"*),
  - `SHA-256` digest matches across hosts or files,
  - line-count (`LOC`) deltas or file counts,
  - unit/integration test pass rates or CI check statuses,
  - deterministic code or schema invariants that a test can assert.
- **Mandatory sub-bullet (`Why the LLM cannot do this:`)**:
  Every item listed under `## What to Review as a Human` MUST include an explicit sub-bullet:
  - `Why the LLM cannot do this: <specific current boundary, evidence, attempts, and resumption trigger>`
- **Qualify every inability claim.** Do not claim that an action is impossible for an LLM in general. Name the exact next action, why this runtime cannot do it now, the controlling policy or capability owner, supported alternatives attempted and their results, and what would let work resume. One failed call, unavailable preferred provider, missing local dependency, or untested alternative does not establish inability.
- **Valid human-only boundaries**:
  1. **Authority / permission**: A specific user-only action remains unauthorized under its current owner. Check the live request and applicable standing approval first; identify the exact missing authorization and do not ask again when it is already present.
  2. **Verified physical capability**: The next step requires physical access or an external session that the available authorized tools cannot provide. Name the device or capability and the supported alternatives attempted; existing credentials and sessions may be used.
  3. **Irreducible human decision**: The user must supply a preference or intent that cannot be inferred safely from the request or repository evidence. Choose a reversible default for ordinary implementation tradeoffs; ask only for an essential unresolved decision.
- **Do the available work first.** Before reporting a human-only item, complete every safe, authorized, reversible check, review, and follow-through action the current runtime can perform. Missing evidence or an untried tool is a blocker to investigate, not by itself a human decision.
- **Zero-Item Escape Hatch**:
  When all verification was completed autonomously by the LLM and no subjective product/UX tradeoff remains, `## What to Review as a Human` MUST state:
  > `None — all authorized work and checks are complete; no human decision is required.` If a merge is actually in scope and still gated, name that exact approval separately.

---

## When to Apply
- **Full Brief (`## What Was Done` + `## What to Review as a Human`)**: Required when finishing a PR update, code/evidence review, multi-step feature implementation, or merge-readiness report, and inside `/pr-summary` breakdowns.
- **Compact Inline Form**: On small local coding turns that do not update a PR or claim merge readiness, emit a 2–3 bullet inline summary of what changed, what was verified autonomously, and any remaining human-only decision (with `Why the LLM cannot do this:`). Skip on trivial Q&A or read-only lookups.

---

## Section 1: `## What Was Done` (Objective Facts & Autonomous Verification Proof)

Provide a scannable 4-bullet summary of verified facts (including all checks the LLM ran itself instead of offloading to the human):
1. **Outcome & Full Links**: 1–2 sentences stating what actually changed, with full clickable GitHub PR (`https://github.com/<owner>/<repo>/pull/<N>`) and 40-char commit URLs (`https://github.com/<owner>/<repo>/commit/<40-char-sha>`).
2. **Production vs. Non-Production LOC Delta (`/ponytail` Check)**:
   - Format: `Production: +X / -Y (M files) | Non-production: +A / -B (N files) | Total: +(X+A) / -(Y+B)`
   - Explicitly flag if net production lines grew (`+X > -Y`) on a fix where simplification or deletion (`/ponytail`) was expected.
3. **Merge-Tree Cleanliness & Silent-Revert Check vs. `origin/main`**:
   - Do not rely on GitHub `mergeable: MERGEABLE` alone (which misses silent reverts of `origin/main` and smuggled formatter churn). Run:
     ```bash
     git fetch origin main
     TREE=$(git merge-tree --write-tree origin/main HEAD)
     comm -23 <(git diff --name-only origin/main "$TREE" | sort) <(git diff --name-only origin/main...HEAD | sort)
     ```
   - Confirm zero conflict markers, zero files reverted relative to `origin/main`, and zero smuggled multi-file formatter edits.
4. **SHA-Bound Gate & Evidence Matrix (`@ <short-sha>`)**:
   - State the exact status and attested SHA for CI / local equivalents (`/green`), `/es`, `/er`, independent review (`advice`), `/cs`, `/wa`, and cross-host `SHA-256` sync verification. Never claim a prior-SHA receipt covers a new head without explicit delta-based applicability analysis.

---

## Section 2: `## What to Review as a Human` (Human-Only Judgment & Blind-Spot Checklist)

First run the **Core Gate** above: execute every check the LLM can perform itself and move those results into `## What Was Done`. Then, if a genuine human decision remains across the 10 empirical Mac + Linux categories below, emit only those items — each with `Why the LLM cannot do this:` — or emit the **Zero-Item Escape Hatch**, followed by the two mandatory closing bullets (`What Current Evidence Does NOT Prove` and `Exact Human Decision Needed`). Missing evidence is not itself a human decision; attempt available authorized checks before escalating.

### The 10 Empirical Mac + Linux Blind-Spot Categories (Verify Autonomously First; Surface Only What the LLM Cannot Decide/Prove)

1. **`Visual / UX / Hidden-State Verification`** *(when UI, CSS, templates, or mobile views change)*:
   - First measure DOM geometry (`getBoundingClientRect` / `getComputedStyle`) and check for `display: none` parents, modal locks, or HUD overlap yourself across `1440x900`, `700–1024px`, and `375x812`.
   - Surface to the human only subjective visual aesthetics/feel with linked before/after frames and video timestamps, plus `Why the LLM cannot do this: Irreducible human decision — automated DOM geometry passes; only the human can judge visual polish and layout feel.`
2. **`Main-Merge Smuggling, Stale Base Diffs & Silent Reverts`** *(when rebasing, resolving conflicts, or merging `origin/main`)*:
   - Run `git merge-tree --write-tree` yourself; surface to the human only when a conflict resolution required an essential business-logic decision between competing intents, with `Why the LLM cannot do this: Irreducible human decision — ...`
3. **`Partial, Stale-SHA, or Substitute-Provider Gates`** *(when reporting `/ready` or gate status)*:
   - Continue with available authorized routes and preserve any unavailable or fallback result as an evidence limitation. Surface it to the human only when an exact user-only decision or capability is needed to proceed; explain the actual boundary and attempted alternatives with `Why the LLM cannot do this: ...`
4. **`Product Constants, Cooldowns & Prompt Compression`** *(when prompts, docstrings, configs, or gameplay/business constants change)*:
   - Verify line counts and tests yourself; surface to the human only when the request leaves an essential product tuning choice unresolved, with `Why the LLM cannot do this: Irreducible human decision — ...`. Choose a reversible default for ordinary engineering tradeoffs.
5. **`Zero-Framework Cognition (ZFC) & Scope-Blind Backend Guards`** *(when backend state, reducers, clamps, sanitizers, or security/migration paths change)*:
   - Write unit tests for deterministic guards and zero-regex compliance yourself; surface a destructive migration only when it is actually in scope and requires user authority; surface architecture only when an essential choice cannot be resolved from the contract, with `Why the LLM cannot do this: ...`
6. **`Cross-PR Stack & Shared Token/Budget Ratchets`** *(when working on stacked PRs or shared system prompts)*:
   - Check `baseRefName` and token ratchets yourself; resolve ordering using existing project policy, surfacing only a genuine unresolved cross-feature decision with `Why the LLM cannot do this: ...`
7. **`Provider-Boundary & Structured-Output Schema Complexity`** *(when JSON schemas, tool definitions, or model catalogs change)*:
   - Live-probe `response_json_schema` against the real provider using available credentials; if that route fails, try supported alternatives and record the limit. An unreachable endpoint is an evidence gap, not automatically a human decision; surface only a specific user-only prerequisite with `Why the LLM cannot do this: ...`
8. **`Cross-Host (macOS vs Linux) & Viewport Parity`** *(when shell scripts, Rust/Python tooling, skills, or hooks change)*:
   - Verify each available authorized host and `SHA-256` sync; surface an untested host as an evidence limitation and continue available checks. Ask for human action only when physical access is actually required, with `Why the LLM cannot do this: ...`
9. **`Linux Systemd / Cgroup Live State & Runner Side Effects`** *(when Linux services, runner fleets, or container limits change)*:
   - Query `systemctl show`, `/etc/systemd/system.control/`, `automation.slice/pids.current`, and PSI `memory.pressure` yourself; decide within approved capacity policy and surface a choice only if that policy leaves an essential user preference unresolved, with `Why the LLM cannot do this: ...`
10. **`Delivery vs Execution, Subprocess Stdin & Hook Hygiene`** *(when automation scripts, background jobs, or agent orchestration change)*:
   - Verify `< /dev/null` stdin closure, hook timeouts in `settings.json`, and `git clone --no-local` review worktree isolation yourself; resolve ordinary workflow implementation choices from current policy and surface only an essential decision it does not settle, with `Why the LLM cannot do this: ...`

### Mandatory Closing Bullets (Always Include in `## What to Review as a Human`)
- **`What Current Evidence Does NOT Prove`**: State what remains unexercised and the exact reason available authorized routes could not establish it; an evidence gap alone does not mean the human must act.
- **`Exact Human Decision Needed`**: State only a decision or user-only action that remains necessary in this task, with `Why the LLM cannot do this:` and the exact authority, capability, or unresolved-intent boundary. If none remains, say `None — no human decision is needed.` Ask for merge approval only when merging is in scope and all other gates have been completed.
