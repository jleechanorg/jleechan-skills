# Specification: /advice outside-reviewer fallback and cleanup

- **Outcome:** CLI quota exhaustion or unavailability does not block `/advice` while eligible authorized
  reviewers remain. Each distinct configured Dot account can supply one independent vote. Hermes and Hermes PC
  are the final fallback. The canonical skill owns the order; command and overlays point to it.
- **Non-goals:** changing the default two-vote quorum, CLI seats, model allowlist, lifecycle applicability,
  conditional static-model independence, disclosure permissions, or mandatory separate review gates; adding
  runner code, wording-pin tests or account configuration. The overlapping record-only exemption in PR #696
  remains separate. Withdraw the unapproved PR-body receipt proposal from active policy; the existing gist
  receipt requirement remains unchanged, with the earlier proposal retained only in PR history.
- **Acceptance:**
  - Quota, usage-limit or exhausted-429 replies make a CLI seat unavailable immediately, with no same-account retry.
  - When CLI seats cannot fill open slots, authorized Dot rotation and web review start together. Each distinct
    eligible account can vote once. Advance after success or failure while quorum is unmet; preserve valid votes.
  - Stop new dispatch at quorum unless a separate workflow obligation remains. Three configured Dot accounts are
    candidates, not three mandatory requests. Valid in-flight reviews and blocking findings are not discarded.
  - Static votes become eligible after CLI, Dot and web attempts end. Hermes instances are requested only if the
    earlier rungs cannot meet quorum or a required outside vote. Static eligibility never waits for Hermes.
  - Existing author/orchestrator exclusions, account deduplication, separate lifecycle `/dot` accounting,
    route-wide deadlines, named-reviewer wait overrides, cold prompts, full-scope receipts and head binding remain.
  - Dot and Hermes use authorized remote review; web seats use the complete uploaded revision/document packet.
    Missing authorization, transport or coverage produces honest unavailable/withheld results, never approval.
- **User stories:** an operator with exhausted CLI quotas receives independent reviews from their eligible Dot
  accounts without unnecessary requests after quorum. If earlier routes cannot complete the review, Hermes is
  tried last. A reviewer reading an overlay follows the same order as the canonical skill.
- **Proof plan:** compare old/new instructions against scenarios for two Dot approvals, CLI plus Dot, success
  then unavailable account, duplicate identities, wrong-head/partial replies, route timeout, static-only
  coordinator substitution, final Hermes and separately required reviews. Run installer, catalog, closure,
  machine-local CLI, portable install, swarm references, sync, Hermes routing and lifecycle tests plus exact-head
  CI. Obtain independent semantic, `/cs` and Ponytail review; tests do not prove prose behavior or formal approval.
- **Mock:** exempt; this Markdown-only instruction change has no UI.
- **Risk:** medium. Wrong ordering can waste quota or manufacture approval. Keep authority, quorum, identity,
  evidence and deadline contracts intact; review the complete diff and preserve unresolved publication gates.
