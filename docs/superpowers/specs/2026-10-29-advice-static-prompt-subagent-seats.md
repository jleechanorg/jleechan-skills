# Advice: static review prompt and subagent-seat fallback

- **Outcome:** `/advice` gives every reviewer (CLI primary and alternates, the
  coordinator ask, subagent seats) one skill-owned verbatim prompt with only
  `<PR URL>` and `<SHA>` filled in, plus a fixed per-channel preamble. When
  every CLI attempt and every coordinator account has ended by its deadline,
  cold, distinct subagent seats may fill the remaining vote slots.
- **Non-goals:** No runner, script or quorum-size change; the portable and
  hermes derivatives are not resynced.
- **Acceptance:** `.claude/skills/advice/SKILL.md` defines the template and
  preambles, voids any vote whose recorded prompt deviates, defines seat
  identity, trigger, no double substitution, the seat receipt and the
  `UNAVAILABLE` record, and amends §2 and §5 to match.
- **User stories:** As an owner, I get a fail-closed two-vote quorum when
  outside reviewers are offline, and the orchestrator cannot steer reviewers
  through its prompt.
- **Proof plan:** Existing `tests/` stay green; the receipt is published as an
  unlisted gist; independent seat review happens at head.
- **Mock:** Exempt, no UI.
- **Risk:** Medium. A weaker independence guarantee for subagent seats is
  mitigated by distinct identities, cold prompts and byte-checked receipts.
