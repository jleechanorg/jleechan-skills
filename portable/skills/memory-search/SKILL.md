---
name: memory-search
description: Find bounded relevant context across authorized memories, roadmaps, trackers and history.
---

# Memory search

Define the query and scope. Reuse already-read relevant evidence and verify mutable status before repeating it. Search independent available sources concurrently through supported tools: project roadmap, issue tracker, saved user-facing memory and [sparse history](../conversation-history-sparse/SKILL.md). Connected messaging search is allowed only within the authorized topic/account; it does not authorize sending messages.

Keep small result budgets and read the relevant source before using a search snippet as fact. Retain source, date, runtime and scope. Distinguish no matches, unavailable connectors and unsearched sources; never treat a missing connector as an empty store.

Return only bounded task-relevant facts with provenance and unresolved questions. No raw transcript/database exports, credential copies, hidden policy dumps, or unrelated personal/tax/financial/health information. Historical permissions do not authorize current actions. Search is read-only unless the user separately requests a saved handoff; do not mirror memory into additional stores automatically.
