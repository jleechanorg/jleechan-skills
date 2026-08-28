---
description: Generate HTML + MD design docs for a feature or PR, matching the repo's existing design doc style. Always produces both formats in parallel.
---

Generate a design reference doc for the current feature or PR.

**Always produce both HTML and MD in parallel** — this is the core contract of this skill.

## Steps

1. **Understand the feature** — read relevant source files, PR description, roadmap/plan docs.

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

## Invocation

```
/design
```

With slug override:
```
/design my-feature-name
```
