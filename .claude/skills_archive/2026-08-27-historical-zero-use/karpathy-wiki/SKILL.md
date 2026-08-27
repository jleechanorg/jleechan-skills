# karpathy-wiki Skill

## When to use
When working with an LLM wiki (Karpathy pattern) - ingesting sources, querying, linting, or building the knowledge graph.

## What it does
Enforces the exact Karpathy LLM Wiki pattern from https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f

## Pattern Requirements

### Directory Structure (MUST FOLLOW EXACTLY)
```
llm_wiki/
├── raw/              # Immutable source documents (NEVER edit these)
├── wiki/             # LLM owns this layer entirely - single source of truth
│   ├── index.md      # Catalog of ALL pages with curated one-line summaries
│   ├── log.md        # Append-only chronological record (format: ## [YYYY-MM-DD] operation | title)
│   ├── overview.md  # Living synthesis across all sources
│   ├── sources/      # Source summary pages (kebab-case.md)
│   ├── entities/    # Entity pages (TitleCase.md - people, companies, projects)
│   ├── concepts/     # Concept pages (TitleCase.md - ideas, methods, theories)
│   └── syntheses/   # Saved query answers
└── (no root-level wiki files - ALL must be under wiki/)
```

### Frontmatter (REQUIRED on every page)
```yaml
---
title: "Page Title"
type: source | entity | concept | synthesis
tags: []
sources: []      # list of source slugs that inform this page
last_updated: YYYY-MM-DD
---
```

### Page Naming
- **Sources**: kebab-case (e.g., `json-display-bugs-analysis-report.md`)
- **Entities**: TitleCase (e.g., `PR278.md`, `OpenAI.md`, `SamAltman.md`)
- **Concepts**: TitleCase (e.g., `StructuredResponse.md`, `RAG.md`)

### Wikilinks
Use `[[PageName]]` for internal links - these become the knowledge graph edges.

### Index Format
```markdown
# Wiki Index

## Overview
- [Overview](overview.md) — one-line synthesis

## Sources
- [Source Title](sources/slug.md) — CURATED one-line summary (NOT raw email subject)

## Entities
- [Entity Name](entities/EntityName.md) — one-line description

## Concepts
- [Concept Name](concepts/ConceptName.md) — one-line description

## Syntheses
- [Analysis Title](syntheses/slug.md) — what question it answers
```

### Log Format
```
## [YYYY-MM-DD] operation | title

Key claims: ...
```
Operations: `ingest`, `query`, `lint`, `graph`

## Ingest Workflow
1. Read source document from `raw/`
2. Read `wiki/index.md` and `wiki/overview.md` for context
3. Write `wiki/sources/<slug>.md` with Source Page Format
4. Update `wiki/index.md` — add entry under correct section
5. Update `wiki/overview.md` — revise synthesis
6. Create/update entity pages for key people/companies/projects
7. Create/update concept pages for key ideas/methods
8. Flag any contradictions
9. Append to `wiki/log.md`

### Source Page Format
```markdown
---
title: "Source Title"
type: source
tags: []
date: YYYY-MM-DD
source_file: raw/...
sources: []
last_updated: YYYY-MM-DD
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

## Contradictions
- Contradicts [[OtherPage]] on: ...
```

## Query Workflow
1. Read `wiki/index.md` to find relevant pages
2. Read those pages
3. Synthesize answer with `[[PageName]]` citations
4. Offer to save as `wiki/syntheses/<slug>.md`

## Lint Workflow
Check for:
- **Orphans**: pages with no inbound `[[links]]`
- **Broken links**: `[[WikiLinks]]` to non-existent pages
- **Contradictions**: conflicting claims across pages
- **Stale summaries**: pages not updated after newer sources
- **Missing entities**: entities mentioned 3+ times without own page
- **Missing concepts**: concepts discussed without own page
- **Data gaps**: questions wiki can't answer

## Graph Workflow
1. Grep all `[[wikilinks]]` → deterministic `EXTRACTED` edges
2. Infer implicit relationships → `INFERRED` edges with confidence
3. Run Louvain community detection
4. Output `graph/graph.json` + `graph/graph.html`

## Common Issues to Fix

### Dual Structure Problem
If wiki exists in both root AND `wiki/` subdirectory:
- Move all wiki content to `wiki/` subdirectory only
- Delete root-level `index.md`, `log.md`, `overview.md` if duplicates exist
- Update ingest.py to write to `wiki/` subdirectory

### Index Quality Problem
If index contains raw email subjects instead of curated summaries:
- Re-ingest with instruction to create proper summaries
- Edit index entries to be content-oriented, not raw titles

### Entity/Concept Gap
If few entity/concept pages created:
- Force extraction: prompt must explicitly create entity pages for EVERY person/company/project mentioned
- Force extraction: prompt must explicitly create concept pages for EVERY idea/method/theory
- Track entity/concept ratio - should be roughly 1:1 with sources or higher