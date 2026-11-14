# Entire-backed human nudge metrics

## Outcome

Record Entire as a tool used by this repository and provide a runnable path from native transcripts through the pinned Entire SDK and model adjudication into the existing human-nudge metric. Reuse the current annotation, aggregation, coverage and rendering contracts.

## Non-goals

No new metrics taxonomy, keyword intent classifier, hosted service, credentials, global model defaults, hook installation or scheduled deployment. Do not commit private transcripts or prompt examples. Existing native ingestion remains usable. This PR does not establish fleet-wide coverage or native human authorship from a user role.

## Acceptance

1. A small Go facade pins `github.com/entireio/cli` at `v0.13.4` (upstream commit `95eabf579d7aa6e5dbe994a6956c8e3fb44d4465`), records MIT licensing and documents its actual caller. Use the SDK's canonical JSONL format, not a parallel exported-Go-struct schema. Read native bytes from stdin with an explicit agent; write normalized JSONL to stdout without diagnostic text containing source values.
2. The existing Python metrics workflow can ingest the normalized results and retain source/session/event identifiers, timestamps, source fingerprints and coverage/error status. Stable IDs and ambiguous/unmapped records remain explicit. Raw text belongs only in an explicitly requested private adjudication packet, never the normal analytics export or diagnostic logs.
3. A caller-selected model command may adjudicate private packets. The model owns actor/intent and nudge decisions; code supplies transport, exact IDs and source metadata. Use existing annotation fields: `actor_kind`, `human_origin`, `message_kind`, `human_nudge_eligible`, optional episode and PR binding fields. No semantic keyword, regex or scoring classifier is added.
4. A nudge is a human continuation/follow-through reminder for already-authorized unfinished work, without a material new requirement or an unmet human-only gate. Status requests, initial tasks and new requirements remain separate. Missing context or actor evidence stays unknown. Preserve native origin separately from reviewer/model actor labels; no user-role-to-human promotion by default.
5. Reuse `aggregate_native_human_steering`: observed nudge messages count only reviewed/verified human records with `message_kind=continuation/followthrough_nudge` and explicit eligibility. Unassigned PRs and unreviewed candidates remain visible; unknown coverage is not represented as universal zero nudges.
6. Executable tests cover real SDK normalization of sanitized Claude and Codex fixtures, model-command transport, strict source-ID association, unknown/automation exclusion, positive and negative nudge decisions from supplied annotations, no raw text in normal exports, and CLI-to-existing-metric integration. No tests pin Markdown prose.
7. A fresh real SDK plus real model-command run demonstrates the full path. Use synthetic/public fixtures for shareable evidence; keep any native captures private and publish only sanitized metadata. Record actual SDK/compiler/model, commands, output, time window, event coverage and tested SHA.

## User story

Today the repository can count human nudges from reviewed annotations but has no Entire parser integration or reusable adjudication path. After this change, an operator can normalize supported native histories with a documented OSS tool, obtain model judgments through an explicitly selected command, and compute the existing nudge metric with visible unknowns and source coverage.

## Proof plan

Establish focused behavioral RED before implementation, then GREEN and impacted Python/Go regressions. Provision the pinned Go toolchain before treating a missing feature as RED. Run one actual SDK/model/metrics CLI integration and verify the nudge count plus unknown/automation controls. Drive one cohesive PR through applicable standards, independent source/evidence review, CI and conflict checks; code approval is separate from the earlier document-only design votes.

## Mock / visual classification

Unit tests may use deterministic judge-command fakes to test transport and aggregation. They do not prove model compliance; the separate real-command run supplies that claim. No rendered product interface is changed by the planned adapter. If implementation changes a dashboard surface or claims displayed values, add the corresponding real browser proof.

## Risks and integration ownership

The SDK normalizes and may omit or merge events, so source/coverage gaps must survive. Its module requires Go 1.27.4; CI and local verification must use an eligible compiler. Model input may contain private excerpts as part of the explicitly requested adjudication; document that data flow and never upload raw histories to browser reviewers. The prior smoke's schema-inspection exposure remains historical failure evidence, not a justification to log source values.

Existing owners are `scripts/native_usage_collector.py`, `scripts/prw_metrics.py`, the reviewed annotation schema in `docs/specs/prw-metrics-dashboard-spec.md`, and their tests. Extend those seams rather than creating a second counter. SDK dependency/version documentation lives with the small Go tool and is linked by its real caller.
