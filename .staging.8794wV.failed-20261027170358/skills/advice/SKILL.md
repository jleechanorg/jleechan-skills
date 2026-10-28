---
name: advice
description: Obtain independent, revision-bound second opinions with explicit coverage and a fail-closed approval quorum.
---

# Advice

1. Ground the decision, constraints, exact revision or document hashes, complete changed files/diff and relevant evidence. Give reviewers a bounded question and pointers to readable artifacts, not the entire conversation.
2. Use [parallelize-to-ceiling](../parallelize-to-ceiling/SKILL.md) for independent native reviewer lanes within current authorized capacity. Reviewers must read the complete assigned material independently. Preserve their identity, revision, coverage and raw verdict as review evidence.
3. At least two independent full-coverage approving reviewers are required for APPROVED. Research and the orchestrator do not vote. One reviewer can block but cannot approve; unavailable or partial coverage cannot satisfy quorum. Report APPROVED, NOT APPROVED or WITHHELD, with findings and missing coverage.
4. Run [research](../research/SKILL.md) only when a separate unanswered source question warrants a lane; keep it outside the approval quorum. External browser review is a separate [web-advice](../web-advice/SKILL.md) route requiring the applicable recipient/content authorization, never an automatic fallback.
5. Bind findings to paths/lines and the exact source revision. After a head move, inspect the delta and changed external artifacts. Material changes need fresh review. A nonbehavioral delta may be explicitly reaffirmed only with prior coverage, provenance and the new delta reviewed; never relabel old evidence.
6. Preserve completed results and retry only concretely failed lanes. Read supporting artifacts before relying on a reviewer summary. Resolve findings or report why approval is withheld.
7. Save the bounded synthesis in the authorized workspace. Publishing a gist, PR comment, or private source to an outside provider is not implicit. Missing transport means missing coverage, not permission to bypass access controls.
