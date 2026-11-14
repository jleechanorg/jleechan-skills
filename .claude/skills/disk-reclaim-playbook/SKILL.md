---
name: disk-reclaim-playbook
description: Use Disk Magician to diagnose disk growth or qualify cleanup on macOS or Linux.
---

# Disk reclaim playbook

Use the existing Disk Magician CLI (`diskm`, or its packaged `disk-magician`
entry point) for diagnosis, candidate qualification, cleanup, and receipts. The
repository's `CLAUDE.md` owns the command contract and host-specific details;
`disk-root-cause` owns the full measurement method. This skill gives the short
execution order and does not replace either owner.

## 1. Establish the live state before estimating reclaim

On the target host, check Disk Magician's scheduled fleet, read its existing
reclaim ledger, inspect recent deletion receipts, and measure current free space
with `df`. Then read the 7-day and 30-day history using `diskm history` /
`diskm history growth-top10 --days N` and the supported ledger fallbacks in
`disk-root-cause`.

Report, separately:

- current `df` free/used space;
- the lowest used-space observation and typical daily minimum in each interval;
- the interval actually covered, collector health, ledger freshness, and coverage;
- current path sizes and measured deltas from comparable snapshots;
- whether each estimate is a measured candidate, a protected item, or unknown.

A short observer history is not a 7- or 30-day floor. Low-coverage snapshots do
not establish a floor or path delta. Concurrent producers and cleaners can move
`df` during a run, so before/after `df` is an observed interval change, not
automatically bytes attributable to one cleanup.

## 2. Find producers and lock owners

Check current CPU, process pressure, and active producers before a deep scan or
cleanup. For a stuck-looking scan, inspect the exact process, parent lineage,
CPU/I/O activity, and output/progress before deciding it is stalled. No stdout
alone does not prove no progress; never stop a process you cannot identify and
own.

Before a Scratch mutation, inspect the exact Scratch lock and its live holder
lineage. Run only one mutating Scratch cleaner at a time when it shares that
lock. A receipt such as `skipped_lock`, a timeout, or `freed_bytes: null` is a
failed or incomplete reclaim, even if the process exit code is zero. Verify the
receipt and post-run `df` before reporting success. Do not kill an unknown lock
holder or extend a lock wait blindly.

## 3. Measure to files before qualifying content

Use `diskm measure-files PATH` or the owning scanner. Every directory at or
above 100 MiB must be itemized recursively until entries are files or directories
below 100 MiB. Never use a large directory's aggregate size or newest-child age
as evidence that its contents are safe or stale. Do not descend through symlinks
or into directories containing `.git`; report those as opaque, with their size
method and the reason they could not be itemized.

Use the real path and size in the 5-GiB ledger table. A table row is a summary,
not a permission to invent equal-sized chunks or a reclaim estimate. State
whether each figure is file-summed or a directory aggregate and the itemization
threshold. For a “nothing reclaimable” conclusion, name the largest individual
files inspected and the threshold reached; a top-level directory scan is not
enough.

Resolve each `kept:` result to its file-level cause before accepting a dry-run
total. A correct preservation decision and a bug can have similar labels. Fix a
proven classifier defect at its owner; do not treat an unqualified preview as
space that will be reclaimed.

## 4. Preserve source content and apply the age rule

The default age floor for ordinary disposable cleanup is 48 hours. Apply it to
each candidate's own content age, not an ancestor's aggregate mtime. Only a
clearly selected emergency override may use a shorter floor; the operator must
choose the override explicitly. Longer retention periods for backups, history,
archives, or lifecycle state are separate policies and do not become 48-hour
deletion defaults.

Dirty or unpushed source is not a permanent veto when a complete recovery copy
can be made. Preserve it through a verified independent remote branch or other
complete recovery path before removal; confirm the recovered commit and needed
content are present. Never publish actual private credentials to GitHub or
another remote. A public CA bundle is not a secret merely because its path
contains a credentials-like name.

Still preserve content when recovery is incomplete or unverifiable, or when the
item has private credentials, a live owner/cwd, an open file, an active lease,
unknown identity, or another explicit protection. Do not weaken these checks to
make an estimate reach a target.

## 5. Use the canonical cleanup and trim paths

Start with the matching `diskm` dry-run/report command and use its clean mode
only for candidates the operator authorized and the tool qualified. Do not
replace the CLI with a hand-written cleanup script, direct `rm`, raw worktree
deletion, or a privileged container with a host-root mount.

On Linux Scratch backed by a sparse image, deleting guest files and returning
host filesystem blocks are separate steps: run the existing
`diskm volume reclaim --available-floor` path after deletion, then measure host
and Scratch space again. A guest `df` or the number of deleted bytes does not
prove host reclamation. On macOS
APFS Scratch, verify the host's post-cleanup `df`; do not run Linux trim tools.
For container VM disk cleanup, use `diskm cleanup-colima` and its supported
host-specific options.

Run cleanup lanes concurrently only when their targets and locks are independent
and the host has measured capacity. Keep same-lock Scratch mutations serialized;
do not serialize unrelated work merely because it is all called cleanup.

## 6. Close with measured results

For each completed pass, capture its receipt and compare fresh host `df` with
the start-of-pass measurement. Report actual measured free-space change,
remaining qualified candidates, protected/unknown amounts, and which floors or
coverage gaps limit the conclusion. Distinguish bytes removed inside an image,
bytes trimmed by the host filesystem, historical growth, and observed host-free
change. Do not promise a fixed yield per machine or claim a target is reachable
without a current granular candidate inventory.
