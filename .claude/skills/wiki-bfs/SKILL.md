---
name: wiki-bfs
description: Run breadth-first research on a topic and optionally ingest results into the local LLM wiki.
---

# /wiki-bfs — Breadth-First Research + Wiki Ingest

## Usage
```
/wiki-bfs <topic> [--layers N] [--ingest] [--wiki <wiki_dir>]
```

Performs N-layer breadth-first search on a topic, discovers entities and concepts, creates wiki pages, and optionally triggers wiki-assess.

**Default: 2 layers. Use `--layers N` for N layers.**

`--wiki <wiki_dir>` overrides the default wiki location (`~/llm_wiki/wiki`). The `raw/` directory is derived as `$(dirname <wiki_dir>)/raw`.

## Execution

### Phase 1: Parse arguments
- `TOPIC` = first positional arg (required)
- `N` = from `--layers N` flag, default 2
- `INGEST` = present if `--ingest` flag set
- `WIKI` = from `--wiki <path>` flag, default `$HOME/llm_wiki/wiki`

### Phase 2: Resolve wiki path
```bash
# Check for local wiki default (project-level override)
if [ -f ".wiki-default" ]; then
  WIKI=$(cat .wiki-default)
elif [ -f "$HOME/.wiki-default" ]; then
  WIKI=$(cat "$HOME/.wiki-default")
else
  WIKI="$HOME/llm_wiki/wiki"
fi
# --wiki flag always wins over .wiki-default
if args contain "--wiki <path>"; then
  WIKI="<path>"
fi
mkdir -p "$WIKI/entities" "$WIKI/concepts" "$WIKI/sources"
```

### Phase 3: BFS Research (N layers)

Launch parallel research agents per layer. Each layer discovers new topics that become the next layer's research targets.

**Layer architecture:**
```
Layer 0 (seed): <TOPIC>
Layer 1: Explore <TOPIC>'s primary systems/frameworks/people
Layer 2: Explore Layer 1's supporting infrastructure, alternatives, critics
Layer N: Explore Layer N-1's ecosystem, downstream, upstream
```

**Research areas per topic (auto-detected):**
- Governance/constraints/policy → research: governance patterns, fail-closed systems, policy engines
- multi-agent/agent coordination → research: orchestration frameworks, evidence systems, workflow engines
- coding agents/SWE → research: benchmarks, verification, skill libraries
- workflow/durability → research: workflow engines, event sourcing, execution models

**For each layer:**
1. Search web for the topic's canonical projects, papers, people
2. Fetch accessible pages (arxiv, github readmes, official docs)
3. Extract entity names (people, companies, projects) and concept names (patterns, methods, architectures)
4. Compile findings into structured report

### Phase 4: Deduplicate against existing wiki

```bash
# Check which entities already exist
for entity in "${ENTITIES[@]}"; do
  slug=$(echo "$entity" | tr '[:upper:]' '[:lower:]' | tr ' ' '-')
  if [ -f "$WIKI/entities/$slug.md" ]; then
    echo "EXISTS: $entity"
  else
    echo "NEW: $entity"
  fi
done

# Check which concepts already exist
for concept in "${CONCEPTS[@]}"; do
  slug=$(echo "$concept" | tr '[:upper:]' '[:lower:]' | tr ' ' '-')
  if [ -f "$WIKI/concepts/$slug.md" ]; then
    echo "EXISTS: $concept"
  else
    echo "NEW: $concept"
  fi
done
```

### Phase 5: Create wiki pages

**Entity page template:**
```markdown
---
title: "<EntityName>"
type: entity
tags: [<topic-area>, <type>]
date: YYYY-MM-DD
---

## Overview
2–3 sentence overview.

## Key Properties
- **Type**: 
- **Key features**: 

## Connections
- [[RelatedConcept]] — relationship
- [[RelatedEntity]] — relationship

## See Also
- [[RelatedConcept]]
```

**Concept page template:**
```markdown
---
title: "<ConceptName>"
type: concept
tags: [<topic-area>, <pattern-type>]
date: YYYY-MM-DD
---

## Overview
2–3 sentence overview.

## Key Properties
- **What**: 
- **Why matters**: 

## Related Systems
| System | Type | Relevance |
|--------|------|-----------|

## Connection to <TOPIC>
How this concept relates to the BFS root topic.

## See Also
- [[RelatedEntity]]
- [[RelatedConcept]]
```

### Phase 6: Update index

Add new entities and concepts to `wiki/index.md` under appropriate sections with brief descriptions.

### Phase 7: Log

Append to `wiki/log.md`: `## [YYYY-MM-DD] bfs | <TOPIC> — <N> layers, <X> new entities, <Y> new concepts`

### Phase 8: (Optional) wiki-assess

If `--ingest` flag is set, run wiki-assess after all pages created.

## BFS Layer Routing

| Topic keywords | Layer 1 research areas | Layer 2 research areas |
|---|---|---|
| governance, constraint, fail-closed | policy engines, constitutional AI, OPA, GitOps | stream governance, RBAC, drift detection, value alignment |
| multi-agent, orchestration, coordination | LangGraph, AutoGen, CrewAI, MetaGPT | CAMEL, router-architecture, prompt registry, multi-turn alignment |
| coding agent, SWE, evidence | SWE-bench, OpenHands, Voyager, Devin | AgentBench, skill library, self-verification, iterative prompting |
| workflow, durability, execution | Temporal, Prefect, Archon, Airbyte | event sourcing, durable execution, MCP Server, YAML DAGs |
| policy, ACL, authorization | OPA, Rego, Constitutional AI, RLAIF | CIRL, value alignment, scalable oversight, constitutional classifiers |

## Research Output Format

Each layer agent returns:
```
## Entities discovered
- EntityName: type, key properties, source

## Concepts discovered
- ConceptName: definition, key properties, source

## Key quotes
> "Quote" — source

## New topics for next layer
- NextTopicName (reason: discovered in this layer)
```

## Quality Standards
- All entities must have ≥2 factual properties (not just "exists")
- All concepts must connect to ≥2 existing wiki pages
- Key quotes must include attribution and date
- Frontmatter must have title, type, tags, date
