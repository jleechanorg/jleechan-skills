# Static review and the /advice static-review fallback

- **Outcome:** A new `static-review` skill owns the cold start, the verbatim
  prompt templates (revision and document-only), per-channel preambles,
  receipts (exact prompt, process and cleanup checks), identity rules and
  "deviation voids the vote" for every reviewer. `/advice` references it and
  keeps the trigger, quorum and no-double-substitution rules: static reviewers
  fill only vote slots left after every CLI attempt and coordinator account
  has ended by its deadline. The primary-pair runner records its exact prompt.
- **Non-goals:** No runner, script or quorum-size change; the portable and
  hermes derivatives are not resynced.
- **Acceptance:** `.claude/skills/static-review/SKILL.md` and its command
  pointer exist; `/advice` links it and defines the trigger, no double
  substitution (a real outside vote is required) and the per-host
  `UNAVAILABLE` record; `run_primary_pair.py` writes `prompt` and
  `prompt_sha256` to its receipt; contract tests cover each rule.
- **User stories:** As an owner, I get a fail-closed two-vote quorum when
  outside reviewers are offline, and the orchestrator cannot steer reviewers
  through its prompt.
- **Proof plan:** Existing `tests/` stay green; the receipt is published as an
  unlisted gist; independent static-review review happens at head.
- **Mock:** Exempt, no UI.
- **Risk:** Medium. A weaker independence guarantee for static reviewers is
  mitigated by distinct identities, cold prompts and byte-checked receipts.
