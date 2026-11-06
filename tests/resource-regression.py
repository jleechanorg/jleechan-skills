#!/usr/bin/env python3
"""Exercise a supplied creation launcher against resource/auth gate cases.

This regression imports the supplied launcher and calls its real main entry
point. It never supplies a default launcher: use RESOURCE_TEST_RUNNER or the
first positional argument so the test cannot silently test a copy.
"""
from __future__ import annotations

import contextlib
import hashlib
import datetime
import importlib.util
import inspect
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


def _runner_from_args() -> Path:
    args = list(sys.argv[1:])
    runner_arg = None
    if args and not args[0].startswith("-"):
        runner_arg = args.pop(0)
    elif args[:1] == ["--runner"]:
        if len(args) < 2:
            raise SystemExit("--runner requires a launcher path")
        runner_arg = args[1]
        del args[:2]
    runner_value = runner_arg or os.environ.get("RESOURCE_TEST_RUNNER")
    if not runner_value:
        raise SystemExit(
            "supply the actual launcher path as the first argument or "
            "RESOURCE_TEST_RUNNER"
        )
    runner = Path(runner_value).expanduser()
    if not runner.is_file():
        raise SystemExit(f"RESOURCE_TEST_RUNNER is not a file: {runner}")
    sys.argv[:] = [sys.argv[0], *args]
    return runner


RUNNER = _runner_from_args()


class ReachedIdentity(Exception):
    """Sentinel proving the launcher reached its auth boundary."""


class ResourceRegression(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location("resource_runner", RUNNER)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"cannot import launcher: {RUNNER}")
        self.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.mod)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.ledger = Path(self.tmp.name) / "scene.json"
        self.now = datetime.datetime.now(datetime.timezone.utc)
        self.start = (self.now - datetime.timedelta(seconds=1)).isoformat()
        self.end = (self.now + datetime.timedelta(seconds=600)).isoformat()

    def invoke(self, state="released", conflicts=(), auth_error=None, hold=None,
               owner="creation-test"):
        ledger_path = self.ledger
        if state == "absent":
            ledger_path = Path(self.tmp.name) / "missing-scene.json"
        else:
            ledger_path.write_text(json.dumps({
                "owner": owner,
                "state": state,
                "start": self.start,
                "end": self.end,
            }))
        argv = [
            "launcher", "--admitted-at", self.start,
            "--bounded-until", self.end,
            "--scene-ledger", str(ledger_path),
        ]
        if hold:
            argv += ["--current-human-hold", hold]
        patches = [
            patch.object(sys, "argv", argv),
            patch.object(self.mod, "verify_inputs"),
            patch.object(self.mod, "verify_source_bound_service",
                         return_value={}),
            patch.object(self.mod, "verify_served_frontend",
                         return_value={}),
            patch.object(self.mod, "verify_backend", return_value={}),
            patch.object(self.mod, "observe_live_resources",
                         return_value=list(conflicts), create=True),
            patch.object(self.mod, "require_identity",
                         side_effect=auth_error or
                         ReachedIdentity("auth reached")),
            patch.object(self.mod.subprocess, "Popen",
                         side_effect=AssertionError("must not launch")),
        ]
        with contextlib.ExitStack() as stack:
            for item in patches:
                stack.enter_context(item)
            self.mod.main()

    def test_released_reaches_auth(self):
        with self.assertRaises(ReachedIdentity):
            self.invoke()

    def test_fresh_handback_with_previous_other_owner_reaches_auth(self):
        with self.assertRaises(ReachedIdentity):
            self.invoke(owner="previous-operator")

    def test_unknown_pending_absent_ledger_do_not_create_permission_gate(self):
        for state in ("unknown", "pending", "absent"):
            with self.subTest(state=state), self.assertRaises(ReachedIdentity):
                self.invoke(state)

    def test_active_conflict_rejected_even_if_ledger_admitted(self):
        conflict = {
            "resource": "browser-profile", "owner": "pid:123",
            "evidence": "live argv exact profile match",
        }
        with self.assertRaisesRegex(
            SystemExit, "live resource conflict.*pid:123"
        ):
            self.invoke("admitted", conflicts=[conflict])

    def test_explicit_current_human_hold_rejected(self):
        with self.assertRaisesRegex(
            SystemExit, "current human hold: STOP device capture now"
        ):
            self.invoke("admitted", hold="STOP device capture now")

    def test_injected_auth_error_preserved_exactly(self):
        with self.assertRaises(SystemExit) as raised:
            self.invoke(auth_error=SystemExit(
                "HTTP 401: authentication rejected by issuer"
            ))
        self.assertEqual(
            str(raised.exception), "HTTP 401: authentication rejected by issuer"
        )

    def test_observer_matches_exact_profile_not_similar_paths(self):
        proc = Path(self.tmp.name) / "proc"
        proc.mkdir()
        for pid, argv in (
            (101, ["chrome", "--user-data-dir=" + str(self.mod.PROFILE)]),
            (102, ["python", "--google-profile", str(self.mod.PROFILE)]),
            (103, ["chrome", "--user-data-dir=" +
                    str(self.mod.PROFILE) + "-other"]),
            (104, ["echo", str(self.mod.PROFILE)]),
        ):
            entry = proc / str(pid)
            entry.mkdir()
            (entry / "cmdline").write_bytes(
                (chr(0).join(argv) + chr(0)).encode()
            )
        self.assertCountEqual(
            [item["owner"] for item in self.mod.observe_live_resources(proc)],
            ["pid:101", "pid:102"],
        )
        argv = [
            "launcher",
            "--bounded-until",
            self.end,
            "--scene-ledger",
            str(self.ledger),
        ]
        patches = [
            patch.object(sys, "argv", argv),
            patch.object(self.mod, "verify_inputs"),
            patch.object(self.mod, "verify_source_bound_service",
                         return_value={}),
            patch.object(self.mod, "verify_served_frontend",
                         return_value={}),
            patch.object(self.mod, "verify_backend", return_value={}),
            patch.object(self.mod, "require_identity",
                         side_effect=ReachedIdentity("auth reached")),
            patch.object(self.mod.subprocess, "Popen",
                         side_effect=AssertionError("must not launch")),
        ]
        with contextlib.ExitStack() as stack:
            for item in patches:
                stack.enter_context(item)
            with self.assertRaisesRegex(
                SystemExit, "live resource conflict.*pid:101"
            ):
                self.mod.main(
                    resource_observer=lambda: self.mod.observe_live_resources(proc)
                )

    def test_conflict_arriving_during_preflight_blocks_child(self):
        self.mod.ROOT = Path(self.tmp.name)
        argv = ["launcher", "--bounded-until", self.end,
                "--scene-ledger", str(self.ledger)]
        conflict = {
            "resource": "browser-profile", "owner": "pid:456",
            "evidence": "observed just before launch",
        }
        patches = [
            patch.object(sys, "argv", argv),
            patch.object(self.mod, "verify_inputs"),
            patch.object(self.mod, "verify_source_bound_service",
                         return_value={}),
            patch.object(self.mod, "verify_served_frontend",
                         return_value={}),
            patch.object(self.mod, "assert_same_served_asset"),
            patch.object(self.mod, "verify_backend", return_value={}),
            patch.object(self.mod, "require_identity",
                         return_value=("test@example.invalid", "synthetic-uid")),
        ]
        popen_patch = patch.object(self.mod.subprocess, "Popen")
        with contextlib.ExitStack() as stack:
            for item in patches:
                stack.enter_context(item)
            popen = stack.enter_context(popen_patch)
            observations = iter([[], [conflict]])
            with self.assertRaisesRegex(
                SystemExit, "live resource conflict.*pid:456"
            ):
                self.mod.main(
                    resource_observer=lambda: next(observations)
                )
            popen.assert_not_called()

    def test_launch_contract_is_sibling_and_child_output_stays_empty(self):
        self.mod.ROOT = Path(self.tmp.name)
        ledger = self.ledger
        ledger.write_text(json.dumps({
            "owner": "creation-test",
            "state": "admitted",
            "start": self.start,
            "end": self.end,
        }))
        fixture_root = Path(self.tmp.name) / "inputs"
        fixture_root.mkdir()
        harness = fixture_root / "harness.py"
        harness.write_text("# synthetic harness fixture\n")
        upload = fixture_root / "avatar.png"
        upload.write_bytes(b"synthetic-upload")
        profile = fixture_root / "profile"
        profile.mkdir()
        worktree = fixture_root / "worktree"
        worktree.mkdir()
        self.mod.HARNESS = harness
        self.mod.WORKTREE = worktree
        self.mod.UPLOAD = upload
        self.mod.PROFILE = profile
        self.mod.EXPECTED_HARNESS_SHA = hashlib.sha256(
            harness.read_bytes()
        ).hexdigest()

        argv = [
            "launcher",
            "--admitted-at",
            self.start,
            "--bounded-until",
            self.end,
            "--scene-ledger",
            str(ledger),
        ]
        seen = {}

        class HealthResponse:
            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

            def read(self):
                return json.dumps({
                    "git_commit": self_mod.BACKEND_SHA,
                }).encode()

        class Child:
            pid = 999999

            def wait(self, timeout=None):
                return 0

        self_mod = self.mod

        def fake_popen(command, **kwargs):
            out = Path(command[command.index("--out") + 1])
            self.assertEqual(list(out.iterdir()), [])
            contract_path = out.parent / (out.name + ".launch-contract.json")
            self.assertTrue(contract_path.is_file())
            contract = json.loads(contract_path.read_text())
            self.assertEqual(contract["scenario"], "upload")
            seen["out"] = out
            seen["contract_path"] = contract_path
            seen["contract"] = contract
            return Child()

        patches = [
            patch.object(sys, "argv", argv),
            patch.object(self.mod, "verify_inputs", create=True),
            patch.object(self.mod, "verify_source_bound_service",
                         return_value={}, create=True),
            patch.object(self.mod, "verify_served_frontend",
                         return_value={}, create=True),
            patch.object(self.mod, "verify_backend", return_value={}, create=True),
            patch.object(self.mod, "assert_same_served_asset", create=True),
            patch.object(self.mod, "same_window", return_value=True, create=True),
            patch.object(self.mod, "require_identity",
                         return_value=("test@example.invalid", "synthetic-uid")),
            patch.object(self.mod.urllib.request, "urlopen",
                         return_value=HealthResponse()),
            patch.object(self.mod.subprocess, "Popen", side_effect=fake_popen),
        ]
        with contextlib.ExitStack() as stack:
            for item in patches:
                stack.enter_context(item)
            kwargs = {}
            if "resource_observer" in inspect.signature(
                self.mod.main
            ).parameters:
                kwargs["resource_observer"] = lambda: []
            with self.assertRaises(SystemExit) as raised:
                self.mod.main(**kwargs)
        self.assertEqual(raised.exception.code, 0)
        self.assertIn("contract_path", seen)
        contract_path = seen["contract_path"]
        receipt_path = seen["out"].parent / (seen["out"].name + ".launcher.json")
        self.assertTrue(contract_path.is_file())
        self.assertTrue(receipt_path.is_file())
        receipt = json.loads(receipt_path.read_text())
        self.assertEqual(receipt["launch_contract"], contract_path.name)
        self.assertEqual(json.loads(contract_path.read_text()), seen["contract"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
