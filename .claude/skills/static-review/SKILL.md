---
name: static-review
description: Use when dispatching any independent reviewer (CLI, coordinator ask or static-review subagent); owns the cold start, the verbatim prompt templates, per-channel preambles, receipts and identity rules.
---

# /static-review — cold, verbatim reviewer input

This skill owns what every reviewer receives and what its receipt proves.
“Static” means the reviewer prompt is fixed, not that approval is restricted.
Static reviewers may approve code, a PR, an exact head SHA, or saved material
when they independently review the complete declared scope and required evidence.
Read-only review through GitHub/API or an existing checkout needs no new clone,
export, or Scratch workspace. Approval remains bound to the reviewed scope;
reviewer approval is not permission to merge.
The `advice` skill owns when reviewers run, the quorum and the
substitution rules; pr-lifecycle owns publication.

## 1. Cold start

A static reviewer starts cold and blank, like a fresh terminal: no parent
context, summary or framing of the change. Every reviewer's entire input,
whether a CLI reviewer, the coordinator ask or a static-review subagent, is
one fixed channel preamble below followed by one template below. Fill exactly the fields that the `advice` skill's §4
table lists for the seat's `isolation:` record - `<PR URL>` `<SHA>` `<BASE SHA>` `<SCRATCH PATH>` for
`isolation: orchestrator-clone`, `<PR URL>` `<SHA>` `<BASE SHA>` `<SCRATCH PATH>` for
`isolation: orchestrator-export`, `<PR URL>` `<SHA>` `<BASE SHA>` for `isolation: read-only`,
`<PACKET PATH>` `<BUNDLE HASH>` `<REVIEW TARGET>` for `isolation: none` - and use that record's
preamble **and** template. The orchestrator writes nothing else.

The export record uses the **shared revision template** in §2 unchanged (it names `<PR URL>`, `<SHA>` and
`<BASE SHA>`, all of which the export supplies); only the preamble differs. Choose exactly one preamble per
seat - the revision preamble for `orchestrator-clone`, the export preamble for `orchestrator-export`,
the read-only preamble for `read-only`, or the saved-content preamble for `none`.
Preambles are alternatives, never concatenated.

## 2. Templates

Static review prompt (skill-owned, verbatim):

```text
Review <PR URL> at head <SHA> (base <BASE SHA>). Ensure it follows the /prw stages and focus on
evidence review before approval. Report P0/P1/P2 with file:line and a
COVERAGE: line naming the files and diff you read; approve only with no P0
and full coverage; report P1/P2 as nonblocking findings; end with exactly one line:
VERDICT: APPROVED|NOT APPROVED|WITHHELD at <SHA> (WITHHELD with a reason).
```

Saved-content review prompt (skill-owned, verbatim):

```text
Review the saved material in <PACKET PATH>, bundle sha256:<BUNDLE HASH>,
for <REVIEW TARGET>. Read the complete declared files, diff and evidence.
Report P0/P1/P2 with file:line and a COVERAGE: line naming the files and diff
you read; approve only with no P0 and full coverage; report P1/P2 as nonblocking
findings. Bind revision approval
to the packet's verified PR URL, base and head; otherwise approve only the
named bundle. End with exactly one line:
VERDICT: APPROVED|NOT APPROVED|WITHHELD at <REVIEW TARGET> (WITHHELD with a reason).
```

## 3. Channel preambles

Each channel's preamble is the exact-SHA or saved-content header the orchestrator adds when it launches that
seat, and the packet must contain exactly the filled template. The orchestrator records the exact prompt in
`receipt.json` as `prompt` and `prompt_sha256`. For CLI
alternates, each `<review request>`, and the stdin of forms without one, is
exactly the preamble plus the template.

Coordinator ask (for example a Dot reviewer channel): the configured account
mentions, then `Advice vote requested.` on its own line, then the template.
Send it to each configured coordinator account in rotation.

The clone, export, read-only and saved-content preambles below apply to **every** CLI reviewer seat - Codex, Opus, the Claude
alternates, Cursor, AGY and any `ADVICE_EXTRA_CLIS` seat - and to static reviewers. They replace the header the
deleted helper used to inject; there is no other header to match, so a seat launched without one
cannot produce a byte-identical prompt and its vote is void.

Revision preamble for every CLI seat and for static reviewers (verbatim):

```text
Work only in the isolated clone at <SCRATCH PATH>; if your working
directory was set to it, stay there. Do not clone, fetch, check out another
commit, add a remote, or create any other copy - these are instructions, and the
orchestrator's post-return checks are what detect a clone whose HEAD or remote
changed. Never work in the original checkout or in a donor repository. Leave the
clone in place - the orchestrator verifies it and removes it after your process
exits. Use the GitHub token already present in your environment and
never print it. Do not modify the original checkout, refs, config or hooks. Do
not post anything; return your review as your final output.
```

Export preamble for every CLI seat and for static reviewers (verbatim):

```text
Work only in the exported tree at <SCRATCH PATH>; if your working
directory was set to it, stay there. The export contains no .git: it is a
snapshot of <SHA>, not a repository, so there is no history, no remote and
nothing to commit. Do not clone, fetch, add a remote, or create any other copy,
and do not run git commands that expect a repository. Your coverage depends on
reading both the tree and the change: read <SCRATCH PATH>/base.diff, the complete
`git diff <BASE SHA>..<SHA>` of the pinned change, and state in your COVERAGE line
that you read it. A review that covers only the head snapshot is not full coverage
and will be withheld. Never work in the original checkout or in a donor repository.
Leave the export in place - the orchestrator verifies it against the pinned tree
after your process exits and removes it afterwards. Use the GitHub token already
present in your environment and never print it. Do not modify any checkout, refs,
config or hooks. Do not post anything; return your review as your final output.
```

Read-only revision preamble for every CLI seat and for static reviewers (verbatim):

```text
Review read-only through GitHub/API or an existing checkout. Read the complete
pinned base-to-head diff, changed files and relevant supporting evidence.
Resolve mutable PR references to the requested SHA before reviewing; do not
substitute a later head or a truncated diff. No clone or export is required.
Do not modify any checkout, refs, config or hooks. Do not post anything;
return your review as your final output. Never print credentials.
```

Saved-content preamble for every CLI seat and for static reviewers (verbatim):

```text
Read only the named saved files and evidence in the given packet, checking each
against its recorded SHA256 and any declared revision binding. Do not modify any checkout, refs,
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
prompt sent, a `COVERAGE:` statement, the `VERDICT:` line, the actual clone path whenever one exists, or the export path for orchestrator-export
whenever one exists (read-only and saved-content review need no copy, so record `none`
there). Record full diff/file coverage, source URLs or paths, hashes and any PR/base/head
binding. Check checkout, refs, local config and hooks when a checkout was used;
record `not used` for an API-only review instead of inventing a filesystem check.
The orchestrator also verifies and
records that no reviewer process survives and that copy cleanup succeeded (clone or
export removal, per the seat's `isolation:` record); copy cleanup is `n/a` when
no copy was created, never an allocation requirement. For
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
