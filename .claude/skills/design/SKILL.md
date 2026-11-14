---
name: design
description: Generate HTML + MD design docs for a feature or PR, matching the repo's existing design doc style. Always produces both formats in parallel.
---

Generate a design reference doc for the current feature or PR.

**Always produce both HTML and MD in parallel** — this is the core contract of this skill.

## Steps

1. **Understand the feature** — read relevant source files, PR description, roadmap/plan docs.

2. **Check existing style** — discover the target repository’s design-doc location and template. Match its style when present; use a simple readable layout otherwise.

3. **Determine slug** — use the feature/PR name as a kebab-case slug (e.g. `session-recovery`, `search-filters`).

4. **Write both files in parallel** (single message, two Write tool calls):
   - `<design-dir>/<slug>.html`
   - `<design-dir>/<slug>.md`

   Use the repository’s documented design directory; `docs/design/` is a
   possible default when the repository does not specify one.

5. **HTML structure** (follow the target repository's selected template if present):
   - Reuse the template's color and layout tokens. Otherwise choose a readable, accessible palette.
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

7. If the task authorizes publication, commit both on the intended branch and follow the repository’s publication workflow.

## Invocation

```
/design
```

With slug override:
```
/design my-feature-name
```
