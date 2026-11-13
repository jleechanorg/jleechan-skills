# Worked examples and incident detail

Scoped reference for `parallelize-to-ceiling`. The rules these illustrate live
in the entry `SKILL.md` and are not restated as optional here.

## Gold-test preflight across 4 machines

- **Capacity boundary:** This example assumes a measured safe per-host capacity
  of 6 light rows; other machines take the remaining independent rows only
  after the current host reaches that bound, not just because they are quieter.
- **Bug:** a sharded preflight passed `--max-workers 1` -> each of 4 machines
  ran its ~8 rows **serially** -> 4 concurrent total, ~7 min wall-time.
- **Token fix:** `--max-workers 3` -> 6 concurrent.
- **Right fix:** `--max-workers 6` + the heavy/light split -> **14 concurrent**.
  Light rows filled to machine concurrency; the few heavy rows still dominated
  one machine each (the real long pole).
- **To go to true all-34-at-once:** heavy rows each want a machine, so this
  needs more eligible capacity than the four already available. The worker
  count was never the real ceiling - per-item CPU and machine count were.

## Resource admission incidents

- **Crash 2026-08-30:** a harness process died silently at the instant it forked
  a 20-minute foreground CLI delegate on a host at 92% swap / memory-pressure
  WARNING / ~64MB free. The spawn itself was the kill site, and silent
  self-exits leave no OS trace.
- **False stop observed 2026-09-02:** 8.9GB/10.24GB swap + pressure=2 was read
  as "stop" under the old wording, while real available memory was 12.9GB and
  the pressure source was a steady-state 11GB Virtualization.framework VM - a
  constant that does not change whether you spawn 0 or 3 lanes. That was a
  false stop.
- macOS sizes the swapfile dynamically, so an "89% full" swapfile can coexist
  with 12+ GB available. Steady-state VMs/daemons (Virtualization.framework,
  colima, docker, qemu, lima) make the pressure structural: it will not improve
  by refusing to spawn.

## Narrow gap became a replacement framework (2026-09-26)

A 264-line capture script's narrow gap turned into an unfinished 987-line replay
adapter that itself needed correctness fixes, and still incorrectly accepted
synthetic input with no real reply, no real stream, and invented data. The
three pre-handoff checks in the entry file (hard constraints vs preferences,
direct consumers, existing evidence driver to reuse) exist to prevent this.

## Active is not progressing (2026-09-25)

Repeated "still exploring wording" updates from an active lane were mistaken for
progress while no patch landed. Related: repeated AGY relaunches and drafting
cycles dominated the critical path on changes that were a few lines each (the
reason handful-of-calls work stays in the root session).

## Collecting results failure (2026-09-07)

15 lanes all completed, direct delivery silently dropped every report, the
orchestrator re-did the analysis itself, and the original 15 reports arrived
afterwards - while the bead-comment channel had been working the entire time and
was never checked. Roughly half a session's review work was paid for twice.
