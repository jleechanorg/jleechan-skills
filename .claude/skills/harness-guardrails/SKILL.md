---
name: harness-guardrails
description: Avoid recurring harness bugs in event handling, state transitions, model-owned contracts, and browser tests.
---

# Harness Guardrails

Apply the active repository’s ZFC, state ownership, and test policies first.

- **Event listener lifetime:** Keep the same function reference for registration and removal. An inline `.bind(this)` creates a new function and does not remove the original registration.
- **State transitions:** For an authorized administrative override, trace which orthogonal states it must preserve or reset. Use the repository’s state-transition contract and test the normal path as well as the override.
- **Shared constants:** Find duplicate definitions before centralizing a value. Keep one authoritative definition for a shared contract; do not extract an abstraction used in only one place.
- **Model-owned output:** Before adding a fallback, repair, or server-synthesized choice, check whether the selected model received a clear prompt/schema contract. Fix the first divergence and require raw-path evidence for any backend exception authorized by local ZFC policy.
- **Diagnosis checkpoint:** If repeated patches address the same symptom, stop adding guards. Verify the first divergence, and use the repository’s escalation or review rule where required.
- **Opaque handles:** Resolve an ID against its source object, then consume explicit typed fields for meaning. Preserve documented legacy compatibility checks without giving new IDs, labels, prefixes, or CSS classes domain authority.
- **Browser tests:** Use the project’s supported runner, fixture locations and path-resolution conventions. Skip only for a known missing prerequisite; do not swallow navigation errors. Run the focused check before publication when the repository requires it.
