---
description: BigQuery evidence verifier for real LLM request/response and RAG shadow claims
type: verification
execution_mode: immediate
---

# /bq - BigQuery Evidence Verifier

Use this command when a PR or evidence bundle claims real LLM request/response
logging, token-count reduction, or RAG/shadow BigQuery provenance.

## Execute immediately

1. Read `.claude/skills/bq-evidence-reading.md`.
2. Extract campaign IDs from artifacts, not PR prose alone.
3. Query `worldarchitecture-ai.llm_forensics.llm_payloads` for raw LLM request/response
   proof.
4. Query `worldarchitecture-ai.llm_forensics.log_events` only for structured event
   claims such as `rag_shadow_comparison`.
5. Report three separate verdicts:
   - BQ raw corpus proof
   - Structured event proof
   - Canonical evidence bundle quality

Do not treat `log_events` as the raw LLM request/response table. Do not treat
`llm_payloads` rows as proof that the local evidence bundle packaging is clean.

## Reference

Authoritative workflow: `.claude/skills/bq-evidence-reading.md`
