---
name: engplan
description: Generic engineering plan skill — produces a stage-PR plan with file-exclusive ownership, beads, memories, TDD, /4layer, /tdd, separate test/code commits, and 100-300 LOC commit caps. Modeled on the ZFC leveling hybrid plan but generic for any feature/cleanup/bug-fix work.
type: planning
---

# /engplan — Generic Engineering Plan Skill

A reusable planning template for medium-to-large engineering work that produces:
- A small number of larger PRs (NOT many small PRs)
- File-exclusive ownership (no two open PRs touch the same file)
- TDD with `/tdd` (red → green → refactor) and `/4layer` minimal-repro ladder
- Separate commits for tests and code (test commits land BEFORE code commits)
- Per-commit delta cap: 100-300 LOC; PRs composed of 3-8 commits
- Beads (`br`) and memory entries linking the plan to existing tracking
- Cross-references to all existing roadmap docs in scope

This skill is project-agnostic. The ZFC leveling plan
(`~/roadmap/nextsteps-2026-04-28-zfc-stage-pr-hybrid-plan.md`) is the canonical
example.

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
4. **Per-PR Commit Plan** — table per PR: commit N → test/code → files → LOC delta
5. **Sequencing** — DAG of PRs (which run parallel, which block)
6. **Open-PR Handling** — what to do with existing open PRs
7. **Concurrency Rule** — codified `gh pr list` query
8. **Net LOC Targets** — per-PR caps
9. **Beads** — existing + new bead IDs per PR
10. **Memory Entries** — what memory files this plan reads/updates
11. **TDD Plan** — red/green/refactor mapping per commit
12. **/4layer Coverage** — which layer each test commit targets
13. **Cross-References** — all related roadmap docs (active, predecessor, foundational, skills)
14. **Sync Requirement** — paths to copy doc to

---

## Core Rules

### Rule 1: File-exclusive ownership
Each PR owns a set of files. **No other open or planned PR may modify a claimed file** until the owning PR merges or releases the claim.

Before opening any new PR in the scope:
```bash
gh pr list --state open --json number,files --jq \
  '.[] | select(.files[].path | IN("FILE_LIST")) | .number'
```
If non-empty → stop, coordinate or wait.

### Rule 2: Separate commits for tests and code
- **Test commit FIRST** (red): adds failing tests asserting target behavior
- **Code commit NEXT** (green): minimum code to make tests pass
- **Optional refactor commit**: cleanup, no behavior change

This is `/tdd` discipline at the commit level — verifiable in `git log`.

### Rule 3: Per-commit LOC cap
- **100 LOC minimum** (forces meaningful chunks, not nit-fixes)
- **300 LOC maximum** (forces decomposition, keeps review tractable)
- Generated files (lockfiles, fixtures, snapshots) excluded from cap
- Pure deletion commits exempt from minimum (deletion is good)

Check before committing:
```bash
git diff --cached --stat | tail -1
# Look for "N insertions(+), M deletions(-)" — N+M should be 100-300
```

### Rule 4: PRs composed of 3-8 commits
- <3 commits → likely too small, fold into another PR
- >8 commits → likely too big, split into stage-PRs

### Rule 5: /4layer test coverage per stage-PR
Every stage-PR must include test commits at the right layer:
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
3. Identify hot files (touched by >2 open PRs) — these MUST be claimed by exactly one stage-PR going forward.

### Phase 2: Stage decomposition
1. Group target work into 2-5 stage-PRs.
2. Assign each file to exactly one stage-PR.
3. Verify no file is in two stage-PRs.
4. Choose sequencing: parallel-eligible vs serial-required.

### Phase 3: Per-PR commit plan
For each stage-PR, plan commits in this order:
1. **Bead-doc commit** (10-30 LOC) — create governing bead, update roadmap if needed
2. **Test commit (red)** (100-300 LOC) — failing tests for target behavior
3. **Code commit (green)** (100-300 LOC) — minimum code to pass
4. **Optional layer-2/3/4 test commit** — broader coverage if Layer 1 isn't enough
5. **Optional refactor commit** — cleanup, no behavior change
6. **Evidence commit** (any size) — evidence bundle path, gist URL in PR body

Verify per-commit cap with `git diff --cached --stat | tail -1`.

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
- **Mixed commits**: tests + code in same commit → can't verify TDD discipline from git log
- **Silent commit-bloat**: commit with 1000+ LOC delta — usually means PR should be split
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
**PR-A: <name>**
| # | Type | Files | LOC | Bead | Description |
|---|---|---|---|---|---|
| 1 | bead-doc | `roadmap/...md` | 30 | rev-xxxxx | Add governing bead |
| 2 | test (red) | `tests/test_a.py` | 200 | rev-xxxxx | Failing tests for X |
| 3 | code (green) | `src/a.py` | 250 | rev-xxxxx | Minimum impl to pass |
| 4 | test (Layer 3) | `testing_mcp/test_a_real.py` | 150 | rev-xxxxx | Real-mode coverage |
| 5 | refactor | `src/a.py` | 100 | rev-xxxxx | Cleanup, no behavior change |
| 6 | evidence | PR body | n/a | rev-xxxxx | Gist URL + bundle path |

### Concurrency Rule (template — paste verbatim)
```bash
gh pr list --state open --json number,files --jq \
  '.[] | select(.files[].path | IN("<FILE_LIST>")) | .number'
```
If any PR is returned → stop, coordinate or wait.

### Net LOC Targets (template)
- PR-A: net ≤ 0 (deletion) | net ≤ +<N> (feature)
- PR-B: net ≤ +<N>
- PR-C: tests only — production code untouched

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
- `~/roadmap/nextsteps-2026-04-28-zfc-stage-pr-hybrid-plan.md` — canonical example
