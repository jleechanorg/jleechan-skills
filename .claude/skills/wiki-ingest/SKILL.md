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

# Create the publish branch NOW, while the tree is still clean. Phases 2-8 edit files, so a
# branch cut later would either abort on local changes or carry them across.
set -e
BRANCH="wiki-ingest/$SLUG"
git -C "$WIKI_ROOT" fetch origin main
git -C "$WIKI_ROOT" ls-remote --exit-code --heads origin "$BRANCH" >/dev/null 2>&1 \
  && { echo "origin/$BRANCH already exists; pick a new slug" >&2; exit 1; }
git -C "$WIKI_ROOT" switch -c "$BRANCH" origin/main
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

The publish branch already exists and is checked out (Phase 1), so this phase only
commits, pushes and opens the PR. Never push `main`.

**Precondition:** this checkout is not being written by another ingest. `raw/` and
`wiki/index.md`/`wiki/log.md` are shared paths, and `git add` takes a file's whole current
contents, so two concurrent ingests cannot be separated once their edits are mixed. If
the checkout is shared, use a separate clone.

Stage exactly the paths this run wrote. `SOURCE` keeps the source file's extension while
`SLUG` strips it, so the raw copy is `$SOURCE`, not `raw/$SLUG`:

```bash
PATHS=("$SOURCE" "$WIKI_ROOT/wiki/sources/$SLUG.md" \
       "$WIKI_ROOT/wiki/index.md" "$WIKI_ROOT/wiki/log.md")
# add each entity/concept page this run wrote
```

Commit those paths explicitly — `git commit` with no paths commits the *entire* index,
including anything a previous run left staged:

```bash
set -e
git -C "$WIKI_ROOT" add -- "${PATHS[@]}"
git -C "$WIKI_ROOT" diff --cached --quiet -- "${PATHS[@]}" \
  && { echo "nothing staged for this ingest" >&2; exit 1; }
git -C "$WIKI_ROOT" commit -m "<cli>/<model>: docs(wiki): ingest $SLUG" -- "${PATHS[@]}"
```

Push, verify that exact commit landed, and only then open the PR. Verify before creating
the PR, and require nonempty values — `test "$A" = "$B"` is true when both are empty,
which is what a failed push plus a failed lookup produces. `gh` has no `-C` flag:

```bash
COMMIT="$(git -C "$WIKI_ROOT" rev-parse HEAD)"
git -C "$WIKI_ROOT" push origin "$BRANCH"
REMOTE="$(git -C "$WIKI_ROOT" ls-remote origin "refs/heads/$BRANCH" | awk '{print $1}')"
[ -n "$REMOTE" ] && [ "$REMOTE" = "$COMMIT" ] \
  || { echo "push did not land $COMMIT (remote='${REMOTE:-none}')" >&2; exit 1; }
(cd "$WIKI_ROOT" && gh pr create --base main --head "$BRANCH" --fill)
```

Note in the PR body when this run did not update the shared index or log. Leaving the
checkout on `$BRANCH` is fine; return to the previous branch only if the caller needs it.

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
