---
name: llm-first
description: Use when fresh model behavior needs a contract or root-cause-first routes a prompt, schema, routing, provider-configuration, or raw-response failure to the LLM lane.
---

# LLM First

## Boundary

For debugging, execute `/root-cause-first` first and proceed only with
`ROOT CAUSE ROUTE: LLM`. For fresh feature development, define the target model
contract and expected raw response before the first experiment; no diagnostic
verdict is required. In both modes, freeze parser, reducer, persistence,
projections, backend guards, and deterministic fixture assumptions.

This skill owns prompt text, response schema, agent selection, provider
configuration, request construction, and raw model compliance. It does not
modify backend behavior.

## Capture the real request first

For an existing behavior or incident, the primary causal input is an exact
provider-boundary capture of the request and response, not a request
reconstructed from current backend source.

1. Query an authoritative provider-boundary capture. BigQuery raw LLM request
   telemetry from the active project's `llm_payloads` table is one storage
   option, not a prerequisite. Use one exact non-test request and its response.
   Record an immutable source-row locator, query/export identity, request ID,
   campaign or equivalent entity IDs when applicable, timestamps, agent,
   model/revision, schemas, MIME settings, generation parameters, cache
   provenance, finish reason, usage, and a source hash.
2. Keep literal `request_json`, unredacted response parts, and original
   substitution values inside authorized access-controlled telemetry.
   Never commit, publish, log, or hand off unredacted values. This prohibition
   covers fixtures, test output, PRs, agent responses, and evidence bundles,
   including numeric PII such as phone or account identifiers.
3. Produce shareable artifacts by PII-scrubbing a copy while preserving
   structure, omissions, non-sensitive numeric values, field and part order,
   and configuration. Record a redaction ledger containing paths, data types,
   and replacements but no original values. Hash the sanitized baseline.
4. Freeze the baseline. Apply one declared prompt, schema, routing, or
   provider-configuration patch and preserve a canonical diff plus its hash.
5. Verify that the captured request actually loaded every prompt file or
   instruction proposed for change. Source-code presence is not runtime proof.

If no qualifying raw row exists, report `NOT-YET-CAPTURED`. A
backend-generated reconstruction is an explicitly labeled fallback for an
uncaptured incident, or the normal starting point for a genuinely fresh
feature. It must not be pooled with captured-wire samples or presented as the
historical production request. A verified non-BigQuery provider-boundary
capture follows the same rules under the label `CAPTURED WIRE REPLAY`.

## Replay the captured wire request

An exact provider-boundary capture is required; BigQuery is one possible storage
source. Label `BQ WIRE REPLAY` only when the BigQuery row itself is the verbatim
provider-boundary request/response payload; transformed, reconstructed, or
backend telemetry does not qualify. A verified non-BigQuery provider-boundary
capture may use `CAPTURED WIRE REPLAY`.

Captured-wire causal attribution requires the same provider API, resolved
model/revision, and transport semantics/configuration except where one of those
fields is itself the one declared mutation. Replay the protected baseline and
its one-variable mutation with every other semantic held constant. Drift means
undeclared variance beyond approved redaction and the one declared mutation. A
content or provider/model/transport change that is itself the one declared
mutation is not drift. Approved containment or shareability redaction that
changes content requires `SANITIZED SURROGATE`. Any undeclared content,
provider, model, or transport variance requires `DRIFTED REPLAY (NON-CAUSAL)`
or another clearly weaker non-causal class; never retain captured-family causal
claims after drift. Direct provider submission is allowed only when an immutable
source-row locator, source hash, sanitized-baseline hash, redaction ledger, and
canonical mutation diff prove that every source difference is an approved
redaction or the one declared mutation. Absent that proof, classify the request
as `RECONSTRUCTED FALLBACK` or `FRESH CONSTRUCTION`, never captured-wire
evidence. A handcrafted or source-reconstructed direct SDK request remains
synthetic exploratory evidence.

Semantic redaction means any model-visible content or value substitution or
transformation that can change model behavior or meaning. Semantic redaction is
a containment or shareability transformation of the captured baseline, not the
declared experimental mutation. Structure-preserving same-type PII replacement
remains semantic when model-visible and requires `SANITIZED SURROGATE`.

Classify evidence fail-closed in this order: missing or unverified
provider-boundary provenance first; verified capture with any undeclared drift
next; verified capture with approved semantic redaction and no undeclared drift
next; verified exact capture with no semantic redaction and no undeclared drift
last. Missing or unverified provenance cannot be classified as `SANITIZED
SURROGATE`; no overlapping condition may retain a stronger class.

Evidence classes are mutually exclusive:

| Input | Evidence class | Causal scope |
|---|---|---|
| Verbatim BigQuery provider-boundary request/response row; no semantic redaction or undeclared drift | `BQ WIRE REPLAY` | Captured request family |
| Non-BigQuery provider-boundary capture; no semantic redaction or undeclared drift | `CAPTURED WIRE REPLAY` | Captured request family |
| Verified capture with approved semantic redaction and no undeclared drift | `SANITIZED SURROGATE` | Sanitized pair only |
| Verified capture with undeclared content/provider/model/transport drift | `DRIFTED REPLAY (NON-CAUSAL)` | No causal scope |
| Missing capture provenance | `RECONSTRUCTED FALLBACK` or `FRESH CONSTRUCTION` | Exact constructed request only |

Keep the original capture system in a separate provenance field; BigQuery
provenance does not preserve the BQ evidence class after a semantic redaction.
The first two classes may earn `LLM CONTRACT RED` or `LLM CONTRACT GREEN` for
raw model compliance and causal attribution within the captured request family.
A surrogate may prove compliance for its pair.
It cannot support a causal claim about the original historical request. Run
exact-content replays only inside the authorized environment and publish only
sanitized metadata, hashes, diffs, and outputs.

Always report sample count and unavoidable provider, model, sanitization, or
transport drift. No wire class proves current backend assembly, persistence,
end-to-end behavior, or production reliability.

After wire-level causality is acceptable:

Require a separate deterministic backend confirmation under the active project's
canonical integration/E2E owner and normal production entrypoint. Compare the
emitted request with the expected patched capture and verify routing, prompt
ordering, schema attachment, cache policy, generation parameters, provider
gateway, and streaming behavior. This confirmation is required before `/es`,
`/er`, merge-readiness, or a "production fixed" claim; deterministic parsing
and state changes remain in the backend lane.

## One-variable discipline

Default to one variable per experiment. A deliberate bundle is allowed when
user constraints and model judgment require coupled changes. Record every
changed variable before running so the result remains attributable. Never edit
prompt text and backend behavior in the same causal cycle.

## Ablation and removal first

Before adding prompt text or schema bloat, test whether removing
contradictory, redundant, or confusing context solves the problem. Removing
instructions often reveals conflicts; for fresh features, add the minimum
schema and instruction needed to express the target contract:

- remove redundant model-owned output surfaces;
- remove contradictory examples or instructions;
- reduce the schema to the one canonical field the product needs;
- remove duplicated semantic ownership;
- add new fields or instructions when the feature requires them;
- test prompt, schema, routing, and context-size effects separately.

## Real-provider proof

Use the same real provider API, resolved model/revision, and transport
semantics/configuration as the failed or intended path. This is mandatory for
captured-wire causal attribution; any drift follows the downgrade rule above.
Preserve every attempt, including failures; never retry until a single success
and discard the rest. Do not start real-provider testing until the user
authorizes that phase. Honor any additional project gate, such as deterministic
backend tests being green, when the active workflow requires it.

For each attempt record:

- exact request/config/schema hash or artifact;
- raw response and part order;
- whether the one requested contract was satisfied;
- token counts, finish reason, agent, model, and request ID.

Use `LLM CONTRACT RED` when the raw response violates the exact request and
`LLM CONTRACT GREEN` only when it satisfies it. State sample count separately;
capability and reliability are different claims.

## Iterate

When RED, classify the request-side cause before the next experiment:

- missing instruction;
- contradictory instruction/example;
- weak or ambiguous ownership;
- wrong agent/routing;
- schema/config mismatch;
- context dilution;
- provider nondeterminism after the above are controlled.

Apply the smallest prompt/schema/routing change or deliberate user/model-chosen
bundle, rerun the same request family, and record every changed variable. Do not
compensate with backend fallbacks in this lane.

## Handoff

After an acceptable response exists, keep complete raw request/response pairs
in access-controlled telemetry and reference them only by safe locator and
hash. Hand the active project's canonical integration/E2E owner the sanitized
baseline, mutation diff, sanitized outputs, redaction ledger without original
values, provenance, and backend-confirmation result for deterministic execution
proof. `/backend-first` remains for incidents routed BACKEND and is not a
follow-on step for an LLM-routed incident.

Completion report:

```text
LLM CONTRACT GREEN or RED
Request IDs: <ids>
Agent/model/revision: <values>
Evidence class: BQ WIRE REPLAY / CAPTURED WIRE REPLAY /
  SANITIZED SURROGATE / DRIFTED REPLAY (NON-CAUSAL) /
  RECONSTRUCTED FALLBACK / FRESH CONSTRUCTION
Capture and mutation hashes: <values>
Ablation/construction: <changed variables and rationale>
Raw contract result: <exact fields>
Sample count: <successes>/<attempts>
Backend confirmation: PASS / FAIL / NOT RUN
Backend behavior: FROZEN / NOT PROVEN
Fixture handoff: <path or telemetry provenance>
```
