# PR workflow discovery and agent-readable compaction

## Outcome
Make the existing PR Workflow Manager discoverable immediately below the README's
six highlighted skills, and reduce copied instructions without changing the canonical lifecycle.

## Non-goals
No new workflow or alias, host installation, runtime changes, merge authorization,
review waiver, or rewrite of incumbent-owned advice instructions.

## Acceptance
- README links the manager, existing alias and lifecycle beneath the highlights.
- Manager names useful highlighted helpers without making them additional gates.
- Duplicate visual and integration rules link to their canonical owner.
- Evidence reuse checks base, evidence, scope and phase even at the same HEAD;
  this aligns the shortcut with the existing canonical SHA-binding requirement.
- Mandatory companions, fail-closed behavior and independent review remain intact.

## User story
An agent opening a PR can find one entry point, select relevant helpers and follow
canonical rules without reconciling duplicate policy paragraphs. No application UI changes.

## Proof plan
Run lifecycle/approval contracts, isolated profile installs and README count checks.
Check relative links and GFM output. Review the complete diff against the original
rules with independent document-review lanes; retain limitations and original times.

## Mock exemption
No application or rendered-product change. Markdown parsing checks document structure;
no screenshot is claimed as proof of application behavior.

## Risk
Compaction can hide a gate or weaken a boundary. Keep mandatory canonical links,
local failure consequences and regression assertions. Leave the PR draft; readiness
and merge require separate applicable gates. Existing advice work remains untouched.
