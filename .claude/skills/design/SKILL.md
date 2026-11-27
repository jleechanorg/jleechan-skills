---
name: design
description: Generate HTML + MD design docs for a feature or PR, matching the repo's existing design doc style. Always produces both formats in parallel.
---

Generate a design reference doc for the current feature or PR.

**Always produce both HTML and MD in parallel** — this is the core contract of this skill.

## Steps

1. **Understand the feature** — read relevant source files, PR description, roadmap/plan docs, and build the request ledger below when using conversation history.

2. **Check existing style** — look in `docs/design/` for `.html` files. Match CSS variables, card/grid layout, section patterns exactly.

3. **Determine slug** — use the feature/PR name as a kebab-case slug (e.g. `autonomy-gaps`, `agent-gemini-plugin`).

4. **Write both files in parallel** (single message, two Write tool calls):
   - `docs/design/<slug>.html`
   - `docs/design/<slug>.md`

5. **HTML structure** (match `docs/design/agent-gemini-plugin.html` as canonical reference):
   - CSS root tokens: `--bg #f2efe7`, `--panel #fffdf8`, `--ink #1f1a16`, `--muted #6f6357`, `--brand #165a72`, `--line #dfd3c2`
   - Hero section: h1 title, muted subtitle, tag pills (PR ref, key files, line delta, status)
   - Overview grid: one card per sub-feature/gap with priority badge and description
   - Per-feature sections with `section-label` dividers: before/after code blocks, tables, flow diagrams
   - Summary section: what-changed table + `.callout` with honest capability claim
   - Responsive: `.grid.two`, `.grid.three`, `.grid.four` breakpoint at 900px

6. **MD structure**:
   - No frontmatter
   - H1 title with metadata block (PR, branch, date, beads, delta)
   - `---` dividers between major sections
   - Per-gap H2 with before/after code blocks and tables
   - Summary table at end

7. **Commit both** to the current branch and push.


## Request ledger

When a design draws on a conversation, build a request ledger before writing the design. Use the stated review window; if none was given, use the relevant feature thread and state its boundaries. Page through accessible history. Distinguish direct user messages (including corrections, research questions and one-word replies) from assistant/tool output and relayed claims. Resolve replies against the exact parent where available. Report inaccessible intervals, threads or attachments instead of claiming full coverage.

- One row per in-scope user message, in order: **source/date | request | disposition | design or evidence pointer | remaining work**. Keep separate rows for distinct messages that affect the same requirement. Use short paraphrases instead of copying transcripts.
- Use **adopted**, **adapted**, **superseded**, **deferred**, **rejected**, or **not design scope**. Give reasons for changes, deferrals and rejections. Link superseded rows to the newer direction. Acknowledging a request is not implementing it.
- Keep research asks even when no feature changes. Record the source checked, what was learned, what it influenced, and any open gap. Distinguish documentation research from hands-on proof.
- Check the ledger against both design formats and relevant acceptance tests. Resolve stale contradictions or make the remaining decision explicit. Verify row count against the accessible source window and note limitations.
- Keep any sensitive source ledger private. Publish only the minimum authorized, sanitized traceability summary, with no private conversations, contact details, credentials, internal links, or unrelated personal data. When uncertain, keep the detailed ledger separate and mention only its coverage.

Synthetic example: “Show a progress count” → adopted, Design § Progress; “Show percentages instead” → supersedes count, Design § Progress; “Check offline support” → researched, stale data is labeled; offline writes deferred, Design § Offline.

## Invocation

```
/design
```

With slug override:
```
/design my-feature-name
```
