# Reproduce a skill failure with Harbor

Use this adapter to compare two instruction versions against one frozen incident.
Harbor runs the agent and verifier; the adapter checks experiment records,
preserves trial evidence and prevents treatment before baseline reproduction.
Each incident has its own manifest. Retain unsuccessful reproduction attempts.

The first campaign needs two independent design approvals and two independent
code approvals. Prepare the incident and qualify its container environment before
launching either arm. An approval of the adapter does not approve an unspecified
task fixture.

## Prepare the case

1. Recover the original request, repository state, instruction layers, runtime,
   dependencies and external-state fixtures from before the failed action. Record
   recovered, reconstructed and missing material separately. Only a complete
   recovered inventory supports the `captured` classification.
2. Export the evidenced full Git commit into a new task-owned directory. Preserve
   dirty and untracked incident inputs as separate, hashed evidence; do not copy
   today's live checkout and call it the historical state. The export command
   rejects unsupported symlinks, submodules and LFS pointers.
3. Build paired Harbor tasks with the same prompt, runtime settings, fixtures,
   verifier and regression criteria. Declare the instruction files that change.
   The adapter's initial scope is instruction-only comparisons; use the general
   experiment workflow for a broader code/runtime intervention.
   Referenced Markdown instructions are included when declared and exposed.
4. Freeze at least five trials per arm, equal trial counts, explicit model and
   reasoning effort, exact Codex version, concurrency and timeout. Preserve the
   complete task trees and executable modes.
5. Record the coordinator's packaging acceptance and container qualification.
   Both bind to the exact case. Qualification records actual per-arm agent and
   verifier image digests, input isolation, hidden answers, network restrictions,
   credential separation, arm separation and supported cleanup.

Select a commit by evidence of what the agent used, not merely by its date before
a complaint. A local simulation of historical API responses is useful, but its
classification must reflect which original inputs were recovered.

## Execution and evidence

Run `python3 scripts/harbor_experiment.py --help` from the skills checkout for the
adapter's command interface. `plan` validates and prints commands without
starting Harbor. `snapshot` reads a pinned Git commit and writes a new export.
`run` is the only trial-launching command; `collect` reads retained results.

The adapter requires Python 3.11+; trial launching uses POSIX process groups.
Harbor v0.25.0 must be available on PATH for execution, with a working supported
container environment. The adapter uses Harbor's installed Codex agent and
passes the pinned model, agent version, effort, attempts and concurrency.
Installing the CLI alone does not establish container or provider readiness.
The launcher uses an isolated child home and working directory. Its supported
provider authentication inputs are `OPENAI_API_KEY` and `CODEX_API_KEY`; it does
not reuse the caller's Codex profile. See the
[environment registry](portability-env-vars.md#harbor-experiment-execution).
The initial adapter supports single-step tasks with separate verification. It
rejects `.harborignore` and empty task directories so its local inventory and
Harbor checksum validation have an explicit, reproducible scope.
Its checksum compatibility check uses `dirhash==0.5.0`, Harbor's documented
name/data hashing protocol; pin that dependency when preparing the runtime.

The command sequence is:

```sh
python3 scripts/harbor_experiment.py snapshot --repo /path/to/incident-repo --commit FULL_COMMIT_SHA --output /path/to/new-snapshot
python3 scripts/harbor_experiment.py plan /path/to/case/manifest.json
python3 scripts/harbor_experiment.py run /path/to/case/manifest.json --arm baseline --output /path/to/new-baseline-run
python3 scripts/harbor_experiment.py collect /path/to/case/manifest.json --arm baseline --run /path/to/new-baseline-run --output /path/to/baseline-receipt.json
python3 scripts/harbor_experiment.py run /path/to/case/manifest.json --arm treatment --baseline /path/to/baseline-receipt.json --output /path/to/new-treatment-run
python3 scripts/harbor_experiment.py collect /path/to/case/manifest.json --arm treatment --run /path/to/new-treatment-run --output /path/to/treatment-receipt.json
```

Replace paths with case-owned locations and `FULL_COMMIT_SHA` with the evidenced
40-character commit. Prepare the manifest and its receipts before `plan`;
the commands above do not manufacture missing approvals or fixtures.

Use a separate verifier environment. Its reviewed detector must distinguish the
reported behavior from missing dependencies, provider failures and unavailable
fixtures. It records five binary metrics:

| Metric | Meaning |
| --- | --- |
| `valid` | Required setup and execution completed. |
| `incident_failure` | The exact frozen incident detector matched. |
| `exposure_verified` | Native instruction-loading evidence was verified. |
| `task_completed` | Shared task acceptance criteria were met. |
| `regression_failed` | A frozen regression criterion failed. |

An exposure reward alone is insufficient. Retain the verifier-owned observation,
case/arm/run identity, expected instruction hashes, raw trajectory digest and
supporting evidence. A file merely existing in the
container or a subject claiming to have read it does not prove exposure.

The adapter supplies `HARBOR_EXPERIMENT_CASE_SHA256`, `HARBOR_EXPERIMENT_ARM` and
`HARBOR_EXPERIMENT_RUN_SHA256` through Harbor's verifier-only `--verifier-env`
options. The reviewed verifier reads these values and writes
`verifier/exposure-observation.json`. The run hash covers the complete manifest
hash, arm and resolved new run directory. The case hash covers frozen experimental
inputs. `plan` prints placeholders for the run directory and its hash.

Collection checks the exact persisted verifier overrides, validates the raw
observation and its referenced bytes, then adds a host-side record containing
Harbor's job/trial UUIDs, the result hash and the raw observation hash. It leaves
the job's raw files unchanged. The verifier needs no access to Harbor's internal
UUID. Duplicate raw observations or native trajectory hashes cannot count as
independent trials; identical final-answer text alone is not a duplicate trace.
The record's `qualified_images` comes from qualification evidence for the frozen
configuration and is not a claim of per-trial image inspection.

Only a complete valid baseline with at least one matching failure unlocks
treatment. A baseline without the failure is `NOT_REPRODUCED`; missing or invalid
trials leave it `INCOMPLETE`. Preserve the results and investigate the specimen
before creating a separately recorded attempt. The adapter rechecks retained
baseline evidence instead of trusting an editable status label.

Do not use production PR writes, live messages or deployments as repeated task
actions. Package controlled PR-tool fixtures and qualify their boundaries.
Hosted models still require their authorized network connection; disabling all
network access also prevents hosted inference.

## Approval and qualification records

Keep manifests, evidence and receipts in authorized task storage. File references
are content-hashed and remain within the manifest's directory. The adapter
validates recorded identities and content; the coordinator establishes who
reviewed the work and whether qualification evidence supports its claims.

Each design/code phase needs two independent cold reviewer seats covering its
entire bundle. Their recorded output must approve the same bundle as the review
record. A hash of an unrelated receipt, an acknowledgement or a partial review
cannot approve a run. Changes to reviewed files invalidate the affected binding.
The initial receipt format accepts the exact terminal line
`VERDICT: APPROVED at DOCUMENTS sha256:<bundle>` from a complete saved-source
review. A bare revision approval needs a separately verified mapping and is not
accepted by this adapter version.

Packaging and qualification are case-specific coordinator records. They are
trusted host-side attestations backed by referenced evidence, not cryptographic
proof of an AI review or automatic proof of Docker isolation. Subjects must be
unable to modify these records or access hidden answers. Preserve failures and
unverified cleanup explicitly; killing a local process does not prove its
containers have exited.
Qualification must examine the actual Harbor backend and mount configuration,
not infer isolation merely from selecting a separate verifier environment.
The collector also rejects pinned Harbor Docker shutdown failure diagnostics in
the retained host `trial.log`. `harbor_completed` means no detected incomplete
process or cleanup signal; it does not certify container absence.

## Manifest and receipt fields

The manifest schema is `harbor-skill-experiment.v1`. Every file reference contains
`path` and `sha256`. Directory identities hash a sorted inventory of relative
POSIX paths, content hashes and executable bits. JSON hashing uses sorted keys,
compact separators and UTF-8. Review bundle inventories are sorted by path.

| Field | Content |
| --- | --- |
| `incident_id`, `incident_kind`, `incident_source` | Stable case ID, `captured` or `constructed`, and the source reference. |
| `repository_commit`, `snapshot` | Historical full SHA and hashed source export. |
| `baseline_task`, `treatment_task` | Hashed Harbor task directories. |
| `intervention_paths` | Changed instruction files within the task environment; all other task content matches. |
| `runtime` | Harbor version, agent and exact version, model, effort, concurrency and timeout. |
| `trials` | Equal baseline/treatment counts, at least five per arm. |
| `design_files`, `code_files` | Complete reviewed file inventories, including the executing adapter. |
| `reviews` | Phase, reviewer ID, verdict, bundle hash and hashed review receipt. |
| `provenance`, `packaging`, `qualification` | Hashed case-specific records described below. |

Required record schemas:

- `experiment-review.v1`: phase, reviewer ID, approval verdict, bundle hash and
  the hashed original review output. Reuse of a reviewer across phases requires
  distinct phase-bound records; a design vote does not approve code.
- `experiment-provenance.v1`: incident ID, repository commit and an input inventory
  for original request, source state, instructions, runtime, dependencies and
  external state. Each category records its recovery status and evidence.
- `experiment-packaging.v1`: coordinator reviewer ID, `READY`, the case hash and
  supporting evidence references.
- `experiment-qualification.v1`: `READY`, the case hash, per-arm image identities
  and evidence for each required isolation/cleanup check.
- `experiment-exposure-observation.v1`: verifier-owned arm/case/run bindings,
  instruction hashes and trajectory/evidence references.
- `experiment-exposure.v1`: the host-side record binding that validated observation
  to Harbor's job/trial IDs, result bytes and qualified image identities.

The case hash includes incident metadata, source/task identities, interventions,
runtime, trial counts and provenance. It excludes review bundles, review records,
packaging and qualification references to avoid a recursive hash. Reference-only
incident metadata still participates in this hash. Use the adapter's definitions
and behavioral tests as the exact serialization contract.

## Measure the result

Report failure counts as X/N, all invalid trials, completion and regression
outcomes separately from token and time measurements. These initial trials are
descriptive. Selecting cases because the baseline reproduced does not support a
general causal efficacy claim; reserve independent confirmation tasks for that.

Use Harbor trajectories and timestamps for the trial record. The existing
[local usage collector](../scripts/prw_local_usage.py) can provide Claude/Codex
session token counters with `--since`, `--until`, explicit `--codex-root` or
`--claude-root`, and `--output`. Select only session IDs assigned to the run,
including its descendants. A shared time window can include unrelated work.
`active_sec` estimates activity from event gaps; measure elapsed wall time
separately. Preserve raw traces alongside privacy-preserving usage summaries.

Read the [measurement inventory](../research/skill-measurement-prior-art-2026-11-26.md)
for existing collectors and the [OSS comparison](../research/agent-evaluation-tools-2026-11-26.md)
for the Harbor choice. The shared
[experiment skill](../.claude/skills/experiment/SKILL.md) owns scoring, blinding
and retention; [experiment-skill](../.claude/skills/experiment-skill/SKILL.md)
owns historical incident selection and instruction-exposure requirements.
