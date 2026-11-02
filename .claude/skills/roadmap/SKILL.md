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

Resolve those sources against the roadmap repository, not the code repository:
`git -C "${ROADMAP_DIR:-$HOME/roadmap}" rev-parse --show-toplevel`, with `br list
--status open` for tracked items. If a source is unavailable, say so and continue.

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
   a UTC timestamp in that line. Then open with a short overview of stage counts, human-only
   blockers, stale/unowned work and total line delta; name the biggest deltas.
   Then give **every in-scope PR 1–2 plain-language sentences**, with its linked PR
   number visible: what changes for the user, which requested fix it addresses,
   and what is done versus still unproven. Put requested feature/fix PRs first and
   supporting tests, tooling and docs afterward. Include already-merged fixes when
   they answer a current request; distinguish implemented, merged, deployed and
   accepted. A stage number or generic label such as “sharing” is not a description.
2. **PR ledger table**, one row per PR:
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
3. **Group the ledger by merge-readiness, not just by stage.** Use these headings in
   this order, omitting any that is empty:
   - `### Merge-safe now` — every gate receipt binds to the current head, or its
     intervening delta has been read and recorded as applicable under
     `~/.claude/skills/pr-lifecycle/SKILL.md` § SHA-binding rule. For each, the
     `Brief` must say what a user gains and name the requested fix it closes.
   - `### Close to merge` — green but missing one named thing (a stale receipt to
     re-run, one failing check, one `hold:` release). For each, the `Brief` must say
     what the PR does **and** the single thing standing between it and merge.
   - `### Not mergeable` — failing checks, conflicting, or unapproved work.
   A stage label alone never earns a place in `Merge-safe now`; a green check alone
   never does either. Explain what each listed PR does in plain language — a stage
   number, a label, or the PR title repeated is not an explanation.
4. **Not yet a PR** — items with an owner but no branch/PR yet.
5. **Human actions outstanding** — only actions that meet the shared human-only
   boundary. For each, state `Why the LLM cannot execute this next step now:`
   with the exact authority, physical dependency or essential unresolved decision.
   Undrafting, evidence review, checks and authorized deployments are not human
   actions merely because they remain undone. Execute available authorized work
   in the caller's scope before ending; preserve a planning/status-only scope.
6. **Owners (cmux surfaces)** — lane → workspace › surface title → PRs covered.
7. **Later** — which PRs will need a `/pr-summary` (architecture diagram, Why It Is
   Needed, How It Works, prod vs non-prod deltas) and the condition for writing it.

Every `/roadmap` report, including a concise chat or status reply, must include a
stage table. A compact reply may shorten the surrounding prose, but it must retain
one row per in-scope PR with the `Stage`, `State`, `Head`, `Next`, and exact marker
status; a prose-only status is incomplete.

## Evidence rules

- Every row comes from a live `gh pr view` at write time. Never carry a state, head, or
  delta forward from prose, a prior board, or another agent's report.
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
