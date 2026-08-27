---
name: end2end-testing
description: Use when adding or modifying end-to-end tests, testing provider-backed application flows, choosing realistic fixtures, or debugging integration failures across service boundaries.
---

# End-to-End Testing

## Rule

Drive the real in-process application path and fake only external boundaries.
An end-to-end test must fail when the user-visible response, persisted state, or
other observable contract is wrong; importing or calling isolated helpers is not
end-to-end proof.

## Resolve the active project contract

Before writing a test:

1. Read the repository instructions and its canonical testing guidance.
2. Locate related end-to-end tests, shared base classes, SDK-faithful fakes, and
   the canonical test command.
3. Trace the application entry point through parsing, domain logic,
   persistence, and projection.
4. Identify the true external boundaries: provider transports, databases,
   queues, clocks, filesystems, or third-party APIs.

Project-local rules override generic names and examples in this skill. Do not
invent paths, fake classes, environment variables, or authentication bypasses.

## Test design

1. Write a focused test and watch it fail for the missing or incorrect
   behavior.
2. Enter through the real route, command, handler, or public service boundary.
3. Keep the parser, reducer/domain logic, persistence adapter, projection, and
   response serialization in process.
4. Fake only external calls and use real serializable values rather than loose
   `Mock` or `MagicMock` objects as application data.
5. Assert the request handed to the external provider, parsed response,
   persisted state or emitted side effect, and user/client/server-visible
   result when those checkpoints are in scope.
6. Cover success, relevant failure, and boundary cases. For multi-phase calls,
   provide ordered external responses and verify context passed between phases.
7. Run the focused test, then the project's relevant end-to-end suite.

Use the project's SDK-faithful realistic response fake when provider response
shape matters. A shallow hand-shaped dictionary can accidentally omit candidate
nesting, streaming part order, finish reason, usage metadata, or tool-result
parts and therefore prove the wrong contract.

## Source preference and fallback labels

Use this fixture-source order:

1. A complete PII-scrubbed request/response pair from raw production or staging
   provider telemetry.
2. A local raw provider transport capture when the matching telemetry row is
   unavailable.
3. A minimal desired-contract payload only when neither real source exists.

Label case 3 `SYNTHETIC CONTRACT FIXTURE` in the fixture header or test
docstring. It proves deterministic application behavior only; it proves nothing
about live-model compliance. Never repair a failed real response while turning
it into a success fixture. Preserve the failure unchanged and source a separate
successful response for the success case.

For telemetry fixtures, select the complete row. Adapt these generic fields to
the actual telemetry owner: `occurred_at`, `request_id`, `event_type`, `agent`,
`model`, `finish_reason`, `request_payload`, `response_payload`,
`response_parts`, `input_tokens`, `output_tokens`, and `deployed_revision`.
Pin one logical request and event type so wrapper or streaming rows are not
mixed. Do not use substring or preview columns to build a fixture.

PII-scrub while preserving structure, omissions, non-sensitive malformed and
numeric values, and content-part order. Replace all PII, including numeric PII,
with clearly synthetic same-type placeholders and record the substitutions.
Also record:

- source kind and stable request/capture identifier;
- timestamp, event type, agent, model, and finish-reason shape;
- deployed revision and any separately verified revision-to-source mapping;
- fields scrubbed and the structurally equivalent placeholders used.

A deployment identifier is not a source commit unless that mapping was
verified separately.

## Claim boundaries

| Fixture | What it can prove | What it cannot prove |
|---|---|---|
| Telemetry or raw local capture | Deterministic behavior for that preserved response shape | Current model reliability or broad frequency |
| `SYNTHETIC CONTRACT FIXTURE` | Desired deterministic parser, state, and projection behavior | Any live-provider capability or compliance |
| Current real-provider run | Capability for the recorded attempts | Backend correctness unless the application path is also exercised |

Keep `BACKEND READY` and `LLM CONTRACT GREEN` as separate claims. One real
response proves capability, not statistical reliability.

## Completion report

```text
END-TO-END READY
Test: <path and test name>
Entry point: <route/command/handler>
External boundaries faked: <boundaries>
Fixture: <source, identifier, provenance, and label if synthetic>
Assertions: <request, parsed result, persisted state/side effect, visible result>
Focused command: <command and result>
Relevant suite: <command and result>
Live provider compliance: NOT TESTED / PROVEN SEPARATELY
```

Do not report completion by running unchanged tests alone. Name the test and the
observable assertion added or changed.
