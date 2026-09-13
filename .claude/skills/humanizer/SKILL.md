---
name: humanizer
description: Use when editing or reviewing prose to remove AI-writing tells — em-dash overuse, rule-of-three padding, "delve"/"tapestry"/"pivotal" vocabulary, sycophantic openers, knowledge-cutoff hedging, fragmented headers. Also use on your own output before publishing release notes, PR descriptions, docs, or essays.
license: MIT
---

# Humanizer: Remove AI Writing Patterns

Identify and remove signs of AI-generated text. Based on [Wikipedia: Signs of AI writing](https://en.wikipedia.org/wiki/Wikipedia:Signs_of_AI_writing) (WikiProject AI Cleanup), derived from thousands of AI-generated text instances.

**Key insight:** LLMs use statistical algorithms to guess the most likely next token. That biases output toward the same handful of phrases, structures, and rhythms — the patterns below.

## When to use

Load when the user asks to "humanize", "de-AI", "de-slop", or "un-ChatGPT" text; when editing drafts (blog, essay, PR, docs, memo, email, tweet, resume) to sound natural; when matching the user's voice; when reviewing their text for AI tells before publishing. Also apply to **your own** output (release notes, PR descriptions, docs, long-form explanations) — a focused pass catches what slips past the default voice.

## How to use

Text arrives inline (rewrite in-place and reply), as a file (read it, then `patch` per section is cleaner than a full rewrite), or with a voice sample to match (read the sample first; mirror its sentence length, word level, transitions, punctuation habits). Always show the rewrite; for file edits, show the diff.

## Process

1. Identify instances of the 29 patterns below.
2. Rewrite each problematic section. Use `is/are/has` over `serves as/boasts/features`. Specific over vague. Active voice. Simple words.
3. Draft the rewrite.
4. Ask: "What makes the below so obviously AI generated?" Answer briefly with any remaining tells.
5. Revise one more time. Present the final version.

## Preserve facts, hedges, and meaning-bearing grammar

Several patterns below (notably pattern 5 "Vague attributions" and pattern 21 "Knowledge-cutoff disclaimers") illustrate rewrites that replace a hedge with a named source. Those are illustrative of *well-attributed* prose — only adopt that shape when an actual source is verified. If the source text says "experts believe," keep it hedged. Do NOT manufacture concrete facts (dates, names, statistics, registration numbers, survey years) the source did not contain.

**Do not strip these without checking meaning:**

- **Progressive aspect.** "The server is running the job" (in progress) ≠ "The server runs the job" (habitual). Keep `-ing` when reporting live state, in-flight operations, or current activity (status feeds, incident updates, release notes, ops dashboards).
- **Passive voice.** Keep when the actor is unknown, irrelevant, or required by genre (scientific, legal, incident reports).
- **Required copulas.** Strip `serves as/stands as/boasts` in favor of `is/has`, but keep `is` when removing it changes meaning (compliance language, definitions, requirements).

Strip wrappers only when the aspect, voice, or copula removal does not change the intended meaning.

## Personality and soul

Avoiding AI patterns is half the job. Sterile, voiceless writing is just as obvious as slop. Soulless signs: every sentence the same length, no opinions, no acknowledgment of uncertainty, no first-person when appropriate, no humor, no edge, reads like Wikipedia. Add voice by: having opinions, varying rhythm (short then long), acknowledging complexity, using "I" when it fits, letting some mess in (tangents, asides, half-formed thoughts), being specific about feelings ("there's something unsettling about agents churning away at 3am" not "this is concerning").

> The experiment produced interesting results. The agents generated 3 million lines of code. Some developers were impressed while others were skeptical.

> I genuinely don't know how to feel about this one. 3 million lines of code, generated while the humans presumably slept. Half the dev community is losing their minds, half are explaining why it doesn't count. I keep thinking about those agents working through the night.

## Patterns

### 1. Undue emphasis on significance, legacy, and broader trends

**Watch:** stands/serves as, is a testament/reminder, a vital/significant/crucial/pivotal/key role/moment, underscores/highlights its importance, reflects broader, symbolizing its ongoing/enduring/lasting, contributing to the, setting the stage for, marking/shaping the, represents/marks a shift, key turning point, evolving landscape, focal point, indelible mark, deeply rooted.

> The Statistical Institute of Catalonia was officially established in 1989, marking a pivotal moment in the evolution of regional statistics in Spain.

> The Statistical Institute of Catalonia was established in 1989 to collect and publish regional statistics independently from Spain's national statistics office.

### 2. Undue emphasis on notability and media coverage

**Watch:** independent coverage, local/regional/national media outlets, written by a leading expert, active social media presence.

> Her views have been cited in The New York Times, BBC, Financial Times, and The Hindu. She maintains an active social media presence with over 500,000 followers.

> In a 2024 New York Times interview, she argued that AI regulation should focus on outcomes rather than methods.

### 3. Superficial -ing analyses

**Watch:** highlighting/underscoring/emphasizing, ensuring, reflecting/symbolizing, contributing to, cultivating/fostering, encompassing, showcasing.

> The temple's color palette of blue, green, and gold resonates with the region's natural beauty, symbolizing Texas bluebonnets, the Gulf of Mexico, and the diverse Texan landscapes, reflecting the community's deep connection to the land.

> The temple uses blue, green, and gold. The architect said these were chosen to reference local bluebonnets and the Gulf coast.

### 4. Promotional / advertisement-like language

**Watch:** boasts a, vibrant, rich (figurative), profound, enhancing its, showcasing, exemplifies, commitment to, natural beauty, nestled, in the heart of, groundbreaking (figurative), renowned, breathtaking, must-visit, stunning.

> Nestled within the breathtaking region of Gonder in Ethiopia, Alamata Raya Kobo stands as a vibrant town with a rich cultural heritage and stunning natural beauty.

> Alamata Raya Kobo is a town in the Gonder region of Ethiopia, known for its weekly market and 18th-century church.

### 5. Vague attributions and weasel words

**Watch:** Industry reports, Observers have cited, Experts argue, Some critics argue, several sources/publications (when few cited).

> Experts believe the Haolai River plays a crucial role in the regional ecosystem.

> The Haolai River supports several endemic fish species, according to a 2019 survey by the Chinese Academy of Sciences.

### 6. Outline-like "Challenges and Future Prospects" sections

**Watch:** Despite its... faces several challenges..., Despite these challenges, Challenges and Legacy, Future Outlook.

> Despite its industrial prosperity, Korattur faces challenges typical of urban areas, including traffic congestion and water scarcity. Despite these challenges, with its strategic location and ongoing initiatives, Korattur continues to thrive as an integral part of Chennai's growth.

> Traffic congestion increased after 2015 when three new IT parks opened. The municipal corporation began a stormwater drainage project in 2022 to address recurring floods.

### 7. Overused AI vocabulary

**Watch:** actually, additionally, align with, crucial, delve, emphasizing, enduring, enhance, fostering, garner, highlight (verb), interplay, intricate/intricacies, key (adj), landscape (abstract noun), pivotal, showcase, tapestry (abstract noun), testament, underscore (verb), valuable, vibrant.

> Additionally, a distinctive feature of Somali cuisine is the incorporation of camel meat. An enduring testament to Italian colonial influence is the widespread adoption of pasta in the local culinary landscape, showcasing how these dishes have integrated into the traditional diet.

> Somali cuisine also includes camel meat, considered a delicacy. Pasta dishes, introduced during Italian colonization, remain common, especially in the south.

### 8. Copula avoidance

**Watch:** serves as/stands as/marks/represents [a], boasts/features/offers [a].

> Gallery 825 serves as LAAA's exhibition space for contemporary art. The gallery features four separate spaces and boasts over 3,000 square feet.

> Gallery 825 is LAAA's exhibition space for contemporary art. The gallery has four rooms totaling 3,000 square feet.

### 9. Negative parallelisms and tailing negations

Constructions like "Not only...but..." or "It's not just about..., it's..." are overused. So are clipped tailing-negation fragments ("no guessing", "no wasted motion") tacked onto sentence ends instead of written as real clauses.

> It's not just about the beat riding under the vocals; it's part of the aggression and atmosphere. It's not merely a song, it's a statement.

> The heavy beat adds to the aggressive tone.

> The options come from the selected item, no guessing.

> The options come from the selected item without forcing the user to guess.

### 10. Rule of three overuse

> The event features keynote sessions, panel discussions, and networking opportunities. Attendees can expect innovation, inspiration, and industry insights.

> The event includes talks and panels. There's also time for informal networking between sessions.

### 11. Elegant variation (synonym cycling)

> The protagonist faces many challenges. The main character must overcome obstacles. The central figure eventually triumphs. The hero returns home.

> The protagonist faces many challenges but eventually triumphs and returns home.

### 12. False ranges

LLMs use "from X to Y" where X and Y aren't on a meaningful scale.

> Our journey through the universe has taken us from the singularity of the Big Bang to the grand cosmic web, from the birth and death of stars to the enigmatic dance of dark matter.

> The book covers the Big Bang, star formation, and current theories about dark matter.

### 13. Passive voice and subjectless fragments

> No configuration file needed. The results are preserved automatically.

> You do not need a configuration file. The system preserves the results automatically.

### 14. Em dash overuse

LLMs use em dashes (—) more than humans, mimicking "punchy" sales writing. Most can be commas, periods, or parentheses.

> The term is primarily promoted by Dutch institutions—not by the people themselves. You don't say "Netherlands, Europe" as an address—yet this mislabeling continues—even in official documents.

> The term is primarily promoted by Dutch institutions, not by the people themselves. You don't say "Netherlands, Europe" as an address, yet this mislabeling continues in official documents.

### 15. Overuse of boldface

> It blends **OKRs (Objectives and Key Results)**, **KPIs (Key Performance Indicators)**, and visual strategy tools such as the **Business Model Canvas (BMC)** and **Balanced Scorecard (BSC)**.

> It blends OKRs, KPIs, and visual strategy tools like the Business Model Canvas and Balanced Scorecard.

### 16. Inline-header vertical lists

> - **User Experience:** The user experience has been significantly improved with a new interface.
> - **Performance:** Performance has been enhanced through optimized algorithms.
> - **Security:** Security has been strengthened with end-to-end encryption.

> The update improves the interface, speeds up load times through optimized algorithms, and adds end-to-end encryption.

### 17. Title case in headings

> ## Strategic Negotiations And Global Partnerships

> ## Strategic negotiations and global partnerships

### 18. Emojis

> 🚀 **Launch Phase:** The product launches in Q3
> 💡 **Key Insight:** Users prefer simplicity
> ✅ **Next Steps:** Schedule follow-up meeting

> The product launches in Q3. User research showed a preference for simplicity. Next step: schedule a follow-up meeting.

### 19. Curly quotation marks

ChatGPT uses curly quotes (U+201C “…”, U+201D …”) instead of straight ASCII ("…").

> He said “the project is on track” but others disagreed.

> He said "the project is on track" but others disagreed.

### 20. Collaborative communication artifacts

**Watch:** I hope this helps, Of course!, Certainly!, You're absolutely right!, Would you like..., let me know, here is a...

> Here is an overview of the French Revolution. I hope this helps! Let me know if you'd like me to expand on any section.

> The French Revolution began in 1789 when financial crisis and food shortages led to widespread unrest.

### 21. Knowledge-cutoff disclaimers

**Watch:** as of [date], Up to my last training update, While specific details are limited/scarce..., based on available information...

> While specific details about the company's founding are not extensively documented in readily available sources, it appears to have been established sometime in the 1990s.

> The company was founded in 1994, according to its registration documents.

### 22. Sycophantic / servile tone

> Great question! You're absolutely right that this is a complex topic. That's an excellent point about the economic factors.

> The economic factors you mentioned are relevant here.

### 23. Filler phrases

- "In order to achieve this goal" → "To achieve this"
- "Due to the fact that it was raining" → "Because it was raining"
- "At this point in time" → "Now"
- "In the event that you need help" → "If you need help"
- "The system has the ability to process" → "The system can process"
- "It is important to note that the data shows" → "The data shows"

### 24. Excessive hedging

> It could potentially possibly be argued that the policy might have some effect on outcomes.

> The policy may affect outcomes.

### 25. Generic positive conclusions

> The future looks bright for the company. Exciting times lie ahead as they continue their journey toward excellence. This represents a major step in the right direction.

> The company plans to open two more locations next year.

### 26. Hyphenated word pair overuse

**Watch:** third-party, cross-functional, client-facing, data-driven, decision-making, well-known, high-quality, real-time, long-term, end-to-end.

**Problem:** AI hyphenates common word pairs with perfect consistency. Humans rarely hyphenate these uniformly, and when they do, it's inconsistent. Less common or technical compound modifiers are fine to hyphenate.

**Rule:** never strip a hyphen from a compound modifier that comes before a noun. The result is a grammatical regression ("cross functional team," "high quality report," "client facing tools," "decision making process," "detail oriented"). Hyphen-stripping is allowed only when the compound is NOT modifying a noun — e.g. "the data is data driven" (predicate), "we work cross-functionally" (adverb).

If the paragraph shows nearly every common pair hyphenated (a stylistic AI tell), flag the paragraph and rewrite by **varying the phrasing or splitting into shorter sentences** — do NOT fix over-hyphenation by removing required hyphens.

> The cross-functional team delivered a high-quality, data-driven report on our client-facing tools. Their decision-making process was well-known for being thorough and detail-oriented.

> The cross-functional team delivered a high-quality, data-driven report on our client-facing tools. Their decision-making process was known for being thorough and detail-oriented. (Only the well-known → known trim was applied; compound-modifier hyphens were preserved.)

> The team delivered a report on tools that clients face. They had a process for making decisions, and it was thorough. (Over-hyphenation in a paragraph was addressed by rewriting the sentences, not by removing required hyphens.)

### 27. Persuasive authority tropes

**Watch:** The real question is, at its core, in reality, what really matters, fundamentally, the deeper issue, the heart of the matter.

> The real question is whether teams can adapt. At its core, what really matters is organizational readiness.

> The question is whether teams can adapt. That mostly depends on whether the organization is ready to change its habits.

### 28. Signposting and announcements

**Watch:** Let's dive in, let's explore, let's break this down, here's what you need to know, now let's look at, without further ado.

> Let's dive into how caching works in Next.js. Here's what you need to know.

> Next.js caches data at multiple layers, including request memoization, the data cache, and the router cache.

### 29. Fragmented headers

A heading followed by a one-line paragraph that restates the heading before the real content begins.

> ## Performance
>
> Speed matters.
>
> When users hit a slow page, they leave.

> ## Performance
>
> When users hit a slow page, they leave.

## Output

1. Draft rewrite
2. "What makes the below so obviously AI generated?" (brief bullets)
3. Final rewrite
4. Optional one-line change summary

## Attribution

Ported from [blader/humanizer](https://github.com/blader/humanizer) (MIT), based on [Wikipedia: Signs of AI writing](https://en.wikipedia.org/wiki/Wikipedia:Signs_of_AI_writing) (WikiProject AI Cleanup). All 29 patterns, personality section, and before/after examples preserved from the source. See `LICENSE` in this directory for the MIT license.