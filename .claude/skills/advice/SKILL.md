---
name: advice
description: "Token-efficient second opinion slash command /advice. Extracts the decision point plus a pointer to the change (PR / ref / paths) so each reviewer reads the code itself, then fans out in parallel to up to five reviewers: (1) Codex + Opus CLI reviewers launched concurrently as the primary pair, (2) fallback chain claude -p→cursor→agy if neither primary reviewer returns a verdict, (3) /research on the decision topic, (4) /secondo multi-model opinion, (5) /web-advice browser review. Reviewers A and B are the portable core; C and D need personal infrastructure and are skipped when unavailable. Use instead of advisor() which ships the full conversation uncached."
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

**Send the pointer, not a transcription.** Every reviewer transport in Step 2 is an *agent* that can read the repo for itself — Codex and Opus run in independent exact-SHA clones, `cursor -p` has access to write and shell tools, `agy`/`claude -p` run with permissions pre-approved, `/secondo` gathers its own `git diff origin/main...HEAD`, and `/web-advice` inspects the PR directly. Handing them a pre-chewed excerpt does not save them a fetch; it *removes* their ability to look. Give the pointer and let each one pull the context it decides it needs.

### The inline-artifact fallback (≤150 lines) — narrow, and it caps the verdict

Inline an artifact only when the reviewer genuinely cannot fetch: no repo access, no PR, or the subject is not in version control (a plan, a pasted stack trace, an architecture sketch). Then keep it under ~150 lines.

**A verdict built on a truncated inline artifact may not be `APPROVED`.** Record `REVIEWED: <n> of <total> lines (<what was omitted>)`, carry it into the synthesis, and emit `WITHHELD` — see Quorum. This is not a formality: across the last 300 merged PRs in `jleechanorg/worldarchitect.ai`, **65% exceed 150 changed lines** (median 349), and for those, a 150-line cap shows a reviewer a median **22.5%** of the diff. A gate that says `APPROVED at <SHA>` after seeing a fifth of the change is asserting something it did not check.

## Step 2: Fan out the reviewers in parallel

Spawn every available reviewer in a single message. **A and B are the portable core** — they work on any machine. **C and D depend on personal infrastructure** and are skipped, not faked, when unavailable.

---

**Reviewer A — Primary pair fired IN PARALLEL:**

**Codex + Opus run concurrently when both are available.** Each reviewer reads
the change independently and returns its own verdict. Use the executable runner
below: descriptive prose or a foreground Codex call followed by an Opus spawn
does not satisfy this contract.

Use the same review packet for both reviewers:

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

Write that packet to a temporary file, capture the exact review SHA, and invoke:

```bash
REVIEW_SHA="$(git rev-parse HEAD)"
ADVICE_TMP="$(mktemp -d)"
ADVICE_RUNNER="${CLAUDE_HOME:-$HOME/.claude}/skills/advice/scripts/run_primary_pair.py"
python3 "$ADVICE_RUNNER" \
  --repo "$(git rev-parse --show-toplevel)" \
  --ref "$REVIEW_SHA" \
  --packet-file "$ADVICE_TMP/review-packet.txt" \
  --output-dir "$ADVICE_TMP/results" \
  --timeout-seconds 1200
```

Create `$ADVICE_TMP/review-packet.txt` before invoking the runner. The output
directory is deliberately outside the repository. Read `codex.txt`, `opus.txt`,
and `receipt.json`; the receipt records the resolved SHA, each transport, launch
times, each clone SHA, cleanup status, and any changed original-repository
fingerprint components. The
input checkout must be clean, including untracked files. The runner refuses a
dirty checkout because those changes are not represented by the requested SHA.

The runner creates two independent disposable clones with `git clone --no-local`,
removes their `origin` remotes, and detaches both at the exact same SHA. It then
starts A1 and A2 behind one concurrency barrier, gives them disjoint output
files, and removes the clones afterward. It preserves the requested
full-permission transports explicitly: `codex exec --yolo` for A1 and
`claude -p --model opus --dangerously-skip-permissions` for A2. Independent
clones prevent reviewer writes to refs, config, or hooks from sharing the
original repository's `.git` state; they are deliberately **not** an OS security
sandbox. If the original checkout, refs, local config, or hooks change, the
runner fails closed and its verdicts may not be used.

Each primary reviewer has a bounded runtime. `--timeout-seconds` sets the
per-lane limit and defaults to 1200 seconds (20 minutes). A timeout records that
lane as `error` with `failure: timeout`; the peer may still supply the sole
primary verdict. If both time out, the runner exits 4 and A3 applies. Clone
cleanup and receipt writing still run after timeouts. Cleanup itself is a gate:
failure is recorded in `receipt.json` and the runner exits 5 rather than hiding
leftover full-permission checkouts. Setup, reviewer, and result-output exceptions
are captured under `operation` instead of escaping as traceback-only failures;
after successful cleanup they exit 6. If operation and cleanup both fail,
`receipt.json` records both and cleanup exit 5 takes precedence.

Ignored regular files may contain credentials, so the fingerprint never opens
or hashes their contents. It records each ignored relative path plus `lstat`
mode, size, and nanosecond modification time; for a symlink it additionally
records the link target without following it. This detects ordinary ignored-file
creation, deletion, replacement, and modification while keeping secret content
unread. It is a mutation tripwire, not a defense against an adversarial process
that deliberately restores identical metadata, and it does not change the
runner's non-sandbox boundary.

Hook coverage follows Git's effective `core.hooksPath`, including configured
absolute or relative hook locations. The fingerprint includes ordinary hook
content and `lstat` metadata; symlinks, including dangling ones, contribute
their link target without being followed. This avoids unsafe traversal while
detecting hook-path and dangling-link mutations.

An exit code of zero is not enough: each successful lane must return a nonempty
line beginning with `VERDICT:`. Empty or malformed output records
`missing_verdict` and counts as an errored lane. If neither primary lane returns
a recognizable verdict, invoke A3.

**A1 — Codex CLI (primary):** `codex exec --yolo -m gpt-5.6-terra --config
model_reasoning_effort=high`. The explicit command guarantees full-permission
mode without relying on wrapper internals.

**A2 — Opus CLI (primary):** `claude -p --model opus
--dangerously-skip-permissions`. It is dispatched concurrently with A1, not
after A1 returns.

**A3 — Fallback chain (whenever neither primary leg produces a verdict):**

A3 activates whenever Reviewer A cannot return a verdict. That covers:
- BOTH A1 (Codex) and A2 (Opus) are unavailable (binary / model missing)
- BOTH A1 and A2 dispatched and both errored
- A1 unavailable AND A2 errored (mixed failure — still no primary verdict)
- A1 errored AND A2 unavailable (mixed failure — still no primary verdict)

In all of the above, fall through this chain in order, stopping at the first success:

**A3.1 — `claude -p` (first-class fallback when invoked outside Claude Code):**
```bash
claude -p --dangerously-skip-permissions "$(cat <<'EOF'
Senior engineer second opinion.

DECISION:
[decision]

WHAT TO REVIEW:
[PR / ref / paths]

Read the change yourself. Return VERDICT, REASONING (3-4 sentences), RISK, COVERAGE, CONFIDENCE.
EOF
)"
```
Note: Same Claude Code context inheritance as agy. For a cleaner isolated call: add `--cwd /tmp`.

**A3.2 — `cursor agent -p` (fallback if claude -p errors):**
```bash
cursor agent -p --force "$(cat <<'EOF'
Senior engineer second opinion.

DECISION:
[decision]

WHAT TO REVIEW:
[PR / ref / paths]

Read the change yourself. Return VERDICT, REASONING (3-4 sentences), RISK, COVERAGE, CONFIDENCE.
EOF
)"
```

**A3.3 — `agy` (fallback if cursor errors):**
```bash
agy --print --dangerously-skip-permissions "$(cat <<'EOF'
Senior engineer second opinion.

DECISION:
[decision]

WHAT TO REVIEW:
[PR / ref / paths]

Read the change yourself. Return VERDICT, REASONING (3-4 sentences), RISK, COVERAGE, CONFIDENCE.
EOF
)"
```
Note: agy is the Antigravity CLI (reads CLAUDE.md on startup like any CC session, but starts fresh — no current conversation history). Independent perspective, slightly slower than cursor.

If all options fail, note "Reviewer A unavailable" in the synthesis table.

**No-verdict guarantee:** A host that lacks BOTH Codex (no codex binary) AND the
Opus CLI MUST still emit at least one
A-leg verdict if any of A3.1 / A3.2 / A3.3 is on PATH. The fallback chain is
gated on "unavailable OR error" — not error alone — so a fully bare host with
just `claude -p` installed still produces a verdict. If every leg (A1 + A2 +
A3.1 + A3.2 + A3.3) is unavailable, mark **A unavailable (no agent binary on
host)** and continue with B / C / D.

**A — solo-mode rule:** If only ONE of {Codex, Opus} is available (the other
binary / model is missing or errors immediately at dispatch), run whichever
survives as the sole A reviewer — do NOT synthesize a "pair" from a single
verdict. Mark the missing partner `unavailable (<reason>)` in the synthesis
table so the reader sees we did not silently drop a leg.

---

**Reviewer B — Research:**

Invoke `/research [decision topic distilled to 6 words]`

---

**Reviewer C — Secondo (optional — needs infrastructure):**

Invoke `/secondo` with the decision and declared review scope, and let it gather
its own context — it already captures `git diff origin/main...HEAD` under its own
budget (`SECOND_OPINION_MAX_DIFF_CHARS`, default 32,000 chars). Require
`COVERAGE: <files/diff scope actually read>` in its response. Do **not** hand it
a ≤150-line extract instead; that throttles it to a fraction of the context it
would have collected on its own.

Requires the AI-Universe MCP endpoint (`AI_UNIVERSE_MCP_ENDPOINT`) and its OAuth flow. `/secondo` bans substituting WebSearch or direct provider MCPs, so there is no portable fallback — if the endpoint is unreachable, mark **C unavailable** and continue.

---

**Reviewer D — Web Advice (optional — needs infrastructure):**

Invoke `/web-advice` with the decision and declared review scope. Require its
synthesis to report `COVERAGE: <files/diff scope actually read>` before it can
vote in this approval quorum.

Requires live authenticated browser sessions. `/web-advice` carries its own HARD-FAIL contract: with no live transport it STOPs rather than substituting. **That STOP is scoped to Reviewer D, not to `/advice`** — mark **D unavailable** and continue with the remaining reviewers. Never satisfy D with an API, CLI, or subagent: an unavailable D is correct, a faked D is a method-fidelity violation.

---

## Step 3: Synthesize

Present:

```
| Reviewer    | Verdict              | Key concern         | Confidence |
|-------------|----------------------|---------------------|------------|
| A1 Codex    | ...                  | ...                 | high/med/low |
| A2 Opus     | ...                  | ...                 | high/med/low |
| B Research  | [consensus finding]  | [main caveat]       | —          |
| C Secondo   | ...                  | ...                 | —          |
| D Web Advice| ...                  | ...                 | —          |
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
- Reviewing the working tree — `git rev-parse HEAD`, **but HEAD does not identify uncommitted changes.** If `git status --porcelain` is non-empty, that SHA does not name the tree you reviewed. Commit the intended state before review; the primary-pair runner refuses dirty input and no approval verdict may be emitted for it.

This verdict is valid only for that exact state — per the SHA-binding rule in `draft-first-pr/SKILL.md`, a new commit invalidates it and `/advice` must be re-run at the new SHA before the PR can be marked ready. Do not emit a bare "APPROVED"/"looks good" without the SHA — an unbound verdict cannot be checked for staleness later.

## Token budget

What `/advice` saves is **the conversation**, not the change. `advisor()` ships the entire uncached transcript; `/advice` sends a decision plus a pointer, and each reviewer pulls only the code it decides it needs. That is the whole economy — and it is preserved without capping the diff.

| Reviewer | What you send |
|---|---|
| A1 Codex | Decision + pointer (reviewer fetches the rest) |
| A2 Opus CLI | Decision + pointer (reviewer fetches the rest) |
| B — /research | Web queries only |
| C — /secondo | Decision; it gathers its own diff under its own budget |
| D — /web-advice | Decision + PR reference, per its own budget |

Do not cite a percentage saving — none has ever been measured here. And do not shrink the pointer to buy tokens: sending a 349-line diff is nothing like sending an 80K-token transcript, so trading review coverage for that margin is a bad trade in the only direction that matters.

## Fallback chain summary

| Priority | CLI | When |
|---|---|---|
| A1 | `codex exec --yolo -m gpt-5.6-terra --config model_reasoning_effort=high` | Primary — runs IN PARALLEL with A2 |
| A2 | `claude -p --model opus --dangerously-skip-permissions` | Primary — runs IN PARALLEL with A1 |
| A3.1 | `claude -p --dangerously-skip-permissions` | Fallback when no primary leg produced a verdict (outside Claude Code) |
| A3.2 | `cursor agent -p --force` | Fallback if A3.1 errors |
| A3.3 | `agy --print --dangerously-skip-permissions` | Fallback if A3.2 errors |

Notes:
- Codex + Opus are the primary PAIR, not a fallback chain. Both are fired in the same turn whenever both are available. A reviewer quorum table needs BOTH rows; mark missing partner `unavailable (<reason>)` per the solo-mode rule.
- The A3.x fallback chain activates whenever no primary leg produces a verdict — Codex alone being unavailable or alone failing does NOT drop to A3 (the surviving leg still counts as the A verdict). The gate is "neither primary succeeded," not "both errored," so hosts with mixed failure modes (one unavailable, one errored) still get a verdict. This keeps `/advice` productive on hosts where only one of {codex, opus} is installed OR only one dispatched cleanly.
- Check a CLI is on `PATH` before counting it as a rung. An absent CLI is an unavailable rung, not a failed reviewer — drop to the next rung without recording a failure.
- `agy --print-timeout` defaults to 5m. Pass a longer value for a full 150-line artifact, or the review dies as an opaque timeout that looks like an error.
- A primary process counts as successful only when it exits zero and emits a nonempty `VERDICT:` line. Otherwise preserve its failure in `receipt.json` and apply the solo/fallback rules above.
