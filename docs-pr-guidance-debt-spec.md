# PR guidance debt outcome spec

## Problem

Several shared skills and examples still describe an older pull request body, so agents can create draft PRs with incomplete sections or duplicate a second body contract. The `/advice` instructions also need to distinguish installed timeout behavior from the required complete-attempt deadline and describe document-overlay integrity accurately.

## Desired outcome

Align the shared CLAUDE example, factory-evolve workflow, and publishing-sanitizer example with the canonical PR description contract. Make advice timeout and overlay guidance match verifiable runner behavior and avoid treating per-process timeouts or byte hashes as stronger guarantees than they provide.

## Tenets

- Keep one canonical PR description contract and point examples to it.
- Preserve repo-specific evidence, user-story, visual-evidence, and review-ledger requirements.
- State installed behavior separately from a proposed or unavailable capability.
- Preserve full-permission reviewer execution and exact-scope review receipts.
- Ship documentation-only scope as Markdown files.

## Acceptance criteria

- The legacy example no longer presents a six-heading body as canonical or makes user stories optional without the required reason.
- The factory-evolve draft step requires a complete body at draft creation, current line deltas, and the repository-specific evidence fields.
- The sanitizer example retains leak-check evidence while dropping its duplicate body structure.
- Advice distinguishes reviewer-process timeout from a complete attempt deadline, accurately scopes timer start and cleanup limitations, and states that byte verification is integrity evidence rather than filesystem immutability.
- Alternate reviewer command forms are not described as full-attempt bounded unless an existing supported invocation supplies that bound and its own receipt.
- `git diff --check` and the portable-skill verifier pass; no code, scripts, tests, or CI changes are included.
