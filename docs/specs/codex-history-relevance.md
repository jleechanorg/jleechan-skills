# Sparse Codex history relevance and bounded tail sampling

## Outcome

For an explicitly admitted Codex profile, return relevant recent project user
messages even when the index has only an unrelated older title match. Inspect
bounded rollout samples rather than treating index hits as complete coverage.
Retain recent followups after long or oversized earlier records without scanning
the full history corpus or claiming complete recall.

## Non-goals

No history-store mutation, broad corpus indexing, provider calls, model-profile
changes, verified human-authorship classification, or automatic deep search.
No promise to find messages in the omitted middle of a rollout or files beyond
the discovery/candidate budgets. No installed-host activation claim.

## Acceptance

- Exact project cwd and updated time (creation time on legacy indexes) prioritize
  admitted candidates; an unrelated index hit does not suppress rollout search.
- Modern and legacy indexes remain usable and read-only. Reject out-of-profile
  and symlink rollout pointers before opening them; explicit profiles stay isolated.
- Search only explicitly identified user-role records, not tool payloads; retain
  `human_verified: false`, timestamp, source path/thread and excerpt budgets.
- Read at most 1 MiB per rollout: whole files within that size, otherwise 512 KiB
  at each end. Parse at most 2000 selected records, preserving both ends when
  needed; skip records larger than 64 KiB and incomplete segment fragments.
- A recent user followup after 5000 ordinary records or a 2 MiB earlier tool
  record remains discoverable when inside the sampled tail. Multiple tail hits
  in one thread do not collapse merely because their line numbers are unknown.
- Every sampled message has an exact byte offset. Use exact absolute line numbers
  only when the prefix was read; otherwise return null. Reset active-turn model
  attribution across omitted records; retain only actually observed context.
- Keep candidate/discovery/SQLite bounds and disclose partial coverage and errors,
  including empty results. An unsampled middle match is not evidence of absence.

## User story

A developer asks a bounded history query for the current project. Recent work
mentions the query only in a followup, while an old unrelated thread has a matching
index title. The helper returns relevant sampled project messages with truthful
locators, role evidence and limitations, allowing bounded expansion of that exact
source without dumping unrelated history.

## Proof plan

Use the actual public `search_codex` and CLI `main` entrypoints with isolated
synthetic JSONL/SQLite profiles. Capture fresh causal RED/GREEN for the tail-loss
regressions; exercise the real CLI on the same fixture at original and candidate
source revisions. Assert byte-offset round trips, unknown tail line numbers,
model-context reset, preserved explicit profile admission, and the 1 MiB read
budget. Run all `test_history_search*.py` regressions, mechanical diff checks and
relevant installer tests. Preserve original benchmark source/results; integration
repair receipts and costs are separate. Independent source/evidence review and
current CI remain subsequent PR gates, not supplied by these tests.

## Mock exemption

No rendered UI or browser surface changes, so no visual mock, screenshot or video
is applicable. Fixtures synthesize local files and SQLite rows because the claim
is deterministic offline retrieval; they do not simulate successful live-provider
or installed-runtime behavior. Reader instrumentation observes actual file reads
without replacing returned data. No real conversations are needed or published.

## Risk

Bounded selection can miss middle messages or undiscovered files; diagnostics must
not overstate coverage. Tail fragments and skipped turn boundaries can otherwise
fabricate records, line numbers or model attribution. Byte-offset provenance and
context reset mitigate those risks without enlarging source admission. Runtime
source changes require the applicable independent review and proof; this spec
neither waives those gates nor authorizes a merge.
