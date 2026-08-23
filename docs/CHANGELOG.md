# Changelog

Full version history for [jleechan-skills](https://github.com/jleechanorg/jleechan-skills) (formerly `claude-commands`). Moved out of `README.md` 2026-08-23 to keep the README focused on current state.

## v1.8.0 (2026-08-23)
- **Command consolidation**: archived 51 commands to `archive/commands/` (see [archive/README.md](../archive/README.md)) — files selected by empirically measuring invocations across Hermes, Claude Code, and Codex session logs (`/command-research`), then keeping any command with either measured usage or a live reference from a command that stays active (fixed-point dependency closure, not a single-pass check).
- New command: `command-research.md` — dispatcher for the usage-mining skill and its bundled scanner (`count_command_usage_unified.py`).
- Removed stale duplicate `.claude/skills/evidence-review.md` (superseded by `evidence-review/SKILL.md`) and fixed two dangling references to it.
- Root-cause fixed a secret-redaction regex bug in `exportcommands.sh` (unanchored `sk-` pattern was corrupting words like `disk-`/`task-`/`risk-` mid-word) and restored 244 of 324 corrupted locations via per-file git-history verification (PR [#358](https://github.com/jleechanorg/jleechan-skills/pull/358), PR [#359](https://github.com/jleechanorg/jleechan-skills/pull/359)).
- Repo renamed `jleechanorg/claude-commands` → `jleechanorg/jleechan-skills`.
- Active command count: 239 (was 290).

## v1.7.0 (2026-07-07)
- New commands: bashrc.md, callpath.md, crash.md, mac.md, meta.md, repro_developer.md, soak.md, social.md
- New hooks: warn-default-branch-bypass.sh
- New scripts: check_autonomy_time_box.sh
- New skills: agent-orchestrator/, aside-browser-default/, auto-factory/, bashrc.md, browserclaw/, callpath/, codex-evolve-loop/, crash.md, fetch-x-tweet.md
- Updated: automation-publish.md, automation.md, browser.md, exportcommands.md, f.md, playwright.md, automation-audit skill, self-hosted-runner-preflight skill, test-tui-claude-feature-via-cmux skill, test_install_native_scheduler.sh
- Removed: exportcommands.py (2361 lines, legacy export script superseded by exportcommands.md/.sh)

## v1.6.0 (2026-06-21)
- New commands: aar.md, accept-adapt-reject.md, beads.md, bq.md, code-quality.md, cq.md, disk_magician.md, diskm.md, er-node.md, f-pr.md, fable.md, factory-evolve.md, hermes.md, keychain_kill.md, launchd.md, linux.md, llm-testing.md, slack-audit.md, spicy_remove.md
- New hooks: auto-trust-workspace.sh
- Updated: 4layer.md, code-standards.md, commentreply.py, er.md, es.md, evidence_review.md, green.md, integrate.md, testing-layers.md, zfc.md, enforce-gh-account-agentf.sh, evidence-reviewer.md, and many more
- Skills expansions: auton, babysit, claw-dispatch, code-standards, disk-audit, evidence-standards, gcp-deployment, harness-engineering, learn, mem0, memory-search, testing-layers, wiki-ingest, zfc-leveling-roadmap
- Workflow updates: coverage.yml, deploy-dev.yml, design-doc-gate.yml, green-gate.yml, mcp-smoke-tests.yml, pr-preview.yml, presubmit.yml, skeptic-self-verify.yml, styleguide-compliance-gate.yml, test.yml, and more
- Major evidence-standards skill consolidation (large net reduction)

## v1.5.0 (2026-06-01)
- New commands: disk-audit.md, f.md, factory-spec.md, fs.md, gmail.md, history_resume.md, think-level-up-validation.md, wiki-assess.md, wiki-bfs.md, wiki-ingest.md, zfc-adjuster.md, team-claude.md
- New agents: anti-gravity-pair-coder.md, anti-gravity-pair-verifier.md
- New hooks: enforce-claudeaf-agentf.sh, enforce-gh-account-agentf.sh, enforce-gitidentity-agentf.sh
- New skills: adjustment-proof/, disk-audit/, domain-lock-standards.md, factory-spec/
- Updated: copilot.md, factory.md, wiki-evolve.md, wiki-search.md, zfclevel.md, ao.md, code-standards.md, 4layer.md, base.py, mem0_config.py, pre-commit-git-identity.sh, green-gate.yml, test.yml, daily-campaign-report.yml, and many more
- Skills expansions: claw-dispatch, code-standards, dark-factory, evidence-standards, history-search, mem0, pr-green-definition, repro-twin-clone-evidence, wiki-assess, wiki-bfs, wiki-ingest, wiki-search, zero-framework-cognition

## v1.4.0 (2026-05-22)
- New commands: archreview.md, cmux-backup.md, cmux-restore.md, code-standards.md, cs.md, end2end-testing.md, factory.md, goal_harness.md, h.md, thermo.md, thermo-nuclear-code-quality-review.md
- New agents: opencode-pair-coder.md, opencode-pair-verifier.md, openw-pair-coder.md, openw-pair-verifier.md, thermo-nuclear-code-quality-review.md
- New scripts: cmux-backup.sh, cmux-restore.sh
- New skills: ao-model-override/, cmux-backup/, code-standards/
- Updated: exportcommands.md, localexportcommands.md, history.md, copilot.md, evidence_review.md, green-gate.yml, skeptic-self-verify.yml, and many more
- Skills expansions: claw-dispatch, cmux-socket-control, evidence-standards, nextsteps, root-cause-first, skillify, zero-framework-cognition

## v1.3.0 (2026-04-24)
- New commands: ao.md, browserclaw.md, cmux-steer.md, es.md, green.md, loop_level_zfc.md, memory_search.md, ms.md, repro.md, repro_copy.md, wiki-evolve.md, wiki-search.md
- New hooks: allow-claude-dir.sh, autoapprove.py, block-merge.sh, openclaw-config-guard.sh, pre-commit-detached-guard.sh
- New skills: 4layer.md
- Updated: execute.md, copilot.md, claw.md, exportcommands.sh, git-header.sh, command_output_trimmer.py, skeptic-cron.yml
- Removed: ralph.md, localexportcommands.md, compose-commands.sh
- ZFC compliance updates across multiple files

## v1.2.0 (2026-04-05)
- ZFC compliance fixes across claw.md, auton.md, base.py, exportcommands.sh
- CLAUDE.md ZFC global rule added
- exportcommands.sh: README neutral-dir fix, `--tools ""` flag, corrupt-detection guard

## v1.1.0 (2025-12-30)
- **Export Statistics**: 244 Commands, 52 Hooks, 22 Scripts, 89 Skills
- Script allowlist expansion (12 additional development scripts)
- Enhanced export utility with broader infrastructure coverage
- Improved documentation for cross-project usage

## v1.0.9 (2025-12-19)
- 194 Commands, 43 Hooks, 19 Scripts, 28 Skills
- Development workflow tools integration
- Improved script categorization

## v1.0.8 (2025-12-16)
- 194 Commands, 43 Hooks, 19 Scripts, 25 Skills
- Enhanced automation patterns
- Documentation improvements

## v1.0.7 (2025-12-11)
- 194 Commands, 43 Hooks, 19 Scripts, 24 Skills
- Infrastructure deployment enhancements
- Cross-project compatibility improvements

## v1.0.6 (2025-11-22)
- 191 Commands, 43 Hooks, 19 Scripts, 20 Skills
- Testing framework enhancements
- Command composition improvements

## v1.0.5 (2025-11-15)
- 186 Commands, 41 Hooks, 19 Scripts, 14 Skills
- Multi-agent orchestration improvements
- Performance optimizations
