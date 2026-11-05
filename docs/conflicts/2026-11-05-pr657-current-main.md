# PR657 current-main reconciliation
Normal merge parents: original PR head e14c2a8b22ddfed0a1808b1c5508ef91250f1600 and current main 921015581f5e061f9a2fdc75cd7ff01aed02dd97.

## Combined resolution
- Before: the candidate duplicated access-mode/lifecycle instructions, added a duplicate root access specification, and modified three prose contract tests.
- After: retain current main versions of lifecycle and all tests, including its no-runner and no-prose-pin contracts. Do not reintroduce the duplicate root spec. Preserve the only unique intended behavior in the existing advice/static-review owners: immutable full-40-hex revision targets versus a DOCUMENTS bundle target.
- After: clarify that MODEL identifies the reviewer runtime/model or says unreported; it never describes the reviewed software. This repairs the repeatedly observed ambiguous output instruction without a new parser, validator, model choice, or count rule.

Current main's dated October29 specification remains historical and is not rewritten to carry current rules; the canonical owners and this PR's source/scenario receipt hold the small residual.
