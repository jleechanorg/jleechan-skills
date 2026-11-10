---
name: swarm
description: Run a goal as parallel agent lanes (a local Workflow fan-out, local Agent-tool lanes, or remote tmux lanes on another host) with one writer per branch, adversarial verification of real outputs, and a lean status registry
---

# /swarm — parallel lanes with verification

`/swarm <goal> [--engine workflow|agents|remote] [--shape retro|review|solutions|innov|triage] [--sidekick [model]]`

Split a goal into independent lanes, run each on the engine that fits, verify what the lanes produced, and ship. The deliverable is the shipped result. Orchestration records exist only so a run can be resumed.

## Pick the engine

| Engine | Use when | Mechanics |
|---|---|---|
| **Local Workflow** | The fan-out shape is known before launch and results come back as data: mining, review, audit, triage, per-item transforms | Workflow tool script built from `agent()`, `parallel()`, `pipeline()` and `phase()`, with a JSON schema per structured output. Resume with `{scriptPath, resumeFromRunId}`. Requires the user's opt-in: the word "ultracode" or an explicit request for a workflow. |
| **Local Agent lanes** | A few long-lived lanes need steering mid-flight, or each next step depends on what the last one found | Agent tool background subagents, steered with SendMessage. Each writing lane gets its own worktree and branch. |
| **Remote tmux lanes** | The local host cannot admit the work (CPU, RAM, disk, a host-only tool), or the lane must outlive this session | [linux-mirror](../linux-mirror/SKILL.md) hands the committed branch to a configured remote host in a persistent tmux session; [linux-remote](../linux-remote/SKILL.md) owns transport and the response-proof contract. Unavailable when no remote host is configured: report that and use a local engine. |

Decide in this order:

1. Fewer than three independent units, or work one agent finishes in minutes: no swarm. Do it inline.
2. The lane must survive the end of this session, or the local admission gate refuses it: remote tmux lane.
3. The work-list and stages are known up front and no lane needs steering: Workflow. Scout the work-list inline first, then fan out over it.
4. Otherwise: Agent lanes.

Engines mix. A common split is a Workflow for the bounded review fan-out, Agent lanes for the fixes, and a remote lane for the long test run.

**Sizing and models.** [parallelize-to-ceiling](../parallelize-to-ceiling/SKILL.md) owns lane sizing, the resource admission gate, host selection and model-tier routing; load it before a fan-out. Start at about ten agents per workflow and go wider only when the work-list or the user calls for it. An agent spawned without `model` inherits the session model, so set a cheaper tier explicitly on mechanical stages.

## Lane ownership

- **One writer per branch.** Every writing lane has its own branch and its own checkout: `isolation: 'worktree'` in a Workflow, a worktree for an Agent lane, the mirrored checkout for a remote lane. After a branch is handed to a remote lane, the local side stops writing to it.
- Read-only lanes share freely. Each lane writes its results to its own file or directory; no two lanes write the same mutable file.
- One integration owner, normally the main session, merges lane branches and pushes. Lanes do not push to each other's branches. It stages only the exact authorized files and commits and pushes through the owning repository's workflow; merging, pushing or publishing still needs the authorization that action normally requires. Never commit raw captures or temporary datasets into a code repository.
- Never `git commit -a` or `git add -A` in a checkout that carries another actor's staged or modified work; use a path-scoped `git add -- <paths>` only.
- Miners read a dataset built once in the main loop instead of each making live API calls.
- Actions that trigger CI (pushes, branch updates) are batched against the runner fleet's capacity, which is a separate limit from agent concurrency. One push can start dozens of jobs.
- A blocked gate blocks only the items that depend on it. Keep dispatching file-disjoint work.
- When a PR driver owns the review budget for a PR, start only the reviewers it assigned. That budget also governs verifier and advice fan-out, including delegated runtimes. When the budget or the driver's authority is unclear, stop automatic reviewer dispatch and ask the driver.

## Verification

- **Check real outputs.** A lane's "done" is a claim. The verifier opens the diff, runs the test or command, reads the rendered artifact, or fetches the PR head. It does not grade the lane's summary of itself.
- **Refute by default.** A finding that drives a decision faces three independent lenses (for example evidence, design, severity), each prompted to refute it, and survives on two of three. A cheap, reversible claim gets one check.
- **A dead verifier is not a refutation.** `agent()` returns `null` when a subagent dies; re-run those. A stage that returns zero findings while most of its agents failed did not run. Read the run's `journal.jsonl` before recording an empty result.
- **Merge-readiness and bug-fixed claims on code** need one reviewer from a different model family that executes the code (`/advice`, or an installed second CLI). Reproduce its most concrete finding yourself before accepting the rest.
- **Reuse valid coverage.** A review or test run that already covered the current head SHA counts. Re-verify only what changed since. Evidence is the command output, the diff and the PR; do not build ledgers or receipts for it.
- **Published docsets** get one pass before publication for leaked local paths or credentials, numbers that disagree between documents, and present-tense claims that are stale at the current head.
- Never report a review or verification that did not run.

## Status registry

The main session keeps one table and updates a row when that lane changes state, not on a timer:

| Lane | Engine | Owns (branch or output path) | Handle | State | Last evidence |
|---|---|---|---|---|---|
| fix-auth | agents | `fix/auth` | agent name | running | test command and result |
| long-tests | remote | `fix/auth-tests` | host and tmux session | waiting | last agent response |

The handle is the workflow run id, the agent name, or the remote host plus tmux session. For a run that ends within the session, the table lives in the conversation. Write it to `${ROADMAP_DIR:-$HOME/roadmap}/<project-slug>/swarm/<mission>/STATE.md` only when the run has to be resumable after the session ends, and record the next command to run beside it. When a sidekick is running, its STATE.md is the registry.

Liveness comes from what the lane last did, not from file mtimes or a status string: the agent transcript for local lanes (procedure in the [sidekick](../sidekick/SKILL.md) skill, "Transcript-proof liveness"), a fresh attributable agent response for remote lanes (linux-remote's response-proof contract; a tmux session that exists proves transport only). Redact secrets before quoting transcript snippets. A lane is stalled only when its transcript shows no events across two checks and no live OS process backs it; only then take over or respawn. A resource probe never authorizes killing or restarting another lane. A lane with a live process and a silent transcript across two checks may be sitting on a rate-limit modal; look before respawning.

## Long runs

- `--sidekick [model]`: for a run expected to outlast one context window or session, such as an overnight drive, wrap it with `/sidekick`. That skill owns STATE.md, checkpoints and respawn. Shorter runs do not need it.
- Rate limits are aggregate across every swarm running on the account. Do not start two large fan-outs in the same minute. Stagger heavy lane starts: launch a wide fan-out in batches of about eight a few seconds apart, not as one instant burst. On mass 429s: stop, wait, probe with a single agent, then resume from the run id.
- A workflow resumes from its run id with cached results for unchanged `agent()` calls. Edit only calls that have not completed.

## Shapes

| `--shape` | Phases |
|---|---|
| `retro` | Collect (themed miners) → Verify → Synthesize → Plan (one doc per confirmed finding) |
| `review` | Review (rubric × module cluster) → Dedup → Verify → Doc per problem class |
| `solutions` | Attack each plan → Redesign with the surviving attacks |
| `innov` | One strongest addition per finding → Challenge |
| `triage` | Single fan-out: one agent per PR or lane, structured verdict |

The shapes are not code-specific. The same mine, verify, synthesize sequence runs research, incident retros and audits.

## Recipe

1. Recall prior runs and datasets with `/history <keywords>` when the goal has history; skip for a fresh, small goal.
2. List the lanes, pick an engine for each, and assign each writer its branch.
3. Launch independent lanes together and enter their handles in the registry.
4. Verify each lane's output as it lands, then integrate it.
5. Close by reporting what shipped, what was verified and how, and what remains. Run `/learn` when the run taught something non-obvious.
