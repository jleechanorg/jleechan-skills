---
name: disk-root-cause
description: Use when a user asks why a disk is filling, what uses its capacity, what grew over time, or what can be safely reclaimed.
---

# disk-root-cause — forensic attribution skill

When a user asks **why the disk filled up**, **what grew over a window**, or **where a specific bucket came from**, this skill is the entry point. It never assumes an answer; it pulls facts from this machine's snapshot history (`~/.disk_magician_backup`), never deletes anything without an explicit human OK, and prefers parallel-subagent fan-out to keep wall-clock bounded.

## Default first-use workflow

Run this before chasing individual directories:

```bash
disk-magician audit
```

This is the mandatory three-lane diagnostic. It launches in parallel:

1. top-down whole-disk accounting from physical/APFS capacity through the Data volume and non-overlapping path buckets at or below 5 GiB;
2. coverage-validated snapshot deltas, so a coverage change cannot masquerade as physical growth; and
3. safe quick wins and obvious outliers, with cleanup commands still behind repository safety gates.

Read the whole report before drilling down. Keep permission/TCC denial, time budget, node budget, cross-device boundaries, APFS sibling allocations, purgeable estimates, and residual bytes as separate fields. The residual is an attribution gap: it is **not backup size and not reclaimable without evidence**.

The 900-second wall-clock cap is the infinite-process guard; live whole-volume runs on this host vary from about 6.5 minutes to more than 8 minutes under I/O load, so 480 seconds was empirically insufficient. Separately, the 100,000,000-record ceiling is a deliberately remote post-scan parser/ledger sanity guard (or a visited-path guard in the legacy fallback), not a normal coverage budget. GNU `du` stdout is spooled to a temporary file rather than retained in memory before that validation. The human-readable report must show the backend, records/paths processed, and this ceiling.

The displayed Data equation must use one accepted leaf ledger: `<=5 GiB bounded path buckets + indivisible files above 5 GiB + measured tail + purgeable estimate + residual = Data used`. Recursively subdivide every directory above 5 GiB; roll accepted descendants up only when their combined size stays at or below 5 GiB. Never display a larger directory as a normal bucket. Permission, time, node, depth, and cross-device limits stay on the named unfinished frontier and inside residual rather than masquerading as a large bucket. An indivisible file above 5 GiB is a separately labeled final path-level explanation, not a directory bucket. Never reuse an earlier parent observation. A hidden measured-total equation does not validate the displayed buckets. Capture Data used before and after the namespace walk; when it changes, report the residual interval and mark the measurement non-atomic.

The top-down scanner prefers one NUL-delimited, multi-root GNU `gdu` inventory process. Never sum independent per-shard `du` processes: hardlink deduplication is process-local. The one pass preserves hardlink dedup across logical top-level shards and supplies the complete postorder directory tree used to select non-overlapping <=5 GiB display rows without rescanning descendants. Allocation held directly by a large directory is shown as <=5 GiB `direct files + directory metadata` segments; unique-link indivisible files above 5 GiB are named separately. Localized permission/TCC errors taint their subtree and every ancestor, so partial ancestor totals are rejected while clean siblings remain attributable. Unknown diagnostics, malformed output, or timeout fail closed to the bounded frontier fallback (`gdu`, then `dua`, then macOS `du`). Fast backends must not be wrapped in `taskpolicy -b`, which can starve them under host I/O pressure. Symlink leaves never pull their targets into the ledger.

**Pair with** `disk_magician` skill (measurement + safe cleanup) and the `CLAUDE.md` / `AGENTS.md` in this repo (cross-repo authorization + never-delete list).

## When to use

Trigger when the user asks any of:
- "Why is my disk filling up"
- "What grew over the last day/week/month"
- "Find the minimum disk used in the last month" (floor)
- "Root cause the disk growth"
- "Show me the delta between then and now"
- "Reclaim X GB / how do I reclaim more" (skill is read-only forensics; safe-cleanup commands below)

Do **not** use this skill for one-off size queries — `du -sh <path>` answers those directly.

## Hard rules (skill-wide)

1. **Never delete anything without explicit user OK.** Every deletion goes through `./disk_magician.sh <script> --clean`, `cleanup-ao-sessions.sh --drop-bak --days N`, etc. — never `rm -rf` directly. The repo's scripts encode mtime filters and the never-delete list.
2. **Never-delete list** (hard-stop): `~/.codex/sessions*`, `~/.codex/state*.sqlite`, `~/.codex/log`, `~/.claude/projects`. Probe these paths only via `du -sh`, never with destructive verbs.
3. **Symlink gotcha — always realpath-verify:** `~/.hermes_prod` and `~/.openclaw.bak` are symlinks to `~/.hermes`; `/tmp`, `/var`, `/etc` are volume-root symlinks to `/private/*`. Naive `du` over args triples-counts them. Use `du -P` (no-follow) and dedup by realpath when comparing totals.
4. **No VACATE-without-name.** When a user says "vacate / pause / stop the CI runners", there is **no** `ez-mac-runner` launchd job on this host — `ez-mac-runner-b-{1,2,3}` are GitHub Actions runner **processes** under `~/actions-runner/`. Stopping the wrong thing (e.g. `com.jleechanorg.disk-root-cause`) is harmless but accomplishes nothing; stopping the GH Actions runners pauses live CI. Always `launchctl list | grep <hint>` and `ps aux | grep <hint>` before any destructive action, and report the candidate names back to the user verbatim.
5. **Read-first, deduce-later.** Do not assert "X grew 5 GB" from one `du`; cross-check against snapshot history (a committed git repo on disk) and the live `df -k /System/Volumes/Data`. If two sources disagree, attribute honestly.
6. **Scope expansions are user-OK gates.** Tools like `bobthecow` style auto-remediators are NOT enabled. The skill recommends; the human runs.
7. **Honest attribution in final report.** If disk improved mid-analysis for reasons outside this session (concurrent sweepers, OS reclaims), say so explicitly. Never claim a delta whose source you didn't observe.

## Phase 0 — environment ground truth (always run)

```bash
# Produce the default concurrent top-down + delta + quick-win report first.
disk-magician audit

# Authenticate the data source
df -h /System/Volumes/Data
hostname -s                                                    # = directory key in ~/.disk_magician_backup
SNAP=~/.disk_magician_backup/backup/$(hostname -s)/disk_snapshot.json
git -C ~/.disk_magician_backup log --oneline -1 -- "$SNAP" 2>/dev/null
python3 -c "import json,sys; d=json.load(open('$SNAP')); print('schema_version:', d.get('schema_version'), 'coverage:', d.get('snapshot_coverage_pct'))"
```

If `schema_version != 2`, the snapshot is pre-v2 (coverage inflates by parent/child double-count). Use `coverage_pct_raw_v1` from `snapshot_metadata` for trend continuity and note the inflation.

## Phase 1 — floor + deltas (snapshot history)

`~/.disk_magician_backup` is a git repo. Every commit is a snapshot. The skill reads history with `git log --all` (+ reflog for orphaned commits per the 07-11 incident) and `git show <sha>:backup/<host>/disk_snapshot.json`.

Three deltas, always reported:

| Window | Find | Compare to |
|---|---|---|
| **Last week** (7 d) | min `disk_used_gb` in window | live `df -k` |
| **Last month** (30 d) | min `disk_used_gb` in window | live `df -k` |
| **All time floor** | min `disk_used_gb` over all reachable + reflog-recovered commits | live `df -k` |

Pull both `disk_used_gb` (denominator, in GiB — verified to use `1024*1024` divisor in `disk_snapshot.sh:200-201`) and `disk_free_gb`. Compute:

```
delta_used = used_now − used_min
delta_free = free_min − free_now
```

Per-directory delta: for each key in `directories`, `git show <floor-sha>` and `git show HEAD` give values in KB; decompress into attributable buckets (colima, /tmp, AO sessions, ~/projects, ~/projects_other, ~/.gemini, ~/.codex, ~/Library subdirs, etc.). For null keys under disk pressure (the `timeout_keys` field), substitute live `du -sk` and label as "live-measured substitute".

**Coverage caveat:** the `topdown_coverage` field (schema_version 2) embeds the frontier scanner's `~/.disk_magician_state/frontier_last.json` summary if <36h old — use `frontier_unfinished_count` and `residual_kb` to flag the unmapped tail and surface it honestly. Days where `snapshot_coverage_pct < 70%` get `WARNING: low_coverage`; treat those deltas as directional, not exact.

## Phase 2 — parallel-subagent fan-out (when scope demands it)

Single-pass `du` answers questions fast (<2 min). When the attribution crosses the boundary into "find everything growing in category X", fan out via /swarm:

| Lane | Fan-out scope | Sample prompt shape |
|---|---|---|
| **lane-audit** | Safe-safe-reclaim inventory across dev caches, worktrees, AO sessions, /tmp, ~/Library/Caches | "Estimate safe-delete inventory from <scope>. Run each cleanup in DRY-RUN. NEVER delete. Hand-rm forbidden. NEVER touch never-delete list." |
| **lane-history** | Snapshot-history growth attribution | "From git history `~/.disk_magician_backup`, identify top growers between <floor-sha> and HEAD; cross-check with live `du`. Cite commit SHAs." |
| **lane-tmp** | /private/tmp live holders vs orphan candidates | "du + lsof, list per-entry: size, mtime, tmux-holder-PID, safe-to-drop?" |
| **lane-colima** | Colima sparse-disk inflation + recovery sequence | "Baseline du ~/.colima; fstrim; measure delta. Stop sequence optional. NEVER docker prune -af." |
| **lane-frontier** | Run `disk_frontier_scan.py --granularity-gib 5 --output-default` (900s cap) | One-pass GNU du inventory when available; named frontier fallback otherwise |
| **lane-critic** | Adversarial reality-check on top claims | "Try to refute each finding by recomputing from raw data. Cite file:line." |

Fan-out rule: **single-writer per file**, `grep -n "agent(" <swarm-script>` cost-routed (haiku for mechanical, sonnet for analysis), staggered starts (rule 4 in `/swarm`), explicit `--model:` on every call. Adversarial verify ≥3 lenses before any actionable claim.

## Phase 3 — readout format (always)

```text
⚠ Limits: coverage < X% / timeouts / pinned-subtrees HELD
↘ FLOOR (last month): used=YGB / free=YGB @ <iso> (commit <sha>)
↘ FLOOR (last week):  used=YGB / free=YGB @ <iso> (commit <sha>)
↘ NOW (live df):      used=YGB / free=YGB (GiB, GiB; units confirmed)
↘ DELTA (30 d):       used_now − used_min = ±Y GB;    free_min − free_now = ±Y GB
↘ Per-bucket attribution:
  - colima: +X (sawtooth Y; what range over time)
  - /tmp: +X
  - AO sessions: +X (post-.bak-drop, mostly live)
  - ~/projects: +X
  - residual (unaccounted): X (frontalier scanner names these within 36h of first nightly run)
↘ Safe-cleanup recommendations (require explicit OK):
  - run A: cleanup_tmp.sh --clean (~X GB, low risk)
  - run B: VACATE_CI_RUNNERS_APPROVED — needs user to confirm GitHub Actions runner target
  - run C: ...
↘ Evidence / proofs (commit SHAs, snapshot JSON keys, df outputs, du numbers)
```

## Cleanup-command catalogue (read-only — never auto-runs)

| Cmd | Use | Requires |
|---|---|---|
| `./scripts/cleanup_tmp.sh --clean` | >240min /tmp + agent scratch | Nothing (script dry-runs when defaults don't apply) |
| `./scripts/cleanup_dev_caches.sh --clean` (via `disk_audit.sh --clean`) | uv/pre-commit/cursor-agent/claude-cli caches | DISK_MAGICIAN_AUTO_CLEAN=1 |
| `user_scope/scripts/cleanup-ao-sessions.sh --drop-bak --days N` | .bak chains (post-6poe fix) | N chosen by caller |
| `./scripts/cleanup_colima.sh --clean` | Docker prune + fstrim (compresses host sparse disk) | Nothing (preserves running containers via docker prune semantics) |
| `./scripts/cleanup_worktrees.sh --clean` | Antigravity worktree GC | pre-WORKTREE-APPROVED if plan targets stale |
| `./scripts/cleanup_apfs_snapshots.sh --clean` | OS update snapshots >24h old | sudo (script silently fails without) |
| `cleanup-ao-sessions.sh --days 0` | Force ALL AO backups drop (aggressive) | User OK |
| `tmutil thinlocalsnapshots` | APFS local TM snapshots reclaim | sudo + user OK (impacts Time Machine reversibility) |

## Known traps (read this before answering)

1. **Snapshot coverage collapses under disk pressure** — biggest dirs go `null` (timeout). Plug with live `du -sk`. Cite both. (bead `$USER-wsbk`.)
2. **`discover` times out at 120s with zero output** — fixed in v2 by mtime cache. Don't repeat the test; use `disk_frontier_scan.py --output-default` instead. (bead `$USER-igr8`)
3. **`cleanup_tmp.sh` defaults to DRY-RUN despite header claiming otherwise** — header was fixed in v0.2.0 (commit `5341a6f`); callers still must pass `--clean`.
4. **Colima wedges with I/O errors when host disk hits 100%** — fstrim can't run; **must** `colima stop && colima start` first. 49.6→6.8 GB recovery verified live.
5. **No `ez-mac-runner` launchd job exists** — confirms via `launchctl list | grep ez` before any VACATE-style directive. (bead `feedback_2026-07-12_no_ez_mac_runner_launchd_job`)
6. **`backup/Mac/` was a stale host profile** — removed in v0.2.1 commit.

## Anti-patterns to flag in code review

- Re-implementing du/dedup in shell when `disk_snapshot.sh` already dedups with a realpath containment trie (schema v2). Live measure if a one-off is needed.
- Source-level `grep` for keys with substrings (e.g. `assert 'measured' not in json.dumps(td)` false-fail when the wanted key is `measured_total_kb`). Test contract: assert on dict keys, not substring matching.
- Heredoc stdin race: `python3 - <<'PY' … | something` — the heredoc wins the fd, so the pipe isn't read. Write to a temp file and pass it as argv.
- Symlink dedup at parent (`/var → /private/var`) for paths given to `du`. Add `-P` always.

## What this skill is NOT

- Not a cleaner (use `disk_magician` for cleanup; this skill explains why something grew).
- Not a real-time monitor (left to `disk-root-cause` + `pressure_sweep.sh`).
- Not authorized to push commits or merge PRs (read-only forensics + typed recommendations only).

## Exit criteria for the skill

A complete root-cause answer for this machine has:
- [ ] Default `disk-magician audit` three-lane report completed or its named limits were reported
- [ ] Every normal Data path bucket is at or below 5 GiB, without parent/child or symlink double counting
- [ ] Every larger directory is recursively subdivided or named on the unfinished frontier; indivisible files above 5 GiB are labeled separately
- [ ] Displayed Data equation reconciles bounded buckets + indivisible files + measured tail + purgeable estimate + residual = Data used from one accepted leaf ledger
- [ ] Data-used before/after bracket is shown; any drift is marked non-atomic with a residual interval
- [ ] Residual is explicitly not called backup or reclaimable without evidence
- [ ] Phase 0 ground-truth probe done
- [ ] Phase 1 floor deltas computed (last week + last month + all-time min)
- [ ] Phase 2 attribution buckets with credible per-bucket numbers
- [ ] Phase 3 readout in the format above, with explicit limits listed
- [ ] No destructive command proposed without an explicit human-OK gate
- [ ] Honest attribution: where any bucket delta is sourced from a concurrent agent or external sweep, say so
