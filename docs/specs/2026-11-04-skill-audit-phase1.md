# Phase 1 skill audit

## Outcome

Make `redgreen`, `4layer`, `superpowers-quick` and `harness-engineering` easier
to follow by removing repeated instructions and moving incident narratives to a
reference file. Check `advice` and the `four-layer` alias without changing them.

## Non-goals

Do not change rules, gates, thresholds, quorums or authorization. Do not resolve
canonical-versus-portable contradictions, rewrite portable copies, install or
sync skills, merge, or deploy. The `evidence-review` audit is a separate remaining
slice; this change does not claim the six-skill Phase 1 exit criterion.

## Acceptance

- `redgreen` has one RED / CODE / GREEN / CONSENSUS sequence and preserves all
  eight critical rules, including the fresh-run RED gate.
- `4layer` states runner discovery and unsupported execution once, keeps the
  pass-only ladder and mandatory companions, and matches its shared-catalog hash.
- `superpowers-quick` preserves the planning-only handoff, independent advice and
  browser-review records, exact-document-hash binding, owner-defined retries and
  authorization. Only a prior browser submission covering both exact hashes may
  substitute for its browser review; a CLI-only advice verdict cannot.
- `harness-engineering` keeps the rules inline and moves the two incident
  narratives without losing their content or installer reachability.
- Changed skill dependency sets stay unchanged. Replace the roadmap-snippet
  wording pin with an executable check; preserve relevant mechanical tests.
- Record unresolved contradictions explicitly rather than deciding policy during
  prose cleanup. Required independent review remains a separate acceptance gate.

## User story

A developer following these skills reads one clear sequence instead of repeated
instructions and can still find the worked incidents. Shorter instructions retain
the same testing, evidence, review and permission requirements.

## Proof plan

Compare the complete diff with its base and map removed instructions to their
remaining owners. Check portable copies for contradictions and report them.
Compare installer dependency sets, verify the reference-file move and catalog
hash, and run the installer, sync, portability, test-integration, shared-skill,
usage, roadmap-snippet, approval and catalog tests listed in the PR. Review prose
semantics independently, without adding wording-pin assertions. Obtain the two
static-review receipts required by the audit plan on the final candidate before
claiming approval; test success alone is not review approval.

## Mock exemption

No application UI or rendered-data claim changes. The deliverable is agent
instruction text, an installed reference file, a catalog hash and an executable
test. A UI mock, screenshots and live-provider calls would not prove this scope.

## Risk

Removing a qualifier can silently weaken a required review or authorization gate.
Review every deletion against the original contract, preserve unresolved policy
questions, and keep the PR draft while required review is unmet. Passing tests
establish mechanical behavior, not equivalence of the instructions' meaning.
