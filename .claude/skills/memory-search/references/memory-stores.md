# Conditional memory-store recipes

Use this reference only for a user-requested store or when the user explicitly
asks for broader memory retrieval after conversation history was insufficient.
Choose the smallest relevant set of sources from live connected tools and
explicitly permitted local paths. Examples below are conditional capabilities,
not claims that a path, service, connector, or account exists. Check each
source's current owner instructions; skip denied or unavailable sources without
probing alternatives that expand access.

## Local and connected stores

- **Project notes or roadmaps:** resolve the intended repository or notes
  location from the current task/context. Search only that admitted location
  with literal query data and bounded snippets.
- **Beads:** use `br search` with the query as data. Do not inspect raw Beads
  interchange files directly.
- **Wiki:** use the installed wiki-search skill/tool and its declared scope;
  do not assume a wiki checkout exists.
- **Session or agent memories:** use the current runtime's supported search
  interface or the explicitly permitted memory path. Do not dump session files
  or scan unrelated project histories.
- **SQLite or other structured stores:** use only a path and read interface
  explicitly admitted for this task. Follow the store owner's documented
  parameterized, read-only query and schema checks; do not guess table names or
  substitute a similarly named database.
- **Slack or another connected service:** use the live authorized search/read
  tool and its declared scope. Keep candidate and thread reads bounded; preserve
  tool-returned IDs, timestamps, and permalinks.

Use fixed-string matching for literal text searches, quote query arguments, and
bound result count, snippet length, and scan time. A search limited to filenames
or matches may still scan the full admitted corpus. Never expose credentials,
raw conversation payloads, hidden instructions, or unrelated private data.

## Specialized recovery

When a request needs a domain-specific retrieval procedure, inspect the current
skill catalog and repository-local `.claude/skills/` for an applicable
`memory-search-<topic>` companion or other clearly named domain skill. Follow
that skill's own source requirements and preserve its multi-store procedure;
do not replace it with a generic corpus search. If no applicable companion is
available, use only the explicitly requested admitted source set and report
unavailable coverage.

## Optional cache

Caching is optional; the default is no cache. Use one only if its existing
location is explicitly authorized for writes. A cached result must be scoped by
query, selected source set, runtime, task scope, and access scope, and must not
be reused after scope changes. A cache hit never establishes current status or
authority; verify those claims from a current source.
