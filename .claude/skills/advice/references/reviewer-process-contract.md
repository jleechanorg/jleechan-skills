# Reviewer process contract

- **Outcome:** each reviewer starts with stdin at EOF, and process-tree sampling permits up to ten seconds for `ps`.
- **Non-goals:** change reviewer selection, dirty-checkout admission, clone isolation, verdict parsing, or process cleanup.
- **Acceptance:** a real reviewer child reading stdin finishes while its caller's input pipe remains open; the process snapshot invokes `ps` with a ten-second timeout; installed smoke tests exercise the current exact-SHA contract.
- **User story:** before, an input-reading reviewer can wait for an inherited terminal or pipe; after, it receives EOF immediately and can produce its review.
- **Proof plan:** demonstrate the stdin regression on the prior runner, pass it on the candidate, run the full focused runner suite, and verify clean installation copies the companion smoke suite.
- **Mock exemption:** no visual interface changes. The stdin boundary uses real subprocesses; only the `ps` timeout assertion mocks command execution.
- **Risk:** a slow `ps` can delay a sample for ten seconds. Existing reviewer deadlines, descendant termination and clone-integrity checks remain the governing behavior and retain their integration coverage.
