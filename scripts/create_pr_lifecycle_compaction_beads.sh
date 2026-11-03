#!/usr/bin/env bash
# Create the pr-lifecycle compaction beads from docs/2026-11-03-pr-lifecycle-compaction-beads.md.
# Run from the repository root on a machine with the br (beads_rust) CLI installed.
# Usage: scripts/create_pr_lifecycle_compaction_beads.sh [--dry-run]
set -euo pipefail
DRY_RUN=0; [[ "${1:-}" == "--dry-run" ]] && DRY_RUN=1
command -v br >/dev/null 2>&1 || { echo "br CLI not found; see .claude/skills/beads-issue-tracking/SKILL.md" >&2; exit 1; }
BR=(br); if [[ "$(git rev-parse --abbrev-ref HEAD 2>/dev/null)" != "main" ]]; then BR=(br --no-auto-flush); fi
DOC="docs/2026-11-03-pr-lifecycle-compaction-beads.md"
declare -A IDS=()
create() { local key="$1" title="$2" type="$3" prio="$4" body="$5"
  body="Spec: $DOC (workflow wf_42eba406-176, verified at HEAD 6662dff)."$'\n\n'"$body"
  if (( DRY_RUN )); then echo "[dry-run] br create \"$title\" --type $type --priority $prio"; IDS[$key]="dry-$key"; return; fi
  local out; out=$("${BR[@]}" create "$title" --type "$type" --priority "$prio" --description "$body")
  echo "$out"; IDS[$key]=$(grep -oE '[A-Za-z]+-[A-Za-z0-9]+' <<<"$out" | head -1 || true)
}
create b1 'EPIC: Compact pr-lifecycle skill family without weakening any pinned contract' epic 1 'Context:
- Repo: https://github.com/jleechanorg/jleechan-skills
- File: .claude/skills/pr-lifecycle/SKILL.md (607 lines, ~8300 words) plus entry points prw, pr-workflow, draft-first-pr, pr-workflow-manager and siblings ready, evidence-review, pr-green-definition.
- Verified at HEAD 6662dff; pr-lifecycle/SKILL.md is byte-identical to 65ecdda (git diff --stat 65ecdda HEAD -- .claude/skills/pr-lifecycle shows no change), so all child-bead line ranges are valid at both.
- Finding: the file is moderately bloated. ~60% of its text is pinned verbatim or via section splits by tests/test_coding_lifecycle_contract.py, tests/test_approval_contracts.py, tests/test_skill_portability_scan.py, tests/test_cross_host_catalog.py; 14 heading anchors are linked from 6 siblings. The compressible mass is (a) a 65-line inline script, (b) a Slow CI section that re-explains pr-green-definition, (c) repeated timeout/fallback/precedence/fast-path clauses, (d) sibling restatements.
- Why it matters: every /prw invocation loads ~8k words; repeated clauses (e.g. the 1800s override parenthetical, commit 2c03315 edited it in 3 places) drift on each patch.
- Staleness note: line numbers verified at 6662dff; re-read before each child.

Implementation (ordered children; each is its own PR):
1. Add anchor-resolution guard test and freeze list (0 lines) — must land first.
2. Extract /er base-resolution script to .claude/skills/pr-lifecycle/scripts/ (~54 lines).
3. Collapse Slow CI section to a pr-green-definition pointer; trim CodeRabbit tail (~11 lines).
4. Dedupe reviewer-timeout/fallback restatements L78-90, L196-197 (~6-8 lines).
5. Micro-dedupe pass: opening precedence, merge-authority tail, advice threshold, batch-fixes pointers, one-liner carve-outs (~10-14 lines).
6. Sibling trims: evidence-review:175, pr-workflow-manager preface/activation/stage block, pr-workflow alias consistency (~15-20 lines).
7. Compact ready/SKILL.md item 3 (~5-6 lines).
8. Optional: references/ extraction of six-stage reference prose and gate 4 detail (~50-65 lines, test helper change).
- Constraints: every child edits approval/review/evidence policy. Per pr-lifecycle L234 (non-policy skill updates are the only skill edits on the non-production path), these PRs do NOT qualify for the lightweight path: each needs the full draft route with an independent adversarial /er review and the two-voter /advice quorum regardless of diff size, and should also get the /advice second-opinion vote before undraft.
- Non-goals: do not resurrect killed findings (SHA-binding dedupe, PUBLICATION BLOCKED dedupe, Retained-review-integrations trim, review-records move, change-impact move, alias collapse, manager Find-the-skills trim).
- Forbidden paths: no heading renames/re-slugs; no new '"'"' ## '"'"' H2 inside pinned section splits (Coding lifecycle 267-320, Advice applicability 46-117, Review records 547-EOF); no edits to lines 14-64, the stage table 160-167, readback 138-145, 105-116 counting rule.

Acceptance criteria:
- Tests: python -m pytest tests/test_coding_lifecycle_contract.py tests/test_approval_contracts.py tests/test_skill_portability_scan.py tests/test_cross_host_catalog.py tests/test_installer.py green after every child.
- Line-count target: pr-lifecycle/SKILL.md <= ~500 lines after children 2-5 (from 607); <= ~440 if child 8 lands.
- Done when: all children closed, wc -l confirms targets, every `../pr-lifecycle/SKILL.md#<slug>` link in .claude/skills resolves (guard test from child 1).'
create b2 'Add pr-lifecycle anchor-resolution guard test and document the freeze list' task 1 'Context:
- Repo: https://github.com/jleechanorg/jleechan-skills, HEAD 6662dff (== 65ecdda for pr-lifecycle).
- Finding: 14 distinct `pr-lifecycle/SKILL.md#<slug>` anchors are linked from 6 siblings (grep -rno "pr-lifecycle/SKILL.md#[a-z0-9-]*" .claude): #precedence-and-scope (evidence-standards:242,543; evidence-review:27), #proportional-exceptions-and-fast-paths (evidence-standards:11; evidence-review:10; pr-workflow-manager:119), #evidence-attached-to-every-stage-exit (evidence-standards:11; evidence-review:10; pr-workflow-manager:143; ready:50), #retained-review-integrations (evidence-review:14; pr-workflow-manager:61; pr-green-definition:25), #advice-applicability (advice:10), #reviewer-timeout-and-completion (pr-workflow-manager:19), #continuation-through-the-requested-endpoint (pr-workflow-manager:57), #stage-title-and-labels, #sha-binding-rule-critical--applies-to-every-gate-in-this-chain, #default-pr-route--prw (pr-workflow-manager:113; evidence-review:281), #review-routes-for-opted-in-repositories (ready:10; pr-workflow-manager:120), #draft-phase-final-acceptance-gates-in-order (ready:12; pr-workflow-manager:121), #ready-phase--finish-ready-then-final-reviews and #review-records-in-the-pr-description (ready:46). Only 7 are asserted as link strings by tests (test_coding_lifecycle_contract.py:40,46,409-412,443; test_approval_contracts.py:176-177). No test asserts that any slug resolves to a heading.
- Why it matters: every compaction child below can silently break a sibling link by rewording a heading; this guard must exist before any heading-adjacent edit lands.
- Staleness note: verified at 6662dff; re-grep before implementing.

Implementation:
- Files: tests/test_coding_lifecycle_contract.py (new test near the anchor assertions at ~L405-412) or a new tests/test_pr_lifecycle_anchors.py.
- Shape: scan every .claude/skills/**/SKILL.md for `pr-lifecycle/SKILL.md#(slug)`, slugify every heading in pr-lifecycle/SKILL.md with the GitHub rule (lowercase, strip punctuation except hyphens, spaces -> '"'"'-'"'"', so '"'"'—'"'"' and '"'"'&'"'"' collapse to '"'"'--'"'"'), assert each discovered slug is in the heading set. Discover targets by scanning; do not hard-code the 14.
- Also record in the test module docstring the freeze list: heading-text pins ('"'"'## Precedence and scope'"'"' :37, '"'"'\n## Proportional exceptions and fast paths\n'"'"' :30, '"'"'## Coding lifecycle — scale layers to risk'"'"' approval:199, '"'"'## Review records in the PR description'"'"' :306, '"'"'### Documentation-only `/er` exception'"'"' portability:199/252, '"'"'State readback before reporting a blocker'"'"'), section-split boundaries ('"'"' ## '"'"' after '"'"'## Coding lifecycle'"'"' :56 and '"'"'## Advice applicability'"'"' :235-236; note the Review-records split at :307 uses '"'"' ## '"'"' which never matches, so that section runs to EOF), ordered tokens in the lifecycle diagram (:259), the six stage-table rows, '"'"'the stage suffix goes last'"'"' (approval:219), '"'"'VISUAL APPROVED at <40-char-sha>'"'"' / '"'"'`/dot: REQUESTED, pending`'"'"' / '"'"'stage:5-final-approval'"'"' co-required in pr-lifecycle, evidence-review and pr-workflow-manager (:419-424), '"'"'**Evidence**: <gist-url> (head <sha>)'"'"' (:383), '"'"'local-equivalent exception'"'"' (:280), '"'"'every PR under 50 changed lines'"'"' (:239,248), the L105-112 counting examples (:223-231), '"'"'Mandatory regardless of class'"'"'/'"'"'Skippable by class'"'"' stated once (:172-173).
- Constraints: test-only change; no SKILL.md edits.
- Non-goals: fixing any currently broken link (none found).
- Forbidden paths: do not change existing assertions.

Acceptance criteria:
- Tests: new test passes at HEAD; mutating any one pr-lifecycle heading locally makes it fail.
- rg check: rg -o '"'"'pr-lifecycle/SKILL.md#[a-z0-9-]+'"'"' .claude/skills | sort -u count equals the number of slugs the test discovers.
- Done when: test merged and listed as a prerequisite in every other child bead.'
create b3 'Extract /er base-resolution bash script to pr-lifecycle/scripts/ with a stub' task 1 'Context:
- Repo: https://github.com/jleechanorg/jleechan-skills, HEAD 6662dff (== 65ecdda).
- File/line evidence: .claude/skills/pr-lifecycle/SKILL.md:381-448, a fenced ```bash block (gh api pulls lookup, embedded python URL normalisation, remote matching, `${BASE_REMOTE}/${BASE_BRANCH}...HEAD` diff) under '"'"'### Documentation-only `/er` exception (narrow allowlist)'"'"'. Quote: `BASE_DATA=$(gh api "repos/{owner}/{repo}/pulls/${PR_NUMBER}" --jq '"'"'[.base.ref, .base.repo.clone_url, .base.repo.ssh_url] | @tsv'"'"')`.
- Why it matters: 65 lines of executable code in the entry file are loaded on every /prw though only the narrow docs-only exemption needs them; a real file is executable, lintable and directly testable. Largest single safe cut in the file.
- Installer: install-claude-commands.sh list_installable_files() (L511-519) copies every file under skills/<name>/ (tests/test_installer.py:32-33 confirms skills/example/scripts/helper.sh is installed), so a skill-local script ships with the prw profile.
- Staleness note: verified at 6662dff; re-read L381-458 before editing.

Implementation:
- Files: new .claude/skills/pr-lifecycle/scripts/pr-base-changed-paths.sh (chmod +x, `#!/usr/bin/env bash`, `set -euo pipefail`, PR number as $1 with the existing `gh pr view --json number` fallback); .claude/skills/pr-lifecycle/SKILL.md:381-448; tests/test_skill_portability_scan.py:~196-260.
- SKILL.md stub (6-8 lines) replacing the fence: keep the heading line 381 verbatim and the prose at 383; add: '"'"'Run `scripts/pr-base-changed-paths.sh <N>` (relative to this skill). It resolves the base via `gh api` on the pulls endpoint (`clone_url`/`ssh_url`), requires exactly one local remote matching the full host plus repo path, and prints `git diff --name-only ${BASE_REMOTE}/${BASE_BRANCH}...HEAD`.'"'"' Keep the 4-item allowlist (450-455) and the `/er: NOT REQUIRED — documentation-only (<changed paths>)` record text inline.
- Tests: in test_documented_base_resolution_works_without_origin_or_main and test_documented_base_resolution_rejects_same_repo_on_foreign_host, replace the `split("### Documentation-only `/er` exception")` + ```bash fence extraction with `script_path = REPO_ROOT/'"'"'.claude/skills/pr-lifecycle/scripts/pr-base-changed-paths.sh'"'"'` and run `["bash", str(script_path), "42"]` with the same fake-gh PATH and BASH_ENV neutralisation. Lines 187-191 string asserts stay unchanged.
- Constraints: stub must literally contain '"'"'gh api'"'"', '"'"'clone_url'"'"', '"'"'${BASE_REMOTE}/${BASE_BRANCH}...HEAD'"'"' (portability:188-190) and must NOT contain '"'"'origin/$BASE_BRANCH...HEAD'"'"', '"'"'origin/${BASE_BRANCH}...HEAD'"'"' or '"'"'origin/main...HEAD'"'"' (:191-193). Script must contain no home paths (portability scan).
- Non-goals: changing script behaviour.
- Forbidden paths: do not rename the heading; do not move the allowlist or record text.
- Policy: this edits an /er exemption rule; full draft route with independent adversarial /er review and /advice quorum required (pr-lifecycle L234).

Acceptance criteria:
- Tests: python -m pytest tests/test_skill_portability_scan.py tests/test_installer.py tests/test_coding_lifecycle_contract.py tests/test_approval_contracts.py.
- rg checks: rg -c '"'"'```bash'"'"' .claude/skills/pr-lifecycle/SKILL.md drops by 1; rg '"'"'origin/main\.\.\.HEAD|origin/\$'"'"' .claude/skills/pr-lifecycle returns nothing; `bash .claude/skills/pr-lifecycle/scripts/pr-base-changed-paths.sh 42` under the fake gh prints the expected diff.
- Line-count target: SKILL.md 607 -> ~551-553.
- Done when: script executable, both behavioural tests run the file, installer test confirms it ships in the prw profile.'
create b4 'Collapse pr-lifecycle Slow CI section to a pr-green-definition pointer' task 2 'Context:
- Repo: https://github.com/jleechanorg/jleechan-skills, HEAD 6662dff (== 65ecdda).
- File/line evidence: .claude/skills/pr-lifecycle/SKILL.md:585-599 ('"'"'## Slow CI — never block-wait'"'"'); pr-green-definition/SKILL.md:31-56, 99-109 own the No-CI exception, the `Gate 1: CI NOT APPLICABLE — <reason>` record format, the sleep-loop ban and the 10-minute local-equivalent rule. Quote: '"'"'Never replace this with `sleep N` + `gh pr checks`, and never call unrun CI passed.'"'"' Also pr-lifecycle:603 restates '"'"'optional advisory reviewers'"'"' twice and pr-green-definition:19 carries the same bold sentence.
- Why it matters: pr-lifecycle says '"'"'Apply the canonical pr-green-definition § No-CI exception'"'"' and then re-lists its contents; two owners drift.
- Staleness note: verified at 6662dff; re-read 585-607 and pr-green-definition 14-56 before editing.

Implementation:
- Files: .claude/skills/pr-lifecycle/SKILL.md:585-603; .claude/skills/pr-green-definition/SKILL.md:19.
- Replace 585-599 with (keep heading verbatim): '"'"'Documentation-only changes use the CI exception immediately; the ten-minute threshold applies only to changes that require CI.'"'"' + one line: CI that does not exist follows `../pr-green-definition/SKILL.md` § No-CI exception, including its evidence and the `Gate 1: CI NOT APPLICABLE — <reason>` record; never `sleep N` + `gh pr checks` polling, never call unrun CI passed. + one line: checks queued/pending more than 10 minutes follow the local-equivalent exception in pr-green-definition § Backlogged CI (run the workflow'"'"'s actual command, post current-head proof); failed checks, the no-conflict check and merge authorization are unchanged.
- 601-603: reduce to one sentence keeping the bold '"'"'**CodeRabbit/Bugbot: optional advisory reviewers**'"'"' phrase once.
- pr-green-definition:19: drop only the trailing '"'"'at any phase of the PR lifecycle'"'"'; keep :21 '"'"'`/green` alone is not merge authorization'"'"'.
- Constraints: keep the literal '"'"'local-equivalent exception'"'"' in the pointer (test_coding_lifecycle_contract.py:280; L295 also carries it but do not rely on that). Do not touch 375-379 (already a pointer) or 605-607 (only in-file merge-authorization pointer; keep '"'"'does not require or waive a human `MERGE APPROVED`'"'"').
- Non-goals: renaming the heading; editing pr-green-definition'"'"'s owner text beyond :19.
- Forbidden paths: no new '"'"' ## '"'"' inserted before this section that would alter the Review-records split (runs to EOF).
- Policy: edits a CI-evidence rule; full route with independent adversarial /er and /advice quorum (pr-lifecycle L234).

Acceptance criteria:
- Tests: python -m pytest tests/test_coding_lifecycle_contract.py tests/test_approval_contracts.py tests/test_cross_host_catalog.py.
- rg checks: rg -c '"'"'never block-wait'"'"' .claude/skills/pr-lifecycle/SKILL.md == 1; rg '"'"'local-equivalent exception'"'"' .claude/skills/pr-lifecycle/SKILL.md >= 2 hits; rg '"'"'CI NOT APPLICABLE'"'"' .claude/skills/pr-lifecycle/SKILL.md == 1.
- Line-count target: ~11-13 lines removed from pr-lifecycle, 0-1 from pr-green-definition.
- Done when: section is <= 5 lines and both tests pass.'
create b5 'Dedupe reviewer-timeout and /dot-fallback restatements in pr-lifecycle L78-90, L196-197' task 2 'Context:
- Repo: https://github.com/jleechanorg/jleechan-skills, HEAD 6662dff (== 65ecdda).
- File/line evidence: .claude/skills/pr-lifecycle/SKILL.md:65-103 ('"'"'### Reviewer timeout and completion'"'"', canonical 1800s limit, TIMED_OUT, /er + two /advice fallback) vs :196 (/wa line) and :197 (/dot paragraph), which each re-spell '"'"'apply the 1800-second default timeout contract above (or an explicit user-specified limit, whether shorter or longer, or a later specific user instruction to await a named reviewer)'"'"'. The fallback paragraph 78-90 ends in a chain of restated negatives ('"'"'without claiming the timed-out review happened'"'"', the /wa-specific sentence, '"'"'A timeout does not grant readiness or merge authorization'"'"', already covered by L37 and L196). Commit 2c03315 (600s -> 1800s) had to edit three places.
- Why it matters: three copies of the override clause drift on every timeout tweak; verification confirmed the saving is modest (~6-8 lines) but the maintenance risk is real.
- Staleness note: verified at 6662dff; re-read 65-103 and 191-200 before editing.

Implementation:
- Files: .claude/skills/pr-lifecycle/SKILL.md:78-90, 196, 197.
- L78-90: keep scope clause (/dot, requested /wa, other non-/advice reviewers), '"'"'recorded as `TIMED_OUT`, with request and timeout times and any partial receipt or findings; it is never recorded as PASS'"'"', '"'"'discharged at timeout'"'"', the '"'"'/er on the finished evidence plus /advice approval from two independent reviewers at the same head'"'"' fallback, '"'"'mandatory for this substitution only; it does not change the general under-50 advice threshold'"'"', '"'"'remain open until proved by applicable evidence or an eligible replacement review'"'"', and '"'"'Preserve and assess late substantive findings ... can reopen the gate'"'"'. Delete only: '"'"'The fallback advances reviewer coverage without claiming the timed-out review happened.'"'"', the /wa-specific sentence (86-87, covered at 196), and '"'"'A timeout does not grant readiness or merge authorization.'"'"' (89-90, covered by L37 and § Precedence and scope — confirm before deleting).
- L196 and L197: replace each three-part parenthetical with '"'"'per § Reviewer timeout and completion (including its user-override clauses)'"'"'. Keep at 197: '"'"'to each account, including queue and send wait'"'"', the busy trigger, '"'"'next configured Dot'"'"' rotation, the late-verdict-does-not-count rule, the `/dot busy: /er + /advice substituted` record string with accounts/times/outcomes, the receipt field list, '"'"'disclosed, not invented approval'"'"', and the standing-authorization clause. At 196 keep '"'"'Do not claim browser-only validation occurred'"'"' once (it is the /wa-specific statement after the 86-87 deletion).
- Constraints: keep H3 heading text verbatim and under '"'"'## Advice applicability'"'"' (section split test_coding_lifecycle_contract.py:235-238); keep literal `TIMED_OUT`; do not touch 93-103 or 105-116; keep L194 verbatim (:33 pin '"'"'small PRs need /advice OR independent /dot approval'"'"'); no table/bullet restructuring of 193-197.
- Non-goals: moving the timeout section to advice or references (killed).
- Forbidden paths: anchors #reviewer-timeout-and-completion (pr-workflow-manager:19) and #review-routes-for-opted-in-repositories (ready:10; manager:120; test :409).
- Policy: edits reviewer-fallback rules; full route with independent adversarial /er and /advice quorum (pr-lifecycle L234).

Acceptance criteria:
- Tests: python -m pytest tests/test_coding_lifecycle_contract.py tests/test_approval_contracts.py.
- rg checks: rg -c '"'"'whether shorter or longer'"'"' .claude/skills/pr-lifecycle/SKILL.md == 1 (only in the canonical section); rg -c '"'"'TIMED_OUT'"'"' >= 1; rg -c '"'"'/dot busy: /er \+ /advice substituted'"'"' == 1.
- Line-count target: ~6-8 lines (~250-350 words) removed.
- Done when: the override clause exists once and 196/197 point to it.'
create b6 'Micro-dedupe pass over pr-lifecycle: precedence, merge-authority tail, advice threshold, batch-fixes, fast-path carve-outs' task 2 'Context:
- Repo: https://github.com/jleechanorg/jleechan-skills, HEAD 6662dff (== 65ecdda).
- Finding: five small, independently verified intra-file redundancies, each worth 1-4 lines, bundled into one PR because none justifies its own policy review cycle:
  a. L10/L12/L16 restate '"'"'local contract governs'"'"'. Quote L12: '"'"'Inspect the target repository'"'"'s instructions first; an explicit local contract governs its workflow.'"'"'
  b. L545 carries the only exact-head / no-inferred-automatic-merge sentences, separate from § Merge authorization (605-607); L461 ends '"'"'and separate merge authorization'"'"'. Quote: '"'"'READY never supplies merge authorization. Earlier-SHA review applicability for readiness does not satisfy a stricter exact-head condition on any separately authorized automatic-merge route.'"'"'
  c. L193 redefines small/large (already defined at 48-54 + 105-112); L63 tail and L82-85 tail re-say '"'"'does not change the under-50 threshold'"'"'.
  d. '"'"'Batch fixes before expensive evidence'"'"' at L272-273, L295, L318-319, L522-523 all restate the draft-phase preamble L323-338.
  e. One-liner fast-path receipt carve-outs at L221, L551, L558, L565-566 restate L249-256; L40 '"'"'Each arrow is a gate, not a formality. Do not skip ahead.'"'"' is rationale.
- Why it matters: individually trivial, collectively ~10-14 lines and the main source of drift when any of these rules is patched.
- Staleness note: verified at 6662dff; re-read each range before editing.

Implementation (files: .claude/skills/pr-lifecycle/SKILL.md only):
- a. L12: delete only '"'"'Inspect the target repository'"'"'s instructions first; an explicit local contract governs its workflow.'"'"' L10: delete only '"'"'Explicit repository requirements govern their domain; this contract supplies defaults only where local instructions are silent.'"'"' Keep in L10 '"'"'Do not infer an opt-out from a repository'"'"'s name or apparent purpose'"'"' (or merge '"'"'or apparent purpose'"'"' into L16), the '"'"'Design documents explain rationale'"'"' sentence and the pr-workflow-manager sync note. Keep L12'"'"'s '"'"'gh pr create --draft'"'"' / '"'"'stays draft until quality is proven'"'"' / gated-action sentences.
- b. Move L545'"'"'s exact-head and no-inferred-automatic-merge sentences verbatim into L607; shorten L545 to '"'"'READY never supplies merge authorization (§ Merge authorization).'"'"' Drop '"'"', and separate merge authorization'"'"' at L461 only if the ordered-token pin at test_coding_lifecycle_contract.py:259 ('"'"'separate merge authorization'"'"' in the lifecycle diagram slice 22-41) is unaffected — it reads L22-41, not L461. KEEP L16, L37, L200, L255 (preserve '"'"'an explicit user request for proof still applies'"'"'), L379.
- c. L193: replace the definition with '"'"'small/large per § Advice applicability'"'"' keeping the '"'"'(or an incomplete/uncountable diff)'"'"' qualifier and the trivial-change sentence; L63: shorten the tail clause; L82-85: keep '"'"'mandatory for this substitution only'"'"' (coordinate with the timeout bead). Do not move L105-112.
- d. L295: remove only '"'"'and batch fixes before paid capture'"'"' (keep '"'"'relevant code and checks have stabilized'"'"', '"'"'Do not wait for green to diagnose a failed test'"'"', '"'"'local-equivalent exception'"'"' — :277-280 pins). L318-319: replace with a one-line pointer to the draft-phase section. L522: delete only '"'"'Batch related fixes before expensive proof, and'"'"'. Keep L272-273 '"'"'preserve passing lanes'"'"'. Keep headings at 308 and 321.
- e. L558: delete the Evidence-marker parenthetical (L256 says it verbatim). L551/L565-566: shrink to '"'"'(see § Proportional exceptions and fast paths)'"'"'. L221: shorten to '"'"'except the one-liner fast path (see §)'"'"'. L40: delete '"'"'Each arrow is a gate, not a formality. Do not skip ahead.'"'"' only if the ordered-token test :259 still passes (it slices 22-41; the sentence contains no pinned token). Keep '"'"'**Evidence**: <gist-url> (head <sha>)'"'"' at 559 (:383). Update evidence-standards/SKILL.md:372 only if it quotes the L221 clause.
- Constraints: no heading changes; no edits inside 22-39, 46-62, 105-116, 138-145, 160-167; keep '"'"'Mandatory regardless of class'"'"'/'"'"'Skippable by class'"'"' once.
- Non-goals: SHA-binding, PUBLICATION BLOCKED, never-fabricate dedupes (killed).
- Policy: edits approval/merge/evidence policy; full route with independent adversarial /er and /advice quorum (pr-lifecycle L234).

Acceptance criteria:
- Tests: python -m pytest tests/test_coding_lifecycle_contract.py tests/test_approval_contracts.py tests/test_skill_portability_scan.py.
- rg checks: rg -c '"'"'an explicit local contract governs its workflow'"'"' == 0; rg -c '"'"'stricter exact-head condition'"'"' == 1 (now in § Merge authorization); rg -c '"'"'batch fixes before paid capture'"'"' == 0; rg -c '"'"'under 50 complete-diff'"'"' == 0 at L193; rg '"'"'every PR under 50 changed lines'"'"' still present.
- Line-count target: 10-14 lines removed.
- Done when: all five sub-edits applied and tests green.'
create b7 'Trim sibling restatements: evidence-review:175 visual pointer, pr-workflow-manager preface/activation/stage block, pr-workflow alias' task 2 'Context:
- Repo: https://github.com/jleechanorg/jleechan-skills, HEAD 6662dff (== 65ecdda).
- File/line evidence:
  a. .claude/skills/evidence-review/SKILL.md:175 ('"'"'**Mandatory AI Visual Inspection (`VISUAL APPROVED at <40-char-sha>`):** ...'"'"') restates pr-lifecycle:198 nearly verbatim; pr-lifecycle:198 is the owner.
  b. .claude/skills/pr-workflow-manager/SKILL.md:28-29 '"'"'Keep these two skills in sync ... Link to the contract instead of copying its rules.'"'"' duplicates pr-lifecycle L10/L214 and draft-first-pr L12; :52-55 '"'"'Activation cues'"'"' duplicates the frontmatter description; :118-124 paraphrases the visual-approval contract ('"'"'including independent reviewers, claim-by-claim before/after findings, artifact links, ...'"'"'); :141-143 '"'"'Stage evidence publication'"'"' is a one-sentence link already implied by :113.
  c. .claude/skills/pr-workflow/SKILL.md:10 sends readers to pr-workflow-manager first, while prw/SKILL.md:10 sends them to pr-lifecycle first; the two are the same command (pr-lifecycle L231 '"'"'/prw (/pr-workflow)'"'"').
- Why it matters: the manager claims to '"'"'link instead of copying'"'"' but copies; aliases that diverge in read order can diverge in behaviour.
- Staleness note: verified at 6662dff; re-read before editing.

Implementation:
- a. evidence-review:175 -> a 3-4 line pointer to ../pr-lifecycle/SKILL.md#review-routes-for-opted-in-repositories keeping the /er-lane obligation (download and inspect actual rendered frames; record VISUAL APPROVED/REJECTED; PARTIAL cap behaviour) and the literals '"'"'VISUAL APPROVED at <40-char-sha>'"'"', '"'"'`/dot: REQUESTED, pending`'"'"' and '"'"'stage:5-final-approval'"'"' (test_coding_lifecycle_contract.py:419-424 pins all three in evidence-review).
- b. manager: delete :28-29 only (keep :30 '"'"'Preserve repository-specific evidence...'"'"' and :19-22 timeout guard '"'"'do not add a separate timer or treat a timeout as approval'"'"'); fold :52-55 '"'"'Use for ...'"'"' sentence into the intro and keep the :57 /prw continuation link; in :118-124 drop the '"'"'including independent reviewers, claim-by-claim before/after findings, artifact links,'"'"' clause but keep one sentence containing the three pinned literals and the links to #review-routes-for-opted-in-repositories, #draft-phase-final-acceptance-gates-in-order, #proportional-exceptions-and-fast-paths; fold :141-143 into :113 (heading not linked anywhere). KEEP :116-117 '"'"'Waiting/blocked is not Working. Do not call a PR ready from badges, skipped tests, an assignment or a pending review.'"'"' (pr-lifecycle does not contain it). Do not touch '"'"'## Retained review integrations'"'"' :59-65 (test_cross_host_catalog.py:257-262 pins the heading, '"'"'For a remote invocation, check'"'"', '"'"'UNAVAILABLE'"'"', '"'"'leave any dependent readiness or plan-approval gate unmet'"'"' in the manager) and keep at least one `/advice` or `advice/SKILL` reference (checked-set count 17 at :264-266).
- c. pr-workflow:10-12: copy the prw body (read pr-lifecycle first; '"'"'defines no independent rules'"'"'; arguments are data; report missing dependency) and keep the manager + draft-first-pr secondary links. Optionally add a test next to test_coding_lifecycle_contract.py:44-52 asserting prw and pr-workflow both contain '"'"'../pr-lifecycle/SKILL.md'"'"' and '"'"'defines no independent rules'"'"'.
- Constraints: manager must still contain '"'"'../pr-lifecycle/SKILL.md'"'"' (:52) and anchors #default-pr-route--prw (:443), #review-routes..., #draft-phase... (:409-410).
- Non-goals: collapsing aliases into one file; trimming manager '"'"'Find the skills'"'"' (killed).
- Policy: edits review/evidence policy text; full route with independent adversarial /er and /advice quorum.

Acceptance criteria:
- Tests: python -m pytest tests/test_coding_lifecycle_contract.py tests/test_approval_contracts.py tests/test_cross_host_catalog.py tests/test_installer.py.
- rg checks: rg -c '"'"'VISUAL APPROVED at <40-char-sha>'"'"' on each of pr-lifecycle, evidence-review, pr-workflow-manager >= 1; rg -c '"'"'Keep these two skills in sync'"'"' .claude/skills/pr-workflow-manager/SKILL.md == 0; rg '"'"'pr-lifecycle/SKILL.md'"'"' .claude/skills/pr-workflow/SKILL.md present.
- Line-count target: evidence-review -5..-8 (word-level, line 175 is one long line), manager -10..-14, pr-workflow 0.
- Done when: all three files edited, tests green, prw and pr-workflow bodies name pr-lifecycle as read-first.'
create b8 'Compact ready/SKILL.md item 3 by deferring quorum rules to advice/SKILL.md' task 3 'Context:
- Repo: https://github.com/jleechanorg/jleechan-skills, HEAD 6662dff (== 65ecdda).
- File/line evidence: .claude/skills/ready/SKILL.md:30-37 (item 3 '"'"'**/advice**'"'"'). Quote: '"'"'Research and the orchestrating agent do not vote. One approval can block but cannot approve; unavailable or partial-coverage reviewers do not satisfy the approval quorum.'"'"' These voter/blocking rules are owned by advice/SKILL.md; item 2 (:23-29) restates the pr-lifecycle SHA-binding reaffirmation.
- Why it matters: ready'"'"'s own '"'"'Stage evidence publication'"'"' section (:46-50) correctly defers by link; items 2-3 do not, so quorum wording can drift from advice.
- Staleness note: verified at 6662dff; re-read ready:20-40 and advice/SKILL.md quorum section before editing, and confirm advice states the voter rules identically before dropping them.

Implementation:
- Files: .claude/skills/ready/SKILL.md:23-37.
- Item 2: keep '"'"'RED-first'"'"', '"'"'may instead be reaffirmed at the new SHA'"'"' (test_coding_lifecycle_contract.py:87), '"'"'actual delta'"'"' (:99), '"'"'changed assertion/driver requires a fresh run'"'"' (:110); shorten the middle by pointing to pr-lifecycle'"'"'s SHA-binding rule. Do not collapse to one line.
- Item 3: reduce to ~3 lines: keep bold '"'"'**/advice**'"'"' (test_approval_contracts.py:345), '"'"'when `pr-lifecycle` § Advice applicability requires it'"'"', '"'"'at least two independent full-coverage approval reviewers from the canonical `advice/SKILL.md` approval lanes'"'"', the REQUEST_CHANGES resolution sentence, '"'"'The same delta-based reaffirmation applies here'"'"' (:127) and '"'"'never reduces the two-reviewer quorum'"'"' (:128) plus the named-reviewer guard and '"'"'needs its own separate, explicitly approved change'"'"'. Drop only '"'"'Research and the orchestrating agent do not vote. One approval can block but cannot approve; unavailable or partial-coverage reviewers do not satisfy the approval quorum.'"'"' after verifying advice/SKILL.md states each.
- Constraints: also keep '"'"'final `/er`'"'"' and '"'"'final `/advice`'"'"' (:264-265) and '"'"'current `**Evidence**` marker'"'"' (:388) wherever they live in ready.
- Non-goals: repointing test pins to pr-lifecycle (would require a larger bead).
- Forbidden paths: anchors #ready-phase--finish-ready-then-final-reviews, #review-records-in-the-pr-description at :46 unchanged.
- Policy: edits approval-quorum text; full route with independent adversarial /er and /advice quorum (pr-lifecycle L234); ready:36-37 itself says changing the named-reviewer requirement needs its own explicitly approved change, so the PR must state it changes wording only.

Acceptance criteria:
- Tests: python -m pytest tests/test_coding_lifecycle_contract.py tests/test_approval_contracts.py.
- rg checks: rg -c '"'"'never reduces the two-reviewer quorum'"'"' .claude/skills/ready/SKILL.md == 1; rg '"'"'do not vote'"'"' .claude/skills/advice/SKILL.md present (ownership confirmed).
- Line-count target: ready 50 -> ~44-45.
- Done when: item 3 <= 4 lines, item 2 shortened, tests green.'
create b9 'Optional: move six-stage reference prose and gate-4 detail to pr-lifecycle/references/ with test-helper update' task 3 'Context:
- Repo: https://github.com/jleechanorg/jleechan-skills, HEAD 6662dff (== 65ecdda).
- File/line evidence: .claude/skills/pr-lifecycle/SKILL.md:123-136 '"'"'Specification and artifact'"'"', :170-178 hold-label paragraph, :204-217 '"'"'Regression and synchronization'"'"' (all under '"'"'## Visible six-stage workflow (repository opt-in)'"'"', which applies only to opted-in repositories yet loads for every PR), and :353-373 draft gate 4 '"'"'**`/visual-verification`**'"'"' (21-line single list item: applicability, seat independence, forbidden substitutes, two-seat rule, SINGLE-SEAT, cross-repo deferred debt, byte-identical caveat). Quote: '"'"'Deferred debt does **not** discharge this gate and never authorises undraft'"'"'.
- Why it matters: ~45-60 lines of opt-in or visual-only detail sit in the every-PR path; this is the only remaining large structural win but needs test and installer changes, so it is last and optional.
- Installer: install-claude-commands.sh list_installable_files() copies all files under skills/<name>/ (other skills already ship references/, e.g. plan-micro, cmux-steer), so references/ ships with the prw profile; verify with tests/test_installer.py.
- Staleness note: verified at 6662dff; do a full phrase audit of every test calling read('"'"'pr-lifecycle'"'"') before moving.

Implementation:
- Files: new .claude/skills/pr-lifecycle/references/six-stage-workflow.md and references/visual-gates.md; SKILL.md ranges above; tests/test_coding_lifecycle_contract.py (read() helper :12-14 and direct owner = read("pr-lifecycle") calls at :55,165,171,202,209); tests/test_approval_contracts.py:219 if affected.
- Move verbatim: 123-136, 170-178, 204-217 -> six-stage-workflow.md, replacing each with a 2-3 line pointer and adding under the opt-in H2: '"'"'When the repository opts in, read references/six-stage-workflow.md; it is mandatory.'"'"' KEEP in SKILL.md: State readback 138-145 (general rule; pinned), title rules 152-158 incl. '"'"'the stage suffix goes last'"'"', stage table 160-167 (six rows pinned as exact whitespace-collapsed strings), the `## PR Stage` placement rule, L194/L197 /dot sentences, L198 Mandatory AI Visual Approval Gate (keep as its own rule; do not merge with gate 4), headings '"'"'Review routes for opted-in repositories'"'"' and '"'"'Evidence attached to every stage exit'"'"' with bodies. Keep the Stage 0 sentences '"'"'A commit on a branch with no PR is not a Stage 0 artifact'"'"' and '"'"'an open PR at the prescribed location'"'"' and '"'"'seven-element specification in the PR body for small changes'"'"' in SKILL.md or extend tests to read the reference.
- Gate 4: move the detail to visual-gates.md and keep item 4 in the numbered list as a 4-5 line stub stating: trigger (publishes media OR claims rendered/interaction/displayed-data effect; not source-literal-only incl. one-liner fast path); seat independent of author and /er seat, PASS required, author-side reading never substitutes; own Review Gate Ledger row, media without a row blocks undraft; two seats for a user-visible headline claim else recorded `SINGLE-SEAT`; deferred debt never authorises undraft; '"'"'every applicable seat must PASS; missing/inaccessible/insufficient media leaves the gate open'"'"'; byte-identical-prose caveat and bounded N/A reason; link '"'"'[details](references/visual-gates.md)'"'"'. Keep item number 4 and the name `/visual-verification` (refs at L31, 225, 255).
- Tests: change read() (or self.owner) to concatenate SKILL.md + references/*.md for the pinned-phrase tests, OR keep every pinned phrase in the stubs; add a test asserting both reference files exist and contain the moved phrases (SINGLE-SEAT, deferred debt, source-literal-only, regression mapping).
- Constraints: headings/anchors unchanged (#stage-title-and-labels, #review-routes-for-opted-in-repositories, #evidence-attached-to-every-stage-exit, #draft-phase-final-acceptance-gates-in-order); no new '"'"' ## '"'"' inside pinned splits; references files must pass the portability scan.
- Non-goals: moving Review records, Change-impact, Proportional exceptions or Reviewer timeout to references (killed).
- Policy: edits stage/visual gate rules; full route with independent adversarial /er and /advice quorum (pr-lifecycle L234).

Acceptance criteria:
- Tests: full suite python -m pytest tests/ green; test_installer prw profile confirms references/ files are installed.
- rg checks: rg -o '"'"'pr-lifecycle/SKILL.md#[a-z0-9-]+'"'"' .claude/skills | sort -u unchanged vs. before; rg -c '"'"'SINGLE-SEAT'"'"' across SKILL.md + references >= 1.
- Line-count target: SKILL.md -40..-50 (six-stage) and -10..-15 (gate 4).
- Done when: references files exist, stubs preserve every blocking rule listed above, tests updated and green.'

# Dependencies (child depends on prerequisite); epic parent link where supported.
link() { (( DRY_RUN )) && { echo "[dry-run] br dep add ${IDS[$1]} ${IDS[$2]}"; return; }; "${BR[@]}" dep add "${IDS[$1]}" "${IDS[$2]}" 2>/dev/null || echo "note: could not link ${IDS[$1]} -> ${IDS[$2]} (check br dep syntax for your version)"; }
link b3 b2
link b4 b2
link b5 b2
link b6 b2
link b6 b5
link b7 b2
link b8 b2
link b9 b2
link b9 b3
link b9 b6
echo "Created: ${IDS[*]}"; (( DRY_RUN )) || "${BR[@]}" sync || true
