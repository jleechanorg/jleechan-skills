---
name: slash-command-layering
description: "Use when designing, refactoring, or auditing Claude/Codex slash commands under `~/.claude/commands/*.md` or repo-local `.claude/commands/*.md`. Covers the project-agnostic (user-scope) vs repo-specific (repo-local) split, the bidirectional-pointer contract, the `> Worldai-only command` / `> Repo-local pointer` banner conventions, the audit pattern for finding repo-specific content embedded inside otherwise-generic commands (hardcoded paths, filter lists, single-repo example scopes), and the gotchas (symlinks to sibling repos, reciprocal-pointer requirement, mirror-on-update rule, missing-command probe-before-block). Triggers on 'make /X project agnostic', 'split this command into user-scope and repo-local', 'this command is too worldarchitect-specific', 'I want /X to work in any repo', 'audit ~/.claude/commands for repo-specific logic', 'add a bidirectional pointer', or when the user invokes a slash command that does not exist in the current runtime."
changelog:
  - "1.1.2 (2026-07-30): Gotcha #6 patch — Codex canonical skill root is `~/.agents/skills/`, not `~/.codex/skills/` (the latter was archived 2026-06-13). Symlink `ln -s ~/.claude/skills/<name> ~/.agents/skills/<name>` is the preferred Codex-native pattern; pointer-only fallback is functional but indirect. Added Gotcha #8 — Hermes `SOUL.md` redundancy carve-out: cross-runtime invariants get 4 runtime pointers only, not a 5th SOUL.md copy; SOUL.md pointers are reserved for Hermes-specific behavior (`## COMMIT:` blocks, launchd, Slack-routing)."
  - "1.1.1 (2026-07-20): Corrected Gotcha #7 — `/superpowers-brainstorm` DOES exist at `~/.claude/commands/superpowers-brainstorm.md` (326 B, wraps `superpowers:brainstorming` skill). The prior 1.1.0 'verified case' claiming 'No such slash command exists' was the wrong answer the user corrected in C0AH3RY3DK6/1784584779 reply 'Read the slash commands that one definitely exists'. Now documents: (a) the required grep recipe before claiming a slash cmd is absent, (b) the slash-command-vs-skill distinction (wrapper file = instructions to invoke the skill, follow the SKILL not the wrapper), (c) the brainstorming skill pitfalls (HARD-GATE no-implement-before-design, one-Q-at-a-time rule violated by multi-option A/B/C dumps, `/super` override only)."
  - "1.1.0 (2026-07-20): Added Gotchas #7 — 'user typed /X and /X does not exist in this runtime — probe before blocking or fabricating'. Covers three runtime-shaped fallback patterns (Hermes/Slack/CLI: synthesize inline; Claude Code/Codex: distinguish /super from /superpowers:brainstorm; unknown: probe-resolver then fall back) with the 2026-07-20 /superpowers brainstorm verification case."
version: 1.1.1
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [slash-commands, claude-code, project-agnostic, repo-local, bidirectional-pointer, organization]
    related_skills: [hermes-agent-skill-authoring, agent-harness-engineering]
---

# Slash Command Layering — Project-Agnostic vs Repo-Local

## Overview

Slash commands in this org live in two parallel trees:

1. **`~/.claude/commands/<name>.md`** — user-scope, project-agnostic.
   Default fallback for every repo, including ones with no repo-local
   `.claude/commands/` directory. Lives in the user's home dir, gitignored
   (`~/.claude/` is user-scope configuration).
2. **`<repo>/.claude/commands/<name>.md`** — repo-local, project-specific.
   Tracked in the repo so the contract ships with the code. Supersedes the
   user-scope copy when the working repo is the one being modified.

The two trees MUST coexist. The user-scope copy is the **fallback** and
**default**; the repo-local copy is **additive** (it adds repo-specific
behavior on top of the four user-scope lanes — it does not replace them).
This is the same split skills use (`~/.claude/skills/` vs
`<repo>/.claude/skills/`), but for slash commands.

## When to Use

- User asks to "make /X project agnostic" / "generalize /X" / "split /X
  into user-scope + repo-local" / "this command is too <project>-specific"
- User asks to "audit ~/.claude/commands for repo-specific logic" /
  "find any commands that hardcode <project> paths" / "make all commands
  project-agnostic"
- User adds a repo-local `.claude/commands/<name>.md` and the user-scope
  copy needs a reciprocal back-pointer (or vice versa)
- A command was working in one repo but breaks when run in another
  (e.g. hardcoded `$PROJECT_ROOT/` paths, hardcoded GCP project names,
  hardcoded symlinks to a sibling repo)
- Codex-side mirrors (`~/.codex/commands/`, `<repo>/.codex/commands/`)
  need the same treatment

**Don't use for:** SKILL.md authoring (use
`hermes-agent-skill-authoring`), one-off banner edits on a non-shared
command, or commands that intentionally live in only ONE tree with no
fallback (no layering needed).

## The Bidirectional-Pointer Contract

Both files in a layered pair MUST point at each other and document
exactly what is shared vs. added. Concrete requirements:

### User-scope file (`~/.claude/commands/<name>.md`)

1. **State that it is project-agnostic** — applies to every repo,
   including ones with no repo-local copy.
2. **Document the bidirectional contract**: "If the working repo has its
   own `.claude/commands/<name>.md`, load **BOTH** files. The repo-local
   file is allowed to ADD repo-specific behavior (e.g. `/thermo`,
   repo-specific smoke markers, repo-specific example scopes) but MUST
   NOT redefine the four user-scope lanes — those live here."
3. **List the user-scope lanes** in a Quick Reference table (the lanes
   that always apply, regardless of which repo).
4. **Do not mention any specific repo** by name. Generic phrases like
   "the working repo" or "the repo-local copy" are correct.

### Repo-local file (`<repo>/.claude/commands/<name>.md`)

1. **Reciprocal pointer at the top**: "This file is the repo-local
   `/<name>` command for `<OWNER>/<REPO>`. The project-agnostic
   counterpart lives at `~/.claude/commands/<name>.md` and is the source
   of truth for the N user-scope lanes."
2. **Document which lanes are added vs inherited** — separated list, so
   the contract is verifiable by reading one file.
3. **Preserve any revision marker** (e.g. `WORLDARCHITECT_CODE_STANDARDS_COMMAND_V1`)
   in both the marker line and the smoke-test spec.
4. **Mirror-on-update rule**: if the user-scope file changes, this file
   MUST mirror the change. Reciprocal is also true if a repo adds a
   lane that generalizes (rare).

### Skill source-of-truth file (`~/.claude/skills/<name>/SKILL.md`)

If the slash command dispatches to a skill, the skill's SKILL.md must
also document the bidirectional contract, with the same 5-point list:

1. Load BOTH files
2. Always reference the user-scope lane source skill
3. Define repo-specific behavior WITHOUT forking user-scope lanes
4. Stay loadable in codex debug smoke-test mode
5. Reciprocal pointer back to the user-scope command

**Anti-pattern:** the user-scope file says "if a repo-local file exists,
PREFER it" — wrong. The user-scope is always loadable; the repo-local
file adds on top.

## The Three Banner Conventions

When a command is intentionally scoped to a single repo (no project-agnostic
intent), use one of these three banners. Each signals a different layer.

### 1. `> Worldai-only command.` (user-scope file that is hardcoded)

For commands in `~/.claude/commands/` whose content is hardcoded to a
specific repo. Examples: `investigatedice.md` (hardcoded to GCP project
`worldarchitecture-ai`), `worldai-usage-email.md` (requires a worldai
worktree). Body should explain:

- Which repo it is hardcoded to
- Why (GCP project, specific paths, specific scripts)
- Where the repo-local counterpart lives (for completeness — usually a
  thin pointer file)

Two-line minimum:

```markdown
> **Worldai-only command.** <one-sentence hardcode reason>.
> The repo-local counterpart lives at
> `<OWNER>/<REPO>/.claude/commands/<name>.md> and is preferred when working
> in that repo. When invoked outside the <repo> repo, <what fails>.
```

### 2. `> Repo-local pointer.` (repo-local thin pointer file)

For repo-local commands that exist only to expose the user-scope canonical
in the repo's command surface. Examples: `your-project.com/.claude/commands/investigatedice.md`,
`gene.md`. YAML frontmatter + 2-3 line body:

```markdown
> **Repo-local pointer.** This file exists so the <repo>'s command surface
> is self-contained. The canonical implementation is at
> `~/.claude/commands/<name>.md` — load that one. <one-sentence scope note>.
```

Body content beyond this is unnecessary and creates drift.

### 3. Full repo-local file (repo-local but not a pointer)

For repo-local commands that add real repo-specific behavior (lanes,
markers, evidence rules). Example: `your-project.com/.claude/commands/code-standards.md`
adds the `/thermo` lane + `/es` evidence check + `WORLDARCHITECT_CODE_STANDARDS_COMMAND_V1`
marker. These MUST:

- Load BOTH files (per the reciprocal pointer rule)
- Inherit all user-scope lanes
- Add new lanes in a clearly-separated section
- Preserve the user-scope lanes untouched

## The Audit Pattern

When asked to "audit ~/.claude/commands for repo-specific content":

1. **List all commands** under `~/.claude/commands/*.md` and any
   `~/.codex/commands/*.md`. Skip `_archive/`, `tests/`, `lib/`,
   `backup-*` subdirs.
2. **Grep each file for repo-specific patterns.** Minimum regex set:
   ```bash
   rg -l -i \
     'worldarchitect|mvp_site|world_logic|rewards_engine|worldai|thermo|jleechanorg/worldarch' \
     ~/.claude/commands/*.md
   ```
   Adjust the pattern to whatever repo is in question
   (`jleechanorg/<repo>` patterns, `<GCP-project-id>`, hardcoded paths).
3. **Classify each hit into one of four buckets:**
   - **A — All-or-nothing worldai-only** (entire file is worldai-specific,
     no general use). Add `> Worldai-only command` banner. Optionally move
     to repo-local.
   - **B — Conditional reference** (one-line mention in evidence stack,
     example scope in CLI usage, env var in test fixture). Leave alone —
     these are not "repo-specific logic," they're legitimate conditional
     content that triggers only when working in the repo.
   - **C — Hardcoded paths or filter list** (e.g. `benchg-ts.md`'s
     `/Users/$USER/projects/worktree_ralph/` paths, `exportcommands.md`'s
     `perl -pi -e` filter list). Add banner. Do NOT move — moving
     changes the discoverability for users in other repos unless they
     also have the repo-local copy, and the script is still on PATH.
   - **D — Already project-agnostic** (`thermo.md`, `ms.md`,
     `memory_search.md`). Leave alone.
4. **For each A or C hit, decide whether to add a reciprocal repo-local
   pointer.** If the repo has a `<repo>/.claude/commands/<name>.md`
   already, just add the banner. If not, create a thin pointer file
   (Option 2 above) so the repo-local command surface is self-contained.
5. **Skip B hits.** Conditional references are valid scope; "fixing" them
   to be generic adds noise without value.
6. **Report disposition in the format:** `<command>: <bucket> —
   <banner|pointer-move|left-as-is>` with a one-line reason.

If the user only asked about `/code-standards` (not a full audit), still
walk this pattern — but limit it to the single command and report what
other commands also have repo-specific content as a follow-up finding.

## Gotchas

1. **Symlinks can rewrite the wrong file.** Commands like
   `~/.claude/commands/<name>.md` are often symlinks to sibling repos
   (e.g. `~/projects/<sibling-repo>/.claude/commands/<name>.md`). When the `patch`
   tool writes via the symlink path, it writes to the sibling repo, not
   the user-scope file. Always check `ls -la` and `readlink` before
   editing; resolve the symlink explicitly if you want the user-scope
   file to be the edited target. (`dev/er.md` had this exact failure
   mode in the original session — fixing the symlink-target edited the
   sibling repo's copy, which was correct because that repo was the
   canonical home, but not obvious without `readlink`.)

2. **Marker-name preservation.** Repo-local commands with revision
   markers (`WORLDARCHITECT_CODE_STANDARDS_COMMAND_V1`) MUST keep the
   marker verbatim across rewrites. Any rename silently breaks the
   smoke-test gauntlet that confirms the right file loaded.

3. **Don't delete the user-scope copy "because it's redundant."** The
   user-scope copy is the FALLBACK for every other repo (not just the
   one with the local copy). Deleting it breaks every repo that hasn't
   yet added its own.

4. **Don't move worldai-only commands into the worldai repo without
   decommissioning the user-scope file.** If the user-scope file stays
   in `~/.claude/commands/` AND a repo-local copy is added, both load;
   that's the contract. If you remove the user-scope copy and only the
   repo-local stays, every other repo loses access. Either commit to the
   move + delete the user-scope file (and then the moved file is no
   longer a layering pair — it's just a repo-local command), or leave
   both and rely on the banner to signal scope.

5. **Mirror-on-update is bidirectional but asymmetric in cost.** When
   the user-scope file adds a lane, every repo-local file MUST mirror it
   (low cost). When a repo adds a lane that generalizes (rare — e.g. the
   `/thermo` lane could one day apply to non-worldai repos), promoting it
   to the user-scope file requires explicit user approval — do not
   auto-promote.

6. **`/codex` mirror has the same shape.** `~/.codex/commands/<name>.md`
   and `<repo>/.codex/commands/<name>.md` mirror Claude's tree.
   Bidirectional contract applies, but Codex discovery is via
   `~/.codex/skills/` rather than skill files. Update both trees in
   the same PR.

   **Update 2026-07-30:** Gotcha #6 above is partially stale — Codex's
   canonical skill root is now `~/.agents/skills/` (per
   `~/.codex/AGENTS.md` § "Skills Discovery"), not `~/.codex/skills/`,
   which was archived 2026-06-13. When the canonical skill lives at
   `~/.claude/skills/<name>/` and Codex needs native discovery, prefer
   the **symlink** pattern:

   ```bash
   ln -s ~/.claude/skills/<name> ~/.agents/skills/<name>
   ```

   The pointer-only fallback (have the Codex pointer reference
   `~/.agents/skills/<name>/SKILL.md` and let Codex fall back to the
   parent `~/.claude/skills/` index) is functional but indirect — call
   it out in the report so the user can opt into the symlink. If you
   find yourself writing "Codex will fall back to the parent index"
   in three or more reports, the symlink is the right answer and
   should be the default.

7. **User typed `/X` and `/X` does not exist in this runtime — probe before
   blocking or fabricating.** When the user invokes a slash command the
   agent cannot execute (unknown name, or it's only defined in Claude
   Code / Codex plugin form and we're in Hermes / Slack / CLI), the
   right move is **NOT** to declare "can't run that." Three concrete
   patterns depending on runtime:

   **Hermes / Slack / CLI runtimes:** there are NO *interactive* slash
   commands — the agent runs once per message and cannot spawn a
   terminal. But the slash command FILES themselves are pure content +
   instructions the agent can `read_file` and follow. The right move
   is to (a) `read_file` the slash command + the underlying skill,
   (b) follow the skill's instructions literally (including any
   HARD-GATEs like "no implementation before design approval"), and
   (c) drive the work to its end-state in-thread. Never block on
   "can't run that slash command" — and never claim a slash command
   is absent without grepping first. Verified case 2026-07-20
   (Slack C0AH3RY3DK6/1784584779): user typed `/superpowers brainstorm
   to design the new god campaign mechanics`. The slash command DOES
   exist — `~/.claude/commands/superpowers-brainstorm.md` (326 B,
   `disable-model-invocation: true` → user-only invokable) wrapping the
   `superpowers:brainstorming` skill at
   `~/.codex/superpowers/skills/brainstorming/SKILL.md`. The full
   pipeline `/super` (15.4 KB) is at
   `~/.claude/commands/super.md` and does brainstorm → plan → execute
   → cloud-build Box dispatch with the user's "auto-pick all questions"
   override. A prior agent's claim that `/superpowers brainstorm` was
   absent was corrected by the user reply *"Read the slash commands
   that one definitely exists"* — the lesson is: ALWAYS grep before
   claiming a slash command is missing. Required grep recipe:

   ```bash
   ls -la ~/.claude/commands/ | grep -iE "<name>|brainstorm|super"
   ls -la ~/.codex/commands/ 2>/dev/null | grep -iE "<name>"
   find ~/.codex/superpowers/skills -maxdepth 3 -name "SKILL.md" \
     | xargs grep -l "<name>" 2>/dev/null
   find ~/.codex/plugins/cache -maxdepth 4 -type d \
     -name "*super*" 2>/dev/null
   ```

   **Slash-command vs skill distinction (CRITICAL):**
   `~/.claude/commands/superpowers-brainstorm.md` is a 326-byte wrapper
   that says "invoke the `superpowers:brainstorming` skill and follow it
   exactly as presented." The actual protocol lives at
   `~/.codex/superpowers/skills/brainstorming/SKILL.md`. When the user
   invokes a slash command that is a wrapper, read the wrapper + the
   skill, and follow the SKILL's instructions (HARD-GATEs, one-Q-at-a-time
   rule, etc.) — do not invent your own protocol from the wrapper text.

   **Claude Code / Codex terminal runtimes:** the `/superpowers` plugin
   ecosystem provides slash commands like `/superpowers:brainstorm`,
   `/superpowers:write-plan`, `/superpowers:execute-plan`. These are
   distinct from the `/super` and `/superlight` cloud-build dispatch
   commands. **Do not auto-substitute one for the other.** The names
   share a prefix but solve different problems: `/super` = cloud-build
   Box hand-off (run a committed plan remotely), `/superpowers:brainstorm`
   = interactive ideation → design plan. If the user typed one and
   meant the other, ask.

   **Generic probe-recipe when the resolution is uncertain:** the slash
   command resolver order is documented in SOUL.md
   (`## Slash Command Discovery`): (1) `<repo>/.claude/commands/<name>.md`,
   (2) `~/.claude/commands/<name>.md`, (3) `~/.claude/skills/<name>/SKILL.md`.
   If none resolve, the command does not exist in this runtime — fall
   back to the runtime-appropriate pattern above. Do NOT tell the user
   "I can't run that, please paste the content"; that pushes work back
   to the human.

   **Brainstorming skill pitfalls (verified 2026-07-20):** when running
   `~/.codex/superpowers/skills/brainstorming/SKILL.md`, the HARD-GATE
   is "Do NOT invoke any implementation skill, write any code, scaffold
   any project, or take any implementation action until you have
   presented a design and the user has approved it." The skill ALSO
   requires **one question at a time** ("Only one question per message
   - if a topic needs more exploration, break it into multiple
   questions"). A common violation: dumping 3-4 design options as
   A/B/C in one message instead of one Q at a time. The `/super`
   command has an explicit override ("auto pick all the questions")
   that the user opted into on 2026-07-20 — but plain brainstorming
   does NOT. If you invoke brainstorming without `/super`, follow
   the upstream one-Q-at-a-time rule literally.

8. **Hermes `SOUL.md` redundancy carve-out for cross-runtime rules.**
   When authoring a new skill via `/up` (or any user-scope policy file
   that lives in the four runtime surfaces — `~/.claude/CLAUDE.md`,
   `~/.codex/AGENTS.md`, `~/.gemini/GEMINI.md`, `~/.cursor/rules/*.mdc`),
   the question "should this also go in `~/.hermes/workspace/SOUL.md`?"
   has a clear answer:

   - **NO** if the rule is a **cross-runtime invariant** (compute/work,
     formatting, environment prefs, a general workflow contract).
     The four runtime pointers above already cover every session in
     which a coding agent runs; Hermes reaches the skill via
     `skill_view(name=...)`. Adding a Hermes pointer is just a copy
     of what the runtime pointers already do — it adds drift surface
     and no new enforcement.

   - **YES** only when the rule is **Hermes-specific behavior** — a
     new `## COMMIT:` block, a launchd contract, a Slack-channel
     routing rule, a heartbeat policy. These genuinely need to live
     in SOUL.md because the other runtimes don't load it.

   Verified 2026-07-30: `/up parallelize-to-ceiling` applied the
   cross-runtime rule to 4 surfaces and correctly skipped SOUL.md.
   Without the carve-out, an agent would reflexively add a 5th
   pointer (just to be "complete"), which is a `no-op prose` failure
   per `hermes-agent-skill-authoring` § "Writing Quality Principles."

## Reference Implementation

See `references/code-standards-bidirectional-contract-2026-07-15.md` for
the verbatim contract, lane attribution table, audit-bucket results
(A/B/C), the sibling-repo symlink gotcha, and the list of reciprocal
pointers created in the same session that spawned this skill. Use it as
a copy-paste template for other layered slash-command pairs.

See `references/slash-cmd-absent-false-claim-2026-07-20.md` for the
session where Gotcha #7's "verified case" claim was itself wrong
(`/superpowers-brainstorm` was declared absent when it existed at
`~/.claude/commands/superpowers-brainstorm.md`). The reference
documents the four-source grep recipe, the brainstorming-skill HARD-GATE
and one-Q-at-a-time violations, and the corrected agent behavior
post-patch. Read it whenever you're tempted to claim a slash command
or skill doesn't exist.

## Verification Checklist

After any slash-command-layering edit, verify:

- [ ] User-scope file has project-agnostic description, no repo-specific
      paths in body, no "prefer repo-local" framing
- [ ] User-scope file has the bidirectional contract block in body
- [ ] Repo-local file (when present) has reciprocal pointer at top
- [ ] Both files preserve any revision marker verbatim
- [ ] Quick-reference lanes table in user-scope file matches lanes in
      `.claude/skills/<name>/SKILL.md`
- [ ] No symlinks bypassed unintentionally (`ls -la` check before edit)
- [ ] Mirror-on-update rule documented in BOTH files (one-line
      sentence each)
- [ ] Codex-side mirror updated if the command has a Codex presence
- [ ] `grep -c 'jleechanorg/<repo>'` on the user-scope file returns 0
      (no repo-specific leaks)
- [ ] `grep -c '~/.claude/commands/<name>.md'` on the repo-local file
      returns ≥ 1 (reciprocal pointer present)
- [ ] Smoke-test mode in both files reports the same paths (sanity
      check: if smoke-test mode prints different paths, the contract is
      wrong)
