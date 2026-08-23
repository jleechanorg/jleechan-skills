---
name: worldai-campaign-to-google-doc
description: Consolidate all artifacts for a your-project.com campaign module — the world_reference/ markdown files (V1 campaign bible + V1/V2 god-mechanics specs + Faerûn pantheon docs), its live GitHub PR, the Gemini share-link source, and any $PROJECT_ROOT/ code references — into a single shareable Google Doc. Use when the user says "put everything for [campaign] in a Google Doc", "update the existing one — don't miss anything", "consolidate the [campaign] doc", or asks for a single shareable artifact. Also fires for **edit-existing-campaign-doc** when the user wants to strip historical/audit content, fix a canonical fact, or apply LLM-input hygiene to an existing campaign doc ("remove historical stuff", "fix the king", "no scar on her nose"). Not for designing a new campaign (campaign-bible-design), not for exporting a prod Firestore campaign (download-campaign), not for reading an existing Google Doc (google-credentials-fallback).
---

# worldai-campaign-to-google-doc

Consolidate every artifact attached to a your-project.com campaign into one Google Doc. Verified 2026-07-21 on the God of Murder / Sanguine Architecture case: produced a 104 KB / 1,479-line / ~16,000-word doc covering 4 stitched source files + PR link + Gemini source attribution, in a single `gog docs write --replace --markdown -f` call.

## When to fire

- User asks to "put everything for [campaign] in a Google Doc"
- User asks to "update the existing one — don't miss anything"
- After iterative V1→V2 design work on a world_reference/ module where the user now wants ONE shareable artifact
- After a multi-PR campaign (e.g. PR #8483 V1 module + PR #8488 V2 overlay) where the diff is hard to follow across branches
- When the user names a specific campaign that has accumulated sibling docs (`*_v1.md`, `*_v2.md`, `*_pantheon.md`, `*_spec.md`)
- **Edit-existing campaign doc:** user says "remove historical stuff", "strip the audit / provenance / PR references", "fix the king / date / name", "no scar / no facial mark", "make it LLM-input only", "drop the v1-v8 references", "this is just campaign content not a design audit". The campaign doc is being treated as LLM input (the source that the gameplay prompt layer reads), not as a design audit trail. Hygiene edits apply.
- **Rebuild from canonical source:** user says "rebuild the Doc from the canonical bible source", "rebuild from the canonical source, removing orphan duplicate content", "the prior subagent left orphan content in the Doc, fix it", or otherwise asks for a single-source overwrite. See Step 4d.

## Anti-triggers (do NOT fire this skill)

- **Designing a NEW campaign** → `campaign-bible-design` (runs brainstorming → writes design doc)
- **Exporting a prod Firestore campaign** → `download-campaign` (downloads FROM Firestore TO disk)
- **Analyzing existing campaigns** → `wa-campaign-content-analysis` (per-scene content classification)
- **Reading an existing Google Doc the user shared** → `google-credentials-fallback` (use `gog docs info` + `gog docs export --format txt`)
- **Iterating on campaign design** → `campaign-design-iteration` (next-version design loop)
- **Pure prompt / $PROJECT_ROOT/ fixes** for a campaign (e.g. fixing a prompt file that already references the campaign) → use the relevant prompt-engineering skill, not this one

## Class-level scope

This skill handles the recurring pattern: your-project.com campaign modules grow across multiple PRs (V1 module + V1 general spec + V2 overlay + setting-specific specialization). The user wants the stitched artifact in a Google Doc for sharing / cross-platform review / provenance. The skill covers any campaign in `$GITHUB_REPOSITORY/world_reference/` — God of Murder, Visenya, Alexiel, Inheritor, Steel Jedi, Year of Four, Heat Detective, Dragon Knight, Luke, Daenerys, Merchant Queen, Shattered Rose, etc.

## Workflow (8 steps)

### Step 1 — Identify the campaign + its artifact inventory

Run parallel:
- `gh pr list --repo $GITHUB_REPOSITORY --state all --search "<campaign keyword>" --json number,title,state,url,headRefName,createdAt,mergedAt`
- `gh pr view <number> --json title,state,headRefName,additions,deletions,changedFiles,files` (one per matching PR)
- `git -C <worktree> diff origin/main..HEAD --name-only` (for the live branch state)
- `ls -la <worktree>/world_reference/` (for the canonical source files)

**Output:** a numbered list of every file that belongs to the campaign. Group into:
- Campaign bible (`world_reference/campaign_module_*.md`)
- V1 mechanic specs (`*_general.md`, `*_v1.md`)
- V2 mechanic specs (`*-v2-*.md`)
- Setting-specific specializations (`*_faerun*.md`, `*_nocturne*.md`)
- Sibling $PROJECT_ROOT/ code references (`campaign_divine.py`, `god_mode_level_up.py`, `constants.py`, `tests/test_*.py`)
- Gemini share link source (e.g. `https://share.gemini.google/Td7fA4pzuvMs`)

### Step 2 — Find the worktree with the live files

```
git worktree list | grep -i "<campaign keyword>"
```

If multiple matches, pick the most recent by HEAD SHA. If none, check `~/projects/wt-<campaign-keyword>` and `$HOME/.worktrees/<campaign-keyword>`. Per `dark-factory-canonical-locations` COMMIT, scan ALL canonical locations (~/projects/, $HOME/.worktrees/, /private/tmp/) before declaring "no worktree."

### Step 3 — Read every artifact end-to-end

Read each file via `read_file` to offset+limit until truncated = false. Critical: don't skip files just because they look like "more spec." Each one carries unique state that the user asked for ("don't miss anything").

### Step 4 — Check for an EXISTING Google Doc

```
gog drive ls -j | python3 -c "..."
```

Search the response for the campaign name (case-insensitive, partial match). If a doc exists, get its ID via `gog drive ls -j | jq '.files[] | select(.name | test("<campaign>"; "i")) | {id, name}'`.

**Decision branch — DO NOT default to overwrite.** Before proceeding, classify the existing doc against the canonical campaign module:

- **Doc exists, content matches the campaign bible, smaller than the merged PR module** → safe to `--replace --markdown -f <stitched>` overwrite.
- **Doc exists, content is structurally richer than the merged PR** (more sections; includes Personality / Family / Open-PRs; sourced from a brainstorm session rather than the PR) → **DO NOT overwrite.** This is the design-spec artifact from before the PR was drafted. Overwriting would *lose* content. Report the diff to the user and offer three options: (a) leave as-is, (b) refresh from the PR (lose sections), (c) stitch-and-replace (PART 1 = merged PR module + PART 2 = existing doc design spec + provenance footer).
- **Doc exists, content is a stale prior version of the same artifact** (e.g. merged PR has new sections the doc lacks) → `--replace --markdown -f <stitched>` is correct.
- **No doc found** → continue to Step 5.

**How to classify:** `gog docs cat <docId> | wc -lc` (size), `gog docs cat <docId> | grep -cE "^Section |^PART "` (section count). Compare against `wc -l <worktree>/world_reference/campaign_module_*.md` and `grep -cE "^## |^### " <same file>`. If the doc has more sections than the PR file, suspect "design-spec artifact" — read the first 60 lines to confirm a brainstorm-session header (look for `source_session:`, `authors:`, `date:` in YAML-style frontmatter).

Verified 2026-07-23 on Visenya v9: existing doc was 924 lines / 15 sections from a Slack brainstorm session, while the merged PR #8486 module was 307 lines / 28 headings — both valid artifacts of the same design at different lifecycle stages. Overwriting would have erased Character Personality, Family dynamics, and the Open PRs audit.

### Step 4b — Edit-existing-campaign-doc branch (LLM-input hygiene + canonical-fact fix)

If the user wants to **edit** an existing doc (not consolidate or refresh), the workflow is different from Steps 5-7. Skip Step 5 (don't create new doc) and Step 6 (don't restitch from files). Instead:

1. `gog docs cat <docId> > /tmp/<campaign>_edit.md` — pull the current doc content as the edit source.
2. Apply the edits the user asked for, in this order:
   - **Canonical-fact fixes** (e.g. "the king at this time is Daeron not Viserys"). Verify against an authoritative source before editing — search `jleechanorg/llm-wiki` wiki/concepts/, the campaign's own `world_reference/` module file, or canonical GRRM lore. If you can't verify, surface the ambiguity to the user instead of guessing. Verified 2026-07-23: Visenya v9 doc said "King Jaehaerys II / Viserys sits the Iron Throne" in 209 AC, but `The Hedge Knight` opens with Daeron I alive (he dies at the Ashford tourney that year). Always cross-check 209 AC → Daeron, 298 AC → Aerys II or Robert Baratheon (depends on year), etc.
   - **LLM-input hygiene strip** — drop any block that is *audit trail*, not campaign content. Use `execute_code` with a single Python pass. Block types to strip (with regex):
     - YAML frontmatter (`^title:`, `^type:`, `^date:`, `^status:`, `^authors:`, `^related:`, `^references:`, `^source_session:`)
     - "Exit Criteria" / "Done when" / "Spec Self-Review" / "Placeholder scan" / "Source accuracy check" / "Internal consistency" blocks
     - "Open PRs In Flight" tables (PR #XXXX, Issue #XXXX columns)
     - Provenance / SHA / wiki-link footer blocks
     - "End of <X> Spec. Awaiting user review at..." trailing lines
     - Section prefaces that link the spec back to WA issues/PRs (e.g. "This section describes what the prompt layer / agent layer must NEVER do — the durable invariants v9 requires from the WA harness")
     - Guardrails tables that have a `WA Reference` column (PR #XXXX link) → convert to bullet list, drop the audit column
   - **Cross-version hygiene** — drop any "V1-V8" / "replaces v6's X" / "pivot from social geometry to physical geometry" / "v1-v8 made Visenya a godling puppeteer" framing. Even in-universe names like "V6-Visenya" are version labels; rename to "the First Song" / "her older self" / "an older world" / "by her calendar" if the in-universe elder self is referenced. Keep references to the campaign's own version name (e.g. "v9 homebrew" stays — it's the current campaign name).
   - **PC-appearance hygiene** — never add facial scars, missing limbs, disfigurement, or "ugly" descriptors to a player character unless the user explicitly asks. The user has stated: Visenya is "extremely beautiful". Replace any scar/disfigurement on a PC with an emphasizer of beauty. PC visual defects only land if the user types them explicitly (e.g. "give her a scar" / "she's missing an eye").
3. **Apply the same edits to the merged PR module file** (`world_reference/campaign_module_<campaign>.md`) so the doc and the canonical source stay in sync. Doc is downstream; module is upstream.
4. Run a final pass: `grep -in -E "Viserys|Jaehaerys|scar|v1-v8|V6-Visenya|replaces v6|End of .* Spec|Exit Criteria|self_review|Self-Review" /tmp/<campaign>_edit.md` should return only matches the user explicitly wants to keep.
5. Write back: `gog docs write <docId> --replace --markdown -f /tmp/<campaign>_edit.md`.
6. Stage the merged module file edit on a fresh `git stash` so it doesn't pollute the active worktree. Do NOT push to the current branch — it's mid-flight on a different PR.

### Step 4c — Out-of-band corrections during edit (also applies to rebuild)

When the user sends an `[OUT-OF-BAND USER MESSAGE]` mid-edit (a refinement they didn't pre-declare, e.g. "don't talk about older versions" or "remove the scar"), treat it as an additional edit pass in the same `gog docs write --replace --markdown` cycle. Do NOT split into multiple writes — one replace keeps the doc atomic. Apply the new edit to the in-memory markdown string, then re-verify against your grep checklist before the final write.

Verified 2026-07-23: two OOB refinements arrived in succession on the Visenya v9 edit (version hygiene + scar removal). Both were applied to the same `/tmp/v9_doc_cleaned_v4.md` buffer before the single `gog docs write --replace --markdown -f` call.

### Step 4d — Rebuild-from-canonical-source branch (single-file overwrite)

When the task is to **rebuild the Doc from a single canonical source** (e.g. "rebuild from the canonical bible source, removing orphan duplicate content"), the workflow is even simpler than Step 4b. Skip Step 4b (no edit list to apply) and skip Step 5 (the Doc already exists):

1. **Verify the orphan content exists** — `gog docs cat <docId>` and search for the specific orphan patterns the user described. If none found, note this in the final reply (see Pitfall #22) but continue with the rebuild.
2. **Identify the canonical source** — typically `world_reference/campaign_module_<campaign>.md`. Verify with `find . -name 'campaign_module_<campaign>*.md'` and confirm the SHA256 matches the latest commit on `origin/main`. Never modify the source.
3. **Backup the current Doc** — `gog docs cat <docId> > /tmp/<campaign>_doc_before.txt` so the pre-fix state is recoverable.
4. **Stage the source as input** — `cp <source> /tmp/<campaign>_doc_input.md`. No transformations; the source goes in as-is.
5. **Write the rebuild in one call** — `gog docs write <docId> --replace --markdown -f /tmp/<campaign>_doc_input.md`. The `--markdown` flag renders headings/lists/tables in Google Docs native formatting. The `--replace` flag overwrites (NOT append — see Pitfall #1).
6. **Verify post-fix** — `gog docs cat <docId>` then `grep -nE '^(Section \d+:|Notes Appendix|DM Notes|Provenance)'` to confirm all expected section headings are present and in correct order. Cross-reference heading count against the source's `grep -cE '^## (Section \d+:|Notes Appendix|DM Notes|Provenance)' <source>`.

Verified 2026-08-01 on Nocturne Ravencrest: doc was rebuilt from `world_reference/campaign_module_nocturne_deceiver.md` (188,642 bytes) in a single `--replace --markdown -f` call. Pre-fix doc was 169,302 bytes / 1,249 lines (already faithful); post-fix doc is 180,385 bytes / 1,755 lines (canonical with proper Google Docs headings/lists/tables rendered).

### Step 5 — Create the new Google Doc

```
gog docs create "<Campaign> — <Subtitle> + God Mechanics V1+V2" 2>&1
```

Note the new doc ID from the response. The `--replace` flag in Step 7 will overwrite any prior content, so you can safely use the same title for updates.

**Title conventions:**
- God of Murder → "God of Murder — Sanguine Architecture + God Mechanics V1+V2"
- Visenya → "Visenya Campaign Bible — V<n> + Mechanics Spec"
- For any campaign: "<Campaign Name> — <One-Line Pitch> + All Mechanics Versions"

### Step 6 — Stitch the master markdown

Use `execute_code` (Python) to:
1. Read each source file into memory.
2. Replace the leading `# Title` line of each with `# PART N — <Subtitle>\n\n*<One-line description of which part this is>.*` — preserves the original content, just adds a part header.
3. Concatenate: header (with TOC) + Part 1 + separator + Part 2 + separator + ... + footer (provenance + recommended next iterations).

**Verified size ceiling:** 104,339 bytes / 1,479 lines / ~16,000 words in a SINGLE `gog docs write` call worked. Above ~120 KB or ~2,000 lines, expect to chunk via multiple `gog docs insert` calls (rare; only if the campaign is enormous).

**Section structure (4-PART template):**
```
# <Campaign Name> (with subtitle)
*Last updated: <date>. Compiled from <worktree-path>.*

[Purpose paragraph]
[Source conversation link if Gemini share]
[GitHub PR link if there's a live PR]

# TABLE OF CONTENTS
1. PART 1: <campaign bible>
2. PART 2: <V1 mechanic spec>
3. PART 3: <V2 mechanic spec / overlay>
4. PART 4: <setting-specific specialization>

---
# PART 1 — The Campaign Bible (<setting> specific)
<file contents, with leading # replaced>

---
# PART 2 — <V1 spec title>
<file contents, with leading # replaced>

[...]

---
# PROVENANCE & NEXT STEPS
- SHA for each source file
- PR links
- Companion $PROJECT_ROOT/ files
- Wiki source mirror
- Recommended next iterations
```

### Step 7 — Write to Google Doc in ONE call

```
gog docs write <docId> -f /tmp/<campaign>_master_doc.md --replace --markdown
```

Use `--replace` to overwrite (append is the default — wrong here). Use `--markdown` to convert headings/lists/tables to Google Docs formatting (requires `--replace`). Use `-f` to stream from disk rather than passing content as argv (avoids shell escaping issues with backticks/quotes in the markdown).

**Verify the write succeeded:**
```
gog docs info <docId> | head -20
gog docs cat <docId> | wc -l
gog docs cat <docId> | grep -c "PART "
```

The grep should return the count of PART headers you added (typically 4).

### Step 8 — Post back to Slack

Use `mcp_slack_conversations_add_message` to the originating thread (channel ID + thread_ts from the user's message). Reply must include:
- **PR link** — full markdown hyperlink (not bare `#8488`), per `pr-hyperlink` rule
- **Doc link** — full URL
- **Doc stats** — KB / lines / words / PART count
- **Artifact table** — every source file mapped to its section in the doc, with SHA
- **Verification status** — `gog docs cat` confirms content landed
- **`🧠 Memories used:` line** — per `response guardrail` (always-on)

Then create a 20-minute status cron via `cronjob(action='create', deliver='slack:<channel>', schedule='20m', ...)` per `one-time-status-cron-after-every-task`. Cron job ID goes in the reply.

## Pitfalls (verified, do not skip)

### Pitfall #1 — `--replace` is required, not the default

`gog docs write` defaults to APPEND. If you skip `--replace`, the second call adds to the first call's content. The 4-PART doc will end up doubled or tripled. Always use `--replace --markdown -f`.

### Pitfall #2 — `gog docs write` needs `-f <path>`, not argv content

Passing the full 104 KB markdown as the `<content>` arg causes shell escaping failures on backticks (`HP×5.4 → DR`) and quotes (`"calculations which don't mean much"`). Use `-f /tmp/<file>` and let gog stream from disk.

### Pitfall #3 — `gog docs write --markdown` REQUIRES `--replace`

The `--markdown` flag (which converts `# headings`, tables, lists, etc. to Google Docs formatting) only works with `--replace`. Without `--replace`, the markdown stays as literal text. Both flags together is the magic combo.

### Pitfall #4 — `gog drive ls` returns 20 items per page

First call shows the 20 most recent files. If the campaign doc was created >20 files ago, you won't find it on page 1. Check `nextPageToken` in the response, fetch more pages, OR create a new doc with a known-good title (safe because of `--replace` overwrite).

### Pitfall #5 — DRIVE `ls` only shows top-level files (no folder recursion)

If the doc lives in a subfolder (e.g. `$USER@gmail.com Drive > Campaigns > 2026/`), `gog drive ls` won't find it. Use `gog drive ls --folder <folderId>` recursively, OR just create a new top-level doc.

### Pitfall #6 — "Don't miss anything" means EVERY file in the worktree

The user said "don't miss anything" — they meant EVERY artifact, not just the headline campaign bible. Read each `*_general.md`, `*_v2-*.md`, `*_faerun*.md` separately and add a PART for each. Skipping files = the user will find the gap and be frustrated.

### Pitfall #7 — Gemini source link must be in the header, not buried

The Gemini share URL is the upstream design source. Put it in the header block under "Source conversation:" so future readers can trace the design history without grepping the doc body.

### Pitfall #8 — Include SHA + PR link in provenance footer

The user will eventually want to verify the doc matches `origin/main`. Embed SHA + PR link + branch name + merge commit in the footer. Verified pattern:

```
- **Campaign module SHA:** `world_reference/campaign_module_god_of_murder.md` @ HEAD `48472d7ed7` (PR #8488)
- **V1 general spec SHA:** `world_reference/god_mechanics_general.md` @ HEAD `48472d7ed7` (PR #8488)
```

### Pitfall #9 — Don't fabricate content for missing files

If a referenced file doesn't exist (e.g. user says "update the Nocturne V2 doc" but the file is only at `world_reference/nocturne-v2-god-mechanics-design.md`, not at the path the user named), say so in the reply. Don't invent placeholder text labeled "TBD" — that's fabrication. Verify with `ls` first.

### Pitfall #10 — The `dark-factory-canonical-locations` COMMIT applies

The campaign module's source-of-truth lives in a specific worktree, NOT in your checkout dir. Use `git worktree list` to find it. If you read from the wrong dir, you'll get stale content from the previous PR.

### Pitfall #11 — `gog docs info` returns revision ID but not content size

The `revision` field in `gog docs info` is a Google-side revision ID (not your content size). To verify content size, use `gog docs cat <docId> | wc -lc` instead.

### Pitfall #12 — Markdown tables with `|` separators work via `--markdown`

Tables in the markdown survive the `--markdown` conversion. The 4-doc God of Murder master had ~20 tables (stat blocks, faction dissonance, ascension tiers) and they all rendered correctly. Don't bother pre-converting tables to plain text.

### Pitfall #13 — Don't use `gws docs` for personal shared docs

Per `google-credentials-fallback` skill, `gws docs` 403s on personal shared docs (service-account auth scope). Use `gog` exclusively — `gog` uses $USER@gmail.com personal OAuth and works for both creating AND reading personal docs.

### Pitfall #14 — Slack reply must use full markdown hyperlinks (not bare `#N`)

Per `pr-hyperlink` rule: every PR number must be `[#N](https://github.com/OWNER/REPO/pull/N)`, never bare `#N`. Same for the Doc URL — paste the full `https://docs.google.com/document/d/<id>/edit` link.

### Pitfall #15 — Cron `deliver` target must be `slack:C0XXXXXXXXX` (channel ID)

Per `one-time-status-cron-after-every-task`: `--deliver 'slack:C0AH3RY3DK6'` (channel ID), not `slack:#worldai` (channel name). The cron resolver expects the ID format.

### Pitfall #16 — An existing Google Doc may be richer than the merged PR module; don't blindly overwrite

The skill assumes "doc exists → overwrite with stitched campaign bible." But campaign docs are often written *before* the PR — the brainstorm session produces a 900-line design spec (Personality, Family, Open PRs audit, etc.), then the PR condenses it to a 300-line campaign bible for `world_reference/`. Both artifacts coexist, and the doc is typically the **richer** one.

Detection: `wc -l` both files. If `gog docs cat <docId> | wc -l` >> `wc -l <worktree>/world_reference/campaign_module_*.md`, suspect the doc is a pre-PR brainstorm artifact, not a post-PR mirror. Read the doc's first 60 lines for `source_session:` / `authors:` / `date:` frontmatter to confirm.

Mitigation: report the diff and offer three options to the user — leave as-is, refresh from PR (lose sections), or stitch-and-replace (PART 1 = PR module + PART 2 = existing doc design spec). Do NOT auto-overwrite. Verified 2026-07-23 on Visenya v9: doc was 924 lines / 15 sections from Slack `C0AH3RY3DK6/p1784584425.185909`; PR #8486 module was 307 lines / 28 headings. Auto-overwrite would have erased 600+ lines of design rationale.

### Pitfall #17 — "It's just LLM input only" means strip every audit/provenance block

Jeffrey's explicit stance (verified 2026-07-23): campaign docs are read by the gameplay prompt layer as raw narrative input. The doc is NOT a design audit. Strip:

- YAML frontmatter (title/type/date/status/authors/related/wiki/references/source_session)
- "Exit Criteria" / "Done when" / "Spec Self-Review" / "Source accuracy check" blocks
- "Open PRs In Flight" tables (PR #XXXX columns)
- Provenance / SHA / wiki-link footer blocks
- "End of <X> Spec. Awaiting user review at..." trailing lines
- Section prefaces that link the spec back to WA issues/PRs

Detection: search the doc for `^title:`, `^date:`, `Exit Criteria`, `Spec Self-Review`, `Open PRs`, `$GITHUB_REPOSITORY`, `wiki/sources/`, `wiki/concepts/`, `SHA`, `Provenance`. Each match is a strip candidate.

Don't strip: campaign content (campaign concept, personality, family, mechanics, guardrails, endings, starting scenes). The guardrail *definitions* stay; only the audit columns (Status, WA Reference) drop. Verified 2026-07-23 on Visenya v9: doc dropped from 924 → 387 lines after hygiene pass; 0 Viserys/Jaehaerys, 0 V6 / 0 v1-v8, 0 scar on PC, all 14 content sections intact.

### Pitfall #18 — Canonical-fact errors in the doc must also be fixed in the merged PR module file

The campaign doc and the `world_reference/campaign_module_<campaign>.md` file should be in sync — both are read by the LLM as campaign input. If you fix a wrong king / wrong date / wrong name in the doc but leave the merged module file unchanged, the LLM gets contradictory inputs depending on which artifact the prompt layer samples.

Verified 2026-07-23 on Visenya v9: doc said "King Jaehaerys II / Viserys" in 209 AC; merged module file said the same. Both wrong — Daeron I is on the throne in 209 AC until the Ashford tourney. Fixed both with the same `patch` calls (line 3 + line 13 in the module file; lines 33 + 421 in the doc).

Always cross-check before editing:
- 209 AC (year of *The Hedge Knight*) → **Daeron I** (dies at Ashford)
- 282 AC → Maekar I on throne
- 298 AC (Rhaegar-wins timeline) → depends on the divergence point
- 129 AC → Viserys I (Dance of the Dragons) or Aegon II / Rhaenyra
- Slaver's Bay dates → Daenerys (≈298-300 AC)

If unsure, surface the ambiguity to the user — don't guess.

### Pitfall #19 — Don't add scars, disfigurement, or "ugly" details to a player character

Player characters in world_reference/ are aspirational figures — Visenya, Alexiel, Daenerys, Luke, etc. are *iconic*. The user has stated explicit preferences:

- Visenya is "extremely beautiful". Never put a facial scar / missing eye / burn mark on her without explicit instruction.
- Same for any PC: PC visual defects land only if the user types them in.

If the existing doc / module has a scar / mark / disfigurement on a PC, treat it as an *artifact of a prior author* and strip on edit. Replace with an emphasizer of beauty / presence / power. Retainer / NPC scars are fine (Ser Tommard Heddle's scar stayed in the Visenya v9 doc — he's a secondary character, not a PC).

Verified 2026-07-23: "A thin, white scar across the bridge of her nose" on Visenya → "A face that has never once been touched — angular, severe, the kind of beauty that makes a room go quiet when she walks in".

### Pitfall #20 — Don't leak cross-version framing into in-universe content

The user has stated: "Don't talk about older versions of the campaign." That means:

- Strip V1-V8 / v1-v8 / "replaces v6's X" / "v6 mirror mechanic" / "pivot from social to physical geometry" framing in narrative prose.
- Drop "(V6-Visenya, ~298 AC in her world)" parenthetical labels — even when V6-Visenya is the in-universe elder self. Rename to "the First Song" / "her older self" / "by her own calendar" / "an older world". The version label is a design-history artifact; the narrative doesn't need it.
- KEEP: the campaign's own version name (e.g. "v9 homebrew" stays — it's identifying the current campaign). Stripping "v9" from a header would be wrong; it just becomes unlabeled.
- KEEP: in-universe elder-self references that don't carry a version label ("the First Song", "the elder Visenya", "her older self").

Verified 2026-07-23: doc went from 9 v1-v8 references + 10 V6 references → 0 v1-v8 + 0 V6 in narrative prose. Module file: 0 v1-v8 + 0 V6. The 4 remaining "v9" mentions in the doc are the campaign's own name (e.g. "Visenya v9 — Hard Guardrails").

### Pitfall #21 — Module file edits don't auto-push; stash on the active branch

When the active worktree is mid-flight on a different PR (e.g. `pr8399-w2verify` with 110 files / +2178/-14156 already changed), committing the v9 doc-only edit to that branch pollutes it. The v9 module file edit is on a *separate topic*.

Mitigation: `git stash push world_reference/campaign_module_<campaign>.md -m "<campaign> <topic> edits (staged for fresh PR)"`. The edit is preserved in the stash; the working tree returns to the active PR's state. When the user approves pushing as a fresh PR:

```bash
git checkout -B docs/<campaign>-<topic>-cleanup origin/main
git stash pop  # if only this file is in the stash
# OR: git stash show -p stash@{0} | git apply
git add world_reference/campaign_module_<campaign>.md
git commit -m "docs(world_reference): strip audit trail + fix canonical fact (<campaign> <topic>)"
git push origin HEAD:refs/heads/docs/<campaign>-<topic>-cleanup
~/.hermes/scripts/gh-safe-publish pr create --base main --title "..."
```

Verified 2026-07-23 on Visenya v9: stash landed on `pr8399-w2verify` cleanly without polluting the active PR's diff stat.

### Pitfall #22 — A pre-existing bug in the source-of-truth file must be preserved in the Doc

Some `world_reference/campaign_module_*.md` files have pre-existing bugs (duplicate letter labels in appended lists, broken numbering, etc.) that the canonical author has not yet fixed. Per "Do NOT modify the source bible file. It is the truth" — when rebuilding the Doc from source, preserve these bugs verbatim. Do NOT silently fix them in the rebuild (the LLM-input layer reads both Doc and source; a divergence will trigger contradiction checks).

Verified 2026-08-01 on Nocturne Ravencrest: source bible's Notes Appendix labeled its last bullet `(g)` even though the prior `(g)` was Sovereign Decoupling (it should have been `(l)`). The Doc was rebuilt with the duplicate `(g)` preserved. The canonical fix lives with the source author, not the doc-builder.

Detection: after rebuilding, `grep -nE '^\* ?\([a-z]\)' <doc>` and visually scan for duplicates. Report any pre-existing source bugs to the user in the final reply so they're aware — but do NOT auto-fix.

### Pitfall #23 — "Rebuild from canonical source" can be the right pattern even when the Doc looks clean

The parent task may describe orphan content (stray headings, partial sentence fragments) that no longer matches the current Doc state. Don't refuse the rebuild on those grounds — the orphan content may have been cleaned up between task-creation and execution, OR the description may be stale. Always verify with `gog docs cat` first, then if no orphan content is found AND the user explicitly said "rebuild from canonical source," still do a full overwrite (`gog docs write --replace --markdown -f <source>`) to guarantee canonical state. The cost is one overwrite; the value is removing ambiguity about which Doc state is canonical.

Verified 2026-08-01 on Nocturne Ravencrest: the pre-fix Doc was 1,249 lines / 169 KB and structurally matched the source bible (13 sections, no orphan duplicate headings, no orphan sentence fragments). Despite the lack of orphan content, the user asked for a rebuild — and the rebuild landed cleanly at 1,755 lines / 180 KB via a single `--markdown --replace -f` call.

### Pitfall #24 — Single-source rebuild ≠ multi-PART stitch

The 4-PART stitch template (Step 6) is for consolidating MULTIPLE artifacts (V1 module + V1 spec + V2 overlay + setting specialization). A single-source rebuild (one `world_reference/campaign_module_*.md` → one Google Doc) does NOT need PART headers, a stitched TOC, or a provenance footer block beyond what the source already carries. Just `cp` the source to `/tmp/<campaign>_doc_input.md` and `gog docs write --replace --markdown -f /tmp/<campaign>_doc_input.md`. Adding PART 1 / PART 2 scaffolding to a single-source rebuild is over-engineering and changes the canonical structure.

## Verification checklist

Before posting completion to Slack, verify ALL of:

- [ ] `gog docs info <docId>` returns the doc + revision ID
- [ ] `gog docs cat <docId> | wc -l` shows the expected line count (~1,400-1,500 for a 4-doc stitch)
- [ ] `gog docs cat <docId> | grep -c "PART "` returns the expected PART count (typically 4)
- [ ] `gog docs cat <docId> | head -20` shows the header + TOC
- [ ] `gog docs cat <docId> | tail -20` shows the provenance footer
- [ ] Slack thread reply includes PR link + Doc link + artifact table + memory citation
- [ ] Cron job ID (`934cf6bee234` style) is in the reply + posted to correct channel
- [ ] `gog docs export <docId> --format txt` round-trips cleanly (optional sanity check)

**Pre-overwrite check (Step 4):** if a doc already exists for this campaign, confirm its size + section count against `wc -l <worktree>/world_reference/campaign_module_*.md` BEFORE running `gog docs write --replace`. If the doc is larger / has more sections than the PR module, surface the diff to the user — don't auto-overwrite (Pitfall #16).

## Cross-references

- **Loaded skill `google-credentials-fallback`** — covers `gog docs info` + `gog docs export --format txt` for READING personal shared docs. This skill covers WRITING large consolidated docs.
- **Loaded skill `campaign-bible-design`** — runs superpowers brainstorming to DESIGN a new campaign. This skill stitches EXISTING artifacts into a shareable doc.
- **Loaded skill `download-campaign`** — exports a prod Firestore campaign to disk. This skill inverts: takes DISK campaigns and pushes them to a Google Doc.
- **Loaded skill `campaign-design-iteration`** — designs next-version of a recurring campaign. This skill is the cross-platform-share step AFTER iteration work completes.
- **SOUL.md `pr-hyperlink` rule** — every PR number must be a full markdown hyperlink.
- **SOUL.md `dark-factory-canonical-locations`** — find the right worktree before reading source files.
- **SOUL.md `one-time-status-cron-after-every-task`** — arm a 20m follow-up cron for every Slack-posted task.

## Reference files

- **`references/gog-docs-write-recipe.md`** — verified gog CLI flags + size limits + `--markdown` table rendering behavior (created this skill version)
- **`references/four-part-stitch-template.md`** — copy-paste-ready markdown template for the 4-PART header + TOC + provenance footer (created this skill version)
