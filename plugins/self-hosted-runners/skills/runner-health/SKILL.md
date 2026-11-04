---
name: runner-health
description: >
  Operational health snapshot for the jleechanorg self-hosted runner fleet.
  Use when user says "check runners", "are runners up", "is jeff-ubuntu down", "diagnose runner health",
  or before/after runner operations. Produces a structured Markdown report at
  /tmp/runner-health-<ts>.md with multi-method checks (GitHub API + local Docker
  + Lima VM + jeff-ubuntu ssh + optional hermes-pc cross-check). Works when jeff-ubuntu
  is unreachable (key insight: busy=true on runners is itself proof of liveness even
  when ssh fails).
type: skill
scope: repo
owner: $USER
version: 1.0.0
triggers:
  - "check runners"
  - "are runners up"
  - "is jeff-ubuntu down"
  - "diagnose runner health"
  - "runner status snapshot"
  - "fleet health"
  - "verify ubuntu runners"
allowed-tools:
  - Bash
  - Read
  - mcp__slack__*
  - Skill (memory-search, history-search)
context:
  - "GitHub /actions/runners org endpoint shows status (online/offline) and busy (true/false) only — no last_active field. busy=true IS the live-heartbeat proof: a runner can only be busy if it actively polled GitHub and accepted a job."
  - "Fleet is **ezgha-managed** (since 2026-07-06, replacing legacy org-runner): 16 Linux (`ez-runner-b-1..16` on jeff-ubuntu) + 6 mac (`ez-mac-runner-b-1..6` on local Mac) = 22 total expected. Ephemeral by design — each runner runs 1 job then exits, supervisor respawns. Online count fluctuates 19-22 normally; 22/22 steady state is impossible."
  - "When user is on a different wifi than jeff-ubuntu, ssh/ping from local host to jeff-ubuntu fails (different L3 subnet) but the runners themselves are still up if busy=true. Do NOT misdiagnose this as 'host down' — it's 'host unreachable from this network'."
  - "hermes-pc (Slack user U0BC138QXUJ / #hermes-pc channel) is on a separate network (172.20.5.90/19). Use as cross-check when local signals are ambiguous."
  - "Self-hosted-runner-preflight skill already exists for FIX-ORIENTED checks. This skill is different: it's an OPERATIONAL health snapshot (no fix proposed). Use this BEFORE preflight."
  - "MacBook: `ezgha serve` runs as launchd daemon `org.jleechanorg.ezgha` (plist at `~/Library/LaunchAgents/org.jleechanorg.ezgha.plist`, binary at `~/.cargo/bin/ezgha`). Restart: `launchctl kickstart -k gui/$(id -u)/org.jleechanorg.ezgha`."
  - "jeff-ubuntu: `ezgha serve` runs as `systemd --user` unit `ezgha.service` (config at `~/.config/ezgha/config.toml`, count=16). Restart: `systemctl --user restart ezgha`."
---

# /runner-health — Operational Health Snapshot

## When to use this skill

- User asks "are the runners up?", "is jeff-ubuntu down?", "show me runner health", "fleet health", "diagnose runners"
- Before any operation that depends on the fleet being healthy (e.g., before a `/green` drive)
- After a long gap (wifi change, host reboot) to verify reconnect
- Anytime a user reports "all alerts are noise" or "transient alerts" — this skill gives the ground truth

## What this skill does NOT do

- This is NOT a fix tool. It does not propose remediations.
- This is NOT a deep dive. For specific failures, use `self-hosted-runner-preflight` after this skill reports AMBER/RED.
- This does NOT modify any state. It only reads.

## The 6 deterministic health checks

Each is a standalone bash script in `scripts/` that outputs structured JSON to stdout.

| # | Script | What it checks | Failure mode (graceful) |
|---|---|---|---|
| 1 | `check_api.sh` | `gh api orgs/jleechanorg/actions/runners` — 22-runner snapshot + busy count + in-flight jobs (per-repo) + rate limit | exits non-zero on API error; runner fleet unreadable |
| 2 | `check_docker.sh` | local `docker ps` for mac-side runners + AO auxiliaries | exits non-zero if Docker daemon is down |
| 3 | `check_lima.sh` | `limactl list` — colima VM status, SSH port, resources | exits non-zero if limactl missing |
| 4 | `check_jeff_ubuntu.sh` | `ssh -o ConnectTimeout=5 jeff-ubuntu 'uptime; df -h /home; free -h; DOCKER_HOST=... docker ps | wc -l'` | exits non-zero on SSH timeout — but script still produces JSON with `reachable: false` |
| 5 | `check_session_conflict.sh` | For every GitHub-`offline` ezgha runner (mac or Linux fleet), cross-checks the local/SSH container state to distinguish **session conflict** (container `Up`, GitHub `offline` — stale registration lock; neither `ezgha serve` nor `ezgha-watchdog` detects this, since both only compare local managed-container counts) from ordinary `runner_offline` (container also down — ezgha will respawn it). Ported from closed PR #8033's `check_github_session_state()` / `container_status_for()` (bead rev-ws17d). | exits non-zero on `gh api` failure; JSON still emitted with `error` set |
| 6 | `cross_check_hermes.sh` | Posts thread to `#hermes-pc` and polls for reply (configurable wait) | exits non-zero if Slack MCP unavailable |

### Session-conflict triage (check 5)

A runner container can show `Up X minutes` in `docker ps` (or over SSH into
jeff-ubuntu) while GitHub's API reports `status:"offline"`. This divergence
is a **triage signal, not a confirmed diagnosis** — `check_session_conflict.sh`
proves the two states disagree (GitHub-offline + container-running), but it
never reads the container's `Runner.Listener` log, so it cannot itself
confirm the container is stuck in `Runner connect error: Error: Conflict`.
Treat every `session_conflicts[]` entry as "worth a human looking at the
listener log," not as "definitely a stale session." Neither `ezgha serve`'s
own churn-replacement nor the `ezgha-watchdog` fleet-size check catches this
divergence class — both only compare a **local** managed-container count
against the configured target, and a session-conflicted container is still
alive and still counted as "managed" locally.

**HUMAN-ONLY — do not automate.** The remediation below is destructive (it
deletes the runner's GitHub registration and restarts its container,
interrupting any in-flight job on that runner). `check_session_conflict.sh`
itself stays strictly read-only — do not wire these commands into any
watchdog, cron, or auto-heal path. A human should confirm the
`Runner.Listener` log actually shows the conflict (or otherwise judge the
runner is safe to bounce) before running any of this by hand:

```bash
# Identify the conflicted runner (check_session_conflict.sh JSON: session_conflicts[])
RUNNER_ID=$(gh api orgs/jleechanorg/actions/runners --jq '.runners[] | select(.name=="<name>") | .id')
gh api -X DELETE orgs/jleechanorg/actions/runners/$RUNNER_ID
# Mac fleet (ez-mac-runner-*): docker restart <name>
# Linux fleet (ez-runner-*/ez-canary-runner-*): ssh jeff-ubuntu "DOCKER_HOST=unix:///home/$USER/.lima/colima/sock/docker.sock docker restart <name>"
sleep 15
gh api orgs/jleechanorg/actions/runners --jq '.runners[] | select(.name=="<name>") | {name, status, busy}'
```

A `RED|SESSION CONFLICT: ...` verdict from `runner-health.sh` takes priority
over the generic per-arch online-count verdict — see
`parse_fields.py::compute_verdict`. Runner naming note: ezgha rotates a
generation letter suffix on supervisor restart (observed live: `b` → `c`),
so `check_session_conflict.sh` matches on the stable `ez-mac-runner-` /
`ez-` prefixes only, never a hardcoded generation letter.

## How to invoke

### Direct script (cron / ad-hoc)

```bash
# Basic (no cross-check)
bash .claude/skills/runner-health/scripts/runner-health.sh

# With hermes-pc cross-check, 1 call
bash .../runner-health.sh --cross-check 1

# Cross-check max 3 calls (deep investigation)
bash .../runner-health.sh --cross-check 3
```

Output: console table + Markdown file at `/tmp/runner-health-<ts>.md`.

### As a slash command (via /skill)

User runs `/runner-health` (or natural-language equivalent like "check runners"). The LLM:

1. **Phase 1 — load context** (optional but recommended):
   - Invoke `memory-search` skill with query "self-hosted runner jeff-ubuntu health check transient"
   - Invoke `history-search` skill to find any prior runner-health invocations in the last 30 days
   - Note any prior transient-pattern memory entries that should bias the verdict

2. **Phase 2 — run all 5 local checks in parallel** (subagents or sequential bash):
   ```bash
   bash .claude/skills/runner-health/scripts/check_api.sh
   bash .claude/skills/runner-health/scripts/check_docker.sh
   bash .claude/skills/runner-health/scripts/check_lima.sh
   bash .claude/skills/runner-health/scripts/check_jeff_ubuntu.sh
   bash .claude/skills/runner-health/scripts/check_session_conflict.sh
   ```
   Each produces JSON. The LLM parses + aggregates.

3. **Phase 3 — synthesize verdict (GREEN/AMBER/RED)** based on the JSON:

   **Session conflict (highest priority):** if `check_session_conflict.sh`
   reports any `session_conflicts[]`, report `RED — SESSION CONFLICT` with
   the affected runner name(s) and the manual-heal steps above instead of
   the generic per-arch online-count framing below — `ezgha serve` /
   `ezgha-watchdog` cannot fix this class.

   **Fleet shape (ezgha-managed, since 2026-07-06):**
   - 16 Linux runners (`ez-runner-b-1..16`) on jeff-ubuntu — managed by `ezgha serve` via `systemd --user`
   - 6 mac runners (`ez-mac-runner-b-1..6`) on local MacBook — managed by `ezgha serve` via `launchd`
   - **Total expected = 22** (16 Linux + 6 mac), but ephemeral by design (each runner exits after 1 job, then re-spawns)
   - Total online count fluctuates 19-22 normally; a 22/22 steady state is impossible by design

   **Verdict thresholds (per-arch, since ezgha):**

   | Verdict | Linux online | Mac online | Trigger |
   |---|---|---|---|
   | **GREEN** | ≥14 (healthy floor) | ≥5 (healthy floor) | Both hosts near full, no Docker restarts, all online runners busy=true |
   | **AMBER** | 10–13 (supervisor stuck) | 4 (supervisor stuck) | One or both `ezgha serve` supervisors not replenishing — needs `systemctl --user restart ezgha` on Linux OR `launchctl kickstart -k` on Mac |
   | **AMBER** | any | any | Docker restart loops detected |
   | **RED** | <10 | any | `ezgha serve` on jeff-ubuntu critically stuck — restart required |
   | **RED** | any | <4 | `ezgha serve` on Mac critically stuck — restart required |
   | **RED** | <10 online + 0 busy | n/a | jeff-ubuntu host dark (three-signal: 0 Linux busy + linux_online <10 + SSH unreachable) — DO NOT restart containers, wait for host |

   **CRITICAL preflight rules:**
   - If jeff-ubuntu SSH is unreachable AND Linux busy=0 AND Linux online is also critically low (<10) → it's the **host dark** class, not a container-level problem. Do NOT restart containers, do NOT spawn new ones. Wait for the host to come back. Log to `rev-runn001` for tracking. A high `linux_online` (e.g. 16/16) with 0 busy + unreachable SSH is a healthy-but-idle fleet on a different wifi subnet, NOT host-dark — it falls through to the GREEN/AMBER verdict below.
   - If online < expected but `ezgha serve` is alive (PID exists) and supervisor is just slow → AMBER, not RED. Restart supervisor to force-refill.
   - Always cross-check by inspecting `ezgha status` output on the suspect host BEFORE classifying as supervisor-stuck vs host-dark.

   **Why per-arch instead of total:** A single verdict line that says
   "RED — 14/22 online" hides whether it's the Mac fleet or the Linux fleet
   that's short. Naming the failing arch in the reason makes the fix
   obvious — `launchctl kickstart` on Mac vs `systemctl --user restart`
   on Linux.

4. **Phase 4 — cross-check** (only if user asks or AMBER detected):
   ```bash
   bash .../cross_check_hermes.sh <0|1|2|3>
   ```
   Posts to `#hermes-pc` thread ts (use existing thread or new one), polls for reply, parses response.

5. **Phase 5 — write Markdown report**:
   - `bash .../runner-health.sh --write-report` (or include in the master script by default)
   - File: `/tmp/runner-health-<unix-ts>.md`
   - Contents: 4-tables (one per check), verdict, recommendations

6. **Phase 6 — present to user**:
   - Print the verdict + table summary to console
   - Reference the Markdown file path

## Output format

### Console (default)

```
=== runner-health @ 2026-06-29 07:50 PDT ===
GitHub API:   22/22 runners online, 11/22 busy (8 Linux, 3 mac)
Docker:       6/6 mac Up, 0 stuck
Lima:         colima running, 4GiB mem, 100GiB disk
jeff-ubuntu:  unreachable from this host (different wifi subnet)
hermes-pc:    cross-checked — 14/22 busy confirmed independently

VERDICT: GREEN — runners healthy, host just on different subnet
```

Host-dark example (two-signal confirmed, see preflight Class E):

```
=== runner-health @ 2026-07-02 09:10 PDT ===
GitHub API:   6/22 runners online (all 6 mac), 16/16 jeff-ubuntu Linux runners online=0/busy=0
Docker:       6/6 mac Up, 0 stuck
Lima:         colima running, 4GiB mem, 100GiB disk
jeff-ubuntu:  ssh timeout + ping timeout — both signals confirm host dark

VERDICT: RED — jeff-ubuntu host dark (16/16 Linux runners offline + SSH/ping timeout confirmed).
NOT a generic <22/22 — this is a single-host outage. See rev-runn001 for tracking; do not open a new bead.
```

### Markdown file (`/tmp/runner-health-<ts>.md`)

```markdown
# Runner Health Report — 2026-06-29 07:50 PDT

## Verdict: GREEN

## Check 1: GitHub API
| Metric | Value |
|---|---|
| Total runners | 22 |
| Online | 22 |
| Busy | 14 |
| Linux busy | 11 |
| mac busy | 5 |
| Rate limit (core) | 4284/5000 |

## Check 2: Docker (local)
| Container | Status |
|---|---|
| org-runner-mac-1..6 | Up |
| AO auxiliaries | 7/8 Restarting (1) (PR #702 fix pending) |

## Check 3: Lima VM
| Field | Value |
|---|---|
| Name | colima |
| Status | Stopped |
| CPUS | 4 |
| Memory | 4GiB |
| Disk | 100GiB |

## Check 4: jeff-ubuntu
| Field | Value |
|---|---|
| Reachable | No (different wifi) |
| Subnet | 192.168.x.x (prior) |
| Recommendation | Check router DHCP lease for new IP |

## Check 5: Session conflict (GitHub offline vs container Up)
| Field | Value |
|---|---|
| Offline count | 0 |
| Session conflicts | none |

## Check 6: hermes-pc cross-check
(only if invoked)

## Notes
- PR #702 (AO spawn fix) not yet merged — bake-in bug recurs every ~1h
- 4 PRs open as DRAFT: #702, #8039, #8040, #8041
```

## Conventions

- Scripts are independent: each can run standalone for debugging
- All scripts output JSON (jq-friendly) and exit non-zero on hard error
- Master script `runner-health.sh` runs all + writes report
- Cross-check is opt-in via `--cross-check=<0|1|2|3>`
- Markdown report is in `/tmp/` (clears on reboot; user can persist by copying elsewhere)

## Anti-patterns

- Treating GitHub "online" as proof of liveness — it's registration cache, not heartbeat. Use busy=true.
- Diagnosing "host down" from ssh timeout alone — could be routing. Use busy=true as ground truth.
- `self-hosted-oss/` is retired (removed by PR #8057 and its cleanup follow-up) — do not reference or resurrect it. Runner-fleet changes now go through the `ez-gh-actions` ("ezgha") daemon / `self-hosted-colima/scripts/`; see `ezgha-watchdog` and `self-hosted-runner-preflight` for that territory.
- Storing state in `~/.local/share/runner-health/` — this skill is stateless by design.
