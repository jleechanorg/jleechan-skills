# Reviewer process contract

- **Outcome:** each reviewer starts with stdin at EOF, and process-tree sampling permits up to ten seconds for `ps`.
- **Non-goals:** change reviewer selection, dirty-checkout admission, clone isolation, or verdict parsing.
- **Acceptance:** a real reviewer child reading stdin finishes while its caller's input pipe remains open; the process snapshot invokes `ps` with a ten-second timeout; sampled Linux parent/child identities are revalidated with pidfds before descendant admission or signaling; installed smoke tests exercise the current exact-SHA contract.
- **User story:** before, an input-reading reviewer can wait for an inherited terminal or pipe; after, it receives EOF immediately and can produce its review.
- **Proof plan:** demonstrate the stdin regression on the prior runner, pass it on the candidate, exercise reused root/parent PID regressions, run the full focused runner suite, and verify clean installation copies the companion smoke suite.
- **Mock exemption:** no visual interface changes. The stdin boundary uses real subprocesses; only the `ps` timeout assertion mocks command execution.
- **Risk:** a slow `ps` can delay a sample for ten seconds. Linux descendant signals use a pidfd and a post-acquisition start-time check; a failed or unavailable identity proof never falls back to numeric `kill`. Start-time ticks can collide for processes created in the same clock tick, so this is bounded identity checking, not a proof of exhaustive or race-free cleanup. Platforms without pidfd can only signal the reviewer process group while its direct child remains unreaped, so a tracked descendant outside that group remains visible as a cleanup failure. Sampling is best effort and cannot discover a descendant that escapes before observation.
