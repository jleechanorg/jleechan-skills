---
name: factory-evolve
description: Analyze conversation and git history to find gaps where cold reviews (codex, Bugbot, CodeRabbit, /reviewdeep) caught issues that dark-factory in-pipeline reviewer nodes missed. Fans out subagents, opens PRs, drives each through /green, and merges (with explicit MERGE APPROVED). Proposes targeted .dot and runner improvements ranked by G1–G9 gap taxonomy.
---

# /factory-evolve Skill (v2 — end-to-end operational)

Compares what dark-factory in-pipeline reviewer nodes actually caught against what cold reviewers (codex, Bugbot, CodeRabbit, manual `/reviewdeep`) caught on the same work. **Fans out subagents to gather context, opens one PR per ranked proposal, drives each through `/green`, and merges (after explicit "MERGE APPROVED").**

## When to invoke

- Automatically from `/integrate` (post-branch cleanup pass)
- Manually after a dark-factory pipeline run to check if reviewer nodes were adequate
- With `--pr N` to audit a specific PR's cold review vs factory wiring
- With `--days N` to widen the lookback (default 7)
- With `--taxonomy` to skip history; just check current .dot files for G1+G2 violations

## Inputs

```
/factory-evolve                     # scan last 7 days, open + drive PRs to /green + merge
/factory-evolve --days 14           # widen lookback window
/factory-evolve --pr 26             # audit one PR (cold review vs factory wiring)
/factory-evolve --taxonomy          # structural G1+G2 audit only (no history, no PRs)
/factory-evolve --no-pr             # write proposals doc only; don't open PRs
```

## Execution steps (end-to-end)

### Phase 0 — Locate the dark-factory repo root

```bash
FACTORY_HOME="${DARK_FACTORY_HOME:-$(git rev-parse --show-toplevel 2>/dev/null)}"
```

### Phase 1 — History search via `/history` (NEVER hand-coded `rg`)

**Use `/history <query> --recent <N>`** as the primary history search. The `/history` skill fans out across 6 sources in parallel (Claude Code JSONL, Codex SQLite, Hermes FTS5, Antigravity Markdown, OpenCode session diff, Cursor prompt history) — and unlike hand-coded `rg`, it catches `nohup`, `tee`, and multiline invocations.

```
/history "dark-factory --pipeline OR gate_er OR holdout_eval OR review_pr.dot OR graph_audit" --recent 1
/history "factory run cold review cold-review caught missed" --recent 1
```

**Why `/history`, not `rg`:** The 2026-06-22 /fe --days 1 run returned 0 factory invocations using a literal `rg --max-filesize 5M -l 'dark-factory --pipeline|...' ~/.claude/projects/` — the pattern missed `nohup dark-factory ... &`, `echo CMD: dark-factory | tee /tmp/log`, and multiline `dark-factory \\\n --pipeline` invocations. /history's multi-source walker surfaces all three styles. **This rule is durable: do not hand-code `rg` for history search.**

**Fallback only when /history is unavailable** (e.g., running outside Claude Code): use the Python multi-source walker documented in `docs/factory-evolve-research/proposals-2026-06-22.md` Evidence section. Code-comment the three missed patterns so future readers don't revert.

**Verification gate (mandatory):** after the search, ask: *does the count match the user's expectation?* If the user said "the last 24 hours of factory runs" and the search returns 0, **do not declare 'no runs found'** — say "I found 0, but I may be missing patterns; want me to broaden the search?" before writing the proposals doc.

### Phase 2 — Subagent fan-out (parallel context gathering)

For each factory-run + cold-review pair surfaced by Phase 1, **fan out subagents in parallel** to gather:

1. **Cold review findings** — what did codex/Bugbot/CodeRabbit/`/reviewdeep` catch that the factory's in-pipeline reviewer missed?
2. **Adjacent code patterns** — what existing modules/handlers look like the proposed fix? (mirrors PR-quantity-control file-overlap discipline)
3. **Risk callouts** — false positives, regression surface, blast radius.

**Subagent type**: `general-purpose` (default) or `Explore` (read-only). **Bounded scope**: one proposal per agent. Each agent returns structured findings (file paths, line counts, effort estimates, risks).

**File-overlap pre-check** (per `~/.claude/CLAUDE.md` "Parallel subagents"): before fanning out, enumerate the EXACT files each agent will touch. If two agents share a mutable file, sequence them (don't parallelize).

**CRITICAL — CWD-aware recovery** (per proposal P-D, 2026-06-22): Before declaring a location "empty" or "checked," `cd` into it explicitly. `git status` in the wrong worktree is not a check. The parent agent's CWD may not match the candidate location's directory. When investigating "lost" work, always:
1. `cd <candidate-location>` first
2. `git status --porcelain` (in the candidate, not parent)
3. `git fsck --lost-found` (catches dangling commits the branch ref doesn't)
4. `git stash list` (work might be stashed not lost)
5. Cross-grep the candidate for keywords — don't trust parent CWD

**Worker template** (one agent per proposal):

```
You are gathering context for proposal P[N]: <one-sentence description>.

The cold-review catch: <PR #X, finding, gap category G[N]>.

Investigate (read-only):
1. Find <prompt file / handler / hook pattern> ...
2. Find <existing precedent / test pattern> ...
3. Find <slim graph opt-in scope> ...
4. Find <test file to mirror> ...

Output format:
- File paths + line counts
- Template substitution mechanism / attribute threading / hook file location
- Existing patterns to mirror
- Test pattern
- Effort estimate (lines of code, files touched, risk)
```

**Why fan-out**: the 2026-06-22 /fe --days 1 → /harness block used 4 parallel agents (P1 lint greps, P2 verdict mapping, P4 pre-push hook, /harness 5-Whys) and surfaced 9 ranked fixes in one session. Sequential exploration would have taken 4× longer and missed cross-cutting gaps.

### Phase 3 — Structural audit of current .dot files and prompts (G1–G5)

As of PR #85 and PR #99, the structural audit runs both G1+G2 graph checks and G3+G4+G5 prompt-substitution contract checks. Run both from the dark-factory repo root:

```bash
cd "$FACTORY_HOME"
python -m runner.graph_audit pipelines
python -m runner.prompt_substitution_audit prompts pipelines runner
```

- **Graph audit (G1/G2):** Exit 0 = clean; exit 1 = violations reported one per line (`G1 | <path> | <location> | <message>`).
- **Prompt audit (G3/G4/G5):** Exit 0 = clean; exit 1 = prompt wiring, file resolution, or minimum content/directive verb violations reported one per line (`A/B/C | <path> | <location> | <message>`).

These checks are wired into `.github/workflows/ci.yml` as blocking CI steps on every PR touching `pipelines/` or `prompts/`. CI runs on Python 3.13.

### Phase 4 — Aggregate proposals + write `docs/factory-evolve-research/proposals-YYYY-MM-DD.md`

Aggregate Phase 1 (history) + Phase 2 (subagent findings) + Phase 3 (structural) into one Markdown doc with this structure:

```markdown
# Factory-Evolve Proposals — YYYY-MM-DD

**Window:** last Nh (YYYY-MM-DD → YYYY-MM-DD UTC)
**Repo:** `jleechanorg/<repo>` at main `<sha>`
**Tool:** `/fe` — `<flags>`
**Search:** `/history` (multi-source) → <count> factory invocations, <count> cold-review catches

---

## Evidence (N cold-review incidents, M structural G1/G2 violations)

| Source | Count | In window | Notes |
|---|---|---|---|

## Gap-category breakdown

| Code | Hits | Notes |
|---|---|---|

## Proposals (ranked by impact × ease)

### [P1] <title>
- **Evidence**: <PR #s, cold reviewer, finding, G category>
- **Impact**: <medium-high / scope>
- **Ease**: <easy / scope>
- **Files**: <absolute paths>
- **Effort**: <lines of code + tests>
- **Acceptance**: <how to verify>
- **Bead**: <$USER-xxx link>

### [P2] ...
```

### Phase 5 — Open one PR per ranked proposal (UNLESS `--no-pr`)

**For each [P1], [P2], ... proposal that warrants a code change**:

1. **Create the bead first** (if not exists): `br create "<P[N] title>" --type task --priority <1|2|3>`.
2. **Open a worktree for the change**: `git worktree add ../worktree-<repo>-<P[N]>-<slug> -b <branch>`.
3. **Implement the change** in the worktree. **Mirror existing patterns** the subagent surfaced (e.g., the `${diff}` injection pattern from PR #85 for the `${lint_findings}` proposal).
4. **Write tests** (unit + count-pinning per the `~/.claude/CLAUDE.md` "Count-pinning tests" memory entry).
5. **Verify locally**: `.venv/bin/python -m pytest tests/` (full suite must be green).
6. **Push the branch**: `git push -u origin <branch>`. **Verify pre-push target matches intended PR branch** per the pre-push check rule.
7. **Open the PR**: `gh pr create --repo jleechanorg/<repo> --base main --head <branch>` with the canonical 6-section body (Background / Goals / Tenets / High-level description / Testing / Low-level details).

**Do not auto-merge.** Per `~/.claude/CLAUDE.md` "Merge safety" rule, the literal phrase "MERGE APPROVED" from the operator is the only valid merge trigger.

### Phase 6 — Complete draft readiness, then `/green`

Keep each opened PR draft while `/es`, `/er`, and `/advice` pass at the current
head per `~/.claude/skills/draft-first-pr/SKILL.md`. Then mark it ready and run
`/green <PR#>` using `~/.claude/skills/pr-green-definition/SKILL.md`.
CodeRabbit/Bugbot feedback is advisory. Re-fetch mergeability immediately before
every readiness claim because a concurrent base merge can introduce conflicts.

### Phase 7 — Merge (operator-gated)

When draft readiness and `/green` both pass:
2. **Summarize readiness** (CI green, CR approved, head SHA, evidence).
3. **STOP. Do not merge.** Per `~/.claude/CLAUDE.md` "Merge safety" rule, the literal "MERGE APPROVED" from the operator in the same turn is the only valid merge trigger. "Looks good" / "ship it" / "go ahead" are NOT merge authorization.
4. The operator types "MERGE APPROVED" → run `gh pr merge <PR> --squash` (default to squash per dark-factory convention).
5. **If the operator types an ambiguous approval** (e.g. "yes merge"), ask for the literal "MERGE APPROVED".

For force-push: per `~/.claude/CLAUDE.md` "Push safety" rule, never `git push --force` without explicit in-thread human approval naming target branch.

### Phase 8 — Report

Output:

- ✅ **Nextsteps doc**: `docs/factory-evolve-research/proposals-YYYY-MM-DD.md`
- ✅ **Beads created**: <$USER-xxx list with links>
- ✅ **PRs opened**: <PR #s with links + green-status>
- ✅ **PRs merged**: <PR #s merged in this session, with merge commit SHAs>
- ⏸ **PRs awaiting MERGE APPROVED**: <PR #s>
- ❌ **PRs blocked on /green**: <PR #s + reason>

## Gap taxonomy reference (G1–G9)

| Code | Name | Key files |
|------|------|-----------|
| G1 | reviewer-not-wired-in-graph | gates.dot, pr_gates.dot, minimal_research.dot |
| G2 | failed-review-routes-to-exit | review_pr.dot, bug_fix.dot, gates.dot |
| G3 | weak/templated reviewer prompt | handler_universal_prompts.py:111,146 |
| G4 | no-diff-injection | prompts/slim/review.md, prompts/catalog/review.md |
| G5 | scope-limited-to-diff-hunk | prompts/slim/review.md step 2 |
| G6 | verdict-parsing-swallows-nuance | handler_verdict.py:28-43, :135-138 |
| G7 | single-vendor-collapse | handler_dispatch.py:361, _execute_gate:423-425 |
| G8 | SHA-binding-not-freshness | handler_verdict.py:66-77 |
| G9 | unit-only/templated-evidence-accepted | prompts/slim/evidence_review.md |

## Output artifacts

- `docs/factory-evolve-research/proposals-YYYY-MM-DD.md` — ranked proposal list with bead links
- Beads via `br create` for each proposal that warrants a code change
- One PR per code-change proposal, driven through `/green`
- Memory entry at `~/.claude/projects/<project_key>/memory/project_<date>_factory_evolve_<slug>.md` if any new lessons
- On-screen summary: top 3 proposals + counts + PR/merge state

## Notes

- **History search**: ALWAYS use `/history` (or the Python multi-source walker fallback). Never hand-coded `rg`. The `~/.claude/CLAUDE.md` "History search" rule is durable.
- **Fan-out scope**: one proposal per subagent. Pre-check file overlap before parallelizing.
- **PR creation**: read the `~/.claude/CLAUDE.md` "PR description — required sections (canonical)" rule for the 6-section body.
- **/green**: `gh pr checks` alone is not sufficient. Use `/green <PR#>` and its canonical skill.
- **Merge**: NEVER auto-merge. "MERGE APPROVED" is the only valid trigger. The user drives which proposals to implement and merge; /factory-evolve proposes, the operator decides.
- **Source files for the gap taxonomy**: `docs/factory-evolve-research/reviewer-gap-taxonomy.md` (canonical) and `docs/factory-evolve-research/git-pr-forensics.md`. (Originally in `specs/factory-evolve-research/` but moved to `docs/` because the agent-facing boundary check in `benchmarks/scripts/check_boundary.py` flags `DARK_FACTORY_HOLDOUTS` references in `specs/`/`prompts/` as a leakage vector — `docs/` is operator-facing and exempt.)
- **Related skills**: `/history` (multi-source conversation search), `/green` (CI + conflict verification), `/es` and `/er` (evidence), `/advice` (second opinion), `/integrate` (auto-caller).

## Related

- `history-search` — primary history search tool used by Phase 1 of this skill
- `green` / `es` / `er` / `advice` — verification tools used by Phase 6
- `pr-quantity-control` — file-overlap discipline used by Phase 2 fan-out
- `merge-safety` — MERGE APPROVED gate used by Phase 7
