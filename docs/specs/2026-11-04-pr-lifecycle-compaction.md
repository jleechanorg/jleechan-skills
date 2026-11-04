# Specification: compact pr-lifecycle and the /prw family

- **Outcome:** `.claude/skills/pr-lifecycle/SKILL.md` and its /prw entry points carry each rule once, with pointers instead of restatements. Agents load less text per /prw run, and wording no longer drifts between copies. The /prw wording-freeze tests are removed under the repository testing policy.
- **Non-goals:** changing any gate, threshold, quorum, review route, exception or merge rule; restructuring the opt-in six-stage section into reference files; editing skills outside the /prw family except to remove copied text.
- **Acceptance:**
  - Every removed sentence is either still stated by its owning section or skill, or is an exact duplicate.
  - Every `pr-lifecycle/SKILL.md#anchor` link in the catalog resolves, enforced by the anchor-resolution guard test.
  - The extracted `scripts/pr-base-changed-paths.sh` behaves exactly like the removed inline block under the fake-gh tests, and ships executable with the prw installer profile.
  - The contract test modules and CI pass at head.
- **User stories:** an agent running /prw reads a shorter contract with the same gates. An agent editing a heading that a sibling links to gets a failing anchor test instead of a silent broken link.
- **Proof plan:** run the fake-gh script tests, the installer profile test, the anchor guard with a renamed-heading negative check, and CI. Get independent adversarial review of every removed sentence against its surviving owner.
- **Mock:** exempt. There is no UI.
- **Risk:** medium. This is agent-instruction policy text, and a lost clause would silently weaken a gate. The mitigation is independent multi-seat review. Clauses that review found narrowed (visual-approval alternatives, the generic /wa timeout sentence) were restored.
