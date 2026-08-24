---
description: Evidence Standards — alias that reads the evidence-standards skill
type: reference
execution_mode: immediate
---

# /es — Evidence Standards Alias

Thin alias that reads both layers of the evidence-standards skill.

**Usage**: `/es`

## Action

Read and display both layers (agents must consult both):
1. `~/.claude/skills/evidence-standards/SKILL.md` — general cross-project standards
2. `.claude/skills/evidence-standards.md` — WorldArchitect-specific standards
3. If the evidence claim mentions BigQuery, `llm_forensics`, raw LLM payloads,
   token counts, RAG shadow comparison, or BQ readback, also read
   `.claude/skills/bq-evidence-reading.md` or run `/extended-library:bq`.

## Publication (gist-first)

When evidence is ready for a PR:

1. **Publish to a secret/unlisted gist** with sanitized artifacts (README, metadata, pytest output, checksums).
2. Put **only the gist URL** in the PR `## Evidence` section (and linked sections as required by the description gate).
3. **Do not commit** evidence bundles under `docs/evidence/` on the PR branch unless a repo gate explicitly requires in-tree paths — local `/tmp/<repo>/<branch>/` is the working bundle; gist is the published copy.
4. Gate-6 accepts `gist.github.com/` URLs; prefer that over `docs/evidence/` tree links in the PR body.

**Caveats**: After reading, you MUST always reconfirm by explicitly stating what the evidence proves vs what it does NOT prove.

## Local provider default

Local real-LLM evidence uses the AGY CLI provider by default. Run
`$PROJECT_ROOT/install.sh` if the sanitized runtime is missing; the local harness must
fail closed rather than silently fall back to the Gemini SDK. An AGY-backed claim
requires successful `agy_request` and `agy_response` records in
`provider_http_request_responses.jsonl` or the equivalent raw provider capture.
Use `AGY_PROVIDER_ENABLED=false` only when the evidence bundle documents the
provider-specific behavior being tested.
