---
name: evidence-review
description: Enforcement rules for reviewing evidence artifacts against the evidence-standards skill. Invoked by /er. Produces PASS / PARTIAL / FAIL / INCONCLUSIVE verdicts.
---

# Evidence Review Skill

**Purpose**: Review evidence for a claim, a path, or a PR. Produce a PASS / PARTIAL / FAIL verdict with specific artifact-level citations. This skill is the enforcement layer for the `evidence-standards` skill (the "what to produce") — this file is the "how to judge it".

**Invoked by**: `/er [subject or path]`

**Standards source**: `evidence-standards` skill (`/es`). When in doubt about a requirement, read the standards first.

**Repo overlay (always check)**: this is the **user-scope (global)** `/er` policy — the floor. Before judging, look for repo-level versions and read them too: `<repo>/.claude/skills/evidence-review.md` and `<repo>/.claude/skills/evidence-standards.md` add project-specific enforcement (e.g. worldarchitect.ai adds BQ/streaming/dice modes) and take precedence on conflict.

---

## Verdict Rubric

| Verdict | Meaning |
|---------|---------|
| **PASS** | Every claim has a matching artifact of STRONG quality and every mandatory check below passes. Satisfies the draft-phase `/er` gate when `/er` is applicable. |
| **PARTIAL** | Claims are supported but one or more mandatory checks soft-warn (e.g., WARN in an optional verification_report.json, missing downloadable MP4). Does not satisfy the draft-phase `/er` gate. |
| **FAIL** | A claim is contradicted by an artifact, or integrity is broken (sha256 mismatch, dirty capture producing the claim, scope exclusion). |
| **INCONCLUSIVE** | Not enough artifact data exists to decide. Request more. |

## Draft-lifecycle integration

The canonical lifecycle, its changed-path classification, and the SHA-binding /
staleness-tolerance rule (`draft-first-pr` § "SHA-binding rule") live in
`draft-first-pr`; apply that policy — including the staleness-tolerance diff
test — before invoking this skill. Do not run a fresh `/er` pass on a HEAD
move the staleness-tolerance test classifies as non-behavioral; re-affirm the
prior verdict at the new SHA instead (see `evidence-standards` §
"Evidence Sequencing"):

- **Documentation-only exception**: when the complete PR diff matches the exact
  documentation allowlist in `draft-first-pr`, `/er` is not run. Record
  `/er: NOT REQUIRED — documentation-only (<changed paths>)` at the reviewed
  SHA. Mixed diffs and every path outside that allowlist follow the normal gate.

Every PR outside that exception requires `/er` = **PASS** at the current SHA
before `/advice`. PARTIAL, FAIL, or INCONCLUSIVE remains informative reviewer
output but does not satisfy the gate.

When `/er` is required and invoked via `gh pr comment N --body "/er"`, the
evidence-review-bot returns the verdict as a structured comment with one of the
four values above. Evidence review is a draft-phase quality gate; `/green`
itself remains the separate two-gate check defined by `pr-green-definition`.

---

## Mandatory Pre-PASS Checks (all must pass)

### 1. Bundle integrity

```bash
cd <bundle_dir>

if [[ -f checksums.sha256 ]]; then
  sha256sum -c checksums.sha256
elif find . -name "*.sha256" -print -quit | grep -q .; then
  find . -name "*.sha256" -execdir sha256sum -c '{}' \;
else
  echo "No checksum files found"
  exit 2
fi
```

- Top-level `checksums.sha256` means bundle-checksum mode.
- If no top-level checksum exists, verify every per-file `*.sha256` file.
- Any checksum mismatch → **FAIL** (not just PARTIAL — the bundle is tampered/stale)
- No checksum files → **INCONCLUSIVE** for integrity; do not award PASS.
- Check manifest has entries for every file listed in the claim map and every file covered by either `checksums.sha256` or the discovered per-file `*.sha256` files, resolving per-file checksum entries relative to each `.sha256` file's directory.

**Checksums establish integrity, not provenance.** A matching digest proves only
that the reviewed bytes match the manifest; it does not prove where they came
from, which code path produced them, or that they demonstrate the claimed
behavior. A checksum alone does not make a claim STRONG. For STRONG evidence,
also resolve the primary raw artifact against its capture provenance (for
example `metadata.json.provenance.git_head`, runtime/process metadata, and the
raw request/response or test output that directly shows the claim). If the
only support for a claim is a checksum or a manifest entry, rate that claim
**MISSING**, not STRONG.

### 2. Verification report ceiling

`verification_report.json` is optional unless the subject claims verifier output exists.

```bash
if [[ -f verification_report.json ]]; then
  jq -r '.overall_verdict' verification_report.json
fi
```

- Missing and not claimed → record "verification_report.json absent / not applicable"; no verdict ceiling by itself.
- Missing but claimed → **INCONCLUSIVE** for that verifier claim until the report is supplied.
- `PASS` → proceed
- `WARN` or `PARTIAL` → verdict ceiling is **PARTIAL** (never promote to PASS without resolving each violation)
- `FAIL` → verdict ceiling is **FAIL**

### 3. Scope note consistency

```bash
grep -A10 "Scope note" README.md
```

- If the scope note explicitly excludes a domain the PR claim covers (e.g. "browser layer out of scope") → narrow verdict to in-scope claims only
- If the scope note has been updated to include a domain, verify the matching artifact exists

### 4. Video artifacts — BOTH types required for non-trivial PRs

**Tmux / Terminal video** (required for any code change, test run, deploy):
- [ ] **GIF** embedded inline in PR description (renders on GitHub without clicking)
- [ ] **MP4** linked and directly downloadable from PR description
- [ ] **Caption** naming: test name, pass/fail result, key assertion

**Browser UI video** (required when PR adds or modifies any `testing_ui/test_*.py` file):
- [ ] **GIF** embedded inline in PR description
- [ ] **MP4** linked and directly downloadable
- [ ] **Caption** naming: URL, user actions, before/after behavior

If ANY of the above is missing → verdict is **PARTIAL** (not PASS), regardless of other evidence quality.

### 5. Public-URL hosting check

GIFs and MP4s must be on a **public** repository — private repo release assets return 404 for anonymous viewers and do NOT render as inline images in PR descriptions.

```bash
# For each <owner>/<repo> hosting a video asset:
gh api repos/<owner>/<repo> --jq '.private'
# Must be: false
```

```bash
# And verify the asset itself is uploaded and accessible:
gh api repos/<owner>/<repo>/releases/tags/<tag> \
  --jq '.assets[] | {name: .name, state: .state}'
# All states must be "uploaded"
```

Private repo assets = **PARTIAL / FAIL** for inline rendering.

### 6. Self-contained / clean-computer reproducibility

A PASS verdict requires the PR to meet the "clean computer" standard from `evidence-standards`:

- [ ] PR description links a **gist** with reproduction instructions
- [ ] Gist contains `git clone <url>` + `git checkout <branch>`
- [ ] Gist lists dependencies (Python version, pip requirements, service account needs)
- [ ] Gist has exact test invocation commands (copy-pasteable into a terminal)
- [ ] Gist documents expected output (pass counts, scenario names)
- [ ] Gist embeds or links the GIF + downloadable MP4

**Failure mode**: if the only instructions are "see the repo" or "run the tests" without exact commands → PARTIAL.

### 7. Anti-Fabrication & Telemetry Verification (Bead rev-wghca)

- [ ] **BQ Record Resolution**: Any cited BigQuery/telemetry timestamp or query payload MUST be verified against the repo's canonical LLM-forensics store (named in the repo-level `/er`//`/es` overlay — e.g. a BigQuery `llm_payloads` table). If the record does not exist or model/content differs → **FAIL**.
- [ ] **Harness & Provenance Disambiguation**: Inspect provenance commit subjects and test user IDs for mock markers (`RealisticFakeLLMResponse`, `mock`, `fake`). Evidence driven by test harnesses or mock LLMs MUST be labeled as *Test-Harness Evidence*, NEVER as "Real Production LLM Evidence". Mislabeling → **FAIL**.
- [ ] **Traceback Code Alignment**: Any cited `file:line` in a stack trace MUST match the exact source code AST at that line. Synthetic line numbers or non-matching code → **FAIL**.
- [ ] **No Paraphrased / Synthesized Payloads**: Reject evidence files produced by custom scripts that construct payload dictionaries or text strings in memory. Evidence MUST be untrimmed raw trace outputs (`llm_request_responses.jsonl`) backed by `.sha256` checksums.
- [ ] **Checksum Recomputation (Gate D)**: Recompute `sha256sum` hashes for all evidence files in the bundle directory. Any mismatch between computed hashes and `checksums.sha256` → **FAIL**.
- [ ] **GREEN Payload Shape Verification (Gate F)**: Inspect the actual GREEN response payload. The GREEN payload MUST demonstrate the positive feature/fix behavior and MUST NOT contain filler phrases ("Administrative Update"), empty responses, or structural inversions that disprove the claimed fix. A GREEN payload that reproduces the defect or disproves its own fix → **FAIL**.
- [ ] **is_test Telemetry Verification (Gate G)**: Check BigQuery / telemetry logs for synthetic test handles matching `test[-_]`, `e2e[-_]?`, `lean_lu_`, `browser-test-` — match BOTH separator forms (`test_user`/`test-user`, `e2e_campaign`/`e2ecampaign`); a literal `test_`/`e2e_` match alone lets `test-user-42` or `e2ecampaign` slip past. Mislabeling synthetic test traffic as production traffic → **FAIL**.
- [ ] **is_test Cannot Be Trusted Alone**: 499 synthetic turns are flagged `is_test=FALSE` (bead rev-gfzts) — the `is_test` flag is not reliable evidence by itself. The reviewer MUST corroborate via the user_id prefix match above rather than relying on the flag → **FAIL**.

**Report & Bead-Close Discipline (Bead rev-siiir)** — provenance: on one mission, three consecutive completion reports asserted numbers the cited artifact contradicted, and two P0 beads were each closed twice against acceptance criteria written plainly in their own bodies:

- [ ] **Artifact Read-Back**: Every numeric claim in a report must be read back OUT of the artifact it cites — if a report cites a file path, it must quote bytes from that path. No number may appear in prose that was not read out of the cited artifact. Worst observed instance: a report claimed `cached_tokens=29604, 98.5% hit rate` while citing a 314-byte JSON file that said `cached_tokens: 0` on both turns → **FAIL**.
- [ ] **Bead-Close Discipline**: A bead may not be closed without quoting its OWN acceptance criterion verbatim and showing the artifact that satisfies it → **FAIL**.
- [ ] **Branch-Scoping**: Any "verified N occurrences" / "verified present" claim must NAME the branch checked, and where a bead names a target PR it must check THAT PR's branch. **Containment is not implementation** — `git branch -r --contains <sha>` proves a commit sits on a branch, it does NOT prove the change was made; a real failure reported a decision "done" three times on containment evidence while the target phrase was still present in the file → **FAIL**.
- [ ] **Token-Count Provenance**: Token counts must come from the API's own usage metadata, never a chars/4 estimate — that error inflated three consecutive reports by ~45% (measured: 5.69 chars/token, not 4) → **FAIL**.
- [ ] **Resolved-Model Provenance (Bead rev-64uf8)**: Any evidence bundle making a model-dependent claim (cache hit rate, latency, output quality, defect rate) MUST record the RESOLVED model name read from the API response metadata — never the intended model, never a constant's name, never what a config comment says. A bundle naming no resolved model, or naming only the intended one, is **PARTIAL** at best for any model-dependent claim.
- [ ] **Stale-Base Model Drift**: A measurement run from a feature branch inherits THAT BRANCH's constants, not production's — a stale base is a config-drift vector, the same class of error as "A/B control must be the deployed config, never 'off'" (bead rev-9piwk.2). Real instance: a cache measurement ran on a branch 10 commits behind `origin/main`, missing PR #8590's revert, so `DEFAULT_GEMINI_MODEL` silently fell back to `gemini-3.5-flash-lite` instead of production's `gemini-3-flash-preview`. The measured 72.6% hit rate was itself reported accurately; the defect was labelling that model as the current production default, so a non-production number stood in for production behavior (the production model separately measured 91% on the same prefix, and flash-lite carries a 62x near-verbatim repeat rate — bead rev-ldn6q). Caught only because the resolved model was logged and diffable against `origin/main` → **FAIL** if resolved model isn't recorded and cross-checked against the target branch.
- [ ] **Self-Check Before Publishing**: The reporting agent runs Gates A–G against its OWN output before publishing, not only as something a reviewer applies afterward. Gate F (GREEN payload shape) would have caught the worst artifact-read-back violation above had the author applied it to their own report.

**BigQuery Query-Discipline Traps** (`worldarchitecture-ai.llm_forensics`) — these produced real wrong numbers and belong wherever a reviewer queries telemetry for this gate:

- [ ] **Two Rows Per Turn**: Every turn writes TWO rows — `event_type` = `gameplay_streaming` AND `event_type` = `stream_story_with_game_state`. Pooling them without filtering to one `event_type` doubles every count → **FAIL**.
- [ ] **finish_reason Payload-Shape Split**: `finish_reason` splits one `event_type` into incompatible payload shapes (`FinishReason.STOP` vs `success`). Never pool rows across `finish_reason` values that use different shapes → **FAIL**.
- [ ] **response_text May Be a JSON Array**: `response_text` is sometimes a JSON array, not an object — a naive `JSON_EXTRACT` on it returns NULL and silently drops rows from the count → **FAIL**.
- [ ] **Key Match ≠ Value Match**: Matching a JSON KEY's presence is not evidence about its VALUE. This single error produced four wrong numbers in one session → **FAIL**.
- [ ] **The Two event_types Carry DISJOINT Columns**: they are not two views of one turn. `gameplay_streaming` populates the size estimates (`system_instruction_tokens_est`, `story_tokens_est`, `story_history_entry_count`) but leaves `turn_index` NULL on **every** row. `stream_story_with_game_state` populates `turn_index` but carries **none** of the size estimates. Measured: 92 rows / 92 NULL `turn_index` / 92 populated estimates vs 200 rows / 0 NULL / 0 populated. Any query needing size estimates MUST use `gameplay_streaming`; counts from the two are not comparable → **FAIL** if reconciled against each other as one population.
- [ ] **Never Dedup `gameplay_streaming` on `turn_index`**: the column is NULL there, so `PARTITION BY campaign_id, turn_index` silently collapses to **one row per campaign** and yields a wrong, plausible-looking rate. Real instance: "12 first attempts" was 12 *campaigns*, not 12 turns, and produced a 25% figure that was pure artifact → **FAIL**.
- [ ] **`agent` MUST Be in the PARTITION BY**: multiple agents log under one `turn_index`, so omitting `agent` keeps only the earliest-`ingested_at` row and silently drops the rest. Real instance: 0 of 25 "first-attempt" rows were `GodModeAgent` — it vanished from the result entirely. Canonical pattern: `ROW_NUMBER() OVER (PARTITION BY campaign_id, turn_index, agent ORDER BY ingested_at ASC) = 1`, on `stream_story_with_game_state`, with an explicit `agent` filter in the WHERE clause on top of the partition → **FAIL** without it.
- [ ] **Agent-Created Replay Campaigns Are Invisible to Both Filters**: copies made with `copy_campaign.py --allow-same-user` inherit the REAL `user_id`, so the synthetic-prefix regex cannot match them and `is_test` is already unreliable. Their cold-start zero-cache turns then sit in production aggregates. Eyeball a per-campaign breakdown for unfamiliar `campaign_id`s before trusting any aggregate → **FAIL** if an agent-generated campaign is counted as production traffic.

### 8. Branch & Commit Containment Verification

- [ ] **Commit Branch Containment Gate**: Run `git branch -r --contains <sha>` before asserting that a commit, fix, or schema change is present on a PR's remote branch. If the commit exists only on a sibling/worktree branch and NOT on the PR's target branch → **FAIL** (do not assume cross-branch propagation without git verification).

---

## Review Procedure

### Phase 0 — Staleness gate (run before anything else)

Resolve the SHA of the last posted `ER-VERDICT:` comment's `HEAD=` value and
compare to the subject's current HEAD. If they match, skip to the verdict phase
and re-emit the prior verdict. If they differ, run `git diff --name-only
<prior-verdict-sha> <current-sha>` per the staleness-tolerance test in
`evidence-standards`: a non-behavioral diff lets you re-affirm the prior
verdict at the new SHA without rerunning the later phases; only a material
production-behavior diff requires a full rerun. Never rerun once per finding —
if fixes are still landing, wait until they are batched into one new SHA
(`evidence-standards` § "Evidence Sequencing") before spending a full pass.
The 2-gate-cycle cap applies: a third full `/er` cycle on the same PR requires
operator escalation, not a self-authorized rerun.

### Phase 1 — Inventory

1. Enumerate all artifacts referenced by the subject (bundle dir, PR description, run.json, metadata.json, gist, release assets)
2. Enumerate all claims (from PR description, commit messages, or user-provided claim list)

### Phase 2 — Claim-to-Artifact Mapping

For each claim, identify the single primary artifact that proves it. Rate quality:

| Quality | Meaning |
|---------|---------|
| **STRONG** | Claim directly observable in a raw artifact (log line, screenshot frame, test output) with resolved capture provenance; checksum integrity is necessary but not sufficient |
| **WEAK** | Claim is indirect — derived from self-reporting (evidence.md, summary.md) without raw backing |
| **MISSING** | No artifact supports the claim |
| **INVALID** | Artifact-quality label only: an artifact exists but contradicts the claim, or fails integrity check. Overall verdict remains **FAIL**. |

### Phase 3 — Mandatory Checks

Run all eight checks in the "Mandatory Pre-PASS Checks" section above. Record the result of each.

### Phase 4 — Verdict Table

Produce output in this format:

```
## Evidence Review Verdict

**Subject**: <what was reviewed>
**Bundle**: <path>
**Overall**: PASS | PARTIAL | FAIL | INCONCLUSIVE
**Confidence**: HIGH | MEDIUM | LOW

### What This Evidence Proves vs. Does NOT Prove
**Proves**:
- <list of specific, verified claims supported by STRONG artifacts>

**Does NOT Prove**:
- <list of limitations, untested scenarios, or claims with WEAK/MISSING artifacts>

### Claim Map
| # | Claim | Artifact | Quality | Notes |
|---|-------|----------|---------|-------|
| 1 | ...   | run.json | STRONG  | Line 42 shows ...|
| 2 | ...   | (none)   | MISSING | No artifact found |

### Mandatory Checks
- [x] bundle or per-file checksums verified → 38/38 OK
- [x] verification_report.json absent/not applicable, or overall_verdict = PASS
- [x] Scope note matches claimed domain
- [x] Terminal GIF + MP4 + caption present
- [ ] Browser UI GIF: 404 — private repo hosting (→ PARTIAL)
- [x] Gist has clone + test commands

### Violations
1. <specific evidence item that fails>

### Accepted Exceptions
1. <with rationale from verification_report.json>

### Recommendations
1. <non-blocking suggestions for future bundles>
```

---

## Anti-Patterns to Reject

- **Self-referencing claims**: `evidence.md` cites itself instead of raw artifacts → WEAK
- **Circular provenance**: the bypass gate reads the reference file it's supposed to match against → artifact INVALID, overall FAIL
- **Evidence committed but not linked**: bundle in `evidence/` but PR description has no gist/release link → PR fails "clean computer" check
- **Private repo release as inline image**: GitHub won't proxy it → broken GIF → PARTIAL
- **"Native video attachment"** (drag & drop into PR comment): not directly downloadable via URL → PARTIAL
- **Screenshot instead of GIF for a flow claim**: cannot show before/action/after → FAIL
- **`echo "PASS"` in terminal video instead of real test runner output**: hard block → FAIL
- **Pre/post git SHA mismatch** in terminal video: test was run against a different commit than claimed → FAIL

---

## Invocation Contract (`/evidence_review` / `/er`)

`/er [subject or path]` runs this skill's judging rubric against a subject, combined
with a manual `evidence-standards` compliance pass, into one verdict.

**Skill-load guard is mandatory.** Before running any review, resolve this skill's
path (user-scope `~/.claude/skills/evidence-review/SKILL.md` takes priority over any
repo-scope copy). If the skill file cannot be found, **abort command execution
immediately and report the error** — do not proceed with an inline/paraphrased
methodology. The canonical skill is the single source of truth and must be present;
a subagent invoked as a fallback reviewer must load this file itself rather than
have the methodology inlined into its prompt.

**Dispatch order:**
1. Attempt codex dispatch first (`ai_orch run --agent-cli codex "<review prompt>"`).
   On success, read the resulting log for findings.
2. On codex failure/no-log, fall back to the `evidence-reviewer` subagent, which
   must load this skill file itself (per the guard above) rather than receive an
   inlined summary.
3. Regardless of which path produced the evidence-review result, continue to a
   separate manual `evidence-standards` compliance pass (read both the
   user-scope and any repo-scope `evidence-standards` skill, then judge the
   collected evidence against them) — the standards check is not optional and is
   not skipped just because codex succeeded. This full two-pass cost is paid
   ONCE per Phase-0-cleared SHA, never per push; a Phase 0 re-affirmation does
   not re-trigger it.

**Two-source verdict synthesis.** `/er` combines this skill's verdict (evidence
review) with the separate evidence-standards compliance verdict into one raw
overall verdict. Goal-driving harnesses own final normalization
(collapsing PARTIAL/INCONCLUSIVE to FAIL, WARN to PASS, per their own convergence
policy) — `/er` itself returns the raw, unnormalized verdict:

| ER verdict | ES verdict | Raw overall verdict | Harness-normalized |
|-----------|-----------|---------------------|--------------------|
| PASS | PASS | PASS | PASS |
| PASS | WARN | WARN | PASS |
| PASS | FAIL | FAIL | FAIL |
| PASS | PARTIAL | PARTIAL | FAIL |
| WARN | PASS | WARN | PASS |
| WARN | WARN | WARN | PASS |
| WARN | FAIL | FAIL | FAIL |
| PARTIAL | any | PARTIAL | FAIL |
| FAIL | any | FAIL | FAIL |
| INCONCLUSIVE | any | INCONCLUSIVE | FAIL |

**Proves vs does NOT prove reconfirmation is mandatory.** For every claim, the
final report must explicitly restate what the evidence proves and what it does
NOT prove — never skip this even when both the evidence-review and
evidence-standards passes individually PASS.

## Historical Lessons (keep the bar high)

- **2026-04-11 PR #6161**: GIFs hosted on private `your-project.com` release returned 404. Moved to public `agent-orchestrator` release. → Added mandatory check 5.
- **Pre-existing**: dirty GREEN captures (working tree dirty during the run that produced the artifact) require explicit exception in `verification_report.json` with rationale.
- **Pre-existing**: if `verification_report.json` exists, a WARN/PARTIAL verdict is a ceiling — never promote to PASS without resolving each recorded violation.
