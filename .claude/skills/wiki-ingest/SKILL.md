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

Publish through a content branch and PR. Never push `main`, and never publish another
session's work that happens to sit in the same checkout.

Build the file list from values Phase 1 already set — `SOURCE` keeps the source's
extension while `SLUG` strips it, so the raw copy is `$SOURCE`, not `raw/$SLUG`. List
only files this run created:

```bash
PATHS=("$SOURCE" "$WIKI_ROOT/wiki/sources/$SLUG.md")
# add each entity/concept page this run created, e.g.
#   PATHS+=("$WIKI_ROOT/wiki/concepts/<concept>.md")
```

**Do not put the shared files in `PATHS`.** `wiki/index.md` and `wiki/log.md` are edited
by every ingest in the same working tree, and `git diff` cannot tell your edits from a
concurrent session's — it reports that the file differs, not who changed it. Taking those
files from the working tree is therefore unsafe no matter how they are added. Apply this
run's edits to the shared files *inside the scratch index*, starting from the committed
base, so only your lines can be committed:

Patch the two files in the base tree, stage the patched result, and record what you
applied in the PR body. One worked shape, using `git show` + a patch file rather than the
working copy — build the patch after `IDX_DIR` exists (the scratch-index block below
creates it):

```bash
# --- after IDX_DIR is set, before write-tree ---
SHARED_PATCH="$IDX_DIR/shared.patch"
: > "$SHARED_PATCH"
# Build each hunk from the committed base blob, never from the working tree:
#   git show "$BASE:wiki/index.md" > "$IDX_DIR/index.base"
#   { our edit applied to index.base } > "$IDX_DIR/index.new"
#   diff -u "$IDX_DIR/index.base" "$IDX_DIR/index.new" \
#     | sed 's|^--- .*|--- a/wiki/index.md|;s|^+++ .*|+++ b/wiki/index.md|' >> "$SHARED_PATCH"
```

Create a fresh branch at the remote main tip and build the commit from a scratch index
read from that base, so the result holds this ingest and nothing else. This never touches
your working tree, the shared index, or `HEAD`:

```bash
set -e   # every step below must be able to stop the run
WIKI_GIT="git -C $WIKI_ROOT"
$WIKI_GIT fetch origin main
BASE="$($WIKI_GIT rev-parse origin/main)"
BRANCH="wiki-ingest/$SLUG"

# refuse a slug whose branch already exists locally or on the remote
for ref in "refs/heads/$BRANCH" "refs/remotes/origin/$BRANCH"; do
  if $WIKI_GIT show-ref --verify --quiet "$ref"; then
    echo "branch $BRANCH already exists ($ref); choose a new slug rather than reusing it" >&2
    exit 1
  fi
done
if $WIKI_GIT ls-remote --exit-code --heads origin "$BRANCH" >/dev/null 2>&1; then
  echo "remote branch origin/$BRANCH already exists; choose a new slug" >&2
  exit 1
fi

IDX_DIR="$(mktemp -d "${TMPDIR:-/tmp}/wiki-index.XXXXXX")"
export GIT_INDEX_FILE="$IDX_DIR/index"
$WIKI_GIT read-tree "$BASE"

# new files: add from the working tree (safe, another session does not own these paths)
$WIKI_GIT add -- "${PATHS[@]}"

# shared files: apply only this run's edit onto the committed base copy
if [ -s "$SHARED_PATCH" ]; then
  $WIKI_GIT apply --cached "$SHARED_PATCH"
fi

TREE="$($WIKI_GIT write-tree)"
COMMIT="$($WIKI_GIT commit-tree "$TREE" -p "$BASE" -m "<cli>/<model>: docs(wiki): ingest $SLUG")"
unset GIT_INDEX_FILE

[ -n "$COMMIT" ] || { echo "commit-tree produced no commit" >&2; exit 1; }
$WIKI_GIT branch "$BRANCH" "$COMMIT"
```

An alternate `GIT_INDEX_FILE` controls what gets committed; it does not remove commits
already on a branch. Starting the branch at `$BASE` and building the commit from
`read-tree "$BASE"` is what guarantees the result holds this ingest and nothing else.

Push the branch by name, verify the remote ref landed that exact commit, and only then
open the PR. `gh` has no `-C` flag (unlike `git`), so run it inside the wiki checkout:

```bash
git -C "$WIKI_ROOT" push origin "$BRANCH"

REMOTE="$(git -C "$WIKI_ROOT" ls-remote origin "refs/heads/$BRANCH" | awk '{print $1}')"
[ -n "$REMOTE" ] && [ "$REMOTE" = "$COMMIT" ] || {
  echo "push did not land $COMMIT on $BRANCH (remote='${REMOTE:-none}')" >&2; exit 1; }

(cd "$WIKI_ROOT" && gh pr create --base main --head "$BRANCH" --fill)
```

Verifying before opening the PR matters: an empty `REMOTE` from a failed `ls-remote`
would otherwise compare equal to an empty `COMMIT` and report success. If any step fails,
report what failed; do not retry blindly.

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
