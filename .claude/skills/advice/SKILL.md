---
name: advice
description: "Token-efficient second opinion slash command /advice. Extracts the decision point plus a pointer to the change (PR / ref / paths) so each reviewer reads the code itself, then fans out in parallel to up to four reviewers: (1) Opus subagent with a cursor→agy→claude -p CLI fallback chain, (2) /research on the decision topic, (3) /secondo multi-model opinion, (4) /web-advice browser review. Reviewers A and B are the portable core; C and D need personal infrastructure and are skipped when unavailable. Use instead of advisor() which ships the full conversation uncached."
---

# /advice — Token-Efficient Second Opinion

**Replaces `advisor()`. Never call advisor() — use this instead.**

## When invoked

`/advice [optional: specific question]` — invoked manually or automatically at a decision point.

## Step 1: Build the review packet

From the current conversation, extract:
- **Decision** (3–5 sentences): what specifically needs a second opinion — be concrete about constraints and tradeoffs
- **Pointer**: where the reviewer can read the change *itself* — a PR number, a `base...head` ref, or an explicit file-path list. Include `git diff --stat` (or `gh pr diff --name-only`) so the reviewer sees the shape of what it is about to read.

If no specific question was passed, infer from most recent context.

**Send the pointer, not a transcription.** Every reviewer transport in Step 2 is an *agent* that can read the repo for itself — the Opus subagent has Read/Grep/Bash, `cursor -p` has "access to all tools, including write and shell", `agy`/`claude -p` run with permissions pre-approved, `/secondo` gathers its own `git diff origin/main...HEAD`, and `/web-advice` inspects the PR directly. Handing them a pre-chewed excerpt does not save them a fetch; it *removes* their ability to look. Give the pointer and let each one pull the context it decides it needs.

### The inline-artifact fallback (≤150 lines) — narrow, and it caps the verdict

Inline an artifact only when the reviewer genuinely cannot fetch: no repo access, no PR, or the subject is not in version control (a plan, a pasted stack trace, an architecture sketch). Then keep it under ~150 lines.

**A verdict built on a truncated inline artifact may not be `APPROVED`.** Record `REVIEWED: <n> of <total> lines (<what was omitted>)`, carry it into the synthesis, and emit `WITHHELD` — see Quorum. This is not a formality: across the last 300 merged PRs in `jleechanorg/worldarchitect.ai`, **65% exceed 150 changed lines** (median 349), and for those, a 150-line cap shows a reviewer a median **22.5%** of the diff. A gate that says `APPROVED at <SHA>` after seeing a fifth of the change is asserting something it did not check.

## Step 2: Fan out the reviewers in parallel

Spawn every available reviewer in a single message. **A and B are the portable core** — they work on any machine. **C and D depend on personal infrastructure** and are skipped, not faked, when unavailable.

---

**Reviewer A — Fallback chain (try in order, stop at first success):**

**A1 — Opus subagent (primary):** Spawn an Agent:
```
You are a senior engineer giving a focused second opinion.

DECISION:
[decision, 3–5 sentences]

WHAT TO REVIEW:
[PR number / base...head ref / file-path list, plus diff --stat]

Read the change yourself — do not rely on any summary in this prompt.
Read as much of it as your judgment requires. If you could not read
what you needed, say so in COVERAGE rather than guessing.

Return exactly:
VERDICT: [recommended approach, one line]
REASONING: [3–4 sentences]
RISK: [main risk, one sentence]
COVERAGE: [what you actually read; note anything you could not reach]
CONFIDENCE: [high / medium / low]
```

**A2 — cursor (fallback if A1 errors):**
```bash
cursor agent -p --force "Senior engineer second opinion.\n\nDECISION:\n[decision]\n\nWHAT TO REVIEW:\n[PR / ref / paths]\n\nRead the change yourself. Return VERDICT, REASONING (3-4 sentences), RISK, COVERAGE, CONFIDENCE."
```

**A3 — agy (fallback if A2 errors):**
```bash
agy --print --dangerously-skip-permissions "Senior engineer second opinion.\n\nDECISION:\n[decision]\n\nWHAT TO REVIEW:\n[PR / ref / paths]\n\nRead the change yourself. Return VERDICT, REASONING (3-4 sentences), RISK, COVERAGE, CONFIDENCE."
```
Note: agy is the Antigravity CLI (reads CLAUDE.md on startup like any CC session, but starts fresh — no current conversation history). Independent perspective, slightly slower than cursor.

**A1.1 — `claude -p` (first-class choice when invoked outside Claude Code; fallback if A3 errors):**
```bash
claude -p --dangerously-skip-permissions "Senior engineer second opinion.\n\nDECISION:\n[decision]\n\nWHAT TO REVIEW:\n[PR / ref / paths]\n\nRead the change yourself. Return VERDICT, REASONING (3-4 sentences), RISK, COVERAGE, CONFIDENCE."
```
Note: Same Claude Code context inheritance as agy. For a cleaner isolated call: add `--cwd /tmp`.

If all options fail, note "Reviewer A unavailable" in the synthesis table.

---

**Reviewer B — Research:**

Invoke `/research [decision topic distilled to 6 words]`

---

**Reviewer C — Secondo (optional — needs infrastructure):**

Invoke `/secondo` with the decision, and let it gather its own context — it already captures `git diff origin/main...HEAD` under its own budget (`SECOND_OPINION_MAX_DIFF_CHARS`, default 32,000 chars). Do **not** hand it a ≤150-line extract instead; that throttles it to a fraction of the context it would have collected on its own.

Requires the AI-Universe MCP endpoint (`AI_UNIVERSE_MCP_ENDPOINT`) and its OAuth flow. `/secondo` bans substituting WebSearch or direct provider MCPs, so there is no portable fallback — if the endpoint is unreachable, mark **C unavailable** and continue.

---

**Reviewer D — Web Advice (optional — needs infrastructure):**

Invoke `/web-advice` (multi-model Web Chat review via `aside-mcp` across Gemini Web, ChatGPT, Grok, inspecting PR, evidence bundle, and video proof).

Requires live authenticated browser sessions. `/web-advice` carries its own HARD-FAIL contract: with no live transport it STOPs rather than substituting. **That STOP is scoped to Reviewer D, not to `/advice`** — mark **D unavailable** and continue with the remaining reviewers. Never satisfy D with an API, CLI, or subagent: an unavailable D is correct, a faked D is a method-fidelity violation.

---

## Step 3: Synthesize

Present:

```
| Reviewer    | Verdict              | Key concern         | Confidence |
|-------------|----------------------|---------------------|------------|
| A (source)  | ...                  | ...                 | high/med/low |
| Research    | [consensus finding]  | [main caveat]       | —          |
| Secondo     | ...                  | ...                 | —          |
| Web Advice  | ...                  | ...                 | —          |
```

- Give every reviewer a row, including the ones that failed — write `unavailable (<reason>)` in the Verdict column. Never drop a row; a missing row hides a missing opinion.
- 2+ available reviewers may inform a recommendation. Only the full-coverage
  reviewer quorum below may emit `APPROVED`.
- Available reviewers diverge → surface the disagreement, ask user which axis matters most (speed / safety / cost).

## Quorum — what you are allowed to conclude (mandatory)

**The orchestrating agent and research-only output are not approval reviewers.**
They write or inform the table; they do not vote. Only A, C, and D count toward
approval quorum, and each must declare `COVERAGE` after reading the change.

| Independent full-coverage reviewers that returned a verdict | What you may emit |
|---|---|
| 2 or more | `APPROVED` or `NOT APPROVED`, per the synthesis |
| exactly 1 | `NOT APPROVED` allowed; `APPROVED` is **not** — emit `WITHHELD` |
| 0 | `WITHHELD` |

Below quorum a lone reviewer may still block — one competent objection is enough to stop — but may never approve. Never resolve unreachable reviewers into `APPROVED`: an unreachable reviewer is missing evidence, not assent.

**Coverage gates approval too.** A reviewer whose `COVERAGE` does not cover the
declared diff/scope counts toward *blocking* but not toward *approving* — it is
an opinion, not a review. `APPROVED` requires two independent coverage declarations
whose combined scope covers the whole declared change. Otherwise emit `WITHHELD`.

## Final verdict format — SHA-bound (mandatory)

When `/advice` is being run as the gate in the `draft-first-pr` lifecycle (`~/.claude/skills/draft-first-pr/SKILL.md`), the synthesis MUST end with exactly one verdict line, bound to what was reviewed:

```
VERDICT: APPROVED at <SHA>
```
```
VERDICT: NOT APPROVED at <SHA>
```
```
VERDICT: WITHHELD at <SHA> — <quorum or availability reason>
```

`WITHHELD` means the review did not happen, not that it failed. It fails the gate exactly like `NOT APPROVED`, so consumers that look for `APPROVED` need no change — the distinction only tells a later reader whether to re-run reviewers or fix the code.

**Capturing `<SHA>`:**
- Reviewing a PR — `gh pr view <N> --json headRefOid --jq '.headRefOid'`
- Reviewing the working tree — `git rev-parse HEAD`, **but HEAD does not identify uncommitted changes.** If `git status --porcelain` is non-empty, that SHA does not name the tree you reviewed. Either commit first, or mark it: `VERDICT: APPROVED at <SHA>+dirty (mvp_site/foo.py, tests/bar.py)`.

This verdict is valid only for that exact state — per the SHA-binding rule in `draft-first-pr/SKILL.md`, a new commit invalidates it and `/advice` must be re-run at the new SHA before the PR can be marked ready. Do not emit a bare "APPROVED"/"looks good" without the SHA — an unbound verdict cannot be checked for staleness later.

## Token budget

What `/advice` saves is **the conversation**, not the change. `advisor()` ships the entire uncached transcript; `/advice` sends a decision plus a pointer, and each reviewer pulls only the code it decides it needs. That is the whole economy — and it is preserved without capping the diff.

| Reviewer | What you send |
|---|---|
| A — subagent / CLI | Decision + pointer (reviewer fetches the rest) |
| B — /research | Web queries only |
| C — /secondo | Decision; it gathers its own diff under its own budget |
| D — /web-advice | Decision + PR reference, per its own budget |

Do not cite a percentage saving — none has ever been measured here. And do not shrink the pointer to buy tokens: sending a 349-line diff is nothing like sending an 80K-token transcript, so trading review coverage for that margin is a bad trade in the only direction that matters.

## Fallback chain summary

| Priority | CLI | When |
|---|---|---|
| A1 | Claude subagent (Opus) | Primary (inside Claude Code) |
| A1.1 | `claude -p --dangerously-skip-permissions` | First-class choice when invoked outside Claude Code; fallback if A3/agy errors |
| A2 | `cursor agent -p --force` | Opus unavailable |
| A3 | `agy --print --dangerously-skip-permissions` | cursor errors |

Notes:
- Check a CLI is on `PATH` before counting it as a rung. An absent CLI is an unavailable rung, not a failed reviewer — drop to the next rung without recording a failure.
- `agy --print-timeout` defaults to 5m. Pass a longer value for a full 150-line artifact, or the review dies as an opaque timeout that looks like an error.
- codex was dropped from the chain 2026-06-24 (gpt-4.5 unsupported on the ChatGPT account, quota exhausted). **That reason is now obsolete** — `codex` is installed and `codexs` (gpt-5.3-codex-spark) is the delegation target named in `~/.claude/CLAUDE.md`. Re-adding it as a rung is a live option; the 2026-06-24 removal is not still-binding evidence against it.
