---
title: Staleness audit recipe for SKILL.md
audience: agent loading `stale-skill-audit`
---

# Auditing an Existing SKILL.md for Stale Content

This reference is the concrete recipe for a *safe-subset* cleanup pass that produces a single PR with no content-meaning edits. Use it when the SKILL.md is the right level of detail; for the philosophy and decision framework, see the umbrella SKILL.md.

## When to run this

- User says "this SKILL is bloated / has outdated stuff / needs cleanup", or names a specific skill that drifted.
- A skill's description has grown past ~1024 chars (validator forces a rewrite — may as well clean the body too).
- You spot one of the *indicator patterns* below in a skill you've loaded.
- The org changed canonical CLIs, paths, or defaults (e.g. `bd` → `br`; old repo URLs in Provenance footers).
- A scheduled `agent-agent-mistakes` or `meta-autonomy-violation-handler` review flagged specific files.

**Do NOT run this** as proactive maintenance without a signal. The user knows what's stale to them; unsolicited cleanup of "any skill that looks old" generates noise and PRs that don't merge.

## The "safe subset only" default

When the user says "cleanup", assume **safe subset** unless they explicitly ask for more. Safe subset = **no content-meaning edits, only**:

- Drop dead-audit data the LLM can't resolve (runIds, bead IDs, commit SHAs, PR URLs in Provenance footers).
- Swap drifted canonical names (`bd` → `br`, old repo paths, retired CLI flags).
- Normalize header dates that pin to a specific moment in time ("2026-07-06" → "2026-07" in framing positions; **keep incident-anchored dates verbatim** — they're load-bearing evidence that the rule is battle-tested).
- Fix typos that change meaning ("province comment" → "provenance comment" is in scope; rewording a rule is not).
- Replace WIP-forward language ("in progress as of 2026-07-06/07", "TODO: ", "TBD") with current-state wording or drop.

**Out of safe subset** (requires explicit user OK):
- Removing paragraphs or rules.
- Promoting content from user-scope to repo (`~/.claude/skills/foo/SKILL.md` has a paragraph the repo file doesn't — that's a separate "promote to repo" PR, not a cleanup PR).
- Restructuring / reordering.
- Changing the trigger phrases in the YAML frontmatter description.

## The indicator patterns (grep the file)

Run these against the candidate SKILL.md and any line that hits is a candidate edit:

```bash
SKILL=~/.claude/skills/<name>/SKILL.md

# 1. Provenance / audit footers — usually dead by now
grep -n '^## Provenance\|^## History\|^## Changelog' "$SKILL"

# 2. CLI drift (org moved from bd to br, or other retirements)
grep -nE '\bbd\b' "$SKILL"

# 3. Specific workflow runIds (wf_xxxx, batch_xxxx, run_xxxx)
grep -nE 'wf_[0-9a-f]{4,}|batch_[0-9a-f]{4,}|run_[0-9a-f]{4,}' "$SKILL"

# 4. Specific bead IDs / PR / commit SHAs
grep -nE '\brev-[a-z0-9]{4,}|\bPR #[0-9]+\b|\b[0-9a-f]{7,}\b' "$SKILL"

# 5. Header dates (description + lead-in + table cells), as opposed to incident-anchored dates
grep -nE '\b2026-[0-9]{2}-[0-9]{2}\b' "$SKILL"

# 6. WIP-forward language that ages badly
grep -nE 'in progress as of|to be (done|added|written)|TODO: |FIXME: |XXX:|TBD' "$SKILL"

# 7. Hard-coded host paths that won't survive expansion
grep -nE 'file:///Users/|/Users/[a-z]+/' "$SKILL"

# 8. Credentials in code blocks (separate, urgent — escalate immediately)
grep -nE 'ghp_|gho_|x-access-token|serviceAccountKey' "$SKILL"
```

For each hit, classify:
- **Header/frame** (description, lead-in, table title): normalize or drop.
- **Incident-anchored** (mid-rule, with a specific defect class or example): keep verbatim.
- **Provenance/audit footer**: drop the whole section.
- **WIP-forward language**: replace with current-state wording or drop.

## The 5-phase workflow

### Phase 1 — Find the canonical file

Before editing, check BOTH locations — local user-scope edits often drift ahead of the remote:

```bash
# Local user-scope (may be ahead of remote)
ls -la ~/.claude/skills/<name>/SKILL.md

# Remote canonical
curl -fsSL https://raw.githubusercontent.com/<org>/<repo>/main/.claude/skills/<name>/SKILL.md | diff - ~/.claude/skills/<name>/SKILL.md
```

If they differ, the user-scope file is the user's working draft and the remote is what other consumers see. Decide with the user which to treat as canonical — usually the answer is "apply safe-subset to the remote file and let the user re-merge their local additions later", because the remote is the public source of truth.

### Phase 2 — Apply safe-subset edits

For each indicator hit, write the minimal `patch` (`old_string` → `new_string`). Use `replace_all=true` only when the edit is unambiguously the same in every occurrence (e.g. `bd` → `br`). For header dates vs incident dates, use targeted single-occurrence patches.

Verify between edits:

```bash
# After every patch, re-run the indicator greps with the EXPECTED post-state
grep -c '\bbd\b' "$SKILL"          # should be 0 after bd→br sweep
grep -c '^## Provenance' "$SKILL"  # should be 0 after footer drop
```

### Phase 3 — Local edit (user-scope)

Edit `~/.claude/skills/<name>/SKILL.md` first. This is the file the user's local sessions actually read; getting it right locally means the user can see the change immediately on next session start.

### Phase 4 — Propagate to remote repo (PR)

Use the `github-pr-workflow` skill's standard branch-from-main → commit → push → `gh pr create` flow. No approval phrase is needed to leave the session's cwd. If the session cwd is `$HOME` (no git repo), clone `jleechanorg/claude-commands` (or whichever repo) into `~/.hermes/state/worktrees/` and work there. Report the absolute path you worked in.

**Do not include the user-scope local additions** in the cleanup PR. If the local file has paragraphs the remote doesn't (e.g. "Domain-general by design", new rules added locally), those are content additions that deserve their own review PR. State this explicitly in the PR description under "Out of scope".

The PR title should be `chore(<skill-name>): <one-line summary>` (Conventional Commits style, matching `hermes-agent-skill-authoring` peer convention).

The PR body should include:
- **What changed** — list each safe-subset edit category with counts.
- **Why** — one line per category (dead-audit, CLI drift, header-date normalization, typo fix).
- **Out of scope** — explicit list of local additions that exist in `~/.claude/skills/<name>/SKILL.md` but not in the remote file.
- **Stats** — bytes before/after, insertions/deletions.
- **Test plan** — the verification commands from Phase 5.

### Phase 5 — Verify the PR landed

```bash
LOCAL_SHA=$(git rev-parse HEAD)
REMOTE_SHA=$(gh pr view <N> --json headRefOid --jq .headRefOid)
[ "$LOCAL_SHA" = "$REMOTE_SHA" ] && echo "✓ match" || echo "✗ MISMATCH"

curl -fsSL https://raw.githubusercontent.com/<org>/<repo>/<branch>/.claude/skills/<name>/SKILL.md | \
  grep -c '\bbd\b'   # must be 0
```

Check `gh pr checks <N>` — CodeRabbit often pre-reviews within 60s for skills repos. Skills repos are usually fast-passing since they're docs.

## Worked example: 2026-07-06 swarm/SKILL.md cleanup

The cleanup of `jleechanorg/claude-commands/.claude/skills/swarm/SKILL.md` ([PR #317](https://github.com/jleechanorg/claude-commands/pull/317)):

- **Indicator grep hit:**
  - 4× `bd` references (lines 34, 35, 41, 60) → all swapped to `br`
  - `## Provenance` footer (lines 79-80) → dropped (9 specific runIds, 6 specific bead IDs, 1 commit SHA, 1 PR URL — all dead audit data)
  - 7× `2026-07-06` header positions → normalized to `2026-07`
  - 3× `2026-07-07` inside rules 3, 4, 11 → **kept verbatim** (incident-anchored)
- **Out of scope (correctly):**
  - "Domain-general by design" paragraph (in user-scope local only — would be a content addition, not a cleanup)
  - New rule 12 (cross-model cold review) — same
- **Stats:** 17,793 → 16,775 bytes (-1,018); 11 insertions / 13 deletions; CodeRabbit pre-approved PASS in <60s.
- **Branch:** `cleanup/swarm-skill-strip-stale-provenance` from `origin/main`.

## Pitfalls (deeper)

1. **"Medium cleanup" is not the default.** When the user says "let's cleanup", they almost always want the safe subset, not a rewrite. Ask once with a small number of escalating options; don't make them pick from 4. If they pull back mid-conversation from a higher scope, narrow immediately, don't re-confirm.
2. **Header dates ≠ incident dates.** Stripping "2026-07-07" from a rule that says "Hit twice on 2026-07-07: `pr-retro-gapfill` (15/15 verify agents died, 5 real Collect-stage findings falsely zeroed out)" removes the *evidence the rule is battle-tested*. That date is load-bearing.
3. **bd → br is not always safe.** Some skills genuinely use `bd` because the project hasn't migrated. Confirm against the org's current canonical CLI in `~/.claude/CLAUDE.md` and `projects/AGENTS.md` before sweeping.
4. **Don't edit a foreign repo's live checkout in place.** It may be on someone else's branch with dirty work. Clone into `~/.hermes/state/worktrees/<repo>` and work from there; no approval phrase is required to change directories.
5. **Don't rebase-then-merge an unrelated local commit.** The local file may have *more* recent additions than the remote. Editing the remote's `git checkout -B cleanup/foo` branch and replaying only the safe-subset diff onto it is the right move.
6. **`git rev-parse origin/<branch>` lies after a fresh push.** The local ref-cache doesn't update immediately. Verify with `gh pr view N --json headRefOid` instead, or `git fetch origin <branch>` first.
7. **Provenance footers can be load-bearing for the project's own audit.** Before dropping a Provenance section wholesale, check whether the bead IDs inside are still resolvable (`bd show <id>` / `br show <id>`). If they are, the footer is documentation of a real artifact trail; consider archiving to a separate `docs/...` file rather than deleting.

## Edge cases

- **Skill has no local file but exists in the repo** — only edit the remote. No local patch needed.
- **Skill exists only in user-scope, not in any repo** — it's personal; safe-subset only, no PR.
- **Skill is referenced from a SOUL.md COMMIT block** — patch the SKILL.md, also update the COMMIT block in `~/.hermes/workspace/SOUL.md` and propagate via `hermes-deploy-pipeline` if it's a Hermes harness skill.
- **Multiple skills share the same stale Provenance footer** — patch each in its own PR; bundling unrelated skill changes into one PR breaks the diff-attribution rule.
- **The skill is the umbrella itself** (e.g. `simplify-code`, `hermes-agent-skill-authoring`) — same workflow, but use `skill_manage` for the local edit instead of `patch`, since the skill is registry-managed.

## Reference

This recipe came from a real session on 2026-07-06 — the cleanup of `jleechanorg/claude-commands/.claude/skills/swarm/SKILL.md`, shipped as [PR #317](https://github.com/jleechanorg/claude-commands/pull/317). For the meta-skill that decides whether to spawn this work via `/meta` (agent failure) vs `/a` (task), see `harness-postmortem`. For the conventions for *authoring* skills (frontmatter, validator, structure), see `hermes-agent-skill-authoring`.