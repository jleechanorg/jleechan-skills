---
name: crash
description: Canonical triage order for crash investigation reports to surface panic traces, rank variables, and propose next steps.
---

# Jeff-Ubuntu crash investigation recipe

A canonical triage order for "the box crashed again" reports. Runs end-to-end in <2 min; surfaces the panic trace, ranks the new variables, and proposes a single concrete next step.

## When to use

- User says the box rebooted / crashed / hard-reset
- `journalctl --list-boots` shows a new short boot
- `uptime` is low after a long stable window
- pstore has unread dumps (`/var/lib/systemd/pstore/<timestamp>/`)

## Phase 1 — Confirm and timestamp (no sudo)

```bash
# Is the box actually post-crash, or is this a long uptime?
uptime
journalctl --list-boots --no-pager | tail -5

# Identify the dead boot and how long it ran
# (column 5 = LAST ENTRY of each boot)
journalctl -b -1 --no-pager | tail -5
journalctl -b -1 --no-pager | head -3
```

**The signature of a silent-stop hard reset:**
- journal cuts off mid-idle (cron, sysstat, snapd stateengine)
- No `kernel:` panic/OOPS/BUG lines in `journalctl -b -1 -k` for the last 5+ min
- No `systemd[1]: Reached target Shutdown` or `systemd-shutdown` lines
- `last reboot -F` shows "still running" for the dead boot (utmp/wtmp didn't get the shutdown entry)

## Phase 2 — Read the panic trace (sudo)

The journal `kernel:` ring only shows boot-start messages. The actual panic lives in pstore. Files are mode 0600 root-only — give the user a `! sudo cat ...` block, do NOT silently fall back to heuristics.

```bash
# All pstore directories
sudo ls -la /var/lib/systemd/pstore/

# For each directory, the dmesg.txt is the full panic log; the
# dmesg-efi_pstore-NNNNNNNNNNNN files are smaller fragments.
# Latest crash first:
sudo cat /var/lib/systemd/pstore/<latest-dir>/dmesg.txt
```

What to extract from the panic trace:
- **Function name** (e.g., `nvidia_pcie_config_check`, `mce_intel`, `kernel BUG at mm/...`) — names the module
- **Call trace / RIP** — points to the specific failure
- **Hardware error / MCE** — names the bus/device
- **"Hardware name"** — confirms machine identity
- **Last log line before panic** — what was happening

## Phase 3 — Variables changed since the last stable window

For each variable, ask: **was it changed since the last known-stable state?**

| Variable | How to read it | Where to find "last stable" |
|---|---|---|
| Kernel | `uname -r` | memory `current_soak_matrix_*` or recent handoff |
| NVIDIA driver | `nvidia-smi --query-gpu=driver_version` | memory `current_soak_matrix_*` |
| microcode | `grep microcode /proc/cpuinfo` | memory `current_soak_matrix_*` |
| GSP firmware | `cat /proc/cmdline \| grep NVreg_EnableGpuFirmware` | nvidia.NVreg_EnableGpuFirmware=0 in cmdline = GSP off |
| power cap | `nvidia-smi -q -d POWER \| head -10` | remember: don't validate under load only |
| Runners | `systemctl is-enabled jleechanorg-org-runners.service; docker ps --filter name=org-runner` | memory `runners_primary_trigger_*` |
| Hermes | `systemctl is-enabled hermes-prod hermes-staging` | memory `workload_trigger_isolation_*` |
| Bootable kernels | `ls /boot/vmlinuz-*` | GRUB will offer all installed |
| Apt history | `grep -B1 "Start-Date" /var/log/apt/history.log \| tail -40` | shows auto-upgrades |

```bash
# One-liner: list auto-upgraded kernel/driver/microcode in the last 60 days
zcat /var/log/apt/history.log.*.gz /var/log/apt/history.log 2>/dev/null \
  | awk '/Start-Date/{ts=$0} /Install|Upgrade/ && /linux-image-|nvidia-driver-595|microcode/ {print ts; print $0; print ""}' \
  | tail -40
```

## Phase 4 — Rank hypotheses (don't converge on the loudest)

After Phase 2 names the panic and Phase 3 names the new variables, **rank by evidence**, not by recency or public-bug similarity.

Template:

```
PANIC SAYS:    <function/call trace from pstore>
NEW VARIABLES: <list each variable changed since last stable>
RANK:
  1. <strongest match between panic and a new variable>
  2. <second strongest>
  3. <others>
NEXT:          <concrete single action>
```

The 2026-04-27 feedback `use_secondo_against_confirmation_bias` says: if the panic name matches a public bug report and you're feeling confident, invoke `/secondo` before publishing. False convergence has cost weeks on this incident cluster.

## Phase 5 — Propose the next step

Common single actions, ranked by reversibility:

1. **Disable a service** (e.g., `sudo systemctl disable --now jleechanorg-org-runners.service` and stop the 10 containers) — reversible, 30s
2. **Roll back kernel** via GRUB advanced → boot into previous `vmlinuz-*` → 24h soak — reversible, 2 min
3. **Cap GPU power** (e.g., `sudo nvidia-smi -pl 250`) — reversible, 1 min
4. **Downgrade nvidia driver** via `apt install nvidia-driver-595=595.58.03-...` — reversible, 10 min
5. **Run memtest86+** from GRUB — irreversible (no work for 6-8h), 1 min to start
6. **Swap hardware** (RAM stick, PSU, GPU reseat) — invasive, hours

Prefer the highest-evidence cheapest action. If 1-2 are inconclusive, move to 3-4. Only escalate to 5-6 after software is exhausted.

## Phase 6 — Save state

```bash
# Update the active bead
br update bd-12v --description "<new findings>"

# Write a memory snapshot
# Path: ~/.claude/projects/-home-$USER-projects-other-user-scope/memory/project_YYYY-MM-DD_<short-slug>.md
# Frontmatter: name, description, type=project, bead=bd-12v
# Body: status, why, how to apply — link with [[other-memory-name]]

# Add a one-line entry to MEMORY.md
```

## Anti-patterns

- **Don't open 4 investigative threads at once.** Pick ONE next step, run it, see the result.
- **Don't suggest the kernel was exonerated by the previous stability window** without re-checking what auto-upgraded since. The 2026-05-01 kernel-falsified conclusion was overridden on 2026-06-09 by the 6.17.0-35 auto-upgrade.
- **Don't validate PCIe link speed at idle.** Validate under load.
- **Don't trust that "Hermes is off" implies "runners are off"** — they are independent services. Check both.
- **Don't recommend memtest86+ as the first action.** It takes 6-8h with no other progress; reserve for hardware-path escalation.
