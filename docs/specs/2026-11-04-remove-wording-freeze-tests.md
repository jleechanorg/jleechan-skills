# Specification: remove wording-freeze tests repo-wide

- **Outcome:** the repository test suite no longer contains assertions that pin prose in Markdown or instruction files, so skills can be reworded and compacted without editing tests. The suite keeps every test that runs code, every structural invariant, and every zero-PII and portability scan, per the AGENTS.md testing policy.
- **Non-goals:** changing any skill, command, script or CI workflow; adding new tests; editing historical plan or spec documents that cite deleted test files (they record past work).
- **Acceptance:**
  - No remaining test asserts phrase presence, phrase order, old-wording absence, or prose length on Markdown or instruction files.
  - Kept: executed-script and executed-snippet tests; installer tests; frontmatter, link, path and filename contracts; static lints of executable shell blocks; PII, private-location and portability scans; thin-dispatcher size limits.
  - The full suite shows no failures beyond the known environment-only set (rsync missing, shallow clone, running as root).
  - The CI-run scripts under `.claude/skills/dot-coordinator/tests/` and `.claude/skills/timeline/scripts/` still pass.
- **User stories:** an agent that compacts a skill does not have to restore deleted sentences to keep tests green. An agent reading a failing test sees a behavioral or structural failure, not a wording diff.
- **Proof plan:** run the full `unittest discover` suite and the CI-run scripts at head, then get independent adversarial review of every deleted assertion against the policy's keep list.
- **Mock:** exempt. There is no UI.
- **Risk:** medium. Removing assertions can drop real guards. The mitigation is the explicit keep list above and adversarial review. Checks that review found wrongly removed (private-location scan, shell safety lints, path contracts, fixture guards) were restored.
