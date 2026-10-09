# Slim Dot coordinator design and implementation plan

## Outcome and scope

On each native scheduler wake, ping one configured Dot to advance its existing
user-authorized goals. An assigned but idle owner is not active execution. This
replaces the quiet event-only default without introducing a coordination platform.
The archived framework and its 1,000-line design are superseded, not dependencies.

## Flow and responsibilities

`launchd/systemd -> existing wrapper -> ping-dots.py -> AGY -> Codex Luna -> Claude Haiku 5.5 -> existing dot.sh send-once`

The wrapper owns runtime setup and start logging. The Python script selects an
account, takes the existing host lock, observes STOP and historical delivery holds,
tries AGY, Codex Luna, and Claude Haiku 5.5 in order for one short reminder, then
sends at most once through the existing Dot tool. A failed or invalid provider
response advances to the next provider; a Dot send result never does.
Dot and its existing task owners decide and execute the next safe actions. The
reminder asks them to verify actual progress, resolve reversible blockers, use
cloud coders for independent work, and route unavailable or quota-limited executors
to another authorized executor. It preserves deliberate pauses, cancellations,
ownership, and real approval boundaries; it creates no new authority.

## Inputs and cadence

Read the existing Dot configuration, with exactly three distinct rotation keys.
For rotation positions 1/2/3, Mac runs at :00/:20/:40 and Linux at :30/:50/:10.
The existing Mac launchd template is retained; Linux's timer wakes at :10/:30/:50.
Only the due slot within two minutes executes; missed slots are not replayed.
An explicit `--account <configured-key>` selects one account for an authorized run.
Existing state and transport overrides support isolated focused tests.

## Bounded execution and observable results

Each generator call has a 180-second subprocess timeout. Codex writes its final
plain-text response to a temporary file; Claude runs without session persistence
or tools. One Dot call has a 180-second timeout, with no remote forwarding or account
rotation. There is no retry loop, new ledger, journal, browser transport, process
supervisor, or semantic routing in application code. The generated message is
limited to 1,200 characters. A successful generator exit does not prove delivery:
`sent` requires Dot exit zero and an exact `DOT_SENT_VERIFIED` output line.
A failed or uncertain send reports failure and is not retried within that run.
No new persistent receipt hold is created: future scheduled ticks remain periodic
and may send a new reminder. Inspect the transport before manually retrying an
uncertain send. A ping does not prove completion of the Dot's underlying tasks.

## Implementation checklist

- [x] Replace the existing wrapper's worker target with the small Python script.
- [x] Reuse existing account configuration, lock, STOP and Dot safety behavior.
- [x] Keep coordination judgment in the model prompt and Dot task owners.
- [x] Try AGY, Codex Luna, and Claude Haiku 5.5 in order; never send until one
  returns a valid plain-text reminder.
- [x] Add focused fake-provider tests for selection, one send, generation failures,
  unverified receipt, STOP, historical holds, lock contention and actual caller wiring.
- [x] Independently run `python3 -m unittest discover -s tests -p test_simple_dot_ping.py -v`.
- [x] Commit and publish the fresh branch and draft PR with exact validation results.
- [x] Install and activate the native Mac and Linux schedules; verify a natural tick on each host.

## Validation boundary

The focused fake-provider tests prove control flow, not live delivery or task
completion. On both Mac and Linux, the installed wrapper separately generated
messages through AGY, Codex Luna, and Claude Haiku 5.5 using `--generate-only`.
AGY quota was intermittent; the automatic path fell through after quota errors.
Native schedules were active and produced natural ticks on both hosts. Exact
delivery and readback were verified for two Mac accounts and one Linux account;
not all six host/account combinations were delivered. No task completion is
claimed from a reminder delivery.
