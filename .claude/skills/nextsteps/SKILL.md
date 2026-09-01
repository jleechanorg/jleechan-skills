---
name: nextsteps
description: Situational assessment and roadmap sync after a work block. Default mode reads ONLY beads (`br`) and `~/roadmap` (lean: independent nextsteps markdown doc + beads update + roadmap activity + ~/roadmap learnings log). `--full` preserves the legacy all-source behavior (adds Claude auto-memory writes, mem0 sync, and GitHub Issue creation). Prefers editing existing roadmap docs over creating new files.
---

# /nextsteps — Situational Assessment & Roadmap Update

Situational assessment and roadmap sync after a work block.

## Modes (read first — determines which phases run)

`/nextsteps` has **two mutually exclusive modes**. Pick one based on the
invocation; do not silently blend them.

| Mode | Invocation | Sources read | Side effects written |
|------|------------|--------------|----------------------|
| **default** (lean) | `/nextsteps` or `/nextsteps [brief]` | beads (`br list`/`br show`) + `~/roadmap/` + `roadmap/activity/YYYY-MM-DD.md` | nextsteps `.md` doc + `br` updates + `roadmap/activity/YYYY-MM-DD.md` (and README date link if new date) + `~/roadmap/learnings-YYYY-MM.md` |
| **`--full`** (legacy all-source) | `/nextsteps --full` or `/nextsteps --full [brief]` | everything in default + Claude auto-memory (`~/.claude/projects/<key>/memory/`) + mem0 | everything in default + Claude auto-memory writes + `MEMORY.md` pointers + `mem0_shared_client.py add` + GitHub Issue creation |

**Default mode skips these phases on purpose** (they are owned by `--full`):

- **Phase 4 — Write to Claude auto-memory** (writes `~/.claude/projects/.../memory/*.md` and `MEMORY.md` pointers).
- **Phase 5 — Save to mem0** (calls `~/.hermes/scripts/mem0_shared_client.py`).
- **Phase 7b — Create or update GitHub Issues** (calls `gh issue create` for each new bead).

<!-- USER REQUEST (verbatim, preserved per task brief): "Make /nextsteps only do beads and ~/roadmap and /nextsteps --full does everything" -->

If a user wants the side-effecting phases in the default run, they must invoke
`/nextsteps --full`. Rationale: the lean default keeps `/nextsteps` focused on
bead + roadmap state, which is what the user is asking for; the memory/issue
mirroring is opt-in and lives behind `--full`.

### How to parse the flag

1. Look at the literal text right after `/nextsteps` or in `$ARGUMENTS`.
2. If the first non-whitespace token is exactly `--full`, run in `--full` mode and strip it from the brief.
3. Otherwise (no `--full` flag on the invocation), run in default mode and treat the rest as the user-provided brief.
4. `--full` is the only recognized flag. Any other token (`--help`, `-h`, etc.) is treated as part of the brief.

Report the chosen mode on the **first line of the Phase 8 report**, e.g.:

```
Mode: default (beads + ~/roadmap)
```

or

```
Mode: --full (beads + ~/roadmap + Claude memory + mem0 + GH Issues)
```

## Fail-closed rule

A `/nextsteps` run is **incomplete** unless it leaves **all** of these artifacts
**for its chosen mode**:

### Default mode (lean) — required artifacts

1. **Independent summary markdown doc** (see [Nextsteps document](#nextsteps-document-mandatory)) — TOC, executive summary, then full self-contained detail; bead links throughout
2. Beads updated/created via `br`
3. `~/roadmap/learnings-YYYY-MM.md` appended
4. **`roadmap/activity/YYYY-MM-DD.md`** appended with session bullet (repo git root — create file if absent). If that date is brand-new, prepend one date link to `roadmap/README.md`'s `## Recent activity (by day)` section.

If the session has no repo checkout, skip item 4 only and note that in the Phase 8 report.

### `--full` mode — required artifacts

In addition to all default-mode artifacts above, a `--full` run must also
leave:

5. Claude memory files written with `MEMORY.md` pointers
6. mem0 entry saved (or `⚠️ mem0 unavailable (skipped)` recorded)
7. GitHub Issue creation attempted / recorded

If the session has no repo checkout, skip item 4 only and note that in the Phase 8 report.

### Continuous completion contract

A normal `/nextsteps` invocation authorizes all relevant stages below. Complete all required stages in the same run before yielding a final response.

- In **default mode**, execute Stage 1 (Phases 1a/1b, 2, 3), skip Stage 2 side-effecting syncs (owned by `--full`), and produce the Phase 8 report immediately.
- In **`--full` mode**, execute Stage 1, then proceed continuously into Stage 2 (Claude auto-memory, mem0, GitHub Issues) before producing the Phase 8 report.
- Do not pause for approval, ask whether to proceed, or stop at stage boundaries.
- Parallelize independent work when slots are available. If parallel capacity is unavailable, continue locally or sequentially; lack of a subagent slot is never a reason to stop.
- Interim user updates are non-blocking status messages, not approval checkpoints.
- If mem0, GitHub Issues, or another optional sink is unavailable in `--full` mode, record the exact attempted result, complete every other artifact, and report the unavailable sink in the final checklist.
- Stop only for a genuine blocker that requires new authority or information and cannot be safely worked around. Routine external failures, disabled integrations, or partial tool availability are not stopping conditions.

## Doc discovery — prefer update over create

Before writing the independent summary or touching roadmap files:

1. **Search for existing nextsteps / session / sync docs** (in order):
   - Repo: `roadmap/nextsteps*.md`, `roadmap/NEXT-STEPS.md`, `roadmap/session-*.md`, `docs/nextsteps*.md` (if present)
   - Home: `~/roadmap/nextsteps-latest.md`, `~/roadmap/nextsteps-*.md`
2. **Prefer:** append a new **dated section** to an existing rolling file (e.g. `nextsteps-latest.md` or the newest `nextsteps-YYYY-MM-DD.md` in the same month), or add a subsection under an existing “Work queue” / “Next steps” heading.
3. **Create new file only when** no suitable file exists. Default **new** path: `~/roadmap/nextsteps-<YYYY-MM-DD>.md` (or `roadmap/nextsteps-<YYYY-MM-DD>.md` if the repo standard is to keep session docs in-repo — match sibling files if any).
4. **Activity log:** append the session bullet to **`roadmap/activity/YYYY-MM-DD.md`** (create file with `# Activity — YYYY-MM-DD` header if absent). If this is the first entry for that date, prepend a `- [YYYY-MM-DD](activity/YYYY-MM-DD.md)` line to the `## Recent activity (by day)` list in `roadmap/README.md`. Do not prepend to README for subsequent entries on the same date — only the per-day file changes. This keeps README conflict-free across concurrent PRs.

## Nextsteps document (mandatory)

The independent `.md` file is the **handoff artifact**: a reader must be able to execute the queue without opening beads or chat.

**Document order (fixed):**

1. **Title line** — e.g. `# Nextsteps — <topic or repo> — <YYYY-MM-DD>`
2. **Table of contents** — Markdown list linking to **every** following `##` section (Executive summary through Roadmap pointer). Use GitHub-style anchors (lowercase, hyphenated, dedupe if titles repeat). Update whenever headings change.
3. **Executive summary** — Short, skimmable block (bullets OK): what this block accomplished, what is blocked or at risk, top priorities / sequencing, beads and PRs that matter (**ids with links**). No deep procedural detail — that lives in the sections below.
4. **Full detail (all following `##` sections)** — Each section is **self-contained** (definitions, file paths, acceptance criteria, dependencies). Do not rely on “see chat” or unstated context. Order: Context → Bead index → Work queue → PR / merge state → Learnings pointer → Roadmap pointer.

**Required `##` sections after Executive summary (skip only if genuinely N/A — one line stating why):**

| Section | Content |
|--------|---------|
| **Context** | 2–6 sentences: what block just ended, repo(s), branch/PR if relevant, scope boundaries |
| **Bead index** | Table: `bd-…` id, title, priority/status if known, **link** — every open bead touched or created this run. Prefer `https://github.com/<owner>/<repo>/issues/<n>` when the bead syncs to GitHub Issues; else `br show <id>` as fallback. Link the id in every row. |
| **Work queue** | Numbered tasks; each task **self-contained**: goal, acceptance criteria, files/areas, dependencies/blockers, suggested order; **reference beads** inline as linked `[bd-xxx](url)` where applicable |
| **PR / merge state** | Same session truth as Phase 1b (`PR #n: OPEN \| MERGED \| CLOSED`) for any PR referenced; full PR URLs |
| **Learnings pointer** | Path/link to the new `~/roadmap/learnings-YYYY-MM.md` entry for this date; one-line summary of what was logged |
| **Roadmap pointer** | Confirm `roadmap/activity/YYYY-MM-DD.md` appended (and README date link added if new date) |

**Link rules**

- **Beads:** linked in **Bead index**, and again **inline** in Work queue items where a task maps to a bead.
- **PRs/issues:** full `https://github.com/owner/repo/pull/n` (or `/issues/n`) when known.
- **Internal:** link from TOC entries to each `##` section anchor.

**Example skeleton**

```markdown
# Nextsteps — <repo> — 2026-04-19

## Table of contents

- [Executive summary](#executive-summary)
- [Context](#context)
- [Bead index](#bead-index)
- [Work queue](#work-queue)
- [PR / merge state](#pr--merge-state)
- [Learnings pointer](#learnings-pointer)
- [Roadmap pointer](#roadmap-pointer)

## Executive summary

- Outcomes: …
- Risks / blockers: …
- Next: …
- Beads: [bd-abc123](https://github.com/org/repo/issues/NN) (short label)

## Context

…

## Bead index

| Bead | Title | Link |
|------|-------|------|
| bd-… | … | [bd-…](https://github.com/org/repo/issues/NN) |

## Work queue

1. … — tracks [bd-…](https://github.com/org/repo/issues/NN)

## PR / merge state

- https://github.com/org/repo/pull/123 — OPEN

## Learnings pointer

- `~/roadmap/learnings-2026-04.md` — section `2026-04-19 — …`

## Roadmap pointer

- Appended `roadmap/activity/YYYY-MM-DD.md` — Recent activity (per-day file)
```

## When invoked — Execution Workflow

### Stage 1: Local Updates (Default & `--full` Modes)

#### Phase 1a — Memory Search Context (parallel subagent)
**Run as a parallel subagent** (Agent tool, subagent_type=Explore) so Phase 1b can start simultaneously:
1. Search memory files for key terms from the user-provided context after `/nextsteps`
2. Check `~/roadmap/nextsteps-*.md` for most recent session doc (target for append vs new file)
3. Check `~/roadmap/learnings-YYYY-MM.md` tail for existing entries
4. Report: existing bead IDs, open items from prior sessions, path of most recent nextsteps doc

#### Phase 1b — Gather context (parallel subagent)
**Run as a parallel subagent** (Agent tool, subagent_type=Explore) concurrently with Phase 1a:
- `git log --oneline -10`
- `br list --status open --limit 0`
- `ls roadmap/` (and `ls ~/roadmap/` for home docs)
- Run [Doc discovery](#doc-discovery--prefer-update-over-create) — note target file for the summary doc (existing vs new path)
- Use any user-provided line after `/nextsteps` as extra context.
- **PR truth (same session):** From open beads, roadmap merge stacks, and user notes, collect every distinct GitHub PR number you will reference. For each `n`, resolve the repo (default: `gh repo view --json nameWithOwner -q .nameWithOwner` from the git root; if the work spans another repo, pass that owner/name explicitly) and run:
  ```bash
  gh pr view <n> --repo <owner/repo> --json state,mergedAt,closedAt,headRefName
  ```
  Map JSON to a human line for the report and the **Nextsteps document**: **`PR #n: OPEN`** if `state` is `OPEN`; **`PR #n: MERGED`** if `mergedAt` is non-null; else **`PR #n: CLOSED`** (closed without merge). Do not recommend “land PR *n*” without this check in the **same** `/nextsteps` run.

#### Phase 2 — Assess & Update Local Assets
- Match recent commits to open beads; close or update status.
- Note gaps → determine new beads to create.
- Create or update beads using `br`:
  ```bash
  br create "<title>" --type task --priority 2
  ```
- Append session bullet to **`roadmap/activity/YYYY-MM-DD.md`** (create with header if new date). Only touch `roadmap/README.md` when the date file is brand-new (prepend one date link to `## Recent activity (by day)`).
- Identify learnings from the session worth persisting, and append them to `~/roadmap/learnings-<YYYY-MM>.md` (create if absent) using this format:
  ```markdown
  ## <YYYY-MM-DD> — <title>
  - **Type**: feedback|project|reference
  - **Classification**: 🚨|⚠️|✅|❌
  - **Summary**: <one-liner>
  - **Bead**: <bd-id or none>
  - **Files**: <paths changed if any>
  - **Nextsteps doc**: <path to independent summary md>
  ```

#### Phase 3 — Write/Update Nextsteps Document & Show to User
- Apply [Doc discovery](#doc-discovery--prefer-update-over-create).
- Write or append to the Nextsteps document: **table of contents**, **executive summary**, then **full detail** sections per [Nextsteps document (mandatory)](#nextsteps-document-mandatory).
- Record the clean table of created/updated beads, learnings, roadmap activity changes, and the Nextsteps document path.
- In **default mode**, skip Stage 2 and proceed directly to Phase 8 report.
- In **`--full` mode**, continue directly to Stage 2. Do not yield a final response or request confirmation here.

---

### Stage 2: Memory & Tool Sync (`--full` only, Parallel When Available)

**Skipped by default mode.** Run only when the invocation includes `--full`.

Run the remaining tasks immediately in the same invocation. Use parallel subagents when available; otherwise perform the tasks locally or sequentially and finish the stage.

#### Phase 4 — Write to Claude auto-memory (`--full` only)
Create a subagent (`TypeName=self` or a custom subagent) to execute the memory write for each learning/finding:
1. Determine type: `feedback` (rules, anti-patterns) | `project` (decisions, state) | `reference` (pointers)
2. Slug: lowercase, underscored, max 40 chars
3. Derive memory dir from git root:
   ```bash
   git_root=$(git rev-parse --show-toplevel)
   project_key="${git_root//\//-}"
   memory_dir="$HOME/.claude/projects/${project_key}/memory"
   ```
4. Write file `${memory_type}_${date}_${slug}.md` with frontmatter:
   ```markdown
   ---
   name: <title>
   description: <one-liner>
   type: feedback|project|reference
   bead: <bd-id or none>
   ---

   <body>

   **Why:** <reason>

   **How to apply:** <when/where this kicks in>
   ```
5. Append pointer to `MEMORY.md` (create file if missing): `- [Title](filename) — one-liner`
6. Report back: `✅ Claude auto-memory: {filename}`

#### Phase 5 — Save to mem0 (`--full` only)
Create a subagent (or run concurrently) to save to mem0:
1. Check: skip if `~/.hermes/scripts/mem0_shared_client.py` is absent.
2. Build text: `"{title}: {one_liner}. {body_1_sentence}"`
3. Run:
   ```bash
   python3 ~/.hermes/scripts/mem0_shared_client.py add "<text>" \
     --user-id $USER \
     --no-infer
   ```
4. Report back: `✅ mem0 saved` or `⚠️ mem0 unavailable (skipped)`

#### Phase 7b — Create or update GitHub Issues (`--full` only)
For each bead created in Stage 1, attempt to create a linked GitHub Issue. Run all issue creates in parallel:
```bash
# Resolve repo from git remote (default jleechanorg/agent-orchestrator-ts)
REPO=$(gh repo view --json nameWithOwner -q .nameWithOwner 2>/dev/null || echo "jleechanorg/agent-orchestrator-ts")

gh issue create --repo "$REPO" \
  --title "[resilience] <bead title>" \
  --body "## Summary
<one-paragraph description>

## Acceptance criteria
- [ ] <criterion 1>
- [ ] <criterion 2>

**Bead:** <bd-id>" \
  --label "task" 2>&1
```
- If `gh issue create` returns "repository has disabled issues", log `⚠️ GH Issues disabled on <repo> — bead only` and continue.
- If it succeeds, capture the issue URL and add it to the bead index in the Nextsteps document.
- Report back: `✅ GH Issue #N created` or `⚠️ GH Issues disabled`

---

### Phase 8 — Report completion

**First line:** the chosen mode (see [Modes](#modes-read-first--determines-which-phases-run)).

Then summarize the results and print the final artifact checklist **for the chosen mode**:

**Default mode checklist:**

- `[x]` **Nextsteps independent `.md`** (TOC + executive summary + full detail; bead index + linked beads in queue)
- `[x]` Beads (`br`) written
- `[x]` `~/roadmap/learnings-YYYY-MM.md` updated (includes nextsteps doc path)
- `[x]` `roadmap/activity/YYYY-MM-DD.md` (and `roadmap/README.md` if new date) updated
- `[ ]` (intentionally blank — Claude memory + mem0 + GH Issues are owned by `--full`)

**`--full` mode checklist:**

- `[x]` **Nextsteps independent `.md`** (TOC + executive summary + full detail; bead index + linked beads in queue)
- `[x]` Beads (`br`) written
- `[x]` Claude memory + `MEMORY.md` pointers written
- `[x]` `~/roadmap/learnings-YYYY-MM.md` updated (includes nextsteps doc path)
- `[x]` `roadmap/activity/YYYY-MM-DD.md` (and `roadmap/README.md` if new date) updated
- `[x]` mem0 entry saved (or `⚠️ mem0 unavailable (skipped)`)
- `[x]` GH Issues created (or `⚠️ GH Issues disabled — bead only`)

**Merge-order sanity:** If any recommended action was “merge **A** before **B**” (or “land A then rebase B”), re-assert **A** using the Phase 1 `gh pr view` results from **this** run. If **A** is **MERGED**, do **not** tell the reader to land A; say instead to **rebase B on `main`** (or the appropriate default branch). If **A** is **OPEN**, keep the ordering advice. If **A** is **CLOSED** without merge, drop merge-order advice and flag that the stack needs re-triage.
