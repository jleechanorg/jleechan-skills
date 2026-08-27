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

## Construct or reconstruct the real request

1. Pin one failing logical request from provider telemetry, or define one
   representative target request for a fresh feature.
2. Capture the selected agent, full system/user request, response and tool
   schemas, MIME settings, parameters, cache provenance, raw response parts,
   finish reason, and usage.
3. When persisted source state matters, use the active project's canonical
   reproduction workflow to clone it safely; do not mutate the source record.
4. Verify that the agent actually loaded every prompt file proposed for change.

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

Use the same real provider and transport configuration as the failed or intended
path.
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

After an acceptable real response exists, preserve its complete raw
request/response pair and provenance. PII-scrub while preserving structure,
omissions, non-sensitive numeric values, and part order. Replace all PII,
including numeric PII such as phone or account identifiers, with clearly
synthetic same-type placeholders and record the substitutions. Hand that
fixture to `/backend-first` for deterministic execution proof.

Completion report:

```text
LLM CONTRACT GREEN or RED
Request IDs: <ids>
Agent/model/revision: <values>
Ablation/construction: <changed variables and rationale>
Raw contract result: <exact fields>
Sample count: <successes>/<attempts>
Backend behavior: FROZEN / NOT PROVEN
Fixture handoff: <path or telemetry provenance>
```
