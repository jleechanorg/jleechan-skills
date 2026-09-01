---
name: document-standards
description: Project-agnostic review or revision of prose documents (roadmap docs, reports, status docs, handoffs, Google Docs, HTML) for truth, economy, readability, structure, and output correctness — optimized for human reading. Adapts /code-standards' five-lane pattern to documents. Dispatched by the /document-standards command.
revision_marker: DOCUMENT_STANDARDS_COMMAND_V1
---

# Document Standards Dispatch

Reviews or revises prose documents using five independent lanes. This skill is
the source of truth; the dispatcher at `${CLAUDE_HOME:-$HOME/.claude}/commands/document-standards.md`
is a thin entry point. Every standard here is evidence-driven, traced to
observed doc-revision patterns or to a named source skill.

The dispatcher resolves `CLAUDE_HOME` to support isolated installs (e.g.
`CLAUDE_HOME=/tmp/jleechan-skills.test/claude bash install-claude-commands.sh`).
The smoke-test section below reports paths using the same `CLAUDE_HOME`
substitution so the diagnostic matches both source-of-truth and isolated
install layouts.

## Supporting skills

The inline rubric in each lane below is load-bearing on its own — the skill
runs without any of these. They are optional companions that run the lane as a
real, full pass when installed; substitute an equivalent if you have one.

| Skill | Use |
|-------|-----|
| Ponytail | Economy lane — deletion-first ladder, adapted to prose |
| Thermo-nuclear code quality | Pattern source for the doc-audit rubric in lane 4 |
| Writer | Prose-level AI-tell, voice, and rhythm rules (optional polish pass) |
| gdocs-access | Google Docs tool order and edit-in-place rules |
| pr-description-sections | Durable-state writing, zero-context reader, section order, User Story requirement |

## Universal lanes

1. **Truth & contract** — every claim in the doc matches its source.
   - Every number traces to a named artifact, query, or commit from which it
     can be re-derived. A number that cannot be re-derived is withdrawn, not
     softened.
   - A present-tense claim about external state (code semantics, deploy status,
     ownership) is verified at the exact current SHA/state, never inferred
     from a commit message or an earlier correction.
   - The doc describes the durable current state. Investigation chronology,
     superseded drafts, and review-response history move to a clearly-labeled
     historical appendix or are deleted (pr-description-sections's "write for the state
     right after the work lands").
   - No orphaned status labels: a PENDING/WIP/TBD/provisional marker either
     resolves before delivery or is a deliberate, dated disclosure — never a
     stale sentence.
   - No fabricated status, no "verified" without evidence, per the global
     no-fabricated-status rule.
   - **Categorization claims trace to the source's own structure, the same
     way numbers trace to a re-derivable artifact.** When content is split
     across topical buckets pulled from an existing structured source (a
     deck's sections, a codebase's modules, a doc's own headings), verify
     each item against that source's actual boundary before writing the
     summary — not from how the content superficially reads. Surface
     topic-matching ("this sounds like a process/workflow item") is a
     hypothesis, not a classification; a fact that reads as generic can
     belong entirely to one feature's internals if that is where the source
     already puts it. Incident (2026-08-25): a conference-abstract draft put
     a product's own engine internals (routing, context budget) under a
     generic "dev workflow" bucket because they read like process concepts —
     the source deck's own section headings already said otherwise.
2. **Economy (ponytail for prose)** — deletion before addition, say it once.
   - The prose ladder: does this section/sentence need to exist at all → does
     another section already say it (merge, link, don't restate) → can it be
     one line → only then write the minimum (ponytail rungs 1–7 mapped to
     prose).
   - Each fact has one canonical home; other sections link to it. Boilerplate
     restated per-section is a defect.
   - A revision pass reports what it deleted. If the doc grew, name what was
     removed to compensate or justify the growth in one line.
   - Any audit must emit a "cut candidates" list, not only additions.
   - **Empty slots stay empty.** A template slot (subtitle, kicker, deck,
     summary line, caption) with nothing new to say is deleted, not filled.
     Generating plausible prose to occupy structure is the most common source
     of filler, because an empty slot reads as unfinished while a filled one
     passes visual review. "The layout expects text here" is not a reason for
     text to exist.
   - **Every sentence names a fact, a constraint, a decision, or a
     consequence.** A sentence that only sets up, reassures, transitions, or
     describes the artifact itself is cut. Apply the deletion test above:
     if removing it loses no information, it was never content.
3. **Readability & structure** — human-first, scannable, BLUF.
   - The first screen answers what this is, what the outcome is, and what the
     reader does next, without scrolling ("audience is someone with zero
     context and a top-level exec summary").
   - Zero-context test: every proper noun, ticket ID, or prior doc referenced
     is linked or one-line glossed. Long docs get a table of contents.
   - Heading hierarchy is consistent; tables carry dense parallel data, prose
     carries narrative — not the reverse. Dense is the goal; bloated is the
     defect.
   - One voice, one tense (present for current state).
   - **PR descriptions**: when the target is a PR description (or the repo's
     `.github/pull_request_template.md`), the Background/Summary section is
     followed by a **User Story** stated in plain, non-technical language —
     what does the user encounter today (the problem/friction/bug) and what
     changes for them after this PR, with no jargon or internal file/function
     names. An implementation summary ("refactors X to use Y") does not
     satisfy this; it must be legible to someone who has never read the code.
     A PR with zero user-facing effect states that explicitly ("No user-facing
     change — pure refactor/CI-only") rather than omitting the section. When
     the repo has a project-specific story docset (e.g. worldarchitect.ai's
     `docs/user-stories-ui/US-###.md` / `NEW-<slug>.md`, per its
     `user-story-worldai` skill), link the matching doc for full detail — the
     link is additional context, not a substitute for the one-sentence
     before/after; a bare link with no sentence does not satisfy this section.
     If the PR introduces new user-facing behavior with none, flag that a
     story doc should be added. See the `pr-description-sections` skill for
     the canonical section list.
   - **Run the AI-tell sub-pass** (catalogue and discriminator below) over the
     doc's own prose. This is a required part of lane 3, not optional polish.
     The `writer` skill's lexicon and rhythm rules, if installed, extend it.
4. **Thermo-style document audit** — the strict structural pass, adapted from
   the thermo rubric (the code-standards lane-4 analog). The rubric below is
   the load-bearing content; run it in full, never a from-memory summary. This
   lane runs as a **real audit pass**: apply every question below to the
   document and return findings, not vibes.
   - Is there a "doc judo" move — a restructuring that deletes whole sections
     by reframing (e.g. one appendix absorbing three scattered caveat
     paragraphs)?
   - Did the doc cross a healthy size boundary for its genre? (A status doc
     that doubled without a scope change is a smell, like thermo's 1k-line
     rule.)
   - Are there scattered special-case caveats bolted onto unrelated sections —
     the prose spaghetti analog — that belong in one disclosures appendix?
   - Does every section earn its keep, or is some a thin wrapper restating the
     exec summary?
   - Would a zero-context fresh reader reconstruct the doc's claims and find
     every referenced artifact? Run that read; content-addressed placement
     beats filename-addressed.
   - Flag aggressively: sections that move complexity around without deleting
     it, chronology masquerading as structure, duplicate tables with drifted
     numbers, "temporary" framing likely to become permanent.
   - Output: few high-conviction structural findings, prioritized — never a
     flood of cosmetic nits (thermo's output-expectations rule).
5. **Output & operability** — the doc must work in its target surface.
   - **Link everything linkable.** Every reference to an artifact that has a
     URL appears as a clickable link on first mention in each section: pull
     requests / issues / commits / files / gists, Google Docs / Sheets /
     Slides, tickets, dashboards, wiki pages, monitoring boards. A bare
     ticket number, repo name, or "the strategy doc" is a defect — a reader
     must never have to search for a source the author already had. Construct
     them: `https://<git-host>/<owner>/<repo>/pull/<N>` (also `/issues/<N>`,
     `/commit/<sha>`, `/blob/main/<path>`), ticket
     `https://<tracker-host>/browse/<KEY>`, gdoc
     `https://docs.google.com/document/d/<id>`. When a referenced thing has no
     URL, say so inline ("no tracking issue exists") rather than leaving a bare
     identifier — the absence is itself information. Cross-surface docs link
     *to each other* both ways, so neither is a dead end.
   - Formatting invariants: times in the reader's local timezone (never UTC
     unless the audience is global); paths `~/`-relative (never literal home
     directories); effort as delta LOC/files/PRs, never calendar time.
   - Surface-render check: before delivery, open the doc in its target surface
     (rendered Markdown, HTML, or Google Doc) and check for escaping artifacts
     (literal `\n`, vertical tabs, eaten line-continuations), broken tables,
     and unclickable links.
   - Markdown: standard GFM; no HTML unless the renderer is known to accept it.
   - HTML: self-contained (inline CSS/JS), no external fetches, opens from
     `file://`.
   - Google Docs: **edit in place, never a parallel doc.** Before creating
     a new doc, check for an existing one on the topic. Use your Google Docs
     integration's in-place edit tools (section update, text replace, append,
     insert). Structural in-place edits (delete-to-header + heading rewrite +
     table row ops) are a known damage class — a *verified damaged* doc may
     be regenerated fresh with the old one bannered SUPERSEDED, never silently
     abandoned. After any gdoc edit, export to Markdown and diff-check the
     sections you did not intend to touch; remember `<pre>` newlines can
     export as vertical tabs (`\x0b`) and trailing backslash
     line-continuations can be eaten.
   - Multi-surface sync: when the doc exists in N surfaces (local md, gdoc,
     repo mirror), name all N; a revision lands on all of them in the same
     work block or carries an explicit "surfaces pending" note. "Updated"
     means pushed and URL-verifiable.

## AI-tell sub-pass (runs inside lane 3)

LLM-drafted prose converges on a small set of constructions that *sound*
authoritative while carrying no information. Scan for the catalogue below, then
apply the discriminator to every hit. The goal is to delete hollow instances —
**not** to ban contrast, parallelism, emphasis, or em dashes as forms.

### Discriminator — run before flagging anything

A hit is a **defect** only if it fails all three tests:

1. **Deletion test** — cut the phrase or clause. If the paragraph loses no
   fact, number, constraint, or decision, it was filler.
2. **Referent test** — for contrastive/negation forms, does the rejected half
   name a position someone actually holds, or a thing the doc actually does
   elsewhere? A rejected half nobody proposed is a strawman built to
   manufacture profundity.
3. **Evidence test** — is the assertion backed within one sentence by a
   number, artifact, source, or falsifiable consequence? Lane 1 asks whether a
   claim is *true*; this asks whether its rhetorical packaging is *earned*.

A hit passing any one test is **fine** — record it as checked-and-cleared, do
not rewrite it. `X, not Y` where Y is a real alternative that was actually on
the table, stating a falsifiable distinction, is good writing. So is a
three-item list whose three items are genuinely the three items. So is an em
dash setting off a real aside. False-positive churn on legitimate prose is a
worse failure than missing one tic.

**Exempt from this pass entirely:** verbatim quotations from humans,
transcripts, chat logs, cited speech, and any block the doc marks
"preserve verbatim". Never rewrite someone's actual words to fix a tic.

### Protected class: Honesty qualifiers

Sentences that bound, source, scope, or disclaim a nearby claim are not filler,
even when they fail the deletion test on their own. Examples include: source and
provenance attributions ("Sources: X, 2018–2026"; "measured over N days");
scope limits ("not shown"; "excludes"; "this window only"); portability and
dependency caveats ("depends on my own infrastructure"; "requires authenticated
access"); maturity and confidence disclaimers ("alpha"; "unverified"); and
precision hedges a specialist would demand ("a floor, not a measurement";
"estimated, not confirmed").

Run this test instead: **If this line is removed, does the remaining claim
become stronger than the evidence supports?** If yes, it is load-bearing — keep
it. The asymmetry matters: cutting filler costs a few words; cutting a qualifier
converts an honest claim into an overclaim, and no reviewer of the tightened copy
can see what's missing. Honesty qualifiers are a constraint layer, not a style
choice.

### Catalogue

| Pattern | Example form | Why it's a red flag |
|---|---|---|
| Negative parallelism | "not just X, it's Y" / "X, not Y" / "X rather than Y" | Manufactures a reveal; the rejected half is often a strawman nobody proposed |
| Staged negation | "Not X. Not Y. Just Z." | Artificial tension; the narrowing is decorative, not logical |
| Self-posed question | "The result? A rewrite." | Answers a question no reader asked, for unearned drama |
| False-suspense transition | "Here's the thing" / "here's the kicker" / "the truth is" | Promises payoff before an unremarkable line |
| Throat-clearing opener | "In today's fast-paced world" / "in the ever-evolving landscape of" | Pure preamble; carries zero information about the subject |
| Empty transition | "it's important to note" / "it's worth noting" / "notably" | Announces a point instead of connecting it to the prior argument |
| Signposted conclusion | "in conclusion" / "at the end of the day" / "ultimately" | Restates rather than concludes; readers can see the end |
| Invitation framing | "let's dive into" / "let's break this down" / "imagine a world where" | Pedagogical hand-holding; assumes the reader needs escorting |
| Copula dodge | "serves as" / "stands as" / "represents" / "marks a" instead of "is" | Inflates a plain statement into ceremony |
| Significance inflation | "pivotal" / "transformative" / "game-changer" / "groundbreaking" / "revolutionize" | Asserts importance the evidence has not established |
| Magic adverbs | "quietly" / "fundamentally" / "remarkably" / "deeply" | Borrowed intensity; delete and the sentence is unchanged |
| AI-vocabulary density | delve, leverage, robust, seamless, cutting-edge, harness, unlock, elevate, tapestry, realm, landscape, underscore, crucial | Individually harmless, collectively diagnostic; each usually has a plainer word |
| Rule-of-three padding | "robust, scalable, and efficient" | Third item added for cadence, not content; check each item earns its slot |
| Anaphora run | three+ consecutive sentences opening identically | Rhythm substituting for argument |
| Participle tack-on | "…, underscoring its role in X" | Smuggles an unattributed opinion onto a factual clause |
| False range | "from prototypes to policy" | Endpoints are not on any real spectrum; it's a list wearing a scale |
| Vague attribution | "experts agree" / "industry reports show" / "studies suggest" | Unnamed source; lane 1 requires a re-derivable citation |
| Invented concept label | "the supervision paradox" / "the acceleration trap" | Coined compound sounds analytical but is never defined or tested |
| Concessive formula | "Despite its challenges, X remains…" | Raises an objection only to dismiss it on schedule, unexamined |
| Grandiose stakes | framing a routine change as industry-defining | Scale claim with no measurement behind it |
| Em-dash addiction | dashes as the default connector throughout | Every clause reads as a dramatic aside; vary the punctuation |
| Bold-first bullets | every list item opening with a bolded lead-in | Documentation tic; fine occasionally, a tell when it's every item |
| One-point dilution | the same argument restated in three framings | Length without added information (overlaps the economy lane) |
| Artifact meta-commentary | "here's the arc" / "what follows is" / "in this section" / "this doc covers" / "let's look at" | Describes the container instead of its contents; the reader can see the structure |
| Preemptive reassurance | "no prior context needed" / "don't worry about the details" / "simply" / "just" / "easy to see" | Tells the audience how to feel instead of telling them something; usually defends against an objection nobody raised |
| Slot-filled subhead | a subtitle/deck/kicker that only restates its own heading or the visible items beneath it | Written because a template slot existed, not because there was a second thing to say |
| Self-certifying quality | "rigorous" / "carefully" / "thoroughly" / "properly" applied to one's own work | Asserts the standard instead of showing the evidence that meets it |
| **NOT a pattern — do not flag** | "Sources: …" / "not shown" / "alpha" / "depends on my own infrastructure" / "a floor, not a measurement" | Honesty qualifier. Looks like filler because it does not advance the argument — it constrains the claim. See *Protected class* above before flagging any line of this shape |

### Output for this sub-pass

Report each finding as: **exact quote** → **which test(s) it failed** →
**concrete rewrite**. Emit high-conviction findings only, per lane 4's
output-expectations rule — a flood of cosmetic nits is itself a failure mode.
Explicitly list the patterns you checked and cleared, so the pass is auditable
and the author can see what was considered rather than only what was cut.

## Workflow

When invoked as `/document-standards <target>`:

1. **Define the target**: a doc path, a gdoc URL, an HTML file, or a prose
   diff. If none given, use the doc most recently touched in the session.
2. **Identify the genre and audience** (status doc, exec report, handoff,
   design doc, gdoc, PR description) — the audit tunes to it (BLUF depth,
   appendix policy).
3. **Read the whole doc** (or the relevant sections plus their neighbors).
   Read linked sources for any claim being checked in lane 1.
4. **Load ponytail** if installed (the deletion-first ladder that prevents
   additive bloat). When ponytail is not installed, apply the inline economy
   rubric in lane 2 directly — same deletion-first ladder, just from this
   file. The skill stays portable across hosts that don't bundle ponytail.
5. **Run the five lanes.** Each returns PASS with section/line evidence, or
   FAIL with the exact location and required fix; N/A only with a reason.
   Lane 4 must cite findings from actually applying the rubric above.
6. **Reconcile** into the report format below. For revision (not just review)
   requests, apply fixes per the smallest-edit philosophy: targeted Edits,
   never a `Write` over a multi-section doc.

## Report format

| Lane | Verdict | Evidence (section/line) | Required fix |
|---|---|---|---|
| Truth & contract | PASS/FAIL/N-A | | |
| Economy (ponytail) | PASS/FAIL/N-A | | |
| Readability & structure | PASS/FAIL/N-A | | |
| ↳ AI-tell sub-pass | PASS/FAIL/N-A | | |
| Thermo-style doc audit | PASS/FAIL/N-A | | |
| Output & operability | PASS/FAIL/N-A | | |

State that the thermo-style rubric ran in full (lane 4). Append a **Cut
candidates** list (economy lane's output requirement), an **AI-tell findings**
list (quote → failed test → rewrite, plus patterns checked and cleared) and,
for multi-surface docs, a **Surface sync status** note.

## Smoke-test mode

If the argument is exactly `smoke-test` (not a substring match — `/document-standards smoke-test-foo`
should still run the lanes), do not run lanes and do not edit files. Report:

- that the command file loaded,
- the command file path (`${CLAUDE_HOME:-$HOME/.claude}/commands/document-standards.md`),
- this skill file path (`${CLAUDE_HOME:-$HOME/.claude}/skills/document-standards/SKILL.md`),
- the ponytail skill (economy lane source, if installed),
- the rubric lane this command runs (thermo-style doc audit),
- the marker for this revision: `DOCUMENT_STANDARDS_COMMAND_V1`.

## Relationship to /code-standards

`/code-standards` reviews code, diffs, and PRs; `/document-standards` reviews
prose. When a PR changes both, run both commands against their respective
surfaces. Neither replaces the other.

