# Recurring-correction → pre-send gate principle

**Added 2026-07-14, harness-postmortem Phase 1.5d.**

The "evolved" form of the 5-Whys protocol. Codified from the PR #8139
recurring failure (2026-07-02 → 2026-07-14, 4 incidents in 12 days).

## The principle

> **When the same user correction has hit ≥3 times across ≤30 days, the fix
> MUST move from "post-hoc documentation" to "pre-send invariant."
> Documentation-only fixes do not survive between sessions — the agent's
> defaults push toward the path of least resistance. A pre-send gate
> (regex matching the draft body, fired before the message tool is invoked)
> is the only durable countermeasure.**

## How this differs from the existing rules

The existing SOUL.md / skill / test layers are *documentation* — they
encode the rule but rely on the agent to remember to load them. The
agent's defaults (especially under prompt-level pressure to "just post
the message") push toward shortcuts:

- "The user asked for screenshots, I'll just put `MEDIA:/path` in the reply"
- "The bot token failed once, I'll try xoxp without checking scope first"
- "I'll describe the screenshot instead of attaching it"

These are the path-of-least-resistance defaults. Documentation doesn't
beat them. **A pre-send gate that intercepts the draft body BEFORE the
message tool is called does.**

## Concrete checklist for Phase 1.5d

When you (the `/meta` agent) encounter a failure class that has recurred
≥3 times:

1. **Verify the recurrence** — search the SQLite state.db for similar
   user corrections in the last 30 days. Quote the trigger phrases the
   user actually typed. Don't accept "I remember this happening twice"
   without evidence.
2. **Audit the existing fix** — if a skill/SOUL.md/test exists for this
   class, why didn't it prevent the recurrence? Most common answers:
   - Documentation-only: the skill exists but the agent never loads it
     because no pre-send invariant forces it.
   - Reactive trigger: the rule fires after the user complains, not
     before the bad output is sent.
   - Stale reference: the skill was written before a known failure mode
     (e.g., OAuth scope gap) was discovered.
3. **Write the pre-send gate** — a regex (or ordered sequence check)
   that the agent MUST run on every draft before invoking the message
   tool. Encode it as a SOUL.md `## COMMIT:` block with trigger +
   action + verification (test file).
4. **Test the gate** — write a contract test (e.g.,
   `tests/test_<name>_presend_contract.py`) that:
   - regex compiles
   - matches realistic bad drafts
   - does NOT match clean drafts (no false positives)
   - enforces the draft → upload → verify → send ordering
5. **Patch the skill** — add a "Pre-Send Gate" section at the TOP of
   the relevant skill. Add the new trigger phrases (especially the
   recurring-correction ones like "you always forget") to the YAML
   frontmatter.
6. **Save memory** — write a durable memory entry that names the
   recurrence pattern and links to the pre-send gate. This is the
   "anti-pattern signature" future agents will hit when they search.

## Worked example — evidence-attach-to-slack (2026-07-14)

### Recurrence verification

| Date | PR | User trigger phrase |
|---|---|---|
| 2026-07-02 | #8139 | "you are showing me a file path you need to upload the actual media" |
| 2026-07-10 | #7953 | "I need the media evidence on this thread" |
| 2026-07-13 | #8337 | "Why are you failing the upload again?" |
| 2026-07-14 | #8139 | "You always fail to attach images to a slack thread ... why do you always forget?" |

4 incidents in 12 days. User's phrasing escalated from specific
("where's the screenshot?") to generic/pattern ("you always fail",
"you always forget") — strong signal they're pointing at the
recurring class, not a specific missing image.

### Existing audit

- Earlier versions documented a native upload recipe and a public-Gist
  fallback. The Gist fallback is retired; consult the current skill for the
  supported workflow.
- SOUL.md `## COMMIT: evidence-attach-not-path-cite` existed across
  all 4 incidents. The rule fires after the user complains.
- Neither layer intercepted the failure before the message was sent.

### Pre-send gate

SOUL.md `## COMMIT: evidence-attach-presend-gate` (added 2026-07-14):

```
Trigger: BEFORE invoking mcp__slack__conversations_add_message or
chat.postMessage with a message body that contains ANY of: (a) a
MEDIA:/absolute/path token referencing .png|.jpg|.jpeg|.gif|.webp|.mp4|.pdf,
OR (b) an absolute filesystem path matching
^/Users/[^ ]+\.(png|jpg|jpeg|gif|webp|mp4|pdf)$, OR (c) the phrases
"BEFORE", "AFTER", "screenshot", "see attached", "here's what it looks like"
AND a local path in the same draft.

Action: Mandatory ordered pre-send sequence:
1. Load the current `evidence-attach-to-slack` skill.
2. Strip `MEDIA:` path tokens from the draft.
3. Use its configured, authorized native Slack attachment workflow. Do not
   invoke `scripts/check_token_scopes.py`, inspect or alter credentials,
   reinstall scopes, or use a public-Gist fallback. If Slack returns
   `missing_scope`, report the exact API error and stop.
4. Verify the native attachments landed before claiming success.
5. Post the summary only after successful verification.
```

### Test

`tests/test_evidence_attach_presend_contract.py` — 8 tests covering
regex compilation, false-positive guard, ordering, fallback chain, and
summary-is-last invariant. All green as of 2026-07-14.

### Memory entry

> **Evidence-attach failure is recurring (2026-07-14).** Agent has failed
> to attach PNGs/GIFs to Slack threads ≥4 times in 12 days. Root cause:
> existing rule was reactive. Fix: pre-send gate fires BEFORE message
> tool is called (regex matches MEDIA:/path and /Users/.../*.png).
> Pattern: when a recurring user correction hits ≥3 times, the fix MUST
> be a pre-send gate, not post-hoc remediation.

## Anti-patterns this principle blocks

| Anti-pattern | Why it fails the ≥3-times rule |
|---|---|
| "Add this to memory so the next agent knows" | Memory isn't loaded on the relevant path; the failure re-occurs |
| "Update the skill to be more emphatic" | The skill was already emphatic; the agent didn't load it |
| "Just be more careful next time" | No mechanism enforces "more careful"; default behavior returns |
| "Run the harness skill and fix the agent" | Fix at the wrong layer — harness fixes need to land in pre-send gates |
| "Document the failure mode in MEMORY.md" | Same as memory — not enforced at draft time |

## Related references

- `~/.hermes/skills/evidence-attach-to-slack/SKILL.md` — v1.6.0 (Pre-Send Gate section at top)
- `~/.hermes/skills/evidence-attach-to-slack/references/recurring-failure-pattern-2026-07.md` — historical summary only; former operational recipes are retired
- `~/.hermes/workspace/SOUL.md` — `## COMMIT: evidence-attach-presend-gate`
- `~/.hermes/skills/harness-postmortem/SKILL.md` — Phase 1.5d section (this file)
- `~/.hermes/skills/evidence-attach-to-slack/tests/test_evidence_attach_presend_contract.py` — 8 contract tests, all green