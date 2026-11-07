# Portable skills: plugin folders and environment variables (design)

Status: approved by `/sq` auto-pick (2026-11-04). Implementation authorized by the
live request ("make PRs to fix").

## Problem

`AGENTS.md` requires every exported skill to work for another developer on a
brand-new machine, in any repository. A four-way audit of `.claude/skills/`
(116 skills matched a portability grep) found that the export does not meet
that bar:

| Category | Count | Meaning |
|---|---|---|
| Product-only | 29 | The skill only makes sense inside one product: WorldArchitect.AI, AI Universe, or the author's self-hosted runner fleet |
| Parameterize | 81 | A generic skill that hardcodes a machine, checkout path, repository, Slack/GCP identifier, personal name, or product example |
| Clean | 6 | Matches were placeholders only |

The per-leak audit records (file, line, text, kind, proposed replacement) are
inputs to the implementation, not shipped artifacts.

Typical leaks:

- **Machine.** Host aliases such as `jeff-ubuntu`; `~/projects/<repo>` and
  `~/projects_other/...` checkouts; `/opt/homebrew`, `~/.local/bin/<tool>`,
  pinned nvm paths; macOS `~/Library/Logs` paths inside Linux units.
- **Account.** `--repo jleechanorg/worldarchitect.ai` defaults; Slack channel,
  user, and bot IDs; GCP project ids and numbers; Firebase UIDs and campaign
  IDs; personal names.
- **Product.** `mvp_site/`, `testing_mcp`, D&D level-up rules, and Firestore
  schemas embedded in generic testing, evidence, and harness skills.

## Goals

1. `.claude/skills/` (the default export and `--all` install) contains no
   product-only skills and no hardcoded machine, account, or product values.
2. Product-only skills stay available as opt-in Claude Code plugins in
   `plugins/<name>/`, installable through the existing marketplace.
3. Machine and account values come from one documented set of environment
   variables. Each has a safe default or fails with a "not configured" message.
4. The fresh-machine rule is stated in `AGENTS.md` and `CLAUDE.md`, and a
   mechanical ratchet test stops new product-token leaks in `.claude/skills/`.

## Non-goals

- Rewriting `.claude/skills_archive/`, `.beads/`, or `shared/comparison-decisions.json`
  history entries. These are archival and are not installed.
- Changing `install-claude-commands.sh`. Plugin skills install through Claude
  Code's native plugin system (see Decision D3).
- Changing what any skill does, beyond resolving its values at run time.

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
    README.md                         # purpose, install, required env vars
    skills/<skill>/SKILL.md (+ references/, scripts/)
    commands/<cmd>.md                 # only commands that point to moved skills
    scripts/                          # e.g. auth-worldai.mjs moved with worldai-auth
  ai-universe/                        # AI Universe MCP server skills
  self-hosted-runners/                # runner-fleet operations (parameterized)
```

- Each `plugin.json` has `name`, `description`, `version`, and `author`. The
  author is the repository's existing team identity, the same one the root
  plugin uses. Each also lists `skills`, plus `commands` when present.
- `.claude-plugin/marketplace.json` gets one `plugins[]` entry per folder, with
  `"source": "./plugins/<name>"`. Install with
  `/plugin marketplace add jleechanorg/jleechan-skills` and then
  `/plugin install <name>@jleechan-skills`.
- Plugin skills follow the same zero-PII rules as the main export. Real UIDs,
  campaign IDs, project numbers, and Slack IDs become placeholders or plugin
  variables (`FIREBASE_PROJECT_ID`, `GCP_PROJECT_ID`, `AI_UNIVERSE_MCP_URL`).
  Moving a skill to a plugin does not license keeping secrets or personal data.

**What moves.** A skill moves wholesale when its name and purpose are
product-only and it has no generic callers:

- **worldarchitect:** agents (renamed `worldai-agent-routing` so it no longer
  collides with `.claude/agents/`), bq-evidence-reading,
  character-creation-modal-exit, dice-roll-audit, field-ownership-contracts,
  firebase-prod-campaigns, generatetest, level-up-validation, levelup,
  local-dev-server, mobile-investigations, pr-preview-servers, repro-copy,
  repro-twin-clone-evidence, smoke-local, smoke-test-local,
  testing-infrastructure, user-story-worldai, worldai-auth,
  worldarchitect-codebase-sherpa, zfc-leveling-roadmap.
- **ai-universe:** ai-universe-auth, ai-universe-httpie,
  ai-universe-second-opinion-workflow, secondo-dependencies.
- **self-hosted-runners:** ezgha-watchdog, runner-health,
  self-hosted-runner-preflight, repo-and-infra-locations (rewritten as a
  template that reads machine-local configuration).

**What splits.** When a product-flavored skill has a generic name, generic
callers, or a place in an install profile, a generic skill stays behind and the
product content becomes a plugin companion named `worldai-<skill>`:

| Skill | Callers | Result |
|---|---|---|
| testing-layers | `prw` profile, pr-lifecycle, evidence-coverage | Generic version stays; product content goes to `worldai-testing-layers` |
| smoke | pr-babysit, `/smoke` command | Generic version stays; product content goes to `worldai-smoke` |
| harness-guardrails, evidence-review, evidence-standards, ui-video-evidence, llm-testing | Several generic callers | Each skill's product section moves to one `worldai-<skill>` companion |

**References.** Generic skills never link to plugin files by relative path,
because the plugin may not be installed. They name the companion by convention,
for example: "if a `worldai-*` or repo-local `user-story-*` skill is installed,
read it." Commands whose only target moved go with the skill into
`plugins/<name>/commands/`. Tests, `shared/install-profiles.json`, and
`shared/retain-local.json` entries that named a moved skill get updated in the
same change.

### D2. Environment variable registry

`docs/portability-env-vars.md` is the single registry. Rules:

1. Resolution order: an explicit env var, then a value derived from the current
   repository or tool, then the documented default. If none applies, fail with
   `<VAR> not configured: <what to set>`. Never guess a host, path, or
   repository.
2. Existing names win over new ones (`PROJECT_ROOT`, `REPO_ROOT`,
   `${CLAUDE_HOME:-$HOME/.claude}`, `ROADMAP_DIR`, `WIKI_ROOT`, `HERMES_HOME`,
   `DARK_FACTORY_HOME`, `AO_CONFIG_PATH`). Where the audits proposed duplicate
   names (`WIKI_DIR`, `WIKI_PATH`), the registry keeps one (`WIKI_ROOT`).
3. Tools resolve through `command -v <tool>`. A `*_BIN` override exists only
   where a script needs one.
4. Users set their values in their shell profile or in the optional sourced file
   `${XDG_CONFIG_HOME:-$HOME/.config}/jleechan-skills/env`. Skills never write
   that file.
5. Removed personal names and identifiers are not replaced with variables. They
   are deleted, or become generic wording such as "the operator" or
   `<campaign-id>`.

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
- **Plugin structure test** (`tests/test_plugin_folders.py`). Every marketplace
  source exists. Every `plugins/*/.claude-plugin/plugin.json` parses and its
  name matches the folder. Every plugin skill has frontmatter whose `name`
  matches its folder. No name exists in both `.claude/skills/` and a plugin.
- **Product-token ratchet** (`tests/test_product_token_ratchet.py`). This scans
  `.claude/skills/**` for `worldarchitect|worldai|mvp_site|your-project\.com|testing_mcp`.
  Any file that matches must appear in `tests/fixtures/product_token_allowlist.txt`,
  which is generated once from the post-move tree. Files may drop off the list;
  new files fail. This follows the zero-PII scan category that `AGENTS.md`
  permits, and it pins no prose.

### D5. Delivery as PRs

| PR | Branch | Base | Scope |
|---|---|---|---|
| 1 | `claude/elegant-einstein-gfcch1` | main | AGENTS.md/CLAUDE.md invariant, this spec, the plan, the env-var registry |
| 2 | `claude/elegant-einstein-gfcch1-plugins` | PR 1 | D1 moves, manifests, references, plugin and ratchet tests |
| 3 | `claude/elegant-einstein-gfcch1-env-machine` | PR 1 | Hosts, paths, tool locations, personal state directories |
| 4 | `claude/elegant-einstein-gfcch1-env-accounts` | PR 1 | GitHub repo and org, Slack, AO, bot logins, personal names, credential blocklist |
| 5 | `claude/elegant-einstein-gfcch1-product-examples` | PR 2 | D1 splits and product examples in generic skills |

PRs 3 and 4 touch disjoint skill sets. PR 2 edits only the reference lines that
name moved skills, so text merges with PRs 3, 4, and 5 resolve hunk by hunk.

## Assumptions and Recommended Defaults

| # | Question | Auto-picked answer | Rationale |
|---|---|---|---|
| Q1 | Plugin folders or a single product section per skill? | Plugin folders (approach A) | The repository already ships a Claude Code marketplace, and the request names "plugin folders" |
| Q2 | How many plugins? | Three: worldarchitect, ai-universe, self-hosted-runners | Each audit cluster is a separate product or system. One plugin per product keeps installs opt-in |
| Q3 | Delete personal identifiers in plugins too? | Yes | The zero-PII invariant covers the whole repository, not just the default export |
| Q4 | Default for host aliases? | None: required, with a "not configured" failure | A default host is a machine assumption. The existing cross-machine-ssh-tier placeholders (`mymac`, `mylinux`) stay as examples only |
| Q5 | Default for `~/projects`-style checkouts? | Derive from `git rev-parse --show-toplevel` or a required var; no `~/projects` default | A checkout location is a personal convention |
| Q6 | Keep `JLEECHAN_DM_CHANNEL`? | Rename to `SLACK_OPERATOR_DM_CHANNEL`; scripts read the old name as a deprecated fallback for one release | Avoids breaking the author's live setup while removing the personal name from docs |
| Q7 | Change the bash installer? | No; use native plugin install | Least risk; the installer has extensive tests |
| Q8 | Where do the design documents live? | `docs/superpowers/{specs,plans}/` in this repository | `~/roadmap` does not exist in this ephemeral container. The repository already keeps `/sq` documents in this folder |
| Q9 | Use one PR or several? | Five, as in D5 | The request says "PRs". Splitting by concern keeps each PR reviewable |
| Q10 | Use a wording-pin test to prevent regressions? | No; a token ratchet over files instead | The AGENTS.md testing policy allows portability scans and forbids prose pins |
| Q11 | Move generic-named skills (testing-layers, smoke)? | Split instead (generic stays, product goes to a companion) | They have profile and skill callers, and moving them would break the `prw` profile |
| Q12 | `@jleechanorg/ao-cli` npm package name? | Keep it | It is the tool's real published package name, not a personal assumption. An `AO_NPM_PACKAGE` override is allowed |

## Error handling

- A skill run without a required variable prints the variable name, its meaning,
  and an example `export` line, then stops. It does not fall back to the author's
  values.
- A generic skill that looks for a product companion and finds none says so and
  continues with generic guidance only (the `user-story-worldai` pattern).

## Testing

- The plugin structure test and the product-token ratchet (D4).
- The existing suites that must stay green, or differ from the base only by
  their pre-existing failures: `test_skill_export_no_personal_paths.py`,
  `test_skill_personal_identifiers.py`, the `test_skill_portability_*` tests,
  `test_installer.py`, and `test_cross_host_catalog.py`.
- Tests that name a moved or renamed skill path, or a removed personal default,
  get updated or deleted per the AGENTS.md policy. Two examples:
  `test_luna_report_containment.py` (the luna scratch folder name), and
  `test_skill_portability_batch*` entries for skills that moved.
- Three suite failures already exist in this container (two
  `test_code_review_export` Hermes import tests and one `md_files` bootstrap
  backup test). They are environmental and stay out of scope.

## Implementation Preconditions

- Pushing branches other than `claude/elegant-einstein-gfcch1` relies on the
  request for multiple PRs. If a push to a suffixed branch is refused, that PR's
  commits stack onto the designated branch instead, and the PR body lists the
  combined scope.
