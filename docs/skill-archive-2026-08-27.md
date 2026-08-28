# Skill and command archive report — 2026-08-27

PR [#376](https://github.com/jleechanorg/jleechan-skills/pull/376) moves 110 recoverable skill packages and 7 command packages outside their discovery roots. A follow-up pass also relocates the repository's pre-existing nested archives and removes stale home-only discovery entries.

## What changes

- Skills move from `.claude/skills/` to `.claude/skills_archive/2026-08-27-historical-zero-use/`.
- Commands move from `.claude/commands/extended-library/` to `.claude/commands_archive/2026-08-27-historical-zero-use/`.
- The installer copies only `.claude/skills/` and `.claude/commands/`, so sibling archive directories are neither installed nor discovered.
- During routine `--merge`, same-named active packages are preserved and reported because they may be user-authored. Explicit `--merge --migrate-archives` moves reviewed collisions into matching sibling archives under the target Claude home.
- Existing archive destinations are never overwritten; a collision fails closed.
- Every move is recoverable. No skill or command body is deleted.

After dependency corrections, the repository contains 219 active skill packages, 110 archived skill packages in this tranche, and 7 archived command packages.

## Skill selection rule

A skill was archived only when all of these checks passed:

1. No structured Claude `Skill` tool call was observed during the 30-day window from 2026-07-28 through 2026-08-27.
2. No retained active skill requires it as a workflow dependency.
3. No active repository or home slash command references it.
4. No repository or global operating contract references it.
5. No current repository test contract requires it to remain active. The retired
   `design-doc-backup-worldarchitect` entry was explicitly removed from the Batch 1
   portability tuple, whose contract now accurately identifies its eight retained
   conversion fixtures.

Raw text mentions were not counted as usage because catalogues, documentation, file extensions, and system reminders repeat package names without invoking them. This is an evidence-based inactivity estimate, not proof that a workflow was never useful. Codex and Hermes do not expose the same structured Claude `Skill` event, so dependency, command, and contract references are additional safety gates.

## Command selection rule

The command tranche comes from the existing authenticated 30-day command audit. A command moved only when it had zero authenticated invocation and no active command caller.

Seven zero-use candidates were retained because callers still exist:

- `efficiency`, invoked by `pr-quantity-control` and `pr-efficiency-audit`.
- `engplan`, exposed by the active `engplan` skill.
- `evidence-coverage`, exposed by the active `evidence-coverage` skill.
- `gene`, called by Genesis/composition commands.
- `header`, called by status and list commands.
- `investigatedice`, called by `idice`.
- `repro_copy`, called by `repro`.

Archiving `loop_level_zfc` removed the only live caller of the zero-use `loop-level-zfc` skill, so that skill moved into the skill archive in the same change.

## Real home state

Repository changes do not automatically modify `~/.claude/`. The real home was synchronized explicitly:

- 11 of the final repository-archived skills were still active in `~/.claude/skills/`; they moved to `~/.claude/skills_archive/2026-08-27-historical-zero-use/`.
- The other 99 final repository-archived skills were already absent from the active home catalogue.
- Five packages found to be required by retained active skills were restored to both repository and real home.
- Zero names from the final skill archive remain active in `~/.claude/skills/`.
- 10 real-home command copies representing the 7 archived commands remain in `~/.claude/commands_archive/2026-08-27-historical-zero-use/`. Three commands have both top-level and extended-library copies.

Future `--merge` installs report these collisions without moving them. After
review, `--merge --migrate-archives` performs the migration. Clean and backup
installs never copy sibling archive roots.

## Follow-up discovery cleanup

The second pass closes two gaps that remained after PR #376:

- Three legacy archive containers under `.claude/skills/` moved to
  `.claude/skills_archive/legacy-pre-2026-08-27/`. They contain 52 historical
  `SKILL.md` packages and 474 total files. No `_archive` or `_archived_*`
  container remains under the active repository skill root.
- Five broken `~/.agents/skills` pointers were repaired. The referenced
  canonicals for `streaming-evidence-standards`, `design`, `ao-spawn-gate`,
  `bead-followup-templates`, and `reviewer-calibration` now live in
  `~/.claude/skills`; the stale `reviewer-calibration` worktree pointer remains
  recoverable in the dated Agents archive.

The post-cleanup home catalogue is directly reconstructible as 166 unique
packages: 138 active plus the 28 packages in the dated closure archive. A scan
of structured Claude `Skill` tool calls from 2026-07-28T00:00:00Z through
2026-08-28T00:00:00Z observes 74 of those names and no invocation of any of the
28 archived names. Zero observed use alone was not enough to archive a package:
active command, global-contract, repository-test, and transitive skill
dependencies were also retained. The 28 home-only packages that cleared every
gate moved recoverably to each runtime's
`skills_archive/2026-08-27-zero-use-closure/` directory:

`ask-matt`, `batch-grill-me`, `claude-handoff`, `cmux-browser`,
`copilot-pr-processing`, `edit-article`, `gh-address-comments`, `gh-fix-ci`,
`git-guardrails-claude-code`, `grill-me`, `grill-with-docs`, `loop-me`,
`migrate-to-shoehorn`, `obsidian-vault`,
`pr-green-definition.bak-20260729`, `request-refactor-plan`,
`scaffold-exercises`, `setup-org-runners`, `setup-pre-commit`,
`setup-ts-deep-modules`, `teach`, `to-questionnaire`, `ubiquitous-language`,
`wayfinder`, `writing-beats`, `writing-fragments`, `writing-great-skills`, and
`writing-shape`.

The result is 138 valid unique home packages and zero broken top-level skill
symlinks across `~/.claude`, `~/.agents`, and `~/.codex`.

## Archived skill manifest

| Skill | What it does |
|---|---|
| `algorithmic-art` | Creating algorithmic art using p5.js with seeded randomness and interactive parameter exploration. Use this when users request creating art using code, generative art, algorithmic art, flow fields, or particle systems. Create original algorithmic art rather than copying existing artists' work to avoid copyright violations. |
| `ao-agent-shorthands` | Read ~/.hermes/agent-orchestrator.yaml BEFORE declaring an --agent <X> value unsupported. Lists plugin shorthands (wafer, minimax, agy). |
| `ao-parameter-fidelity` | Use whenever running an AO spawn. Honors exact --agent/--runtime/--project/--claim-pr; verifies session metadata; never silently substitutes a different worker. |
| `automation-completeness` | Use when adding automation scripts. Requires a caller (CI/cron/hook); watchdog scripts need launchd plist template + deploy.sh install step. |
| `automation-output-verification` | Use BEFORE running any automation loop. Requires stating the observable success output (PR, fixed test, push); rejects prediction-only loops. |
| `autonomous-execution` | Guidelines for autonomous execution in automation/orchestration contexts |
| `autor-bench-eloop` | Historical package. |
| `autor-n15-loop` | Historical package. |
| `bashrc-credential-guard` | Always check ~/.bashrc for credentials, API keys, passwords, and configuration values before asking user |
| `branch-upstream` | Use when creating a new branch or entering a worktree. Sets upstream immediately via `git branch --set-upstream-to=origin/<branch>` after first checkout. |
| `brand-guidelines` | Applies Anthropic's official brand colors and typography to any sort of artifact that may benefit from having Anthropic's look-and-feel. Use it when brand colors or style guidelines, visual formatting, or company design standards apply. |
| `browser-testing-ocr-validation` | Historical package. |
| `canvas-design` | Create beautiful visual art in .png and .pdf documents using design philosophy. You should use this skill when the user asks to create a poster, piece of art, design, or other static piece. Create original visual designs, never copying existing artists' work to avoid copyright violations. |
| `check-team-worldai-workstreams` | Historical package. |
| `chrome-localhost3000-usage` | Historical package. |
| `chrome-superpowers-reference` | Historical package. |
| `claude-api` | Build apps with the Claude API or Anthropic SDK. TRIGGER when: code imports `anthropic`/`@anthropic-ai/sdk`/`claude_agent_sdk`, or user asks to use Claude API, Anthropic SDKs, or Agent SDK. DO NOT TRIGGER when: code imports `openai`/other AI SDK, general programming, or ML/data-science tasks. |
| `claude-code-schema-validation` | Historical package. |
| `claude-code-settings-maintenance` | Historical package. |
| `cli-secrets` | Use when debugging unauthorized/fallback errors. Flags redacted placeholders (e.g. __OPENCLAW_REDACTED__) as invalid tokens; checks env overrides first. |
| `cmux-codex-autoapprove` | Run or maintain the cmux approval worker that scans cmux terminal surfaces for approval dialogs, classifies them with `codex exec`, and sends the matching approval key. Use when testing or operating the launchd-based auto-approver, debugging missed prompts, moving the worker, or tuning candidate detection and approval heuristics. |
| `cmux-socket-control` | Control cmux tabs, workspaces, and terminal panes via Unix socket. Use when reading terminal output, sending commands to another agent's pane, switching tabs, or monitoring coder progress. |
| `codex-evolve-loop` | Codex-native AO evolve loop. Run a deterministic local observe/measure cycle, then optionally delegate targeted fixes via /claw using the canonical evolve-loop skill. |
| `codex-symlinks` | Historical package. |
| `coverage-analysis` | Code coverage analysis using coverage.sh script and pytest-cov |
| `dark-factory.bak.1784359965` | Run the Dark Factory DOT pipeline runner against a goal. |
| `deletion-milestones` | Use for PRs scoped to deletion. Net production LOC must be ≤0; PR lifecycle time-boxed at 30 min; document, do not substitute, the deletion. |
| `design-doc-backup-worldarchitect` | /design - Product & Engineering Design Documentation |
| `design-retro-publishability-gate` | Final whole-docset publishability gate for design-retro / adversarial-doc swarm workflows. Use as the LAST stage of any design-retro, solutions-hardening, /innov, pr-retro, or code-quality-swarm run, after all writer/verifier lanes finish and before the PR description claims the docset is "ready" or "publishable". Catches cross-document contradictions, present-tense staleness vs current HEAD, leaked machine paths/tokens, unmarked superseded docs, false-green copyable commands, and git diff --check hygiene issues that per-finding adversarial review structurally cannot see. |
| `diagnose-lifecycle-worker` | Diagnose and fix AO lifecycle-worker backfill failures (stale worktrees, branch conflicts, claim_failed loops) |
| `doc-coauthoring` | Guide users through a structured workflow for co-authoring documentation. Use when user wants to write documentation, proposals, technical specs, decision docs, or similar structured content. This workflow helps users efficiently transfer context, refine content through iteration, and verify the doc works for readers. Trigger when user mentions writing docs, creating proposals, drafting specs, or similar documentation tasks. |
| `factory-spec.bak.1784359965` | Display the Dark Factory pipeline node graphs, gates, node types, edge conditions, and handler mappings. |
| `firebase-campaign-copy` | Copy production Firebase campaigns across users for testing with Admin SDK. |
| `fix-completion-deploy.pre-user-scope-20260727T035804Z` | Use when a persistent repository, tool, configuration, automation, launcher, wrapper, or installed CLI fix could remain only in a working tree, topic branch, or one machine's live state. |
| `gateway-upgrade` | Safe gateway upgrade/downgrade with pre-flight checks, rollback, and post-verification |
| `gcp-deployment` | Historical package. |
| `gcp-deployments` | Historical package. |
| `harness-fix-durability` | Use when /harness is invoked or fixing a harness rule violation. Matches fix durability to severity (nit=memory, wrong=CLAUDE.md, silent-sub=hook+commitment). |
| `hook-refire-shortcircuit` | Detailed procedures for hook re-fire short-circuit — sentinel files, CR incremental-mode detection, Branch A caps, stale review dismissal commands |
| `integrate-completion-protocol` | Use after every /integrate invocation. Mandates /learn before reporting done; integrate without learn is incomplete execution. |
| `internal-comms` | A set of resources to help me write all kinds of internal communications, using the formats that my company likes to use. Claude should use this skill whenever asked to write some sort of internal communications (status reports, leadership updates, 3P updates, company newsletters, FAQs, incident reports, project updates, etc.). |
| `launchd-auto-cleanup` | Create macOS launchd cleanup agents with dry-run verification. Writes cleanup script + plist installer, verifies with --dry-run, then installs and runs live. |
| `level-up-zfc` | DEPRECATED — Redirects to the consolidated ZFC leveling skill |
| `llm-json-schema-documentation` | Document both INPUT and OUTPUT JSON schemas for LLM-driven features to prevent data flow confusion |
| `local-agy-provider-detection` | Detect Gemini SDK / BYOK leaks when local AGY-default provider is expected. |
| `loop-level-zfc` | Use when supervising the level-up ZFC migration loop in this repo, especially when the cleanup-first roadmap is drifting, AO workers need steering, or PR sequencing must stay aligned with the canonical roadmap. |
| `mcp-gmail-agent` | MCP Gmail Agent - Email Automation and Processing with Model Context Protocol |
| `mcp-installation` | Use when adding/troubleshooting MCP servers. Installs to stable paths (npm -g, uvx, uv tool); updates ~/.config/mcp-daemon/start-mcp-daemons.sh for HTTP MCPs. |
| `metric-policy-wiring` | Use when adding/changing a metric (zero-touch, smoothness, etc.). Wires canonical doc, README, AGENTS.md, CLAUDE.md, monitor script in the same pass. |
| `minimax-401-diagnostic` | Diagnose and fix MiniMax 401 auth errors in AO workers — the root cause is always a redacted or invalid MINIMAX_API_KEY, not the model name. Use when workers stall at /login, show API Error 401, or when ao-XXXX shows "minimax" in its tmux pane but isn't making progress. |
| `minimax-cli-fix` | Historical package. |
| `modal-agent-pattern` | Historical package. |
| `mvp-site-app-dev-i6xf2p72ka-uc-a-run-app` | API skill for mvp-site-app-dev-i6xf2p72ka-uc.a.run.app. Use when: interacting with this site's APIs, automating workflows, debugging requests. Auth: Unknown — capture may reveal auth mechanism. |
| `mvp_site_app_dev_i6xf2p72ka_uc_a_run_app_root` | API skill for mvp-site-app-dev-i6xf2p72ka-uc.a.run.app. Use when: interacting with this site's APIs, automating workflows, debugging requests. Auth: Unknown — capture may reveal auth mechanism. |
| `normalization-atomicity` | Use when persisting rewards_box or any data structure to Firestore. ALL paths (streaming/polling/passthrough) must canonicalize before writing. |
| `openclaw-diagnostics` | Historical package. |
| `openclaw-models` | OpenClaw agent model configs — which work, which are broken/quota-limited, and how to switch |
| `optimization-baseline-fidelity` | Use BEFORE any cost/latency optimization. A/B control MUST be deployed prod config; gate code-start on stated $X/mo savings; reject forced-OFF controls. |
| `oracle-browser-usage` | Use Oracle CLI in browser mode (no API key) for context bundling and analysis |
| `pairv2-llm-driven-philosophy` | Historical package. |
| `playwright-mcp-manual-interaction` | Historical package. |
| `pr-automation-workflows` | Historical package. |
| `pr-body-design-doc` | Use for production-code PRs ($PROJECT_ROOT/**, gates, ZFC). Requires full GitHub URL to governing roadmap/design doc and a `br` bead ID in the body. |
| `runtime-mirror-sync` | RETIRED — self-hosted-oss/install.sh and its runtime mirror sync flow no longer exist. Historical reference only; see runner-health and ezgha-watchdog for the current mechanism. |
| `shadow-execution-gate` | Run a Shadow Execution Gate for high-risk changes using isolated replay, objective evidence, and promotion criteria |
| `skeptic-agent` | Define and run skeptic exit criteria for non-trivial tasks — independent verification agent with inverted incentive to find gaps |
| `skill-creator` | Create new skills, modify and improve existing skills, and measure skill performance. Use when users want to create a skill from scratch, edit, or optimize an existing skill, run evals to test a skill, benchmark skill performance with variance analysis, or optimize a skill's description for better triggering accuracy. |
| `slack-gif-creator` | Knowledge and utilities for creating animated GIFs optimized for Slack. Provides constraints, validation tools, and animation concepts. Use when users request animated GIFs for Slack like "make me a GIF of X doing Y for Slack." |
| `spec-design-docs` | Use when writing any spec, design doc, or implementation plan for a non-trivial feature — enforces the three-doc rule (no-code spec, design doc with interfaces, TDD impl plan) with adversarial review gates between stages. |
| `spec-intent-confirmation` | Use BEFORE infra specs (CI/runner routing/deploy config). Confirm key behavioral decisions explicitly; flag infeasible numeric targets as STOP. |
| `sprite-generation` | Historical package. |
| `sprite-quality-eval` | Historical package. |
| `superpowers-dispatching-parallel-agents` | Use when facing 2+ independent tasks that can be worked on without shared state or sequential dependencies |
| `superpowers-executing-plans` | Use when you have a written implementation plan to execute in a separate session with review checkpoints |
| `superpowers-finishing-a-development-branch` | Use when implementation is complete, all tests pass, and you need to decide how to integrate the work - guides completion of development work by presenting structured options for merge, PR, or cleanup |
| `superpowers-receiving-code-review` | Use when receiving code review feedback, before implementing suggestions, especially if feedback seems unclear or technically questionable - requires technical rigor and verification, not performative agreement or blind implementation |
| `superpowers-requesting-code-review` | Use when completing tasks, implementing major features, or before merging to verify work meets requirements |
| `superpowers-subagent-driven-development` | Use when executing implementation plans with independent tasks in the current session |
| `superpowers-systematic-debugging` | Use when encountering any bug, test failure, or unexpected behavior, before proposing fixes |
| `superpowers-test-driven-development` | Use when implementing any feature or bugfix, before writing implementation code |
| `superpowers-using-superpowers` | Use when starting any conversation - establishes how to find and use skills, requiring Skill tool invocation before ANY response including clarifying questions |
| `superpowers-writing-skills` | Use when creating new skills, editing existing skills, or verifying skills work before deployment |
| `symphony-daemon` | Set up and use the Symphony launchd daemon in repositories that include orchestration/symphony_overlay/daemon. |
| `technique-router` | Classifies GitHub issues/PRs into PR-type categories and recommends autor techniques. Used by packages/core/src/decomposer.ts. |
| `tessl__dispatching-parallel-agents` | Use when facing 2+ independent tasks that can be worked on without shared state or sequential dependencies |
| `tessl__executing-plans` | Use when you have a written implementation plan to execute in a separate session with review checkpoints |
| `tessl__interface-contract-verifier` | Verify that interface and class contracts (preconditions, postconditions, invariants) are preserved across program versions. Use when validating refactorings, checking API compatibility, verifying design-by-contract implementations, or ensuring behavioral contracts remain intact after code changes. Automatically detects contract violations, identifies affected methods and classes, and provides actionable guidance for resolving violations while maintaining program correctness. |
| `tessl__requesting-code-review` | Use when completing tasks, implementing major features, or before merging to verify work meets requirements |
| `tessl__subagent-driven-development` | Use when executing implementation plans with independent tasks in the current session |
| `tessl__systematic-debugging` | Use when encountering any bug, test failure, or unexpected behavior, before proposing fixes |
| `tessl__verification-before-completion` | Use when about to claim work is complete, fixed, or passing, before committing or creating PRs - requires running verification commands and confirming output before making any success claims; evidence before assertions always |
| `tessl__verify` | Self-check your own completed change before independent review — the pre-review sanity pass. Use when you want to check your work, run checks, validate changes, make sure a change is ready, test it end-to-end, run repo guardrails (lint, typecheck, tests, build), exercise the real surface with evidence, and catch obvious self-correctable issues. Produces a `ready for review` / `needs more work` / `blocked` verdict — never a ship decision. Do not use when the repo cannot be booted or exercised reliably, or when auditing someone else's diff, branch, or PR. |
| `tessl__writing-plans` | Use when you have a spec or requirements for a multi-step task, before touching code |
| `tessl__writing-skills` | Use when creating new skills, editing existing skills, or verifying skills work before deployment |
| `test-api-keys-ai-universe` | Test API keys against jleechanorg/ai_universe repository services |
| `test-tui-claude-feature-via-cmux` | When asked to verify whether a Claude Code feature works (especially slash commands, dialogs, pickers, status indicators), spawn a real interactive TUI session in cmux — never use `claude --print "/feature"` as a test, because --print is non-interactive and will always return "isn't available in this environment" regardless of whether the feature actually works. |
| `theme-factory` | Toolkit for styling artifacts with a theme. These artifacts can be slides, docs, reportings, HTML landing pages, etc. There are 10 pre-set themes with colors/fonts that you can apply to any artifact that has been creating, or can generate a new theme on-the-fly. |
| `thinclaw` | Use thinclaw MCP server — thin inference-less bridge to OpenClaw Gateway for executing tools |
| `unified-logging` | Historical package. |
| `validation-gate` | Pre-report gate — verifies all planned evidence artifacts exist before writing comparison/validation reports |
| `verify-secrets-backup` | Historical package. |
| `video-edit-letterbox-caption` | Historical package. |
| `video-frame-review` | Historical package. |
| `web-artifacts-builder` | Suite of tools for creating elaborate, multi-component claude.ai HTML artifacts using modern frontend web technologies (React, Tailwind CSS, shadcn/ui). Use for complex artifacts requiring state management, routing, or shadcn/ui components - not for simple single-file HTML/JSX artifacts. |
| `wiki-integrity` | Use BEFORE writing wiki/sources, wiki/entities, or wiki/concepts. Routes through /wiki-ingest; bulk generation must also create entity+concept pages. |
| `worldai-browser-login` | Browser-based login to WorldAI via Firebase Google OAuth using Chrome Superpowers MCP |
| `worldai-tools-mcp-proxy-testing` | Historical package. |
| `worldarchitect-local-debugging` | Historical package. |
| `xlsx` | Use this skill any time a spreadsheet file is the primary input or output. This means any task where the user wants to: open, read, edit, or fix an existing .xlsx, .xlsm, .csv, or .tsv file (e.g., adding columns, computing formulas, formatting, charting, cleaning messy data); create a new spreadsheet from scratch or from other data sources; or convert between tabular file formats. Trigger especially when the user references a spreadsheet file by name or path — even casually (like "the xlsx in my downloads") — and wants something done to it or produced from it. Also trigger for cleaning or restructuring messy tabular data files (malformed rows, misplaced headers, junk data) into proper spreadsheets. The deliverable must be a spreadsheet file. Do NOT trigger when the primary deliverable is a Word document, HTML report, standalone Python script, database pipeline, or Google Sheets API integration, even if tabular data is involved. |
| `zero-touch-metrics` | Historical package. |

## Archived command manifest

| Command | What it does |
|---|---|
| `benchg-ts` | /benchg-ts - TypeScript Migration Benchmark: Genesis vs Ralph (your-project.com only — hardcoded to worldai_genesis2 / worldai_ralph2 target paths under worktree_ralph/) |
| `feature-dev` | Guided feature development with systematic codebase understanding and architecture focus (your-project.com only — defaults to $PROJECT_ROOT/ layouts and Flask/Firebase/Gemini patterns) |
| `loop_level_zfc` | Run the task-specific level-up ZFC evolve loop for this repo |
| `mobile` | /mobile - run the mobile-browser investigation workflow |
| `wakebugbot` | Deterministically trigger a Bugbot CI run for its optional advisory feedback. |
| `worldai-usage-email` | Send daily/weekly Your Project usage report email to $USER@gmail.com (worldai-only — requires your-project.com worktree + scripts/daily_campaign_report.py) |
| `zfc-adjuster` | ZFC adjuster proof review — verify backend adjustments have root-cause-first proof and minimal state-aware scope |

## Important retained skill exceptions

Fifty skills initially caught by the usage filter were restored after command, global-contract, repository-test, and all-active-skill dependency audits. Examples include:

- `agent-orchestrator` and AO operator/session/spawn skills required by `/ao`, `/claw`, and global policy.
- `claude-code-computer-use`, `babysit-openclaw`, `pair-benchmark-all-executors`, `pr-quantity-control`, and `user-story-worldai`, required by retained active skills.
- `agento-report`, `repro-evidence`, `pr-babysit`, `mcp-agent-mail`, and other slash-command targets.
- `superpowers-quick`, `command-research`, and portability-test members protected by repository contracts.
- `pptx`, `write-goal`, `wiki-bfs`, and other packages with active command pointers.

## Restore a package

Repository skill:

```bash
git mv .claude/skills_archive/2026-08-27-historical-zero-use/<name> .claude/skills/<name>
```

Legacy repository package:

```bash
git mv .claude/skills_archive/legacy-pre-2026-08-27/packages/<name> .claude/skills/<name>
```

Repository command:

```bash
git mv .claude/commands_archive/2026-08-27-historical-zero-use/<name>.md .claude/commands/extended-library/<name>.md
```

Home skill or command:

```bash
mv ~/.claude/skills_archive/2026-08-27-historical-zero-use/<name> ~/.claude/skills/<name>
mv ~/.claude/commands_archive/2026-08-27-historical-zero-use/extended-library/<name>.md ~/.claude/commands/extended-library/<name>.md
```

Start a fresh client session after restoration so discovery is recomputed.

## Verification

```bash
python3 -m unittest discover -s tests -p 'test_*.py'
bash -n install-claude-commands.sh
git diff --check
```

The installer fixture proves that sibling archive roots are omitted on clean installs, stale active packages migrate during `--merge`, and existing archive targets fail closed instead of being overwritten.
