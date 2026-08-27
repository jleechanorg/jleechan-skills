---
name: backend-first
description: Use when fresh backend behavior needs deterministic proof, root-cause-first routes a failure to the backend lane, or an acceptable model response changes or disappears after the provider boundary.
---

# Backend First

## Boundary

Freeze prompts, routing, provider configuration, and fixture content. Mock only
external provider and persistence boundaries; exercise the real in-process
parser, reducer, persistence, projection, and application route.

For debugging, execute `/root-cause-first` first and proceed only with
`ROOT CAUSE ROUTE: BACKEND`. For fresh feature development, define the desired
model/backend contract before the first test; no diagnostic verdict is
required. If a captured raw model response violates the requested contract,
stop and execute `/llm-first` instead.

## Required fixture

Use the project's SDK-faithful realistic response fake rather than a loose mock
or hand-shaped dictionary. Resolve the concrete fake and fixture rules through
the active project's canonical end-to-end testing skill; keep that
project-specific pointer outside this portable skill.

**Strong default:** source the complete request/response pair from raw
production provider telemetry. Pin one request ID, one event type, one
finish-reason shape, model, agent, and deployed revision; scrub sensitive data
without trimming or repairing the payload. Preserve omitted or malformed
fields, SDK/streaming part order, finish reason, and usage metadata. If a source
revision is needed, record a separately verified deployment-to-source mapping;
do not treat a deployment identifier as a commit hash.

Adapt this complete-row query shape to the active telemetry owner; use bound
parameters and the project's real column names:

```sql
SELECT occurred_at, request_id, event_type, agent, model, finish_reason,
       request_payload, response_payload, response_parts, input_tokens,
       output_tokens, deployed_revision
FROM <provider_telemetry_table>
WHERE request_id = <bound_request_id>
  AND event_type = <bound_event_type>
ORDER BY occurred_at DESC
LIMIT 1;
```

Do not replace complete payload columns with substring previews when building a
fixture.

Use a local raw provider capture only when the matching production telemetry row
is unavailable. A minimal desired-contract fixture is a last resort and must be
labeled `SYNTHETIC CONTRACT FIXTURE`; it proves no live-model behavior. Never
silently upgrade a synthetic fixture into a real-response claim.

Record the fixture payload, telemetry query or capture provenance, expected
persisted state, and expected user/server-visible response.

## Workflow

1. Write a fresh failing test before changing behavior.
2. Add narrow Layer 1 coverage for the first deterministic divergence.
3. Add or update an integration/end-to-end test in the project's canonical test
   location that drives the real in-process route with only external boundaries
   faked.
4. Assert the request handed to the provider, parsed response, persisted state,
   and user/server-visible output.
5. Fix only a proven backend-transformation bug or server-owned invariant. Do
   not add model-semantic fallback logic.
6. Run targeted Layer 1, targeted Layer 2, compile/import checks, and relevant
   contract validators until green.
7. Report `BACKEND READY` separately from `LLM CONTRACT GREEN`.

## Completion

```text
BACKEND READY
SHA: <sha>
Fixture: <payload and provenance>
Layer 1: PASS
Layer 2: PASS
Persisted state: <values>
Visible response: <values>
Live LLM compliance: NOT TESTED / PROVEN SEPARATELY
```
