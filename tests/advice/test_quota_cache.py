import hashlib
import json
import os
import concurrent.futures
import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / ".claude/skills/advice/scripts/quota_cache.py"
SPEC = importlib.util.spec_from_file_location("quota_cache", TOOL)
quota_cache = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(quota_cache)
CLAUDE_PRIMARY = hashlib.sha256(b"verified claude primary account id").hexdigest()
CLAUDE_ALT = hashlib.sha256(b"verified claude alternate account id").hexdigest()
AGY_PRIMARY = hashlib.sha256(b"verified agy primary account id").hexdigest()


class AdviceQuotaCacheTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="advice-quota-test-")
        self.addCleanup(self.temp.cleanup)
        self.cache = Path(self.temp.name) / "cache"

    def run_cache(self, *args, expected=0):
        env = {**os.environ, "ADVICE_QUOTA_CACHE_TESTING": "1"}
        result = subprocess.run(
            [sys.executable, str(TOOL), *args, "--cache-root", str(self.cache)],
            capture_output=True,
            text=True,
            env=env,
            timeout=10,
        )
        self.assertEqual(result.returncode, expected, result.stderr + result.stdout)
        return result

    def record(self, identity=CLAUDE_PRIMARY, reset="2030-01-01T00:00:00Z", provider="claude"):
        return self.run_cache(
            "record", "--identity-sha256", identity, "--provider", provider,
            "--model", "opus", "--reset-at", reset,
            "--now", "2029-12-31T00:00:00Z",
        )

    def test_quota_blocks_only_same_seat_until_reported_reset(self):
        self.record()
        blocked = self.run_cache(
            "check", "--provider", "claude", "--identity-sha256", CLAUDE_PRIMARY,
            "--now", "2029-12-31T23:59:00Z", expected=10,
        )
        self.assertIn("reset_at=2030-01-01T00:00:00+00:00", blocked.stdout)
        self.assertEqual(
            "ELIGIBLE\n",
            self.run_cache("check", "--provider", "claude", "--identity-sha256", CLAUDE_ALT,
                           "--now", "2029-12-31T23:59:00Z").stdout,
        )
        self.assertEqual(
            "ELIGIBLE\n",
            self.run_cache("check", "--provider", "claude", "--identity-sha256", CLAUDE_PRIMARY,
                           "--now", "2030-01-01T00:00:00Z").stdout,
        )
        self.assertEqual([], list(self.cache.glob("*.json")))

    def test_successful_fresh_probe_clears_cached_quota(self):
        self.record()
        self.run_cache("clear", "--provider", "claude", "--identity-sha256", CLAUDE_PRIMARY)
        self.assertEqual(
            "ELIGIBLE\n",
            self.run_cache("check", "--provider", "claude", "--identity-sha256", CLAUDE_PRIMARY,
                           "--now", "2029-12-31T12:00:00Z").stdout,
        )

    def test_provider_scopes_the_same_account_seat_separately(self):
        self.record(identity=AGY_PRIMARY, provider="agy")
        result = self.run_cache("check", "--provider", "claude", "--identity-sha256", AGY_PRIMARY,
                                "--now", "2029-12-31T12:00:00Z")
        self.assertEqual("ELIGIBLE\n", result.stdout)

    def test_unknown_or_expired_reset_does_not_create_a_blocking_record(self):
        result = self.run_cache(
            "record", "--identity-sha256", AGY_PRIMARY, "--provider", "agy",
            "--model", "gemini-3.8-flash-high", "--reset-at", "2029-12-30T00:00:00Z",
            "--now", "2029-12-31T00:00:00Z",
        )
        self.assertIn("RESET_ALREADY_PASSED", result.stdout)
        self.assertFalse(self.cache.exists() and list(self.cache.glob("*.json")))
        result = subprocess.run(
            [sys.executable, str(TOOL), "record", "--identity-sha256", CLAUDE_PRIMARY,
             "--provider", "claude", "--model", "opus", "--cache-root", str(self.cache)],
            capture_output=True, text=True,
            env={**os.environ, "ADVICE_QUOTA_CACHE_TESTING": "1"}, timeout=10,
        )
        self.assertEqual(2, result.returncode)
        self.assertFalse(self.cache.exists() and list(self.cache.glob("*.json")))

    def test_corrupt_entry_is_removed_and_does_not_block(self):
        self.record()
        entry = next(self.cache.glob("*.json"))
        entry.write_text("not json")
        result = self.run_cache("check", "--provider", "claude", "--identity-sha256", CLAUDE_PRIMARY,
                                "--now", "2029-12-31T12:00:00Z")
        self.assertEqual("ELIGIBLE\n", result.stdout)
        self.assertFalse(entry.exists())

    def test_corrupt_reset_time_is_removed_and_does_not_block(self):
        self.record()
        entry = next(self.cache.glob("*.json"))
        data = json.loads(entry.read_text())
        data["reset_at_utc"] = "not-a-time"
        entry.write_text(json.dumps(data))
        result = self.run_cache("check", "--provider", "claude", "--identity-sha256", CLAUDE_PRIMARY,
                                "--now", "2029-12-31T12:00:00Z")
        self.assertEqual("ELIGIBLE\n", result.stdout)
        self.assertFalse(entry.exists())

    def test_cached_entry_never_contains_raw_provider_error(self):
        self.record()
        entry = next(self.cache.glob("*.json"))
        self.assertNotIn("Weekly usage limit reached", entry.read_text())

    def test_cache_never_stores_identity_key_or_raw_provider_text(self):
        identity = CLAUDE_PRIMARY
        self.record(identity=identity)
        files = list(self.cache.glob("*.json"))
        self.assertEqual(1, len(files))
        key = f"claude\0{identity}".encode()
        self.assertEqual(hashlib.sha256(key).hexdigest() + ".json", files[0].name)
        data = json.loads(files[0].read_text())
        serialized = json.dumps(data)
        self.assertNotIn(identity, serialized)
        self.assertNotIn("token", serialized.lower())
        self.assertEqual(0o700, self.cache.stat().st_mode & 0o777)
        self.assertEqual(0o600, files[0].stat().st_mode & 0o777)

    def test_symlinked_cache_root_fails_open_without_touching_target(self):
        target = Path(self.temp.name) / "target"
        target.mkdir()
        self.cache.symlink_to(target, target_is_directory=True)
        result = self.run_cache("check", "--provider", "claude",
                                "--identity-sha256", CLAUDE_PRIMARY)
        self.assertEqual("ELIGIBLE\n", result.stdout)
        self.assertEqual([], list(target.iterdir()))

    def test_symlinked_entry_cannot_block_or_read_target(self):
        self.record()
        entry = next(self.cache.glob("*.json"))
        entry.unlink()
        target = Path(self.temp.name) / "private-target"
        target.write_text("do not read")
        entry.symlink_to(target)
        result = self.run_cache("check", "--provider", "claude",
                                "--identity-sha256", CLAUDE_PRIMARY)
        self.assertEqual("ELIGIBLE\n", result.stdout)
        self.assertEqual("do not read", target.read_text())

    def test_swapping_cache_directory_name_after_open_cannot_redirect_write(self):
        root = Path(self.temp.name) / "cache"
        victim = Path(self.temp.name) / "victim"
        victim.mkdir()
        identity = hashlib.sha256(b"verified claude primary account id").hexdigest()
        digest = hashlib.sha256(f"claude\0{identity}".encode()).hexdigest()
        entry = {"version": 1, "identity_sha256": digest, "provider": "claude",
                 "model": "opus", "reason": "quota", "observed_at_utc": "2029-12-31T00:00:00+00:00",
                 "reset_at_utc": "2030-01-01T00:00:00+00:00"}
        moved = Path(self.temp.name) / "opened-cache"
        with quota_cache.locked(root) as directory_fd:
            root.rename(moved)
            root.symlink_to(victim, target_is_directory=True)
            quota_cache.write_entry(directory_fd, f"{digest}.json", entry)
        self.assertTrue((moved / f"{digest}.json").is_file())
        self.assertFalse(list(victim.iterdir()))

    def test_concurrent_records_leave_one_complete_private_record(self):
        commands = []
        for reset in ("2030-01-01T00:00:00Z", "2030-01-02T00:00:00Z"):
            commands.append([sys.executable, str(TOOL), "record", "--provider", "claude",
                "--identity-sha256", CLAUDE_PRIMARY, "--model", "opus",
                "--reset-at", reset, "--now", "2029-12-31T00:00:00Z",
                "--cache-root", str(self.cache)])
        env = {**os.environ, "ADVICE_QUOTA_CACHE_TESTING": "1"}
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda argv: subprocess.run(
                argv, capture_output=True, text=True, env=env, timeout=10), commands))
        self.assertEqual([0, 0], [result.returncode for result in results])
        entries = list(self.cache.glob("*.json"))
        self.assertEqual(1, len(entries))
        self.assertIn(json.loads(entries[0].read_text())["reset_at_utc"],
                      {"2030-01-01T00:00:00+00:00", "2030-01-02T00:00:00+00:00"})


if __name__ == "__main__":
    unittest.main()
