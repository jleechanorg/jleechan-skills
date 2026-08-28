---
name: wiki-integrity
description: "Use BEFORE writing wiki/sources, wiki/entities, or wiki/concepts. Routes through /wiki-ingest; bulk generation must also create entity+concept pages."
---

# Wiki integrity — route through /wiki-ingest


**Never write files directly to `wiki/sources/`, `wiki/entities/`, or `wiki/concepts/` via raw scripts or direct disk I/O.**

Always route through the `/wiki-ingest` workflow (or equivalent slash command). Bulk generation of source pages MUST also trigger entity + concept extraction — a batch that only writes source pages without entity/concept pages is **incomplete automation**.

When ingesting campaign text: extract and create entity pages for (a) player character, (b) named NPCs in 3+ scenes, (c) named locations, (d) factions. Create concept pages for game mechanics, settings, themes.

**Why**: A script wrote 22,132 raw scene pages to wiki/sources/ bypassing /wiki-ingest — zero entity pages created, entity ratio dropped to 1.7%.
