---
name: second-call-boundary
description: Post-tool LLM calls are allowed when the first model response requested server-executed tools and the second call incorporates exact tool results
---

# Second-Call Boundary Protocol

## Policy Overview
Post-tool LLM calls are allowed when the first model response requested server-executed tools and the second call incorporates exact tool results.

## Prohibited Patterns
Do not add any of the following second-call wrapper variations:
- JSON/schema repair calls
- Fallback re-prompts
- Spell-repair calls
- Missing-tool retry prompts
- Prompt-based retry calls

The only allowed semantic sidecar is the FastEmbed intent classifier.
