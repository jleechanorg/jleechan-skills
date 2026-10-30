---
name: advice
description: Obtain independent, revision-bound second opinions with explicit coverage and a fail-closed approval quorum.
---

# Advice

1. Ground the decision, constraints, exact revision or document hashes, complete changed files/diff and relevant evidence. Give reviewers pointers to readable artifacts, not the entire conversation or a framed question; the orchestrator answers the user's question in its synthesis.
2. Use [parallelize-to-ceiling](../parallelize-to-ceiling/SKILL.md) for independent native reviewer lanes within current authorized capacity. Reviewers must read the complete assigned material independently. Preserve their identity, revision, coverage and raw verdict as review evidence.
3. At least two independent full-coverage approving reviewers are required for APPROVED. Research and the orchestrator do not vote. One reviewer can block but cannot approve; unavailable or partial coverage cannot satisfy quorum. Report APPROVED, NOT APPROVED or WITHHELD, with findings and missing coverage.
4. Run [research](../research/SKILL.md) only when a separate unanswered source question warrants a lane; keep it outside the approval quorum. External browser review is a separate [web-advice](../web-advice/SKILL.md) route requiring the applicable recipient/content authorization, never an automatic fallback.
5. Bind findings to paths/lines and the exact source revision. After a head move, inspect the delta and changed external artifacts. Material changes need fresh review. A nonbehavioral delta may be explicitly reaffirmed only with prior coverage, provenance and the new delta reviewed; never relabel old evidence.
6. Preserve completed results and retry only concretely failed lanes. Read supporting artifacts before relying on a reviewer summary. Resolve findings or report why approval is withheld.
7. Save the bounded synthesis in the authorized workspace. Publishing a gist, PR comment, or private source to an outside provider is not implicit. Missing transport means missing coverage, not permission to bypass access controls.
8. Every reviewer gets a cold, verbatim, skill-owned prompt (only PR URL/SHA or document hashes filled) plus a fixed per-channel preamble; the receipt records the exact prompt, and any deviation voids the vote. Static-review subagents launch in parallel with the coordinator ask (or, with no coordinator, with the CLI attempts) and fill only slots still unfilled after every CLI attempt and coordinator account ends (owner-authorized 2026-10-29); one outside vote pairs with one static reviewer, never double substitution. Record each unavailable seat as host, CLI or static reviewer, attempted or skipped, time and reason, and tell the user. Static-review votes need the canonical `/static-review` skill's verbatim templates and preambles; this portable package does not ship them, so where that skill is not installed, record static review as UNAVAILABLE rather than improvising a prompt.
