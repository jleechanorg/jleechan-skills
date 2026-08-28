# Streaming Evidence Standards

**Purpose**: Prove end-to-end streaming chunk delivery from LLM output to HTTP SSE client with timestamped, sequence-level evidence.

## Required References
- Bead: `BD-iwr`
- Roadmap spec: `roadmap/2026-02-11-streaming-evidence-reference-standard.md`
- PR requirement section: `LLM-to-HTTP Chunk Timing Evidence Requirement`

## Mandatory Evidence (Single Fresh Run)
1. Record identifiers:
- `campaign_id`
- `request_id` (or stable equivalent)
- environment/service identifier

2. LLM chunk timeline:
- UTC timestamp for first LLM chunk
- UTC timestamp for every LLM chunk
- sequence index per chunk

3. HTTP SSE timeline:
- UTC timestamp for first HTTP chunk received
- UTC timestamp for every HTTP chunk received
- sequence index per chunk

4. Joined per-sequence table:
- `sequence`
- `llm_ts_utc`
- `http_ts_utc`
- `delta_ms = http_ts - llm_ts`

5. Summary metrics:
- first-chunk latency summary
- `p50/p95/max` of `delta_ms`

6. PASS/FAIL thresholds:
- `p95(delta_ms) <= 2000 ms`
- `max(delta_ms) <= 5000 ms`

7. Reproducibility artifacts:
- raw LLM chunk log path
- raw HTTP chunk log path
- joined table/report path

## Skeptical Validation Checklist
- Same `campaign_id`/`request_id` appears across all artifacts.
- Sequence counts align between LLM and HTTP timelines.
- No skipped/duplicate sequence rows without explanation.
- First chunk is observed in logs (not inferred from request start).
- Reported metrics match the raw joined table.

## Failure Conditions
Mark FAIL when any apply:
- Missing per-chunk timestamps on either side
- Missing joined table
- Missing identifiers preventing correlation
- Threshold violations without documented external incident
- Summary claims without raw evidence paths
