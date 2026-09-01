# Skill Usage Quantification System Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build and verify an empirical multi-runtime skill usage scanner that measures human-typed slash commands, agent model tool calls (`Skill` / `invoke_skill`), and subagent dispatches without substring noise.

**Architecture:** Extend `.claude/skills/command-research/scripts/count_command_usage_unified.py` into a unified `measure_skill_usage_unified.py` that extracts both human command invocations and agent `tool_calls` payloads across Claude Code JSONL, Hermes SQLite, Codex SQLite, and Antigravity transcript logs.

**Tech Stack:** Python 3.13, SQLite3, pytest, JSONL parsers

---

### Task 1: Write Unit Tests for Tool Call Extraction and Anti-Noise Filtering

**Files:**
- Create: `tests/test_skill_usage_measurement.py`

**Step 1: Write the failing test**

```python
import unittest
from pathlib import Path
from .claude.skills.command_research.scripts.measure_skill_usage_unified import (
    extract_human_invocations,
    extract_tool_call_invocations,
    filter_system_reminder_noise,
)

class SkillUsageMeasurementTest(unittest.TestCase):
    def test_system_reminder_noise_is_completely_rejected(self):
        noisy_reminder = """
        <skill_listing>
        - advice: fan out independent reviewers
        - 4layer: unit to end-to-end escalation
        - repro: isolate and reproduce defect
        </skill_listing>
        """
        hits = extract_human_invocations(noisy_reminder, {"advice", "4layer", "repro"})
        self.assertEqual(len(hits), 0)

    def test_structured_human_tag_is_extracted(self):
        content = "Please analyze this <command-name>/advice</command-name> on PR 373"
        hits = extract_human_invocations(content, {"advice"})
        self.assertEqual(hits, ["advice"])

    def test_assistant_tool_call_skill_is_extracted(self):
        tool_payload = {
            "name": "Skill",
            "input": {"skill": "4layer"}
        }
        hits = extract_tool_call_invocations([tool_payload], {"4layer"})
        self.assertEqual(hits, ["4layer"])
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_skill_usage_measurement.py`
Expected: FAIL (module `measure_skill_usage_unified` does not exist yet).

**Step 3: Write minimal implementation**

Create `.claude/skills/command-research/scripts/measure_skill_usage_unified.py` with parsing functions for human tags, prompt token starts, and structured assistant tool call arrays.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_skill_usage_measurement.py`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/test_skill_usage_measurement.py .claude/skills/command-research/scripts/measure_skill_usage_unified.py
git commit -m "feat: add skill usage parser unit tests [gemini][gemini-3.7-flash]"
```

---

### Task 2: Implement Multi-Store Scanner (Claude JSONL + Hermes SQLite + Codex SQLite)

**Files:**
- Modify: `.claude/skills/command-research/scripts/measure_skill_usage_unified.py`

**Step 1: Write the failing test**

```python
    def test_scan_aggregates_dual_channels(self):
        from .claude.skills.command_research.scripts.measure_skill_usage_unified import aggregate_metrics
        raw_events = [
            {"channel": "typed", "skill": "advice"},
            {"channel": "typed", "skill": "advice"},
            {"channel": "tool_call", "skill": "advice"},
            {"channel": "tool_call", "skill": "4layer"},
        ]
        result = aggregate_metrics(raw_events)
        self.assertEqual(result["advice"]["typed"], 2)
        self.assertEqual(result["advice"]["tool_call"], 1)
        self.assertEqual(result["4layer"]["tool_call"], 1)
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_skill_usage_measurement.py -k test_scan_aggregates_dual_channels`
Expected: FAIL

**Step 3: Write minimal implementation**

Implement `aggregate_metrics` and multi-store query extractors with indexed time cutoffs (`sessions.started_at >= ?` for Hermes; mtime filtering for Claude JSONLs).

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_skill_usage_measurement.py -k test_scan_aggregates_dual_channels`
Expected: PASS

**Step 5: Commit**

```bash
git add .claude/skills/command-research/scripts/measure_skill_usage_unified.py tests/test_skill_usage_measurement.py
git commit -m "feat: add multi-store dual-channel aggregation logic [gemini][gemini-3.7-flash]"
```

---

### Task 3: Add Scope-Aware Filtering and CLI Reporting

**Files:**
- Modify: `.claude/skills/command-research/scripts/measure_skill_usage_unified.py`
- Modify: `.claude/skills/command-research/SKILL.md`

**Step 1: Write the failing test**

```python
    def test_scope_filter_excludes_unregistered_global_commands(self):
        from .claude.skills.command_research.scripts.measure_skill_usage_unified import filter_by_repo_scope
        repo_skills = {"advice", "4layer", "redgreen"}
        global_hits = {"advice": 10, "unregistered_foo": 50}
        filtered = filter_by_repo_scope(global_hits, repo_skills)
        self.assertIn("advice", filtered)
        self.assertNotIn("unregistered_foo", filtered)
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_skill_usage_measurement.py -k test_scope_filter_excludes_unregistered_global_commands`
Expected: FAIL

**Step 3: Write minimal implementation**

Add `--repo-scope-only` flag and markdown/JSON output formatting to `measure_skill_usage_unified.py`. Update `.claude/skills/command-research/SKILL.md` documentation.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_skill_usage_measurement.py`
Expected: PASS (all tests pass).

**Step 5: Commit**

```bash
git add .claude/skills/command-research/scripts/measure_skill_usage_unified.py .claude/skills/command-research/SKILL.md tests/test_skill_usage_measurement.py
git commit -m "feat: add scope filtering and report formatting to skill usage scanner [gemini][gemini-3.7-flash]"
```

---

### Task 4: Full Suite Validation & Sync

**Files:**
- None (operational verification)

**Step 1: Run full pytest suite**

Run: `pytest`
Expected: 58+ tests pass with 0 errors.

**Step 2: Run sync installer**

Run: `bash install-claude-commands.sh --merge`
Expected: Exit code 0 with manifest validation passed.
