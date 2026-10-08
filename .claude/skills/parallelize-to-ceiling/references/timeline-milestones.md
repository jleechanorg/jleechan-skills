# Timeline, parallel lanes, and milestone reports

Required on every `/plan-micro`, `/nextsteps`, `/parallel`, and `/planexec` run.

## Always publish a timeline and lane design

Include a compact timeline in both the user-facing output and any plan or
handoff artifact the command already requires. Estimate elapsed start/end
windows, deliverables, dependencies, lane owners, and completion evidence.
Identify the critical path and distinguish estimates from observed completion.
For short work, one row and the final completion report are sufficient.

Design as many useful independent parallel lanes as possible. Follow
`${CLAUDE_HOME:-$HOME/.claude}/skills/parallelize-to-ceiling/SKILL.md` for resource admission,
isolation, and live concurrency proof. State the independent lane count,
measured runnable ceiling, planned simultaneous count, and the binding limit.
When future execution capacity cannot yet be measured, label the ceiling
provisional and require a fresh admission check before launch.

Give each lane an owner, bounded scope, exclusive write files or workspace,
prerequisites, expected output, and verification handoff. Keep every ready lane
running up to the measured ceiling; refill freed slots and reassess the DAG as
work completes. Serialize only actual dependencies, shared-state conflicts,
or measured resource/tool limits, and name the reason. Task complexity or
length alone does not justify serial execution. Do not invent work, duplicate
lanes, expand scope, or provision paid resources without existing authority.

## Every 20 minutes, with an hourly rollup

Record the active workflow start time and next report deadline. During active
work, send a milestone update at elapsed 20, 40, 60 minutes, then every 20
minutes thereafter. At 60, 120, 180 minutes, and each later hour, combine that
20-minute update with an hourly rollup; do not send duplicate reports.

- Each 20-minute update: elapsed time, completed deliverables with observed
  evidence, running/blocked lanes, current concurrency versus the ceiling,
  timeline changes, and the next 20-minute milestone.
- Each hourly rollup also: planned versus actual progress over the hour,
  verified outcomes, critical-path changes, remaining estimate, and milestones
  for the next hour.

These are non-blocking progress reports, never approval checkpoints. Continue
the next authorized action without asking. Preserve any faster runtime progress
cadence. Use asynchronous jobs and bounded monitoring so long tool calls do not
silence reporting; if a deadline is missed, report at the first opportunity,
state the delay, and retain the original schedule. Resume from the recorded
start/deadline after a checkpoint rather than resetting the clock.

Finish promptly when done, including before 20 minutes; never wait to fill a
reporting interval. No updates are promised after the active run ends or while
awaiting required user approval. A plan-only or stopped-work handoff records
future milestones relative to execution start and this reporting contract; it
does not start implementation, create a daemon, or resume paused work.
