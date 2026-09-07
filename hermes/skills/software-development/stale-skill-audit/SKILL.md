---
name: stale-skill-audit
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
description: "Audit an existing SKILL.md for stale content and produce a safe-subset cleanup PR — drop dead Provenance footers, swap drifted canonical names (bd→br), normalize header dates, never rewrite content. Use when the user says 'cleanup this skill', 'this skill is bloated', names a specific skill that drifted, or a scheduled `agent-agent-mistakes` review flagged a file. Triggers: 'cleanup this skill', 'prune this skill', 'this skill is bloated', 'audit stale skill content', 'normalize dates in SKILL.md', 'swap bd to br', 'safe subset cleanup'."
metadata:
  hermes:
    tags: [skills, audit, cleanup, maintenance, staleness, sediment]
    related_skills: [hermes-agent-skill-authoring, skillify, simplify-code, session-learn-distill, harness-postmortem]
---

# Stale-Skill Audit — Safe-Subset Cleanup for an Existing SKILL.md

Skills accumulate **sediment**: dead Provenance footers, drifted CLI names, header dates that pin to a specific moment in time, WIP-forward language, and content-meaning edits that no longer pull their weight. This skill is the recipe for a single PR that removes the sediment **without rewriting the skill**.

**Default philosophy: safe subset only.** No paragraph removal, no rule reordering, no content-meaning edits. Drop dead audit data, swap drifted names, normalize header dates. Stop there unless the user explicitly escalates.

## When to Use

- User says "cleanup this skill" / "prune this skill" / "this skill is bloated" / "audit stale skill content".
- User names a specific SKILL.md that drifted from current org conventions.
- A scheduled `agent-agent-mistakes` or `meta-autonomy-violation-handler` review flagged a file.
- The org changed canonical CLIs, paths, or defaults and a skill still references the old ones (e.g. `bd` → `br`).
- The skill's description is approaching 1024 chars (validator forces a rewrite — may as well clean the body too).

**Do NOT use this** for:
- Proactive "this looks old" cleanup without a signal. Unsolicited cleanup PRs don't merge.
- *Creating* a new skill (use `skillify`).
- *Simplifying code* (use `simplify-code` — that one is for code, not docs).
- Promoting local user-scope additions to the repo (separate "promote to repo" PR, not a cleanup PR).

## Quick Start

1. **Find the canonical file.** Check both `~/.claude/skills/<name>/SKILL.md` (user-scope local) and the repo's `.claude/skills/<name>/SKILL.md` (remote canonical). They often drift.
2. **Run the indicator greps** (see `references/staleness-audit.md`). Each hit is a candidate edit.
3. **Classify each hit:**
   - Header/frame (description, lead-in, table title): normalize or drop.
   - Incident-anchored (mid-rule, with a specific defect class or example): keep verbatim — it's load-bearing evidence.
   - Provenance/audit footer: drop the whole section.
4. **Apply minimal patches** with `patch` (or `skill_manage` action='patch' for in-repo skills). `replace_all=true` only when every occurrence is unambiguously the same edit (e.g. `bd` → `br`).
5. **Edit local first** (`~/.claude/skills/<name>/SKILL.md`) — user's local sessions read it.
6. **Propagate to remote** via `github-pr-workflow` (branch from `origin/main`, commit, push, `gh pr create`). Do NOT include user-scope local additions — those are content additions, not cleanups.
7. **Verify:** `gh pr view N --json headRefOid --jq .headRefOid` matches local SHA; indicator greps on the remote head return 0 hits for `bd`, `Provenance` header, and unnormalized `2026-07-06` header dates.

The full recipe (exact grep commands, classification rules, foreign-checkout pitfall, and the safe-subset edge cases) is in `references/staleness-audit.md`.

## The Safe-Subset Contract

| Edit | In safe subset? | Why |
|---|---|---|
| Drop `## Provenance` footer (dead runIds, bead IDs, SHA, PR URL) | ✓ | LLM has no way to resolve dead audit data |
| `bd` → `br` when org migrated | ✓ | Drift fix; org-canonical CLI |
| Header date `2026-07-06` → `2026-07` (description, lead-in, table cells) | ✓ | Header dates are pinpoints, not evidence |
| Incident-anchored date inside a rule body | ✗ keep verbatim | The date is evidence the rule is battle-tested |
| Typo that changes meaning ("province" → "provenance") | ✓ | Mechanical fix |
| WIP-forward language ("in progress as of ...", "TODO: ", "TBD") | ✓ | Ages badly; replace with current-state wording or drop |
| Removing a paragraph | ✗ escalate | Content-meaning edit — ask user first |
| Reordering rules | ✗ escalate | Content-meaning edit |
| Promoting a user-scope local addition to the repo | ✗ separate PR | That's a content-addition PR, not a cleanup PR |

## Pitfalls

1. **"Medium cleanup" is not the default.** When the user says "let's cleanup", assume safe subset unless they explicitly escalate. Offer 2-3 scope options at most — don't make them pick from 4. If they pull back mid-conversation, narrow immediately, don't re-confirm.
2. **Header dates ≠ incident dates.** Stripping `2026-07-07` from a rule that says "Hit twice on 2026-07-07: `pr-retro-gapfill` (15/15 verify agents died, ...)" removes the *evidence the rule is battle-tested*. That date is load-bearing. Header/frame dates are safe to normalize.
3. **`bd` → `br` is not always safe.** Confirm against `~/.claude/CLAUDE.md` and `projects/AGENTS.md` before sweeping. Some projects genuinely still use `bd`.
4. **Don't edit a foreign repo's live checkout in place.** It may be on someone else's branch with dirty work. Clone into `~/.hermes/state/worktrees/<repo>` and work from there; no approval phrase is required to change directories.
5. **Don't conflate local and remote.** The user-scope file at `~/.claude/skills/<name>/SKILL.md` may have *more* recent additions than the remote (Domain-general paragraphs, new rules added locally). Treat the remote as canonical for the cleanup PR; flag the local additions in the PR description under "Out of scope" so the user can promote them separately.
6. **`git rev-parse origin/<branch>` lies after a fresh push.** The local ref-cache doesn't update immediately. Verify with `gh pr view N --json headRefOid` instead, or `git fetch origin <branch>` first.
7. **Don't auto-run a sweep of every skill.** The user knows what's stale to them. A single targeted cleanup PR is welcome; a "I cleaned 14 skills at once" PR is not.

## Verification Checklist

- [ ] Local user-scope file (`~/.claude/skills/<name>/SKILL.md`) edited first
- [ ] Each `references/staleness-audit.md` indicator grep run against both local and remote files
- [ ] Each hit classified as header-frame / incident-anchored / provenance-audit / typo
- [ ] No content-meaning edits in the PR (paragraph removal, rule reordering, content additions)
- [ ] Local additions flagged in PR description under "Out of scope" if they exist
- [ ] Branch created from `origin/main` (per `pr-branch-from-main.mdc`)
- [ ] PR created via `gh pr create` with full description (What changed, why, out of scope, stats)
- [ ] `gh pr view N --json headRefOid` matches local HEAD SHA
- [ ] Indicator greps on the remote head return 0 hits for `bd`, `Provenance` header, and unnormalized `2026-07-06` header dates
- [ ] CodeRabbit / CI pre-checks all pass

## Related

- `hermes-agent-skill-authoring` — peer skill on authoring conventions; this skill is its **maintenance** counterpart.
- `skillify` — the 11-item completeness contract for *creating* new skills. Use when adding a new skill; use this one when pruning an old one.
- `simplify-code` — parallel 3-agent cleanup of recent code changes. Code, not skills.
- `session-learn-distill` — post-session /learn extraction. Run after a cleanup PR merges to capture what was learned.
- `harness-postmortem` — slash `/meta` for agent behavior failures. Different scope (the harness, not the skills).

## Support files

- **`references/staleness-audit.md`** — the full 5-phase recipe with exact grep commands, the 8 indicator patterns, the safe-subset classification table, the worked 2026-07-06 example, and edge cases (multi-skill PRs, skill-vs-repo-only, SOUL.md cross-references). Load this before any cleanup that touches more than one indicator hit.