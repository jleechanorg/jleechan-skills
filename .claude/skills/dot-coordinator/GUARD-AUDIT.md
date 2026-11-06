# Seven-day guard audit

Window: 2026-10-14T05:01:25Z through 2026-10-21T05:01:25Z. Bounded source: timestamped journal entries for the three currently configured Linux coordinator units, matched to exact launcher diagnostic prefixes. Per-event timestamp, unit and invocation originals are retained privately. Undated Mac flat logs and other historical unit labels are not covered; offline tests are excluded from runtime counts.

| Observed event | Count | What it establishes |
| --- | ---: | --- |
| Shared profile flock refusal | 5 | A held kernel lock excluded a competing browser launch before it started. |
| Coordinator global flock refusal | 1 | Cross-account serialization during an existing manual read-only transport. |
| Chrome-or-stale-Singleton refusal | 65 | Mixed active/stale ownership; cannot classify all as useful collision prevention. |
| STOP skip | 14 | Reminder dispatch was suppressed; known temporary review holds outlived their protected turns. |
| Pi failure | 1 | A runner failure was reported. |
| Invocation deadline | 1 | A bounded turn exceeded its deadline. |

The five profile refusals occurred at UTC Oct17 22:30, Oct18 01:10/05:50/14:50, and Oct20 08:10. Retained owner/session binding is incomplete; no receipt proves counterfactual corruption or session damage was prevented.

An OOM-failed invocation retained its pending payload/time/binding. Read-only destination reconciliation later proved absence before a backed-up reconciliation and fresh send. This demonstrates useful recovery evidence, not a proven duplicate averted. Overlapping historical reminders separated by an acknowledgment lack message/time/run binding, so they cannot establish one process versus multiple runs or a lock failure. No exactly-once claim is supported.

The user explicitly accepted the concurrent-session and duplicate-delivery risks of removing coordinator participation in these controls. This audit does not claim they never helped. Shared browser helpers retain their own controls; coordinator source removal neither deletes live records nor activates a host transition. See MIGRATION.md for the separately approved quiescent transition.
