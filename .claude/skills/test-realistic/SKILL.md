---
name: test-realistic
description: Project-agnostic realistic-user-testing skill. Converts any target (freeform text prompt, PR # or branch diff, commit SHA, or a project's own doc-target class) into a model-authored player scenario, dispatches a REAL multi-persona browser+LLM player swarm (via a per-project dispatch command), and verifies captured turns against a real anti-false-green coverage judgment. Requires a per-project .test-realistic.toml config contract -- this skill itself contains zero project names, ports, or paths. Use for /test-realistic, realistic end-to-end user testing, or building a coverage-judge-backed real-browser test harness for a new project.
---

# /test-realistic (generalized)

End-to-end, real-infrastructure user testing: real local server, real
browser, real LLM calls at every judgment point. There is no mock mode and
no template fallback anywhere in this pipeline -- that is the entire point.
If any model call in this pipeline fails, the run fails loud (non-zero exit),
it never silently substitutes a keyword heuristic or a canned verdict.

**Provenance**: this generalizes the pipeline design of an existing
production `/test-realistic` harness -- see `PROVENANCE.md` for the source
lineage. Nothing project-specific from that source was carried over; every
value a project needs is supplied by its own `.test-realistic.toml`.

## Before you can use this skill: write a project config

Every project MUST have a `.test-realistic.toml` at its repo root (or any
ancestor of the directory you invoke from -- `config.find_config_path` walks
up, like git). There is no built-in default project. See
`examples/test-realistic.example.toml` for a fully-annotated EXAMPLE
(clearly labelled, not read by any code path).

Required fields (fails loud with `ConfigError` if any is missing):

| Field | Meaning |
|---|---|
| `project_name` | Label used in verdict artifacts |
| `repo_root` | Absolute or config-relative path to the project's repo root (used for `gh`/`git` context fetching and relative-izing artifact paths) |
| `base_url` | The URL surface under test (e.g. your local dev server) |
| `feature_surface_vocabulary` | This project's own equivalent of a "renderer field allowlist" -- the list of `rendered.*`/`parsed.*` (or your own naming) field paths the model may cite as `relevant_surfaces` when classifying a target. Grounded in your app's REAL turn-capture shape, never invented. |
| `dispatch_command` | Argv template (list of strings) for YOUR project's real player-swarm dispatcher. Supports `{pool}` `{scenario}` `{output_root}` `{mode}` `{base_url}` `{turns}` `{backend_url}` `{repo_root}` placeholders. |

Optional fields (see `scripts/config.py` for full validation and defaults):
`backend_url`, `personas` (defaults to 5 generic QA archetypes), `actor_fixtures`
(your project's equivalent of selectable player characters, if any),
`capture_glob` (default `agent-*/capture.jsonl`), `output_root_default`,
`doc_target_patterns` + `doc_dispatch_command` (if your project has its own
docs-to-invariants-style generator for a documentation-driven target class),
`turns_default` (default 15), `agy_model`, `agy_timeout_seconds`,
`runner_excuse_predicate` (a `module:function` hook to excuse a non-zero
dispatch exit under conditions YOUR project defines -- see
`scripts/target_scoped_run.py`'s module docstring).

### The one contract your dispatch_command MUST satisfy

Your dispatcher is responsible for ALL of the app-specific plumbing: booting
or connecting to your real local server, driving a REAL browser (Playwright,
Aside, or your own), making REAL LLM calls to decide what a player-persona
does at each turn, and writing one capture file per agent under
`--output-root` matching `config.capture_glob` (default
`agent-*/capture.jsonl`), one JSON turn-record per line, each line a JSON
object (no required key names -- `feature_coverage_judge.py` accepts any
dict shape). This skill never inspects HOW you did that -- only that
captures exist afterward. No mocks anywhere in this chain: a capture file
produced without a real browser and a real model call is not evidence, it's
theater, and the coverage judge downstream will have nothing real to grade.

### Onboarding a new project: verify your adapter first

Before your first real scenario run, sanity-check that `dispatch_command`
actually satisfies the contract above -- no real model call, just "argv in,
capture.jsonl out":
```bash
python3 "${CLAUDE_HOME:-$HOME/.claude}/skills/test-realistic/scripts/verify_adapter.py" --config <path/to/.test-realistic.toml>
```
This dispatches your real command against a trivial fixture pool/scenario
and checks: at least one file matches `capture_glob`, every line parses as
JSON, every parsed line is a non-empty object. It never calls
`feature_coverage_judge`, so it's a fast, cheap way to catch a broken
adapter (wrong output path, empty captures, malformed JSON) before spending
a real coverage-judge model call diagnosing the same problem indirectly.

## Who does what (model vs. code) -- unchanged from the source design

| Step | Owner | Why |
|---|---|---|
| Doc-path target detection (only if `config.doc_target_patterns` is set) | **CODE** (mechanical regex match) | Pure structural shape check, never judgment. Absent config, always returns "not a doc target" and every input flows through the model-delegated path below. |
| Target-type disambiguation among PR # / commit SHA / freeform prompt | **MODEL** (call #1, `classify_and_summarize`) | Genuinely ambiguous judgment -- a bare number could be a PR # or an unrelated mention. |
| Fetching raw context (`gh pr view`, `git show --stat`) | **CODE** | Shape/existence checks select WHICH fetcher to try -- mechanics, not meaning classification. Works against any `gh`/`git`-hosted repo, unchanged. |
| Scenario step authoring (3-5 `user_action`/`expected_render` beats) | **MODEL** (call #2, `author_scenario_steps`) | Must be grounded in the raw diff/prompt text just fetched. |
| `feature_summary` derivation | **MODEL**, its own call, NEVER supplied via `--from-json` | Must be independent of any later self-grading -- the coverage judge compares captured turns against this exact string. |
| Predicate reuse-vs-author decision | **MODEL**, recorded on the generated scenario's `PREDICATE_DECISION` | Correctness signal; non-blocking in v1 (matches source design). |
| Schema/structural validation of authored JSON | **CODE** | Pure shape conformance. |
| `relevant_surfaces` membership check | **CODE**, against `config.feature_surface_vocabulary` | Set-membership, enforced both in the JSON-schema `enum` and an explicit check. |
| File emission (scenario `.py`, `pool.yaml`) | **CODE** | Deterministic templating, zero judgment. |
| Swarm dispatch | **YOUR PROJECT'S dispatch_command** | Real infra you own -- this skill never vendors or reimplements it. |
| Coverage judgment (did the swarm capture actually touch the feature) | **MODEL** (`feature_coverage_judge.judge_feature_exercised`) | The load-bearing anti-false-green gate -- "was this feature exercised" is exactly the judgment class ZFC reserves for models, never a keyword/token heuristic. |

## Workflow

### Step 1: Unit-test gate (always run first, zero model calls, zero network)
```bash
python3 -m pytest "${CLAUDE_HOME:-$HOME/.claude}/skills/test-realistic/tests" -q
```
The model seam (`llm_callable`) is stubbed in every unit test. This proves
the harness's own mechanics (batching, retry, validation, verdict
aggregation) without spending a real model call.

### Step 2: Generate (model-delegated, three real model calls)
```bash
python3 "${CLAUDE_HOME:-$HOME/.claude}/skills/test-realistic/scripts/scenario_generator.py" "<TARGET>" --output-dir <path> [--config <path/to/.test-realistic.toml>]
```
`<TARGET>` is a freeform prompt, a PR number, a commit SHA, or (if your
project configured `doc_target_patterns`) a doc-target id. On malformed
model output: exactly one bounded retry, then a hard non-zero exit -- no
template fallback of any kind.

Output: `<output-dir>/generated_<slug>.py` (carries `FEATURE_SUMMARY`,
`RELEVANT_SURFACES`, `PREDICATE_DECISION`) and
`<output-dir>/generated_pool_<slug>.yaml`.

#### `--from-json` short-circuit (session-authored scenario, NOT session-authored feature_summary)
An in-session agent that already has full target context may author the
classification+steps JSON itself and hand it off:
```bash
python3 scenario_generator.py "<TARGET>" --from-json <payload.json> --output-dir <path>
```
This performs zero subprocess calls for step authoring, but STILL makes one
fresh model call to derive `feature_summary` -- any `feature_summary` key in
the payload is discarded. This anti-self-grading exemption exists so the
downstream coverage judge is never compared against the same session's own
paraphrase of what it did.

### Step 3: Dispatch + Judge + Report (one command)
```bash
python3 target_scoped_run.py \
  --pool <output-dir>/generated_pool_<slug>.yaml \
  --scenario <output-dir>/generated_<slug>.py \
  --mode headless \
  --output-root <fresh-empty-dir> \
  [--config <path/to/.test-realistic.toml>]
```
Refuses to run over a reused `--output-root` that already has captures or a
prior verdict in it (never grades a stale run's leftovers). Dispatches
`config.dispatch_command`, collects every `config.capture_glob` match,
judges coverage with a real model call
(`feature_coverage_judge.judge_feature_exercised` -- batches turns by prompt
size, labels every turn with its true GLOBAL capture index so a model can
never accidentally echo a batch-local position, and treats any
`exercised: True` claim with empty evidence as malformed, not a pass), then
writes `<output-root>/target_scoped_verdict.json`.

`CoverageJudgeUnavailableError` is a hard failure after one bounded retry --
never caught to fabricate a verdict. Exit code is 0 only when the dispatch
subprocess also exited 0 (or was explicitly excused via
`--allow-dispatch-excuse` + a configured `runner_excuse_predicate`) AND
`target_pass` is true.

## Anti-false-green rules (non-negotiable, carried over verbatim from the source design)

1. Target classification and scenario-step authoring are ALWAYS real model
   calls (unless scenario steps are explicitly supplied in-session via `--from-json`) -- never `if "pr" in target.lower()`-style keyword routing.
2. `feature_summary` is derived independently at generation time and is
   NEVER supplied by the same session that will later grade the run.
3. The coverage judge's `exercised: True` requires non-empty
   `evidence_turn_indices` -- a claim without evidence is treated as
   malformed output (retried, then a hard failure), never a pass.
4. Every captured turn is judged (batched to fit prompt budgets), never
   silently windowed to a fixed prefix.
5. `CoverageJudgeUnavailableError` and `ScenarioGenerationError` are hard,
   non-zero-exit failures. No caller in this skill may catch either to
   fabricate a verdict or fall back to a keyword/token heuristic.
6. A capture produced without a real browser and a real model call is not
   valid evidence for this pipeline -- there is no mock mode.

## Directory layout

```
${CLAUDE_HOME:-$HOME/.claude}/skills/test-realistic/
  SKILL.md                    # this file
  PROVENANCE.md               # source lineage (EXAMPLE/historical block)
  scripts/
    config.py                 # .test-realistic.toml loader/validator
    agy_adapter.py             # default real model-call adapter (agy CLI)
    feature_coverage_judge.py  # the anti-false-green gate
    aggregate.py                # target-scoped verdict aggregation
    scenario_generator.py      # model-delegated scenario generation
    target_scoped_run.py       # dispatch + judge + report orchestrator
    verify_adapter.py          # onboarding conformance self-test (no model call)
  tests/                       # fast, stubbed-model unit tests (pytest)
  examples/
    test-realistic.example.toml  # fully-annotated EXAMPLE config
```

## Extending for your project

- No existing doc-to-invariants generator? Leave `doc_target_patterns`
  unset -- every target flows through the model-delegated path.
- Want style-grounded step authoring? Add
  `pattern_scenario_files = ["path/to/example1.py", ...]` (repo-root
  relative) to your TOML; absent that, steps are authored from context alone.
- Want a project-specific excuse for a flaky-but-not-feature-related
  dispatch failure? Implement `def my_excuse(returncode, output_root) ->
  tuple[bool, str]` somewhere importable, set
  `runner_excuse_predicate = "my_module:my_excuse"`, and pass
  `--allow-dispatch-excuse` explicitly per run (never on by default).
- Want a different default LLM adapter (not `agy`)? Pass your own
  `llm_callable` (a `(prompt, json_schema) -> dict` callable) into
  `scenario_generator.resolve_target_info` / `target_scoped_run.main`
  instead of relying on `agy_adapter.make_llm_callable`.
