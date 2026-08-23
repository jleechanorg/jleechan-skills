---
name: wiki-vault-safeguards
description: "Safety patterns for working with a populated LLM-wiki / personal knowledge vault (~/llm_wiki, ~/wiki, etc.) — preventing concept-page clobber, enforcing append-not-overwrite, the default-doing-now save location for research artifacts, AND the push-to-origin-main flow when the wiki is a git repo with concurrent agent activity. Activates when the user asks to save research / a brief / top-10 / synthesis to the wiki, or asks to push the wiki to origin main. Loads alongside llm-wiki and obsidian skills."
version: 1.2.0
author: Hermes Agent
license: MIT
platforms: [linux, macos]
changelog:
  - "1.2.0 (2026-07-28): Two new pitfalls. (a) 'sources/' vs 'raw/' directory trap — workers invent `sources/articles/` because the frontmatter field is `sources:` and they confuse field-with-directory. The wiki's Layer 1 directory is ALWAYS `raw/articles/` (or `raw/papers/`, `raw/transcripts/`). A worker that wrote `sources: [\"sources/articles/mbti/ENFJ-per.html\"]` left 17 files with non-existent directory references; parent had to sed-fix all 17. (b) Concept pages without raw sources — workers that summarize N articles and write N concept pages but skip the curl-fetch into `raw/articles/<file>.<ext>` step silently break re-ingest drift detection. Lint's source-drift check (item ⑧ in llm-wiki) becomes a no-op for the skipped sources. Both pitfalls verified on 16-MBTI ingest (2026-07-28, personalitypage.com)."
  - "1.1.0 (2026-07-26): Add Failure Modes 3a-3e (cross-org push with wrong gh account, git ls-files truth over git status, stash-then-checkout pattern, journal-file rebase conflict resolution)."
  - "1.0.0 (initial): Failure Modes 1-3 (overwrite trap, default-doing-now save, push-to-origin-main)."
metadata:
  hermes:
    tags: [wiki, knowledge-base, safety, git, vault, llm-wiki, karpathy]
    category: research
    related_skills: [llm-wiki, obsidian]
---

# Wiki / Vault Safeguards

Companion to the `llm-wiki` and `obsidian` skills. Those skills describe the Karpathy
pattern and Obsidian vault mechanics. This skill covers the **safety patterns** that
apply specifically when the vault is *populated* (multiple agents writing over time,
months of accumulated concept pages) and **backed by a git repo** (`jleechanorg/llm-wiki.git`,
`jleechanclaw` etc.) with concurrent activity.

## When This Skill Activates

Load this skill when ANY of these are true:

- The user asks to save, write, ingest, file, or commit a research artifact to a wiki/vault
- The user asks to "push the wiki to origin main" / "commit the wiki" / "push my notes"
- You're about to call `write_file` on a path inside `~/llm_wiki/` or `~/wiki/` or any
  other markdown-vault directory
- You see `wiki/` or `notes/` or `vault/` referenced in the conversation and the wiki
  is already populated (>20 markdown files)

## Three Failure Modes This Skill Prevents

### Failure Mode 1: Concept-page overwrite trap

**Symptom:** You complete the orientation routine (read SCHEMA + index + scan log), see
that `concepts/HarnessEngineering.md` exists with a 2026-04-14 last_updated date, and
correctly decide "the answer belongs in `concepts/HarnessEngineering.md`." Then you
call `write_file(path='concepts/HarnessEngineering.md', content=<new content>)`. The
pre-existing 60+ lines of Meta-Harness paper + 4-layer architecture + OpenAI workshop
notes are silently gone. No error, no warning.

**Why orientation didn't save you:** The orientation routine tells you a page exists.
It does not enforce the merge-with-existing rule on `write_file`. `write_file` is a
*clobber-and-replace* primitive — that's its contract.

**The three-step pattern before any write to a known-existing page:**

1. **Re-read the target file** (`read_file path=<concept>.md`) immediately before
   `write_file`. Even if you saw the path in `index.md` 3 turns ago, re-read — the
   page may have been updated by another agent in parallel.
2. **Diff concepts, not just filenames.** If the existing page covers a *different
   framing* of the same word (e.g. pre-existing HarnessEngineering is the
   self-bootstrapping agent runtime harness; new research is the AIEWF 2026
   human-org harness), the answer is **append a section, not overwrite**.
   Append-only preserves the compounding nature of the wiki.
3. **When in doubt, `patch` not `write_file`.** Read the existing page, find a stable
   anchor (last bullet list, last heading, etc.), and `patch` to add a new section.
   `write_file` is only safe for genuinely new pages or genuinely
   contradicted-and-resolved content (mark with `contradictions:` frontmatter first).

**Recovery if you clobbered:** If the vault is under git (which is the assumption for
this skill), `git checkout HEAD -- <path>` restores the pre-write state, then re-do
the work as a `patch` append.

**Verified session:** 2026-07-14, AIEWF 2026 brief. I clobbered `HarnessEngineering.md`
that had the Meta-Harness paper + 4-layer architecture. Recovered via `git checkout HEAD
-- concepts/HarnessEngineering.md`, then used `patch` to append a new AIEWF validation
section. Net result: +14 lines additive, zero content loss.

### Failure Mode 2: Research artifact saved to /tmp, then pick-one-menu asked

**Symptom:** User asks "research the top 10 learnings from the conference." You write the
brief to `/tmp/aiewf-2026-top-10.md` (volatile), post a Slack reply with the summary,
and ask "Pick one: (a) save to wiki (b) deeper AO pull (c) LinkedIn draft." User replies
"keep going save the brief and summarize it, why did you stop."

**Why this is wrong twice over:** (1) `/tmp/foo.md` is volatile — gone on next reboot.
(2) The pick-one-menu violates SOUL.md `no-pick-one-menus` COMMIT explicitly.

**The default-doing-now move:**

1. Write the brief to `sources/<descriptive-slug>-YYYY-MM-DD.md` (or `raw/articles/`
   per plain Karpathy-pattern vaults).
2. Create the 2-3 concept pages the brief implies, each with cross-references via
   `[[wikilinks]]`.
3. Add entries to `index.md` linking them.
4. Post a one-line summary back to the originating thread.

**Do NOT ask "where should I save this?"** The vault is the answer. Default-doing-now
applies. Volatile `/tmp` + ask-the-user is the failure mode. The user can always say
"move it elsewhere," but `/tmp` is wrong by default.

### Failure Mode 3: Push to origin main with divergent history

**Symptom:** User says "push to origin main." You `git status` and see 3
`[Auto] Pending changes` commits ahead of origin/main, none of them yours. You try
`git rebase origin/main` and it aborts with conflicts in `raw/campaigns/*` that have
nothing to do with your work.

**The safe pattern:**

1. `git fetch origin` first — see the actual remote state.
2. `git status --short --branch` — local divergence from origin.
3. `git log origin/main..HEAD` and `git diff --stat origin/main..HEAD` — identify
   which local commits are yours vs pre-existing.
4. **Decision tree:**
   - **Unrelated pre-existing commits → `git reset --hard origin/main`** then unstash
     your work, commit, push. Cleaner linear history.
   - **Your commits you want to preserve → rebase manually**, resolve conflicts
     file-by-file with `git checkout --theirs/--ours <path>` for specific hunks.
5. **Never `git checkout --theirs <index.md>` wholesale** — you'll lose other agents'
   recent entries. Resolve `index.md` conflicts manually by reading both versions and
   merging the additions.
6. **Stage only your files** with explicit paths, not `git add -A`. Untracked files
   in `.beads/`, `artifacts/`, `raw/` from other agents are not yours to commit.
   (Verified: 50+ untracked `.beads/.br_history/*.jsonl` files in `~/llm_wiki` from
   prior sessions — none related to AIEWF brief, all left alone.)
7. Commit with a scoped message that names the source/session/task, then `git push origin main`.
8. Verify: `git rev-parse origin/main` matches local HEAD SHA.

If the vault is **not** under git, report that explicitly to the user and offer
`git init` + first-commit. Don't `git push` to a non-existent remote.

#### 3a. Cross-org push when `gh auth` is wrong for the vault's remote

**Trigger:** `git push origin main` returns `Repository not found` against a remote
URL like `https://github.com/Agnt-F/<repo>.git` or `https://github.com/<other-org>/<repo>.git`,
while `gh auth status` shows the active account is `jleechan2015` (member of
`jleechanorg` but NOT of the vault's org).

**Why this fires:** `gh`'s HTTP-credential helper scopes the token to the active
account's accessible orgs. `jleechan2015` cannot push to `Agnt-F/*` even if a `$USER-af`
account exists in 1Password/Keychain — `gh` only knows about one active user at a time.

**The fix — token override for one push, no global config pollution:**

```bash
# 1. Verify a non-gh token exists for the target org in the environment
GH_TOKEN_AGENTF="$GH_TOKEN_AGENTF" curl -sS -o /dev/null -w "HTTP %{http_code}\n" \
  -H "Authorization: token $GH_TOKEN_AGENTF" -H "User-Agent: hermes-push" \
  https://api.github.com/repos/Agnt-F/<repo>

# Expect HTTP 200. If 401/404 the token is wrong or has wrong scope.

# 2. Push with that token via URL insteadOf + a credential helper that reads from env
git -c credential.helper='!f() { echo "username=x-access-token"; echo "password=$1"; }; f "$@"' \
    -c "url.https://x-access-token:$GH_TOKEN_AGENTF@github.com/Agnt-F/<repo>.git/.insteadOf=https://github.com/Agnt-F/<repo>.git" \
    push origin main
```

**DOs / DON'Ts:**
- DO use `GH_TOKEN_AGENTF` (or whatever the org-scoped env var is) — DO NOT embed the
  token in the remote URL with `git remote set-url origin ...`.
- DO scope the `-c` flags to the one `push` invocation — DO NOT `git config --global`.
- DO verify the token with the API probe before pushing (saves a round-trip on a wrong token).
- DO NOT echo the token in shell history. Use `$GH_TOKEN_AGENTF` directly, never `echo $GH_TOKEN_AGENTF`.

**Companion rule:** for `Agnt-F/*` Agnt-F vault work, load `agentf` skill alongside
this one — it documents the `$USER-af` vs `jleechan2015` distinction and the
canonical token location.

#### 3b. "Is this file already committed?" — `git status` lies, `git ls-files` is the truth

**Trigger:** A path appears in `git status --short` as `?? foo/bar.md` (untracked)
on the first scan, but after `git add` of OTHER files it disappears from the
untracked list — and yet `git ls-files foo/bar.md` returns the path. If you
included the path in your `git add` list, it was a no-op but you also didn't double-check.

**Why this fires:** A race between your `git status` call and another agent / cron
running `git add foo/bar.md && git commit` mid-session. The untracked-list snippet
you snapshotted is stale by the time you stage other files.

**The diagnostic:**
```bash
# Before adding ANY borderline path, verify it is currently untracked
git ls-files <path>          # empty output → truly untracked, safe to add
git log --all --oneline -- <path> | head -3   # see if it has commit history
```

**The rule:** when building an `git add <list>` command, run `git ls-files <each-path>`
in a parallel batch first. Paths that return a hit were already committed by another
agent — drop them from the add list. Paths that return empty are still untracked.

#### 3c. Landmine taxonomy — pre-push checklist for untracked file lists

**Trigger:** `git status --short` lists 10+ untracked files and at least one has a
borderline name (`*-recovery-*`, `nextsteps-*`, `*-audit-*`, numeric ID, etc.).
Three classes of landmines recur across multi-repo pushes:

1. **Multi-MB recovery artifact folders** — `dk2d-recovery-*/`, `*/artifacts/`, `ao-*-*/`
   containing `b3/`, `native32/`, `*.so`, raw ffprobe dumps. NEVER push.
2. **`.beads/.br_history/*.jsonl`** — bead CLI history dumps that aren't in `.gitignore`
   by default. ALWAYS skip; recommend adding `.beads/.br_history/` to `.gitignore` in
   the next session.
3. **Auto-export cron dumps under `cron/` or `launchd/`** — these are usually already
   committed at their canonical paths, but the local working tree may have stale copies
   that look untracked after a half-completed export run.

**The pre-push checklist:**

```bash
# 1. Size audit — anything >5 MB untracked is suspicious
git status --short | grep "^??" | awk '{print $2}' | xargs -I {} sh -c 'du -sh "{}" 2>/dev/null' | sort -h | tail -10

# 2. First-line sniff of every borderline file (.md files, by 10-line head)
for f in $(git status --short | grep "^??" | awk '{print $2}' | grep '\.md$'); do
  echo "=== $f ==="; head -10 "$f"; echo
done

# 3. Stale-branch probe — confirm you're on the branch you think you are
git branch --show-current
git rev-parse --abbrev-ref --symbolic-full-name @{u}    # upstream

# 4. Auth probe — confirm gh-vs-target-org alignment
gh auth status | grep -E "account|Active" | head -3
```

If any check returns a landmine, STOP and ask the user or skip the file explicitly.
Do not `git add -A` and hope.

#### 3d. Stash-then-checkout to free a dirty worktree for branch switching

**Trigger:** You need to `git checkout main` (or any branch) but the current branch
has `M` files that `git status` reports would be overwritten. The dirty files are
content you DO want to push (they correspond to commits on the current branch you'll
re-apply via cherry-pick), but `git checkout` refuses without `commit` or `stash`.

**The pattern:**

```bash
# 1. Stash ONLY the explicitly-named files (not `git stash` blanket)
git stash push -m "branch-rescue-stash" -- README.md learnings-2026-07.md

# 2. Now checkout succeeds
git checkout main

# 3. Cherry-pick the commits that originally carried those file changes
git cherry-pick <sha1> <sha2> ...

# 4. Resolve any post-cherry-pick conflicts (see 3e below)

# 5. Drop the stash when the cherry-picks succeed
git stash list    # confirm it's still there
git stash drop stash@{0}
```

**DO NOT use `git stash pop` here** — if cherry-picking conflicted, `stash drop` is
cleaner; `stash pop` would either fail or silently re-apply dirt that the merge
already covered.

#### 3e. Rebase-onto-origin/main conflict when BOTH local-main commits AND
cherry-picked-feature-branch commits modified the same journal file

**Trigger:** You `git rebase origin/main` after fetching new remote commits, and the
rebase aborts with a `<<<<<<< HEAD` / `=======` / `>>>>>>> <sha>` conflict in a file
named `learnings-YYYY-MM.md`, `daily-log-YYYY-MM.md`, or any chronological journal
where both sides added dated entries.

**Why this fires:** the local feature branch was branched from origin/main BEFORE
the auto-export cron added N more journal entries. After you cherry-pick the
feature-branch commits onto `main`, then `git fetch` shows origin/main has 7 more
journal entries ahead of `main` too. The rebase merges local-vs-remote BOTH having
new journal entries — most are unique-but-similar in shape, so `git` conflates them
into a hunk conflict.

**The resolution rule:** **keep ALL dated entries from both sides, in chronological
order.** Do NOT `git checkout --theirs` (loses your entries) or `--ours` (loses
remote's entries). Open the conflict block, identify each `## YYYY-MM-DD` heading,
interleave them by date, drop the markers.

```bash
# After patch'ing the file with merged content:
grep -nE "^(<<<<<<<|=======|>>>>>>>)" learnings-2026-07.md | head -5
# MUST return zero matches before continuing

git add learnings-2026-07.md
git rebase --continue
```

If the markers still exist after `patch`, the rebase will silently produce a
corrupted commit — gate on `grep` returning zero.

## Integration with Existing Skills

- **Load with `llm-wiki`** when the user is doing structured research ingest. The
  llm-wiki skill covers the Karpathy pattern and orientation; this skill covers the
  safety + git-push layer.
- **Load with `obsidian`** when the user is doing personal-note work in Obsidian.
  The obsidian skill covers vault mechanics (path resolution, read/write/append,
  wikilinks); this skill covers the "populated vault + git push" edge cases.
- **Companion to `github-pr-workflow`**: this skill is for personal wikis, not
  project repos. For project repos with branch protection and PR review, follow
  the standard `always-pr-never-local-edit` + `github-pr-workflow` patterns instead.

## Quick Reference: Decision Table

| Situation | Action |
|---|---|
| Vault exists, target page exists, content is mine to write | `read_file` then `patch` (append) |
| Vault exists, target page exists, content contradicts existing | `patch` + add `contradictions:` frontmatter |
| Vault exists, target page is new | `write_file` (safe — no existing content to clobber) |
| Vault exists, user asked for a "research artifact" / "brief" | Default-doing-now: write to `sources/`, create concepts, update index |
| User asked "where should I save this?" | Don't ask back. Save to vault on this turn and tell them where. |
| User asked "push to origin main" and local is divergent | `reset --hard origin/main` → unstash → commit → push |
| User asked "push to origin main" and local is clean | `git push origin main` directly |

## Pitfalls (one-liners)

- `write_file` clobbers — always `read_file` first.
- Append-only by default; `write_file` only for genuinely new pages.
- Default-doing-now: research artifacts go to vault, not `/tmp`.
- Never `git add -A` in a vault repo with concurrent agent activity.
- Never `git checkout --theirs` on `index.md` — merge manually.
- `/tmp/foo.md` is a bug, not a strategy.
- `git status` snapshot is stale — confirm `git ls-files <path>` before staging borderline files.
- Pre-push audit: `du -sh` every untracked dir, head-sniff borderline `.md`s, verify branch + auth.
- `git push` returning "Repository not found" against a non-`jleechanorg` org = wrong active `gh` account; use a token override pattern (see 3a).
- `git rebase origin/main` conflict on a journal file = both sides added dated entries; merge chronologically, never `--theirs` or `--ours`.
- `git stash drop`, not `git stash pop`, after a successful cherry-pick that re-applies stashed content.

### Failure Mode 4: `sources/` vs `raw/` directory trap (frontmatter field confused with Layer 1 directory)

**Symptom:** A worker is told to ingest N source articles into the wiki. It writes N concept pages with correct frontmatter `sources: ["mbti/ENFJ-per.html"]` but the **directory** it points at is `sources/articles/mbti/ENFJ-per.html` — a path that does not exist in this wiki. The wiki's Layer 1 directory is `raw/articles/` (or `raw/papers/`, `raw/transcripts/`, `raw/assets/`), not `sources/articles/`. The wiki is missing the actual source files (the worker either never fetched them, or fetched them into the wrong directory, or just summarized without saving). The next lint pass's source-drift check (item ⑧ in `llm-wiki`) becomes a no-op for those sources.

**Why this fires:** The frontmatter field is `sources:` (plural noun) and the URL-prefix convention is `raw/`. The worker has both `sources:` (in frontmatter) and the source path string (in the value) and conflates them, inventing `sources/articles/` as a directory because "the value starts with `sources/`". This is a "the model improvises formatting" class of error — see `llm-narration-format-clarifier` for the broader pattern.

**The rule:** the `sources:` frontmatter field's value is **always a path under `raw/`**. Valid forms:
- `raw/articles/<descriptive-slug>-YYYY-MM-DD.md` (LLM-extracted text)
- `raw/articles/<descriptive-slug>-YYYY-MM-DD.html` (raw HTML when the original is HTML and the LLM hasn't reformatted it)
- `raw/papers/<arxiv-id>-<slug>.pdf` (arXiv PDFs)
- `raw/transcripts/<meeting-slug>-YYYY-MM-DD.md`
- `raw/assets/<image>.png`

Never `sources/`, never `articles/` (without `raw/` prefix), never any path that doesn't start with `raw/`.

**Diagnostic (5 commands, ~3s):**

```bash
# 1. List every concept page's sources: frontmatter value
for f in $WIKI/concepts/*.md; do
  grep -E '^sources:' "$f"
done | sort -u

# 2. For every non-raw-prefixed source, flag it
grep -rEh '^sources:' $WIKI/ | grep -vE '"raw/' | head -20

# 3. For every flagged source, check whether the file exists
# (this is what `llm-wiki` lint item ⑧ does — if it can't find the file, it can't drift-check)
```

**Recovery recipe (sed fix across all flagged files):**

```bash
# Verify the substitution works for one file before bulk-applying
grep -nE '^sources:.*"sources/' "$WIKI/concepts/mbti/ENFJ.md"

# Bulk-fix: sources/articles/<TYPE>.html → raw/articles/<TYPE>.html
for f in $(grep -rlE '^sources:.*"sources/' $WIKI/); do
  sed -i '' 's|"sources/articles/|"raw/articles/|g' "$f"
done

# Verify no flagged paths remain
grep -rEh '^sources:' $WIKI/ | grep -vE '"raw/' | head -5
# Expect: zero output
```

**Verified session (2026-07-28):** 16-MBTI ingest. The wiki worker wrote 16 concept pages + 1 index page, each with `sources: ["sources/articles/mbti/{TYPE}-per.html"]`. None of those source files existed. Parent session (1) ran the Python-script curl-fetch into the **correct** `raw/articles/mbti/` directory, then (2) bulk-sed-fixed all 17 files to use `raw/articles/` paths. ~10 lines of sed + a 90-second Python ingest script. The fix would have been 2 lines per file if the worker had used the right path the first time.

**Anti-pattern:** re-running the worker with a bigger `--max-turns` budget. The worker will fix 1-2 files and re-time-out at the same place. The parent-session sed fix is faster (sub-second) and avoids losing the worker's well-formed concept pages.

### Failure Mode 5: Concept pages without raw sources (skipped the `raw/` ingest step)

**Symptom:** A worker is told to ingest N articles (e.g. "ingest 16 MBTI personality pages from personalitypage.com"). It writes 16 concept pages summarizing each article, but it **skipped** the curl-fetch step into `raw/articles/`. The `sources:` frontmatter on each concept page references a file that does not exist on disk. The wiki appears complete (17 markdown files for the MBTI topic) but is **un-re-ingestable**: when the source URL changes, the wiki can't detect drift because there's no source-of-truth hash to compare against.

**Why this fires:** The worker treats "summarize N articles into N concept pages" as the deliverable and optimizes for "concept pages exist" rather than "concept pages exist AND their raw sources exist". This is a "task boundary invisible" error — see `claude-code-claudem` for the related worker-context boundary case.

**The rule:** an ingest of N articles MUST produce N raw files in `raw/articles/` (or `raw/papers/` / `raw/transcripts/`) AND N corresponding concept pages AND `index.md` references AND a `log.md` entry. Skipping any one of these four steps is incomplete. The lint check that catches this is **`raw/` file-existence assertion during concept-page write**: when writing a concept page that references a `sources:` path, assert the file exists at write-time.

**The write-time assertion recipe (run BEFORE `write_file` on the concept page):**

```python
import os, re
WIKI = "$HOME/llm_wiki/wiki"
concept_path = "concepts/mbti/ENFJ.md"
# Extract the sources: line
with open(concept_path) as f:
    sources_line = next((l for l in f if l.startswith("sources:")), "")
m = re.search(r'"([^"]+)"', sources_line)
if m:
    raw_path = os.path.join(WIKI, m.group(1))
    assert os.path.exists(raw_path), f"Missing raw source: {raw_path}"
```

**Diagnostic for "did the worker skip the raw step?":**

```bash
# 1. List all source paths referenced in concept pages
grep -rhE '^sources:' $WIKI/concepts/ | grep -oE '"raw/[^"]+"' | sort -u

# 2. For each, check existence
grep -rhE '^sources:' $WIKI/concepts/ | grep -oE '"raw/[^"]+"' | sort -u | \
  tr -d '"' | while read p; do
    [ -f "$WIKI/$p" ] && echo "OK $p" || echo "MISSING $p"
  done

# 3. Count missing
grep -rhE '^sources:' $WIKI/concepts/ | grep -oE '"raw/[^"]+"' | sort -u | \
  tr -d '"' | while read p; do
    [ ! -f "$WIKI/$p" ] && echo "$p"
  done | wc -l
```

**Recovery recipe (fetch the missing sources into `raw/`):**

```bash
mkdir -p $WIKI/raw/articles/mbti
# Use Python with proper request handling (curl loop with 0.5s sleep is acceptable
# but watch for Ezoic/Cloudflare bot-detection that returns 200 with empty body).
# The personalitypage.com 16-page MBTI ingest took 14s with a 0.4s sleep.
for t in ISTJ ISFJ INFJ INTJ ISTP ISFP INFP INTP ESTP ESFP ENFP ENTP ESTJ ESFJ ENFJ ENTJ; do
  curl -fsS --max-time 30 -o $WIKI/raw/articles/mbti/${t}-per.html \
    "https://personalitypage.com/html/${t}-per.html"
  sleep 0.5
done
```

**Verified session (2026-07-28):** 16-MBTI ingest. Worker wrote 16 concept pages but skipped the raw step. Parent session ran a 90-second Python ingest script (with size-check + sleep) into the correct directory. The wiki now has 16 HTML files (79-97 KB each, sha256-hashed) AND 16 concept pages AND `index.md` references AND `log.md` entry — all 4 deliverable components intact.

**Anti-pattern:** telling the worker "you also need to write the raw files" and re-dispatching. The worker will time out at the same place. Parent-session recovery is faster AND avoids losing the worker's well-formed concept pages.