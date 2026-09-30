---
name: skillify
description: Use when creating or updating a reusable Claude skill, deciding whether a workflow belongs in a skill, or exporting a requested skill package.
---

# Skillify

Create or improve one reusable Claude skill with the smallest coherent change.
The canonical source for shared Claude skills is
`~/.claude/skills/<name>/SKILL.md` (or the explicitly selected native Claude
home when the user names one).

## Contract

- Reuse before create. Inspect the target and nearby skills before choosing a
  name or adding a package. Update the actual owner when one exists.
- Inspect both the live Claude home and the repository or export source. Follow
  symlinks and record which path is canonical; do not infer ownership from a
  copied file, archive, or stale report.
- `~/.claude/skills/` is the Claude source of truth when the request names the
  normal Claude home; an explicitly selected native Claude home is honored.
  `${HOME}/.codex/skills/` and `${HOME}/.agents/skills/` are projection paths
  only when they are symlinks to that source. Never write independent copies
  there.
- A skill package has one `SKILL.md` at its package root. Do not create a
  nested `SKILL.md` under another skill, and keep backups outside every active
  skill-discovery root.
- A slash command is optional. If one is needed, keep it a thin pointer that
  reads the canonical skill and forwards `$ARGUMENTS`; put the workflow in the
  skill. Do not add a command merely to satisfy a checklist.
- Hermes is an explicit contextual route. Use it only when the user or native
  Hermes instructions select it, and follow that runtime's own resolver and
  packaging rules. Do not apply gbrain, Hermes, resolver, or brain requirements
  to every Claude skill.

## Steps

### 1. Discover the owner

Read the requested target and its nearest existing pattern. Inspect the live
Claude path, the repository path, and any symlink targets. Search for a
same-purpose skill or command before creating a name. Classify the target as
one of:

- existing canonical skill to update;
- existing skill that should be reused without a new package; or
- genuinely new Claude skill.

If the user requests an export, resolve the requested package's dependency
closure first. Export only that package and closure into an isolated skills
repository worktree; preserve unrelated dirty files, home changes, and remote
state.

### 2. Author the minimum useful skill

Keep `SKILL.md` concise and operational. Its frontmatter contains only the
portable `name` and `description`, with the directory name matching `name`.
The description states when the skill applies and uses terms a user would
actually say. The body should explain the purpose, decision boundaries,
ordered actions, and output or evidence contract.

Add a `references/` or `scripts/` file only when it has concrete reuse value.
Do not invent deterministic code, tests, evals, resolver entries, brain or
memory filings, services, schemas, or artifacts that the target and request do
not need. Do not move model judgment into keyword, regex, score, or hardcoded
routing logic.

For a command, use the existing local dispatcher form, for example:

```markdown
---
name: skillify
description: Use when creating or updating a reusable Claude skill.
---

Read `${CLAUDE_HOME:-$HOME/.claude}/skills/skillify/SKILL.md` completely, then execute it with `$ARGUMENTS`.
```

### 3. Validate proportionately

For instruction-only edits, run structural and spelling checks and inspect the
rendered frontmatter. Check any command locally before documenting it; do not
encode a guessed path or flag. Run an existing targeted test when it covers
the changed export or dispatcher. Export changes also run the relevant
installer and portability checks already present in the repository.

For behavior changes, capture a baseline and candidate using realistic
pressure scenarios that exercise the requested boundary. Run an independent
forward check against the candidate. Confirm that the skill preserves existing
authorization, autonomy, evidence, and user-visible failure boundaries. A
written checklist or self-report is not independent proof.

There is no fixed completeness score. Mark each applicable validation as
passed, failed, or not applicable with its reason. Do not claim a resolver,
test, integration, or runtime result when that capability was not run.

### 4. Reconcile and export safely

Before replacing an existing canonical file, make a recoverable backup outside
every active discovery root and record its path. An ignored file inside a
skills tree is still unsafe as a backup. Inspect the export diff for scope,
frontmatter, symlink, and dependency errors. Test the staged export in its
isolated worktree, then promote it only when the user has authorized that
promotion. After promotion or synchronization, hash the exact artifact and
read it back from every requested destination to confirm identical content.

Honor the user's requested PR, `/advice`, `/wa`, merge, and synchronization
scope. Do not invent an additional approval or a self-recursive ironclad or
skillify loop. An explicit merge or sync authorization does not authorize
unrelated packages, home writes, force-pushes, or destructive cleanup.

## Output

Report the canonical owner, whether the skill was reused or created, the files
changed, applicable checks and their fresh results, and any requested export
or synchronization paths with hashes and readback results. State blockers as a
specific unmet authority or failed check, and leave unrelated work untouched.
