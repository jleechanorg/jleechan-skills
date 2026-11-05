# Specification: /advice outside-reviewer fallback and cleanup

- **Outcome:** CLI quota exhaustion or unavailability does not block `/advice` while eligible authorized
  reviewers remain. Available CLI reviewers and at most one Dot vote are preferred; static subagents
  collectively one vote and Hermes or Hermes-PC one distinct vote are next; authenticated web chats are last.
  The canonical skill owns the order; command and overlays point to it.
- **Non-goals:** changing the default two-vote quorum, CLI seats, model allowlist, lifecycle applicability,
  compact low-risk eligibility, conditional static-model independence, disclosure permissions, or mandatory
  separate review gates; adding
  runner code, wording-pin tests or account configuration. The overlapping record-only exemption in PR #696
  remains separate. Withdraw the unapproved PR-body receipt proposal from active policy; the existing gist
  receipt requirement remains unchanged, with the earlier proposal retained only in PR history.
- **Acceptance:**
  - Quota, usage-limit or exhausted-429 replies make a CLI seat unavailable immediately, with no same-account retry.
  - Tier1 uses available independent CLI identities or one Dot; prefer different CLI/model identities without
    requiring any brand, account or mixture. Dot rotation can replace a failed attempt, not provide a second vote.
  - Tier2 admits native static subagents collectively as at most one full-scope vote, plus Hermes or Hermes-PC
    as at most one distinct full-scope vote. Tier3 uses existing authorized authenticated web accounts last.
  - Missing, busy, quota-blocked and duplicate seats advance with explicit availability reasons, not approval
    or indefinite waiting. Preserve bounded active attempts and retain valid earlier-tier votes.
  - Stop new dispatch at quorum unless a separate workflow obligation remains. Valid in-flight reviews and
    blocking findings are not discarded. Partial inspections cannot be aggregated into an approval.
  - One reviewer suffices only for the existing lifecycle compact low-risk eligibility, confirmed by that
    reviewer. Stricter gates and mandatory two-vote supplementary-review substitution remain unchanged.
  - Existing author/orchestrator exclusions, account deduplication, separate lifecycle `/dot` accounting,
    route-wide deadlines, named-reviewer wait overrides, cold prompts, full-scope receipts and head binding remain.
  - Dot and Hermes use authorized remote review; web seats use the complete uploaded revision/document packet.
    Missing authorization, transport or coverage produces honest unavailable/withheld results, never approval.
- **User stories:** an operator uses reviewers actually available on their machine without waiting for absent
  brands or spending quota on duplicate identities. An eligible small low-risk change uses one complete review;
  higher-risk changes retain their applicable quorum and proof. An overlay points to the same canonical rules.
- **Proof plan:** inspect complete old/new instructions against mixed CLI/Dot, Dot-cap, static-cap, Hermes-cap,
  web-last, busy/quota/duplicate, partial/wrong-head, compact-eligibility exclusion and mandatory-substitution
  scenarios. Run available mechanical portability, frontmatter/link and installer checks plus exact-head CI;
  report unavailable coverage honestly. Obtain independent semantic, /cs and Ponytail review as applicable.
  Tests do not prove prose behavior or formal approval; add no wording-pin tests.
- **Mock:** exempt; this Markdown-only instruction change has no UI.
- **Risk:** medium. Wrong ordering can waste quota or manufacture approval. Keep authority, quorum, identity,
  evidence and deadline contracts intact; review the complete diff and preserve unresolved publication gates.
