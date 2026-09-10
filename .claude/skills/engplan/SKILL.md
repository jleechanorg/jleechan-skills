---
name: engplan
description: Plan medium-to-large engineering work across staged PRs with file ownership, dependencies, tracking, and proportional evidence.
type: planning
---

# /engplan — Generic Engineering Plan Skill

A reusable planning template for medium-to-large engineering work that produces:
- Coherent PR boundaries suited to dependencies, risk, and the delivery goal
- Explicit file ownership and coordination for overlapping work
- TDD with `/tdd` (red → green → refactor) and `/4layer` minimal-repro ladder
- Fresh failing evidence before behavior fixes, with reviewable commits
- Commit/PR sizes suited to the change and any explicit user-requested limits
- Beads (`br`) and memory entries linking the plan to existing tracking
- Cross-references to all existing roadmap docs in scope

This skill is project-agnostic. The ZFC leveling plan
(`~/roadmap/nextsteps-2026-04-28-zfc-stage-pr-hybrid-plan.md`) is a historical
example; the current task and repository owners govern the plan.

---

## When to use /engplan

- Multi-week effort with several files in flight
- Work currently fragmented across many small open PRs (>5 in same scope)
- Bug-class or milestone work where >2 PRs have touched the same file
- Cleanup/deletion milestone needing net-LOC discipline
- Greenfield feature where stage boundaries are obvious

Do NOT use for:
- Single-line fix or one-file change (use direct PR)
- Pure refactor with no behavior change (use `/refactor` if exists)
- Spec exploration without a target (use `/research` first)

---

## Output Artifact

Always produces `~/roadmap/nextsteps-<YYYY-MM-DD>-<scope>-stage-pr-plan.md`
synced to `<repo>/roadmap/nextsteps-<YYYY-MM-DD>-<scope>-stage-pr-plan.md`.

The doc has these sections in order:
1. **Goal** — one paragraph
2. **Why** — bullet list of audit findings, prior failures, file-contention evidence
3. **File-Exclusive Ownership Map** — table: PR → owns/may-read/closes
4. **Per-PR Commit Plan** — coherent changes, files, and accepted commit boundaries; estimate LOC only when useful
5. **Sequencing** — DAG of PRs (which run parallel, which block)
6. **Open-PR Handling** — what to do with existing open PRs
7. **Concurrency Rule** — codified `gh pr list` query
8. **Size Constraints** — explicit limits from the current request or accepted plan, if any
9. **Beads** — existing + new bead IDs per PR
10. **Memory Entries** — what memory files this plan reads/updates
11. **TDD Plan** — fresh failure and verification for behavior fixes
12. **/4layer Coverage** — sufficient layers selected by the repository's testing owner
13. **Cross-References** — all related roadmap docs (active, predecessor, foundational, skills)
14. **Sync Requirement** — paths to copy doc to

---

## Core Rules

### Rule 1: File-exclusive ownership
Assign file ownership and inspect overlapping changes before editing. Coordinate
shared files or sequence dependent patches; do not overwrite another worker's
changes. An open PR touching a file does not by itself block independent work.

Before opening any new PR in the scope:
```bash
TARGET_FILES=()

(
  set -euo pipefail
  if [ ${#TARGET_FILES[@]} -eq 0 ] || [[ "${TARGET_FILES[*]}" =~ \<.*\> ]]; then
    echo "Error: TARGET_FILES must be set to actual file paths before running concurrency check" >&2
    exit 1
  fi
  for f in "${TARGET_FILES[@]}"; do
    if [[ "$f" =~ ^path/to/ ]]; then
      echo "Error: TARGET_FILES contains placeholder path '$f'; supply actual planned paths" >&2
      exit 1
    fi
  done

  LIMIT=300
  if ! PR_DATA=$(gh pr list --state open --limit "$LIMIT" --json number,files); then
    echo "Error: Failed to query open PRs from GitHub API" >&2
    exit 1
  fi

  if ! PR_COUNT=$(echo "$PR_DATA" | jq 'length' 2>/dev/null); then
    echo "Error: Failed to parse PR data with jq" >&2
    exit 1
  fi

  if [ "$PR_COUNT" -ge "$LIMIT" ]; then
    echo "Notice: Open PR query reached limit ($LIMIT); inspecting bounded sample, older open PRs not checked." >&2
  fi

  if ! MATCHING_PRS=$(echo "$PR_DATA" | jq -r --args '
    $ARGS.positional as $targets |
    [ .[] | select(any(.files[]?.path; . as $p | $targets | index($p))) | .number ] | unique | .[]
  ' "${TARGET_FILES[@]}" 2>/dev/null); then
    echo "Error: Failed to extract matching PRs with jq" >&2
    exit 1
  fi

  if [ -n "$MATCHING_PRS" ]; then
    echo "Overlapping open PRs found:"
    echo "$MATCHING_PRS"
  else
    if [ "$PR_COUNT" -ge "$LIMIT" ]; then
      echo "No overlapping PRs found within bounded sample of $LIMIT open PRs (older open PRs not checked)."
    else
      echo "No overlapping open PRs found across $PR_COUNT open PRs checked."
    fi
  fi
)
```
If non-empty, inspect actual overlap and coordinate the affected files. Continue independent authorized work.

### Rule 2: Preserve test/fix sequence

Capture fresh failure evidence before a behavior fix, then implement the smallest
change that resolves it. Separate red/green commits when the user or accepted plan
requires them; otherwise a verified commit may contain both test and fix with the
actual RED/GREEN sequence recorded in evidence.

### Rule 3: Commit size

Keep commits coherent and reviewable. Honor explicit size limits in the current
user request or accepted plan; do not impose a 100-line minimum, pad a small fix,
or remove needed behavior to meet an inherited line-count target.

### Rule 4: PR size

Choose commit and PR boundaries from dependencies, risk, and the delivery goal.
A small coherent fix may be one commit. Preserve explicit user-requested staging
or count limits, but do not invent a minimum number of commits or PRs.

### Rule 5: /4layer test coverage per stage-PR
Select sufficient checks using the repository's testing and evidence owners.
Tests may share a coherent implementation commit; separate test commits are not
required by this skill. The layer examples are:
- **Layer 1**: Unit tests (`$PROJECT_ROOT/tests/test_*.py`)
- **Layer 2**: End-to-end (`$PROJECT_ROOT/tests/test_end2end/`)
- **Layer 3**: MCP/HTTP real-mode (`testing_mcp/`)
- **Layer 4**: Browser (`testing_ui/`)

Choose layer by what the PR changes:
- Pure logic → Layer 1
- Cross-module orchestration → Layer 2
- API contract → Layer 3
- User-visible behavior → Layer 4

### Rule 6: Beads tracking
- Every PR has ≥1 governing bead (`rev-xxxxx`)
- Every commit message references at least one bead
- New beads created BEFORE PR work starts (not retroactively)

### Rule 7: Memory linkage
Plan reads:
- `~/.claude/projects/<project>/memory/MEMORY.md` for prior context
- Recent feedback and project memory entries in scope

Plan writes:
- New project memory entry summarizing the stage-PR plan
- Update memory when each stage-PR merges

---

## Execution Workflow

### Phase 0: Discovery (read-only)
1. Identify scope keyword (e.g., "auth", "checkout", "level-up").
2. List existing roadmap docs in scope: `ls ~/roadmap/ | grep -i <scope>`.
3. List existing repo roadmap docs: `ls <repo>/roadmap/ | grep -i <scope>`.
4. List open PRs in scope: `gh pr list --state open --search "<scope> in:title"`.
5. List active beads in scope: `br list | grep <scope>` (or equivalent).
6. Check MEMORY.md for relevant entries: `grep -l <scope> ~/.claude/projects/.../memory/*.md`.

### Phase 1: File ownership audit
1. For each open PR, list modified files: `gh pr view <N> --json files`.
2. Build conflict matrix: which files are touched by multiple PRs?
3. Inspect files touched by multiple PRs and assign coordination or sequencing for actual conflicts.

### Phase 2: Stage decomposition
1. Group target work into the smallest coherent set of stage-PRs that fits the accepted plan.
2. Assign each file to exactly one stage-PR.
3. Verify no file is in two stage-PRs.
4. Choose sequencing: parallel-eligible vs serial-required.

### Phase 3: Per-PR commit plan
For each stage-PR, plan the activities needed for its scope. These are not a
required number of commits; combine or omit optional activities as appropriate:
1. **Tracking and documentation** — link governing tracking and update the roadmap as required by the repository
2. **RED check** — failing tests for target behavior; commit separately when required
3. **Verified implementation commit** — minimum code and relevant tests to pass
4. **Optional layer-2/3/4 test commit** — broader coverage if Layer 1 isn't enough
5. **Optional refactor commit** — cleanup, no behavior change
6. **Evidence record** — link the evidence at the authorized destination using the canonical evidence-standards owner; a separate commit or external publication is not inherently required

Use existing task authorization for the selected evidence destination. An external
publication needs applicable authorization, but an already authorized destination
does not create another confirmation checkpoint.

Inspect `git diff --cached --stat` for reviewability and any explicitly agreed size limit.

### Phase 4: Doc generation
Write the artifact at `~/roadmap/nextsteps-<date>-<scope>-stage-pr-plan.md`.
Include all 14 sections above. Cross-reference every roadmap doc found in Phase 0.

### Phase 5: Sync
Copy doc to `<repo>/roadmap/` and any active worktrees.

### Phase 6: Memory write
Add entry to `~/.claude/projects/<project>/memory/` describing the plan and add a one-line pointer to `MEMORY.md`.

---

## Anti-Patterns to Avoid

- **PR proliferation**: opening a new PR for each small fix when an existing PR in scope could absorb it
- **File contention**: two PRs editing the same file simultaneously → rebase churn, stale CR
- **Missing RED proof**: a combined test/fix commit still needs evidence that the check failed before the behavior fix
- **Unreviewable changes**: split incoherent changes by dependency or risk; a line count alone is not a split requirement
- **Bead-after-the-fact**: creating a bead AFTER the PR opens — defeats tracking
- **Roadmap-drift**: writing a plan but never syncing the repo copy
- **Generic plans**: "fix bugs", "improve performance" — must have concrete file ownership

---

## Template Sections (copy into each plan)

### Goal (template)
> Close out <scope> work with N stage-PRs sequenced so no two open PRs modify
> the same file at the same time. Existing M small open PRs remain open but
> are handled later — they do not gate this plan.

### File-Exclusive Ownership Map (template)
| Stage-PR | Owns (exclusive) | May read | Closes |
|---|---|---|---|
| **PR-A: <name>** | `path/a.py`, `path/b.py` | `path/c.py` | <bug class / bead> |
| **PR-B: <name>** | `path/d.py` | `path/a.py` (read) | <bug class / bead> |
| **PR-C: Evidence** | `tests/test_*.py` | none modify | Gate-6 evidence |

### Per-PR Commit Plan (template)
Illustrative activities, not a commit or line-count quota. Select the rows and
boundaries required by the accepted plan; one coherent commit may be sufficient.

**PR-A: <name>**

| # | Type | Files | Size estimate, if useful | Bead | Description |
|---|---|---|---|---|---|
| 1 | tracking/docs, if needed | `roadmap/...md` | <estimate or n/a> | <tracking> | Link governing work |
| 2 | test and implementation | <test and source paths> | <estimate or n/a> | <tracking> | Capture required RED before the fix and verify GREEN |
| 3 | broader evidence, if needed | <scoped driver or artifact> | <estimate or n/a> | <tracking> | Record results at the authorized destination |

### Concurrency Rule (template)
Execute the concurrency check defined in [Rule 1: File-exclusive ownership](#rule-1-file-exclusive-ownership) for the files planned in this stage before opening a PR:
- Supply the planned file paths in `TARGET_FILES`
- If an overlapping open PR is returned, inspect actual overlap and coordinate affected work
- Bounded query inspects open PRs up to the limit; older open PRs or large file lists may require checking individual PR diffs
- Continue independent authorized tasks; open PRs touching a file do not inherently gate unrelated work


### Size Constraints (template)
- Explicit user or accepted-plan constraint: <limit and source, or none>
- Expected diff size, if useful: <estimate, not a quota>
- Review boundary: <dependency or risk that justifies splitting, if any>

### Cross-References (template)
- Active/governing: `<paths>`
- Predecessor next-steps: `<paths>`
- Foundational design: `<paths>`
- Implementation history: `<paths>`
- Skill / harness: `<paths>`

---

## See Also
- `.claude/skills/zfc-leveling-roadmap/SKILL.md` — domain-specific instance
- `.claude/skills/deletion-milestone.md` — net-LOC discipline for deletion PRs
- `.claude/skills/repro-twin-clone-evidence/SKILL.md` — evidence capture
- `.claude/commands/4layer.md` — minimal-repro ladder
- `.claude/commands/tdd.md` — red/green/refactor with matrix testing
- `~/roadmap/nextsteps-2026-04-28-zfc-stage-pr-hybrid-plan.md` — historical example
