---
name: harness-postmortem
internal-aliases: ["meta"]
version: 0.5.0
description: "Harness-fix meta-skill (slash: /meta) — analyze an agent behavior failure and run /harness to fix the agent, NOT the underlying task. Input: Slack thread URL, pasted conversation, or freeform description of agent misbehavior. Re-anchored on MAST (arXiv:2503.13657) and ETCLOVG (arXiv:2606.06324) failure taxonomies; supersedes the trivial '5 Whys' spine with the Observe→Isolate→Simulate→Evaluate 4-step pattern, retaining 5-Whys as a Simulate-phase prompt heuristic. v0.4.0 (2026-07-14): adds Phase 1.5c — 'Polluted PR (merged another PR's full history)' detection recipe + companion skill `pr-cleanup-replay` + reference file `references/polluted-pr-cleanup-replay.md`. v0.3.0 (2026-07-05): adds Phase 1.5 'fix authored but never merged to origin/main' detection recipe + replaces naive `deploy.sh --skip-pull --skip-restart` with the staging-dirty-surgical-sync recipe that actually works when staging is on a non-main branch."
tags: ["meta", "harness", "autonomy", "agent-behavior", "no-confirmation-gate", "scope-guardrail", "mast", "etclovg", "reflexion"]
category: workflow
triggers:
  - autonomy violation
  - hermes refused
  - agent refused
  - agent stopped halfway
  - stopped halfway
  - why did hermes stop
  - why did the agent stop
  - agent didn't do its job
  - hermes didn't do its job
  - you didn't do your job
  - fix the agent
  - fix hermes behavior
  - fix the harness not the task
  - meta skill
  - /meta
  - run meta
  - harness postmortem
  - harness retro
  - harness audit
  - harness fix
  - agent failure analysis
  - run harness postmortem on
  - stop X from giving me Y
  - stop X from Y
  - stop X from these reports
  - stop MCP mail from
  - stop the bot from
  - passively listening
  - these reports
  - wrong target
  - wrong target removal
  - I said the agent not the cron
changelog:
  - "0.5.0 (2026-07-20): Add Phase 0 working class `wrong-target-removal-on-stop-X-from-Y`. Trigger phrases: 'stop X from giving me Y', 'stop X from Y', 'these reports', 'passively listening', 'self-reports'. Companion SOUL.md `## COMMIT: mcp-agent-mail-no-passive-slack-listening`. Reference file `references/wrong-target-removal-stop-X-from-Y-2026-07-20.md`. Originating incident: Slack thread C0AJ3SD5C79/p1784344760053389 — user said 'Lets stop mcp mail from giving these reports', agent removed `clawchief:ea-sweep-hourly` cron (the wrong target). Actual source was the MCP Agent Mail agent's Socket-Mode listener ingesting Slack messages into MCP, then re-posting agent replies. User feedback (verbatim): 'No keep the job you fucking idiot — I said mcp mail agent I don't want it passively listening to my threads.' Durable fix landed in the second-pass session: env overlay `~/mcp_mail/.env.slack-off` + `run_server_with_token.sh` sources overlay before any other env + plist has no SLACK_ENABLED override + launchd restart + 14-gate contract test."
  - "0.4.0 (2026-07-14): Add Phase 1.5c — 'Polluted PR (merged another PR's full history)' detection recipe. Companion skill `~/.hermes/skills/pr-cleanup-replay/SKILL.md` (4-phase replay recipe) + SOUL.md `## COMMIT: pr-clean-branch-from-main-no-history-bloat` (prevention rule) + contract test `tests/test_pr_clean_branch_contract.py` (5 tests). Reference file `references/polluted-pr-cleanup-replay.md`. Originating incident: PR #8401 (Visenya V8 stuck-lu) inadvertently merged PR #7952's full 22-commit history (31 files, +1413/-629) instead of a clean 2-file / +597/-20 replay. User feedback: 'Seems like this wasnt made from a clean branch from origin/main?'"
  - "0.3.0 (2026-07-05): Add Phase 1.5 — 'fix authored but never merged to origin/main' detection. Replaces naive Phase 3 step 5 `deploy.sh --skip-pull --skip-restart` with the staging-dirty-surgical-sync recipe that actually works when staging is on a feature branch with dirty diff (the recipe that shipped the babysit-cron-leak fix on origin/main as b2ad00770d, cherry-picked from stranded commit 7690435707 on fix/babysit-stale-merged-pr). Bug-ref: 2026-07-05 thread C0AH3RY3DK6/p1783240445.370119 — deploy.sh failed at port:UNBOUND health check while sync stages succeeded silently under [single-dir] mode; previous Phase 3 step 5 instructed the failing invocation as canonical."
  - "0.2.0 (2026-07-02): Reviewer B iteration — rename internal skill `meta` → `harness-postmortem` to avoid collision with `meta-prompting` / `meta-harness` / `MetaGPT`. Slash command `/meta` retained (user's invocation pattern). Add MAST (arXiv:2503.13657) failure taxonomy + ETCLOVG (arXiv:2606.06324) layer model to Phase-0. Replace 5-Whys structural spine with Observe→Isolate→Simulate→Evaluate 4-step pattern; keep 5-Whys as a Simulate-phase heuristic. Cite Reflexion (Shinn et al., 2023). Credit prior art: Refinex-Space `harness-fix` skill + HarnessFix paper."
  - "0.1.0 (2026-07-02): Initial authoring, run on C0AH3RY3DK6/p1782941155305869 autonomy violation (exportcommands). Trigger: 'agent made local commit but stopped at 4-way menu instead of running the slash command or dispatching AO'."
---

# /meta (canonical: `harness-postmortem`) — Fix the agent, not the task

**Naming note (added 0.2.0):** The internal skill name is `harness-postmortem` to avoid collision with `meta-prompting` (Anthropic / LangGPT / SkillMD), `meta-harness` (ruflo, Nx), and `MetaGPT`. The **slash command** remains `/meta` because that's the user's invocation pattern (matches their 2026-07-02 Slack thread phrasing "let's define a skill called /meta"). When invoked via slash, the same skill runs; when resolved via natural-language triggers or referenced in SOUL.md `## COMMIT:` blocks, both `harness-postmortem` and `meta` aliases match.

**The meta-skill.** When the user reports an agent behavior failure (refusal, premature stopping, mid-task clarification freeze, local-commit-without-PR, "want me to X?" after explicit go-ahead, etc.), `/meta` analyzes the failure with the **/harness protocol** and produces a fix that lands in the **agent's harness** — never in the code path the agent was attempting.

## Scope guardrail (the entire skill hinges on this)

`/meta` is **scope-locked** to the agent behavior failure. It does NOT:

- Investigate the underlying task the agent was trying to do (e.g., if the agent refused to make a PR for /exportcommands, `/meta` does NOT run /exportcommands).
- Make a code change to the project the agent was working on.
- Continue the original task under a different framing.

It DOES:

- Read the thread / input describing the agent behavior failure.
- Apply the `/harness` protocol verbatim (5 Whys technical + 5 Whys agent path, existing coverage audit, proposed fixes at the **Instructions / Skill / Test** layer).
- Produce a **durable harness fix** — a SOUL.md `## COMMIT:` block, a new skill, a test, a rule patch, or a documented pattern change.
- Land that fix via the appropriate deploy lane (jleechanclaw self-merge for SOUL.md/skills, PR for project code if the fix is genuinely project-level — but only after explicit Phase-0 confirmation that the project owns the gap).

**Anti-pattern check:** if Phase 0 finds that the fix belongs to the project the agent was working on (e.g., the exportcommands script needs a real fix), `/meta` dispatches that as a separate `dispatch-task` job and produces ONLY the agent-side lessons-learned commit. It does not absorb the project task.

## Input shapes

`/meta` accepts three input shapes — each triggers the same protocol but with different Phase-1 extraction:

| Input shape | Example | Phase 1 action |
|---|---|---|
| **Slack thread URL** | `/meta https://jleechanai.slack.com/archives/C0AH3RY3DK6/p1782941155305869` | `mcp__slack__conversations_replies(channel_id, thread_ts)` to fetch the thread, then extract the failure description. |
| **Pasted conversation** | `/meta <paste full Slack transcript or chat log>` | Regex-split on Slack message boundaries (`MsgID,UserID,...` for CSV exports, or speaker turns for plain text), identify the user-correction message, extract the failure. |
| **Freeform description** | `/meta hermes stopped halfway again, said "want me to push?" after I said go` | Direct parse — no fetch. |

If the input is empty or ambiguous, `clarify` once with the options (URL / pasted text / freeform description). One question, four choices max.

## Phases

### Phase 0 — Classify the failure mode (MAST-anchored)

Read the input, classify the agent behavior failure using the **MAST taxonomy** (Cemri et al., NeurIPS 2025, arXiv:2503.13657 — 14 failure modes, 3 root categories) AND the orthogonal **ETCLOVG layer model** (Chen et al., HarnessFix, arXiv:2606.06324 — 7 layers: Environment, Tool, Context, Lifecycle, Orchestration, Verification, Governance). The combination answers two questions: WHAT failed (MAST root category + specific mode) and WHERE in the harness it failed (ETCLOVG layer).

**MAST root categories** (cite `https://arxiv.org/abs/2503.13657`):

| Category | Frequency | Common modes |
|---|---|---|
| **FC1 — System Design Issues** | ~11.8–15.7% | step repetitions, completion blindness, specification ambiguity, role unclarity, missing constraints |
| **FC2 — Inter-Agent Misalignment** | ~37% | communication breakdowns, conflicting objectives, state desynchronization |
| **FC3 — Task Verification & Termination** | ~21% | premature termination, weak/missing verification of outputs, fabricated verification |

For each incident, classify into ONE of these working buckets (operationalized from MAST + the 2026-07-02 originating incident + Hermes-specific SOUL.md patterns):

| Working failure class | MAST mapping | ETCLOVG layer | Hermes symptom |
|---|---|---|---|
| **`mid-task-clarification-freeze`** | FC1 (specification ambiguity) + FC3 (premature termination) | Verification | Agent asks multi-option menu mid-stream after explicit user invocation. (`finish-the-job` Phase 0 fork-resolution not auto-applied.) |
| **`local-commit-without-PR`** | FC3 (premature termination) | Verification | Agent `git commit`s locally then waits for "want me to push?" instead of running `git push origin <branch>`. (`push-pr-donot-stop-halfway` rule unenforced.) |
| **`task-correction-pivot-refused`** | FC1 (role unclarity) + FC2 (state desynchronization) | Orchestration | User corrected scope mid-task ("now make a PR", "and run it"), agent did not pivot — kept reading files instead. |
| **`capable-didn't-execute`** | FC3 (premature termination) | Verification | Agent had the tools, said it would, then narrated the plan without calling the tools. (`task-ack-and-execute` rule unenforced.) |
| **`wrong-tool-discussed`** | FC1 (specification ambiguity) | Tool / Context | Agent talked about a stale tool/CLI/runtime after the user migrated (e.g., `openclaw cron` after migrating to `hermes cron`). |
| **`fabricated-proof`** | FC3 (fabricated verification) | Verification | Agent claimed "PR is green / tests pass / push succeeded" without raw terminal output. (`proof-before-claim` rule unenforced.) |
| **`missed-existing-skill`** | FC1 (missing constraints) | Context | Agent did work manually that an existing skill covers, because session_init did not load the skill. (`ms-on-new-task` rule unenforced.) |
| **`documented-but-unreachable`** | FC3 (fabricated verification) | Verification + Orchestration | The skill/prompt documents a contract (e.g. "issue `cronjob action=remove` on terminal state") but the script underneath has no parameter, helper, or code path to execute it. The fix exists on `origin/main` and passes tests — but the tests only verify the skill text, not the script's ability to invoke the documented action. The prior `/meta` pass declared "done" without verifying executability. |
| **`wrong-target-removal-on-stop-X-from-Y`** (added 2026-07-20) | FC1 (specification ambiguity) + FC3 (premature termination) | Verification | User says "stop X from doing Y" or "stop X from giving me Z". Agent parses the message literally — X = the named noun — and disables/removes X, when X is a downstream consumer and the actual source of Y is X's *upstream agent/service*. **Wrong-target rule:** when the user names a noun that sounds like a consumer (a cron job, a workflow, a named task) AND the symptom ("these reports", "that bot", "passively listening", "self-reports") matches an agent's behavior pattern, the agent MUST trace the **provenance** of the symptom back to its actual source before acting. Anti-pattern: trust the literal noun and remove the named job. Recipe: (a) grep the **symptom noun** (e.g. "these reports", "passively listening", "self-reports", "self-investigation") across the past 24-72h of Slack history — the originating source is usually in a quoted thread; (b) for the named target X, trace its **data path**: cron → script → MCP server → external API. The actual fix lives at the layer where data is generated, not where the named consumer displays it; (c) only after the provenance is confirmed AND a one-line clarification fails to disambiguate, take action — and the action is at the source layer, not at the consumer. Verified 2026-07-20 incident: user said "Lets stop mcp mail from giving these reports" — the agent removed `clawchief:ea-sweep-hourly` (the cron that posted briefs to DM). The actual source was the **MCP Agent Mail agent** (`U0A4G7LDJ4R`) with Socket-Mode listener ingesting Slack messages → MCP messages → agent replies. User feedback (verbatim): "No keep the job you fucking idiot — I said mcp mail agent I don't want it passively listening to my threads." The fix landed at the right layer (env overlay + launchd restart) but only after the user re-clarified with strong language. Companion SOUL.md `## COMMIT: mcp-agent-mail-no-passive-slack-listening` was authored in the second-pass fix. |
| **`other`** | (any) | (any) | Default — apply full Observe→Isolate→Simulate→Evaluate cycle. |

If the input mentions multiple failure classes (common — the user pastes a long thread), pick the **earliest** one (closest to the agent's actual deviation point) and note the others in the post-mortem as "secondary issues, separate `/meta` pass recommended." ETCLOVG layer maps the failure to a specific harness layer; the proposed fix MUST target that layer (don't propose a context-window patch when the failure is in the Verification layer).

### Phase 1 — Observe → Isolate → Simulate → Evaluate (4-step pattern)

Replace the standalone "5 Whys" spine with the **Observe → Isolate → Simulate → Evaluate** lifecycle (after Kuldeep Paul's "How to Debug LLM Failures" 4-step pattern). This pattern is **trace-aware** (knows which span / tool call produced the failure) and **multi-causal** (does not assume a single root cause) — both critical for LLM agent failures.

1. **Observe** — gather the trace: the exact user message that triggered the failure, the agent's response, all tool calls in between, the final state of the artifact (or its absence). Cite the message ID + tool-call trace. **Use Reflexion-style verbal reflection** (Shinn et al., NeurIPS 2023, `https://openreview.net/pdf?id=vAElhFcKW6`): at this step, the agent generates a verbal hypothesis about WHY the deviation happened, stored as the postmortem's "Reflection" section.
2. **Isolate** — apply the MAST taxonomy to localize WHICH failure mode (FC1/FC2/FC3) and the ETCLOVG layer model to localize WHERE (which of the 7 layers). Both axes must be filled in.

   **Phase 1.5 — "Fix authored but never merged to origin/main" check (added 2026-07-05, harness-postmortem v0.3.0).** Before concluding "no existing fix", scan all branches for prior-art commits on the topic. Concretely:

   ```bash
   # 1. Search commit messages for the failure-mode keyword
   cd ~/.hermes && git log --all --oneline --grep="<keyword>" | head -20

   # 2. Find candidate fix commits (look for [antig], [meta], fix(babysit), etc.)
   git log --all --oneline | grep -iE "<keyword>|<class>" | head -20

   # 3. For each candidate, check which branches contain it
   for sha in <candidates>; do
     echo "=== $sha ==="
     git branch --contains "$sha" --all
     echo "origin/main: $(git merge-base --is-ancestor "$sha" origin/main && echo YES || echo NO)"
   done
   ```

   **Why this matters:** the 2026-07-05 babysit-cron-leak post-mortem found commit `7690435707 [antig] fix(babysit): detect merged PRs and self-terminate + watchdog cron` on branch `fix/babysit-stale-merged-pr` (HEAD = 7690435707). It was the canonical fix for exactly this leak class — but it was **never merged to origin/main**. The "fix exists but is on a feature branch" gap is a recurring failure mode distinct from "fix doesn't exist"; catching it skips the entire SKILL.md authoring + test-writing cycle and replaces it with a cherry-pick + push.

   **Output:** if a candidate fix is found, the protocol becomes:
   - `git worktree add ~/.worktrees/<fix>-replay -b feat/replay-<fix> origin/main`
   - `git cherry-pick <fix-sha>` (resolve conflicts if the file paths drifted)
   - Add only the harness-side guardrails (SOUL.md COMMIT, regression test) that the original author missed
   - Push as before

   **Anti-pattern:** re-writing a fix that's already authored but stranded on a non-main branch. The new branch is just a replay with possibly added guardrails, not a re-implementation.

   **Phase 1.5b — "Fix on origin/main but not executable" check (added 2026-07-05, harness-postmortem v0.3.1):** After confirming the fix IS on `origin/main`, verify that the script the fix documents actually has the code path to execute it. The 2026-07-05 babysit-cron-leak recurrence exposed this gap: the v1.1.0 fix landed on origin/main (commit `b2ad00770d`), added `is_pr_terminal()` to `babysit.py`, documented `cronjob action=remove` self-cancel in the skill — but `babysit.py` had no `--cron-job-id` parameter and no `cronjob_remove()` helper. The self-cancel was prompt-level documentation with zero executable path in the script. A second `/meta` pass was needed to add the executable contract (`ef311283ed`).

   Concrete verification after confirming `origin/main` contains the fix:

   ```bash
   # Does the SCRIPT (not just the skill .md) have the code path to execute
   # the documented contract? For babysit-style fixes, grep the actual .py:
   grep -c '<documented-action>' <script-path>   # e.g. grep -c 'cronjob_remove' babysit.py
   grep -c '<cli-arg>' <script-path>              # e.g. grep -c 'cron.job.id' babysit.py
   # If the count is 0, the fix is documented-but-unreachable → Phase 2 must
   # add the executable code path, not just another prompt clause.
   ```

   **Why this matters:** Phase 1.5 catches "fix stranded on a branch". Phase 1.5b catches "fix on origin/main but only at the skill/prompt layer — the script underneath can't execute it". Both are distinct failure classes. A fix that passes the existing test suite but the tests only verify skill text (not script executability) will pass 1.5 and fail 1.5b.

   ### Phase 1.5c — "Polluted PR (merged another PR's full history)"** is a third distinct failure class — agent's PR carries another PR's full history (beads drift, CI fixes, merge chains) when the stated scope is a focused fix. See `references/polluted-pr-cleanup-replay.md` for the full detection + recovery recipe (companion skill: `pr-cleanup-replay`).

   ### Phase 1.5d — "Recurring correction needs pre-send gate, not documentation" (added 2026-07-14)

   When the same user correction has hit ≥3 times across ≤30 days, **documentation-only fixes do not survive between sessions.** The agent's defaults push toward the path of least resistance; a post-hoc SOUL.md rule or skill text only fires after the user complains. The durable countermeasure is a **pre-send gate** — a regex (or ordered sequence check) that the agent MUST run on every draft before invoking the message/Post tool.

   **Concrete diagnostic** (codified from the PR #8139 evidence-attach chain 2026-07-02 → 2026-07-14):
   1. Verify recurrence: search SQLite state.db for similar user corrections in last 30 days; quote trigger phrases verbatim.
   2. Audit existing fix: if a skill/SOUL.md/test exists, why didn't it prevent the recurrence? Most common: documentation-only (agent doesn't auto-load), reactive trigger (rule fires after complaint), or stale reference (pre-dates a known failure mode).
   3. Write the pre-send gate: SOUL.md `## COMMIT:` block with trigger + action + verification (test file).
   4. Test the gate: contract test for regex compilation, false-positive guard, draft → upload → verify → send ordering.
   5. Patch the skill: add a "Pre-Send Gate" section at the TOP. Add the recurring-correction phrases ("you always forget", "you always fail", "stop doing X") to YAML triggers.
   6. Save memory: durable entry naming the recurrence pattern and linking to the gate.

   **Anti-patterns blocked by this principle:**
   - "Add this to memory so the next agent knows" — memory isn't loaded on the relevant path
   - "Update the skill to be more emphatic" — the skill was already emphatic; the agent didn't load it
   - "Just be more careful next time" — no mechanism enforces "more careful"
   - "Document in MEMORY.md" — not enforced at draft time

   See `references/recurring-correction-pre-send-gate.md` for the full worked example, the 4-incident chain, and the concrete checklist.

   **Test coverage:** `tests/test_harness_postmortem_contract.py` adds a Phase 1.5d case that verifies the harness-fix layer (SOUL.md `## COMMIT:` + skill trigger regex + contract test) is present for any failure class that has hit ≥3 times.

3. **Simulate** — generate the counterfactual: "what would the agent have done if [harness rule X] had fired at this exact point?" Validate the rule exists in SOUL.md/skills (existing coverage check). If absent, the gap is real. **5-Whys is allowed as a prompt heuristic WITHIN this step** (a sub-routine), not as the structural spine. Apply 5-Whys twice (Technical + Agent path) for the specific causal chain that produced the failure.
4. **Evaluate** — propose the harness fix at the layer where the failure lives. Tag the fix as **[Instructions]** (SOUL.md `## COMMIT:`), **[Skill]** (new or patched skill), or **[Test]** (regression test that would have caught the failure). Verify the fix does not just push the failure to a different layer (ETCLOVG re-classification check).

Output the full Observe→Isolate→Simulate→Evaluate analysis before applying fixes (unless `--fix` flag was passed, or the user explicitly said "fullrun").

### Phase 2 — Apply fixes (auto if fullrun)

If the user said "fullrun" / "don't stop" / `/a` / `/finish`, apply fixes without confirmation:

- **SOUL.md `## COMMIT:` block** — surgical `patch mode=replace` against a unique anchor. NEVER full-rewrite SOUL.md (per `harness-engineering` "Never full-rewrite a SOUL.md" pitfall). Preserve all existing `## COMMIT:` blocks.
- **New skill** — `skill_manage(action='create', ...)` to `~/.hermes/skills/<name>/SKILL.md`. Tracked under git on `jleechanclaw`. Write tests under `tests/`.
- **Test** — `tests/test_<name>_contract.py` with pytest, runs locally without external services.
- **Existing skill patch** — `skill_manage(action='patch', ...)` with `old_string` / `new_string`.

Each fix must include in its commit message:

```
[meta] <one-line summary>

- <file:section>: <what changed>
- <commit-SHA-not-yet>: <linkage>

Trigger: <Slack URL or thread ts>
Failure class: <Phase-0 classification>
```

### Phase 3 — Land via hermes-deploy-pipeline (with staging-dirty-surgical-sync recipe)

For SOUL.md / skill / script changes in `~/.hermes/`:

1. **Pre-edit diff check** — `git diff HEAD~1 -- ~/.hermes/workspace/SOUL.md | grep -c '^[-]## COMMIT:'` BEFORE pushing. If positive, restore or justify.
2. **Self-merge flow** — `~/.hermes` is `jleechanorg/jleechanclaw`. The repo has no branch protection on `main` (verified `gh api .../branches/main/protection` → HTTP 404). Push via `git push origin HEAD:refs/heads/main` from a fresh `feat/meta-<name>` worktree at `origin/main`. NEVER force-push (rejected with `GH013`).
3. **Staging dirty?** — `~/.hermes/` is often on a feature branch (e.g. `dev1783194285`, `fix/ao-tracker-config`) with massive unrelated dirty diff. Per `hermes-deploy-pipeline`, do NOT commit onto the dirty branch. Use `git worktree add ~/.worktrees/meta-<name> -b feat/meta-<name> origin/main`, commit there, push via refspec.
4. **Verify landed on origin/main** — `git -C ~/.hermes rev-parse origin/main` shows new SHA. `grep -c '^## COMMIT: <name>$' ~/.hermes/workspace/SOUL.md` returns ≥1.
5. **Sync to staging tree** (changed 2026-07-05 from naive `deploy.sh` invocation): `~/.hermes/scripts/deploy.sh --skip-pull --skip-restart` is **NOT** the canonical recipe. It is brittle in three known ways:
   - It can fail at the **port health check** (`port:UNBOUND`) when the gateway is in a transient state, even when Stage 4.5 (policy file sync) and Stage 4.6 (skills sync) succeeded silently under `[single-dir]` mode. The exit code is non-zero so the deploy reports "DEPLOY FAILED" but the files DID sync.
   - It **skips the rsync** entirely when `~/.hermes_prod` is a symlink to `~/.hermes` (the [single-dir] mode message), so the deploy script becomes a health-check wrapper around a no-op. This is correct behavior, not a bug, but it means the script reports no useful signal about whether the sync actually happened.
   - It requires the staging tree to be on `main` (not a dirty feature branch); if staging is on `dev1783194285`, the `--skip-pull` flag does nothing because there's nothing to merge, and the dirty staging files override the just-pushed origin/main changes.

   **Canonical recipe (staging-dirty-surgical-sync)**, used in the 2026-07-05 babysit-cron-leak post-mortem:

   ```bash
   # Step 5a: Verify origin/main has the new commits
   git -C ~/.hermes fetch origin
   git -C ~/.hermes rev-parse origin/main  # should equal <new-sha>
   git -C ~/.hermes log --oneline origin/main -5

   # Step 5b: Confirm staging is dirty on a non-main branch
   git -C ~/.hermes branch --show-current  # if NOT 'main', staging is dirty
   git -C ~/.hermes status --short | wc -l  # >0 means dirty

   # Step 5c: Copy new files from worktree to staging (~/.hermes is the canonical tree;
   # ~/.hermes_prod is a symlink on this machine, so no separate prod sync needed)
   SRC=~/.worktrees/<feat-worktree>
   DST=$HOME/.hermes

   # SOUL.md needs -f because workspace/ is gitignored (only README.md is tracked)
   git -C ~/.hermes add -f workspace/SOUL.md  # if SOUL.md is in this change

   # All other files: plain cp -p (preserves timestamps/permissions)
   for f in scripts/babysit_stale_watchdog.py \
            scripts/tests/test_babysit_stale_watchdog.py \
            scripts/tests/test_babysit_prompt_contract.py \
            skills/babysit-stale-watchdog/SKILL.md \
            skills/ao-babysit/scripts/babysit.py \
            skills/ao-babysit/scripts/test_babysit_pr_exit.py \
            launchd/ai.hermes.schedule.babysit-stale-watchdog.plist.template; do
     mkdir -p "$(dirname "$DST/$f")"
     cp -p "$SRC/$f" "$DST/$f"
   done

   # Step 5d: Run regression tests from staging to confirm the sync didn't lose any
   # file content (cp -p preserves bytes, but a sanity pytest catches encoding drift)
   cd ~/.hermes && PYTHONPATH=scripts python3 -m pytest \
     scripts/tests/test_babysit_prompt_contract.py \
     scripts/tests/test_babysit_stale_watchdog.py \
     skills/ao-babysit/scripts/test_babysit_pr_exit.py -q

   # Step 5e: Verify the COMMIT block is in BOTH staging and prod SOUL.md
   # (~/.hermes_prod is a symlink to ~/.hermes on this machine, so a single grep is enough)
   grep -c "^## COMMIT: <name>$" ~/.hermes/workspace/SOUL.md ~/.hermes_prod/workspace/SOUL.md
   ```

   **When `deploy.sh --skip-pull --skip-restart` IS the right call:** staging is on `main` (not a feature branch), the dirty diff is empty or small, and the port health check is known to pass. Otherwise default to the staging-dirty-surgical-sync recipe above.

6. **Skip the gateway restart** for SOUL.md/skills/scripts changes — the running gateway has the old rules loaded, but skills + RESOLVER.md + SOUL.md take effect on the next session start. A restart is not required and risks disrupting in-flight conversations.

### Phase 4 — Final reply

Per `finish-the-job` contract, every `/meta` completion reply MUST contain:

1. **End-state declaration** — `<harness fix landed>` or `<harness fix + dispatch job for project fix>`.
2. **Proof artifact** — commit SHA, push URL, `git log` output, test output.
3. **What was decided mid-stream** — every judgment call the agent made instead of asking (the user's rule from `finish-the-job`: "correct but misinterpret is fine but stopping halfway is not").
4. **No follow-up question** — the work is done. The user reviews.

## Worked example — the originating incident (2026-07-02)

Thread: `https://jleechanai.slack.com/archives/C0AH3RY3DK6/p1782941155305869` (`C0AH3RY3DK6`, `thread_ts=1782937339.179469`)

**Trigger (verbatim):** User asked "Run /exportcommands and lets ensure it does the superset of /.claude/ and http://your-project.com - your-project.com, cmmands skill etc" at `MsgID=1782937339.179469`. Agent investigated for ~63 minutes, ran a contract test, made a local commit `7a7578d280` on `fix/dUfl4-character-creation-empty-planning-block` (PR #7711's branch). Then posted a 4-way question (a/b/c/d) and waited. User came back ~22 hours later: "You didn't do your job. I wanted a /green PR and I want the hermes skills in there too."

**Phase 0 — Classify:**
- **MAST category:** FC1 (specification ambiguity — agent couldn't decide whether side effects were approval-required) + FC3 (premature termination — agent stopped at clarification instead of running the slash command).
- **ETCLOVG layer:** Verification (the rule that should have verified "user invoked an action verb → execute, do not gate" lives in the Verification layer).
- **Working class:** `mid-task-clarification-freeze`.

**Phase 1 — Observe → Isolate → Simulate → Evaluate:**

1. **Observe (Reflexion):** "The agent had every input available (commit SHA, branch name, AO dispatch path, inline drive-to-green option per `pr-green-dispatch` rule). It classified the side effects (PR creation, README regen, branch drive-by) as approval-required despite the user's invocation being an action verb ('Run /exportcommands')."

2. **Isolate (MAST + ETCLOVG):** FC1 + FC3, Verification layer. The `no-confirmation-gate` SOUL.md COMMIT (Verification layer) is the gap.

3. **Simulate (5-Whys sub-routine):**
   - *Agent path 5-Whys:* Why did the agent stop? → Posted a 4-way clarification. → Why ask instead of execute? → Classified side effects as approval-required. → Why classify as approval-required? → `no-confirmation-gate` rule enumerates bypass phrases; "run /exportcommands" not in the list. → Why closed-list instead of principle? → Rule was instantiated as enumeration, not codification of the principle.
   - *Technical 5-Whys:* Why did the agent wait 60+ minutes before posting the clarification? → `clarify` tool has no timeout return-value. → No rule enforces "if clarify was posted and user hasn't replied within N minutes, proceed with the safe default." → `finish-the-job` v1.3.0 has the recipe but it's documentation, not a runtime guardrail. → No SOUL.md COMMIT auto-applies Phase-3 fork-resolution.

4. **Evaluate (ETCLOVG re-classification check):** Fix lands in **Verification** layer (SOUL.md `## COMMIT:` + new skill + new test). NOT in Context, Tool, or Orchestration — those are not where this failure lived.

**Phase 1 Existing coverage:**
- `~/.hermes/skills/finish-the-job/SKILL.md` v1.3.0 — clarify-timeout recipe exists but is not auto-applied.
- `~/.hermes/workspace/SOUL.md` `## COMMIT: no-confirmation-gate` — closed-list of trigger phrases, not principle-based.
- `~/.hermes/skills/finish-the-job/SKILL.md` — anti-pattern "clarify didn't come back → ask again with a different menu" documented (added 2026-07-01, agento-config-cleanup thread).

**Phase 2 proposed fixes (this `/meta` pass implements these):**

1. **[Instructions]** `~/.hermes/workspace/SOUL.md` — add `## COMMIT: meta-autonomy-violation-handler` block that:
   - Detects agent behavior failure descriptions (autonomy violation, "didn't do its job", "stopped halfway").
   - Routes to `/meta` automatically.
2. **[Skill]** `~/.hermes/skills/harness-postmortem/SKILL.md` — this file. Scope-locked, harness-only, deploys via hermes-deploy-pipeline.
3. **[Test]** `~/.hermes/skills/harness-postmortem/tests/test_harness_postmortem_contract.py` — verifies scope guardrail (does NOT investigate underlying task), commit-not-codepath invariant, and Phase 0/1 protocol coverage.
4. **[Skill patch]** `~/.hermes/skills/finish-the-job/SKILL.md` — strengthen "clarify timeout → yolo default" from documentation to auto-application rule (linked via reference, not duplicated text).
5. **[Memory]** User feedback memory: "agent behavior violations are a meta-task, route to /meta, do NOT continue the underlying task."

## Prior art (cited to avoid duplicate work)

This skill was authored as an operationalization for the Hermes runtime specifically. Functionally adjacent work exists in the open-source ecosystem and is **referenced, not duplicated**:

- **Refinex-Space `harness-fix` SKILL** (`https://github.com/Refinex-Space/Refinex-Skills/blob/master/plugins/harness-powers/skills/harness-fix/SKILL.md`) — covers bug/regression/incident/flaky-path debugging. Lifecycle owner for "diagnose and repair with evidence." Functional overlap with this skill's Verification-layer fixes.
- **HarnessFix paper** (Chen et al., Institute of Software, Chinese Academy of Sciences, June 2026, arXiv:2606.06324) — improves held-out test performance 15.2%–50.0% via trace-guided diagnosis + harness repair. Introduces the **ETCLOVG** 7-layer model (Environment, Tool, Context, Lifecycle, Orchestration, Verification, Governance), which Phase 0 of this skill uses as the layer-localization axis.
- **MAST** (Cemri et al., UC Berkeley, NeurIPS 2025, arXiv:2503.13657) — 14 failure modes in 3 root categories (FC1 System Design, FC2 Inter-Agent Misalignment, FC3 Task Verification & Termination), 1,600+ execution traces, Cohen's κ = 0.88. Phase 0 maps working classes to MAST root categories.
- **Reflexion** (Shinn et al., NeurIPS 2023, `https://openreview.net/pdf?id=vAElhFcKW6`) — verbal reflection on failure → episodic memory → guide next attempt. Phase 1 Observe step uses Reflexion-style verbal hypothesis.
- **Observe → Isolate → Simulate → Evaluate** 4-step pattern (after Kuldeep Paul, "How to Debug LLM Failures", `https://dev.to/kuldeep_paul/how-to-debug-llm-failures-a-step-by-step-guide-for-ai-developers-4do`) — the structural spine of Phase 1. Trace-aware and multi-causal, unlike 5-Whys which assumes single-root-cause chains.
- **muratcankoylan/Agent-Skills-for-Context-Engineering** — catalogs agent failure modes including "Claude declares victory on the entire project too early." Pattern-match for our `capable-didn't-execute` class.
- **dotika-ai/harness-engineering** (`https://github.com/dotika-ai/harness-engineering`) — `classify → execute → verify → document` pattern, broadly similar to Phase 1.

This skill's delta: tight integration with the Hermes SOUL.md / skills / tests runtime, the explicit scope guardrail, the MAST+ETCLOVG two-axis Phase 0, and the user-confirmed originating incident trace.

## Anti-patterns

- **"Fix the underlying task too while I'm at it."** — BANNED. `/meta` is scope-locked to the harness fix. The original task is a separate dispatch (`dispatch-task` skill, full brief).
- **"Read SOUL.md / CLAUDE.md end-to-end and propose a 50-page rewrite."** — BANNED. The fix is ONE `## COMMIT:` block (or one skill, one test). If the audit suggests >2 file rewrites, narrow the scope and dispatch the rest.
- **"Skip the 5 Whys because the trigger is obvious."** — BANNED. The /harness protocol mandates BOTH 5 Whys sections. Skipping them is the same anti-pattern that produced the originating incident (skipping the principled fix in favor of a 4-way menu).
- **"Commit on the dirty branch because deploy will sort it out."** — BANNED. Per `hermes-deploy-pipeline`, always worktree-from-`origin/main`, commit clean, push via refspec. The current dirty tree is not the meta-skill's concern.
- **"Post the analysis as a Slack reply and stop."** — BANNED. Analysis-only is the same anti-pattern that produced the originating incident. The user said "fullrun" or equivalent → implement and push.
- **"Wait for the user to reply before iterating."** — BANNED. Iteration is internal: write skill → write test → run test → patch → re-run → commit → push → deploy → verify. The user reviews the final state.

## Loader / auto-fire contract

This skill is registered in `~/.hermes/skills/RESOLVER.md` (the entry can be titled `## meta` or `## harness-postmortem` — both names resolve to the same skill file) and the `## COMMIT: meta-autonomy-violation-handler` SOUL.md block (added in this same pass) makes it load automatically on any of:

- User reports an autonomy violation ("didn't do its job", "stopped halfway", "you refused").
- User types `/meta [input]` (slash command at `~/.claude/commands/meta.md`).
- User pastes a Slack thread where the last natural message describes the agent's deviation (Phase-1 extractor matches).

Trigger phrase regex (per RESOLVER.md entry):

```
(autonomy violation|hermes refused|agent refused|stopped halfway|stopped at half|
 why did (hermes|the agent) stop|didn't do (its|your) job|fix the agent|
 fix hermes behavior|fix the harness not the task|meta skill|/meta|run meta|
 harness postmortem|harness retro|harness audit|harness fix|agent failure analysis|
 run harness postmortem on)
```

Case-insensitive. Slack channel-agnostic (does not bind to `C0AH3RY3DK6`).

**Internal-name policy:** The skill is functionally invokable as either `/meta` (slash command) or `harness-postmortem` (skill_view). Future contributors adding natural-language aliases SHOULD prefer the `harness-*` prefix to avoid the `meta-prompting` / `meta-harness` / `MetaGPT` collisions documented in the "Prior art" section above.

## Deploy sync awareness

Per `hermes-deploy-pipeline`, `~/.hermes_prod/` is a symlink to `~/.hermes/` — staging = prod = live runtime. Writing the skill here is sufficient for the prod resolver to see it. The deploy step (`~/.hermes/scripts/deploy.sh --skip-pull --skip-restart`) handles Stage 4.5 (policy file sync, includes SOUL.md) + Stage 4.6 (skills sync) without a gateway restart (skills + RESOLVER.md + SOUL.md take effect on next session start, not on the running gateway).

## Related skills — load order when `/meta` fires

1. `/harness` (always — for the 5 Whys protocol)
2. `finish-the-job` (always — for the end-state + reply shape)
3. `hermes-deploy-pipeline` (always — for the landing recipe)
4. `harness-engineering` (always — for SOUL.md-as-policy-upstream, never-rewrite, verify-CLI-before-quoting rules)
5. `dispatch-task` (only if Phase 2 produces a separate dispatch for the underlying task — `/meta` itself does NOT dispatch the underlying task, but the user may want it queued)

## Pitfalls

- **The user's original task is a dispatch candidate, not a /meta target.** When `/meta` finishes, post a one-line "the underlying task remains unblocked; spawn via `dispatch-task` if you want it picked up." Do not silently absorb it.
- **SOUL.md full-rewrite is a SOUL.md-drop hazard.** Per `harness-engineering`, always `patch mode=replace` against a unique anchor. `git diff HEAD~1 -- workspace/SOUL.md | grep -c '^[-]## COMMIT:'` MUST be 0 BEFORE pushing.
- **`git push origin main` from the dirty `fix/ao-tracker-config` branch will fail** (not fast-forward, plus it's not even main). Worktree-from-origin-main is mandatory.
- **AO cap-reached** (the 2026-07-02 thread tried AO, hit 41/20 cap, then pivoted to inline) — irrelevant for `/meta` since this is a skills/SOUL.md change, not an AO task. No AO dispatch needed.
- **`deploy.sh --skip-pull --skip-restart` is not the canonical recipe for SOUL.md/skills/scripts changes** (added 2026-07-05). It can fail at the port health check (`port:UNBOUND`) while Stage 4.5/4.6 sync succeeds silently under `[single-dir]` mode; the failure is a false-negative. Use the **staging-dirty-surgical-sync recipe** documented in Phase 3 step 5 instead. The deploy script is still the right tool when staging is on `main` with no dirty diff and the gateway is known-healthy.
- **"Fix authored but never merged to origin/main" is a distinct failure class from "fix doesn't exist"** (added 2026-07-05). Always run `git log --all --oneline --grep="<keyword>"` before authoring a new fix. If a candidate fix is on a feature branch, the protocol becomes cherry-pick + push instead of write-skill + write-test + push. The 2026-07-05 babysit-cron-leak fix (`7690435707`) had been stranded on `fix/babysit-stale-merged-pr` for 2 days before the cherry-pick replay shipped it as `b2ad00770d` on `origin/main`.

## Support files

- `tests/test_harness_postmortem_contract.py` — scope-guardrail + Phase 0/1 protocol coverage + commit-not-codepath tests. Run via `cd ~/.hermes/skills/harness-postmortem/tests && python3 -m pytest -q`.
- `references/wrong-target-removal-stop-X-from-Y-2026-07-20.md` — Phase 0 working class recipe for "stop X from Y" requests where X is the wrong target. Loaded when the user reports the agent removed the wrong cron / workflow / service.
- `references/recurring-correction-pre-send-gate.md` — Phase 1.5d recipe for turning recurring user corrections into pre-send gates (regex + test, not documentation).
- `references/polluted-pr-cleanup-replay.md` — Phase 1.5c recipe for cleaning a PR whose branch carries another PR's full history.
- `references/staging-dirty-surgical-sync-2026-07-05.md` — Phase 3 step 5 staging-dirty-surgical-sync recipe (replaces naive `deploy.sh --skip-pull --skip-restart` when staging is on a feature branch).
- `~/.claude/commands/meta.md` — slash command file (`/meta` invocation). NOT in the jleechanclaw repo (lives in the user's Claude Code user-scope); mirrors the skill content with a header so Claude Code resolves `/meta` to this skill.

## Changelog

See YAML frontmatter `changelog` field. Latest: 0.1.0 (2026-07-02, originating incident).

## Self-review checklist (skillify 10-item)

| # | Check | Status |
|---|-------|--------|
| 1 | YAML frontmatter has `name`, `version`, `description`, `triggers` | ✅ |
| 2 | Trigger phrases cover natural-language invocations | ✅ |
| 3 | Phases are numbered, with explicit gate between each | ✅ |
| 4 | Anti-patterns section exists | ✅ |
| 5 | Worked example traces the originating incident | ✅ |
| 6 | Test file referenced | ✅ |
| 7 | Deploy sync awareness documented | ✅ |
| 8 | Loader / auto-fire contract spelled out | ✅ |
| 9 | Pitfalls called out | ✅ |
| 10 | No fabrication — every command/file path is verifiable | ✅ |