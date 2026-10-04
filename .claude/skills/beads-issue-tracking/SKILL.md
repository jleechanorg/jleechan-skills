---
name: beads-issue-tracking
description: Use when creating, querying, updating, closing, syncing, or diagnosing Beads issues with the br CLI.
---

# Beads issue tracking (`br`)

`br` (`beads_rust`) is the supported issue tracker. Never use the retired `bd` CLI. Keep all Beads mutations via `br`. Never edit raw `.beads/*.jsonl` directly; bounded read-only forensic inspection of a backed-up copy is allowed only when `br` fails on malformed interchange (preserve all records, exclude secrets, and never perform raw rewrites).

## Essential commands

```bash
br list --status open
br list --status open --json
br show REV-demo
br search "keyword" --status open --label bug
br create "Fix login bug" --type bug --priority 2 --description "Provenance: file:line, repro, or URL"
br update REV-demo --status in_progress
br close REV-demo --reason "Fixed and verified"
br stats
```

Use `br close`, not `br update --status closed`; the update command rejects terminal states so close-policy and dependency rewiring run.

## Operating contract

- `beads.db` is the primary working store; keep all mutations via `br`.
- `.beads/issues.jsonl` is the version-controlled interchange/export. Do not edit it directly; inspect via `br`, except for bounded read-only forensic inspection of a backed-up copy when `br` fails on malformed interchange (preserve records, secrets excluded, no raw rewrite).
- Default to creating a bead for sourced follow-up work, regressions, flaky behavior, harness gaps, cross-session debt, and review leftovers.
- Do not create one for an unsourced idea or a trivial sub-two-minute fix already in flight.
- Include provenance in `--description`; close with `--reason`; reopen a failed fix with `br reopen <id>`.
- Reference the bead ID in related commits and PR artifacts.

## Sync and diagnosis

### Automatic union sync and agent conflict resolution

Automatically reconcile discovered divergence during Beads work. `jsonl_newer`,
`db_newer`, both together, and shared-ID conflicts do not require human review.
The agent or an LLM resolves record conflicts and completes sync without waiting
for approval. This is an agent workflow, not a claim that a timer is installed.

- Resolve and pin the configured canonical database with `br where`/`br info`.
  Honor intentional worktree redirects; do not create a competing database.
- Preserve consistent source snapshots and audit history before reconciliation.
  Union records by exact issue ID. Retain records present on only one side;
  union comments, labels, dependencies, and other relationships by their identity.
  Preserve explicit deletion/tombstone intent rather than resurrecting it blindly.
- For conflicting fields on the same ID, inspect both versions and their history.
  The agent/LLM chooses or synthesizes the coherent result from provenance and
  meaning; timestamps are evidence, not a blanket winner rule. Retain superseded
  values and the resolution rationale in a recoverable receipt or audit record.
  Ambiguity alone is not a human gate: make the best supported reversible choice.
- Use supported `br` commands for all record mutations. Inspect the installed
  `br sync --help`; preview additive reconciliation where supported, resolve
  remaining fields/relations through the CLI, then apply the fresh plan. A
  "reviewed" plan means agent review; no human signoff is required. Use the
  plan token when supported and re-plan if source state changes concurrently.
- Verify the union's IDs, comments, relationships, selected fields and readback,
  then publish through the repository's existing single export owner. Do not
  raw-concatenate JSONL, replace one side wholesale, rebuild away missing IDs,
  or bypass integrity checks merely to get a successful exit.
- A malformed store or failed integrity check is a technical recovery task,
  not a request for human conflict review. Continue supported recovery on
  preserved copies and unrelated work. If no verified supported recovery can
  proceed, report the exact technical blocker; never claim successful sync.

Repository merge, credential, and destructive-action gates remain separate.
Automatic record reconciliation does not authorize a Git merge or force-push.

### Export ownership and store authority

In repositories that explicitly configure this exporter architecture (verify the named files and owner first): `.github/workflows/beads-flush-on-main.yml` is validation-only; it never exports, flushes, or writes. `scripts/beads_sync_canonical.sh` is the single approved local canonical exporter, gated by `scripts/check_beads_jsonl_drift.sh` and `bead-jsonl-sort-check.yml`. Publication is push-from-local, not pull-from-CI (changed 2026-09-08: every self-hosted-macos-labeled CI runner is a Docker container with zero host filesystem access to the canonical `.beads` directory, confirmed via a throwaway diagnostic PR — a CI job can never read it, so the earlier `beads-flush-on-merge.yml` auto-publish-on-merge design cannot work regardless of trigger). `scripts/beads_publish_canonical_pr.sh` on a `scripts/launchd/` timer (the machine that owns the canonical store) is now the approved publisher (draft-only, human-merge boundary preserved); `beads-flush-on-merge.yml` is manual-only (`workflow_dispatch`) scaffold. Do not add a second exporter; see `rev-8xvey.6`.

For standalone stores without Git export (such as Linux factory instances), resolve store authority from the configured supervisor. Distinguish known store authority and DB-newer freshness from an actual data conflict; do not infer an authority conflict when canonical store authority is already established.

### Reusable containment/export scripts for other repos

`br`'s own safety contract (`br capabilities` → `no_automatic_git_operations`) means every repo that adopts Beads must build its own git-merge/CI orchestration around it — `br` deliberately does none of this itself. `scripts/check_beads_jsonl_drift.sh` and `scripts/beads_sync_canonical.sh` in this skill directory are portable copies of `$GITHUB_REPOSITORY`'s hardened implementations (the drift check survived 4 rounds of adversarial review closing a "competing writable authority" bypass; see `rev-8xvey`). A new repo adopting the same single-canonical-authority architecture (one physical `.beads/beads.db`, worktrees redirecting to it, `--no-auto-flush` on feature branches) can reuse both directly instead of rediscovering the same bypasses:

- `check_beads_jsonl_drift.sh` is already fully repo-path-agnostic (derives everything from `git rev-parse --show-toplevel`/`--git-common-dir`); it needs its sibling `compare_beads_jsonl_semantic.py` (co-located here) and, in CI, `BEADS_DRIFT_BASE_SHA` set to the exact fetched base commit.
- `beads_sync_canonical.sh` requires `CANONICAL_BEADS_DIR` (absolute path to the canonical checkout's `.beads` dir — no baked-in default, unlike the origin repo's copy) and `BEADS_EXPORT_BUNDLE_DIR`.

CI workflow YAML (`beads-flush-on-merge.yml`, `bead-jsonl-sort-check.yml`) is NOT ported here — those encode this specific repo's branch-naming and label conventions and should be adapted per repo, using `$GITHUB_REPOSITORY`'s `.github/workflows/` as the reference implementation.

### Routine issue batches

For already-specified issues, resolve the canonical store and perform the scoped
health/sync checks once per batch; repeat only if the store or health changes.
Reuse the supplied findings. Keep duplicate searches specific and initially return
only IDs, titles, and status; inspect full descriptions only for plausible matches.
Do not turn routine creation into a broad issue, memory, or repository audit.

Run commands against the same canonical store sequentially. If a tool returns a
live session, await its terminal result before starting the next `br` command.
On a lock timeout, inspect or await the known live operation before retrying;
do not remove locks or bypass safety checks. Verify created IDs in one compact
read and report them. Preserve the repository's no-auto-flush and authority rules.

```bash
br sync --status
br sync --flush-only
br sync --import-only
br doctor --robot-triage
br doctor --quick
```

`br sync` never runs Git commands. Export/import guards protect against empty, stale, conflicted, or malformed data. Do not use `--force`, `--repair`, or `--bypass-policy` without first reading the matching command help and inspecting the proposed scope.

For machine-readable contracts, run `br capabilities`, `br schema`, or `br robot-docs guide`. Treat live `br <command> --help` as authoritative when this reference and the installed version differ.

## Worktrees and conflicts

Each worktree has its own checked-out `.beads/issues.jsonl`, while the database location depends on workspace discovery. Use `br where` before diagnosis. Do not discard or stage another worktree's Beads state by assumption.

**Resolve the database before mutating, not just before diagnosing.**
`br` may discover a database outside the current worktree. Verify that it is the
configured canonical store, including any intentional `.beads/redirect`, and pin
mutating calls with `--db` to that resolved path. A configured shared database is
valid; do not fork it into one database per worktree. If discovery is unexpected,
inspect repository configuration and correct the target autonomously before
writing. Preserve any misplaced changes and reconcile them through `br`; never
run `git restore .beads/` to erase another session's work.

Resolve JSONL conflicts with the automatic union workflow above. Keep source
versions intact, resolve their records through `br`, validate, and use the owning
exporter. Git's textual conflict marker or `-merge` attribute is a signal for
agent reconciliation, not a request for human review.
