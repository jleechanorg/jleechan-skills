---
name: wiki-ingest
description: Ingest a file into the local LLM wiki and update source/entity/concept pages.
---

# /wiki-ingest — Ingest a file into the LLM Wiki

## Usage
```
/wiki-ingest <file_or_path> [--wiki <wiki_dir>]
```

Ingest a source document into the wiki. Creates a source page, extracts entities and concepts, updates the index.

`--wiki <wiki_dir>` overrides the default wiki location (`~/llm_wiki/wiki`). The `raw/` directory is derived as the sibling of the wiki dir: `$(dirname <wiki_dir>)/raw`.

## Execution

### Phase 1: Resolve wiki path and source file
```bash
# Parse args: file is first positional; --wiki <path> overrides default
# Check for local wiki default (project-level override)
if [ -f ".wiki-default" ]; then
  WIKI=$(cat .wiki-default)
elif [ -f "$HOME/.wiki-default" ]; then
  WIKI=$(cat "$HOME/.wiki-default")
else
  WIKI="$HOME/llm_wiki/wiki"
fi
FILE_ARG="<first positional arg>"
# --wiki flag always wins over .wiki-default
if args contain "--wiki <path>"; then
  WIKI="<path>"
fi

WIKI_ROOT=$(dirname "$WIKI")
RAW_DIR="$WIKI_ROOT/raw"
SOURCE="$RAW_DIR/$(basename "$FILE_ARG")"

# Copy source to raw/ if not already there
mkdir -p "$RAW_DIR"
cp "$FILE_ARG" "$SOURCE" 2>/dev/null || cp "$(pwd)/$FILE_ARG" "$SOURCE"

# Determine slug from filename
SLUG=$(basename "$FILE_ARG" | sed 's/\.md$//' | sed 's/[^a-zA-Z0-9]/-/g' | tr '[:upper:]' '[:lower:]')
```

### Phase 2: Read source document
Read the file fully.

### Phase 3: Read wiki context
Read `wiki/index.md` and `wiki/overview.md` for current wiki state.

### Phase 4: Create source page
Write `wiki/sources/<slug>.md` using Source Page Format:

```markdown
---
title: "<title>"
type: source
tags: []
date: YYYY-MM-DD
source_file: <relative path>
---

## Summary
2–4 sentence summary.

## Key Claims
- Claim 1
- Claim 2

## Key Quotes
> "Quote here" — context

## Connections
- [[EntityName]] — how they relate
- [[ConceptName]] — how it connects
```

### Phase 5: Update index
Add entry to `wiki/index.md` under Sources section.

### Phase 6: Oracle impact check
Check if new content affects [[jeffrey-oracle]]. If so, append to `wiki/log.md`.

### Phase 7: Entity & concept extraction
Create entity pages for key people, companies, projects.
Create concept pages for key ideas, frameworks, methods.

### Phase 8: Log
Append to `wiki/log.md`: `## [YYYY-MM-DD] ingest | <Title>`

### Phase 9: Commit and Push

Publish through the wiki repository's own delivery contract — a content branch plus PR —
and never straight to `main`.

Name the exact paths this ingest wrote; never stage the whole tree, because `raw/` and
`wiki/` may hold another session's in-progress work:

```bash
PATHS=("raw/$SLUG" "wiki/sources/$SLUG.md" "wiki/index.md" "wiki/log.md")
git -C "$WIKI_ROOT" add -- "${PATHS[@]}"
git -C "$WIKI_ROOT" diff --cached --quiet || git -C "$WIKI_ROOT" commit -m "<cli>/<model>: docs(wiki): ingest $SLUG"
```

Extend that list with any entity or concept page you created or edited. Then push a
branch and open a PR per that repository's `AGENTS.md`/`CLAUDE.md`, and verify the PR
head matches your commit:

```bash
git -C "$WIKI_ROOT" push -u origin HEAD
gh -C "$WIKI_ROOT" pr create --fill   # or the repository's required PR command
test "$(git -C "$WIKI_ROOT" rev-parse HEAD)" = "$(git -C "$WIKI_ROOT" rev-parse origin/HEAD)" 2>/dev/null || git -C "$WIKI_ROOT" log --oneline -1
```

If `$WIKI_ROOT` sits on a dirty non-`main` branch owned by another session, do not switch
branches and do not publish that branch: create a fresh branch at the remote main tip and
commit only this ingest's paths onto it, so the pushed branch contains this ingest and
nothing else. An alternate `GIT_INDEX_FILE` controls what gets committed, not which
commits are already on the branch you push.

## GitHub-Readable Output — TOC + Standard Markdown Links (default for ported-source branch)

When a ported-source page will be published to GitHub (gist, repo, or any non-Obsidian viewer), GitHub does **not** render `[[WikiLinks]]` as clickable — they show up as literal `[[brackets]]`. Default behavior for any ported-source ingest that touches a GitHub-rendered surface:

1. **Add a Table of Contents** at the top of the document, after the metadata block, with anchor links to every major heading. Format:
   ```
   ---

   ## Table of Contents

   1. [Setup & Cast](#setup--cast)
   2. [Beat 1 — The Rat Summoning](#beat-1--the-rat-summoning)
   ...
   ```

2. **Convert all `[[WikiLinks]]` to standard `[label](url)` markdown links** pointing to the canonical GitHub raw URL for the target page. Slug → URL map should be built up front based on the page tree under `wiki/`. Example:
   ```python
   wiki_url = "https://github.com/jleechanorg/llm-wiki/blob/main"
   wiki_link_map = {
       "HestiaRegistrar":  f"{wiki_url}/wiki/entities/hestia-registrar.md",
       "VerminCommander":  f"{wiki_url}/wiki/concepts/vermin-commander.md",
       "VoyagePlatform":   f"{wiki_url}/wiki/concepts/voyage-platform.md",
   }
   new_text = re.sub(r"\[\[([^\]]+)\]\]",
       lambda m: f"[{m.group(1).split('|')[-1]}]({wiki_link_map.get(m.group(1).split('|')[0], f'{wiki_url}/wiki/{m.group(1)}.md')})",
       src)
   ```

3. **Preserve `[[WikiLinks]]` in the Obsidian-side copies** (the `~/llm_wiki/wiki/sources/...` page) so they still work in Obsidian/Logseq — only the gist/published GitHub version converts them.

4. **Header metadata block** should include clickable links to the source transcript and the wiki source page when the document is going to a gist or remote repo.

This rule was added 2026-06-13 after the Voyage first-dev-playthrough gist had `[[WikiLinks]]` that didn't render on github.com. Apply by default to any future ported-source ingest.
