# Measurement already available in this repository

Inspected source: `cc1e8d6047bef8e26830491f057ae2dbc5642f6a`, on 2026-11-26.
Reuse the collectors and provenance patterns below for `/experiment-skill`.
The missing piece is orchestration: historical replay, verified instruction
exposure, a baseline reproduction gate, paired trials and independent scoring.

| Existing component | Reuse | Boundary |
| --- | --- | --- |
| [Local usage collector](../scripts/prw_local_usage.py) | Claude/Codex session IDs, model token counters, time windows and `prw-local-usage.v1` JSON | `active_sec` sums event gaps up to the idle threshold; measure run wall time separately. The feed omits prompt/response text. |
| [PR metrics](../scripts/prw_metrics.py) | Aggregation and optional usage-feed integration | PR lifecycle measurements and cached API replay do not reproduce agent incidents. |
| [Command/skill capture](../scripts/capture_command_skill_usage.py) | Scope-qualified inventories, content hashes, symlink targets and source receipts | Inventory membership alone does not establish that a trial loaded the instruction. |
| [Command/skill audit](../scripts/audit_command_skill_usage.py) | Snapshot-bound evidence and distinctions among selection, reads, reachability and unknown usage | Historical usage classification is not a causal treatment-effect estimate. |

The [skill-usage design](../docs/superpowers/specs/2026-08-27-quantifying-skill-usage-system-design.md)
separates implemented behavior from planned extensions. Use the implemented
collectors rather than treating every design section as a working interface.

## Use in an experiment

The [Harbor adapter guide](../docs/harbor-skill-experiments.md) connects these
measurement sources to incident replay and the baseline reproduction gate.

1. Assign each subject run and descendant session to an arm in a private manifest.
   Record explicit start/end timestamps, task identity and actual model/profile.
2. Collect usage for that window with `scripts/prw_local_usage.py`. Its CLI supports
   `--since`, `--until`, repeatable `--claude-root` and `--codex-root`, and `--output`.
   Use the experiment's actual log roots, then select the manifest's session IDs;
   a shared time window alone does not isolate experiment work.
3. Retain raw outputs and tool traces separately. Reuse the capture/audit source's
   hashing and receipt patterns to bind instructions to runs, and obtain runtime
   evidence of loading. Do not substitute the usage summary for these receipts.
4. Report quality and failure ratios separately from tokens, active time and wall
   time. Include invalid attempts and recovery work; identify unmeasured work.

Existing collector coverage lives in
[local usage tests](../tests/test_prw_local_usage.py),
[metrics usage tests](../tests/test_prw_metrics_usage.py), and
[capture pipeline tests](../tests/test_skill_usage_pipeline.py).
Those verify collector behavior, not the effectiveness of an edited skill.

## Historical implementation

`scripts/native_usage_collector.py` and its tests were removed in commit
`4ce6a275b`; inspect its parent for the former normalized-history receipts,
coverage windows, deduplication and partial-data handling. They are useful design
precedents, not commands available in the current checkout.

For an execution substrate, see the separate
[OSS evaluation research](agent-evaluation-tools-2026-11-26.md). Start by adapting
these existing measurement components to one reproduced incident before building
a new collector or broad evaluation service.
