# Provenance

This package is a portable generalized `test-realistic` skill. Its installed-runtime files were retained as a byte-level baseline, but the exact versioned upstream Git lineage of that runtime remains unknown. The import record establishes which package contents were compared; it does not establish their repository ancestry.

A historical Linux sync record attributes the design to `worldarchitect.ai/testing_ui/realistic` and `docs/plans/2026-08-09-test-realistic-generalization-design.md`. Preserve these as historical design references only. They do not prove that the imported runtime came from that repository or document, or establish byte-for-byte runtime Git history.

Executable defaults contain no project-specific configuration or credentials. The historical references above are attribution only. Update the runtime lineage only when a versioned source verifies it.

## Seven-element specification

1. **Outcome:** Version the installed portable runtime and prevent incomplete player captures or failed adapters from producing a coverage pass; bind PR scenario context to immutable comparison revisions.
2. **Non-goals:** No player-facing application change, project-specific adapter implementation, synthetic acceptance evidence, definitive upstream runtime ancestry, or model-error fallback.
3. **Acceptance:** Before judgment, the number of matched capture files equals the emitted pool size, and every matched file contains a parsed nonempty JSON object. Malformed, missing, or empty captures fail. A nonzero dispatch fails unless dispatch excuses were explicitly enabled and the configured predicate returned a valid `(bool, str)` result with `True`. This check does not correlate a capture file to a particular actor. PR context is fetched from the configured repository root and uses the observed repository and immutable base/head revisions. Historical design references remain distinct from unknown runtime Git ancestry.
4. **User stories:** No player-facing change. A maintainer receives an explicit failure for incomplete testing instead of a misleading pass, while project adapters may exercise real browsers or native clients with truthful runtime provenance.
5. **Proof plan:** Reproduce the capture and adapter defects offline, run the package regression tests, check the actual GitHub metadata/immutable diff command, verify the installer includes all runtime resources, and compare scoped Mac/Linux bytes. Real application behavior requires a separate real-client/provider run; unit and installation checks make no such claim.
6. **Mock:** Visual mock exempt: no application UI changes. Offline tests use explicit fake dispatcher/model seams only to prove harness mechanics; they are not real-service acceptance evidence.
7. **Risk:** Existing runtime ancestry is unknown; large PR context is explicitly bounded and actor/persona pairing preserves its existing shortest-list behavior. Source review, evidence review and host sync must retain their exact tested/reviewed revisions. No native app or physical-device result follows from these harness changes alone.
