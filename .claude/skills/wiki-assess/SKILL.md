---
name: wiki-assess
description: Assess wiki structure and ratios against Karpathy pattern standards
---

# /wiki-assess — Wiki Quality Assessment

## Usage
```
/wiki-assess [<wiki_dir> | --wiki <wiki_dir>]
```

Assess any wiki directory against Karpathy pattern:
- Structure: sources/entities/concepts in wiki/ subdir
- Ratios: Entity and Concept should be >5% of sources
- Index: Curated summaries, not raw content
- Frontmatter: YAML frontmatter with type field

`--wiki <wiki_dir>` or a bare positional path both override the configured wiki (`.wiki-default`, then `~/.wiki-default`, then `$WIKI_ROOT/wiki`; with none set, stop with "WIKI_ROOT not configured").

## Execution

### Phase 1: Resolve wiki path
```bash
# Check for local wiki default (project-level override)
if [ -f ".wiki-default" ]; then
  WIKI=$(cat .wiki-default)
elif [ -f "$HOME/.wiki-default" ]; then
  WIKI=$(cat "$HOME/.wiki-default")
elif [ -n "${WIKI_ROOT:-}" ]; then
  WIKI="$WIKI_ROOT/wiki"
fi
# Accept either positional arg or --wiki flag (both override .wiki-default)
if first positional arg is a path (not a flag); then
  WIKI="<first positional arg>"
elif args contain "--wiki <path>"; then
  WIKI="<path>"
fi
if [ -z "${WIKI:-}" ]; then
  echo "WIKI_ROOT not configured: your wiki checkout (contains wiki/ and raw/). Example: export WIKI_ROOT=\$HOME/llm_wiki (or pass --wiki <wiki_dir>)" >&2
  exit 1
fi
```

### Phase 2: Count pages
```bash
SOURCES=$(find "$WIKI/sources" -name "*.md" 2>/dev/null | wc -l | tr -d ' ')
ENTITIES=$(find "$WIKI/entities" -name "*.md" 2>/dev/null | wc -l | tr -d ' ')
CONCEPTS=$(find "$WIKI/concepts" -name "*.md" 2>/dev/null | wc -l | tr -d ' ')
```

### Phase 3: Calculate ratios
- Entity ratio = ENTITIES / SOURCES * 100
- Concept ratio = CONCEPTS / SOURCES * 100

### Phase 4: Check structure
- Verify wiki/ subdirectory exists
- Verify sources/, entities/, concepts/ subdirs exist
- Check for root duplicates

### Phase 5: Check oracle backlink density
```bash
# The owner/oracle synthesis page, if the wiki has one; skip this phase when absent.
ORACLE=$(ls "$WIKI"/syntheses/*-oracle.md 2>/dev/null | head -1)
ORACLE_SLUG=$(basename "${ORACLE:-none}" .md)
# Count outbound links (both [[wikilink]] and markdown link [Name](../concepts/Name.md) formats)
OUTBOUND_WIKI=$(grep -oE '\[\[[^]]+\]\]' "$ORACLE" 2>/dev/null | grep -v '|' | sort -u | wc -l | tr -d ' ')
OUTBOUND_MD=$(grep -oE '\[[^]]+\]\(\.\./(concepts|entities)/[^)]+\)' "$ORACLE" 2>/dev/null | sort -u | wc -l | tr -d ' ')
OUTBOUND=$((OUTBOUND_WIKI + OUTBOUND_MD))
INBOUND=$(grep -rn "$ORACLE_SLUG" "$WIKI"/ 2>/dev/null | cut -d: -f1 | sort -u | wc -l | tr -d ' ')
```
Target: outbound ≥15, inbound ≥10.

### Phase 6: Output assessment

```
## Wiki Assessment: <wiki_path>

### Structure: ✅/❌
### Ratios:
| Metric | Value | Target | Status |
|--------|-------|--------|--------|
| Sources | N | - | - |
| Entities | N | - | - |
| Concepts | N | - | - |
| Entity ratio | X% | >5% | ✅/❌ |
| Concept ratio | X% | >5% | ✅/❌ |

### Index Quality: ✅/❌
### Frontmatter: ✅/❌

### Oracle Backlink Density:
| Metric | Value | Target | Status |
|--------|-------|--------|--------|
| Outbound wikilinks from oracle | N | ≥15 | ✅/❌ |
| Inbound links to oracle | N | ≥10 | ✅/❌ |

### Verdict: COMPLIANT / NON-COMPLIANT
```

## Example usage
- `/wiki-assess` — assess the configured wiki (`$WIKI_ROOT/wiki`)
- `/wiki-assess ~/memory/wiki` — assess memory wiki
- `/wiki-assess --wiki <path-to-other-wiki>/wiki` — assess another wiki
