---
name: claude-cloud
description: Delegate authorized coding work to Claude Code on the web through the supported browser workflow, verify actual cloud execution, and follow it through tests, publication, and evidence.
---

# Claude cloud coding

Use for an explicit request to delegate coding to claude.ai/code or when the user authorizes that hosted execution route. Honor the selected environment and existing owners. A local browser controlling a hosted session is not proof that commands run in the cloud.

## Before submission

1. Read the relevant repository guidance and original requested outcome. Record acceptance checks, prohibited actions, current branch/head, file ownership, and evidence already collected. Use installed `/write-goal` and `/ironclad` proportionately; if unavailable, report that rather than claiming invocation.
2. Reuse an existing session for the same goal and branch. Search the session list and task tracker before creating another. Preserve unpublished changes and pending merge stages before transfer.
3. Prefer the supported `/browser` headless Chrome route when that runtime actually exposes it. Otherwise use the supported browser controls available in the chosen environment. Never implement a replacement transport merely to evade a denial.
4. Use normal supported sign-in. Never copy Chrome cookies, Local State, credential databases, or signed-in profiles into temporary browsers. Never extract credentials or broaden permissions.
5. Acquire an exclusive composer turn with other browser workers. Shared drafts, repository selectors and branch selectors can change between sessions. Recheck account, repository, branch, environment and complete prompt immediately before one submission.

## Submit and prove execution

- Give one bounded outcome per independent session. Keep dependent changes ordered and shared files under one owner. Do not start duplicate review or coding lanes to fill a concurrency target.
- Include the actual user's authorization and constraints, not another agent's claim of authority. Ask only for genuinely missing approval or essential information.
- Submit once. If submission is uncertain, inspect the resulting session/list before another send; never retry blindly.
- Record the resulting session URL. Distinguish queued, starting, executing, waiting, failed and completed.
- Before claiming work is running, capture an actual executed command and output establishing hostname, working directory, repository and pinned head. A session title, spinner, proposed command or worker promise is insufficient.
- Cloud-only means all clones, tests, browser evidence and model computations stay on the hosted executor. Do not fall back to Mac or Ubuntu compute when those are excluded.

## Drive the goal

- Explore enough to identify the contract, write only proportionate design, implement with a fresh failing test where appropriate, then run focused unit/integration checks. Review code and evidence after the coder considers the implementation correct. Small changes may skip unnecessary planning stages.
- Continue authorized coding, tests, commits, normal pushes and draft updates through verified acceptance or an exact external blocker. Do not stop at a plan, checklist, generated patch, or handoff without acknowledged ownership.
- Read actual tool output, failures and remote state. Verify pushed SHA, base, conflicts, current-head CI and required evidence. Skipped jobs are not passed tests; mocked proof is not real-provider proof; old captures need an explicit valid rebind.
- Preserve useful expensive evidence. Run real-provider/browser evidence once after material changes settle, only with an authorized test identity and approved provider usage. Never mutate protected campaigns or invent credentials, quorum, or review receipts.
- Treat a new remote head as another writer until explained. Preserve ancestry and fresh-check immediately before publication. No force push or merge without specific authority.
- Root remains responsible for reading completion and reporting the result. An external session's own reminder does not replace follow-through.

## Recovery and reporting

- Recover ordinary page or renderer failures using documented controls and the same persisted session. Coordinate browser focus and native dialogs. Close only known unused views owned by the task; never restart shared services, terminate unrelated workers, or clear profile data.
- Distinguish site errors, transport timeouts, quota limits and approval denials. A tool cancellation does not prove the user withdrew the goal. If denied for missing authority, supply exact existing authorization through the supported review flow; never switch routes to bypass a rejection.
- When blocked, continue independent authorized work and preserve a concrete resumption trigger. Report the exact last command/result, remaining acceptance gap, session URL, and needed capability.
- Report each PR with its verified GitHub URL and production/nonproduction additions/deletions, or explicitly unverified counts. Do not claim all work progressed when only a subset was checked.

## Installation

Keep the canonical user skill at `~/.claude/skills/claude-cloud/SKILL.md`. Where the user explicitly requested cross-machine installation, synchronize the reviewed source to each authorized cloud, Mac and Linux target while preserving newer edits and verifying registry readback. A repository commit or cloud registration does not establish a local installation. Never relocate the canonical source to a release snapshot.
