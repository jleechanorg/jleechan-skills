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
   For a constructed diagnostic, `snapshot --selection /path/to/selection.json`
   can export only the relevant files. The selection object has `tree` (the
   committed tree SHA), `include` (path
   strings) and `exclude` (objects with `path` and `reason`). Use a trailing `/`
   for directory prefixes. Every tracked path must match exactly one entry;
   selecting a symlink, submodule or LFS pointer still fails. The exporter writes
   a sibling `.receipt.json` with the original commit object and complete
   tree catalog, plus selected paths and exclusions. The manifest validator
   reconstructs the Git object hashes without the live checkout. Keep this
   provenance receipt coordinator-side; it may contain private commit
   metadata and paths. This is not a full snapshot.
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
key-mode inputs are `OPENAI_API_KEY` and `CODEX_API_KEY`; it does not reuse the
caller's Codex profile. See the
[environment registry](portability-env-vars.md#harbor-experiment-execution).
The initial adapter supports single-step tasks with separate verification. It
rejects `.harborignore` and empty task directories so its local inventory and
Harbor checksum validation have an explicit, reproducible scope.
Its checksum compatibility check uses `dirhash==0.5.0`, Harbor's documented
name/data hashing protocol; pin that dependency when preparing the runtime.

### Access-only baseline

For a constructed baseline on Linux, opt in with runtime `auth_mode` set to
`codex_access_only` and agent version `0.172.0`. Provide `--codex-auth-file`
with the selected normal managed ChatGPT file and `--expected-account-fd` with
an inherited mode `0600`, write/grow/shrink/seal-sealed Linux memfd at offset zero
holding the account and a digest of the explicitly selected profile path, frozen
after review and dummy qualification. Mutable file descriptors are not accepted. This establishes
local account continuity, not external identity attestation. If the original
reference is lost, do not select a different account or infer continuity.
Neither an API key nor another account is a fallback. This mode relies on pinned Codex
implementation behavior, not a public bearer-import contract. It requires
enough access-token lifetime for the entire job plus safety margin. Harbor
receives a private temporary derivative with an empty refresh field, never the host
refresh grant or a mounted profile. Do not use logout to clean up the copy.
For access-only jobs, `runtime.timeout_sec` is per attempt; the whole-job
budget is 60 seconds plus the number of concurrency waves times the attempt
timeout plus 180 seconds for per-wave setup, verification and drain.

Before any live run, qualify the immutable image, the native Codex shim and
the restricted inference route (including blocked refresh and revoke routes)
with dummy credentials. Record the Harbor virtualenv identity as
`harbor_install_sha256` in the qualification record. It binds the resolved
launcher and interpreter, virtualenv configuration, and installed package
bytes and modes. Access-only runs invoke the launcher with the verified
virtualenv interpreter in isolated mode with the normal bytecode cache disabled,
not through its shebang. The adapter checks the installation before delivering
the derivative. Keep the qualified virtualenv stable.
Acquire raw logs in a private `0700` holder under `/dev/shm`. The trusted host
may have active swap; there is no swap-free or forensic-erasure guarantee.
Only publish a separate sanitized release after writers and scoped Docker resources
are gone and the private acquisition is removed. The access-only seal requires
paired lifecycle events for each observed writer, using container IDs captured
by a per-job live Docker event listener started before Harbor. It checks
remaining container bind mounts, including mounts from outside the run's naming
prefix, and checks the identities of volumes mounted by scoped containers even
when the volumes have no Compose labels. An incomplete event pair, a failed listener, or a live mount withholds
the acquisition rather than treating an empty name search as cleanup. The adapter
unlinks the derivative when Harbor returns control, before waiting for the Docker
seal. Once its process group and descendants are drained, a failed seal triggers
a bounded reconciliation of Docker resources whose Compose project labels prove
ownership in the qualified daemon. It verifies namespace and bind-mount absence
again. A single deadline starts when Harbor returns and covers the event fence,
Docker checks and reconciliation, staging, and private removal; no scoring
release is published after it expires. Reconciliation never upgrades an unsealed
acquisition to a scoring release. An unsealed
acquisition or failed removal identifies only the local private recovery
basename if a private holder remains. The supervisor records the exact resolved output and the actual
launcher/process scope before launch. If the launcher dies without a receipt,
`access_holder(experiment.case_sha256)` locates the same holder. Resolve its actual
`acquisition-<UUID>` child before calling `staged_name(experiment, acquisition)`
to identify the corresponding Docker scope. A retained holder
prevents a new acquisition of the same case even with a different output directory.
Record that attempt as unsealed, never recover
it as a scored release, and confirm exact process and Docker quiescence before
removing the named derivative and private holder. Leave unknown scope isolated.
Unexpected acquisition files, nonempty private home or work directories,
and unrecognized output roles cause withholding regardless of the file suffix.
Unframed JSON records are not accepted as plain diagnostic logs. Native MCP
results are checked for split values in structured content as well as text.
The release checks known
token values and supported serializations, not arbitrary encodings by a
hostile subject. Check the native session's provider tag independently of the
configured model label. Account matching before launch is not a provider
attestation: qualification must prove that the isolated process can use only
the matched derivative, including when it receives a provider 401. A native
execution error invalidates the attempt even if later output claims success;
a 401 reported by the controlled permission fixture is ordinary tool evidence.
Post-run inventory limits do not cap the growth of the live job tree. Bound private storage during actual
qualification; a healthy disk before launch is not a live storage quota.
Invalid attempts are excluded
from observed matches; retain and report the incomplete fixed cohort instead
of miscounting infrastructure failures or substituting extra attempts. A
successful Harbor process with missing or quarantined released results is an
incomplete release and the `run` command exits nonzero.
Any treatment field used only to satisfy the comparison schema is reserved
and unrun; access-only manifests cannot launch treatment.
Bind the qualification to the approved code bundle (`code_bundle_sha256`),
the local Docker server ID and the exact local image
IDs used in both `environment.docker_image` and
`verifier.environment.docker_image`. Access-only runs use the default local
Docker socket and Harbor's standard Compose definitions without rebuilds.
The access-only manifest also includes `launch_policy`, a `{path, sha256}`
reference to a reviewed `experiment-launch-policy.v1` record. Its `cases`
map keys each case by `incident_id`; each entry binds `arm: "baseline"`, the
exact manifest `runtime` object and the baseline `trials` count. Include this
same reference in `code_files` before review. The generic adapter does not
choose campaign settings.
The qualification also records `docker_client_sha256` (the resolved Docker
and Compose paths and bytes), `egress_image_id` (the Harbor-computed sidecar
tag's qualified target), and `codex_binary_sha256`. Before delivery, verify
the client chain, sidecar target and executable hashes inside the immutable
agent image. Before upload, the Harbor job hook checks the actual running main
and sidecar image IDs, shared network namespace and sidecar health. The recorded
container IDs must also match the sealed Docker lifecycle. The host observes
the actual verifier start and checks its immutable image, isolated network,
scoped verifier-log mount and lack of auth environment variables. The sidecar tag must
still resolve to the same image after drain.
The local Docker event subscription remains open through descendant drain. Two
disposable, uniquely named local volume lifecycle events bound the event stream;
a missing end boundary withholds the run's private acquisition.
Install the reviewed `scripts/harbor_codex_egress.py` into the task-owned
Harbor virtual environment, not on `PYTHONPATH` (the job uses isolated mode):

```bash
site_dir=$("$HARBOR_VENV/bin/python" -I -B -c 'import sysconfig; print(sysconfig.get_path("purelib"))')
install -m 0644 scripts/harbor_codex_egress.py "$site_dir/harbor_codex_egress.py"
cmp scripts/harbor_codex_egress.py "$site_dir/harbor_codex_egress.py"
```
Pin `network_mode = "no-network"` for environment setup and both verifier
settings, and the agent-phase allowlist to `chatgpt.com`. The immutable agent
image must install the Codex shim at `/usr/local/bin/codex`. Set
`environment.healthcheck.command` to `/usr/local/bin/codex --harbor-check-denied`
with `retries = 1`: Harbor checks the setup network before agent setup and
credential delivery. Before Harbor uploads auth, the launcher checks the live
container namespace, confirms the initial deny policy, and reads back the
effective allowlist for the single approved host. The shim checks the TLS route again after Harbor switches
to the agent-phase policy and before starting Codex. Those probes are not a
proof of all protocols or routes; the qualification must also check Harbor's
egress implementation and test actual isolation independently, without secrets.
The staged task name provides the Docker cleanup namespace even if Harbor
does not write trial metadata. The trusted supervisor uses
`freeze_account_descriptor` on the selected managed file and passes the frozen
descriptor to the runner without putting its contents on the command line:

```sh
python3 scripts/harbor_experiment.py run /path/to/case/manifest.json --arm baseline --output /path/to/new-baseline-run --codex-auth-file /path/to/authorized/auth.json --expected-account-fd 3
```

The standard paired command sequence is:

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

An exposure reward alone is insufficient. Bind the verifier-owned observation
to the case, arm, run, expected instruction hashes, native trajectory and
supporting evidence. A file merely existing in the container or a subject
claiming to have read it does not prove exposure.

The adapter supplies `HARBOR_EXPERIMENT_CASE_SHA256`, `HARBOR_EXPERIMENT_ARM` and
`HARBOR_EXPERIMENT_RUN_SHA256` through Harbor's verifier-only `--verifier-env`
options. The reviewed verifier reads these values and writes
`verifier/exposure-observation.json`. The run hash covers the complete manifest
hash, arm and resolved new run directory. The case hash covers frozen experimental
inputs. `plan` prints placeholders for the run directory and its hash.

Collection checks the exact persisted verifier overrides. Standard runs retain
the unmodified observation and trajectory and bind their hashes and the result
hash to Harbor's job/trial UUIDs. Access-only runs check the raw observation
and its references against the sealed raw bytes in private storage. The
separate verifier receives only the credential-free native witness and fixture
events; the host independently checks the complete workspace instruction body
and task prompt in the native first root turn, not just their file hashes.
Catalog entries do not prove that any selected skill body was shown to the model.
The release includes projected
Harbor records without raw diagnostics, validated trajectories, and evidence
with hashes of the released bytes. Fixture events are withheld if sanitizing
them would change their bytes. The released completion record indicates
whether raw observation-to-rollout validation passed. The first-turn witness
binds that observation to a rollout digest; it does not release raw acquisition
bytes or let a later reader reconstruct or revalidate them.
An unsafe trial is withheld with a nonsecret marker and cannot count as valid;
other trials whose sanitized artifacts pass validation remain available.
Container cleanup is checked for every writer that started. A trial without a
complete agent/verifier lifecycle and a matching live egress receipt cannot
publish a result, but does not invalidate quiescent, qualified siblings.
An ordered, typed projection of the verified native rollout is the scoring
trace. Native ordinals refer to positions in the private source, not rows in
the projection. It includes observed tool calls, process outcomes, the output
actually shown to the model, assistant messages, and the terminal answer. A
truncated model-visible response does not establish that the model saw the
omitted part of the full process output. A command poll is bound to its
originating native process; it does not create a second execution result.
Continuation chunks are released only when their order and untruncated
contents match the execution result. Unqualified tool event forms withhold
the trial rather than representing an incomplete trace as a behavioral result.
Raw instruction bodies and native reasoning records are not released. If masking
would change a retained observation, that trial is withheld instead of treating
altered evidence as scoreable. Raw stdout/stderr, the
native CLI stream, optional Harbor logs and its derived ATIF copy stay on the
acquisition side; use the native CLI stream to validate lifecycle before release.
The staged task stays private too. The launch binds its pre/post inventories;
staged file bytes, including verifier-only inputs, do not enter the scoring release.
Incomplete native streams cannot prove tool actions.
The verifier receives the credential-free run, Harbor trial UUID, and native
thread binding through the private witness. Duplicate observations
or native trajectories cannot count as independent trials; identical
final-answer text alone is not a duplicate trace.

An access-only case must stage a private `tests/detector.md`, which must
remain out of the agent image, prompt, and mounts. Its separate verifier returns
only `exposure_verified`. After safe release, an independent grader reads the
frozen detector and sanitized native trace; `collect --adjudications PATH`
binds the result without changing Harbor output. The `harbor-semantic-cohort.v1`
object has `case_sha256`, `arm`, `launch_sha256`, `adjudicator`, and `trials`.
Each trial record carries `trial_id`, `result_sha256`, `trajectory_sha256`,
`detector_sha256`, a `VALID` verdict, evidence line numbers in the sanitized
JSONL, and binary `incident_failure`, `task_completed`, and `regression_failed`
under `metrics`. When citing fixture events, include `fixture_evidence` with
the released TSV's `sha256` and 1-based `lines`. Missing, invalid or mismatched judgments never enter the
denominator. The collector checks evidence identity and line bounds, not the
grader's semantic judgment or independence; retain the grader's output separately.
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
separately. For the standard paired mode, preserve raw traces alongside
privacy-preserving usage summaries. In access-only mode, preserve only the
validated sanitized release; unsealed acquisition has an unknown trial census.

Read the [measurement inventory](../research/skill-measurement-prior-art-2026-11-26.md)
for existing collectors and the [OSS comparison](../research/agent-evaluation-tools-2026-11-26.md)
for the Harbor choice. The shared
[experiment skill](../.claude/skills/experiment/SKILL.md) owns scoring, blinding
and retention; [experiment-skill](../.claude/skills/experiment-skill/SKILL.md)
owns historical incident selection and instruction-exposure requirements.
