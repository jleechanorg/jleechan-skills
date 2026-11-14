---
type: reference
created: 2026-07-15
session: slash-command audit + bidirectional split for /code-standards
---

# `/code-standards` Bidirectional Contract — Reference Implementation

Historical example of a layered slash-command pair (user-scope generic and
repository-local specialized). Reuse the split, not the dated lane list or
paths below. The current generic code-standards skill and the active
repository’s own instructions define the applicable review today.

## Files (delivered 2026-07-15)

### User-scope (project-agnostic)
- `~/.claude/commands/code-standards.md` — 63 lines
- `~/.claude/skills/code-standards/SKILL.md` — 5-point bidirectional contract

### Repo-local (worldai-specialized)
- `your-project.com/.claude/commands/code-standards.md` — 120 lines
- Reciprocal pointer at top, marker `WORLDARCHITECT_CODE_STANDARDS_COMMAND_V1`

## Bidirectional Contract (verbatim, copy-paste basis)

User-scope preamble:

> This is the **project-agnostic** `/code-standards` command, at
> `~/.claude/commands/code-standards.md`. It applies to every repo — including
> ones without a repo-local `.claude/commands/code-standards.md`.
>
> **Bidirectional pointer contract:**
> 1. If the working repo has its own `.claude/commands/code-standards.md`,
>    load **BOTH** this file AND the repo-local one. The repo-local file is
>    allowed to add repo-specific lanes (e.g. `/thermo`, repo-specific smoke
>    markers, repo-specific example scopes) but MUST NOT redefine the four
>    user-scope lanes — those live here.
> 2. The repo-local file MUST contain a reciprocal pointer back to this file
>    so the two stay synchronized.
> 3. If a repo-local file is absent, this file is the complete implementation.

Repo-local preamble:

> **Bidirectional pointer — always look for the other one.**
> This file is the **repo-local** `/code-standards` command for
> `$GITHUB_REPOSITORY`. The project-agnostic counterpart lives at
> `~/.claude/commands/code-standards.md` and is the **source of truth** for
> the four user-scope lanes (ponytail, ZFC, ZFC leveling, root-cause-first).
>
> **When invoked in this repo, load BOTH files.** This file adds
> worldai-specific behavior (the `/thermo` lane, the `/es` evidence rule,
> the worldai smoke-test marker) on top of those four lanes — it does not
> replace them.
>
> If the user-scope file is updated, mirror the change here. If this file
> adds or removes a lane, update both files.

## Lane attribution (the verifiable surface of the contract)

User-scope lanes (always apply):
1. Ponytail (`~/.claude/skills/ponytail/SKILL.md`)
2. ZFC (`~/.claude/skills/zero-framework-cognition/SKILL.md`)
3. ZFC leveling (`~/.claude/skills/zfc-leveling-roadmap/SKILL.md`)
4. Root-cause-first (`~/.claude/skills/root-cause-first/SKILL.md`)

Repo-local additions (worldai only):
5. `/thermo` (load `~/.claude/skills/thermo-nuclear-code-quality-review/SKILL.md`)
6. `/es` evidence check (real server, real LLM, captioned video)

## Audit results from this session (2026-07-15)

Full sweep of `~/.claude/commands/*.md` (~100 files) for repo-specific
content. Bucketing:

### Bucket A — All-or-nothing worldai-only (9 files, banner added)

| File | Reason | Disposition |
|---|---|---|
| `end2end-testing.md` | hardcoded to `$PROJECT_ROOT/tests/test_end2end/`, Fake Firestore | Banner |
| `investigatedice.md` | hardcoded to GCP `worldarchitecture-ai`, dice service | Banner + new repo-local pointer |
| `worldai-usage-email.md` | requires worldai worktree + `scripts/daily_campaign_report.py` | Banner + new repo-local pointer |
| `feature-dev.md` | hardcoded to Python/Flask/Firebase/Gemini + `$PROJECT_ROOT/` | Banner + new repo-local pointer |
| `auto-factory.md` (symlink) | drives `$GITHUB_REPOSITORY/.beads/` | Banner + new repo-local pointer |
| `af.md` (symlink) | alias for /auto-factory | Banner + new repo-local pointer |
| `gene.md` | Genesis = Your Project orchestration system | Banner + new repo-local pointer |
| `benchg-ts.md` | hardcoded `worktree_ralph/`, `worldai_genesis2`, `worldai_ralph2` | Banner |
| `exportcommands.md` | `perl -pi -e` filter list hardcoded to worldai patterns | Banner |

### Bucket B — Conditional references (left as-is)

`a.md`, `fullrun.md`, `beads.md`, `green.md`, `er.md`, `evidence_review.md`,
`redgreen.md`, `testing-layers.md`, `claude-md-validate.md`, `polish.md`,
`slack-audit.md`, `tester.md`, `testerc.md`, `second_opinion.md` — all carry
one-line conditional mentions of `$PROJECT_ROOT/` or `your-project.com` in
evidence stacks, CLI examples, or test fixtures. None of them are
"repo-specific logic" — they're legitimate conditional content that
triggers only when working in the worldai repo.

### Bucket C — Project-agnostic (left as-is)

`thermo.md`, `thermo-nuclear-code-quality-review.md`, `ms.md`,
`memory_search.md`, `hermes.md`, etc. — already project-agnostic.

## Symlink gotcha (caught in this session)

`~/.claude/commands/auto-factory.md` and `~/.claude/commands/af.md` are
symlinks to `~/projects/dark-factory/.claude/commands/<name>.md`. Edits via
the symlink path land in the dark-factory repo (correct home). Verified:

```
$ ls -la $HOME/.claude/commands/auto-factory.md
... $HOME/.claude/commands/auto-factory.md ->
$HOME/projects/dark-factory/.claude/commands/auto-factory.md
```

Use `ls -la` before editing any command file with an unfamiliar name.

## Reciprocal pointers created in `your-project.com/.claude/commands/`

7 new thin pointer files (YAML frontmatter + 2-3 line body, no other
content):

- `investigatedice.md`
- `worldai-usage-email.md`
- `feature-dev.md`
- `auto-factory.md`
- `gene.md`
- `benchg-ts.md`
- `af.md`

Total: 16 file edits across 2 repos, no PR (config files outside
the worldai repo's normal git surface — pending user review for which
surface to PR through).
