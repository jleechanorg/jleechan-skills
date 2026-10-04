---
name: research
description: Investigate a question against high-trust primary sources and capture the findings as a Markdown file in the repo. Use when the user wants a topic researched, docs or API facts gathered, or reading legwork delegated to a background agent.
---

Spin up a **background agent** to do the research, so you keep working while it reads.

Its job:

1. Investigate the question against **primary sources** — official docs, source code, specs, first-party APIs — not a secondary write-up of them. Follow every claim back to the source that owns it.
2. Run a **fresh web search on every invocation**, including when repository files or prior notes are available. Open the relevant primary sources to verify the findings; old notes and cached summaries do not count as a fresh search. Run web search **in parallel with repository/context research** when the work is independent and capacity is available; otherwise do both sequentially.
3. Write the findings to a single Markdown file, citing each claim's source and recording the research date plus source dates or versions where available. Distinguish current verified findings from historical context. If web search is unavailable or fails, disclose the gap and its effect on confidence instead of claiming freshness.
4. Save it where the repo already keeps such notes; match the existing convention, and if there is none, put it somewhere sensible and say where.
