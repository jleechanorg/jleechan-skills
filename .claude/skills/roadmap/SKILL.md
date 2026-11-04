---
name: roadmap
description: Use when /roadmap is requested to survey, update, and coordinate roadmap work.
---

# Roadmap

## Contract

Run `/roadmap` by producing (or updating) ONE in-flight PR board document in the
roadmap repo, committing it, pushing it, and showing the URL. Anything else — surveys,
memory reads, nextsteps rotas — is supporting material, not the deliverable.

Survey (optional context gathering). When the board needs history, consult
whichever of these are available before writing: authorized project memory for prior
decisions, existing documents in the roadmap repository, and related open beads. Use
them so the board references earlier work instead of duplicating it. None of this is a
prerequisite — skipping it is valid, especially for a status-only board — and it never
changes the mandatory output format below.

Each source resolves from its own root, so scope the lookups deliberately:

- **Project memory** belongs to the project the board is about. Resolve it from that
  project's root, not from the roadmap repository.
- **Roadmap documents and beads** belong to the roadmap repository. `br` reads the
  beads store of the directory it runs in, so a board built from a code checkout would
  otherwise survey the wrong items:

```bash
ROADMAP_REPO="$(git -C "${ROADMAP_DIR:-$HOME/roadmap}" rev-parse --show-toplevel)" || exit 1
(cd "$ROADMAP_REPO" && br list --status open)
```


If a source is unavailable, say so and continue. Durable decisions from the run belong
in the board itself; write them to project memory only when the user asks or the owning
project already requires it.

When running in cmux, open the pushed GitHub board in a browser tab in the
caller's current workspace. Resolve that workspace from caller context; if it is
unavailable, query and verify cmux's current workspace. An installed CLI or reachable
socket alone does not establish that this task is using cmux.

Use the published branch's board URL so refresh loads the latest commit, while
retaining the commit-pinned proof URL in the report. Inspect only that workspace's
browser surfaces and their actual URLs. If this board is already open, refresh
that surface with `cmux browser --surface <surface> reload`; navigate the same tab
to the current branch URL if it holds the task's older pinned version. Otherwise,
use `cmux browser open <url> --workspace <workspace> --window <window> --focus false`,
preserving the workspace's existing task-owned browser session/profile.
For a private repository, use an existing task-owned profile that can read it;
an unsigned profile's 404 does not prove the file is missing. Verify the file
through the authenticated GitHub API and check the relevant existing task-owned
profile before reporting browser access blocked. Never use a personal profile
or copy cookies to repair access.

Do not create a window, workspace or profile, change unrelated surfaces, or launch
cmux outside a cmux session. Verify workspace membership, URL, title and rendered
board content; report a 404 or other rendering failure explicitly. Keep the tab
on the GitHub URL even if authentication blocks rendering; never substitute a
local file, rendered copy, localhost page or other non-GitHub destination.
Outside cmux, skip this UI step and return the GitHub link normally.

## Output document

Path convention: `~/roadmap/pr-inflight-YYYY-MM-DD.md` (update the same day's file
instead of creating a second one). Repo: `jleechanorg/roadmap`.

Required structure, in this order:

1. **TLDR at the very top.** Directly under the `## TLDR` heading, put one line
   `_Measured <Weekday> <Mon> <D>, <YYYY>, <h:mm AM/PM> PT_` in 12-hour Pacific
   time (e.g. `_Measured Thu Oct 29, 2026, 9:49 PM PDT_`); never a 24-hour clock or
   a UTC timestamp in that line. Immediately after it, add a named
   `### What changes for the user` section with a table:
   `| Work item | Before → after / user benefit | PR or bead | Status / stage | Done / remaining |`.
   Repeat a PR’s actual stage when it covers several work items; keep summary
   stages consistent with the detailed ledger, including marker mismatches.
   Include only requested user-facing features and fixes that remain open or
   active, then assigned work items that do not yet have a PR; list supporting
   tests, tooling and docs afterward. For each item, use a visible open PR number
   or bead link and state its current status (`planned`, `implemented`, or
   `unproven`). Explain the concrete before-and-after experience and user benefit.
   Do not name or narrate merged/completed PRs here, even when they answer the
   current request; put their records only in the final `Appendix — Merged work`.
   A PR title, stage, or opaque label such as “transport,”
   “harness,” or “sharing” does not explain the change. If no requested
   user-facing work is in scope, say so in this section.

   Only after this active-work list, give a short engineering overview of open /
   active stage counts, human-only blockers, stale or unowned work, total line
   delta and the biggest deltas. Then give every remaining in-scope open or active
   PR one or two plain-language sentences with its linked PR number visible, what
   is done and what remains unproven. Put supporting tests, tooling and docs after
   requested feature or fix work. Keep merged/completed PR names, rows, completion
   narratives and receipts out of the top section; include them only in the final
   `Appendix — Merged work`.
2. **Open / active PR ledger table**, one row per in-scope open or active PR:
   `| PR | Title | Repo | Stage | State | Head | Δ (lines) | Next | Brief |`
   - `PR` links to the full GitHub URL (number visible in the link text).
   - `Stage` = the explicit pr-lifecycle stage. Follow the manager's [Find the skills before inventing
     a workflow step](../pr-workflow-manager/SKILL.md#find-the-skills-before-inventing-a-workflow) to
     verify its official remote and record its commit before acting. Use `/pr-workflow` or `/prw` only
     when installed and verified; otherwise follow that entry point directly. Stage rules stay owned by
     `~/.claude/skills/pr-lifecycle/SKILL.md` § Stage, title and labels — e.g.
     `2 evidence generation`, plus any `hold:*` label. In a repository that opts into
     the six-stage workflow, read the stage label, title suffix and `## PR Stage`
     block; if they disagree, report the earliest unmet stage and write
     `MISMATCH (label X / title Y / block Z)` instead of picking one. A PR with no stage
     marker is `unstaged`; never infer a stage from draft status or CI colour. For
     PRs this session owns, before running the resolved `/prw` workflow entry point,
     read and retain the pre-sync values of the stage label, title and
     `## PR Stage` block, including any missing marker. If they disagree, record the
     earliest unmet stage and exact pre-sync mismatch
     (`MISMATCH (label X / title Y / block Z)`) for the final report.
     Then follow the resolved workflow entry point so the board reads synchronized markers, and preserve
     and report every recorded pre-sync mismatch even when that workflow resolves it. This is mandatory
     for every `/roadmap` invocation, including status-only and concise-report modes, and
     it must happen before the stage table is produced. When another owner controls a
     PR, run the resolved workflow in its status/read-only mode, preserve that owner's
     markers, and do not advance the stage without live workflow proof. If markers
     disagree, report the earliest unmet stage and the exact mismatch
     (`MISMATCH (label X / title Y / block Z)`); do not select a stage from draft
     status, CI colour, or prose.
   - `State` = OPEN/draft/ready + MERGEABLE|BLOCKED|UNKNOWN at the measured head.
   - `Head` = first 8 chars of the head SHA.
   - `Δ (lines)` = `+additions/−deletions` for the whole PR.
   - `Next` = the next action or exact blocker that exits the current stage.
   - `Title` = the PR's own title, verbatim and visible — trimmed with an ellipsis
     if longer than fits, never replaced by a label or a stage name. A reader must be
     able to recognise which PR this row is without opening GitHub.
   - `Brief` = ONE sentence stating what the PR changes and whether it is prod or
     test-only. No changelog.
3. **Group open / active ledger rows by merge-readiness, not just by stage.** Use
   these headings in this order, omitting any that is empty:
   - `### Merge-safe now` — every gate receipt binds to the current head, or its
     intervening delta has been read and recorded as applicable under
     `~/.claude/skills/pr-lifecycle/SKILL.md` § SHA-binding rule. For each, the
     `Brief` must say what a user gains and name the requested fix it closes.
   - `### Close to merge` — green but missing one named thing (a stale receipt to
     re-run, one failing check, one `hold:` release). For each, the `Brief` must say
     what the PR does **and** the single thing standing between it and merge.
   - `### Not mergeable` — failing checks, conflicting, or unapproved work.
   Closed PRs never appear in these groups. A stage label alone never earns a place
   in `Merge-safe now`; a green check alone never does either. Explain what each
   listed PR does in plain language — a stage number, a label, or the PR title
   repeated is not an explanation.
4. **Not yet a PR** — items with an owner but no branch/PR yet.
5. **Human actions outstanding** — only actions on open / active work that meet the
   shared human-only boundary. For each, state `Why the LLM cannot execute this next step now:`
   with the exact authority, physical dependency or essential unresolved decision.
   Undrafting, evidence review, checks and authorized deployments are not human
   actions merely because they remain undone. Execute available authorized work
   in the caller's scope before ending; preserve a planning/status-only scope.
6. **Owners (cmux surfaces)** — lane → workspace › surface title → open / active PRs covered.
7. **Later** — which open / active PRs will need a `/pr-summary` (architecture
   diagram, Why It Is Needed, How It Works, prod vs non-prod deltas) and the
   condition for writing it.
8. **Appendix — Merged work** — the final section, containing all merged or otherwise
   completed PR records and no active work. Preserve each record's historical stage,
   head SHA, deployment claim, and evidence/review receipts with their dates or source
   references. Do not promote historical claims to current status. Never put a
   merged PR name, ledger row, completion narrative, or its receipts elsewhere in
   the board. If none are in scope, state that here.

Every `/roadmap` report, including a concise chat or status reply, must start with
a named `What changes for the user` section before engineering counts or the
stage table. Cover open / active requested user-facing work first, followed by
assigned not-yet-PR items and then supporting tests, tooling and docs. Link each
item to its open PR or bead, state the actual status, and describe the concrete
before-and-after experience and user benefit; do not substitute a title or opaque
task label. Do not list or narrate merged/completed PRs in this section or in the
top-level engineering overview. After that section, every report must include the
open / active stage table. A compact reply may shorten surrounding prose, but it
must retain one row per in-scope open / active PR with the `Stage`, `State`, `Head`,
`Next`, and exact marker status; a prose-only status is incomplete. If there is no
open / active PR, say so and omit an empty ledger. Put all merged/completed PR
records only in the final `Appendix — Merged work`, including when they answer the
current request; preserve their historical stage, head, deployment claim and
receipts there.

## Evidence rules

- Every open / active ledger row comes from a live `gh pr view` at write time. Never
  carry a state, head, or delta forward from prose, a prior board, or another agent's
  report.
- For PR file counts or changed-file claims, resolve the actual current base-branch
  tip SHA and PR head SHA, then compute additions, deletions, and changed paths from
  `git diff <base-tip>...<head>` or a paginated REST compare bound to those SHAs. Do
  not use a stale PR `baseRefOid`, cached `gh pr view` totals, or cached
  `pulls/{number}/files` results as the source of truth.
- If today's board/report already exists on the current owner branch or main, reconcile
  it with live sources and the current base-branch tip, preserving other owners' rows
  and holds instead of appending duplicates or overwriting from a stale snapshot.
- Repeat the same 12-hour Pacific measurement time (`9:49 PM PDT`, not `21:49`) in one
  line at the bottom, and state that deltas are total
  additions/deletions (not prod-only) unless you computed the split.
- If a PR is stale, say how stale (last-updated date). If an item has no owner, write
  `no owner` rather than listing a retained name.

## Git rules

- Commit only the board file (`git commit -- <path>`); never sweep unrelated dirty
  files into the commit. Preserve other lanes' uncommitted work exactly as found.
- Use an isolated branch/worktree and the roadmap repository's PR workflow.
  Preserve unrelated dirty files and the shared index; do not stash another
  lane's work to force a rebase or push directly to main.
- Report the actual pushed commit, PR and commit-pinned board URLs. Do not claim
  the board is on main before the verified merge; merge authority remains separate.

## Canonical source

`~/.claude/skills/roadmap/` is the live copy; `jleechan-skills/.claude/skills/roadmap/`
is the published source. Diff both copies and repository status first, reconcile
only authorized changes, then verify exact hashes after synchronization. Do not
absorb another lane's unpublished edit merely to make copies match.

**Direction is one-way: repo -> live.** A live copy is never a source. A live-only
edit found during a board run is drift to report, not a change to copy back into the
repository.

Before editing, prove the baseline so foreign drift surfaces before your own edit can
hide it:

```bash
RM_BASE="$(mktemp "${TMPDIR:-/tmp}/rm-base.XXXXXX")" || exit 1
git -C <jleechan-skills-worktree> show origin/main:.claude/skills/roadmap/SKILL.md > "$RM_BASE" || {
  echo "Cannot read the published baseline; nothing was compared." >&2; exit 1; }
diff -u "$RM_BASE" ~/.claude/skills/roadmap/SKILL.md
```

An empty diff means the two copies agree and the edit may proceed. Any non-empty
diff is foreign drift: report it, and reconcile it deliberately (naming those lines
as not yours in the commit or PR body) instead of folding it in silently.

After editing the repository copy, propagate and verify exact hashes:

```bash
cp <repo>/.claude/skills/roadmap/SKILL.md ~/.claude/skills/roadmap/SKILL.md
if command -v sha256sum >/dev/null 2>&1; then
  sha256sum <repo>/.claude/skills/roadmap/SKILL.md ~/.claude/skills/roadmap/SKILL.md
else
  shasum -a 256 <repo>/.claude/skills/roadmap/SKILL.md ~/.claude/skills/roadmap/SKILL.md
fi
```

The two digests must match before the change is called synchronized. `~/.agents/skills/roadmap`
is a symlink into `~/.claude/skills/roadmap`, so it needs no separate copy.
