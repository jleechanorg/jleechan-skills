# Portable skills: plugin folders and environment variables (design)

Status: design auto-picked by `/sq` (2026-11-04). The plugin-layout slice is implemented;
independent source review is owned by the PR reviewers, not by this document.

## Problem

`AGENTS.md` requires every exported skill to work for another developer on a
brand-new machine, in any repository. An audit of `.claude/skills/` found that the
export does not meet that bar: some skills only make sense inside one product
(WorldArchitect.AI, AI Universe, or the author's self-hosted runner fleet), and many
generic skills hardcode a machine, checkout path, repository, Slack/GCP identifier,
personal name, or product example.

The per-leak audit records (file, line, text, kind, proposed replacement) are inputs
to implementation, not shipped artifacts.

Typical leaks:

- **Machine.** Personal SSH host aliases for companion machines; `~/projects/<repo>` and
  `~/projects_other/...` checkouts; `/opt/homebrew`, `~/.local/bin/<tool>`, pinned nvm
  paths; macOS `~/Library/Logs` paths inside Linux units.
- **Account.** `--repo <owner>/<product-repo>` defaults; Slack channel, user, and bot
  IDs; GCP project ids and numbers; Firebase UIDs and campaign IDs; personal names.
- **Product.** `mvp_site/`, `testing_mcp`, D&D level-up rules, and Firestore schemas
  embedded in generic testing, evidence, and harness skills.

## Goals

1. `.claude/skills/` (the default export and `--all` install) contains no product-only
   skills and no hardcoded machine, account, or product values.
2. Product-only skills stay available as opt-in Claude Code plugins in
   `plugins/<name>/`, installable through the existing marketplace.
3. Machine and account values come from one documented set of environment variables.
   Each has a safe default or fails with a "not configured" message.
4. The fresh-machine rule is stated in `AGENTS.md` and `CLAUDE.md`, and the existing
   zero-PII/portability scanners cover the plugin folders too.

## Non-goals

- Rewriting `.claude/skills_archive/`, `.beads/`, or `shared/comparison-decisions.json`
  history entries. These are archival and are not installed.
- Changing `install-claude-commands.sh`. Plugin skills install through Claude Code's
  native plugin system (see D3).
- Changing what any skill does, beyond resolving its values at run time.
- Parameterizing every generic skill's host, path, and account values. That work is
  split across separate, independently reviewable slices; this document records the
  contracts they must follow, not their contents.

## Approaches considered

| # | Approach | Verdict |
|---|---|---|
| A | **Plugin folders plus an env-var registry.** Move product-only skills to `plugins/<product>/skills/`, registered in `.claude-plugin/marketplace.json`. Replace machine and account literals in generic skills with registry variables. Move product examples into plugin companion skills. | **Selected.** It uses the Claude Code plugin format that the repository already ships, keeps generic skills small, and matches the `user-story` + repo-local `user-story-*` companion pattern that already exists. |
| B | Keep all skills in place and put a single `if WorldArchitect…` section in each skill | Rejected. Product text still ships to every installer and fails the fresh-machine rule. |
| C | Delete product-only skills and leave them to the product repositories | Rejected. The author still uses them, and the product repositories are not in this session's scope. Plugins keep them installable without polluting the generic export. This option stays open as a later step. |

## Design

### D1. Plugin folders

```
plugins/
  worldarchitect/                     # WorldArchitect.AI product skills
    .claude-plugin/plugin.json
    skills/<skill>/SKILL.md (+ references/, scripts/, local.sh)
    commands/<cmd>.md                 # only commands whose target skill moved here
  ai-universe/                        # AI Universe MCP server skills
    .claude-plugin/plugin.json
    skills/<skill>/SKILL.md
  self-hosted-runners/                # runner-fleet operations (parameterized)
    .claude-plugin/plugin.json
    skills/<skill>/SKILL.md (+ scripts/, tests/fixtures/)
```

- Each `plugin.json` has `name`, `description`, `version`, `author`, `homepage`,
  `repository`, and `license`. The author is the repository's existing team identity,
  the same one the root plugin uses. Manifests do **not** list `skills` or `commands`:
  Claude Code discovers a plugin's default `skills/` and `commands/` folders, and
  listing them again can load them twice.
- `.claude-plugin/marketplace.json` gets one `plugins[]` entry per folder, with
  `"source": "./plugins/<name>"`. Install with
  `/plugin marketplace add <owner>/<repo>` (this repository's own public location) and
  then `/plugin install <name>@<marketplace-name>`.
- Plugin skills follow the same zero-PII rules as the main export. Real UIDs,
  campaign IDs, project numbers, and Slack IDs become placeholders or plugin
  variables (`FIREBASE_PROJECT_ID`, `GCP_PROJECT_ID`, `AI_UNIVERSE_MCP_URL`).
  Moving a skill to a plugin does not license keeping secrets or personal data.
- Required variables and install details live in `docs/portability-env-vars.md` and in
  the marketplace entry description; plugins do not ship a second copy of either.

**What moves.** A skill moves wholesale when its name and purpose are product-only,
no generic skill depends on it as a required read, and no curated install profile in
`shared/install-profiles.json` selects it:

- **worldarchitect:** bq-evidence-reading, character-creation-modal-exit,
  dice-roll-audit, field-ownership-contracts, firebase-prod-campaigns, generatetest,
  level-up-validation, levelup, local-dev-server, mobile-investigations,
  pr-preview-servers, repro-copy, repro-twin-clone-evidence, smoke-local,
  smoke-test-local, testing-infrastructure, user-story-worldai, worldai-agent-routing
  (renamed from `agents` so it no longer collides with `.claude/agents/`),
  worldai-auth, worldarchitect-codebase-sherpa, zfc-leveling-roadmap.
- **ai-universe:** ai-universe-auth, ai-universe-httpie,
  ai-universe-second-opinion-workflow, secondo-dependencies.
- **self-hosted-runners:** ezgha-watchdog, runner-health,
  self-hosted-runner-preflight, repo-and-infra-locations (rewritten as a template that
  reads machine-local configuration).

Other mentions of a moved skill (`closure_excluded`, `shared/retain-local.json`,
non-curated profile entries, references, workflow paths) are removed or reworded in the
same change, so nothing points at a path that no longer exists.

**What splits (not in this slice).** When a product-flavored skill has a generic name,
generic callers, or a place in an install profile, a generic skill stays behind and the
product content becomes a plugin companion named `worldai-<skill>`:

| Skill | Callers | Result |
|---|---|---|
| testing-layers | `prw` profile, pr-lifecycle, evidence-coverage | Generic version stays; product content goes to `worldai-testing-layers` |
| smoke | pr-babysit, `/smoke` command | Generic version stays; product content goes to `worldai-smoke` |
| harness-guardrails, evidence-review, evidence-standards, ui-video-evidence, llm-testing | Several generic callers | Each skill's product section moves to one `worldai-<skill>` companion |

**References.** Generic skills never link to plugin files by relative path, because the
plugin may not be installed. They name the companion by convention instead, for
example: "if an installed product plugin provides a companion for this skill, read it",
or "a product plugin's `<skill>` skill, if installed". Commands whose only skill target
moved move with the skill into `plugins/<name>/commands/`.

**Dependencies and link closure.** An installed plugin may depend on the declared
generic core it is installed alongside: it may name a core skill by name, and it may
read a repository-relative script only when the skill states that the repository is a
prerequisite. It must not resolve a moved skill through the generic export path
(`.claude/skills/<moved-skill>/…`) or through any personal or absent-repository path.
A plugin command that dispatches to its own skill points at that skill inside the
plugin, not at a copy in the default export. Do not duplicate a canonical shared skill
inside a plugin to satisfy a literal reading of "self-contained": duplication creates
two drifting copies, and `tests/test_plugin_folders.py` asserts links stay within the
plugin or its declared dependencies.

**Host floor.** Plugin scripts run on the operator's own host, so they use
`#!/usr/bin/env bash` and the system `python3`: no bash-4-only constructs
(`declare -A`, `mapfile`, `${var,,}`), no GNU-only coreutils flags, and no Python
syntax that needs more than 3.8 at import time. Mac hosts therefore run them with
bash 3.2 and the Command Line Tools Python.

### D2. Environment variable registry

`docs/portability-env-vars.md` is the single registry. Rules:

1. Resolution order: an explicit env var, then a value derived from the current
   repository or tool, then the documented default. If none applies, fail with
   `<VAR> not configured: <what to set>`. Never guess a host, path, or repository.
2. Existing names win over new ones (`PROJECT_ROOT`, its accepted alias `REPO_ROOT`,
   `${CLAUDE_HOME:-$HOME/.claude}`, `ROADMAP_DIR`, `WIKI_ROOT`, `HERMES_HOME`,
   `AO_CONFIG_PATH`). Where the audits proposed duplicate names (`WIKI_DIR`,
   `WIKI_PATH`), the registry keeps one (`WIKI_ROOT`).
3. Conventional home-based locations (`$HOME/.hermes`, `$HOME/roadmap`) may be defaults
   only when the skill checks that they exist and skips only the dependent steps when
   they do not. Missing optional tooling is "unavailable/skipped" for an unrelated task,
   not a universal blocker.
4. Production cloud targets are explicit: `FIREBASE_PROJECT_ID` is required and never
   derived from `GCP_PROJECT_ID`, so a skill that touches production data cannot target
   whatever project gcloud happens to consider active.
5. Removed personal identifiers are not replaced with variables or legacy fallbacks.
   `SLACK_OPERATOR_DM_CHANNEL` is explicit and no personal-named legacy variable is
   read; existing users rename their own export in their machine-local shell profile.
   Values that were personal names, IDs, or paths are deleted or become generic wording
   such as "the operator" or `<campaign-id>`.
6. Tools resolve through `command -v <tool>`. A `*_BIN` override exists only where a
   script needs one. Users set values in their shell profile or in the optional sourced
   file `${XDG_CONFIG_HOME:-$HOME/.config}/jleechan-skills/env`. Skills never write
   that file, and no capability gains a mandatory new credential just because it is
   unused.

### D3. Install surface

- `install-claude-commands.sh` keeps installing `.claude/skills/` only. Its
  `--all` result shrinks by the moved skills, which is intended.
- Plugins install natively through the marketplace. A bash-installer
  `--plugin` flag is deferred until someone asks for it (YAGNI).
- `.agents/plugins/` (Antigravity) keeps pointing at `.claude/skills/`; no
  plugin entries are added there.

### D4. Enforcement

- **Rules.** `AGENTS.md` states the fresh-machine, any-developer invariant;
  `CLAUDE.md` points to it.
- **Plugin structure test** (`tests/test_plugin_folders.py`). Every marketplace source
  exists. Every `plugins/*/.claude-plugin/plugin.json` parses and its name matches the
  folder. Every plugin has at least one `skills/<name>/` whose frontmatter `name`
  matches the folder. No name exists in both `.claude/skills/` and a plugin. Every
  relative Markdown link inside a plugin resolves within that plugin.
- **Privacy scans cover plugins.** `tests/test_skill_export_no_personal_paths.py` and
  `tests/test_skill_personal_identifiers.py` (backed by
  `scripts/skill_portability_scan.py`) scan `plugins/` as well as `.claude/skills/`, so
  moving a skill never removes it from zero-PII enforcement.
- **Installer and closure owners stay authoritative.** `tests/test_installer.py`,
  `tests/test_command_closure.py`, `tests/test_thin_command_dispatchers.py`, and
  `tests/test_portable_install.py` continue to define installer, closure, alias, and
  dependency behavior; a moved skill updates them rather than adding a parallel check.
- **CI triggers cover the new tree.** `.github/workflows/tests.yml` path filters include
  `plugins/**` and `.claude-plugin/**`, so a plugin-only change runs the contract suite.

### Retired proposals

Explicitly not adopted, so a later reader does not restore them:

- **Product-token ratchet plus a generated allowlist** (`test_product_token_ratchet.py`,
  `tests/fixtures/product_token_allowlist.txt`). It duplicates the existing zero-PII
  scanners, ships a machine-generated allowlist that grows silently, and is a
  keyword-over-prose gate that the current `AGENTS.md` testing policy does not authorize.
- **Scan-count tables and per-PR branch/ordering plans.** Counts and branch stacks go
  stale as soon as one slice merges; this document states outcomes instead.
- **A committed task-by-task implementation plan.** It is obsolete the moment the slice
  lands, and the repository keeps the design as the spec.

## Delivery

This slice ships: the `AGENTS.md`/`CLAUDE.md` invariant, this design, the env-var
registry, the plugin folders and marketplace entries, the moved-skill reference
rewrites, and the plugin-inclusive privacy/structure checks. Generic-skill
parameterization (hosts, paths, tool locations, accounts) and the product-companion
splits above remain separate slices; each adds the variables it reads to the registry
in its own change. No branch names or merge order are pinned here.

## Assumptions and Recommended Defaults

| # | Question | Auto-picked answer | Rationale |
|---|---|---|---|
| Q1 | Plugin folders or a single product section per skill? | Plugin folders (approach A) | The repository already ships a Claude Code marketplace, and the request names "plugin folders" |
| Q2 | How many plugins? | Three: worldarchitect, ai-universe, self-hosted-runners | Each audit cluster is a separate product or system. One plugin per product keeps installs opt-in |
| Q3 | Delete personal identifiers in plugins too? | Yes | The zero-PII invariant covers the whole repository, not just the default export |
| Q4 | Default for host aliases? | None: required, with a "not configured" failure | A default host is a machine assumption. Cross-machine placeholders (`mymac`, `mylinux`) stay as examples only |
| Q5 | Default for `~/projects`-style checkouts? | Derive from `git rev-parse --show-toplevel` or a required var; no `~/projects` default | A checkout location is a personal convention |
| Q6 | Keep the legacy personal-named DM-channel variable? | No. `SLACK_OPERATOR_DM_CHANNEL`, explicit, no fallback; users rename their own export | A fallback would ship the personal name in exported scripts, which zero-PII forbids |
| Q7 | Change the bash installer? | No; use native plugin install | Least risk; the installer has extensive tests |
| Q8 | Where do the design documents live? | `docs/superpowers/specs/` in this repository | The repository already keeps `/sq` documents in this folder |
| Q9 | One slice or several? | Several bounded slices, each independently reviewable | A single PR mixing layout, parameterization, and splits is unreviewable |
| Q10 | Use a wording-pin test to prevent regressions? | No; reuse the existing zero-PII scanners | The `AGENTS.md` testing policy forbids prose pins and prefers existing mechanical owners |
| Q11 | Move generic-named skills (testing-layers, smoke)? | Split later instead (generic stays, product goes to a companion) | They have profile and skill callers, and moving them would break the `prw` profile |
| Q12 | The AO CLI's published npm package name? | Keep it, with an `AO_NPM_PACKAGE` override | It is the tool's real published package name, not a personal assumption |
| Q13 | Conventional locations such as `$HOME/roadmap` or `$HOME/.hermes` as defaults? | Allowed only when probed for existence and skipped gracefully when absent | Matches existing `${ROADMAP_DIR:-$HOME/roadmap}` usage without breaking a fresh machine |
| Q14 | Derive `FIREBASE_PROJECT_ID` from `GCP_PROJECT_ID`? | No: required, never derived | Silent derivation can point a production write at the wrong project |
| Q15 | Literal personal tokens in shipped grep checks? | No; checks reference machine-local configuration, not shipped literals | The docs themselves are exported and fall under zero-PII |

## Error handling

- A skill run without a required variable prints the variable name, its meaning,
  and an example `export` line, then stops. It does not fall back to the author's
  values.
- A generic skill that looks for a product companion and finds none says so and
  continues with generic guidance only (the `user-story-worldai` pattern).
- A plugin command whose skill is missing from the installed plugin reports the missing
  skill and stops; it never reaches back into the default export for a copy.

## Testing

- Structural and privacy owners: `python3 -m pytest -q tests/test_plugin_folders.py
  tests/test_skill_export_no_personal_paths.py tests/test_skill_personal_identifiers.py`
- Installer and closure owners: `python3 -m pytest -q tests/test_installer.py
  tests/test_portable_install.py tests/test_command_closure.py
  tests/test_thin_command_dispatchers.py tests/test_cross_host_catalog.py`
- Plugin script harnesses, run from the repository root:
  `bash plugins/self-hosted-runners/skills/ezgha-watchdog/scripts/test_restart_gate.sh`,
  `bash plugins/self-hosted-runners/skills/runner-health/scripts/test_check_api.sh`,
  `bash plugins/self-hosted-runners/skills/runner-health/scripts/test_check_session_conflict.sh`,
  `bash plugins/self-hosted-runners/skills/runner-health/scripts/test_read_json_or_default.sh`,
  `python3 plugins/self-hosted-runners/skills/runner-health/scripts/test_parse_fields.py`.
- No shipped test pins Markdown wording. Tests that name a moved skill path get updated
  or deleted per the `AGENTS.md` policy.
