---
name: static-review
description: Use when dispatching any independent reviewer (CLI, coordinator ask or static-review subagent); owns the cold start, the verbatim prompt templates, per-channel preambles, receipts and identity rules.
---

# /static-review — cold, verbatim reviewer input

This skill owns what every reviewer receives and what its receipt proves. The `advice` skill owns when reviewers
run, the quorum and substitution; pr-lifecycle owns publication.

## 1. Cold start

Every reviewer (CLI seat, coordinator ask, web-provider ask or static-review subagent) starts cold: no parent
context, summary or framing. Its whole input is one channel preamble from §3 followed by one template from §2, with
only the fields the `advice` skill's §4 table lists for the seat's `isolation:` row filled in:

| `isolation:` | Template | Fields |
|---|---|---|
| `orchestrator-clone` | clone review | `<PR URL>` `<SHA>` `<BASE SHA>` `<SCRATCH PATH>` |
| `remote` | remote review | `<PR URL>` `<SHA>` `<BASE SHA>` |
| `packet` | revision packet | `<PR URL>` `<SHA>` `<BASE SHA>` `<PACKET PATH>` `<BUNDLE HASH>` |
| `none` | document-only | `<PACKET PATH>` `<BUNDLE HASH>` |

The orchestrator writes nothing else.

## 2. Templates

Clone review prompt, for `isolation: orchestrator-clone` CLI seats and static
reviewers (skill-owned, verbatim):

```text
Review <PR URL> at head <SHA> (base <BASE SHA>, work only in <SCRATCH PATH>). Ensure it follows the /prw stages and focus on
evidence review before approval. Report P0/P1/P2 with file:line and a
COVERAGE: line naming the files and diff you read; approve only with no P0/P1
and full coverage; end with exactly one line:
VERDICT: APPROVED|NOT APPROVED|WITHHELD at <SHA> (WITHHELD with a reason).
```

Remote review prompt, for `isolation: remote` outside reviewers such as a Dot
or Hermes (skill-owned, verbatim):

```text
Review <PR URL> at head <SHA> (base <BASE SHA>) using a checkout you already
have; do not make a new clone. Fetch <SHA> if it is missing and read it with
git diff <BASE SHA>..<SHA> and git show <SHA>:<path>, without switching that
checkout's branch or touching its working tree. Ensure it follows the /prw stages and focus on evidence review
before approval. Report P0/P1/P2 with file:line, a MODEL: line naming the model
and account you reviewed with, and a COVERAGE: line naming the files and diff
you read; approve only with no P0/P1 and full coverage; end with exactly one
line: VERDICT: APPROVED|NOT APPROVED|WITHHELD at <SHA> (WITHHELD with a reason).
```

Revision packet prompt, for `isolation: packet` web-provider seats
(skill-owned, verbatim):

```text
Review the attached change packet for <PR URL> at head <SHA> (base <BASE SHA>),
saved as <PACKET PATH>, bundle sha256:<BUNDLE HASH>. It holds the complete diff
and the full post-change content of every changed file. Ensure it follows the
/prw stages and focus on evidence review before approval. Report P0/P1/P2 with
file:line, a MODEL: line naming the model you are, and a COVERAGE: line naming
every packet file you read; if any file was truncated or unreadable, say so and
do not approve; end with exactly one line:
VERDICT: APPROVED|NOT APPROVED|WITHHELD at <SHA> (WITHHELD with a reason).
```

Document-only review prompt (skill-owned, verbatim):

```text
Review the saved documents in <PACKET PATH>, bundle
DOCUMENTS sha256:<BUNDLE HASH>. This is document-only review: do not approve
code, a PR or HEAD. Report P0/P1/P2 with file:line, a MODEL: line naming the
model you are, and a COVERAGE: line naming the files you read; approve only with no P0/P1 and full coverage; end with
exactly one line: VERDICT: APPROVED|NOT APPROVED|WITHHELD at
DOCUMENTS sha256:<BUNDLE HASH> (WITHHELD with a reason).
```

## 3. Channel preambles

The orchestrator records the exact prompt sent as `prompt` and `prompt_sha256` in the seat's receipt. For a CLI
seat, the `<review request>` argument (or stdin, for forms without one) is exactly preamble plus template.

Coordinator ask (each Dot account in rotation and each configured Hermes instance): the sender line its owning
skill requires, if any (for example the Dot `From ...:` prefix), then the configured mentions, then
`Advice vote requested.` on its own line, then the remote preamble, then the remote review prompt. Coordinator asks are revision-only: a remote reviewer
cannot read a local packet. Exactly these four parts, in this order, may precede the template: the sender line,
the mentions, `Advice vote requested.` and the remote preamble; record the sender line and mentions in the
receipt. A vote request is not a `/hermes` task handoff: it carries no task marker, owner or acceptance fields,
because the template's PR URL and SHA already bind it.

Web-provider ask (web-advice seats): the channel preamble is the `/web-advice` titling line
`[web advice] Advice vote at <SHA>` (or `<BUNDLE HASH>` for documents, which also asks the model to title the chat
that way), then `Advice vote requested.` on its own line, followed
by the revision packet prompt (revision), or by the document-only preamble plus the document-only review prompt, with the packet files uploaded as
attachments.

Every CLI seat (Codex, Opus, the Claude alternates, Cursor, AGY, any `ADVICE_EXTRA_CLIS` seat) and every static
reviewer gets the revision or document-only preamble below. A seat launched without one cannot produce a
byte-identical prompt, so its vote is void.

Revision preamble for every CLI seat and for static reviewers (verbatim):

```text
Work only in the isolated clone at the scratch path given below; if your working
directory was set to it, stay there. Do not clone, fetch, check out another
commit, add a remote, or create any other copy - these are instructions, and the
orchestrator's post-return checks are what detect a clone whose HEAD or remote
changed. Never work in the original checkout or in a donor repository. Leave the
clone in place - the orchestrator verifies it and removes it after your process
exits. Use the GitHub token already present in your environment and
never print it. Do not modify the original checkout, refs, config or hooks. Do
not post anything; return your review as your final output.
```

Remote preamble for every coordinator ask (verbatim):

```text
Review only; this is a vote request, not a task. Do not push, commit, comment
on, label, approve or otherwise change the PR or its branch, and do not hand the
review to another account. Return your review in this conversation as your
final reply.
```

Document-only preamble for every CLI seat and for static reviewers (verbatim):

```text
Read only the named saved files in the given packet, checking each against its
recorded SHA256. Do not clone or review code. Do not modify any checkout, refs,
config or hooks. Do not post anything; return your review as your final output.
```

## 4. Identity

- A static reviewer reports its actual model. Same identity (type, harness and model) means one vote.
- Two reviewers that both leave their model unreported count as one vote, and so do two where one is unreported
  and their type or harness match. At most one counted static reviewer may leave its model unreported, and it must differ from the other by
  subagent type and harness.
- Static reviewers run in separate contexts and do not read each other's output first.
- Each static reviewer has a 600-second end-to-end deadline from launch, replacing the `advice` skill's 1800-second
  default for static reviewers only. The orchestrator, not the reviewer, timestamps launch and return.
- Reviewers never post; the orchestrator publishes verdicts through pr-lifecycle.

## 5. Receipt

Every receipt records the reviewer identity (type, harness, model), the exact SHA or bundle hash, launch and return
times taken by the orchestrator, the exact prompt, the `COVERAGE:` statement, the `VERDICT:` line, the clone path
(`none` when there is none) and a read-only check that the original checkout, refs, local config and hooks are
unchanged. The orchestrator also records that no reviewer process survives and that clone cleanup succeeded.

- For a static-review subagent this receipt replaces only the seat-exit field.
- For an outside route (`remote` or `packet`), record instead of the exit, process and cleanup fields: the route, the
  message reference or permalink read back at the source, the `MODEL:` line as `attested.model`, and the row's
  evidence from the `advice` skill's §4 table.
- Outside the authorized workspace, publish only the prompt's SHA256 and template name whenever a filled field (PR
  URL, packet path) or other content could reveal private paths, hosts, repository names or tokens; otherwise strip
  those values first. The template name plus filled fields is not redaction.

## 6. Deviation voids the vote

Check the recorded prompt byte for byte against the channel preamble plus the
filled template. Any deviation, including added context, summary or framing,
voids that vote.
