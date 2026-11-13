# History Search Output Budget

## Outcome

Sparse history-search JSON returns readable previews while keeping title metadata bounded. The default snippet budget is 500 characters; explicit `--max-chars` values continue to control previews.

## Non-goals

Do not add a whole-response byte cap, change source admission or ranking, filter history semantically, or shorten source identifiers and timestamps.

## Acceptance

- JSON titles longer than 160 characters are represented by a 160-character preview ending in an ellipsis, with `metadata.title_truncated: true`.
- Thread/conversation IDs and timestamps remain unchanged.
- Default snippets are at most 500 characters, and explicit positive `--max-chars` values are honored by file and SQLite sources.
- The Codex CLI regression covers an oversized indexed title, the default preview, a 700-character override, and preserved ID/timestamp.

## User story

No product-facing change — agent history-search output becomes more useful while keeping its source identity intact.

## Proof plan

Run the focused history-search unit tests and the executable sparse-history documentation examples. Compare the same synthetic Codex SQLite row against `origin/main` and the changed helper; record JSON byte size, title/snippet lengths, and ID/timestamp preservation.

## Mock

Use only temporary synthetic files and SQLite fixtures. No private history corpus, live service, model, or provider call is required.

## Risk

The JSON title field is now a preview when the source title exceeds 160 characters; the truncation flag makes that explicit. There is no overall byte cap, and callers can request previews longer than the default.
