---
name: ezgha-watchdog
description: >-
  Read-only fleet-size consumer for the 6 mac + 16 linux ezgha runner
  invariant. Restart-only remediation is UNAVAILABLE (fail-closed) pending
  jleechanorg/ez-gh-actions PR 67 (dual-Lima convergence) and PR 70/issue 60
  (recovery controller) merging AND being proven live-deployed — a
  2026-07-09..11 audit found restarts can kill active jobs, create
  offline-busy 422 registrations, and cannot repair a dead/wrong-namespace
  backend. Use when the user says "make sure we have N mac and M linux
  runners", "ezgha fleet short", "supervisor stuck", or after any
  /runner-health AMBER/RED verdict — but diagnose with ez-gh-actions'
  doctor-runner first, never treat a shortfall as expected churn.
type: skill
scope: repo
owner: $USER
version: 2.0.0
triggers:
  - "enforce ezgha fleet size"
  - "ezgha serve stuck"
  - "fill missing runner slots"
  - "auto-replenish ezgha"
  - "is the ezgha fleet recovered"
allowed-tools:
  - Bash
  - Read
context:
  - "ezgha serve is a long-running supervisor that respawns runner containers as jobs complete (one job per container, then exit). It replaces churned slots but does NOT aggressively top-up to N when below configured count — if a slot stays deregistered for any reason (rate limit, crash, race), serve won't refill it on its own loop. That part of the diagnosis is still true."
  - "What is NO LONGER true: treating a restart as the normal/expected fix, or treating 5/6 mac or 14/16 linux as unremarkable churn. A 2026-07-09..11 audit (bead rev-ft3i8, GH issue #8329) proved restarts can kill ACTIVE jobs mid-run, can create offline-busy 422 runner registrations that neither `ezgha status` nor the GitHub API auto-cleans, and CANNOT repair a dead or wrong-namespace backend (e.g. a Lima VM pointing at the wrong Docker context) — a restart just respawns containers against the same broken backend, looking 'recovered' while masking the real defect."
  - "Runtime recovery logic (graceful drain, backend health verification, safe respawn ordering) belongs in jleechanorg/ez-gh-actions, not your-project.com. This repo's skills/scripts are READ-ONLY CONSUMERS of that repo's health contract (doctor-runner, ezgha status, GitHub runner API) — do not add backend-recovery mutation logic here."
  - "Expected fleet: 6 mac (`ez-mac-runner-b-1..6` on MacBook via `~/.config/ezgha/config.toml` `count=6`) + 16 linux (`ez-runner-b-1..16` on jeff-ubuntu via SSH `~/.config/ezgha/config.toml` `count=16`) = 22 total."
  - "A shortfall (N/M below configured count) is a DIAGNOSTIC PROMPT, not a threshold to dismiss. Run `doctor-runner` (see below) before deciding anything is 'expected'. Never lower `count` or the alert threshold to make a shortfall look normal — that hides the same defect the audit found."
---

# /ezgha-watchdog — read-only consumer of the 6 mac + 16 linux runner invariant

## STATUS (2026-07-13): restart-only remediation is UNAVAILABLE — diagnose-first, fail-closed

**Do not treat `launchctl kickstart` / `systemctl --user restart ezgha` as a
routine self-heal.** The previous version of this skill said restarting the
supervisor was the normal/expected fix and that 5/6 mac or 14/16 linux was
"expected churn — don't alarm." Both statements are now known to be unsafe
defaults per the 2026-07-09 through 2026-07-11 audit (bead `rev-ft3i8`, GH
issue [#8329](https://github.com/$GITHUB_REPOSITORY/issues/8329)):

- Restarts can kill **active jobs mid-run**, not just idle slots.
- Restarts can create **offline-busy 422 runner registrations** that neither
  `ezgha status` nor GitHub's runner API cleans up automatically.
- A restart **cannot repair a dead or wrong-namespace backend** (e.g. a Lima
  VM pointing at the wrong Docker context) — it just respawns containers
  against the same broken backend, which *looks* recovered while the real
  defect stays live.

**Gating condition for restart-only mutation to become available again** —
BOTH must be independently confirmed merged in git AND proven live-deployed
on the Mac/Linux hosts (a git merge alone is not activation — see "MANDATORY:
post-merge activation check" below):

1. jleechanorg/ez-gh-actions **PR #67** — dual-Lima convergence to a single
   canonical Docker backend (bead `ez-gh-actions-apye`). Verify current
   status with:
   ```bash
   gh api repos/jleechanorg/ez-gh-actions/pulls/67 --jq '{state,merged,merged_at}'
   ```
   Status as of 2026-07-13: `{"state":"open","merged":false,"merged_at":null}`
   — **NOT merged**.
2. jleechanorg/ez-gh-actions **PR #70** — singleton backend-aware recovery
   controller for Mac+Linux (bead `ez-gh-actions-ghd2.7`, tracking issue
   [ez-gh-actions#60](https://github.com/jleechanorg/ez-gh-actions/issues/60)).
   Verify current status with:
   ```bash
   gh api repos/jleechanorg/ez-gh-actions/pulls/70 --jq '{state,merged,merged_at}'
   ```
   Status as of 2026-07-13: `{"state":"open","merged":false,"merged_at":null}`
   — **NOT merged**.

Until both are merged AND their live-deployment is independently proven (see
"Live-deploy proof required" below), any restart of `ezgha serve` — via this
skill's script, `launchctl kickstart`, or `systemctl --user restart` — is a
**last-resort, human-approved action only**, never an automated first
response or something to silently normalize.

**Restart gate (fixed 2026-07-16, bead `rev-5rqci`)**: `scripts/ezgha-fleet-watchdog.sh`
(the launchd/systemd-installed watchdog, ticking every 120s) now always
detects and logs a below-target shortfall, but only executes the actual
restart command (`launchctl kickstart` / `systemctl --user restart`) when
`EZGHA_WATCHDOG_ALLOW_RESTART=1` is explicitly set — unset/0 is fail-closed
(alert-only), matching this doc's stated policy. Do not set that env var in
the launchd/systemd unit until PR #67/#70 (or an equivalent live-deployed
recovery path) is confirmed non-destructive. Regression test:
`scripts/test_restart_gate.sh`.

## Diagnose with the real tool: `doctor-runner` (ez-gh-actions repo)

`doctor.sh` in ez-gh-actions is **LEGACY/BROKEN on Docker 27+** (bead
`ez-gh-actions-91r`) — on modern Docker it silently misclassifies every
working runner as IDLE. **Use `doctor-runner` instead** — the authoritative
script (shipped 2026-07-08; extended 2026-07-09 with the 4-state per-slot
activity-truth model):

```bash
# From an ez-gh-actions checkout (clone a scratch copy if you don't have one):
git clone https://github.com/jleechanorg/ez-gh-actions.git /tmp/ez-gh-actions-check
cd /tmp/ez-gh-actions-check

./doctor-runner            # health gate: exit 0 = healthy, real per-slot state
./doctor-runner --prove    # + dispatches a live canary job and verifies it lands
                            #   on the configured runner prefix with conclusion=success
                            #   — the strongest available evidence
```

If working directly inside an ez-gh-actions checkout, use its own slash
command instead: `/doctor-ezactions` (runs `doctor-runner`, then `/harness`
automatically when unhealthy or the queue tail exceeds threshold).

`doctor-runner` section 9 classifies every configured slot via
`docker top <container> | grep Runner.Worker` into exactly one of four
states:

| State | Meaning | Defect? |
|---|---|---|
| EXECUTING | `Runner.Worker` process present, job running | No |
| IDLE-OK | listening; nothing queued, or queued < 5 min | No |
| IDLE-STARVED | listening; queue non-empty ≥ 5 min | **Yes** |
| DOWN | no running container | **Yes** |

**The GitHub runner API alone cannot be trusted for fleet state.** Under
rate limiting it returns truncated/partial data — the same live fleet has
been reported as 7/11/16/19/22 across calls minutes apart. `docker top` /
`docker ps` on the host is the source of truth for per-slot state; never
conclude fleet health from API counts in isolation.

## Live-deploy proof required before any "recovered" claim

A code fix merging upstream is **not** the same as it running (see the
"MANDATORY: post-merge activation check" section below and the user-scope
Runtime Activation Claim rule). Before claiming any fleet is "recovered" or
"healthy" after any remediation — restart, manual `docker rm -f`, service
restart, or a future recovery-controller action once PR #67/#70 ship — show
real command output for BOTH of the following:

1. **Docker identity proof** — confirm which Docker backend/context is
   actually live and matches the intended one. This is exactly the class of
   bug PR #67 fixes (dual-Lima drift to the wrong backend):
   ```bash
   docker context show
   docker info --format '{{.Name}} {{.ServerVersion}}'
   docker ps --filter label=ezgha=managed --format '{{.Names}} {{.Image}} {{.Status}}'
   ```
2. **Functional runner/job proof** — a real job actually completing on the
   fleet, not just a container existing or a registration showing:
   ```bash
   docker top <container-name> | grep Runner.Worker   # process-level proof it's executing
   # stronger:
   ./doctor-runner --prove                             # dispatches + verifies a live canary job
   ```

`managed=N` container count alone is **insufficient** — a container can
exist and even show registered while still being IDLE-STARVED or wedged
against a dead/wrong backend. Anything short of both (1) and (2) above is a
tool-layer claim ("container started", "`systemctl restart` exit 0"), not an
end-state recovery claim.

## your-project.com scope: read-only consumer only

This repo (`.claude/skills/ezgha-watchdog/`) must only:

- **Read** fleet state (`ezgha status`, `docker ps`, the GitHub runner API,
  `/runner-health` output) to report AMBER/RED verdicts.
- **Surface** the diagnose-first `doctor-runner` command to the operator.
- **Never** implement its own backend recovery/drain/respawn-ordering logic.
  That responsibility lives in jleechanorg/ez-gh-actions (PR #67, PR #70).
  Any future change to this repo that adds new autonomous mutation logic
  beyond a human-approved, last-resort restart is out of scope here and
  should be redirected upstream to ez-gh-actions instead.

## Layout

| File | Host | Purpose |
|---|---|---|
| `scripts/ezgha-fleet-watchdog.sh` | both | Check + restart logic; restart itself gated fail-closed behind `EZGHA_WATCHDOG_ALLOW_RESTART=1` (see "Restart gate" above, bead `rev-5rqci`) |
| `scripts/test_restart_gate.sh` | both | Regression test proving the restart gate is fail-closed by default and opt-in works |
| `~/Library/LaunchAgents/org.jleechanorg.ezgha-watchdog.plist` | MacBook | launchd job, runs every 120s |
| `~/.config/systemd/user/ezgha-watchdog.{service,timer}` | jeff-ubuntu | systemd --user timer, runs every 120s |
| `/tmp/ezgha-watchdog.log` | both | Append-only log of check + restart actions |
| `$HOME/.cache/ezgha-watchdog/{mac,linux}.consecutive` | both | Hysteresis counters — consecutive below-target samples per arch, persisted across invocations since each 120s tick is a fresh process, not a long-lived loop |

## Hysteresis (restart trip point) — degraded pending upstream fix

Each tick is one sample. The script only restarts the supervisor once the
consecutive below-target count exceeds 2 (i.e. on the 3rd consecutive
sample, ~4-6 minutes of continuous shortfall). The counter resets to 0 the
moment a sample is back at/above configured count. Override the state
directory with `EZGHA_WATCHDOG_STATE_DIR` (used by the test suite for
isolation).

**This hysteresis threshold does not make the resulting restart safe** — it
only reduces restart *frequency*, not the risk that a given restart kills an
active job or masks a wrong-backend defect. Treat every fired restart as a
signal to run `doctor-runner` afterward and confirm live-deploy proof (above)
before considering the shortfall resolved.

## MANDATORY: post-merge activation check

**A PR merging the watchdog script/templates is NOT the same as the watchdog
running.** This is the exact failure this session hit: PR #8193 (the
watchdog fix) merged and passed all CI/codex/`/advice` gates, but the
launchd job was never actually installed on the Mac host —
`launchctl list | grep ezgha-watchdog` returned nothing for ~19 hours after
merge, silently leaving the Mac fleet under-provisioned (4/6) the whole
time. The code/test layer was verified; the deployment/installation layer
was not (this is this repo's "Runtime Activation Claim" trap applied to an
operational daemon). The same discipline applies upstream: PR #67 and PR
#70 merging in ez-gh-actions is not proof they are running on the actual
Mac/Linux hosts — verify live deployment there too before relying on them.

**Whenever a PR touches this skill's `scripts/` files, the
close-out checklist is incomplete until BOTH of these are run and show real
output, not just "PR merged":**

```bash
# Mac
launchctl list | grep ezgha-watchdog        # must show a PID or "-" (loaded), NOT empty
tail -5 /tmp/ezgha-watchdog.log             # must show a recent timestamp (<5 min old)

# jeff-ubuntu (Linux)
ssh jeff-ubuntu 'systemctl --user list-timers ezgha-watchdog*'   # must show a NEXT/LAST fire time
ssh jeff-ubuntu 'tail -5 /tmp/ezgha-watchdog.log'
```

If either check comes back empty, install using the "Install on a new host"
section below — a merged PR is a necessary but not sufficient condition for
this being active.

## How to invoke manually

```bash
# Both hosts, fix if needed
bash .claude/skills/ezgha-watchdog/scripts/ezgha-fleet-watchdog.sh

# Only one host
bash .../ezgha-fleet-watchdog.sh --host mac
bash .../ezgha-fleet-watchdog.sh --host linux

# Dry-run (report only, do not restart) — PREFER THIS until PR #67/#70 land
bash .../ezgha-fleet-watchdog.sh --dry-run

# View recent watchdog activity
tail -n 20 /tmp/ezgha-watchdog.log
```

## Exit codes

| Code | Meaning |
|---|---|
| 0 | Both hosts at configured count |
| 1 | One or more hosts below count (fixed by restart, or dry-run reported it) |
| 2 | Cannot read state (ezgha missing, SSH timeout, config unreadable) |

## Install on a new host

This skill ships only `scripts/ezgha-fleet-watchdog.sh` and
`scripts/test_restart_gate.sh`; no launchd plist, systemd unit or timer
template exists in this repository, so there is no `install/` directory to
copy from. Create the job by hand and keep it on `--dry-run` until the
restart gate above is lifted:

- macOS: write a `~/Library/LaunchAgents/org.jleechanorg.ezgha-watchdog.plist`
  that runs `bash <repo>/.claude/skills/ezgha-watchdog/scripts/ezgha-fleet-watchdog.sh --dry-run`
  every 2 minutes and logs to `/tmp/ezgha-watchdog.log`; follow the
  `launchd-plist-template` skill (template in the repo that owns the job,
  `@HOME@` placeholders), then `launchctl load` it.
- Linux (jeff-ubuntu): write an `ezgha-watchdog.service` (same command) and an
  `ezgha-watchdog.timer` (`OnUnitActiveSec=2min`) under `~/.config/systemd/user/`,
  then `systemctl --user daemon-reload && systemctl --user enable --now ezgha-watchdog.timer`.

Confirm with the two live checks in the close-out checklist above.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Watchdog keeps restarting serve every 2 min | Supervisor fundamentally broken, or backend is dead/wrong-namespace (restart cannot fix this — see STATUS above) | Run `doctor-runner` first; check `/tmp/ezgha-launchd-stderr.log` (Mac) or `journalctl --user -u ezgha` (Linux); check Docker identity (`docker context show`) before assuming another restart will help |
| `managed=0` for >5 min | Docker daemon dead OR container image missing | `docker info` + `docker images \| grep ezgha-runner` |
| `configured=N` missing in log | Config file unreadable | `cat ~/.config/ezgha/config.toml` — should have `count = N` under `[runner]` |
| Linux check returns "cannot read state" | SSH key / alias broken | `ssh -o ConnectTimeout=5 jeff-ubuntu 'echo ok'` |

## Anti-patterns

- Do NOT treat a restart as routine self-heal, and do NOT treat N/M below
  configured count as "expected churn" without first running `doctor-runner`
  — both were the exact false assumptions the 2026-07-09..11 audit disproved.
- Do NOT claim a fleet is "recovered" without both Docker-identity proof and
  functional runner/job proof (see "Live-deploy proof required" above).
- Do NOT run `ezgha start --count 1` to fill a single missing slot — the
  supervisor's own slot state will conflict. Prefer diagnosis over any
  restart while PR #67/#70 remain unmerged.
- Do NOT lower `count` in config to "match reality" — the count is the
  target, not the actual. Lowering it removes the alert.
- Do NOT add a separate alerting Slack channel — `/runner-health` AMBER/RED
  already names the failing arch with the diagnostic command inline.
- Do NOT add backend recovery/drain/respawn logic to this repo — that
  belongs in jleechanorg/ez-gh-actions (PR #67, PR #70). your-project.com
  stays a read-only consumer of its health contract.
