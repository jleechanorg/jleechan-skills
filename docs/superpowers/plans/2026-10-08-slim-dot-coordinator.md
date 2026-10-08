# Slim Dot coordinator design and implementation plan

## Outcome and scope

On each native scheduler wake, ping one configured Dot to advance its existing
user-authorized goals. An assigned but idle owner is not active execution. This
replaces the quiet event-only default without introducing a coordination platform.
The archived framework and its 1,000-line design are superseded, not dependencies.

## Flow and responsibilities

`launchd/systemd -> existing wrapper -> ping-dots.py -> AGY -> existing dot.sh send-once`

The wrapper owns runtime setup and start logging. The Python script selects an
account, takes the existing host lock, observes STOP and historical delivery holds,
asks AGY for one short reminder, and sends once through the existing Dot tool.
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

One AGY call has a 610-second subprocess timeout and a 600-second print timeout.
One Dot call has a 180-second timeout, with no remote forwarding or account
rotation. There is no retry loop, new ledger, journal, browser transport, process
supervisor, or semantic routing in application code. The AGY-generated message is
limited to 1,200 characters. A successful AGY exit does not prove delivery:
`sent` requires Dot exit zero and an exact `DOT_SENT_VERIFIED` output line.
A failed or uncertain send reports failure and is not retried within that run.
No new persistent receipt hold is created: future scheduled ticks remain periodic
and may send a new reminder. Inspect the transport before manually retrying an
uncertain send. A ping does not prove completion of the Dot's underlying tasks.

## Implementation checklist

- [x] Replace the existing wrapper's worker target with the small Python script.
- [x] Reuse existing account configuration, lock, STOP and Dot safety behavior.
- [x] Keep coordination judgment in the AGY prompt and Dot task owners.
- [x] Add focused fake-provider tests for selection, one send, generation failures,
  unverified receipt, STOP, historical holds, lock contention and actual caller wiring.
- [x] Independently run `python3 -m unittest discover -s tests -p test_simple_dot_ping.py -v`.
- [ ] Commit and publish the fresh branch and draft PR with exact validation results.
- [ ] Separately authorize service installation/activation and verify natural live ticks.

## Validation boundary

Focused checks prove local control flow with fake AGY/Dot executables. They do not
prove real AGY generation, browser delivery, installed service activation, or
progress across six host/account combinations. No service is installed or changed
by preparing or publishing this branch.

A real AGY transport probe on 2026-10-08 accepted the stream-JSON arguments but
returned exit 3 and `RESOURCE_EXHAUSTED` (individual quota), with zero generated
tokens. The result envelope matched the parser; generation remains unverified
until provider quota is available. No Dot call or delivery followed this probe.
