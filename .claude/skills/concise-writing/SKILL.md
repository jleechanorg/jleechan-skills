---
name: concise-writing
description: Use when prose runs long, repeats itself, opens with throat-clearing, hedges every claim, or pads sentences with adverbs and Latinate words. Trims prose without flattening it. Pairs with humanizer for AI-tell removal.
license: MIT
---

# Concise Writing

Short is not the goal. Clear is. These are the moves that cut without cutting meaning.

## Preserve meaning before trimming

The moves below are *defaults*. None of them apply unconditionally. **Do not change the factual content of the text.** If the source says "several failures," keep "several" unless an exact count is available. If the source says "issue," keep "issue" unless the actual diagnosis is known. If the source says "somewhat confident," keep the degree — "somewhat" carries material uncertainty that "confident" alone drops. Trimming rewrites the *words*, not the *facts* or the *stance* of the author.

When editing someone else's neutral prose (resumes, memos, docs, third-party email), do not inject opinions, humor, or feelings the author did not express — tightening does not mean adding a voice.

## When to use

Apply when the user asks to "tighten", "shorten", "trim", or "make this more concise". Apply to your own output when drafting PR descriptions, release notes, docs, memos, or replies that exceed what the situation needs. Skip for fiction, poetry, and cases where length is the point.

## The moves

**Cut adverbs.** "very", "really", "extremely", "quite", "rather", "fairly", "somewhat" — drop them when they are redundant (the verb already carries the weight, or the sentence is padding). **Keep them when they carry material intensity or uncertainty:** "somewhat confident" is not the same as "confident"; "fairly complete" is not the same as "complete"; "extremely toxic" is not the same as "toxic". Limit removal to redundant modifiers, or replace with wording that preserves the original degree.

> She was very tired → She was tired. / She was exhausted. (Redundant "very" — drop.)
> The report was quite long → The report was long. ("Quite" as filler — drop.)
> I am somewhat confident this will hold → KEEP "somewhat" — drops material uncertainty if removed.
> The toxin was extremely toxic → KEEP "extremely" — strengthens the claim.

**Lead with the outcome.** First sentence answers "what happened" or "what's the answer". No preamble.

> After investigating, I have determined that the test failure was caused by a race condition in the cache layer → Cache-layer race condition caused the test failure.

**One idea per sentence.** If you wrote "and" and started a new clause, split the sentence.

> The PR fixes the bug, and it also updates the docs → The PR fixes the bug. It also updates the docs.

**Short words over long ones.**

| long   | short     |
|--------|-----------|
| utilize | use      |
| facilitate | help |
| leverage | use       |
| commence | start    |
| terminate | end     |
| ascertain | find out |
| demonstrate | show   |
| subsequent | next   |
| prior to | before    |
| in order to | to    |
| at this point in time | now |
| due to the fact that | because |

**Drop hedging.** "might possibly perhaps" → "may". One hedge per claim, only when genuinely uncertain.

> It could potentially possibly be the case that the cache might be the issue → The cache may be the issue.

**Remove throat-clearing.** "It is important to note that...", "I would like to point out that...", "Please be advised that..." — delete.

> It is important to note that the migration completed successfully → The migration completed successfully.

**End sections without restating.** No "In summary...", "To recap...", "In conclusion...". If the prior sentences were clear, the summary is filler.

**Prefer active voice.** Subject does the verb.

> The bug was caused by the migration → The migration caused the bug.

**Kill "is"/"are" wrappers around gerunds.** "is showing", "is running", "is being processed" → the gerund alone, or active voice. **Preserve progressive aspect when it carries current state.** "The server is running the job" (in progress) is not the same as "The server runs the job" (habitual behavior). Strip the wrapper only when timing does not matter — status updates, live ops, in-flight actions keep the `-ing`.

> The server is running the job → The server runs the job. (OK for docs describing routine behavior.)
> The server is running the job → The server is running the job. (KEEP — describes in-flight state, e.g. in a status feed.)

**Numbers over hand-waving.** "many", "several", "various", "a number of" → a count, a range, or "some" — *only when an actual number is available*. If the source only said "several," keep "several" (or "some") rather than fabricating a count.

> Several users reported cache misses (N=4 reported between Mar–May) → Several users reported cache misses, four in the March–May window. (Use the count if you have it.)
> Several users reported cache misses → KEEP "several" if no count is available — do not invent one.

**Specific over vague.** "issue" → "cache miss", "problem" → "stale read", "thing" → "retry queue" — *only when the specific diagnosis is known*. If the source only said "issue," keep "issue" until an actual diagnosis is verified.

## Process

1. Read the text.
2. Cut the items above in order: throat-clearing → hedging → adverbs → long words → weak verbs → restated summaries.
3. Read aloud. Any sentence that doesn't earn its place, delete.
4. Stop before the prose sounds clipped. Some rhythm and connective tissue is human.

## Pair with humanizer

This skill trims; [humanizer](../humanizer/SKILL.md) strips AI tells. Use together: humanizer catches the patterns LLMs bake in (em-dash overuse, rule-of-three, "delve"/"tapestry"); concise-writing catches the patterns humans write when they overwrite (throat-clearing, adverbs, hedge stacks).