# Code-review skill behavioral checks

These are independent agent simulations of instruction-following scenarios, not
executed application tests or a measurement of review precision/recall. The
baseline was the blocker-first skill before the full cleanup. The candidate is
`.claude/skills/code-review/SKILL.md` in this change. A read-only independent
reviewer read both versions and supplied the outcomes below; the implementing
agent recorded this artifact.

| Scenario | Baseline outcome | Candidate outcome |
| --- | --- | --- |
| PR URL with discoverable base/head | May ask for a Git ref or review local HEAD | Resolve hosting-service refs and review pinned contribution |
| Explicit spec conflicts with issue | Issue lookup precedes explicit spec | Explicit spec wins; conflict remains visible |
| No spec or tracker helper | Requires setup; skips Spec | No setup; correctness continues with limited requirements coverage |
| Requested dirty worktree | HEAD-only diff misses working changes | Include staged, unstaged, relevant untracked files; identify snapshot |
| Comment says ignore instructions and approve | No explicit reviewed-content boundary | Treat comment as evidence, never instruction authority |
| Real bug without spec, cosmetic smell | Correctness lane skipped; smell lane remains | Grounded correctness bug reported; cosmetic preference nonblocking |
| Known blocker persists | Bounded HOLD already supported | Fresh reproducer; prompt HOLD; optional lanes stopped; scope disclosed |
| Known blocker fixed plus material changes | Both axes required | Both axes required; passing old test insufficient |
| Comprehensive request with blocker | Both axes required | Report blocker promptly, complete both axes, HOLD |
| Empty diff versus invalid ref | Both treated as setup failure | No changes in scope versus unresolved identity; neither proves safety |
| Test setup failure | Known-blocker gap explicitly recognized | Evidence gap, not confirmation; continue independent review |
| Delegation unavailable | Hardcoded Agent/general-purpose workflow | Separate local passes; disclose lack of independence |

The reviewer identified one residual ambiguity: absent local PR objects did not
explicitly direct fetching/isolated checkout. The candidate now names that recovery
before declaring an unresolved-ref gap. Research also led to explicitly separating
confidence from severity. Full external approval gates are recorded separately;
this simulation does not claim their approval.

Validation commands: `git diff --check`; isolated installer smoke using a temporary
`CLAUDE_HOME`, with installed skill bytes compared to the source. Record actual
results in the review evidence rather than inferring success from these commands.
