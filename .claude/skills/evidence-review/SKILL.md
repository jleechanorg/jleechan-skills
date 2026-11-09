---
name: evidence-review
description: Enforcement rules for reviewing evidence artifacts against the evidence-standards skill. Invoked by /er. Produces PASS / PARTIAL / FAIL / INCONCLUSIVE verdicts.
---

# Evidence Review Skill

## Claim-proportionate evidence and publication

For claim-proportionate proof, follow [pr-lifecycle](../pr-lifecycle/exceptions.md#proportional-exceptions-and-fast-paths); for PR publication, use its [stage-exit receipt contract](../pr-lifecycle/six-stage.md#evidence-attached-to-every-stage-exit). Evidence content and integrity remain governed by [evidence-standards](../evidence-standards/SKILL.md).

## Retained review integrations

Follow [pr-lifecycle's retained review integrations](../pr-lifecycle/SKILL.md#retained-review-integrations) for skill discovery (including on a remote host), `UNAVAILABLE` reporting, quorum and disclosure boundaries.

**Purpose**: review evidence for a claim, a path or a PR, and produce a verdict with specific artifact-level citations. `evidence-standards` (`/es`) defines what to produce; this skill defines how to judge it. When in doubt about a requirement, read the standards first.

**Invoked by**: `/er [subject or path]`

**Standards source**: `evidence-standards` skill (`/es`). When in doubt about a requirement, read the standards first.

**Repo overlay (always check)**: this is the **user-scope (global)** `/er` policy — the floor. Before judging, resolve repo overlays through the target repository's instructions/catalog. Check `<repo>/.claude/skills/<overlay-name>.md` and `<repo>/.claude/skills/<overlay-name>/SKILL.md`, where `overlay-name` is `evidence-review` or `evidence-standards`; inspect both forms if present. These add domain-specific proof (e.g. worldarchitect.ai adds BQ/streaming/dice modes). For lifecycle stages, generic review routing, proportionality and SHA reuse, the shared [pr-lifecycle precedence rule](../pr-lifecycle/SKILL.md#precedence-and-scope) governs conflicting copies. Domain proof, security and separate merge authority remain intact.

---

## Evidence-only scope and read-only dispatch

`/er` approves evidence for the actual claims, not full source correctness or an
`/advice` vote. `/er` is not source approval and does not count toward source-review
quorum; likewise, a source-only reviewer vote does not count as evidence
approval or establish that raw evidence was reviewed. Read the complete
base-to-head diff to derive explicit and implicit claims,
then inspect claim-relevant source, artifacts, and provenance. Do not require prior
source approval or an adjacent, undeclared source-review log. If claim-relevant
source or provenance is missing, withhold the affected evidence claim rather than
guessing.

Completeness means every artifact needed for the actual claims and applicable
owner requirements, not a whole-repository semantic dump to restamp unchanged
proof. This scope boundary does not waive real-service, auth, provider, BQ,
source/provenance, visual or integrity gates, independent code/advice quorum, or
separate user/merge authority. An observed acceptance violation remains FAIL,
never a limitation or nonblocking P1.

For every claim being reviewed, directly open and inspect **all available
claim-scoped raw evidence content and source records**, including failed and
incomplete attempts. Reconcile the underlying records to the claim, provenance,
and any derived summary; independently check the content, not only hashes,
filenames, manifests, ledgers, or another reviewer's summary. Record which raw
items were inspected and which were unavailable, with the affected claim and
reason. This requires the full relevant evidence set, not unrelated repository
data or new evidence classes.

Apply the redaction and protected-original comparison requirements in
[evidence-standards](../evidence-standards/SKILL.md). Never request or expose
secrets, read `.env` files, or put unredacted credentials in reviewer/model
output. If raw evidence required for a claim cannot be opened or independently
reconciled, and no inspected artifact establishes a contradiction or acceptance
violation, mark that claim **INCONCLUSIVE** and do not approve it. A contradiction
or observed acceptance violation in inspected evidence remains **FAIL** under the
verdict rubric, even when another portion is unavailable. Label summary-only
review as limited; it cannot replace the raw-evidence review gate. Record other
claims' independently supported coverage separately.

Every review dispatch, including coordinator asks, must explicitly say: remain
read-only; do not mutate source/evidence, post, push, update branches, or change
PR metadata/stages. Return findings only. Do not regenerate evidence or write a
verification report into the producer bundle. Frame extraction may use unique
review scratch without changing original media. The separately authorized owner
handles fixes and publication; a review invocation does not authorize them.

### Claim and artifact preflight

Inventory claimed artifacts and reconcile raw bytes, provenance, and checksum
coverage with existing utilities. Map canonical producer files to `/es` duties;
do not demand duplicate logs. Independently verify coverage and bytes, and
reproduce each applicable documented check. Runtime claims require actual
runtime/provider provenance. Missing claim-required proof is non-approving.
Source-only Markdown changes do not trigger an artifact campaign; runtime or
artifact claims retain named domain proof. Batch fixes before dispatch; use
Phase 0 for later deltas rather than relabeling old evidence.

## Verdict Rubric

| Verdict | Meaning |
|---------|---------|
| **PASS** | Every claim has a matching artifact of STRONG quality and every applicable mandatory check below passes. Satisfies the draft-phase `/er` gate when `/er` is applicable. |
| **PARTIAL** | Claims are supported but one or more required claims lack proof, or a warning identifies a gap in required proof or evidence integrity (including a relevant warning in an optional verification_report.json). An unrelated optional warning does not change the verdict. Does not satisfy the draft-phase `/er` gate. |
| **FAIL** | A claim is contradicted by an artifact, or integrity is broken (sha256 mismatch, dirty capture producing the claim, scope exclusion). |
| **INCONCLUSIVE** | Not enough artifact data exists to decide. Request more. |

## Lifecycle applicability

The [canonical pr-lifecycle contract](../pr-lifecycle/SKILL.md) owns `/er`
applicability, phase, and SHA-bound reuse or delta review. Resolve that route
before invoking this skill; do not restate or expand its exceptions. Preserve
original tested/reviewed SHAs and explain candidate applicability under its
delta rule. Follow the lifecycle and domain owners for any separate review,
runtime-proof, or publication requirements.

---

## Mandatory Pre-PASS Checks (all must pass)

### 1. Bundle integrity

The example below handles the default manifest and sibling modes. If the
canonical producer uses another aggregate filename, explicitly record its mapping
to the same complete coverage contract and verify it with the existing producer
verification utility or `sha256sum -c <mapped-manifest>` instead. A filename
difference is not missing integrity; absent coverage or mismatching bytes is.

```bash
(
  bundle_dir='<bundle_dir>'
  cd "$bundle_dir" || { echo "Failed to enter bundle directory" >&2; exit 1; }

  if [[ -f checksums.sha256 ]]; then
    sha256sum -c checksums.sha256
  else
    cs_list="$(mktemp)" || exit 1
    if ! find . -name "*.sha256" -type f -print0 > "$cs_list"; then
      echo "Failed to discover checksum files" >&2
      rm -f "$cs_list"
      exit 1
    fi

    found_any=false
    status=0
    while IFS= read -r -d '' cs_file; do
      found_any=true
      dir="$(dirname "$cs_file")"
      base="$(basename "$cs_file")"
      ( cd "$dir" && sha256sum -c "$base" ) || status=1
    done < "$cs_list"
    rm -f "$cs_list"

    if [ "$found_any" = false ]; then
      echo "No checksum files found" >&2
      exit 2
    fi
    exit "$status"
  fi
)
```

- A top-level `checksums.sha256` means bundle-checksum mode; without one, verify every per-file `*.sha256`.
- Any checksum mismatch → **FAIL** (not just PARTIAL: the bundle is tampered or stale).
- No checksum files → **INCONCLUSIVE** for integrity; do not award PASS.
- Independently inventory every substantive bundle artifact, including every claim-map artifact, and reconcile it against checksum coverage. A complete aggregate `checksums.sha256` manifest OR per-file `.sha256` siblings is sufficient; do not demand both. Resolve manifest paths from the bundle root and sibling entries from their own directory. Missing coverage or a listed-but-missing artifact is an integrity **FAIL**. A successful `sha256sum -c` checks listed bytes only and does not establish inventory completeness.

**Checksums establish integrity, not provenance.** A matching digest proves only that the reviewed bytes match the manifest, not where they came from, which code path produced them, or that they demonstrate the claimed behavior. For STRONG evidence, also resolve the primary raw artifact against its capture provenance (for example `metadata.json.provenance.git_head`, runtime/process metadata, and the raw request/response or test output that directly shows the claim). A claim supported only by a checksum or manifest entry is **MISSING**, not STRONG.

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
- `WARN` or `PARTIAL` → affects the overall verdict only when it identifies a gap in a required claim, required proof, or evidence integrity; an unrelated warning is recorded as a note and does not cap the verdict
- `FAIL` → verdict ceiling is **FAIL**

### 3. Scope note consistency

```bash
grep -A10 "Scope note" README.md
```

- If the scope note excludes a domain the PR claim covers (e.g. "browser layer out of scope") → narrow the verdict to in-scope claims.
- If the scope note was updated to include a domain, verify the matching artifact exists.

### 4. Video artifacts required by the claim

Select video requirements from the user-scope evidence-standards and the repository UI owner, including the canonical narrow trivial-copy exceptions. Other user-visible behavior needs captioned video tied to the tested SHA. Terminal recording is required when the relevant owner or user asks for it or the claim depends on terminal behavior; a test invocation alone does not create a GIF-plus-MP4 requirement.

For each applicable video requirement, verify:
- The required format is present and accessible, including any inline GIF or downloadable MP4 the PR claims to provide.
- The caption identifies the test/action, observed result and tested SHA.
- Apply the canonical [`evidence-standards` continuous-video rule](../evidence-standards/SKILL.md#continuous-video-only--slideshows-are-forbidden). A slideshow remains **FAIL** even when transport and file-integrity checks pass.
- UI footage visibly shows the relevant element and the applicable before→after behavior; when a user action exists, it also shows the before/action/after flow.
- Terminal footage, when required, shows the command and relevant result.
- The mpdecimate retained-frame count and nominal count are reported with the fail-closed probe in `../ui-video-evidence/SKILL.md`; a low count is diagnostic evidence of a possible slideshow or frozen capture, while the canonical continuous-capture provenance rule remains mandatory.
- When a user action exists, each clip includes the action (e.g. the Send tap) plus the before state; a window anchored only to completion that omits the action fails. If the observable has no user action, record N/A with the reason and require a before-state → after-state transition clip.
- Before/after clips come from fresh runs of each build; any re-cut or reused baseline is labeled `derived` with its source.
- This `/er` verdict (and any `/advice` on the evidence) comes from a different agent/lane than the one that produced the evidence, and the verdict names that lane (lanes may share one GitHub account).

A missing or inaccessible media format yields **PARTIAL** only when it is
supplemental and the claim's decisive raw evidence has been inspected. If the
media is the claim's decisive raw proof and cannot be opened, mark the claim
**INCONCLUSIVE** under the raw-coverage rule above, unless inspected evidence
establishes **FAIL**. Record inapplicable formats as N/A with a reason; do not
impose terminal and browser video on every PR.

**Video acceptance needs an independent content review.** When a video backs an acceptance claim, an independent AI reviewer (not the author or orchestrator) extracts frames from the published video itself (not the capture's own screenshots) and returns PASS/FAIL per acceptance step with the timestamp where it is visible. Privacy masking, decode/playback, upload read-back, captions, and turn-record or coverage-judge JSON are separate checks and never substitute. No content review → **PARTIAL**; a step the frames contradict → **FAIL**.

**Mandatory AI Visual Inspection (`VISUAL APPROVED at <40-char-sha>`):** applicability, record contents and SHA binding are owned by [pr-lifecycle's visual-approval contract](../pr-lifecycle/six-stage.md#review-routes-for-opted-in-repositories). For any user-visible change outside the documented exemptions, the approving seat (an `/advice` visual lane, `/dot`, or an `/er` visual lane run by a seat other than the one that produced or reviewed the evidence, as that contract requires) MUST download and visually inspect the actual rendered image or extracted video frames, never just URL status or checksums, and record `VISUAL APPROVED at <40-char-sha>` (or `VISUAL REJECTED at <40-char-sha>`) with the per-claim findings that contract requires. A link-existence check or pending request (e.g. `/dot: REQUESTED, pending`) is NEVER a visual approval PASS: it caps `/er` at **PARTIAL** and blocks `stage:5-final-approval` and merge readiness.

### 5. Media hosting check

Apply this check when inline or linked media backs a claim; it does not by itself require publishing an otherwise private evidence bundle. Evidence classes and hosting rules are owned by evidence-standards (§ UI/media proof); this check applies them and adds no stricter hosting rule.

- GCS is the default host; a GitHub attachment or any other host the task authorizes is also acceptable.
- Authorized private hosting is acceptable when the intended reviewer can open and play the media; record the access mode.
- Never make evidence public, or change bucket access, merely to pass a link check.
- A `github.com/.../releases/download/untagged-*` link is a red flag: the release is a draft and the asset is not reliably reachable.

Media the intended reviewer cannot open or play is **INCONCLUSIVE** when it is
the claim's decisive raw proof; it is **PARTIAL** only for a supplemental format
when the claim's raw evidence has already been inspected. An inspected
contradiction or acceptance violation remains **FAIL**.

### 6. Self-contained / clean-computer reproducibility

Apply the reproducibility requirements for the evidence class in `evidence-standards`. A PASS needs self-contained directions that identify:

- [ ] The exact reviewed SHA, source location, and commands to retrieve it. If evidence was re-affirmed, keep its original tested SHA and the reviewed SHA with the canonical materiality justification.
- [ ] Required dependencies and prerequisites, including runtime versions and any service/account requirements; never include credentials.
- [ ] Exact validation commands and expected results, such as pass counts or scenario outcomes.
- [ ] Any media required by section 4, with its tested SHA and accessible location.

Directions may live in the PR, a checked-in document, an access-controlled evidence receipt or an authorized gist. Link them and ensure the intended reviewer can access them; this check does not authorize external publication.

**Failure mode**: instructions that only say "see the repo" or "run the tests", without exact commands and expected results → PARTIAL.

### 7. Anti-Fabrication & Telemetry Verification (Bead rev-wghca)

- [ ] **BQ Record Resolution**: Verify any cited BigQuery/telemetry timestamp or query payload against the repo's canonical LLM-forensics store (named in the repo-level `/er`//`/es` overlay, e.g. a BigQuery `llm_payloads` table). Record missing, or model/content differs → **FAIL**.
- [ ] **Harness & Provenance Disambiguation**: Inspect provenance commit subjects and test user IDs for mock markers (`RealisticFakeLLMResponse`, `mock`, `fake`). Evidence driven by test harnesses or mock LLMs MUST be labeled *Test-Harness Evidence*, NEVER "Real Production LLM Evidence". Mislabeling → **FAIL**.
- [ ] **Traceback Code Alignment**: A cited `file:line` in a stack trace MUST match the exact source code AST at that line. Synthetic line numbers or non-matching code → **FAIL**.
- [ ] **No Paraphrased / Synthesized Payloads**: Reject evidence files produced by custom scripts that build payload dictionaries or text strings in memory. Evidence MUST be untrimmed raw trace output (`llm_request_responses.jsonl`) backed by `.sha256` checksums.
- [ ] **Checksum Recomputation (Gate D)**: Recompute `sha256sum` for all evidence files in the bundle (check 1). Any mismatch with `checksums.sha256` → **FAIL**.
- [ ] **GREEN Payload Shape Verification (Gate F)**: Inspect the actual GREEN response payload. It MUST demonstrate the positive feature/fix behavior and MUST NOT contain filler phrases ("Administrative Update"), empty responses, or structural inversions. A GREEN payload that reproduces the defect or disproves its own fix → **FAIL**.
- [ ] **is_test Telemetry Verification (Gate G)**: Check BigQuery / telemetry logs for synthetic test handles matching `test[-_]`, `e2e[-_]?`, `lean_lu_`, `browser-test-`, matching BOTH separator forms (`test_user`/`test-user`, `e2e_campaign`/`e2ecampaign`); a literal `test_`/`e2e_` match alone lets `test-user-42` or `e2ecampaign` slip past. Synthetic test traffic labeled as production → **FAIL**.
- [ ] **is_test Cannot Be Trusted Alone**: 499 synthetic turns are flagged `is_test=FALSE` (bead rev-gfzts). Corroborate with the user_id prefix match above rather than the flag → **FAIL** otherwise.

**Report & Bead-Close Discipline (Bead rev-siiir)** — provenance: on one mission, three consecutive completion reports asserted numbers the cited artifact contradicted, and two P0 beads were each closed twice against acceptance criteria written plainly in their own bodies:

- [ ] **Artifact Read-Back**: Read every numeric claim in a report back OUT of the artifact it cites; a report citing a file path quotes bytes from that path, and no number may appear in prose that was not read from the cited artifact. Worst observed instance: a report claimed `cached_tokens=29604, 98.5% hit rate` while citing a 314-byte JSON file that said `cached_tokens: 0` on both turns → **FAIL**.
- [ ] **Bead-Close Discipline**: A bead may not be closed without quoting its OWN acceptance criterion verbatim and showing the artifact that satisfies it → **FAIL**.
- [ ] **Branch-Scoping**: A "verified N occurrences" / "verified present" claim must NAME the branch checked, and where a bead names a target PR it must check THAT PR's branch. **Containment is not implementation**: `git branch -r --contains <sha>` proves a commit sits on a branch, not that the change was made; a real failure reported a decision "done" three times on containment evidence while the target phrase was still in the file → **FAIL**.
- [ ] **Token-Count Provenance**: Token counts come from the API's own usage metadata, never a chars/4 estimate; that error inflated three consecutive reports by ~45% (measured: 5.69 chars/token, not 4) → **FAIL**.
- [ ] **Resolved-Model Provenance (Bead rev-64uf8)**: Evidence making a model-dependent claim (cache hit rate, latency, output quality, defect rate) MUST record the RESOLVED model name read from the API response metadata, never the intended model, a constant's name or a config comment. Naming no resolved model, or only the intended one, is **PARTIAL** at best for any model-dependent claim.
- [ ] **Stale-Base Model Drift**: A measurement run from a feature branch inherits THAT BRANCH's constants, not production's; a stale base is a config-drift vector, the same class of error as "A/B control must be the deployed config, never 'off'" (bead rev-9piwk.2). Real instance: a cache measurement ran on a branch 10 commits behind `origin/main`, missing PR #8590's revert, so `DEFAULT_GEMINI_MODEL` silently fell back to `gemini-3.5-flash-lite` instead of production's `gemini-3-flash-preview`. The measured 72.6% hit rate was reported accurately; the defect was labelling that model the production default, so a non-production number stood in for production behavior (the production model measured 91% on the same prefix, and flash-lite carries a 62x near-verbatim repeat rate — bead rev-ldn6q). Caught only because the resolved model was logged and diffable against `origin/main` → **FAIL** if the resolved model isn't recorded and cross-checked against the target branch.
- [ ] **Self-Check Before Publishing**: The reporting agent runs Gates A–G against its OWN output before publishing, not only as a reviewer step afterward. Gate F (GREEN payload shape) would have caught the worst artifact-read-back violation above.

**BigQuery Query-Discipline Traps** (`worldarchitecture-ai.llm_forensics`) — these produced real wrong numbers and apply wherever a reviewer queries telemetry for this gate:

- [ ] **Two Rows Per Turn**: Every turn writes TWO rows, `event_type` = `gameplay_streaming` AND `event_type` = `stream_story_with_game_state`. Pooling them without filtering to one `event_type` doubles every count → **FAIL**.
- [ ] **finish_reason Payload-Shape Split**: `finish_reason` splits one `event_type` into incompatible payload shapes (`FinishReason.STOP` vs `success`). Never pool rows across `finish_reason` values with different shapes → **FAIL**.
- [ ] **response_text May Be a JSON Array**: `response_text` is sometimes a JSON array, not an object; a naive `JSON_EXTRACT` returns NULL and silently drops rows from the count → **FAIL**.
- [ ] **Key Match ≠ Value Match**: A JSON KEY's presence is not evidence about its VALUE. This single error produced four wrong numbers in one session → **FAIL**.
- [ ] **The Two event_types Carry DISJOINT Columns**: they are not two views of one turn. `gameplay_streaming` populates the size estimates (`system_instruction_tokens_est`, `story_tokens_est`, `story_history_entry_count`) but leaves `turn_index` NULL on **every** row; `stream_story_with_game_state` populates `turn_index` but **none** of the size estimates. Measured: 92 rows / 92 NULL `turn_index` / 92 populated estimates vs 200 rows / 0 NULL / 0 populated. Queries needing size estimates MUST use `gameplay_streaming`, and the two counts are not comparable → **FAIL** if reconciled as one population.
- [ ] **Never Dedup `gameplay_streaming` on `turn_index`**: the column is NULL there, so `PARTITION BY campaign_id, turn_index` silently collapses to **one row per campaign** and yields a wrong, plausible-looking rate. Real instance: "12 first attempts" was 12 *campaigns*, not 12 turns, and produced a 25% figure that was pure artifact → **FAIL**.
- [ ] **`agent` MUST Be in the PARTITION BY**: several agents log under one `turn_index`, so omitting `agent` keeps only the earliest-`ingested_at` row and drops the rest. Real instance: 0 of 25 "first-attempt" rows were `GodModeAgent`; it vanished from the result. Canonical pattern: `ROW_NUMBER() OVER (PARTITION BY campaign_id, turn_index, agent ORDER BY ingested_at ASC) = 1`, on `stream_story_with_game_state`, with an explicit `agent` filter in the WHERE clause on top of the partition → **FAIL** without it.
- [ ] **Agent-Created Replay Campaigns Are Invisible to Both Filters**: copies made with `copy_campaign.py --allow-same-user` inherit the REAL `user_id`, so the synthetic-prefix regex cannot match them and `is_test` is already unreliable; their cold-start zero-cache turns sit in production aggregates. Eyeball a per-campaign breakdown for unfamiliar `campaign_id`s before trusting any aggregate → **FAIL** if an agent-generated campaign is counted as production traffic.

### 8. Branch & Commit Containment Verification

- [ ] **Commit Branch Containment Gate**: Run `git branch -r --contains <sha>` before asserting that a commit, fix or schema change is on a PR's remote branch. A commit only on a sibling/worktree branch and NOT on the PR's target branch → **FAIL** (never assume cross-branch propagation without git verification).

### 9. Observed acceptance violations

Before PASS, list every forbidden-state observation in the raw artifacts (request ledgers, logs, frames) and compare it verbatim with the user's stated acceptance and the UI's own disclosure text.

- [ ] An observation either one forbids → **FAIL**. It may not be moved to Does NOT Prove, `limits`, a follow-up bead or a P1 "wording" item, and narrowing the claim (e.g. "protected endpoints only", "no zero-network claim") does not clear it. Exits: a code fix with fresh evidence, or the user accepting that exact behavior in a live message.
- [ ] A benign label (transport-only, warmup, best-effort, no content) is not a waiver: the disclosure and acceptance govern, not the payload.
- [ ] Reviewer prompts must not carry the author's classification of the observation; the reviewer judges it from the raw artifact.

Example: if a warm-up request fires while consent is off under a dialog saying "Nothing is sent until you allow it", neither filing it as a nonblocking follow-up nor handing the reviewer a "transport-only" assessment allows PASS, and no video bundle passes without an independent AI review of the frames.

---

## Review Procedure

### Phase 0 — Staleness gate (run before anything else)

Resolve the last `ER-VERDICT:` and its original HEAD, base, claims, evidence, and
phase. Apply [pr-lifecycle's SHA-binding rule](../pr-lifecycle/SKILL.md#sha-binding-rule-critical--applies-to-every-gate-in-this-chain):
a matching HEAD alone does not establish unchanged scope or coverage. Record
candidate applicability without restamping the original verdict. Recheck claims
affected by changes to behavior or to a dependent assertion, driver, or
executable instruction, using the review coverage the lifecycle requires.
If impact cannot be bounded, rerun the affected review; batch fixes first.

Continue necessary review and already-authorized fixes within the task scope and autonomy deadline. A review-only invocation reports findings without editing the reviewed source or evidence; fixes use write authority the parent task already holds. Review count alone does not require escalation; ask only for missing authority or an unresolved decision that blocks the affected action.

### Phase 1 — Inventory

1. Enumerate all artifacts referenced by the subject (bundle dir, PR description,
   run.json, metadata.json, gist, release assets), including the complete
   claim-scoped raw set and failed or incomplete attempts. Record unavailable
   items with the affected claim and reason.
2. Enumerate all claims (from PR description, commit messages, or user-provided claim list).

### Phase 2 — Claim-to-Artifact Mapping

For each claim, identify the single primary artifact that proves it. Rate quality:

| Quality | Meaning |
|---------|---------|
| **STRONG** | Claim directly observable in a raw artifact (log line, screenshot frame, test output) with resolved capture provenance; checksum integrity is necessary but not sufficient |
| **WEAK** | Claim is indirect — derived from self-reporting (evidence.md, summary.md) without raw backing |
| **MISSING** | No artifact supports the claim |
| **INVALID** | Artifact-quality label only: an artifact exists but contradicts the claim, or fails integrity check. Overall verdict remains **FAIL**. |

### Phase 3 — Mandatory Checks

Run each applicable check in "Mandatory Pre-PASS Checks" above. Record its result, or N/A with the scope reason.

### Phase 4 — Verdict Table

Produce output in this format:

```
## Evidence Review Verdict

**Subject**: <what was reviewed>
**Bundle**: <path>
**Raw coverage**: inspected <claim/items>; unavailable <claim/item, reason> (or None)
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
- [x] Required or claimed terminal media: <verified artifacts, or N/A with reason>
- [ ] Required or claimed browser media: <verified artifacts, or concrete missing artifact and verdict>
- [x] Linked reproduction directions: <location with exact SHA, dependencies, commands, and expected results>

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
- **Reproduction directions missing or inaccessible**: no accessible link or inline directions meeting section 6 → PARTIAL, even if evidence files were committed.
- **Inline media the reviewer cannot open**: e.g. a private-repo release asset GitHub won't proxy, or an `untagged-*` release link → **INCONCLUSIVE** when it is the claim's decisive raw proof; **PARTIAL** only for a missing supplemental format after the raw claim evidence was inspected (see check 5).
- **Required media inaccessible**: mark the claim **INCONCLUSIVE** when the inaccessible artifact is decisive raw proof; use **PARTIAL** only for a supplemental format when the claim's raw evidence has already been inspected. An inspected contradiction or acceptance violation remains **FAIL**. Verify access rather than inferring failure from the attachment method.
- **Static screenshot offered as required flow video**: it does not show before/action/after behavior → FAIL for that flow claim.
- **`echo "PASS"` in terminal video instead of real test runner output**: hard block → FAIL
- **Pre/post git SHA mismatch** in terminal video: test was run against a different commit than claimed → FAIL

---

## Invocation Contract (`/evidence_review` / `/er`)

`/er [subject or path]` combines this skill's judging rubric with a manual `evidence-standards` compliance pass into one verdict.

**Skill-load guard is mandatory.** Before any review, resolve this skill's path (user-scope `~/.claude/skills/evidence-review/SKILL.md` takes priority over any repo-scope copy). If the file cannot be found, **abort and report the error**; never proceed with an inline or paraphrased methodology. A subagent invoked as a fallback reviewer loads this file itself rather than having the methodology inlined into its prompt.

**Review and standards coverage:** Select one available independent evidence reviewer through [advice's capability profiles and tiers](../advice/SKILL.md#capability-profile-and-tier-selection), using the first authorized tier that can cover the complete scope; no fixed CLI, model or machine dependency applies. The selected reviewer loads this skill and the applicable user-scope and repository `evidence-standards` requirements, then reports artifact-level findings. Evidence adjudication is separate from the `/advice` source-vote quorum: this reviewer supplies the evidence verdict, not a source-review vote. The lifecycle owns quorum, stage coverage, and receipt reuse.

**Verdict synthesis.** Combine this skill's evidence findings with the
applicable evidence-standards compliance result into one raw overall verdict.
Goal-driving harnesses own any further normalization under their own policy.
Evaluate rows from top to bottom; the first matching row wins. A FAIL in either
input takes precedence over PARTIAL or INCONCLUSIVE in the other.

| ER verdict | ES verdict | Raw overall verdict | Harness-normalized |
|-----------|-----------|---------------------|--------------------|
| any | FAIL | FAIL | FAIL |
| FAIL | any | FAIL | FAIL |
| PASS | PASS | PASS | PASS |
| PASS | WARN | WARN | PASS |
| PASS | PARTIAL | PARTIAL | FAIL |
| WARN | PASS | WARN | PASS |
| WARN | WARN | WARN | PASS |
| PARTIAL | any | PARTIAL | FAIL |
| INCONCLUSIVE | any | INCONCLUSIVE | FAIL |

**Normalization constraint:** A harness may normalize `WARN` to `PASS` only when all mandatory proof, required artifacts, and claim coverage are fully verified (i.e., the warning is strictly advisory/non-blocking and all mandatory checks pass). A normalization label can NEVER establish `PASS` while mandatory proof or required claim coverage is missing; in such cases the verdict remains capped at `PARTIAL` or `FAIL` under the applicable mandatory check in sections 1–4 (and at `PARTIAL` per check 2 when `verification_report.json` is `WARN`/`PARTIAL`). Under no circumstance may a harness or reviewer promote missing mandatory proof to PASS.

**Proves vs does NOT prove reconfirmation is mandatory.** For every claim, the final report restates what the evidence proves and does NOT prove, even when both passes PASS.

## Historical Lessons (keep the bar high)

- **2026-04-11 PR #6161**: GIFs hosted on private `your-project.com` release returned 404. Moved to public `agent-orchestrator` release. → Added mandatory check 5 (now deferring to evidence-standards hosting rules, with GCS as the default host).
- **Pre-existing**: dirty GREEN captures (working tree dirty during the run that produced the artifact) require explicit exception in `verification_report.json` with rationale; a WARN/PARTIAL report stays a ceiling under check 2.
