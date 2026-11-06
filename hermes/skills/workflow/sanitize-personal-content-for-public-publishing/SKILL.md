---
name: sanitize-personal-content-for-public-publishing
description: |
  Sanitize a working personal file (CLAUDE.md, AGENTS.md, skill, README, dotfile)
  into a publishable public example and ship it to a public repo via a clean
  PR — replacing every personal/internal reference with clearly-marked
  placeholders, embedding a reusable sanitization checklist in the published
  file, and verifying zero leaks before push. Distinct from
  `outbound-secret-redaction-gate` (credential-leak prevention at send time)
  and `backup-folder-leak-purge` (force-purging an unintentional repo leak).
  Trigger phrases: "publish a sanitized version", "make a public example",
  "strip the personal refs", "share this publicly", "publish my CLAUDE.md
  as an example", "fork this for the public repo", "make a template
  version", "I want to share my config without leaking private infra".
metadata:
  hermes:
    tags: [publishing, sanitization, github, pr-workflow, personal-content, examples]
    related_skills:
      - github-pr-workflow
      - outbound-secret-redaction-gate
      - backup-folder-leak-purge
      - pr-clean-branch-from-main-no-history-bloat
---

# Sanitize personal content for public publishing

Class-level skill for the recurring workflow of taking a working personal file
that contains private infra references and shipping a **publishable public
example** to a public repo. Distinct from credential-leak prevention at send
time (`outbound-secret-redaction-gate`) and from purging an accidental leak
(`backup-folder-leak-purge`) — this is the *intentional* publishing case
where the user explicitly wants to share a working artifact.

## When to use this skill

- User says "publish a sanitized version of X", "make a public example",
  "strip the personal refs from this", "share this publicly",
  "publish my CLAUDE.md as an example", "fork this for the public repo",
  "I want to share my config without leaking private infra".
- You are about to publish a working `~/.claude/CLAUDE.md`, `~/.bashrc`,
  `~/.zshrc`, AGENTS.md, skill, README, or other personal file that
  contains references to: home paths, machine names, GitHub org names,
  Slack/Discord channel IDs, internal skill names, private memory entries,
  specific PR/issue numbers pointing to private work, OAuth tokens or
  keychain service names, beads IDs.
- The user has a working artifact they want to share with the world but
  the source contains enough personal context that a direct `cp` would
  leak.

## Failure pattern (what goes wrong without this skill)

1. **Sanitization is under-specified.** The agent substitutes generic
   language and the published file loses the value of the working original.
   Or the agent treats "sanitize" as "delete stuff" and the resulting
   example is too generic to be useful.
2. **Personal references slip through.** Common leaks:
   - Home paths (`~/.claude/skills/...`, `~/projects/X`)
   - GitHub org/repo names (`jleechanorg`, internal orgs)
   - Internal tool/CLI names (`agento`, `ao spawn`, `vpython`,
     `mcp_mail`) that imply private infrastructure
   - Slack/Discord channel IDs that are searchable on the public archive
   - PR/issue numbers pointing to private work
   - Memory entries with session-local evidence (dates, session IDs)
   - Bashrc wrapper function names (`claudem`, `claudeg`, etc.)
3. **No reusable recipe.** The published file has the right content but
   no embedded checklist, so a future agent cannot reproduce the workflow.
4. **Wrong base branch.** The PR was branched from `main` (3 commits
   behind `origin/main`) instead of from `origin/main` directly, so the
   diff contains 3 unrelated commits and the reviewer sees noise.

## Recipe — 5 phases (execute in order)

### Phase 0 — Clarify "sanitized" upfront (DO NOT SKIP)

The phrase "sanitized public example" has at least three materially
different outcomes. Ask the user to pick before you write a single line.
Use `clarify` with the three options as choices.

The three flavors (pick one):

| Flavor | What it does | When to use |
|---|---|---|
| **Structure + placeholders** | Show the structure with `<PLACEHOLDER>` markers where personal refs go. Voice/rule shape preserved exactly. | Default. Best as a fill-in-the-blank template. |
| **Rewrite with generic wording** | Take the strongest rules, rewrite them generically, drop everything tied to private infra. Stands on its own. | When the source has too much private context to template. |
| **Hybrid (structure + minimal generic rules + placeholders)** | Mostly structure + a few generic rules + clearly-marked placeholder sections. | Easiest for users to fork and adapt. |

If the user does not respond within ~60 min or says "Continue", default
to **Structure + placeholders** — most defensible: voice preserved,
risk of over-sanitization minimized, leak risk bounded by clearly
visible markers.

### Phase 1 — Pre-write leak inventory

Before writing any sanitized content, build a list of what *would* leak
if you just copied the source. Run these greps against the source file
(adapt patterns to your file type):

```bash
# Personal identifiers
grep -nEi \
  '$USER|jeffrey|<first_name>|<machine_name>|homebrew' \
  <source_file>

# GitHub orgs / repos
grep -nEi 'jleechanorg|<your-org>|hermes-agent|browserclaw' <source_file>

# Internal tool/CLI names
grep -nEi 'agento|ao spawn|vpython|mcp_mail|claudem|claudeg' <source_file>

# Channel IDs / numeric IDs
grep -nE 'C[0-9A-Z]{8,}|U[0-9A-Z]{8,}|launchd|beads|\.jsonl' <source_file>

# Path leaks
grep -nE '~/(\.claude|\.hermes|\.codex|projects|repos)' <source_file>

# Memory references (private feedback files)
grep -nE 'feedback_[0-9]{4}-[0-9]{2}-[0-9]{2}|MEMORY\.md' <source_file>
```

Adapt the patterns to your actual source. The output is your **leak
inventory** — every line that grep returned must be either (a) replaced
with a placeholder, (b) removed, or (c) explicitly justified in the
sanitization checklist at the bottom of the published file.

### Phase 2 — Write the sanitized file

Apply the chosen Phase 0 flavor. Universal rules to include (most
personal CLAUDE.md/AGENTS.md examples cover these):

- File location & layering (user-scope vs repo-scope)
- Core behavior (full absolute paths, state-the-deliverable-first,
  verify-before-reporting)
- Zero-framework cognition (never hand-roll intent classification)
- Working directory lock (don't silently switch cwd)
- Large file read discipline (prevent context thrash)
- Proactive issue tracking (create by default, cite provenance)
- Parallel subagents (fan out independent work; check independence first)
- Subagent model routing (set `model` explicitly on every spawn)
- Git workflow (branch from `origin/main`, one logical commit per PR)
- Force-push safety (explicit human approval required)
- Browser default (headless unless asked)
- Commit often (push after every green unit)
- PR description: follow `~/.codex/AGENTS.md` § PR descriptions (canonical owner), then the target repository's `AGENTS.md`/`CLAUDE.md` and PR template when present.
- Merge safety (literal approval phrase required)
- Disk / resource discipline (three-lane diagnosis, structural preconditions)
- Time-boxing (3-hour wall-clock cap)
- Skill discovery & creation

**Critical: at the bottom of the published file, embed a
**`## Sanitization checklist for public examples`** section that lists
what to grep for, what to remove, what to keep, and what to verify.
This makes the workflow reproducible — anyone forking your example can
apply the same recipe.

Use `<PLACEHOLDER>`-style markers wrapped in angle brackets (e.g.
`<YOUR_GITHUB_ORG>`, `<skill-name>`, `<protected-branch>`). They are
easy to grep for and self-document:

```bash
rg '<[A-Z_0-9]+>' -n <published_file>
```

### Phase 3 — Pre-write verification (run BEFORE push)

Before `git add` + commit, verify zero leaks in the file you are about
to publish:

```bash
# Run the Phase 1 inventory greps against the sanitized file
grep -nEi '$USER|jeffrey|homebrew|jleechanorg|hermes-agent|...' <sanitized_file>
# Expected: zero matches. If any match, fix the file before continuing.

# Count placeholders (sanity check — should be >0 if you used structure+placeholder flavor)
grep -cE '<[A-Z_0-9]+>' <sanitized_file>
```

Document the verification result in the PR body under `## Testing` so
the reviewer can confirm the check happened.

### Phase 4 — Ship via clean PR

1. **Branch from `origin/main`, not local `main`.** Even if your local
   `main` is ahead, base the PR on `origin/main` so the diff is only
   your new file — exactly per `pr-clean-branch-from-main-no-history-bloat`.

   ```bash
   git fetch origin
   git checkout -B docs/<topic>-public-example origin/main
   ```

2. **Verify the diff is clean:**

   ```bash
   git log --oneline origin/main..HEAD      # should be empty before commit
   git diff --stat origin/main..HEAD         # after commit, should be 1 file / +N
   ```

3. **Commit + push:**

   ```bash
   git add <sanitized_file>
   git commit -m "docs: add sanitized public example <name>

   Reference template derived from a working personal <source_type>.
   Personal references replaced with <PLACEHOLDER> markers; sanitization
   checklist embedded at the bottom of the file."

   git push -u origin docs/<topic>-public-example
   ```

4. **The pre-push secret-guard hook will scan automatically.** If it
   finds anything credential-shaped, it will block the push — fix and
   retry. (Per `outbound-secret-redaction-gate`.)

5. **Open the PR with `gh pr create` and a body that includes:**

   - Follow `~/.codex/AGENTS.md` § PR descriptions and the target repository's
     policy and PR template. Keep the example-specific leak-check results
     (`0 matches`, placeholder count, and `git diff --stat`) in the test plan
     and evidence. Do not add a separate Low-level details section; put naming
     and exclusion rationale with the relevant change area or risks.

6. **Do NOT merge.** Wait for the user's review. Per the project's
   merge-safety rules, a public-facing file needs human eyes before
   it ships.

## Pitfalls

1. **Don't substitute the opposite extreme.** The user asked for a
   *sanitized example*, not a stripped-down generic stub. Preserve the
   voice, rule shape, and rule categories — that's the value.
2. **Don't skip Phase 0.** Without the upfront clarification, you will
   guess wrong about which flavor the user wanted. 60 minutes of waiting
   for clarification is cheaper than rewriting a 300-line file twice.
3. **`rg '<[A-Z_]+>'` only matches UPPERCASE placeholders.** If you use
   mixed-case or include digits, adapt the pattern. The point is that
   the placeholder scheme is greppable.
4. **The pre-push secret-guard is a credential scanner, not a
   personal-reference scanner.** It catches PATs/tokens but will NOT
   catch `jleechanorg` or `~/.claude/skills/...`. Phase 3 grep is the
   actual leak gate.
5. **`.example` suffix vs `CLAUDE.md`.** Naming the file
   `CLAUDE.md.example` (or `AGENTS.md.example`) keeps it from being
   picked up as an actual policy file by Claude Code, while signaling
   intent to readers. Users copy it to the real path and edit.
6. **Branch from `origin/main` even when local main is behind.** The
   commit count ahead/behind does not matter — what matters is the
   diff in the PR. Base the PR on the canonical tip.
7. **Don't put secrets in the sanitization checklist example
   greps.** Use synthetic patterns (`jleechanorg` is fine as a sample
   pattern because it's a public org name; `[REDACTED_GITHUB_TOKEN]...` is fine
   because it's a synthetic prefix).
8. **The sanitization checklist itself is example-meta content**, not
   policy. It inflates the line count but is essential for
   reproducibility. Note this in the PR body so reviewers don't ask
   "why is this so long?"
9. **Embedding the checklist makes the file ~2x larger than a
   minimal policy file.** That is OK for a *public example* — the goal
   is reproducibility, not brevity. For an actual user-scope policy
   file, move the checklist to a separate doc.
10. **Multi-machine personal files** — if you have the same content on
    multiple machines (e.g. via a sync script), the sanitized version
    must also strip machine-specific paths. Test on a clean clone, not
    on the original host.

## Companion skills

- `outbound-secret-redaction-gate` — handles *credential* leaks at the
  send boundary. Run that gate's pre-send scan as a final check before
  push, even though the secret-guard pre-push hook covers most cases.
- `backup-folder-leak-purge` — handles *unintentional* leaks where a
  backup cron pushed private content to a public repo. Different
  trigger (accidental vs intentional); if you find one of those, this
  skill's checklist can help identify what should have been redacted,
  but the fix is in `backup-folder-leak-purge`.
- `github-pr-workflow` — covers the standard PR lifecycle (branch,
  commit, push, open PR). Phase 4 of this skill references its branch
  creation and PR-creation patterns.
- `pr-clean-branch-from-main-no-history-bloat` — Phase 4's
  "branch from `origin/main`" requirement is straight from this rule.

## Support files

- [`templates/sanitization-checklist.md`](templates/sanitization-checklist.md)
  — the embedded checklist to drop at the bottom of any published
  example, with the canonical grep patterns and a what-to-keep /
  what-to-remove / what-to-verify matrix.
- [`scripts/verify-no-personal-leaks.sh`](scripts/verify-no-personal-leaks.sh)
  — re-runnable harness that runs the Phase 1 inventory greps against
  a target file and exits 0 only when zero matches found. Use as a
  pre-push gate (similar in spirit to `outbound-secret-redaction-gate`'s
  PAT scanner, but for personal references rather than credentials).

### Example usage

```bash
# After writing your sanitized file, run the gate before push
./scripts/verify-no-personal-leaks.sh .claude/CLAUDE.md.example

# Drop the checklist at the bottom of any example file you publish
cat templates/sanitization-checklist.md >> <your-example-file>
```

## Provenance

- **First verified:** 2026-07-24, claude-commands PR #342
  (`docs/claude-md-public-example`). Source: `~/.claude/CLAUDE.md`
  (562 lines / 57 KB). Output: `.claude/CLAUDE.md.example` (296 lines
  with embedded sanitization checklist). Branched from
  `origin/main` @ `b72956aac`, commit `2938e4f1d`. Pre-push
  secret-guard clean. PR opened, awaiting user review.
