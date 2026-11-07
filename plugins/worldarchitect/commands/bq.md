---
description: BigQuery evidence verifier for real LLM request/response and RAG shadow claims
type: verification
execution_mode: immediate
---

# /bq - BigQuery Evidence Verifier

Use this command when a PR or evidence bundle claims real LLM request/response
logging, token-count reduction, or RAG/shadow BigQuery provenance.

## Execute immediately

1. Read the `bq-evidence-reading` skill.
2. Extract campaign IDs from artifacts, not PR prose alone.
3. Query `${GCP_PROJECT_ID}.${LLM_FORENSICS_DATASET}.llm_payloads` for raw LLM request/response
   proof.
4. Query `${GCP_PROJECT_ID}.${LLM_FORENSICS_DATASET}.log_events` only for structured event
   claims such as `rag_shadow_comparison`.
5. Report three separate verdicts:
   - BQ raw corpus proof
   - Structured event proof
   - Canonical evidence bundle quality

Do not treat `log_events` as the raw LLM request/response table. Do not treat
`llm_payloads` rows as proof that the local evidence bundle packaging is clean.

## Reference

Authoritative workflow: the `bq-evidence-reading` skill
