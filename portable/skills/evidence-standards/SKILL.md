---
name: evidence-standards
description: Author and assess evidence whose provenance, coverage and strength match the actual claim.
---

# Evidence standards

Start with the reported symptom and acceptance claim. Build a claim-to-artifact map before capture. Record exact revision, source/command, timestamp, environment, inputs, outputs, exit status and hashes. Preserve failed attempts and omissions; never fabricate, relabel or silently repair evidence.

Separate integrity from provenance: a valid checksum proves stable bytes, not that they came from the claimed system. Reproduce derived counts from their source and report collection limitations. Read actual artifacts, not just filenames or manifests.

Use the smallest real execution layer that proves the claim. A unit or synthetic fixture proves deterministic behavior only; source presence does not prove runtime loading, screenshots do not prove backend persistence, and one model response does not prove reliability. UI claims need observed interaction/rendered state; streaming claims need genuine frame/chunk sequence; real-service claims need authorized real-service receipts. Discover project-specific harnesses and constraints rather than imposing a universal telemetry store.

For multi-item work keep per-item statuses: inspected, executed, passed, failed, skipped or blocked, with reasons. Report denominator and exact coverage; never convert partial proof into whole-task success.

A material code, prompt, skill, model/configuration or external-artifact change can stale evidence. Inspect the causal delta before reuse, retaining original revision and recording any reaffirmation at the current head. Do not exempt instruction changes merely because they are Markdown.

Use meaningful tests suited to the behavior and risk; avoid test-shaped string assertions or redundant tests for trivial reversible prose. A bug fix should show a fresh same-symptom failure and same-scenario success when feasible; explain unavailable reproduction honestly.

Keep raw sensitive inputs only in their authorized store. Create shareable redacted copies and a category/path ledger without original values. Secret scanning is one check, not proof of privacy: inspect personal, tax, financial, health and account identifiers semantically. Publish only to an authorized audience and destination; an unlisted URL is not private.

Use [evidence-review](../evidence-review/SKILL.md) for an independent verdict. This standard does not authorize provider spend, external publication, deployment or merge.
