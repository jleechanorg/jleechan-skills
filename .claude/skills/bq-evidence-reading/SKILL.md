---
name: bq-evidence-reading
description: Use this when reviewing WorldArchitect PR evidence that claims real LLM request/response logging, token counts, RAG/shadow comparison, or BigQuery provenance.
---

# BQ Evidence Reading

Use this when reviewing WorldArchitect PR evidence that claims real LLM request/response
logging, token counts, RAG/shadow comparison, or BigQuery provenance.

## Core rule

Do not infer raw LLM request/response proof from `llm_forensics.log_events`.

Use the tables by responsibility:

| Claim type | BigQuery table | Required fields |
| --- | --- | --- |
| Raw LLM request/response corpus | `worldarchitecture-ai.llm_forensics.llm_payloads` | `request_json`, `model`, `campaign_id`, `user_id`, `event_type`, `prompt_tokens`, `output_tokens`, `is_test` and at least one of `response_text` or `response_parts_json` |
| Structured events such as RAG shadow comparison | `worldarchitecture-ai.llm_forensics.log_events` | `event_type`, `campaign_id`, `fields_json`, `ingested_at` |

`log_events` may prove that a `rag_shadow_comparison` event was emitted. It does not
prove that per-turn raw Gemini/OpenAI requests and responses were captured. That proof
lives in `llm_payloads`.

## Required review sequence

1. Identify the exact campaign IDs from artifacts, not PR prose alone.
   Prefer `rag_mode_comparison.json`, `mode_{original,rag,shadow}_scenario.json`,
   `run.json`, or `metadata.json`.
2. Query `llm_payloads` for those campaign IDs.
3. Verify row counts, nonempty `request_json`, model, `is_test`, timestamps, token
   counts, and that each row carries a response payload (either `response_text`
   for non-streaming calls or `response_parts_json` for streaming OpenAI-proxy and
   similar events — `$PROJECT_ROOT/llm_providers/openai_proxy_provider.py:676-683`
   intentionally logs streaming responses in `response_parts_json` only).
4. Query `log_events` separately for structured event claims such as
   `rag_shadow_comparison`.
5. Separate the verdict:
   - BQ raw corpus proof: PASS/FAIL from `llm_payloads`.
   - Structured event proof: PASS/FAIL from `log_events`.
   - Canonical evidence bundle quality: PASS/FAIL from local/gist bundle shape,
     checksums, `metadata.json`, `run.json`, and trace validation.

Never collapse those three into one verdict.

## Verified query templates

Replace the campaign IDs before running. These patterns were verified against PR #7593
on 2026-06-18.

### Raw LLM payload coverage

```bash
bq query --use_legacy_sql=false --format=json '
SELECT
  campaign_id,
  event_type,
  COUNT(*) AS row_count,
  COUNTIF(request_json IS NOT NULL AND LENGTH(request_json) > 0) AS request_rows,
  COUNTIF(
    (response_text IS NOT NULL AND LENGTH(response_text) > 0)
    OR (response_parts_json IS NOT NULL AND LENGTH(response_parts_json) > 0)
  ) AS response_rows,
  COUNTIF(model = "gemini-3-flash-preview") AS gemini3_rows,
  COUNTIF(is_test) AS test_rows
FROM `worldarchitecture-ai.llm_forensics.llm_payloads`
WHERE campaign_id IN ("CAMPAIGN_ORIGINAL", "CAMPAIGN_RAG", "CAMPAIGN_SHADOW")
GROUP BY campaign_id, event_type
ORDER BY campaign_id, event_type
'
```

Pass condition for raw BQ proof:

- Expected campaigns are present.
- Expected event types are present.
- `request_rows == row_count`.
- `response_rows == row_count` (a row counts if EITHER `response_text` is
  non-empty — typical for non-streaming Gemini — OR `response_parts_json` is
  non-empty — typical for `openai_proxy_streaming` and similar streaming
  events that log the streamed response parts only).
- Model and `is_test` counts match the claim.

### Token-count comparison rows

Use this when a PR claims a specific token reduction.

```bash
bq query --use_legacy_sql=false --format=json '
SELECT
  campaign_id,
  user_id,
  ingested_at,
  event_type,
  agent,
  model,
  prompt_tokens,
  output_tokens,
  LENGTH(request_json) AS request_len,
  LENGTH(response_text) AS response_len,
  JSON_VALUE(extra_json, "$.stream") AS stream
FROM `worldarchitecture-ai.llm_forensics.llm_payloads`
WHERE campaign_id IN ("CAMPAIGN_ORIGINAL", "CAMPAIGN_RAG", "CAMPAIGN_SHADOW")
ORDER BY ingested_at
'
```

If there are many rows, narrow by known token counts or timestamps only after the
coverage query proves the campaign set.

### RAG shadow comparison event

```bash
bq query --use_legacy_sql=false --format=json '
SELECT
  campaign_id,
  event_type,
  ingested_at,
  fields_json
FROM `worldarchitecture-ai.llm_forensics.log_events`
WHERE campaign_id = "CAMPAIGN_SHADOW"
  AND event_type = "rag_shadow_comparison"
ORDER BY ingested_at DESC
LIMIT 3
'
```

Pass condition for shadow event proof:

- Row exists for the shadow campaign.
- `fields_json` contains the claimed instruction chars, hashes, response hashes,
  and `code_execution_used` when those are claimed.

## Common failure modes

- Wrong table: querying `log_events` and concluding raw request/response BQ proof is
  absent. Correct table is `llm_payloads`.
- Overclaiming: seeing `llm_payloads` rows and calling the full `/es` bundle clean
  even when `metadata.json`, `run.json`, checksums, or canonical JSONL traces failed.
- Summary-only artifact: a gist file may summarize BQ rows. Prefer a row-level export
  or rerun the BQ query live when judging a blocker.
- Row count ambiguity: `llm_payloads` can include paired event types such as
  `gameplay_streaming` and `stream_story_with_game_state`. State whether a number is
  raw rows or logical turns/pairs.
- Checksum transport mismatch: verify gist checksums from a real `gh gist clone` when
  `gh gist view --raw` produces a stream digest mismatch.

## Verdict wording

Use wording like:

> BQ raw request/response proof is present in `llm_payloads`: all expected campaigns
> have nonempty `request_json` and `response_text` rows. The structured shadow event
> is separately present in `log_events`. This does not by itself make the canonical
> evidence bundle clean; bundle packaging/checksum/trace validation must be judged
> separately.

Avoid wording like:

> BQ proof is missing because `log_events` only has `rag_shadow_comparison`.

Avoid wording like:

> `/es` passes because `llm_payloads` has rows.
