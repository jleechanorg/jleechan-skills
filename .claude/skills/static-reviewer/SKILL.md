---
name: static-reviewer
description: Use when dispatching any independent reviewer (CLI, coordinator ask or static-reviewer subagent); owns the cold start, the verbatim prompt templates, per-channel preambles, receipts and identity rules.
---

# /static-reviewer — cold, verbatim reviewer input

This skill owns what every reviewer receives and what its receipt proves.
[advice](../advice/SKILL.md) owns when reviewers run, the quorum and the
substitution rules; pr-lifecycle owns publication.

## 1. Cold start

A static reviewer starts cold and blank, like a fresh terminal: no parent
context, summary or framing of the change. Every reviewer's entire input,
whether a CLI reviewer, the coordinator ask or a static-reviewer subagent, is
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

For the primary-pair runner, its built-in header (the exact-SHA or
document-only lines in `run_primary_pair.py`) is that channel's preamble, and
`--packet-file` must contain exactly the filled template. The runner records
the exact prompt in `receipt.json` as `prompt` and `prompt_sha256`. For CLI
alternates, each `<review request>`, and the stdin of forms without one, is
exactly the preamble plus the template.

Coordinator ask (for example a Dot reviewer channel): the configured account
mentions, then `/advice vote requested.` on its own line, then the template.
Send it to each configured coordinator account in rotation.

Revision preamble for CLI alternates and static reviewers (verbatim):

```text
Work in a fresh clone of the PR repository without an `origin` remote, pinned
to the given SHA. Use the GitHub token already present in your environment and
never print it. Do not modify the original checkout, refs, config or hooks. Do
not post anything; return your review as your final output.
```

Document-only preamble for CLI alternates and static reviewers (verbatim):

```text
Read only the named saved files in the given packet, checking each against its
recorded SHA256. Do not clone or review code. Do not modify any checkout, refs,
config or hooks. Do not post anything; return your review as your final output.
```

## 4. Identity

Each static reviewer is a distinct reviewer identity and reports its actual
model; if a model cannot be reported, the reviewers must differ by both
subagent type and harness. Same-identity reviewers are one vote. Static
reviewers run in separate contexts and do not read each other's output first.
Each has one 600-second end-to-end acceptance deadline from launch; the
orchestrator, not the reviewer, timestamps launch and return. Reviewers do not
post; the orchestrator publishes verdicts through pr-lifecycle.

## 5. Receipt

Every reviewer receipt records the reviewer identity (type, harness and model),
the exact SHA or bundle hash, orchestrator launch and return times, the exact
prompt sent, a `COVERAGE:` statement, the `VERDICT:` line, the clone path (none
for document-only review), and a read-only check that the original checkout,
refs, local config and hooks are unchanged. The orchestrator also verifies and
records that no reviewer process survives and that clone cleanup succeeded. For
a static-reviewer subagent this receipt replaces only the runner exit field of
the runner receipt.

## 6. Deviation voids the vote

Check the recorded prompt byte for byte against the channel preamble plus the
filled template. Any deviation, including added context, summary or framing,
voids that vote.
