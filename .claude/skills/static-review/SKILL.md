---
name: static-review
description: Use when dispatching any independent reviewer (CLI, coordinator ask or static-review subagent); owns the cold start, the verbatim prompt templates, per-channel preambles, receipts and identity rules.
---

# /static-review — cold, verbatim reviewer input

This skill owns what every reviewer receives and what its receipt proves.
The `advice` skill owns when reviewers run, the quorum and the
substitution rules; pr-lifecycle owns publication.

## 1. Cold start

A static reviewer starts cold and blank, like a fresh terminal: no parent
context, summary or framing of the change. Every reviewer's entire input,
whether a CLI reviewer, the coordinator ask or a static-review subagent, is
one fixed channel preamble below followed by one template below. Fill only `<PR
URL>` and `<SHA>`, or for document-only review `<PACKET PATH>` and `<BUNDLE
HASH>`. The orchestrator writes nothing else.

## 2. Templates

Static review prompt (skill-owned, verbatim):

```text
Review <PR URL> at head <SHA>. Ensure it follows the /prw stages and focus on
evidence review before approval. Report P0/P1/P2 with file:line and a
COVERAGE: line naming the files and diff you read; approve only with no P0/P1
and full coverage; end with exactly one line:
VERDICT: APPROVED|NOT APPROVED|WITHHELD at <SHA> (WITHHELD with a reason).
```

Document-only review prompt (skill-owned, verbatim):

```text
Review the saved documents in <PACKET PATH>, bundle
DOCUMENTS sha256:<BUNDLE HASH>. This is document-only review: do not approve
code, a PR or HEAD. Report P0/P1/P2 with file:line and a COVERAGE: line naming
the files you read; approve only with no P0/P1 and full coverage; end with
exactly one line: VERDICT: APPROVED|NOT APPROVED|WITHHELD at
DOCUMENTS sha256:<BUNDLE HASH> (WITHHELD with a reason).
```

## 3. Channel preambles

Each channel's preamble is the exact-SHA or document-only header the orchestrator adds when it launches that
seat, and the packet must contain exactly the filled template. The orchestrator records the exact prompt in
`receipt.json` as `prompt` and `prompt_sha256`. For CLI
alternates, each `<review request>`, and the stdin of forms without one, is
exactly the preamble plus the template.

Coordinator ask (for example a Dot reviewer channel): the configured account
mentions, then `Advice vote requested.` on its own line, then the template.
Send it to each configured coordinator account in rotation.

The revision and document-only preambles below apply to **every** CLI reviewer seat - Codex, Opus, the Claude
alternates, Cursor, AGY and any `ADVICE_EXTRA_CLIS` seat - and to static reviewers. They replace the header the
deleted helper used to inject; there is no other header to match, so a seat launched without one
cannot produce a byte-identical prompt and its vote is void.

Revision preamble for every CLI seat and for static reviewers (verbatim):

```text
Work in the clone the orchestrator gives you for this review (no `origin`
remote, pinned to the given SHA). Use the GitHub token already present in your environment and
never print it. Do not modify the original checkout, refs, config or hooks. Do
not post anything; return your review as your final output.
```

Document-only preamble for every CLI seat and for static reviewers (verbatim):

```text
Read only the named saved files in the given packet, checking each against its
recorded SHA256. Do not clone or review code. Do not modify any checkout, refs,
config or hooks. Do not post anything; return your review as your final output.
```

## 4. Identity

Each static reviewer is a distinct reviewer identity and reports its actual
model. Two reviewers whose models are both unreported, or where either model is
unreported and type or harness match, are not distinct and count as one vote;
at most one counted static reviewer may have an unreported model, and it must
differ from the other by subagent type and harness. Same-identity reviewers are
one vote. Static
reviewers run in separate contexts and do not read each other's output first.
Each has one 600-second end-to-end acceptance deadline from launch; the
orchestrator, not the reviewer, timestamps launch and return. Reviewers do not
post; the orchestrator publishes verdicts through pr-lifecycle.

## 5. Receipt

Every reviewer receipt records the reviewer identity (type, harness and model),
the exact SHA or bundle hash, orchestrator launch and return times, the exact
prompt sent, a `COVERAGE:` statement, the `VERDICT:` line, the actual clone path
whenever one exists (document-only review launches no clone, so record `none`
there), and a read-only check that the original checkout,
refs, local config and hooks are unchanged. The orchestrator also verifies and
records that no reviewer process survives and that clone cleanup succeeded. For
a static-review subagent this receipt replaces only the seat-exit field of the
seat receipt. When publishing a receipt outside the authorized
workspace, publish only the prompt's SHA256 and template name if any filled
field (PR URL, packet path) or other content could carry private paths, hosts,
repository names or tokens; otherwise remove those values before publishing.
Keeping the template name plus filled fields is not redaction.

## 6. Deviation voids the vote

Check the recorded prompt byte for byte against the channel preamble plus the
filled template. Any deviation, including added context, summary or framing,
voids that vote.
