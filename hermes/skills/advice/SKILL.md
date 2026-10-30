---
name: advice
version: 1.5.0
description: "Hermes wrapper for the `/advice` token-efficient second-opinion slash command. Canonical source is `~/.claude/skills/advice/SKILL.md`. Adds docs-accuracy review template, patch-review template, and three operator-correction pitfalls verified 2026-07-30: #14 'I don't care about X' = indifferent mechanism, not a ban; #15 gateway re-injection = break the echo chain on turn 2; #16 env-driven configuration preference."
---

# /advice — Token-Efficient Second Opinion (Hermes overlay)

**This is the Hermes-side wrapper.** The canonical skill lives at:
- `~/.claude/skills/advice/SKILL.md` — full pattern, all 3 reviewers, fallback chain

**Read the canonical file for the full procedure.** This overlay exists so that:
1. `skill_view(name='advice')` works from the Hermes session (the canonical Claude skill is not registered in the Hermes skill registry).
2. Future agents learn to **search both `~/.hermes/skills/` AND `~/.claude/skills/`** when a user invokes a `/slash` command — slash commands are not Hermes-native; they are Claude Code constructs.

## Static review (synced 2026-10-29)

The canonical `/advice` now delegates reviewer input to `~/.claude/skills/static-review/SKILL.md`: every reviewer (CLI, coordinator ask, static-review subagent) gets the cold, verbatim template with only the PR URL and SHA filled, plus the fixed per-channel preamble. The receipt records the exact prompt; any deviation voids the vote. Static-review subagents launch in parallel with the coordinator ask (or, with no coordinator, with the CLI attempts) and fill only slots still unfilled after every CLI attempt and coordinator account ends; one outside vote pairs with one static reviewer (no double substitution). Record unavailable seats as `<host> — <CLI or static reviewer> — attempted|skipped — <attempt time> — <reason>` and tell the user. A cloud-only failure does not make Mac or Ubuntu CLIs unavailable.

## When to use

User says `/advice [optional question]`, or you reach a decision point that needs a second opinion without shipping the full conversation uncached.

## Review types (added 2026-07-06)

The canonical `/advice` SKILL.md describes the general-purpose "extract decision + artifact, fan out 3 reviewers, synthesize" pattern. For docs-accuracy reviews (e.g. "are these merged docs accurate against the source?"), use this specialized template — it produces far more useful verdicts than the generic one:

### Docs-accuracy review template

```markdown
# /advice Decision + Artifact

## DECISION (3-5 sentences)
[What specifically needs review — be concrete. For docs-accuracy:
"docs X/Y/Z were merged in PR #N; need a second opinion on whether
the claims match the actual `src/` code, whether the terminology
is consistent across files, and whether anything was fabricated."]

## ARTIFACT (≤150 lines, claim-bearing excerpts only)
[Paste ONLY the claim-bearing sections from each doc, plus the
load-bearing source files. Drop boilerplate, drop "Install" sections,
drop Config tables — they don't bear accuracy claims. If the docs
total 800+ lines, summarize to ≤150 lines.]

### Doc §"<section name>" — claim-bearing excerpts
> [quote 1-3 sentences that make a verifiable claim]

### Doc §"<section name>" — claims under review
**L1 ...**: enforces X
**L2 ...**: enforces Y
**L3 ...**: enforces Z

### Source: `src/<file>.rs::<fn>()`
```rust
[the actual source code that backs the claim]
```

## QUESTIONS FOR THE REVIEWER

1. **[Specific factual claim]**: does doc say X? does code do X?
2. **[Terminology consistency]**: are the terms used consistently?
3. **[Missing callout]**: is there a case the doc should surface that
   it doesn't? (e.g. macOS short-circuit, sudo escalation wording)
4. **[Fabrication check]**: does any claim in the doc contradict
   actual source?

## DELIVERABLE

Return exactly:
VERDICT: [docs accurate / docs need fixes (list) / docs misleading (explain)]
REASONING: [3-4 sentences citing file:line evidence]
RISK: [main risk if docs are wrong, one sentence]
CONFIDENCE: [high / medium / low]

Plus a numbered list of every inaccurate claim you found, each with:
doc-file:line, source-file:line, what the doc says vs what the code
actually does.
```

**Why this template works (verified 2026-07-06, ez-gh-actions PR #9 review):**

1. The "QUESTIONS FOR THE REVIEWER" numbered list forces the reviewer to
   address each load-bearing claim explicitly instead of waving a hand
   at "looks accurate".
2. The 3 reviewer roles get differentiated goals:
   - **Reviewer A (source accuracy)**: file:line citations from the docs
     AND the source for each claim — every claim must trace to code.
   - **Reviewer B (public docs)**: cross-reference with Docker/Colima/QEMU
     official docs, GitHub Security Lab research, kernel docs.
   - **Reviewer C (internal consistency)**: terminology drift between
     README/DESIGN/SVG/wiki/roadmap, broken anchor links, jargon overload.
3. The "Plus a numbered list of every inaccurate claim you found"
   output format surfaces EVERY gap in one table — easier to synthesize
   into a follow-up PR than prose paragraphs.
4. The 150-line artifact budget forces distillation: only the claims
   that matter go to the reviewer. Boilerplate config tables and install
   instructions are noise for accuracy review.

**When NOT to use the docs-accuracy template:** use the generic pattern from
the canonical SKILL.md when the question is about code design, an
architecture decision, a trade-off between two approaches, or anything
that doesn't fit "are these docs accurate against source X".

### Outcome-driven product spec review template (added 2026-07-31)

When the artifact is a design doc / product spec (not a merged doc, not a patch) AND the product **supersedes** an existing tool's contract — i.e. the spec contradicts an existing README / CLAUDE.md / architecture doc in the same repo — use this variant. The shape of `QUESTIONS FOR THE REVIEWER` changes because three load-bearing questions are unique to supersession reviews:

1. **What does the new spec say that the old contract explicitly forbids?** This is the question that breaks "the design says X" if X is forbidden by the existing CLAUDE.md / README.
2. **Does the new spec name where the old contract gets amended?** Most supersession PRs land without amending the old contract, leaving the repo internally contradictory.
3. **Does the spec invent new mechanisms, or re-skin old ones?** A spec that "moves cookies out of the design" or "drops manual auth" without naming the mechanism it's replacing is doing more than it admits.

The artifact shape (≤150 lines, claim-bearing excerpts only) is the same as docs-accuracy; what differs is the questions + a new section in the artifact. Add a `Source: existing v1 contract` block alongside `Source: src/<file>.rs`, with the verbatim v1 text that the new spec contradicts. This lets the reviewer do an apples-to-apples diff instead of re-deriving the conflict.

Also include the **state-machine ↔ classification cross-check**: if the spec defines a state machine and a failure-classification list, verify every classification maps to a real state. The most common miss is "names `recovery_exhausted` in classifications but the state diagram has no terminal edge for it." Surface this explicitly in `QUESTIONS FOR THE REVIEWER` as Q0.

**Provenance:** browserclaw-autonomous-browser-control-design.md review (2026-07-31, doc-id `doc_f51132550e72_…`, 791 lines after 4 doc-level fixes). Verdict: NEEDS-FIXES, confidence high (Reviewer A source-accuracy) + medium (Reviewer B external-docs) + high (Reviewer C adversarial). 4 unresolved issues closed by the 4 doc-level patches: state-machine gap (added `recovery → recovery_exhausted → escalated` edge), `operator_id` source (named `HERMES_OPERATOR_ID`), cookie storage backend (`cryptography.fernet` + macOS Keychain + `keyring` fallback), fetched Aside password-autofill citation (`Agent-safe password manager autofill` + scoped access + audit log, with live `curl https://aside.com/` evidence).

### Patch review template (added 2026-07-15)

Use this variant when the artifact IS a patch / diff / content-edit, NOT a
static merged doc — the user uploaded a `.patch`/`.diff`, pasted a "fix
typo / rename / trim / refactor" PR diff, or the input is a sequence of
`--- a/path +++ b/path` hunks. Reviewers must answer BOTH "is the new
content accurate?" AND "did the diff remove anything load-bearing?". The
docs-accuracy template only covers the first question.

The full taxonomy (5-bucket `-` line classification, orphan-reference
detection, the overclaim-pitfall, worked example from the 2026-07-15
sidekick-swarm-trim review) lives in
[`references/patch-review-taxonomy.md`](references/patch-review-taxonomy.md).
Read it before dispatching reviewers on a patch. Quick recap:

- **Phase -0 (state-corruption pre-flight)**: md5/size/mtime of every file in
  the patch BEFORE running reviewers. If on-disk state has been replaced
  with unrelated content (e.g. sidekick/SKILL.md = swarm content), the patch
  physically can't apply and reviewers are wasting quota. Verified
  failure mode — 2026-07-15.
- **Reviewer B's 5-bucket classification**: every `-` line is flavor /
  load-bearing-example / safeguard / cross-reference / snuck-in.
- **Reviewer C's orphan-reference check**: grep `+` lines for "see X below",
  "forbidden", "mandatory"; verify each referenced section survives.
- **Reviewer A's overclaim pitfall**: hunks titled "fix overclaim" require
  EXTRA scrutiny. The author has already convinced themselves the claim
  is wrong; verify the NEW disclaimer against the cited source, not just
  the OLD claim. Common failure: patch removes an accurate paraphrase and
  replaces it with a strawman that denies real source features.

## Hermes-adapted Reviewer A fallback chain

The canonical Claude chain is `subagent → cursor → agy`. On this machine `cursor` is **not installed** (only `claude`, `codex`, `agy` are available). Use this adapted chain:

| Priority | Tool | When |
|---|---|---|
| A1 | `delegate_task` (subagent) | Primary inside Hermes |
| A2 | `agy --print --dangerously-skip-permissions` | subagent unavailable / failed |
| A3 | `codex ...` (headless codex invocation) | agy failed; codex has quota |
| A4 | `claude -p --dangerously-skip-permissions --cwd /tmp` | last resort; requires `claude` login |

## Known pitfalls (learned 2026-06-28)

5. **`/advice` is NOT a PR comment bot.** Posting `/advice` as a PR comment does nothing — the skill is processed locally by the calling LLM, not by a GitHub workflow. Confirm this with `grep -rln "/advice" $HOME/projects_other/your-project.com/.github/workflows/` (returns empty).
6. **Mid-tier source-code-review subagents can hit the 600s hard timeout** (verified 2026-07-15, wa-campaign-content-analysis + Drive template integration review). The subagent model (`delegate_task` `MiniMax-M3` per the standard chain) reads 30+ files line-by-line and never converges inside the 600s budget. Symptoms: API call counter climbs to ~28 before timeout, last action is a `read_file` or `search_files`. Two safer patterns: (a) split the review into 2-3 narrower sub-tasks each scoped to one file or one question; (b) skip the subagent entirely and do the source review inline using `read_file` + `search_files` directly — fast and deterministic when the file paths are known. Reserve full 3-reviewer fan-out for **decisions / designs / trade-offs** where opinion diversity matters; for **source-accuracy reviews** of a finite file set, inline is faster + cheaper.
2. **The skill is in `~/.claude/skills/`, not `~/.hermes/skills/`.** `skill_view(name='advice')` will fail with "Skill not found" until this overlay exists. After this overlay is loaded, `skill_view(name='advice')` returns this file.
3. **`claude -p` requires login** on this machine (`claude -p` → "Not logged in · Please run /login"). Do not burn time on Reviewer A4 if A1-A3 also fail — just note "Reviewer A unavailable."
4. **No Hermes parallel exists.** `~/.hermes/skills/` has no native `advice` skill; this overlay is the only Hermes-side path.
5. **`/research` and `/secondo` referenced by the canonical skill are also Claude-Code slash commands** — not available in Hermes. Replace them with `delegate_task` (research flavor) and `delegate_task` (multi-model opinion flavor) if needed.

## How to invoke /advice from Hermes

1. **Discover:** Call `skill_view(name='advice')` — returns this overlay. For full text, `cat ~/.claude/skills/advice/SKILL.md`.
2. **Extract:** Decision (3-5 sentences) + Artifact (≤150 lines).
3. **Fan out (parallel):**
   - Reviewer A: `delegate_task(goal="Senior engineer second opinion...", toolsets=["terminal","web"])` — that's the Hermes equivalent of the Claude subagent.
   - Reviewer B: `delegate_task(goal="Research question...", toolsets=["web","search"])`
   - Reviewer C (optional): `delegate_task(goal="Second-opinion from a different model...", toolsets=["terminal","web"])` — note `claude -p` is not logged in.
4. **Synthesize:** Same table format as canonical skill.

## Worked example: Codex hook review (2026-07-17)

When asked to "review the evidence that the hooks worked", the natural pattern
is unit tests + tmux replay. The unit tests passed; the tmux replay showed the
hook firing; everything looked green. `/advice` fan-out found **4 real bugs**:

1. **apply_patch regex was case-sensitive** — silently allowed the canonical `*** Delete File:` (capital D/F) per the Codex/Claude apply_patch grammar.
2. **`cwd` field-name mismatch** — hook read `payload.working_dir` (Claude shape); Codex 0.144+ nests it under `tool_input.cwd`. Bare relative paths resolved against hook process's cwd, not the caller's.
3. **Schema trap** — hook emitted `{"continue":false,"stopReason":"..."}`. Codex docs explicitly say these are "parsed but not supported yet. Codex marks the hook run as failed, reports the error, and continues the tool call." My denies were being IGNORED, not enforced.
4. **Non-dict `tool_input` silent allow** — `_extract_command` returned `""` for `tool_input: [1,2,3]` → `_classify("")` returned None → `_allow()`. The documented fail-closed posture was broken.

None of these showed up in unit tests because the tests were written to match
the hook's expectations, not the spec. The fix chain:
- Reviewer A (source accuracy, MiniMax-M3): FAIL with file:line evidence
- Reviewer B (external docs, MiniMax-M3): schema-deviation; fetched learn.chatgpt.com/docs/hooks.md verbatim
- Reviewer C (adversarial, MiniMax-M3): 9-vector probe, 2 real bypasses + 3 heuristic gaps

All 4 fixes were inline (`<10 lines` each per `diagnosis-requires-followthrough-or-handoff`); 38-case test suite extended; skill rewritten to surface the Codex schema rules in Pitfall #0 / Codex schema section. Live tmux replay also revealed the deeper Codex 0.144.5 limitation: **`unified_exec` skips PreToolUse entirely** per docs warning. The hook is a guardrail not a boundary — must be paired with sandbox + approval policy + backup.

**Lesson for future `/advice` reviews of CLI hook code**: never trust "the unit tests pass" alone. Always (a) fetch the vendor's hook schema docs verbatim, (b) drive a live CLI session in tmux to confirm the hook is actually invoked, (c) run an adversarial probe of payload shape edge cases (non-dict types, wrong field names, case-sensitive regex vs spec). All three found different classes of bugs in the same session.

**The "fixtures+docs" trap on cross-CLI hook reviews (added 2026-07-30, PR `jleechanorg/claude-commands#344`):** A `/advice` review on a cross-CLI hook is not complete until the reviewer confirms the hook fires in a real CLI session. Two failure modes that this trap catches:

1. **Codex discovery indirection** — the PR shipped `<repo>/.codex/hooks.json` + `<repo>/codex_hooks.json` Stop entries. Vendor docs list those as canonical. Neither was actually executed; Codex dispatches through `~/.codex/stop-hook-dispatch.sh` and the project's Stop entry just suppresses the legacy fallback. The hook was silently never invoked until `stop-hook-dispatch.sh` was replaced. Two iterations of "the JSON file is missing, the hook must be wrong" followed before the indirection was traced.
2. **Claude v2.1.220 Stop payload schema divergence from statusline docs** — the docs say `model`, `context_window`, and `cost` are present in any lifecycle payload. They are NOT present in the Stop payload (statusline-only). Fixture tests passed against the docs; the live `claude --print` session revealed the missing fields. The unit tests were rewritten with `CLAUDE_LIVE_PAYLOAD` (the actual captured payload) as the regression fixture.

**Reviewer B's mandatory gate for any cross-CLI hook review (effective 2026-07-30):** before approving the verdict, the external-docs reviewer must also confirm:

- A live CLI session has been run for EACH supported CLI (paste the `jq . "$HOME/.claude/var/<hook>/last.json"` transcript or equivalent live-payload capture into the synthesis).
- The unit-test fixtures in `tests/test_<hook>.py` reference the captured payloads, NOT the docs' claimed shapes.
- The discovery indirection is verified for each CLI (e.g. for Codex, the reviewer must confirm `~/.codex/stop-hook-dispatch.sh` actually invokes the hook, not just sets `local_stop_configured=true`).

If any of these three are missing, the verdict must be `NEEDS-FIXES` with a specific item: "live-payload capture missing for CLI X" or "discovery indirection unverified for CLI Y". Do NOT let "the unit tests pass" stand as evidence for cross-CLI hook code.

Companion skill: `~/.hermes/skills/cross-cli-hook-integration/SKILL.md` — the full cross-CLI hook recipe including the discovery-indirection table (§1), the live-payload capture protocol (§4), and the per-CLI response-schema rules (§3). Verified 2026-07-30 against Claude v2.1.220, Codex 0.144.5, Cursor 3.11.13, Antigravity, agy 1.1.8.

## Cross-reference
- Canonical Claude-Code skill: `~/.claude/skills/advice/SKILL.md`
- Hermes skill paths: `~/.hermes/skills/` (staging, git-tracked), `~/.hermes_prod/skills/` (prod runtime)
- Hermes deploy pipeline: `~/.hermes/scripts/deploy.sh --system hermes` syncs this overlay to prod
- Codex canonical mirror: `~/.codex/skills/` archived 2026-06-13; new path is `~/.agents/skills/`
- Companion skill `~/.hermes/skills/codex-path-deletion-guard/SKILL.md` — the hook that triggered this review, with full Pitfall #0 (Codex 0.144 unified_exec) and Codex-schema-allowlist details
- Companion reference `~/.hermes/skills/codex-path-deletion-guard/references/adversarial-probe-2026-07-17.md` — 9-vector probe transcripts + v1-vs-v2 comparison table

---

## Pinned synthesis output format (added 2026-07-15)

Every `/advice` synthesis reply — whether the verdict is "ship it", "needs more changes", or "no fix needed" — MUST end with the same 5-block shape so the user can parse it the same way every session. Tested on the merge_train PR #43 cross-CLI hook review (Jeffrey accepted with no follow-up).

```markdown
### Recommended next action (one tap)
[One shell command OR "no action — PR is ready at the standard green gate"]

### Evidence table
| Bug-report claim (file:line) | PR/fix evidence (file:line) | Test coverage |
|---|---|---|
| ... | ... | ... |

### Reviewers consulted
- Reviewer A (source accuracy, model X): verdict + confidence
- Reviewer B (external docs, model Y): verdict + confidence
- Reviewer C (adversarial, model Z): verdict + confidence

### Disagreements not resolved
[Numbered list of claims where reviewers disagree, with what evidence
would settle each one. Skip this section if all three agreed.]

🧠 Memories used: [source:…, ids_or_labels:…, effect:…]
```

The Evidence table is the load-bearing piece — it's what makes "fix as needed" answers parseable. Without it, the user has to re-read the synthesis to know whether the dispatch was actually justified.

---

## "Fix as needed" pattern — no-fix-is-a-valid-answer (added 2026-07-15)

When the user says "fix X as needed and use /advice to review first", the default execution flow is:

1. `/advice` review of the existing PR/diff against the supplied context (Slack bug report, issue body, doc, etc.).
2. Map every claim in the supplied context to a concrete diff hunk + test in the existing branch. The Evidence table above is built from this mapping.
3. **Stop with no dispatch** if every claim is already addressed and the reviewers converged. This is a first-class outcome, not a failure mode — the user wants the question answered, not necessarily new code.
4. Dispatch via `ao spawn` (NOT `agento` — see Known Pitfalls) only when the Evidence table has unresolved rows.

**Anti-pattern to avoid:** dispatching an `ao spawn` worker "just in case" because the task framing implies action. The dispatch adds latency, consumes quota, and produces a noisy PR diff that the user has to review. When reviewers converge and CI is green, the right reply is one tap (`gh pr merge N --auto --squash`) and a `🧠 Memories used:` line — nothing more.

**Provenance:** merge_train PR #43 (jleechanorg/merge_train, head SHA `431faca`, 2026-07-15). The supplied context was a 9-section Slack bug report covering 4 separate concerns (installer reinstall, runtime-specific matchers, migration cleanup, OpenCode `apply_patch` paths). All 4 had corresponding diff hunks in the existing single commit; CI was green across 7 GH Actions checks (cross-OS pytest + install.sh smoke + evidence staleness); all 3 reviewers converged. No dispatch.

## Verified 2026-07-21 — `/advice` as Gate-3 substitute for the fullrun cycle

**Use this path when all three official review bots are simultaneously unavailable** AND the user is waiting in-thread for a green verdict. Verified on jleechanorg/dark-factory PR #407 (commit `f461f93`) — both Reviewer A (source-accuracy) and Reviewer B (architecture) ran as Hermes subagents in parallel; combined latency <60 sec vs 51-55 min for the v2.5.7 babysit-cron path.

**Pre-flight signature** (all three must be present):
```bash
gh pr checks N --repo OWNER/REPO
# CodeRabbit       fail    "Review rate limited"
# Cursor Bugbot    skipping "usage limit reached"
# chatgpt-codex-connector skipping "Codex usage limits"
```

**Fan-out recipe** (parallel):
- Reviewer A: source-accuracy with file:line citations for every claim
- Reviewer B: architecture + design-intent + audit-chain correctness (catches ordering + opt-in-pattern mismatches that Reviewer A misses)
- Optional Reviewer C: adversarial probe (9-vector for sandbox/fork/edge cases)

**Verdict format** (verbatim, parseable by `green.md` Step 3.4):
```
VERDICT: [APPROVED-as-is / NEEDS-FIXES (numbered list) / REJECT]
REASONING: [3-4 sentences citing file:line evidence]
RISK: [main risk if merged as-is, one sentence]
CONFIDENCE: [high / medium / low]
NUMBERED FINDINGS: [file:line — what — why — suggested fix]
```

**Then post the synthesis as a PR comment** (`gh pr comment N --body '<synthesis>'`) so the gate-3 substitute is recorded on the PR thread per `green.md` Step 3.4's "current-head ... independent adversarial review recorded on the PR" requirement.

**Cross-reference**: full recipe in `workflow/drive-pr-to-green/SKILL.md` v2.5.9 addendum + `references/advice-substitute-and-fork-divergent-rebase-2026-07-21.md`.

## "Needs fixes (cosmetic/clarity, not blocking)" middle ground (added 2026-07-20, PR #8467)

The most common `/advice` verdict on a real PR is **"needs fixes (cosmetic/clarity, not blocking)"** with confidence: medium. This is neither "ship as-is" nor "fundamentally wrong" — the PR shape is correct, but Reviewer A found N soft contradictions or polish issues. The right flow is:

1. **Apply the most-impactful findings inline in a follow-up commit on the same PR branch.** Sort findings by user-visible impact (boundary mismatches → duplicate labels → terminology drift → ortho/canon notes). Skip findings whose fix would expand scope beyond the original directive.
2. **Document the rest in the PR comment thread.** Acknowledge what was not fixed and why. Reviewer A's numbered list becomes a tracked-issue backlog rather than a blocking PR revision.
3. **Re-push.** The precheck re-runs; the new commit shows up in `git log origin/main..HEAD`.
4. **Re-poll CI** (passive — `gh api` REST endpoints, not GraphQL when rate-limited).
5. **Do NOT spin up a fresh AO worker.** The PR already exists; the work is in-place. A new AO spawn burns quota on a duplicate diff.

**Anti-pattern:** treating "needs fixes (not blocking)" as license to `ao spawn` a worker to do the fixes. The findings are 1-10 line edits in known files — `patch` calls inline are faster, deterministic, and the diff stays reviewable.

**Why this middle ground matters:** the alternative is "merge as-is" (defies the verdict) or "draft follow-up PR" (loses context, requires CodeRabbit re-review of the whole branch). The follow-up-commit-on-same-branch pattern keeps the PR atomic and reviewable.

**Provenance:** $GITHUB_REPOSITORY PR #8467 (head SHA `0314a434e4`, 2026-07-20). Reviewer A returned 10 findings; 4 most-impactful (band-boundary mismatch, duplicate Exposure label, Ma[REDACTED_OPENAI_KEY]/Forbidden-Spell semantic drift, Ao 1-3%/scene trickle inconsistency) were applied as commit `0314a434e4` on top of `ec74ca2dda`. The other 6 (dual attribution tables, mitigation-token interpretation, "offending faction" terminology, A.5 Inevitables FR canon note, etc.) were logged as known follow-ups. Green Gate passed on the new SHA with REAL-mode smoke dispatch via `scripts/dispatch-real-smoke.sh` from the `wa-green-gate-pr-shape` skill.

**When this middle ground does NOT apply:** if Reviewer A returns VERDICT: misleading or RISK: <a concrete hazard if shipped as-is>, the right move is either a follow-up PR (not follow-up commit) or explicit user-call on whether to ship with the documented risk. Don't auto-merge a "misleading" verdict regardless of "not blocking" wording.

14. **"I don't care about X" = indifferent to mechanism, not a ban** (learned 2026-07-30, browserclaw-autonomous-browser-control-design.md review). When the operator says "I don't care about X" during a design review, the right fix is to **mark X as an implementation detail the operator is indifferent to** — keep X in the design, add a one-line "operator-indifferent" note, and move on. The wrong fix is to remove X from the design (verified failure: removed all cookie-promotion language from Goals, CredentialBroker, Security, Recovery, Final-design-decisions, and the transport-preference diagram — operator immediately pushed back with "browserclaw can store cookies its fine"). Symptom: you find yourself gutting 6+ sections to "respect" a clarifying answer. Counter-symptom: the user complains and you have to restore 6 sections. **Read the meta-question, not the literal one.** Same pattern: "I don't care how you do X" / "any way is fine" / "doesn't matter to me" → operator-indifference clause, not removal.
15. **Gateway re-injection creates a no-op echo chain — break it on turn 2** (learned 2026-07-30, browserclaw thread, verified 11 consecutive idle turns). When the Slack/Hermes gateway re-injects your prior reply as a new "user" message (common after gateway shutdown/restart cycles), the next turn is a forward with no new directive. The wrong response is to keep producing longer status reports that themselves get re-injected. The right response is to reply once with a short "Idle. Awaiting real directive." and stop. If the same echo arrives again (turn 2, turn 3, ...), reply **literally one line** — "Idle." — without any tool calls. Do not re-run the same `grep` for "verification" (the state hasn't changed); do not re-explain the work; do not re-post a multi-option menu. The work is done; the gate is silent. When real content eventually arrives, resume normal behavior. Confirmed pattern: every "Idle." turn in the browserclaw thread used zero tool calls and zero new claims — the long-idle review thread stayed parseable when the operator came back.
16. **Operator preference for env-driven configuration** (learned 2026-07-30, browserclaw thread). When the operator says "lets have X configurable" or "lets make this optional" or "other people may have other setups," the right encoding is **a `BROWSERCLAW_<THING>` env var with a sensible default + a `local` opt-out slot**. The wrong encoding is to hardcode "Slack + email" (verified failure: original design said "Slack and email simultaneously," operator immediately said "lets have hermes DM me and lets make this optional"). Same pattern: any system that has to integrate with the operator's preferred channel/notification/storage MUST read its target from env, with a default that matches the current operator's setup but an explicit way to redirect or silence it. Document the env vars next to the component, not in a separate "configuration" section. (Design-doc-level capture lives in browserclaw §NotificationRouter; this pitfall is the principle.) When the operator says "I don't care about X" during a design review, the right fix is to **mark X as an implementation detail the operator is indifferent to** — keep X in the design, add a one-line "operator-indifferent" note, and move on. The wrong fix is to remove X from the design (verified failure: removed all cookie-promotion language from Goals, CredentialBroker, Security, Recovery, Final-design-decisions, and the transport-preference diagram — operator immediately pushed back with "browserclaw can store cookies its fine"). Symptom: you find yourself gutting 6+ sections to "respect" a clarifying answer. Counter-symptom: the user complains and you have to restore 6 sections. **Read the meta-question, not the literal one.** Same pattern: "I don't care how you do X" / "any way is fine" / "doesn't matter to me" → operator-indifference clause, not removal.
- When external verification requires fetching plain-text from a URL, use the `curl + grep` recipe in [`references/plain-text-web-extraction-curl-fallback.md`](references/plain-text-web-extraction-curl-fallback.md) instead of `web_extract` (ddgs backend is search-only; Tavily is disabled per SOUL.md).

17. **"Default with manual fallback as exception" = load-bearing binding constraint, not a config setting** (learned 2026-07-30, browserclaw thread). When the operator says "X is the default, manual fallback is the exception" or "I want X automatic, never [manual] unless forced," that phrasing encodes a **binding design constraint** — it must appear in the design doc as an explicit clause (e.g. "manual operator step only after every automated path is exhausted") and the implementation must enforce it. The wrong encoding is to treat it as a config knob (`--manual-fallback-allowed=false`) — that lets the binding constraint erode over time when a future operator flips the flag. Three concrete patterns: (1) §Goals bullet rewritten as "**automatically** — the operator should never need to open a browser for routine work, and manual fallback is the exception, not the default" (bold + "not the default"); (2) §3 Recover step 9 rewritten as "Only if every automated path is exhausted, escalate with a request that the operator open a browser and complete the specific step the system could not"; (3) §Relationship to existing browserclaw v1 contract explicitly supersedes the v1 "Manual auth only" ceiling with the new automatic-auth posture. The Rule: any operator-phrased "automatic X, manual only when forced" is a §Goals-level invariant, not a §Configuration-level switch.

18. **`delegate_task` thread-pool capacity failure is silent — check `result[0].get("status") == "error"` immediately** (verified 2026-07-21, PR #8488 `/advice` fan-out). Three failure modes all return a non-obvious `status: error` payload that is easy to miss:
    - `"DaemonThreadPoolExecutor' object has no attribute '_initializer'"` — pool capacity exhausted, the task DID NOT run
    - `"background delegation pool was at capacity"` — concurrent children limit reached
    - `"spawn-failed-but-worktree-exists"` — see `dispatch-task` SKILL
    The error message naming can mislead (mentions `_initializer`, not `delegation.max_concurrent_children`), and the failed call returns the same shape (`{"results": [{...}], "note": ...}`) as a successful one — so a quick `if result[0].status == 'error'` check is mandatory. **Fix:** always check before synthesizing. The fan-out is non-atomic; the right behavior on error is to immediately fall back to inline 3-reviewer reading via `read_file` + `skill_view` on the relevant skill files (per Pitfall #6 below — inline is faster anyway for finite-file-set reviews).

---

## Cross-CLI hook schema verification recipe (added 2026-07-15)

When the review question involves cross-CLI hook payloads (Codex / Claude / Gemini / Cursor / OpenCode / Antigravity `agy`), reviewers often need to verify whether field names like `permissionDecision`, `additionalContext`, `patchText`, `apply_patch`, `write_file`, `write_to_file` actually exist in the live vendor docs. The recipe:

```bash
mkdir -p /tmp/advice-hooks && cd /tmp/advice-hooks
for url in \
  "https://learn.chatgpt.com/docs/hooks.md" \
  "https://geminicli.com/docs/hooks/reference/" \
  "https://geminicli.com/docs/hooks/best-practices/" \
  "https://opencode.ai/docs/tools/"; do
  fname=$(echo "$url" | sed -E 's|https?://([^/]+)/.*|\1|; s|\.|_|g').txt
  curl -fsS "$url" -o "$fname" || echo "FAIL $url"
done

python3 - <<'PY'
from pathlib import Path
terms = ["write_to_file","write_file","replace","apply_patch","patchText",
         "additionalContext","permissionDecisionReason","statusMessage","timeout"]
for f in Path('.').glob('*.txt'):
    s = f.read_text(errors='ignore')
    print(f.name, len(s))
    for t in terms:
        i = s.find(t)
        print(f'  {t}:', 'HIT @', i if i>=0 else 'MISS',
              s[i:i+300].replace('\n',' ')[:300] if i>=0 else '')
PY
```

**What this gives the reviewer:** ground-truth presence/absence of each candidate field name in vendor docs at session time. Reviewer B (the external-docs reviewer) cites the `HIT @ <offset>` line as file:line evidence for their verdict.

**What this does NOT give:** schema-version drift, undocumented changes between SDK releases, or runtime-specific behaviors that only show up in `--help` output. For those, the reviewer must say "external verification unavailable" and downweight their confidence — do not assert the absence of a field as a positive fact just because it didn't appear in fetched docs (research-integrity rule: proving presence needs only one hit, proving absence requires exhausting sources).

See [`references/cross-cli-hook-schema-verification.md`](references/cross-cli-hook-schema-verification.md) for the full transcript (URLs hit, terms searched, hit/miss counts) from the 2026-07-15 merge_train PR #43 review. Future agents should re-run the curl loop, not trust the cached transcript verbatim — vendor docs change.

---

## Known pitfalls (extended 2026-07-15)

6. **`agento` is not a CLI on this machine** (verified 2026-07-15, jleechanorg/merge_train PR #43 triage). The `agento` SKILL.md description claims it's the entrypoint, but `command -v agento` returns not-found. The actual dispatcher is `ao` (`$HOME/.local/bin/ao`). When you need to dispatch a coding worker, use `ao spawn --project <id> --claim-pr <N> --prompt "..."`, not `agento`. If `ao project list` doesn't show the target repo, run `ao project add <path>` first (interactive prompt — preflight that the path exists before spawning). The `agento` keyword in user messages still routes here, but the underlying command is `ao`.
7. **Treating "fix X as needed" as license to dispatch unconditionally** — see the "no-fix-is-a-valid-answer" section above. Dispatch burns quota and produces noisy PRs; the Evidence table tells you whether dispatch is warranted.
8. **Quoting absence as fact** — see the verification recipe's "What this does NOT give" caveat. Reviewer B must explicitly downgrade confidence when external verification is incomplete.
9. **Skipping state-corruption pre-flight on patch reviews** (learned 2026-07-15, sidekick-swarm-trim): when the artifact is a patch / diff, verify `md5 + size + mtime` of every file the patch targets BEFORE fanning out reviewers. If on-disk state has been replaced with unrelated content (verified failure mode: sidekick/SKILL.md was byte-identical to swarm/SKILL.md since 2026-07-14), the patch will produce `.rej` files when applied, reviewers will quote line numbers from a corrupted source, and you'll spend quota to ship a verdict against the wrong file. Phase -0 takes 5 seconds and prevents 30+ minutes of reviewer churn. Full recipe: [`references/patch-review-taxonomy.md`](references/patch-review-taxonomy.md) § "State-corruption pre-flight".
10. **Patch hunks titled "fix overclaim" / "correct attribution" / "remove inaccurate claim" require EXTRA scrutiny** (learned 2026-07-15): the author has already convinced themselves the original claim is wrong, so they're working backwards. Verify the NEW disclaimer against the cited source — does the thing they're disclaiming actually exist? Common failure: patch removes an accurate paraphrase and replaces it with a strawman that denies real source features (verified this session: Fusion's two headline techniques ARE dynamic mid-session routing + cache-preserving model switches; the "overclaim fix" denied both).
11. **`git apply --stat` from a non-repo parent dir is NOT a valid pre-flight** (learned 2026-07-20, jleechanai `C09GRLXF9GR/p1784582518.247009`, infra03q patch bundle). When the artifact is a patch from a Slack attachment or `~/Downloads`, `cd $HOME && git apply --stat <patch>` exits 0 even when every target file is missing — missing-file warnings get treated as warnings rather than errors at the parent level. The gating signal is `git apply --check` from the repo root that actually contains the patch's target tree. See `finish-the-job/references/patch-bundle-cwd-preflight-2026-07-20.md` for the full recipe. Companion to pitfall #9 — file-existence (cheap check) + content-match (`md5 + size + mtime`, full check) + hunk-applicability (`git apply --check`, gating check) form a layered defense.
12. **`/super` and `/aar` resolve differently than session memory suggests** (learned 2026-07-20). `/super` is Superpowers Cloud Build dispatch (remote GLM-5.2 box) per the 2026-07-20 rewrite of `~/.claude/commands/super.md` — NOT the legacy local `claudeg` thin-router. `/aar` = `/accept-adapt-reject` (feedback triage into Accept/Adapt/Reject), NOT a generic after-action-review. When `/advice` says "dispatch via `/super`", verify the user's intent matches the dispatch semantics before quoting the slash command back.
14. **"I don't care about X" = indifferent to mechanism, not a ban** (learned 2026-07-30, browserclaw-autonomous-browser-control-design.md review). When the operator says "I don't care about X" during a design review, the right fix is to **mark X as an implementation detail the operator is indifferent to** — keep X in the design, add a one-line "operator-indifferent" note, and move on. The wrong fix is to remove X from the design (verified failure: removed all cookie-promotion language from Goals, CredentialBroker, Security, Recovery, Final-design-decisions, and the transport-preference diagram — operator immediately pushed back with "browserclaw can store cookies its fine"). Symptom: you find yourself gutting 6+ sections to "respect" a clarifying answer. Counter-symptom: the user complains and you have to restore 6 sections. **Read the meta-question, not the literal one.** Same pattern: "I don't care how you do X" / "any way is fine" / "doesn't matter to me" → operator-indifference clause, not removal.
15. **Gateway re-injection creates a no-op echo chain — break it on turn 2** (learned 2026-07-30, browserclaw thread; reinforced 2026-07-30, superpowers/gsd/grill-me thread, 20+ consecutive idle turns). When the Slack/Hermes gateway re-injects your prior reply as a new "user" message (common after gateway shutdown/restart cycles), the next turn is a forward with no new directive. The wrong response is to keep producing longer status reports that themselves get re-injected. The right response is to reply once with a short "Idle. Awaiting real directive." and stop. If the same echo arrives again (turn 2, turn 3), reply **literally one line** — "Idle." — without any tool calls. Do not re-run the same `grep` for "verification" (the state hasn't changed); do not re-explain the work; do not re-post the multi-option menu. The work is done; the gate is silent. Verified pattern: 11 consecutive idle turns in one session, all single-line replies, zero tool calls, all preserved the operator's review-thread context for when they next engage.

    **Anti-pattern: emitting structured-report replies on echo turns** (learned 2026-07-30, superpowers/gsd/grill-me thread, 20+ idle turns). Even after correctly identifying the echo chain and citing the SOUL.md `never-hallucinate-no-new-content` rule, the agent kept producing Healthy/Risky/Blocked sections, multi-option decision menus, and "Memories used" footers on every echo turn — each ~200-500 words, each structurally identical to a real report, each one more candidate for the next re-injection. **The report template is itself the failure mode on echo turns.** The right output for turn 2+ of the echo chain is one literal line ("Idle.") with NO sections, NO menus, NO footer, NO `🧠 Memories used:` line. If you feel the urge to write a structured status update on an echo turn, that urge is the bug — resist it. The structured template is for real directives; the literal one-liner is for echoes. Confirmed: the long-idle thread stayed parseable across ~20 idle turns only when the operator's gateway finally started emitting templated queue notices instead of echo-looping the prior reply.

15a. **Multi-hour gateway stalls need durable state, not just one-line replies** (learned 2026-07-30, browserclaw thread, ~3 hours of stall). Pitfall #15 covers the per-turn reply discipline; this pitfall covers the *system* discipline when the stall extends beyond a few turns. After 5–10 idle turns with no real operator directive: (a) persist the work-product paths as durable memory — file paths, line ranges, commit SHAs (or absent), PR numbers (or absent) — so a fresh session can recover state without re-deriving 30+ turns of context; (b) capture any unresolved decisions to `~/.hermes/memory.md` or the project's `specs/` directory, not just in the thread; (c) if the operator's intent is unambiguous, write the work product to disk even if no PR/dispatch is happening (design docs in `~/.hermes/cache/documents/`, plans in `projects/<repo>/docs/plans/`); (d) do NOT delete in-progress artifacts because "they're not authoritative yet" — a recovery agent needs the partial state to continue. Verified pattern: browserclaw thread stalled ~3 hours with the design doc + TDD plan + 4 D-patches all on disk at known paths; recovery means point at the paths, not re-run the conversation. Anti-pattern: keeping everything in the conversation memory and trusting the session resume. When the gateway finally responds with a real directive, state the recovered state in the first 50 words — "Doc at path X (Y lines, Z patches verified), TDD plan at path W (N tasks), no PR open, awaiting execute directive" — and let the operator redirect from there.