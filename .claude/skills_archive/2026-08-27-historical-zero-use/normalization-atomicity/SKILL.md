---
name: normalization-atomicity
description: "Use when persisting rewards_box or any data structure to Firestore. ALL paths (streaming/polling/passthrough) must canonicalize before writing."
---

# Normalization atomicity — all persisted data must be canonicalized


**Any value written to Firestore (or any persistent store) must pass through its canonicalizer before persistence — regardless of which execution path performs the write.**

Specific case: `rewards_box` dicts written to Firestore must pass through `normalize_rewards_box_for_ui()` (or `rewards_engine.canonicalize_rewards()`) before being stored. "Passthrough", "passthru", and "passthrough" path names are semantically misleading — they imply no transformation but persistence requires canonicalization.

Correct pattern:
- Streaming path → `llm_parser.py` → calls `canonicalize_rewards()` → normalized output persisted
- Polling path → `project_level_up_ui()` → normalized output stored
- Passthrough path → must still call `normalize_rewards_box_for_ui()` before persisting

**Why**: PR #6265 fixed the passthrough branch when `_has_level_up_ui_signal` was False — the raw LLM `rewards_box` was returned without normalization. A path labeled "passthrough" does not mean "skip normalization."
