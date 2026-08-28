---
name: design-retro-publishability-gate
description: Final whole-docset publishability gate for design-retro / adversarial-doc swarm workflows. Use as the LAST stage of any design-retro, solutions-hardening, /innov, pr-retro, or code-quality-swarm run, after all writer/verifier lanes finish and before the PR description claims the docset is "ready" or "publishable". Catches cross-document contradictions, present-tense staleness vs current HEAD, leaked machine paths/tokens, unmarked superseded docs, false-green copyable commands, and git diff --check hygiene issues that per-finding adversarial review structurally cannot see.
type: skill
scope: repo
owner: $USER
version: 1.0.0
triggers:
  - "publishability gate"
  - "final design-retro check"
  - "is this docset publishable"
  - "whole-docset review before publishing"
  - "synthesize-report final check"
allowed-tools:
  - Bash
  - Read
  - Grep
context:
  - "Root cause: PR https://github.com/$GITHUB_REPOSITORY/pull/8191 ran ~180 adversarial agents across design-retro, solutions-hardening, innov, pr-retro, and code-quality lanes, validating/refuting candidate FINDINGS, but never re-read the assembled markdown as a single publishable artifact. A cold review found six defect classes still present in already-'confirmed' docs. Full writeup: docs/design-retro-2026-06-adversarial-gaps.md (this repo). This SKILL.md is the fix (bead rev-qj6qb)."
  - "This mirrors and operationalizes ~/.claude/skills/swarm/SKILL.md rule 11 ('Publishability gate') for THIS repo. If that user-scope rule's wording changes, re-sync the checklist below rather than let them drift."
  - "This is a planning/process gate, not application code. Nothing here does keyword/regex SEMANTIC judgment (contradiction detection, staleness detection, supersession detection) in a script — those three items are LLM-judgment checklist items by design, per this repo's ZFC principle (CLAUDE.md 'Zero-Framework Cognition'). The companion script only does mechanical, non-semantic checks: secret-shape pattern matching, shell syntax validation, and git's own diff --check."
---

# Design-Retro Publishability Gate

## When to use this skill

Run this gate exactly once, as the final stage, in any workflow that:

- fans out multiple writer agents across sibling docs (design-retro, solutions-hardening, `/innov`, pr-retro, code-quality swarms), and
- uses single-file write locks per agent (so no single agent ever held the whole docset in context), and
- is about to have its PR description say the docset is "ready", "publishable", or "final".

Do **not** substitute this for per-finding adversarial verification (evidence/severity/design lenses). This gate assumes those already ran. It exists because per-finding verification structurally cannot see problems that only exist at the whole-docset level (contradictions between docs, stale corrections, leaked paths, unmarked superseded plans).

## Why per-finding review misses this (do not re-derive this — it is proven)

From `docs/design-retro-2026-06-adversarial-gaps.md` §2, six structural reasons, condensed:

1. Verifiers ran on candidate findings *before* doc writers wrote the rendered markdown — nothing ever re-read the shipped prose.
2. Single-file write locks (needed for parallel-safety) guaranteed no agent ever held two docs in context, so cross-doc contradictions were invisible by construction.
3. Corrections landed only in the doc that produced them; the top-level report (written earlier, by a different agent) was never reopened.
4. No freshness re-baseline: docs were checked against one HEAD; later commits changed ground truth; present-tense claims went stale silently.
5. Policy compliance (ZFC / ZFC-leveling / credential-discipline / regex bans) was never a review lens — a recommendation can be evidentially true and still be forbidden.
6. The one lane structurally positioned to catch all of this (`synthesize-report`) failed on provider overload in the original PR #8191 run and was finished by hand, without gate checks.

## The checklist (run in this order)

Run the automated subset first (cheap, deterministic); only spend LLM judgment on the items that need it.

### Automated (companion script — run first)

```bash
scripts/check_design_retro_publishability.sh <doc1.md> [doc2.md ...]
```

| # | Check | What it does | Exit signal |
|---|-------|---------------|--------------|
| 3 | **Redaction sweep** | Greps every doc for machine-path and token-shape patterns (`/Users/<name>`, `ghp_`/`gho_`/`github_pat_`, `x-access-token`, `serviceAccountKey.json`, AWS/`sk-` key shapes). Fixed pattern list, not a semantic classifier. | FAIL line + matched line numbers |
| 5 | **Copyable command syntax validity** | Extracts every fenced ` ```bash `/` ```sh `/` ```shell ` block and runs `bash -n` (syntax-only, no execution) | FAIL line + parser error |
| 6 | **Mechanical hygiene** | `git diff --check <base> -- <files>` — trailing whitespace, conflict markers | FAIL line + diff |

This is intentionally the automatable third of the checklist. It does **not** run any command in the docs, and it does not judge whether a command's *expected outcome* is correct (see item 5 below, which stays manual) — it only proves the shell syntax parses.

### LLM-judgment (semantic — do these by hand, one pass over the WHOLE docset in context)

1. **Cross-document consistency.** Every numeric claim in a top-level/summary doc must match its per-finding source doc. Read all sibling docs in the SAME context window (this is the one step single-file write locks structurally prevented during authoring) and diff every repeated number/claim. Any disagreement blocks publication until one doc is corrected and the other explicitly cites it. Real example this caught: PR #8191's top-level report repeated an "89%" unprefixed-commit figure after `05-process...md` had already corrected it to "~14-36%".
2. **Current-head freshness re-baseline.** Re-check every present-tense claim ("X is missing", "Y has not shipped") against the PR's *current* head SHA, not the SHA the doc was originally verified against. Historical evidence that is still true only "at the time of writing" must be re-worded as "at base `<sha>`". Real example: later branch commits (`.beads` dedupe, `rev-18xst` priority/remediation) changed current state while docs stayed present-tense stale.
3. **Superseded-doc markers.** Every finding must have exactly one authoritative doc. If a brainstorm/plan track was overtaken by a later, more-detailed design doc, the earlier one needs an explicit banner pointing to the authoritative doc — silence is a defect, not an acceptable draft state. Real example: PR #8191 had contradicting route counts (3 vs "3 of ~8" vs "8 inline + ~15 additional") across three docs, none marked superseded.
4. **Policy lens.** Check every recommendation against repo-specific hard law that the evidence/severity/design lenses never covered: ZFC / ZFC-leveling file boundaries (`.claude/skills/zfc-leveling-roadmap/SKILL.md`), credential-discipline (`.claude/skills/credential-discipline` / `~/.claude/skills/credential-discipline/SKILL.md`), no-unapproved-regex-on-LLM-output (CLAUDE.md). A recommendation can be evidentially true, severe, and well-designed, and still be forbidden — e.g. PR #8191 plan docs proposed registering a backend XP-threshold fallback the ZFC-leveling contract explicitly forbids.
5. **Copyable-command *expected-outcome* validity.** Beyond syntax (automated above): does the acceptance criterion for each command state the CORRECT expected color? A negative/regression test should assert red, not green. Real example: PR #8191's `06-level-up...md:169` acceptance step asserted the gate CI job goes *green* on a PR that intentionally reintroduces the violation — the correct expectation is red.

## After the gate

- If the automated script FAILs: fix the doc, re-run the script on just the changed file(s), do not re-run the whole LLM pass unless the fix could have introduced a new cross-doc contradiction.
- If any LLM-judgment item finds a defect: open (or reuse) a bead citing the exact doc:line, fix in-branch, and re-run item 1 (cross-doc consistency) once more before calling the docset done — a fix to one doc is itself a new opportunity for the sibling docs to go stale.
- Only after both halves pass: the PR description may say the docset is publishable. Cite this gate (`.claude/skills/design-retro-publishability-gate/SKILL.md`) and its result in the PR's evidence section.

## Non-goals / what this skill deliberately does NOT do

- It does not replace per-finding adversarial verification (evidence/severity/design lenses) — it runs strictly after them.
- It does not implement contradiction/staleness/supersession detection as regex or keyword matching in the script. Those are inherently semantic judgments (per this repo's Zero-Framework Cognition principle) and stay as an LLM checklist, not application logic.
- It does not execute any command found in the docs — the syntax check is `bash -n` only, never a live run.
