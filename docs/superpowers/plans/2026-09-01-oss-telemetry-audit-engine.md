# Implementation Plan: Next-Generation OSS Telemetry & Graph Analyzer

**Date**: 2026-09-01  
**Spec**: `docs/superpowers/specs/2026-09-01-oss-telemetry-audit-engine-design.md`

---

## Phase 1: Archival of Superseded Legacy Packages (Completed)
- [x] Create `.claude/skills_archive/2026-09-01-superseded-legacy/`
- [x] `git mv` 8 superseded packages:
  - `build-test-lint-autopilot`
  - `dice-authenticity-standards`
  - `dice-real-mode-tests`
  - `worldai-mcp-server-usage`
  - `babysit-openclaw`
  - `agento-report`
  - `pairv2-usage`
  - `pair-benchmark-all-executors`
- [x] Add documentation `README.md` with recoverability instructions.

---

## Phase 2: High-Performance Ingestion Engine
- [ ] Add `DuckDB` accelerated query path in `scripts/capture_command_skill_usage.py` for vectorized scanning of `~/.claude/history.jsonl` and `~/.claude/projects/`.
- [ ] Implement fallback to standard streaming JSON reader when `duckdb` is not installed.
- [ ] Add embedded conversational slash token extraction (`(?<![\w/])/([a-zA-Z0-9_-]+)(?![\w/])`) across all human message bodies.

---

## Phase 3: AST-Based Markdown Reference Extraction
- [ ] Implement CommonMark AST visitor in `scripts/audit_command_skill_usage.py` using `markdown-it-py` (with fallback to verified regex tokenizers).
- [ ] Extract structured nodes:
  - Frontmatter `aliases: [...]` and `alias: "..."`
  - Inline code references: `` `~/.claude/skills/<name>/SKILL.md` ``
  - Command invocations in prose: `/<command>`
  - Exclude fenced code block examples and multi-slash path strings.

---

## Phase 4: Graph Closure & Multi-Tier Reporting
- [ ] Run 3-Step BFS Transitive Closure from observed telemetry seeds.
- [ ] Emit structured JSON manifests (`strict-claude-command-usage-30d.json`, `skill-usage-30d.json`) and CSV summaries.
- [ ] Enforce invariant `archive_eligible_from_usage_alone: False`.

---

## Phase 5: Verification & Automated Tests
- [ ] Run `PYTHONPATH=. pytest tests/test_command_skill_usage_audit.py`.
- [ ] Run full test suite `PYTHONPATH=. pytest`.
- [ ] Verify clean linter passes: `ruff check scripts/ tests/`.
