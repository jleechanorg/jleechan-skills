# Scheduled PR metrics collector memory

## Outcome

Refresh the dashboard and retained telemetry without holding the complete decoded usage history and all its intermediate representations in Python memory.

## Non-goals

Changes to attribution rules, rate calculations, the dashboard schema, retention windows, or the publishing schedule are outside this change.

## Acceptance

- Preserve event selection, first-seen ordering, deduplication, pricing, and dashboard output on matched replay inputs. Ignore generated timestamps and the code version when comparing dashboard output.
- Reduce peak resident memory on a matched test with overlapping retained windows. Record wall time alongside memory so the tradeoff is visible.
- Commit the same telemetry bytes for valid inputs, reject corrupt retained shards, and propagate publication failures without committing an incomplete update.
- Before activating this release on the scheduler, measure memory, wall time, and temporary disk use on a production-sized offline replay with both history feeds and retained telemetry.

## User story

The dashboard operator can run the scheduled refresh on a shared machine without the collector holding the entire decoded history in memory. Dashboard readers see the same data for the same inputs.

## Proof plan

Run the focused and contract suites and compare offline replay results before and after the change. Exercise the real publisher against a disposable local Git remote. Record fixture size, revision, command, peak RSS, output parity, and limitations. Evaluate the production-sized inputs separately before scheduler activation.

## Mock

The change has no visual design. Existing dashboard output comparison covers its display-data contract.

## Risk

Disk-backed staging increases temporary I/O and storage. Human records, PR metadata and DuckDB still consume resident memory. Review shard validation and publication carefully because they protect retained history.
