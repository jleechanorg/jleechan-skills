# Plan granularity baseline, 2026-08-04 through 2026-08-06 PST

## Result

This reference reports different measurements. They use different populations
and rubrics, so none is a substitute for another.

| Measurement | Population and rubric | Result | What it answers |
|---|---|---:|---|
| Roadmap observed-corpus planning-artifact frequency | The 116 Markdown addition events in the committed [roadmap inventory](roadmap-markdown-additions-2026-08-04-06.tsv), scored for ordered or dependent future work, a concrete scope anchor, and an executable acceptance or test criterion | 56/116 (48.3%) | How often the frozen observed roadmap additions were executable planning artifacts |
| Formal-plan granularity | The curated 16-document sample below, scored for ordered work, scope, acceptance, test/proof, dependencies, and Bead mapping | 15/16 | How completely the sampled formal plans satisfy the six-field planning rubric |
| Document-listed Bead granularity | The 35 task-level Bead rows exposed by four pinned plan documents, scored for scope, explicit acceptance/test proof, and dependency/order | 26/35 | How completely those documented planning rows specify executable work |
| Bead-event frequency | Created or updated Bead events during the window | not measurable | No trustworthy event ledger or denominator is available |
| Session planning-episode frequency | Deduplicated assistant-authored planning episodes during the window | not measurable | The archives were enumerated but were not classified to completion |

The roadmap figure is an observed-corpus frequency. It covers
Markdown addition events in the committed inventory, not unique final paths,
all plans ever written, Bead events, or assistant planning episodes.
This is not an exhaustive population claim because the mutable ref set and exact
capture time were not recorded. A path added more than once is counted once
per event.

## Rubric

A roadmap addition is a planning artifact only when its inventory row has all
three fields: ordered or dependent future work, a concrete scope anchor, and an
executable acceptance or test criterion.

A formal roadmap row is granular only when all six fields are present: ordered
work, scoped files or areas, acceptance criteria, tests or proof, dependencies,
and Bead mapping. A document-listed Bead row is granular only when it has
concrete scope, explicit acceptance or test proof, and dependency or ordering.
The two samples use only their own stated populations.

## Roadmap planning-artifact frequency

The committed [roadmap inventory](roadmap-markdown-additions-2026-08-04-06.tsv)
is the frozen 116-event audit corpus observed for August 4 through August 6,
2026 PST. Every row pins the creation commit and source-blob SHA-256, preserves
re-additions as distinct events, and records the three-field rubric result. It
can validate every included event, but cannot prove that mutable refs exposed
no additional in-window event when the original sweep ran.

Fifty-six of 116 rows satisfy all three fields, for a planning-artifact
frequency of 48.3%. The remaining 60 rows are 16
status/activity/cookie-state documents, 11 postmortems, 13 reports or reference
results, 15 verdict/reconciliation receipts, and 5 onboarding/data-reference
documents. This does not claim that later revisions remain current or that the
same rate applies outside the window.

## Formal-plan sample

This is a curated 16-document sample, not a population frequency. Its 15/16
result answers only the six-field formal-plan rubric defined above.

The roadmap source revision was
[a0650bbc](https://github.sc-corp.net/jleechan/roadmap/commit/a0650bbc1421b7cae867fb5d332a1ead45a75bd4).
Three `/e` and `/p` lanes independently inspected formal-plan history,
roadmap documents, and Bead stores. The denominator is exactly this curated sample,
not every filename returned by the sweep. The lanes excluded status snapshots,
logs, postmortems, goal-ironclad contracts, and additional plan-like files they
did not score. This avoids presenting a purposive sample as an exhaustive file
selection.

- [2026-08-04-nextsteps-snap-bench.md](https://github.sc-corp.net/jleechan/roadmap/blob/78e6de152ee16f910823b8a0991d06f3a093eb12/2026-08-04-nextsteps-snap-bench.md)
- [nextsteps-2026-08-04-agent-loop-harness.md](https://github.sc-corp.net/jleechan/roadmap/blob/a0bb4a3da72bf957a674be1e91f32e061efc888e/nextsteps-2026-08-04-agent-loop-harness.md)
- [nextsteps-2026-08-04-databricks-installer-stop.md](https://github.sc-corp.net/jleechan/roadmap/blob/5ba55df16333194623b70654889c4ef72e553cdd/nextsteps-2026-08-04-databricks-installer-stop.md)
- [nextsteps-2026-08-04-llm-router-pr-design-handoff.md](https://github.sc-corp.net/jleechan/roadmap/blob/489a2f63b393f0532c2e3dc838a3c9b062318a11/nextsteps-2026-08-04-llm-router-pr-design-handoff.md)
- [nextsteps-2026-08-04-v2full-sanctioned-admission.md](https://github.sc-corp.net/jleechan/roadmap/blob/660ccd4a85df16ab5f7ca5847521f06efc78a419/nextsteps-2026-08-04-v2full-sanctioned-admission.md)
- [nextsteps-2026-08-04-v2light-admission-decoupling.md](https://github.sc-corp.net/jleechan/roadmap/blob/6f01debd981f35712632ea29da9dcf2e9e7b5b75/nextsteps-2026-08-04-v2light-admission-decoupling.md)
- [2026-08-05-agi-inference-inflight-pr-roadmap.md](https://github.sc-corp.net/jleechan/roadmap/blob/a66f2dd25baff3af38217473b0d43d66b5fc5308/2026-08-05-agi-inference-inflight-pr-roadmap.md), the sole strict-rubric exception
- [2026-08-05-python-installer-replacement-plan.md](https://github.sc-corp.net/jleechan/roadmap/blob/9d5330412046aaab0da1db3bcd2a5a393f557bb2/2026-08-05-python-installer-replacement-plan.md)
- [nextsteps-2026-08-05-llm-router-p0.md](https://github.sc-corp.net/jleechan/roadmap/blob/5344e815f355a1ceca86fb1cce1b91502b97d928/nextsteps-2026-08-05-llm-router-p0.md)
- [nextsteps-2026-08-05-m1-router-review-readiness-handoff.md](https://github.sc-corp.net/jleechan/roadmap/blob/52e529de95b7b6580b4c12744afc992aab257a60/nextsteps-2026-08-05-m1-router-review-readiness-handoff.md)
- [nextsteps-2026-08-05-snapbench-hermetic-mvp.md](https://github.sc-corp.net/jleechan/roadmap/blob/86da57bdcdd4e40164913063f960de95244aeb0b/nextsteps-2026-08-05-snapbench-hermetic-mvp.md)
- [nextsteps-2026-08-06-agi-inference-pr88-framing.md](https://github.sc-corp.net/jleechan/roadmap/blob/5ba5a5333d4bca49f23210a5a579652a08fba4e2/nextsteps-2026-08-06-agi-inference-pr88-framing.md)
- [nextsteps-2026-08-06-beads-dolt-reconciliation.md](https://github.sc-corp.net/jleechan/roadmap/blob/3f8506ff1e4e7775dae6c938b9a524c2ac3a466d/nextsteps-2026-08-06-beads-dolt-reconciliation.md)
- [nextsteps-2026-08-06-or-arc-sidekick-closeout.md](https://github.sc-corp.net/jleechan/roadmap/blob/0314ecbfd26a34a5875c32f887b779ca18e92493/nextsteps-2026-08-06-or-arc-sidekick-closeout.md)
- [nextsteps-2026-08-06-provider-matrix-expansion.md](https://github.sc-corp.net/jleechan/roadmap/blob/89e2d824832e175a97a04722beeebd8bcac3cf93/nextsteps-2026-08-06-provider-matrix-expansion.md)
- [nextsteps-2026-08-06-snapbench-phase-a-evidence-durability.md](https://github.sc-corp.net/jleechan/roadmap/blob/c1003b2f7d62cbaa95bb103e00cd3b7beaddda7e/nextsteps-2026-08-06-snapbench-phase-a-evidence-durability.md)

## Per-item scoring

The row order matches the pinned manifest above.

| Row | Ordered | Scope | Acceptance | Test/proof | Dependencies | Bead |
|---|---:|---:|---:|---:|---:|---:|
| 01 | Y | Y | Y | Y | Y | Y |
| 02 | Y | Y | Y | Y | Y | Y |
| 03 | Y | Y | Y | Y | Y | Y |
| 04 | Y | Y | Y | Y | Y | Y |
| 05 | Y | Y | Y | Y | Y | Y |
| 06 | Y | Y | Y | Y | Y | Y |
| 07 | Y | Y | Y | Y | Y | N |
| 08 | Y | Y | Y | Y | Y | Y |
| 09 | Y | Y | Y | Y | Y | Y |
| 10 | Y | Y | Y | Y | Y | Y |
| 11 | Y | Y | Y | Y | Y | Y |
| 12 | Y | Y | Y | Y | Y | Y |
| 13 | Y | Y | Y | Y | Y | Y |
| 14 | Y | Y | Y | Y | Y | Y |
| 15 | Y | Y | Y | Y | Y | Y |
| 16 | Y | Y | Y | Y | Y | Y |

## Excluded lanes and limits

The formal-history lane also scored 13/13 artifacts under a three-field rubric,
but three inputs were untracked local Claude plan files. Local-only limitation:
that result is excluded from the durable headline.

The Bead lane found one uncommitted local interaction line for `roadmap-909` in
`~/roadmap/.beads/interactions.jsonl`, but the issue was absent from the current
payload and SQLite store. The local file's observed SHA-256 was
`20a0dc2923846365709dd78abd3de2441ee93f38c8e3f1cf52d66b21333223df`.
Because this source is uncommitted and the stores disagree, Bead granularity is
not measurable for the window. Treating that line as a complete denominator
would overstate the evidence.

## Planning Beads named in documents

This is a document-derived sample of 35 task-level rows, not a Bead-event
history. Its 26/35 result answers only the three-field task-row rubric above.

The Bead-event ledger could not supply dates, but four pinned plans exposed 35
unique task-level identifiers that could be scored as planning records:

| Source | Beads | Granular |
|---|---:|---:|
| [Agent-loop harness](https://github.sc-corp.net/jleechan/roadmap/blob/a0bb4a3da72bf957a674be1e91f32e061efc888e/nextsteps-2026-08-04-agent-loop-harness.md) | 8 | 8 |
| [LLM-router provider/client matrix](https://github.sc-corp.net/jleechan/roadmap/blob/a269d87014889e3e6d83d20cf905ae16bd261dd8/2026-08-04-llm-router-pilot-provider-client-matrix.md) | 9 | 0 |
| [Provider-matrix expansion](https://github.sc-corp.net/jleechan/roadmap/blob/89e2d824832e175a97a04722beeebd8bcac3cf93/nextsteps-2026-08-06-provider-matrix-expansion.md) | 10 | 10 |
| [Snapbench Phase A](https://github.sc-corp.net/jleechan/roadmap/blob/c1003b2f7d62cbaa95bb103e00cd3b7beaddda7e/nextsteps-2026-08-06-snapbench-phase-a-evidence-durability.md) | 8 | 8 |

The matrix's nine open task rows lacked per-Bead acceptance and dependency
fields. Parent/index identifiers and three closed historical references were
excluded. The resulting inspectable planning score is 26/35. It measures Beads
as documented plans, not confirmed `bd create` or `bd update` events.

## Unavailable Bead-event and session rates

No trustworthy Bead-event denominator is available: the stores were split and
stale, and the observed local interaction record was uncommitted and absent
from the current payload and SQLite store. Therefore this reference reports no
Bead-event frequency.

The session archive enumeration found 1,335 Codex JSONL files, 13,728
assistant-message records, and 2,132 Claude JSONL files with target-date
timestamps. Structural filtering and semantic classification did not finish,
so this reference reports no session planning-episode frequency. These counts
describe archive discovery only; they are not planning rates.

