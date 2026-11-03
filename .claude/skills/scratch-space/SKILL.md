---
name: scratch-space
description: Single source of truth for agent scratch, temporary files, disposable builds, and evidence paths across macOS and Linux. Use whenever an agent, skill, or workflow needs a scratch directory, temporary file path, build output folder, or evidence directory instead of hardcoding /tmp or OS-specific mountpoints.
---

# Scratch Space (`/scratch-space`) — Single Source of Truth

## Purpose (Ponytail / DRY / ZFC Invariant)

Do **not** hardcode temporary workspace paths or a host-specific Scratch mountpoint across individual skills, prompts, or agent instruction files.

All temporary, disposable build, test scratch, and evidence paths resolve dynamically through the canonical Scratch resolver backed by local disk-magician configuration. Hosts may export `$DISKM_SCRATCH` and runtime temp variables, but exported skills must not assume those values exist; use the resolver and fail closed when it cannot resolve Scratch:

1. **Repo-Scoped Build, Test & Evidence Directories (Managed Lease + Admission)**
   ```bash
   # Allocate a managed build or evidence directory. If no Scratch volume is configured,
   # stop and report it: /tmp workspaces are prohibited (see the section below), so the
   # helper must not be used as a /tmp fallback.
   OUT_DIR="$(diskm scratch-new <repo-path> <purpose> --kind build)"
   EVIDENCE_DIR="$(diskm scratch-new <repo-path> <purpose> --kind evidence)"
   ```
   - Pass `--owner-pid <PID>` when allocating for a long-lived background process.
   - `diskm scratch-new` validates the request, applies admission checks, creates the directory, and records its lease. It does not enforce an age-based recency floor. `diskm scratch-prune` owns age-based cleanup; its current help reports a 24-hour default recency floor.

2. **Ad-Hoc Helper Files, PR Bodies, Frame Dumps, Server Logs & Ephemeral Scripts**
   ```bash
   # Resolve the host's active Scratch root (or create/return a subdirectory inside it)
   SCRATCH_ROOT="$(~/.claude/skills/scratch-space/scripts/scratch-dir.sh)"
   SCRATCH_TMP="$(~/.claude/skills/scratch-space/scripts/scratch-dir.sh tmp)"
   ```
   - Example (`gh` PR/issue body file):
     ```bash
     BODY_FILE="$(~/.claude/skills/scratch-space/scripts/scratch-dir.sh gh)/pr_body_$$.md"
     ```
   - Before using the helper for a workspace-shaped output, reject an empty result and any fallback to a system temporary directory. If Scratch is unconfigured, stop and report it.
   - Example (ephemeral `mktemp` directory for video frames, clones, or probes):
     ```bash
     SCRATCH_TMP="$(~/.claude/skills/scratch-space/scripts/scratch-dir.sh tmp)" || {
       echo "Scratch resolver unavailable; refusing allocation" >&2
       exit 75
     }
     [ -n "$SCRATCH_TMP" ] || {
       echo "Scratch resolver returned an empty path; refusing allocation" >&2
       exit 75
     }
     WORK_DIR="$(mktemp -d "$SCRATCH_TMP/work.XXXXXX")" || {
       echo "Scratch allocation failed" >&2
       exit 75
     }
     ```
   - Example (dev/test server logs):
     ```bash
     LOG_DIR="$(~/.claude/skills/scratch-space/scripts/scratch-dir.sh "logs/${REPO_NAME}/${BRANCH_NAME}")"
     ```

## What NOT to Put in Scratch

- **Git worktrees**: Always use `~/.worktrees/<repo>/<name>` via `diskm worktree-new <repo-path> <branch>`. Never put git worktrees in Scratch or `/tmp`.
- **Durable reports & roadmaps**: Keep in `~/roadmap/`.
- **Mutable agent state, credentials & transcripts**: Keep in `$HOME` (`~/.claude`, `~/.codex`, `~/.gemini`, `~/.config`).
- **Global `TMPDIR`**: Never remap global `TMPDIR` or replace `/tmp`.

## Host Provisioning Reference

Operators provision or inspect the quota-bounded Scratch volume via `diskm`:
- Provision (optional, recommended 200 GiB): `diskm setup --scratch [--quota-gb 200]`
- Query active mountpoint: `diskm volume path scratch`
- Check volume status: `diskm volume status scratch`

## `/tmp` workspaces are prohibited — enforcement depends on the host

A `PreToolUse` scratch-routing guard, where the host installs one (a hook wired into the
active runtime's settings, exit 2 = blocked), rejects tool calls that would create a
**workspace** under `/tmp`. It fires for `git clone`/`git worktree add`/`mkdir`/`mktemp
-d`/`cp`/`rsync`/`tar -C`/`unzip -d`/`pip --target` destinations and for document
writes under `/tmp`.

Why blocking rather than advice: `/tmp` is on the root filesystem whose free space gates
self-hosted runner admission, and lane clones there have drained a CI fleet twice
(20 -> 0 containers, then 20 -> 7). Relocating existing directories did not stop new ones
appearing, so a host that installs the guard enforces the rule there.

**This export does not ship that hook.** Enabling it is a host decision; where it is not
installed, the rules below are still the required behavior for an agent, and nothing
rejects a violation automatically.

`/tmp` remains correct — and is allowed — for: logs (`.log`), sockets, pid/lock/marker
files, single temp files, `.json`/`.jsonl` state, scripts (`.sh`/`.py`), pip unpack
dirs, X11/ssh-agent/chromium profile dirs. Durable documents belong in the reports
repository, never `/tmp`.

Where the runtime's own temp already points at the scratch volume, the guard covers the
Bash commands an agent types, which is where the drift was. A human operator can bypass
one call with `SCRATCH_GUARD_ALLOW_TMP=1`; an agent never sets it on its own behalf.
Global `TMPDIR` is still never remapped and `/tmp` is never replaced.
