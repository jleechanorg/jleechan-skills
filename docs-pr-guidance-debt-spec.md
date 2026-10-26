# PR guidance debt outcome spec

## Outcome

Several shared skills and examples still describe an older pull request body, so agents can create draft PRs with incomplete sections or duplicate a second body contract. The `/advice` instructions also need to distinguish installed timeout behavior from the required complete-attempt deadline and describe document-overlay integrity accurately.

Align the shared CLAUDE example, factory-evolve workflow, and publishing-sanitizer example with the canonical PR description contract. Make advice timeout and overlay guidance match verifiable runner behavior and avoid treating per-process timeouts or byte hashes as stronger guarantees than they provide.

## Non-goals

No runtime timeout implementation, reviewer wrapper, test, script, CI change, policy change, or host synchronization is included. The runtime implementation and evidence remain a separate lane.

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

## User story

No user-facing product change. Agents creating or reviewing PRs receive consistent instructions, and reviewers can distinguish installed timeout behavior from the documented contract.

## Proof plan

- Run `git diff --check`.
- Run `python3 scripts/verify_portable_skills.py portable`.
- Inspect the changed examples and advice skill against their referenced canonical contracts and installed runner source.
- Record reviews as pending until an eligible reviewer completes the required independent review with exact-SHA coverage and a receipt.

## Mock

Not applicable: this is a Markdown-only agent-guidance change and creates no UI or runtime behavior to mock.

## Risk

The advice timeout contract could overstate installed behavior if implementation and documentation drift. The text therefore marks the currently installed path unavailable for the complete-attempt guarantee, requires receipt-backed bounded routes, and explicitly excludes pre-main-entry dispatch delay and potentially blocked OS cleanup from any hard wall-clock claim.
