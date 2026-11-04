# Specification: /advice outside-reviewer fallback and cleanup

- **Outcome:** when every CLI reviewer is quota-walled, missing or void, `/advice` still reaches a two-vote quorum
  through outside reviewers before falling back to in-session static reviewers. The owner asked for this on
  2026-11-04: "when all cli reviewers out of quota ... it should try to use /wa and ask hermes hermes pc and the dots
  in dot coordination for a review and use /dot", and, in a PR review comment, to "explicitly say if available use
  #dot-coordination slack to ask hermes for reviews". `advice` and `static-review` also lose duplicated text
  (`advice/SKILL.md` goes from 3,232 to under 2,900 words) without changing their other rules.
- **Non-goals:** changing the quorum size, the CLI seat list or defaults, the Codex model allowlist, pr-lifecycle's
  applicability thresholds, or the 2026-10-29 static-review exception (including whether two same-model sub-agents
  are two votes); adding runner code, tests or new markdown links that change install-profile closures; editing the
  `/prw` family (separate PR) or `portable/skills/advice`.
- **Acceptance:**
  - A quota, usage-limit or exhausted-429 reply makes that CLI seat `UNAVAILABLE` at once, with no same-account retry.
  - Once CLI seats cannot fill the open slots, the Dot, Hermes (including hermes-pc, through `#dot-coordination` when
    available) and `/web-advice` routes are dispatched concurrently. Each Dot or Hermes reply counts only with full
    `COVERAGE:` and a SHA-bound `VERDICT:`.
  - Dot and Hermes review a pushed SHA from an existing checkout (`isolation: remote`). `/web-advice` reviews an
    uploaded packet of the pinned `BASE..SHA` diff and full changed files (`isolation: packet`). Both have matching
    `static-review` templates, preambles and receipt fields.
  - A disclosure restriction or secret content makes the affected outside route `UNAVAILABLE`.
  - Static reviewers fill only slots still open after every CLI seat and outside route has ended.
  - `test_installer`, `test_cross_host_catalog`, `test_command_closure`, `test_advice_machine_local_clis`,
    `test_portable_install`, `test_swarm_references`, `test_sync_live_config` and CI `contract-tests` pass.
- **User stories:** an operator whose Codex and Claude quotas are exhausted runs `/advice` and gets votes from their
  Dots, Hermes instances or web chats instead of a `WITHHELD` that only says "CLIs unavailable". A reviewer reading
  `advice` finds each rule stated once.
- **Proof plan:** run the listed test modules locally and CI on the head; run two static reviewers (different
  model and sub-agent type) with the new verbatim prompts at the head; resolve every P0/P1 and record each verdict,
  coverage and receipt in the PR body.
- **Mock:** exempt. There is no UI; the change is skill and command Markdown.
- **Risk:** medium.
  - Outside routes disclose PR content to Dot, Hermes and third-party web providers. Mitigation: the owner's quoted
    authorization, the disclosure carve-out, and the remote no-mutation preamble.
  - The cleanup could drop a rule. Mitigation: a section-by-section `/ds` pass and independent full-coverage review.
