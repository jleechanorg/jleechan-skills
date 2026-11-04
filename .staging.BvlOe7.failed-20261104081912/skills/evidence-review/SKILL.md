---
name: evidence-review
description: Review claim coverage, integrity and provenance with an explicit evidence verdict.
---

# Evidence review

Read [evidence-standards](../evidence-standards/SKILL.md), the claimed outcome, repository evidence overlays and exact current revision. Review the actual artifacts and their source records.

Check separately: (1) byte integrity/checksums, (2) source and revision provenance, (3) whether real execution occurred at the claimed layer/model/service, and (4) whether the evidence covers each acceptance claim. Actual model identity comes from authoritative runtime receipts, not a filename or requested flag. Verify privacy/redaction and authorized audience before sharing.

Report one primary verdict: PASS when every required claim is supported; FAIL for contradicted claims or violated mandatory standards; PARTIAL when some required claims are supported but coverage is incomplete; INCONCLUSIVE when provenance/availability prevents a reliable determination. FAIL takes precedence over PARTIAL/INCONCLUSIVE when a mandatory violation is established. Notes are annotations, not a separate WARN approval state. Missing proof never earns PASS.

Use independent native review when required by the active workflow; do not label self-checks independent. Cite file/line or artifact locators, hash/revision, finding severity, missing evidence and a concrete remedy. Public hosting is not required for valid private evidence, and publication is never automatic.

On a head or external-artifact change, inspect the delta before reusing a verdict. Preserve original capture provenance; material changes require new evidence and review. Return the report to the owning workflow without starting unrequested repairs or ending its other authorized work.
