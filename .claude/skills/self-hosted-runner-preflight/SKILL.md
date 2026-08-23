---
name: self-hosted-runner-preflight
description: Pre-flight checklist for self-hosted runner failures. Use when investigating low disk, missing runner, or stuck Green Gate on the $GITHUB_REPOSITORY fleet. Always verifies host-level container state, not just GitHub API.
---

# Self-Hosted Runner Pre-Flight

## When to use this skill
- User says "runner is offline", "runner missing", "CI failed low_disk_space", "Green Gate stuck"
- `gh api orgs/jleechanorg/actions/runners` shows fewer than 22 runners
- A workflow run has been "in_progress" on Green Gate >30 minutes

## The 5-questions pre-flight (MANDATORY before any fix)

For each failure class, answer BEFORE proposing a fix:

1. **What does GitHub say?**
   `gh api orgs/jleechanorg/actions/runners?per_page=100 --jq '.runners[] | {name,status,busy}'`
2. **What does the host actually have?**
   - mac: `docker ps --format "{{.Names}}\t{{.Status}}" | grep org-runner-mac-`
   - jeff-ubuntu: `ssh jeff-ubuntu "DOCKER_HOST=unix:///home/$USER/.lima/colima/sock/docker.sock docker ps --format '{{.Names}}\t{{.Status}}' | grep org-runner-"`
3. **What does the disk look like inside the container?**
   `docker exec <name> df -Pk /` — needs >=1GB free for preflight to pass.
4. **Is the runner in restart loop?**
   - `docker ps -a --format "{{.Names}}\t{{.Status}}" | grep Restarting`
   - If yes, check logs: `docker logs --tail 30 <name>` for 403/registration errors.
5. **Is Green Gate stuck?**
   Check the run step "Check smoke gate (gate 8)" — if IN_PROGRESS >30min with no smoke runs on the branch, see Class C re-dispatch.

## Failure-class fixes

### Class A: low_disk_space (>=1 runner has <1GB free inside container)
- ROOT FIX: edit `self-hosted-oss/pre-job-hook.sh` to add disk cleanup (fires on EVERY job, not periodic).
- Pattern:
  ```bash
  AVAIL_KB="$(df -Pk "${RUNNER_WORKDIR}" 2>/dev/null | awk 'NR==2 {print $4}')"
  if [[ "$AVAIL_KB" -lt "$DISK_MIN_KB" ]]; then
    rm -rf /root/.cache/pip
    rm -rf "${RUNNER_WORKDIR}/<repo>"
  fi
  ```
- Set `DISK_MIN_KB=5242880` (5GB, 5x the preflight threshold).
- Belt-and-suspenders: add a periodic launchd script (`mac-runner-disk-cleanup.sh` style).
- Deploy: `bash self-hosted-oss/install.sh` syncs to `~/.local/share/worldarchitect-runners/pre-job-hook.sh` (bind-mounted live — no restart needed).
- VERIFY: `docker exec <runner> bash -c 'pgrep Runner.Worker'` returns empty (idle), then `df -Pk /` shows >=5GB.

### Class B: missing runner (compose defines N but only N-1 containers exist)
- mac (ARM64): `RUNNER_COUNT=<N> bash ~/.local/share/worldarchitect-runners/start-runner.sh start`
- jeff-ubuntu (X64):
  `ssh jeff-ubuntu "cd ~/projects/worktree_runner/self-hosted-colima && DOCKER_HOST=unix:///home/$USER/.lima/colima/sock/docker.sock docker compose up -d runner-<N>"`
- Then verify: `docker ps | grep runner-<N>` and `gh api orgs/jleechanorg/actions/runners --jq '.runners[].name' | grep runner-<N>`

### Class C: Green Gate stuck on gate 8 (smoke)
- Compare `SKEPTIC_GATE_TRIGGER` SHA pinned in PR comments to `gh pr view <N> --json headRefOid`.
- If mismatched, re-dispatch in order:
  ```bash
  gh workflow run "MCP Smoke Tests" --ref <branch> -f pr_number=<N>
  gh workflow run "Skeptic Self-Verify" --ref <branch> -f pr_number=<N>
  gh workflow run green-gate.yml --ref <branch> -f pr_number=<N> -f head_sha=<sha>
  ```
- All 3 require `pr_number`; green-gate.yml ALSO requires `head_sha`.

### Class D: token returns 403 from inside container
- Confirm token length: `docker exec <name> bash -c 'echo ${#ACCESS_TOKEN}'` (should be ~40).
- Test directly:
  `docker exec <name> curl -X POST -H "Authorization: token $ACCESS_TOKEN" -H "Accept: application/vnd.github+json" https://api.github.com/orgs/jleechanorg/actions/runners/registration-token`
- 201 → token fine, timing issue (config.sh ran before API ready), re-run start-runner.
- 401/403 → token bad/expired, rotate `gh auth token` and re-deploy.

### Class E: jeff-ubuntu host fully unreachable ("host dark")

**Distinct from Class B/D.** Those assume the runner *process* is broken and a
docker-level fix (restart, token rotate) will work. Class E is for when the
**entire physical host** is unreachable — no SSH, no API response, nothing to
restart, and (per standing org policy) no smart-plug/IPMI remote-power path to
even attempt a hard reset. jeff-ubuntu is on-prem with zero remote-power
access; this is a known, accepted limitation, not a gap to fix here.

**Two-signal confirmation (MANDATORY before declaring "host dark")** — a
single failed signal is not sufficient; the skill's own wifi/subnet caveat
(see `runner-health` SKILL.md) means SSH timeout alone is frequently a false
positive when the operator is on a different network than jeff-ubuntu:

1. **Signal 1 — direct reachability from the local Mac:**
   ```bash
   ssh -o ConnectTimeout=5 -o BatchMode=yes jeff-ubuntu true; echo "ssh_exit=$?"
   ping -c 2 -W 2 jeff-ubuntu; echo "ping_exit=$?"
   ```
   A non-zero exit on both is necessary but NOT sufficient on its own (could
   be local wifi/subnet routing, not a dead host).

2. **Signal 2 — GitHub API shows ALL jeff-ubuntu runners idle simultaneously:**
   ```bash
   gh api orgs/jleechanorg/actions/runners?per_page=100 \
     --jq '.runners[] | select(.name | startswith("org-runner-")) | select(.name | test("mac") | not) | {name,status,busy}'
   ```
   If EVERY Linux (non-mac) runner shows `status:"online", busy:false` (or
   `offline`) with none in-flight, combined with Signal 1's timeout, that is
   the confirmed two-signal "host dark" verdict. (A prior incident also saw
   `dig jeff-ubuntu` / `host jeff-ubuntu` return NXDOMAIN — a bonus third
   signal when local DNS is involved, but not required for the verdict.)

   **Do NOT declare host-dark from Signal 1 alone.** If Signal 2 shows any
   Linux runner `busy:true`, the host is alive and this is a network/wifi
   false-positive — stop, do not proceed to the playbook below.

**Playbook once both signals confirm host-dark:**
- **Do:** accept degraded capacity — the fleet temporarily runs on mac
  runners only (or whatever GitHub-hosted overflow lane exists, if one has
  been separately designed and merged; check for a GitHub-hosted-failover
  design before assuming one is live — this preflight skill does not
  implement that lane itself).
- **Do:** log the recurrence as a comment on bead `rev-runn001` ("Jeff-Ubuntu
  host freezes") — this is a known, tracked incident class open since
  2026-04-28. Do NOT open a new bead per recurrence; add evidence (date,
  two-signal output) as a comment so the P1 stays a single source of truth.
  `br comments add --actor <you> rev-runn001 -- "<date>: host dark, ssh+api both confirmed..."`
- **Don't:** retry SSH in a tight loop hoping it comes back — the host has no
  remote-power path, so nothing you run from the Mac will bring it back.
  Wasted retries burn time that should go to capacity triage instead.
- **Don't:** attempt any smart-plug/IPMI/remote-power action — explicitly
  deprioritized; this is a documentation/triage gap, not a hardware-control
  gap to fill.
- **Escalation:** if the host has been dark for a threshold you care about
  (this org's own SLA), the only real remediation is physical (someone at the
  location power-cycles it). Note that in the bead comment rather than
  attempting a workaround that doesn't exist yet.

## Anti-patterns
- Trusting GitHub UI as ground truth for runner health.
- Proposing "schedule a cron to clean up" as the primary fix (use per-job hook).
- Re-dispatching Green Gate without first dispatching smoke (gate 8 polls forever).
- Restarting the container while a job is running (always check `pgrep Runner.Worker` first).
- Editing the runtime mirror directly (`~/.local/share/worldarchitect-runners/`) — edit `self-hosted-oss/`, then `bash install.sh` to sync.
- Declaring "host dark" (Class E) from a single SSH/ping timeout — always confirm with the GitHub API signal too; SSH-only failure is frequently a wifi/subnet false positive.
- Retrying SSH to a confirmed-dark host in a tight loop — there is no remote-power path, so it will not come back on its own; spend the time on capacity triage and the `rev-runn001` bead comment instead.
- Opening a new bead for each jeff-ubuntu-dark recurrence — this incident class is tracked on `rev-runn001` (open since 2026-04-28); add a comment with the new date + two-signal evidence instead.
