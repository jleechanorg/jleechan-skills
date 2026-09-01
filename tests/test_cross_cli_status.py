"""Unit tests for the cross-cli Stop hook.

These tests exercise every CLI branch, defensive parsing, locking, and
fail-closed behaviors without requiring live CLIs or external dependencies.
"""
from __future__ import annotations

import concurrent.futures
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
HOOK = REPO_ROOT / ".claude" / "hooks" / "cross_cli_status.py"

# Dynamically import hook module for direct unit testing of internal helpers
spec = importlib.util.spec_from_file_location("cross_cli_status", str(HOOK))
assert spec and spec.loader
cross_cli_status = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cross_cli_status)

CLAUDE_LIVE_PAYLOAD = {
    "cwd": "/tmp/test-project",
    "session_id": "c726962e-3185-4681-aec2-313689a33360",
    "transcript_path": "/tmp/claude-projects/c7269/transcript.jsonl",
    "prompt_id": "550e8400-e29b-41d4-a716-446655440000",
    "last_assistant_message": "ping",
    "stop_hook_active": False,
    "session_crons": [],
    "effort": {"level": "medium"},
    "background_tasks": [],
    "permission_mode": "bypassPermissions",
    "hook_event_name": "Stop",
}

CODEX_LIVE_PAYLOAD = {
    "cwd": "/tmp/test-project",
    "hook_event_name": "stop",
    "last_assistant_message": "pong",
    "model": "gpt-5.6-sol",
    "permission_mode": "bypassPermissions",
    "session_id": "019fb560-de6b-7320-a070-5642753ded3d",
    "stop_hook_active": False,
    "transcript_path": "/tmp/codex-archived_sessions/transcript.jsonl",
    "turn_id": "019fb560-de6b-7320-a070-5642753ded3d",
}

CLAUDE_FIXTURE = {
    "cwd": "/tmp/test-project",
    "session_id": "abc123",
    "session_name": "ratelimit-hook",
    "transcript_path": "/tmp/claude-projects/abc/transcript.jsonl",
    "model": {"id": "claude-opus-5", "display_name": "Opus"},
    "workspace": {"current_dir": "/tmp/test-project"},
    "version": "2.1.220",
    "output_style": {"name": "default"},
    "cost": {
        "total_cost_usd": 0.01234,
        "total_duration_ms": 45000,
        "total_api_duration_ms": 2300,
        "total_lines_added": 156,
        "total_lines_removed": 23,
    },
    "context_window": {
        "total_input_tokens": 15500,
        "total_output_tokens": 1200,
        "context_window_size": 200000,
        "used_percentage": 8,
        "remaining_percentage": 92,
        "current_usage": {
            "input_tokens": 8500,
            "output_tokens": 410,
            "cache_creation_input_tokens": 0,
            "cache_read_input_tokens": 0,
        },
    },
    "rate_limits": {
        "five_hour": {"used_percentage": 12, "resets_at": 1785398400},
        "seven_day": {"used_percentage": 4, "resets_at": 1785916800},
    },
}

CODEX_FIXTURE = {
    "cwd": "/tmp/test-project",
    "model": {"display_name": "gpt-5-codex", "id": "gpt-5-codex"},
    "usage": {
        "input_tokens": 1234,
        "output_tokens": 567,
        "cost_usd": 0.0042,
    },
    "rate_limits": {"block_reset_seconds": 1785398400, "reset_seconds": 1785398400},
    "session_id": "codex-thread-xyz",
}

AGY_FIXTURE = {
    "cwd": "/tmp/test-project",
    "model": "claude-sonnet-4",
    "usage": {
        "input_tokens": 9000,
        "output_tokens": 800,
        "cost_usd": 0.05,
    },
    "rate_limits": {"block_reset_seconds": 1785398400},
    "session_id": "agy-abc",
}

CURSOR_FIXTURE = {
    "conversation_id": "conv-abc",
    "generation_id": "gen-xyz",
    "model": "claude-4.5-sonnet",
    "model_id": "claude-4-5-sonnet-20250929",
    "status": "completed",
    "loop_count": 0,
}

CURSOR_LOOP_STORM = {
    "conversation_id": "conv-loop",
    "generation_id": "gen-loop",
    "model": "claude-4.5-sonnet",
    "status": "error",
    "loop_count": 6,
}

ANTIGRAVITY_FIXTURE = {
    "cwd": "/tmp/test-project",
    "session_id": "ag-session",
    "model": "gemini-2.5-pro",
    "decision": "allow",
}


def _run_hook(
    stdin_text: str,
    env_overrides: dict[str, str] | None = None,
    cwd: str | None = None,
) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    if env_overrides:
        env.update(env_overrides)
    return subprocess.run(
        [sys.executable, str(HOOK), "--no-header", "--print"],
        input=stdin_text,
        capture_output=True,
        text=True,
        env=env,
        cwd=cwd,
        timeout=20,
    )


class CrossCliHookTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="cross-cli-hook-test-"))
        self.env_backup = os.environ.copy()
        os.environ["HOME"] = str(self.tmp)
        os.environ["CROSS_CLI_STATUS_HISTORY_MAX"] = "20"
        cross_cli_status.STATE_DIR = self.tmp / ".claude" / "var" / "cross_cli_status"
        cross_cli_status.LAST_PATH = cross_cli_status.STATE_DIR / "last.json"
        cross_cli_status.HISTORY_PATH = cross_cli_status.STATE_DIR / "history.jsonl"
        cross_cli_status.HISTORY_MAX = 20

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self.env_backup)
        shutil.rmtree(self.tmp, ignore_errors=True)

    # --- Unit tests for defensive parsing functions ----------------------
    def test_int_env_parsing(self) -> None:
        os.environ["TEST_INT_VAR"] = "42"
        self.assertEqual(cross_cli_status._int_env("TEST_INT_VAR", 10), 42)

        os.environ["TEST_INT_VAR"] = "not_a_number"
        self.assertEqual(cross_cli_status._int_env("TEST_INT_VAR", 10), 10)

        os.environ.pop("TEST_INT_VAR", None)
        self.assertEqual(cross_cli_status._int_env("TEST_INT_VAR", 10), 10)

    def test_coerce_int_and_float(self) -> None:
        self.assertEqual(cross_cli_status._coerce_int("123"), 123)
        self.assertEqual(cross_cli_status._coerce_int(123), 123)
        self.assertIsNone(cross_cli_status._coerce_int(None))
        self.assertIsNone(cross_cli_status._coerce_int("abc"))
        self.assertIsNone(cross_cli_status._coerce_int([]))

        self.assertEqual(cross_cli_status._coerce_float("12.34"), 12.34)
        self.assertEqual(cross_cli_status._coerce_float(12.34), 12.34)
        self.assertIsNone(cross_cli_status._coerce_float(None))
        self.assertIsNone(cross_cli_status._coerce_float("abc"))
        self.assertIsNone(cross_cli_status._coerce_float({}))

    def test_resolve_dotted_paths(self) -> None:
        payload = {"a": {"b": {"c": "found"}}, "x": None}
        self.assertEqual(
            cross_cli_status._resolve(payload, ("missing", "x", "a.b.c")),
            "found",
        )
        self.assertIsNone(cross_cli_status._resolve(payload, ("missing", "x")))

    # --- claude ----------------------------------------------------------
    def test_claude_full_payload_extracts_rate_limit(self) -> None:
        proc = _run_hook(
            json.dumps(CLAUDE_FIXTURE),
            env_overrides={"HERMES_HOOK_CLI": "claude"},
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr)
        rec = json.loads(proc.stdout)
        self.assertEqual(rec["cli"], "claude")
        self.assertEqual(rec["model"], "Opus")
        self.assertEqual(rec["rate_limit_pct"], 12)
        self.assertEqual(rec["rate_limit_window"], "5h")
        self.assertEqual(rec["rate_limit_reset_at"], 1785398400)
        self.assertEqual(rec["tokens_in"], 8500)
        self.assertEqual(rec["tokens_out"], 410)
        self.assertAlmostEqual(rec["cost_usd"], 0.01234)
        self.assertEqual(rec["version"], "2.1.220")
        self.assertIn("cwd", rec)

    def test_claude_seven_day_fallback(self) -> None:
        payload = json.loads(json.dumps(CLAUDE_FIXTURE))
        payload["rate_limits"] = {
            "seven_day": {"used_percentage": 81, "resets_at": 1785999999},
        }
        proc = _run_hook(
            json.dumps(payload),
            env_overrides={"HERMES_HOOK_CLI": "claude"},
        )
        rec = json.loads(proc.stdout)
        self.assertEqual(rec["rate_limit_pct"], 81)
        self.assertEqual(rec["rate_limit_window"], "7d")
        self.assertEqual(rec["rate_limit_reset_at"], 1785999999)

    def test_claude_zero_five_hour_usage_is_not_dropped(self) -> None:
        # A freshly-reset 5h window reports used_percentage=0. An `or`
        # chain would treat that falsy 0 as "missing" and fall through to
        # the (nonzero) seven-day value while still labeling the window
        # "5h" — corrupting the record. 0 must be preserved.
        payload = json.loads(json.dumps(CLAUDE_FIXTURE))
        payload["rate_limits"] = {
            "five_hour": {"used_percentage": 0, "resets_at": 1785400000},
            "seven_day": {"used_percentage": 81, "resets_at": 1785999999},
        }
        proc = _run_hook(
            json.dumps(payload),
            env_overrides={"HERMES_HOOK_CLI": "claude"},
        )
        rec = json.loads(proc.stdout)
        self.assertEqual(rec["rate_limit_pct"], 0)
        self.assertEqual(rec["rate_limit_window"], "5h")
        self.assertEqual(rec["rate_limit_reset_at"], 1785400000)

    def test_claude_legacy_statusline_shape_detected(self) -> None:
        # No HERMES_HOOK_CLI env. Detection must still pick claude from
        # the rate_limits.five_hour key + session_id + transcript_path.
        proc = _run_hook(json.dumps(CLAUDE_FIXTURE))
        rec = json.loads(proc.stdout)
        self.assertEqual(rec["cli"], "claude")
        self.assertEqual(rec["model"], "Opus")

    def test_claude_live_v2_1_220_stop_payload(self) -> None:
        # Captured from a real `claude --print` invocation on 2026-07-30
        # against Claude Code v2.1.220. The Stop payload does NOT carry
        # `model` or `context_window` (those only appear in the
        # statusline payload). Detection must still pick `claude` and
        # the extractor must record session_id + cwd.
        proc = _run_hook(json.dumps(CLAUDE_LIVE_PAYLOAD))
        rec = json.loads(proc.stdout)
        self.assertEqual(rec["cli"], "claude")
        self.assertEqual(rec["session_id"], "c726962e-3185-4681-aec2-313689a33360")
        self.assertEqual(rec["cwd"], "/tmp/test-project")
        self.assertIsNone(rec["model"])

    def test_codex_live_0_144_5_stop_payload(self) -> None:
        # Captured from a real `codex exec` invocation on 2026-07-30
        # against Codex 0.144.5. The model is a top-level STRING (not a
        # dict) and tokens/cost are not in the Stop payload (only in the
        # final usage summary). Detection picks `codex` from
        # `last_assistant_message` + `turn_id`.
        proc = _run_hook(json.dumps(CODEX_LIVE_PAYLOAD))
        rec = json.loads(proc.stdout)
        self.assertEqual(rec["cli"], "codex")
        self.assertEqual(rec["model"], "gpt-5.6-sol")
        self.assertIsNone(rec["tokens_in"])
        self.assertIsNone(rec["tokens_out"])

    def test_claude_rate_limits_absent_returns_no_rl(self) -> None:
        # Non-Pro/Max Claude subscribers do not get rate_limits in the
        # statusline payload. The hook must still work.
        payload = json.loads(json.dumps(CLAUDE_FIXTURE))
        del payload["rate_limits"]
        proc = _run_hook(
            json.dumps(payload),
            env_overrides={"HERMES_HOOK_CLI": "claude"},
        )
        rec = json.loads(proc.stdout)
        self.assertIsNone(rec["rate_limit_pct"])
        self.assertIsNone(rec["rate_limit_window"])

    # --- codex -----------------------------------------------------------
    def test_codex_flat_rate_limit_reset_seconds(self) -> None:
        proc = _run_hook(
            json.dumps(CODEX_FIXTURE),
            env_overrides={"HERMES_HOOK_CLI": "codex"},
        )
        rec = json.loads(proc.stdout)
        self.assertEqual(rec["cli"], "codex")
        self.assertEqual(rec["model"], "gpt-5-codex")
        self.assertEqual(rec["rate_limit_reset_at"], 1785398400)
        self.assertEqual(rec["tokens_in"], 1234)
        self.assertEqual(rec["tokens_out"], 567)
        self.assertAlmostEqual(rec["cost_usd"], 0.0042)

    def test_codex_legacy_session_cost_usd(self) -> None:
        payload = {
            "cwd": "/tmp",
            "model": {"name": "codex-mini"},
            "usage": {"input_tokens": 1, "output_tokens": 1},
            "session": {"cost_usd": 0.99},
        }
        proc = _run_hook(
            json.dumps(payload),
            env_overrides={"HERMES_HOOK_CLI": "codex"},
        )
        rec = json.loads(proc.stdout)
        self.assertAlmostEqual(rec["cost_usd"], 0.99)

    # --- agy -------------------------------------------------------------
    def test_agy_detected_via_hermes_env(self) -> None:
        proc = _run_hook(
            json.dumps(AGY_FIXTURE),
            env_overrides={"HERMES_HOOK_CLI": "agy"},
        )
        rec = json.loads(proc.stdout)
        self.assertEqual(rec["cli"], "agy")
        self.assertEqual(rec["model"], "claude-sonnet-4")
        self.assertEqual(rec["tokens_in"], 9000)
        self.assertEqual(rec["tokens_out"], 800)
        self.assertEqual(rec["rate_limit_reset_at"], 1785398400)

    # --- cursor ----------------------------------------------------------
    def test_cursor_completed_status(self) -> None:
        proc = _run_hook(
            json.dumps(CURSOR_FIXTURE),
            env_overrides={"HERMES_HOOK_CLI": "cursor"},
        )
        rec = json.loads(proc.stdout)
        self.assertEqual(rec["cli"], "cursor")
        self.assertEqual(rec["model"], "claude-4.5-sonnet")
        self.assertEqual(rec["status"], "completed")
        self.assertEqual(rec["loop_count"], 0)
        self.assertIsNone(rec["rate_limit_pct"])

    def test_cursor_loop_storm_flags_100pct(self) -> None:
        proc = _run_hook(
            json.dumps(CURSOR_LOOP_STORM),
            env_overrides={"HERMES_HOOK_CLI": "cursor"},
        )
        rec = json.loads(proc.stdout)
        self.assertEqual(rec["cli"], "cursor")
        self.assertEqual(rec["rate_limit_pct"], 100)
        self.assertEqual(rec["rate_limit_window"], "loop_storm")
        self.assertEqual(rec["loop_count"], 6)

    # --- antigravity -----------------------------------------------------
    def test_antigravity_decision_captured(self) -> None:
        proc = _run_hook(
            json.dumps(ANTIGRAVITY_FIXTURE),
            env_overrides={"HERMES_HOOK_CLI": "antigravity"},
        )
        rec = json.loads(proc.stdout)
        self.assertEqual(rec["cli"], "antigravity")
        self.assertEqual(rec["model"], "gemini-2.5-pro")
        self.assertEqual(rec["decision"], "allow")

    def test_antigravity_detected_via_decision_shape(self) -> None:
        proc = _run_hook(json.dumps(ANTIGRAVITY_FIXTURE))
        rec = json.loads(proc.stdout)
        self.assertEqual(rec["cli"], "antigravity")
        self.assertEqual(rec["decision"], "allow")

    # --- fail-closed & defensive parsing ---------------------------------
    def test_unknown_payload_records_error(self) -> None:
        proc = _run_hook(
            json.dumps({"foo": "bar"}),
            env_overrides={"HERMES_HOOK_CLI": "unknown"},
        )
        rec = json.loads(proc.stdout)
        self.assertEqual(rec["cli"], "unknown")
        self.assertEqual(rec["error"], "unknown_cli_payload")
        self.assertEqual(proc.returncode, 0)

    def test_unknown_payload_still_resolves_cwd(self) -> None:
        proc = _run_hook(
            json.dumps({"foo": "bar", "cwd": "/tmp/some-project"}),
            env_overrides={"HERMES_HOOK_CLI": "unknown"},
        )
        rec = json.loads(proc.stdout)
        self.assertEqual(rec["cli"], "unknown")
        self.assertEqual(rec["cwd"], "/tmp/some-project")

    def test_strict_unknown_payload_exits_2(self) -> None:
        proc = subprocess.run(
            [sys.executable, str(HOOK), "--no-header", "--strict", "--print"],
            input=json.dumps({"foo": "bar"}),
            capture_output=True,
            text=True,
            env={**os.environ, "HERMES_HOOK_CLI": "unknown"},
            timeout=15,
        )
        self.assertEqual(proc.returncode, 2)
        rec = json.loads(proc.stdout)
        self.assertEqual(rec["error"], "unknown_cli_payload")

    def test_invalid_json_returns_1(self) -> None:
        proc = _run_hook("{not json", env_overrides={"HERMES_HOOK_CLI": "claude"})
        self.assertEqual(proc.returncode, 1)
        rec = json.loads(proc.stdout)
        self.assertIn("invalid_json", rec["error"])

    def test_non_object_json_returns_1(self) -> None:
        proc = _run_hook(
            json.dumps(["item1", "item2"]),
            env_overrides={"HERMES_HOOK_CLI": "claude"},
        )
        self.assertEqual(proc.returncode, 1)
        rec = json.loads(proc.stdout)
        self.assertEqual(rec["error"], "payload_not_object")

    def test_empty_stdin_returns_0_and_records_unknown(self) -> None:
        proc = _run_hook("")
        self.assertEqual(proc.returncode, 0)
        rec = json.loads(proc.stdout)
        self.assertEqual(rec["cli"], "unknown")

    def test_invalid_history_max_env_falls_back_gracefully(self) -> None:
        # Non-numeric CROSS_CLI_STATUS_HISTORY_MAX must not crash import / run
        proc = _run_hook(
            json.dumps(CLAUDE_FIXTURE),
            env_overrides={
                "HERMES_HOOK_CLI": "claude",
                "CROSS_CLI_STATUS_HISTORY_MAX": "not-an-integer",
            },
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr)
        rec = json.loads(proc.stdout)
        self.assertEqual(rec["cli"], "claude")

    # --- IO: atomic last.json + locked history trim ---------------------
    def test_last_json_and_history_written(self) -> None:
        for fixture, cli in (
            (CLAUDE_FIXTURE, "claude"),
            (CODEX_FIXTURE, "codex"),
            (AGY_FIXTURE, "agy"),
            (CURSOR_FIXTURE, "cursor"),
            (ANTIGRAVITY_FIXTURE, "antigravity"),
        ):
            _run_hook(
                json.dumps(fixture),
                env_overrides={"HERMES_HOOK_CLI": cli},
            )
        last = json.loads(
            (self.tmp / ".claude" / "var" / "cross_cli_status" / "last.json").read_text()
        )
        self.assertEqual(last["cli"], "antigravity")
        history = (
            self.tmp / ".claude" / "var" / "cross_cli_status" / "history.jsonl"
        ).read_text().splitlines()
        self.assertEqual(len(history), 5)
        self.assertEqual(json.loads(history[0])["cli"], "claude")
        self.assertEqual(json.loads(history[-1])["cli"], "antigravity")

    def test_history_trims_to_max(self) -> None:
        # 25 events with HISTORY_MAX=20 -> keep only the last 20.
        for _ in range(25):
            _run_hook(
                json.dumps(CURSOR_FIXTURE),
                env_overrides={"HERMES_HOOK_CLI": "cursor"},
            )
        history = (
            self.tmp / ".claude" / "var" / "cross_cli_status" / "history.jsonl"
        ).read_text().splitlines()
        self.assertEqual(len(history), 20)

    def test_concurrent_appends_do_not_lose_entries(self) -> None:
        count = 8
        with concurrent.futures.ThreadPoolExecutor(max_workers=count) as pool:
            procs = list(
                pool.map(
                    lambda _: _run_hook(
                        json.dumps(CURSOR_FIXTURE),
                        env_overrides={"HERMES_HOOK_CLI": "cursor"},
                    ),
                    range(count),
                )
            )
        for proc in procs:
            self.assertEqual(proc.returncode, 0, msg=proc.stderr)
        history = (
            self.tmp / ".claude" / "var" / "cross_cli_status" / "history.jsonl"
        ).read_text().splitlines()
        self.assertEqual(len(history), count)

    def test_direct_append_history_locking_and_trim(self) -> None:
        cross_cli_status.HISTORY_MAX = 5
        for i in range(10):
            cross_cli_status._append_history({"index": i})
        history = cross_cli_status.HISTORY_PATH.read_text().splitlines()
        self.assertEqual(len(history), 5)
        self.assertEqual(json.loads(history[0])["index"], 5)
        self.assertEqual(json.loads(history[-1])["index"], 9)

    def test_direct_append_history_no_trim_when_zero(self) -> None:
        cross_cli_status.HISTORY_MAX = 0
        for i in range(10):
            cross_cli_status._append_history({"index": i})
        history = cross_cli_status.HISTORY_PATH.read_text().splitlines()
        self.assertEqual(len(history), 10)

    # --- Legacy git-header merge ----------------------------------------
    def test_no_header_skips_git_header(self) -> None:
        proc = _run_hook(
            json.dumps(CLAUDE_FIXTURE),
            env_overrides={"HERMES_HOOK_CLI": "claude"},
        )
        rec = json.loads(proc.stdout)
        self.assertNotIn("header_status", rec)
        self.assertNotIn("pr_url", rec)

    def test_header_captured_when_omitting_flag(self) -> None:
        env = os.environ.copy()
        env["HERMES_HOOK_CLI"] = "claude"
        proc = subprocess.run(
            [sys.executable, str(HOOK), "--print"],
            input=json.dumps(CLAUDE_FIXTURE),
            capture_output=True,
            text=True,
            env=env,
            cwd=str(self.tmp),
            timeout=20,
        )
        self.assertEqual(proc.returncode, 0)
        rec = json.loads(proc.stdout)
        self.assertIn("cli", rec)
        self.assertEqual(rec["cli"], "claude")


if __name__ == "__main__":
    unittest.main(verbosity=2)
