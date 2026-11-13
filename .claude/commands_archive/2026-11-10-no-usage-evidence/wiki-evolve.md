---
description: Self-improving wiki evolution loop — validates against Karpathy pattern, fixes gaps. Usage: /wiki-evolve [--wiki <wiki_dir>]
---

# /wiki-evolve — Wiki Pattern Evolution Loop

## Usage
```
/wiki-evolve [--wiki <wiki_dir>]
```

`--wiki <wiki_dir>` overrides the default wiki location (`~/llm_wiki/wiki`).

## Purpose

Self-improving loop that validates an llm-wiki against Karpathy pattern, identifies gaps, fixes issues via re-ingest, and verifies compliance. Runs via `/loop 5m /wiki-evolve`.

## Reference
- Karpathy gist: https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f
- Skill: /karpathy-wiki

## Loop Body

### Phase 0: Resolve wiki path
```bash
WIKI_DIR="$HOME/llm_wiki/wiki"
if args contain "--wiki <path>"; then
  WIKI_DIR="<path>"
fi
WIKI_ROOT=$(dirname "$WIKI_DIR")
```

### Phase 1: OBSERVE — Wiki State Snapshot

```bash
echo "=== WIKI STRUCTURE CHECK ==="
ls -la "$WIKI_DIR"/

echo "Sources: $(ls "$WIKI_DIR"/sources/*.md 2>/dev/null | wc -l)"
echo "Entities: $(ls "$WIKI_DIR"/entities/*.md 2>/dev/null | wc -l)"
echo "Concepts: $(ls "$WIKI_DIR"/concepts/*.md 2>/dev/null | wc -l)"

echo "=== ROOT DUPLICATES CHECK ==="
ls "$WIKI_ROOT"/*.md 2>/dev/null || echo "No root .md files (good)"
```

### Phase 2: MEASURE — Pattern Compliance

```bash
SOURCES=$(ls "$WIKI_DIR"/sources/*.md 2>/dev/null | wc -l)
ENTITIES=$(ls "$WIKI_DIR"/entities/*.md 2>/dev/null | wc -l)
CONCEPTS=$(ls "$WIKI_DIR"/concepts/*.md 2>/dev/null | wc -l)

echo "Sources: $SOURCES, Entities: $ENTITIES, Concepts: $CONCEPTS"
echo "Entity ratio: $(echo "scale=2; $ENTITIES * 100 / $SOURCES" | bc)%"
echo "Concept ratio: $(echo "scale=2; $CONCEPTS * 100 / $SOURCES" | bc)%"

head -30 "$WIKI_DIR"/index.md
```

### Phase 3: DIAGNOSE — Identify Gaps

Compare against Karpathy pattern:
1. **Structure**: Only `wiki/` subdirectory, no root duplicates
2. **Ratio**: Entity + Concept should be ~10-20% of sources minimum
3. **Index**: Curated summaries, not raw email subjects
4. **Frontmatter**: All pages have YAML frontmatter with type field

### Phase 4: FIX — Implement Corrections

Pass `--wiki "$WIKI_DIR"` to every `/wiki-ingest` call so child commands write
to the destination selected for this `/wiki-evolve` run, not their default.

For each gap found:
1. **Structure gap**: Propose changes; route wiki writes through
   `/wiki-ingest <candidate-source> --wiki "$WIKI_DIR"`.
2. **Ratio gap**: Re-ingest eligible key sources through
   `/wiki-ingest <candidate-source> --wiki "$WIKI_DIR"`.
3. **Index gap**: Route index changes through
   `/wiki-ingest <candidate-source> --wiki "$WIKI_DIR"`.
4. **Frontmatter gap**: Route page updates through
   `/wiki-ingest <candidate-source> --wiki "$WIKI_DIR"`.

### Phase 5: VERIFY — Confirm Pattern Compliance

```bash
# Verify no broken wikilinks
grep -r '\[\[' "$WIKI_DIR"/sources/*.md | head -20
```

### Phase 6: RECORD — Log Findings

Record findings through `/wiki-ingest <candidate-source> --wiki "$WIKI_DIR"`;
do not append to wiki files directly.

### Phase 7: RECAP — Cycle Summary

```
## Wiki Evolve Cycle — $(date '+%H:%M')
- Wiki: $WIKI_DIR
- Structure: ✅/❌
- Entity ratio: X% (target: >5%)
- Concept ratio: X% (target: >5%)
- Index quality: ✅/❌
- Fixes: [list]
```

## Termination Conditions

1. User says "stop" or "pause"
2. Acceptance criteria are met and verified.
3. The shared eight-hour autonomy deadline is reached; report progress, remaining work, and the resumption trigger.
