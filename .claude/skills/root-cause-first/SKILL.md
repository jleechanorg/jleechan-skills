---
name: root-cause-first
description: Use when a bug may cross an LLM/backend boundary or tempts changes to prompts, schemas, parsing, persistence, retries, fallbacks, guards, or response repair.
---

# Root Cause First

## Rule

Diagnose before editing. This skill locates the first divergence and chooses one
causal lane. It does not tune prompts or change backend behavior itself.

## Modes

- **Direct diagnostic mode** applies only when this skill is invoked directly
  to diagnose a concrete failure and the active task authorizes investigation
  or fixes. After the route verdict, it may execute the selected owner skill.
- **Review-only mode** applies automatically when loaded by another review or
  audit workflow, or when the subject is a code diff, PR, proposed guard, or
  proof classification. Emit the evidence-backed verdict and findings, then
  stop before executing `/llm-first` or `/backend-first`.

If the invocation mode is unclear or the active task does not authorize
changes, use review-only mode.

## Boundary trace

Capture the same failing turn across these checkpoints:

1. Intended agent, prompt, schema, provider configuration, and user request.
2. Exact request actually handed to the provider, including cache provenance.
3. Exact raw provider response and finish/usage metadata.
4. Parsed structured response handed to backend logic.
5. Reducer/persistence input and persisted state.
6. User/client/server-visible response.

Pin the relevant entity/run ID, request ID, event type, agent, model, deployed
revision, and timestamps. Prefer raw provider and persistence artifacts over
summaries. Preserve omissions and malformed fields; never repair evidence while
diagnosing it.

## Decision matrix

| First divergence | Route |
|---|---|
| Actual request uses the wrong agent, prompt, schema, or provider config | `/llm-first` |
| Raw response omits or violates the exact requested contract | `/llm-first` |
| Raw response satisfies the contract but parsing changes or drops it | `/backend-first` |
| Parsed input is correct but reduction, persistence, or projection is wrong | `/backend-first` |
| A fixed acceptable response behaves inconsistently behind the provider boundary | `/backend-first` |
| Evidence cannot locate the first divergence | `UNDER-INSTRUMENTED` |

When useful, replay the same acceptable raw response twice through the backend
with the project's SDK-faithful realistic response fake. This is a diagnostic
comparison, not permission to change the backend before classification.

## Verdict

Emit exactly one route label with the first divergent artifact:

- `ROOT CAUSE ROUTE: LLM`
- `ROOT CAUSE ROUTE: BACKEND`
- `ROOT CAUSE ROUTE: UNDER-INSTRUMENTED`

In direct diagnostic mode, execute only the selected owner skill:

- LLM route: execute `/llm-first`.
- Backend route: execute `/backend-first`.
- Under-instrumented: report the missing artifact and stop. Instrumentation
  requires a separately authorized follow-up that changes no prompt/schema or
  backend semantics; rerun this diagnostic after that evidence exists.

In review-only mode, stop after the evidence-backed verdict and findings. Do
not launch owner skills, provider experiments, or edits.

## Protection review

Before accepting a backend guard, fallback, clamp, retry, sanitizer, or
suppression, classify it as one of:

- server-owned invariant;
- backend-transformation fix;
- prompt/schema-insufficient with raw-path proof;
- unproven fallback;
- model-ownership violation candidate (the ZFC workflow calls this a `ZFC violation candidate`).

Do not call backend protection necessary without server ownership or raw-path
proof. Retain any domain-specific approval gates from the active repository
policy.

## Guardrails

- Freeze the opposite side once a route is chosen.
- Do not edit prompt and backend behavior in one causal experiment.
- Do not add semantic keyword/regex routing, response repair, retry-until-pass,
  or hidden model-decision fallbacks.
- Synthetic fixtures prove deterministic behavior only.
- One real response proves capability, not statistical reliability.
