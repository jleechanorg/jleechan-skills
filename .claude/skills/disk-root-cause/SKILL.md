---
name: disk-root-cause
description: Use when a user asks why a disk is filling, what grew, or how much can be reclaimed. Reclaimable-amount estimates require leaf-level attribution; plain capacity checks use disk-audit.
---

# disk-root-cause — forensic attribution skill

When a user asks **why the disk filled up**, **what grew over a window**, or **where a specific bucket came from**, this skill is the entry point. A plain capacity check routes to the zero-`du` triage in `../disk-audit/SKILL.md`. For disk attribution and reclaim estimates, use the state repository reported by `diskm state status` and prefer parallel fan-out when resources permit.

## Mandatory 100 MiB directory descent

Every measurement, inventory, report, age decision, and reclaim-candidate scan must resolve directories to individual files and directories smaller than 104857600 bytes (100 MiB). A directory at exactly 100 MiB must be descended into. Files are terminal items at any size; name and size every file at or above 100 MiB. Never treat a fixed class name, depth, Git marker, protected status, or configuration ceiling as a successful measurement stop.

Continue read-only metadata measurement inside Git worktrees, source trees, sessions, and other protected paths. Measurement does not authorize deletion, content reads, or changes: preserve existing owner, lease, cwd, open-file, dirty/unpushed, secret, and retention gates. Never follow a symlink; measure it as a link leaf. Preserve inode and hardlink deduplication.

A real permission, identity, enumeration, or deadline failure is unfinished work. Name the blocked path and reason, preserve its resume point, and exclude its parent and subtree from complete totals, floors, age decisions, and reclaim estimates. Report aggregate directory sizes as navigation hints only; they do not replace leaf itemization or prove reclaimability.

## Default first-use workflow

Start with the ground-truth probes defined in `../disk-audit/SKILL.md`, including the fleet check, existing per-host ledger, and 7-day growth history. Read those results before drilling down.

For root-cause, floor, growth, or reclaim-estimate requests, run the full `diskm audit` after these probes unless an existing current report already proves complete 100 MiB leaf coverage for every requested path and period. Directory-aggregate snapshots cannot prove that coverage. A quick capacity-only request may stop after the triage if its answer is sufficient.

The audit is the three-lane diagnostic. Its top-down accounting must resolve requested Data paths into file leaves and directories below 100 MiB. This instruction defines the required result; it does not change the scanner. Check the emitted report's actual resolution and unfinished paths. Until the installed runtime produces complete leaf itemization, treat coarse or unfinished paths as incomplete and any reclaim estimate that depends on them as unknown. The audit launches in parallel:

1. top-down whole-disk accounting from physical/APFS capacity through the Data volume to individual files and directories smaller than 100 MiB;
2. coverage-validated snapshot deltas, so a coverage change cannot masquerade as physical growth; and
3. safe quick wins and obvious outliers, with cleanup commands still behind repository safety gates.

Read the whole report before drilling down. Keep permission/TCC denial, time budget, node budget, cross-device boundaries, APFS sibling allocations, purgeable estimates, and residual bytes as separate fields. The residual is an attribution gap: it is **not backup size and not reclaimable without evidence**.

The 900-second wall-clock cap is the infinite-process guard; live whole-volume runs on this host vary from about 6.5 minutes to more than 8 minutes under I/O load, so 480 seconds was empirically insufficient. Separately, the 100,000,000-record ceiling is a deliberately remote post-scan parser/ledger sanity guard (or a visited-path guard in the legacy fallback), not a normal coverage budget. GNU `du` stdout is spooled to a temporary file rather than retained in memory before that validation. The human-readable report must show the backend, records/paths processed, and this ceiling.

The displayed Data equation must use one accepted leaf ledger: measured file leaves + measured directory leaves below 100 MiB + measured tail + purgeable estimate + unresolved residual = Data used. Report APFS container-free space and sibling-volume allocations in a separate container-level reconciliation so they are not mistaken for Data leaves or counted twice. A directory total, synthetic direct-allocation segment, or arbitrary size bucket is not a resolved leaf. Measure every file leaf and descend every directory at or above 100 MiB; name files at or above 100 MiB individually. Smaller file leaves may be compactly displayed as lossless count-and-size totals only after each file was measured and inode deduplication applied. Permission, identity, time, node, enumeration, or unscanned cross-device children stay on the named unfinished frontier and inside residual. Never reuse an earlier parent observation. A hidden measured-total equation does not validate the displayed leaves. Capture Data used before and after the namespace walk; when it changes, report the residual interval and mark the measurement non-atomic.

The top-down scanner prefers one NUL-delimited, multi-root GNU `gdu` inventory process. Never sum independent per-shard `du` processes: hardlink deduplication is process-local. The one pass must traverse all measurable directories to the 100 MiB stop floor and preserve hardlink/inode deduplication. Do not replace file rows with synthetic direct-allocation chunks. Localized permission/TCC errors taint their subtree and every ancestor; unreadable or unfinished subtrees remain explicitly incomplete. Unknown diagnostics, malformed output, or timeout fail closed to the bounded frontier fallback (`gdu`, then `dua`, then macOS `du`) and preserve the resume point. Fast backends must not be wrapped in `taskpolicy -b`, which can starve them under host I/O pressure. Symlink leaves never pull their targets into the ledger.

**Pair with** `disk-magician` skill (measurement + safe cleanup) and the `CLAUDE.md` / `AGENTS.md` in this repo (cross-repo authorization + never-delete list).

## When to use

Trigger when the user asks any of:
- "Why is my disk filling up"
- "What grew over the last day/week/month"
- "Find the minimum disk used in the last month" (floor)
- "Root cause the disk growth"
- "Show me the delta between then and now"
- "Which bucket is worth reclaiming, and why" or "how much can I free" — both require full leaf-level attribution. A quick available-space question with no reclaim estimate goes to `../disk-audit/SKILL.md`. This skill reports findings and typed recommendations; cleanup commands are separate.

For a one-file size query, report that file's size directly. A directory below 100 MiB may be reported as one measured unit; for any directory at or above 100 MiB, descend into files and smaller directories before reporting age, attribution, or reclaimability.

## Hard rules (skill-wide)

1. **Action scope and cleanup gates:** Perform cleanup only when the live request or standing authorization covers the same action, targets, and result. Authorization persists across the steps needed to complete that task; do not ask again for those steps. Route each deletion through its canonical `diskm` command and satisfy its current target-specific gates. Ask before adding new actions or targets not already covered; never use `rm -rf` directly.
2. **Never-delete list** (hard stop for removal by every route): `~/.codex/sessions*`, `~/.codex/state*.sqlite`, `~/.codex/log`, and `~/.claude/projects`. Continue read-only metadata descent through directories at or above 100 MiB; never delete, alter, or read protected file contents.
3. **Symlink gotcha — always realpath-verify:** agent-home aliases (for example backup or prod copies of `${HERMES_HOME:-$HOME/.hermes}`) are often symlinks to the live home; `/tmp`, `/var`, `/etc` are volume-root symlinks to `/private/*`. Naive `du` over args triples-counts them. Use `du -P` (no-follow) and dedup by realpath when comparing totals.
4. **No VACATE-without-name.** When a user says "vacate / pause / stop the CI runners", verify the runners' actual supervisor first — self-hosted GitHub Actions runners are often plain **processes** under their install directory, not a service job. Stopping the wrong thing (e.g. an unrelated service) is harmless but accomplishes nothing; stopping the GH Actions runners pauses live CI. Always inspect the service list (`launchctl list` on macOS, `systemctl --user list-units` on Linux) and `ps aux | grep <hint>` before any destructive action, and report the candidate names back to the user verbatim.
5. **Read-first, deduce-later.** Do not assert "X grew 5 GB" from one `du`; cross-check against snapshot history (a committed git repo on disk) and the live `df -k` output. If two sources disagree, attribute honestly.
6. **Stay within authorized scope.** Do not use an auto-remediator outside the canonical `diskm` commands. Continue cleanup that the current request authorizes and that the canonical per-target gates permit; ask only before a new action or target the request does not cover.
7. **Honest attribution in final report.** If disk improved mid-analysis for reasons outside this session (concurrent sweepers, OS reclaims), say so explicitly. Never claim a delta whose source you didn't observe.

## Phase 0 — environment ground truth (always run)

```bash
# Resolve the snapshot from the machine-specific state repository reported by the CLI.
df -h
STATE_REPO="$(diskm state status | sed -n 's/^\[state_repo\] state repo: //p')"
if [[ -z "$STATE_REPO" || ! -d "$STATE_REPO" ]]; then
  echo "state repo unavailable; snapshot history is incomplete" >&2
  exit 1
fi
SNAP="$STATE_REPO/snapshots/disk_snapshot.json"
git -C "$STATE_REPO" log --oneline -1 -- 'backup/*/disk_snapshot.json' snapshots/disk_snapshot.json 2>/dev/null
if [[ -r "$SNAP" ]]; then
  python3 -c 'import json,sys; from pathlib import Path; d=json.loads(Path(sys.argv[1]).read_text()); print("schema_version:", d.get("schema_version"), "coverage:", d.get("snapshot_coverage_pct"))' "$SNAP"
else
  echo "snapshot unavailable at resolved state-repo path: $SNAP" >&2
fi
```

If `schema_version != 2`, the snapshot is pre-v2 (coverage inflates by parent/child double-count). Use `coverage_pct_raw_v1` from `snapshot_metadata` for trend continuity and note the inflation.

## Phase 1 — floor + deltas (snapshot history)

The Git root for current state is the repository reported by `diskm state status`. Use resolver-backed history commands for archived samples; do not assume frozen `backup/<host>/disk_snapshot.json` files live under the current state repo. A frozen archive may contribute only a historical sample whose embedded capture time is in the requested window and whose coverage is at least 70%. Never use an archived file as the current snapshot or count duplicate captures twice.

Three deltas, always reported:

| Window | Find | Compare to |
|---|---|---|
| **Last week** (7 d) | Minimum `disk_used_gb` in window from snapshots with `snapshot_coverage_pct >= 70%` | live `df -k` |
| **Last month** (30 d) | Minimum `disk_used_gb` in window from snapshots with `snapshot_coverage_pct >= 70%` | live `df -k` |
| **All time floor** | Minimum covered `disk_used_gb` over reachable + reflog-recovered commits | live `df -k` |

Pull both `disk_used_gb` (denominator, in GiB — verified to use `1024*1024` divisor in `disk_snapshot.sh:200-201`) and `disk_free_gb`. Compute:

```
delta_used = used_now − used_min
delta_free = free_min − free_now
```

Per-directory snapshot deltas locate growers but remain directory aggregates. They do not establish file-level age, full attribution, or reclaimability. For a current attribution or reclaim estimate, descend every directory at or above 100 MiB to file and small-directory leaves. For null keys under disk pressure (the `timeout_keys` field), continue bounded itemization or report the exact unfinished key; a live `du -sk` parent total is not a substitute.

**Coverage gate:** exclude snapshots with missing, null, or `snapshot_coverage_pct < 70%` from floor selection and exact per-directory delta comparisons; keep them as low-coverage context only. The `topdown_coverage` field embeds the frontier scanner's `~/.disk_magician_state/frontier_last.json` summary if <36h old; use `frontier_unfinished_count` and `residual_kb` to name unmeasured tails. If no qualifying snapshot remains, report the snapshot floor unavailable and use the df-only daily `host_disk.used_kb` history in the configured disk observer log and its rotations. Report observed days and earliest/latest dates; do not infer all-time floors or per-path deltas from that fallback.

## Phase 2 — parallel-subagent fan-out (when scope demands it)

For a point size query on an individual file, report that file's size. A parent `du` total locates a directory; it never replaces descent at or above 100 MiB. When the attribution crosses the boundary into "find everything growing in category X", fan out via /swarm:

| Lane | Fan-out scope | Sample prompt shape |
|---|---|---|
| **lane-audit** | Reclaim-candidate inventory across dev caches, worktrees, AO sessions, /tmp, and Library caches | "Descend each directory at or above 100 MiB; measure file-level size/activity. Use cleanup previews and preserve their delete gates. Report unfinished paths and skip reasons." |
| **lane-history** | Snapshot-history growth attribution | "From the state repository reported by `diskm state status`, identify directory aggregates that grew between <floor-sha> and HEAD; treat these as navigation hints and itemize any current directory at or above 100 MiB before attributing or estimating reclaim. Cite commit SHAs." |
| **lane-tmp** | /private/tmp live holders vs orphan candidates | "Use directory sizes to locate candidates; descend each directory at or above 100 MiB to files and smaller directories. List each terminal item's size, age, open-handle/cwd owner, and cleanup gate." |
| **lane-colima** | Colima sparse-disk inflation + recovery sequence | "Measure the VM image file and its allocation; do not treat the enclosing ~/.colima directory total as itemized. Run the authorized fstrim sequence and measure its result. NEVER docker prune -af." |
| **lane-frontier** | Configure `disk_frontier_scan.py --granularity-gib 0.09765625 --output-default` after the scanner passes the inclusive-boundary and file-leaf checks | Do not claim complete leaves from this flag alone; verify that equality descends and that no synthetic chunks or skipped children remain. Record unfinished paths. |
| **lane-critic** | Adversarial reality-check on top claims | "Try to refute each finding by recomputing from raw data. Cite file:line." |

Fan-out rule: **single-writer per file**, `grep -n "agent(" <swarm-script>` cost-routed (haiku for mechanical, sonnet for analysis), staggered starts (`/swarm`, "Long runs"), explicit `--model:` on every call. Adversarial verify ≥3 lenses before any actionable claim.

## Phase 3 — readout format (always)

```text
⚠ Limits: coverage < X% / timeouts / pinned-subtrees HELD
↘ FLOOR (last month): used=YGB / free=YGB @ <iso> (commit <sha>)
↘ FLOOR (last week):  used=YGB / free=YGB @ <iso> (commit <sha>)
↘ NOW (live df):      used=YGB / free=YGB (GiB, GiB; units confirmed)
↘ DELTA (30 d):       used_now − used_min = ±Y GB;    free_min − free_now = ±Y GB
↘ Per-bucket attribution (non-overlapping sums of measured file/small-directory leaves; directory aggregates are navigation hints only):
  - colima: +X (sum of measured leaves; sawtooth Y; what range over time)
  - /tmp: +X (sum of measured leaves)
  - AO sessions: +X (sum of measured leaves; post-.bak-drop, mostly live)
  - ~/projects: +X (sum of measured leaves)
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

1. **Snapshot coverage collapses under disk pressure** — directories can be `null` or unfinished after a timeout. A live parent `du -sk` total only locates the path; it does not restore file-leaf coverage. Continue itemization within the available budget or report the exact unfinished paths.
2. **`discover` times out at 120s with zero output** — do not treat parent sizes as a completed inventory; use the bounded frontier and preserve every unfinished path.
3. **`cleanup_tmp.sh` defaults to DRY-RUN despite header claiming otherwise** — header was fixed in v0.2.0 (commit `5341a6f`); callers still must pass `--clean`.
4. **Colima wedges with I/O errors when host disk hits 100%** — fstrim can't run; **must** `colima stop && colima start` first. 49.6→6.8 GB recovery verified live.
5. **Confirm the runner supervisor** — `launchctl list | grep -i runner` (macOS) or `systemctl --user list-units | grep -i runner` (Linux), plus `ps aux | grep -i runner`, before any VACATE-style directive.
6. **Legacy snapshot path:** `backup/<host>/disk_snapshot.json` is frozen historical data, not a current measurement. Consider it only as an in-window historical sample with a valid embedded capture timestamp and coverage of at least 70%. Current measurement uses `snapshots/disk_snapshot.json`; `diskm state status` identifies the per-host state repository.

## Anti-patterns to flag in code review

- Re-implementing du/dedup in shell when `disk_snapshot.sh` already dedups with a realpath containment trie (schema v2). Live measure if a one-off is needed.
- Source-level `grep` for keys with substrings (e.g. `assert 'measured' not in json.dumps(td)` false-fail when the wanted key is `measured_total_kb`). Test contract: assert on dict keys, not substring matching.
- Heredoc stdin race: `python3 - <<'PY' … | something` — the heredoc wins the fd, so the pipe isn't read. Write to a temp file and pass it as argv.
- Symlink dedup at parent (`/var → /private/var`) for paths given to `du`. Add `-P` always.

## What this skill is NOT

- Not a cleaner (use `disk-magician` for cleanup; this skill explains why something grew).
- Not a real-time monitor (left to `disk-root-cause` + `pressure_sweep.sh`).
- Not authorized to push commits or merge PRs (read-only forensics + typed recommendations only).

## Exit criteria for the skill

A complete root-cause answer for this machine has:
- [ ] Default `diskm audit` three-lane report completed or its named limits were reported
- [ ] Every resolved directory leaf is below 100 MiB; every directory at or above 100 MiB was descended, and every file is individually itemized with hardlinks deduplicated and symlinks not followed
- [ ] Every traversal failure is named as unfinished and excluded from complete leaf totals, floors, age decisions, and reclaim estimates
- [ ] Displayed Data equation reconciles measured file leaves + measured directories below 100 MiB + measured tail + purgeable estimate + unresolved residual = Data used, with APFS siblings reported separately
- [ ] Data-used before/after bracket is shown; any drift is marked non-atomic with a residual interval
- [ ] Residual is explicitly not called backup or reclaimable without evidence
- [ ] Phase 0 ground-truth probe done
- [ ] Phase 1 floor deltas computed (last week + last month + all-time min)
- [ ] Phase 2 attribution buckets are non-overlapping sums of measured leaves; directory aggregates remain navigation hints
- [ ] Phase 3 readout in the format above, with explicit limits listed
- [ ] No destructive command proposed without an explicit human-OK gate
- [ ] Honest attribution: where any bucket delta is sourced from a concurrent agent or external sweep, say so
