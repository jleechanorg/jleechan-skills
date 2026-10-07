import hashlib
import json
import os
import stat
import subprocess
import tempfile
import time
import unittest
import importlib.util
import sys
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL_DIR = REPO_ROOT / ".claude" / "skills" / "dot-portfolio-coordinator"
sys_path = str(SKILL_DIR / "scripts")
import sys
if sys_path not in sys.path:
    sys.path.insert(0, sys_path)

CLI_SCRIPT = str(SKILL_DIR / "scripts" / "coordinator-portfolio.py")
PREPARED_NONCE = "0123456789abcdef0123456789abcdef"
WRAPPER_SCRIPT = str(SKILL_DIR / "scripts" / "dot-portfolio-coordinator-wrapper.sh")
SCRIPTS_DIR = str(SKILL_DIR / "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)
COORDINATOR_SPEC = importlib.util.spec_from_file_location(
    "coordinator_portfolio", CLI_SCRIPT
)
coordinator_portfolio = importlib.util.module_from_spec(COORDINATOR_SPEC)
COORDINATOR_SPEC.loader.exec_module(coordinator_portfolio)


class TestDotPortfolioCoordinatorObserve(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(dir="/tmp")
        self.run_dir = os.path.join(self.temp_dir.name, "observe_run")

        # Create a valid test sources registry in temp_dir
        self.sources_data = {
            "version": "1.0.0",
            "sources": [
                {
                    "id": "test-repo",
                    "namespace": "test",
                    "type": "github_repo",
                    "github_host": "github.com",
                    "repository": "example-org/test-repo",
                    "canonical_tracker": "github_issues",
                    "authority": "read_only",
                    "audience_policy": {"title": ["model", "internal"],
                                        "updated_at": ["internal"]}
                }
            ]
        }
        self.sources_file = os.path.join(self.temp_dir.name, "test_sources.json")
        with open(self.sources_file, "w") as f:
            json.dump(self.sources_data, f)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_observe_runs_real_collection_and_creates_private_files(self):
        cmd = [
            CLI_SCRIPT,
            "--sources", self.sources_file,
            "observe",
            "--duration", "2",
            "--interval", "1",
            "--run-dir", self.run_dir
        ]
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.assertEqual(proc.returncode, 0)

        # 1. Verify run_dir permissions (mode 0700)
        st = os.stat(self.run_dir)
        mode = st.st_mode & 0o777
        self.assertEqual(mode, 0o700)

        # 2. Verify files created: source_manifest.json, heartbeat.jsonl, latest_snapshot.json, final_receipt.json
        manifest_file = os.path.join(self.run_dir, "source_manifest.json")
        hb_file = os.path.join(self.run_dir, "heartbeat.jsonl")
        snap_file = os.path.join(self.run_dir, "latest_snapshot.json")
        receipt_file = os.path.join(self.run_dir, "final_receipt.json")

        self.assertTrue(os.path.exists(manifest_file))
        self.assertTrue(os.path.exists(hb_file))
        self.assertTrue(os.path.exists(snap_file))
        self.assertTrue(os.path.exists(receipt_file))

        # Check file modes are 0600
        for fpath in (manifest_file, hb_file, snap_file, receipt_file):
            f_mode = os.stat(fpath).st_mode & 0o777
            self.assertEqual(f_mode, 0o600, f"File {fpath} should be mode 0600")

        # 3. Verify real collection happened: snap_file contains 'test-repo'
        with open(snap_file, "r") as f:
            snap_data = json.load(f)
        self.assertIn("snapshots", snap_data)
        self.assertIn("test-repo", snap_data["snapshots"])

        # 4. Verify final receipt accurately records completed cycles
        with open(receipt_file, "r") as f:
            receipt = json.load(f)
        self.assertIn("completed_cycles", receipt)
        self.assertIn("partial_cycles", receipt)
        self.assertEqual(receipt.get("stop_reason"), "completed")

    def test_observe_drift_detection_stops_run(self):
        # We start observe for 10 seconds with interval 1.
        # But we modify the sources file immediately so it detects drift on tick 2.
        cmd = [
            CLI_SCRIPT,
            "--sources", self.sources_file,
            "observe",
            "--duration", "10",
            "--interval", "1",
            "--run-dir", self.run_dir
        ]
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        time.sleep(1.2)
        # Modify the sources file to cause drift
        with open(self.sources_file, "a") as f:
            f.write("\n")

        stdout, stderr = proc.communicate(timeout=10)
        self.assertEqual(proc.returncode, 0)
        receipt_file = os.path.join(self.run_dir, "final_receipt.json")
        self.assertTrue(os.path.exists(receipt_file))
        with open(receipt_file, "r") as f:
            receipt = json.load(f)
        self.assertEqual(receipt.get("stop_reason"), "manifest_drift_detected")

    def test_observe_active_requires_grant(self):
        cmd = [
            CLI_SCRIPT,
            "--sources", self.sources_file,
            "observe",
            "--duration", "2",
            "--interval", "1",
            "--send-messages",
            "--run-dir", self.run_dir
        ]
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("error", proc.stderr.lower() + proc.stdout.lower())

    def test_default_registry_supports_private_item_version_receipts(self):
        sources_path = SKILL_DIR / "references" / "sources.json"
        sources_data = json.loads(sources_path.read_text(encoding="utf-8"))
        registry = coordinator_portfolio.SourceRegistry(sources_data)
        fetched_at = "2026-10-07T00:00:00Z"

        def fetch(source, *args, **kwargs):
            item = {"id": "17", "title": "Fixture task", "status": "open",
                    "updated_at": fetched_at}
            if source["type"] == "github_repo":
                return {"items": [item], "has_next": False}
            return [item]

        collected = coordinator_portfolio.PortfolioCollector(registry).collect_all(
            fetch_fn=fetch
        )
        candidates, reason = coordinator_portfolio.build_driver_candidates(
            collected, registry
        )
        self.assertEqual(reason, "ok")
        self.assertEqual(len(candidates), len(registry.sources))
        for candidate in candidates:
            self.assertEqual(candidate["source_binding"]["record_version"], fetched_at)
        internal_item = collected["snapshots"]["web-app"]["items"][0]
        self.assertIn("updated_at", internal_item)
        self.assertNotIn("updated_at", registry.filter_by_audience(
            "web-app", internal_item, "model"
        ))
        self.assertNotIn("updated_at", registry.filter_by_audience(
            "web-app", internal_item, "public"
        ))

    def test_real_shaped_187_item_packet_stays_within_driver_limit(self):
        from modules.driver_adapter import MAX_PACKET_BYTES, _validate_packet

        sources = []
        for index in range(3):
            source_id = f"fixture-source-{index}"
            sources.append({
                "id": source_id,
                "namespace": f"fixture-{index}",
                "type": "github_repo",
                "github_host": "github.com",
                "repository": f"fixture-org/repository-{index}",
                "canonical_tracker": "github_issues",
                "authority": "read_only",
                "audience_policy": {
                    field: ["model"]
                    for field in ("title", "status", "priority", "owner",
                                  "next_action", "blocker")
                } | {"updated_at": ["internal"]},
            })
        registry = coordinator_portfolio.SourceRegistry({
            "version": "1.0.0", "sources": sources,
        })

        snapshots = {}
        item_index = 0
        for source in sources:
            items = []
            for _ in range(63 if item_index == 0 else 62):
                item_id = str(item_index + 1000)
                items.append({
                    "id": item_id,
                    "task_composite_key": [
                        "github.com", source["repository"],
                        source["namespace"], item_id,
                    ],
                    "title": f"Review task {item_index:03d}",
                    "status": "open",
                    "priority": "P2",
                    "owner": "owner",
                    "next_action": "Record the current blocker and evidence.",
                    "blocker": "Pending review.",
                    "updated_at": f"2026-10-07T00:{item_index % 60:02d}:00Z",
                })
                item_index += 1
            snapshots[source["id"]] = {
                "status": "fresh",
                "version": "fixture-cursor-v1",
                "cursor": {"completed": True},
                "checkpoint_committed": True,
                "items": items,
            }

        candidates, reason = coordinator_portfolio.build_driver_candidates(
            {"snapshots": snapshots}, registry
        )
        self.assertEqual(reason, "ok")
        self.assertEqual(len(candidates), 187)
        model_snapshot = {
            "coverage": {
                "registered_count": 3, "fresh_count": 3,
                "stale_count": 0, "unavailable_count": 0,
            },
            "sources": {},
            "candidate_bindings": candidates,
        }
        for source in sources:
            source_id = source["id"]
            collected = snapshots[source_id]
            model_snapshot["sources"][source_id] = {
                "status": "fresh",
                "version": collected["version"],
                "cursor": collected["cursor"],
                "checkpoint_committed": True,
                "authority": source["authority"],
                "items": [
                    registry.filter_by_audience(source_id, item, "model")
                    for item in collected["items"]
                ],
            }
        packet = {
            "schema_version": 1,
            "task_id": None,
            "event_id": "fixture-event-187",
            "authority": {"instruction": "Review fixture tasks.", "source": "fixture"},
            "snapshot": {key: value for key, value in model_snapshot.items()
                         if key != "candidate_bindings"},
            "previous_dot_reply": "",
            "dialogue_stage": "inventory",
            "phase": "inventory_due",
            "candidate_bindings": candidates,
            "source_binding": None,
            "grant_binding": {"grant_version": 1, "grant_sha256": "a" * 64},
            "correlation": None,
        }
        validated, packet_reason = _validate_packet(packet)
        self.assertEqual(packet_reason, "ok")
        self.assertEqual(len(validated["candidate_bindings"]), 187)
        packet_bytes = len(json.dumps(
            packet, ensure_ascii=False, allow_nan=False, separators=(",", ":")
        ).encode())
        self.assertGreater(packet_bytes, 90_000)
        self.assertLessEqual(
            packet_bytes,
            MAX_PACKET_BYTES,
        )

    def test_candidate_task_ids_are_stable_and_distinguish_source_items(self):
        registry = coordinator_portfolio.SourceRegistry(self.sources_data)

        def build(item_id):
            item = {
                "id": item_id,
                "task_composite_key": ["github.com", "example-org/test-repo",
                                       "test", item_id],
                "updated_at": "2026-10-07T00:00:00Z",
            }
            collected = {"snapshots": {"test-repo": {
                "status": "fresh", "version": "v1",
                "cursor": {"completed": True},
                "checkpoint_committed": True, "items": [item],
            }}}
            return coordinator_portfolio.build_driver_candidates(
                collected, registry
            )[0][0]["task_id"]

        self.assertEqual(build("item-1"), build("item-1"))
        self.assertNotEqual(build("item-1"), build("item-2"))
        self.assertLessEqual(len(build("item-1")), 80)

    def test_observe_active_mode_with_grant_sends_messages(self):
        with tempfile.TemporaryDirectory(dir="/tmp") as tmp:
            root = Path(tmp)
            started = time.time()
            accounts = []
            for name in ("first", "second", "third"):
                grant = {"grant_version": 1, "task_id": "dot-coordinator-separated-20261007",
                         "account_id": name, "action": "coordination_message", "max_messages": 12,
                         "min_interval_secs": 3600, "activated_at_epoch": started,
                         "expiry_epoch": started + 900}
                path = root / (name + ".json")
                path.write_text(json.dumps(grant)); path.chmod(0o400)
                accounts.append({"account": name, "grant_file": str(path),
                                 "grant_sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
            config = {"run_id": "integration", "task_id": "dot-coordinator-separated-20261007",
                      "activated_at_epoch": started, "duration_secs": 900,
                      "authority": "Continue the fixture task; no merge or destructive authority.",
                      "state_dir": self.run_dir,
                      "accounts": accounts}
            pilot = root / "pilot.json"
            pilot.write_text(json.dumps(config)); pilot.chmod(0o400)
            fake_dot = root / "dot"
            fake_dot.write_text(
                "#!/bin/sh\n"
                "if [ \"$3\" = send-once ]; then\n"
                f"  echo prepared {PREPARED_NONCE}\n"
                "  read -r cmd\n"
                f"  if [ \"$cmd\" = 'commit {PREPARED_NONCE}' ]; then\n"
                "    cat \"$4\" > \"$DOT_CAPTURE_FILE\"\n"
                "    echo DOT_SENT_VERIFIED\n"
                "  fi\n"
                "fi\n"
            )
            fake_dot.chmod(0o700)
            fake_gh = root / "gh"
            fake_gh.write_text(
                "#!/bin/sh\nprintf '%s\\n' '[{\"number\":7,\"id\":7,"
                "\"title\":\"Fixture authorized task\",\"state\":\"open\","
                "\"updated_at\":\"2026-10-07T00:00:00Z\"}]'\n"
            )
            fake_gh.chmod(0o700)
            fake_agy = root / "agy"
            fake_agy.write_text(
                "#!/usr/bin/env python3\nimport json,sys\n"
                "event=json.loads(sys.stdin.readline())\n"
                "p=json.loads(event['message']['content'].split('Packet JSON:' + chr(10))[-1])\n"
                "source=p['snapshot']['sources']['test-repo']\n"
                "assert isinstance(source.get('collected_at'),int) and not isinstance(source['collected_at'],bool)\n"
                "for field in ('validated_at','attempted_at'):\n"
                " value=source.get(field)\n"
                " assert field not in source or (isinstance(value,int) and not isinstance(value,bool))\n"
                "candidate=p['candidate_bindings'][0]\n"
                "assert candidate['source_binding']['source_id']=='test-repo'\n"
                "assert candidate['source_binding']['record_version']=='2026-10-07T00:00:00Z'\n"
                "sanitized={'task_composite_key':candidate['source_binding']['task_composite_key'],"
                "'id':7,'title':'Fixture authorized task',"
                "'updated_at':'2026-10-07T00:00:00Z'}\n"
                "digest=__import__('hashlib').sha256(json.dumps(sanitized,sort_keys=True,"
                "ensure_ascii=False,separators=(',',':')).encode()).hexdigest()\n"
                "assert candidate['source_binding']['record_digest']==digest\n"
                "d={'schema_version':1,'event_id':p['event_id'],"
                "'task_id':candidate['task_id'],'outcome':'send_proposal',"
                "'stage':p['dialogue_stage'],'source_binding':candidate['source_binding'],"
                "'grant_binding':p['grant_binding'],'correlation':None,"
                "'judgment':{'assessment':'unknown','safe_next_action':'ask Dot'},"
                "'blockers':[],'action':'send','message':'List current blockers with evidence.'}\n"
                "print(json.dumps({'event':'result','result':{'status':'SUCCESS',"
                "'response':json.dumps(d)}}))\n"
            )
            fake_agy.chmod(0o700)
            sent_message_path = root / "sent-message.txt"
            env = dict(os.environ, PATH=str(root) + os.pathsep + os.environ["PATH"],
                       DOT_CAPTURE_FILE=str(sent_message_path))
            cmd = [CLI_SCRIPT, "--sources", self.sources_file, "observe", "--interval", "1",
                   "--send-messages", "--pilot-config", str(pilot), "--transport-script", str(fake_dot),
                   "--run-dir", self.run_dir]
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
            observed = None
            try:
                deadline = time.monotonic() + 10
                while time.monotonic() < deadline and proc.poll() is None:
                    state_file = Path(self.run_dir) / "run_state.json"
                    if state_file.exists():
                        observed = json.loads(state_file.read_text()).get("slots", {}).get("0")
                        if observed and observed.get("outcome") != "in_progress_hold":
                            break
                    time.sleep(0.05)
            finally:
                if proc.poll() is None:
                    proc.terminate()
                stdout, stderr = proc.communicate(timeout=5)
            self.assertIsNotNone(observed, (stdout, stderr))
            self.assertTrue(observed.get("delivery_verified"), (observed, stdout, stderr))
            sent_message = sent_message_path.read_text()
            guidance = (SKILL_DIR / "references" / "dot-self-unblock.md").read_text()
            self.assertTrue(sent_message.startswith(guidance + "\n\n"))
            self.assertTrue(sent_message.endswith("List current blockers with evidence."))
            receipt = json.loads((Path(self.run_dir) / "final_receipt.json").read_text())
            self.assertEqual(receipt["sent_messages"], 1)
            self.assertEqual(receipt["stop_reason"], "interrupted")
            self.assertEqual(receipt["mode"], "active")

    def test_typed_no_eligible_task_never_invokes_sender(self):
        with tempfile.TemporaryDirectory(dir="/tmp") as tmp:
            root = Path(tmp)
            started = time.time()
            grant = {"grant_version": 1, "task_id": "dot-coordinator-separated-20261007",
                     "account_id": "first", "action": "coordination_message", "max_messages": 12,
                     "min_interval_secs": 3600, "activated_at_epoch": started,
                     "expiry_epoch": started + 900.0}
            grant_path = root / "grant.json"
            grant_path.write_text(json.dumps(grant))
            grant_path.chmod(0o400)
            grant_sha = hashlib.sha256(grant_path.read_bytes()).hexdigest()
            key = ["github.com", "example-org/test-repo", "test", "7"]
            source_binding = {"source_id": "test-repo", "task_composite_key": key,
                              "record_version": "2026-10-07T00:00:00Z",
                              "record_digest": "a" * 64}
            snapshot = {"candidate_bindings": [{"task_id": "task-7",
                                                "source_binding": source_binding}]}
            config = {"task_id": "dot-coordinator-separated-20261007",
                      "authority": "Continue the fixture task.",
                      "accounts": [{"account": "first", "grant_file": str(grant_path),
                                    "grant_sha256": grant_sha}]}
            packet = {"schema_version": 1, "task_id": None, "event_id": "event-7",
                      "authority": {"instruction": config["authority"],
                                    "source": "local_operator_pilot"},
                      "snapshot": {}, "previous_dot_reply": "",
                      "dialogue_stage": "inventory", "phase": "inventory_due",
                      "candidate_bindings": snapshot["candidate_bindings"],
                      "source_binding": None,
                      "grant_binding": {"grant_version": 1, "grant_sha256": grant_sha},
                      "correlation": None}
            no_eligible = {"schema_version": 1, "event_id": "event-7", "task_id": None,
                           "outcome": "no_eligible_task", "stage": "inventory",
                           "source_binding": None, "grant_binding": packet["grant_binding"],
                           "correlation": None,
                           "judgment": {"assessment": "not_blocked",
                                        "safe_next_action": "wait for a viable task"},
                           "blockers": [], "action": "no_action", "message": None}
            with mock.patch("modules.driver_adapter.DriverAdapter") as adapter, \
                    mock.patch.object(coordinator_portfolio, "call_sender") as sender:
                adapter.return_value.decide.return_value = {
                    "status": "ok", "decision": no_eligible,
                }
                outcome = coordinator_portfolio.run_pilot_slot(
                    config, {"account_index": 0, "event_id": "event-7"},
                    {"dialogue": {"0": "inventory"}}, snapshot, root, "agy", "unused",
                    time.monotonic() + 600,
                )
            self.assertEqual(outcome["outcome"], "no_eligible_task")
            sender.assert_not_called()

    def test_source_change_after_draft_passes_callback_to_sender(self):
        with tempfile.TemporaryDirectory(dir="/tmp") as tmp:
            root = Path(tmp)
            started = time.time()
            grant = {"grant_version": 1, "task_id": "dot-coordinator-separated-20261007",
                     "account_id": "first", "action": "coordination_message", "max_messages": 12,
                     "min_interval_secs": 3600, "activated_at_epoch": started,
                     "expiry_epoch": started + 900}
            grant_path = root / "grant.json"
            grant_path.write_text(json.dumps(grant))
            grant_path.chmod(0o400)
            grant_sha = hashlib.sha256(grant_path.read_bytes()).hexdigest()
            binding = {"source_id": "test-repo",
                       "task_composite_key": ["github.com", "example-org/test-repo", "test", "7"],
                       "record_version": "2026-10-07T00:00:00Z", "record_digest": "a" * 64}
            task_id = json.dumps(["test-repo", *binding["task_composite_key"]],
                                 separators=(",", ":"))
            candidate = {"task_id": task_id, "source_binding": binding}
            snapshot = {"candidate_bindings": [candidate]}
            config = {"task_id": "dot-coordinator-separated-20261007",
                      "authority": "Continue the fixture task.",
                      "accounts": [{"account": "first", "grant_file": str(grant_path),
                                    "grant_sha256": grant_sha}]}
            decision = {"schema_version": 1, "event_id": "event-8", "task_id": task_id,
                        "outcome": "send_proposal", "stage": "inventory",
                        "source_binding": binding,
                        "grant_binding": {"grant_version": 1, "grant_sha256": grant_sha},
                        "correlation": None,
                        "judgment": {"assessment": "unknown", "safe_next_action": "ask Dot"},
                        "blockers": [], "action": "send", "message": "Request evidence."}
            changed = dict(binding, record_digest="c" * 64)
            with mock.patch("modules.driver_adapter.DriverAdapter") as adapter, \
                    mock.patch.object(coordinator_portfolio, "call_sender") as sender:
                adapter.return_value.decide.return_value = {
                    "status": "ok", "decision": decision,
                }
                def fake_call_sender(argv, event_id, message, source_callback=None):
                    self.assertIsNotNone(source_callback)
                    ok, reason = source_callback()
                    self.assertFalse(ok)
                    self.assertEqual(reason, "source_changed_after_draft")
                    return {"outcome": "no_action", "reason": reason, "delivery_verified": False}

                sender.side_effect = fake_call_sender
                outcome = coordinator_portfolio.run_pilot_slot(
                    config, {"account_index": 0, "event_id": "event-8"},
                    {"dialogue": {"0": "inventory"}}, snapshot, root, "agy", "unused",
                    time.monotonic() + 1000,
                    source_receipt_reader=lambda expected, timeout: (changed, "ok"),
                )
            self.assertEqual(outcome, {"outcome": "no_action",
                                       "reason": "source_changed_after_draft",
                                       "delivery_verified": False})
            sender.assert_called_once()

    def test_fake_transport_reports_prepared_source_changes_warmup_aborts_without_click(self):
        import shlex
        with tempfile.TemporaryDirectory(dir="/tmp") as tmp:
            root = Path(tmp)
            started = time.time()
            grant = {
                "grant_version": 1,
                "task_id": "dot-coordinator-separated-20261007",
                "account_id": "first",
                "action": "coordination_message",
                "max_messages": 12,
                "min_interval_secs": 3600,
                "activated_at_epoch": started,
                "expiry_epoch": started + 900,
            }
            grant_path = root / "grant.json"
            grant_path.write_text(json.dumps(grant))
            grant_path.chmod(0o400)
            grant_sha = hashlib.sha256(grant_path.read_bytes()).hexdigest()

            binding = {
                "source_id": "test-repo",
                "task_composite_key": ["github.com", "example-org/test-repo", "test", "7"],
                "record_version": "2026-10-07T00:00:00Z",
                "record_digest": "a" * 64,
            }
            task_id = json.dumps(["test-repo", *binding["task_composite_key"]], separators=(",", ":"))
            candidate = {"task_id": task_id, "source_binding": binding}
            snapshot = {"candidate_bindings": [candidate]}
            config = {
                "task_id": "dot-coordinator-separated-20261007",
                "authority": "Continue the fixture task.",
                "accounts": [{"account": "first", "grant_file": str(grant_path), "grant_sha256": grant_sha}],
            }
            decision = {
                "schema_version": 1,
                "event_id": "event-abort-test",
                "task_id": task_id,
                "outcome": "send_proposal",
                "stage": "inventory",
                "source_binding": binding,
                "grant_binding": {"grant_version": 1, "grant_sha256": grant_sha},
                "correlation": None,
                "judgment": {"assessment": "unknown", "safe_next_action": "ask Dot"},
                "blockers": [],
                "action": "send",
                "message": "Request evidence.",
            }

            click_marker = root / "clicked.txt"
            abort_marker = root / "aborted.txt"
            prepared_marker = root / "prepared.txt"
            fake_transport = root / "fake_transport.sh"
            fake_transport.write_text(
                "#!/usr/bin/env bash\n"
                f"echo 'prepared {PREPARED_NONCE}' > {shlex.quote(str(prepared_marker))}\n"
                f"printf 'prepared {PREPARED_NONCE}\\n'\n"
                "read -t 5 -r cmd || cmd='timeout'\n"
                "case \"$cmd\" in\n"
                f"  'commit {PREPARED_NONCE}')\n"
                f"    echo 'clicked' > {shlex.quote(str(click_marker))}\n"
                "    echo 'DOT_SENT_VERIFIED'\n"
                "    exit 0\n"
                "    ;;\n"
                "  *)\n"
                f"    echo \"$cmd\" > {shlex.quote(str(abort_marker))}\n"
                "    exit 0\n"
                "    ;;\n"
                "esac\n"
            )
            fake_transport.chmod(0o700)

            changed_binding = dict(binding, record_digest="b" * 64)
            with mock.patch("modules.driver_adapter.DriverAdapter") as adapter:
                adapter.return_value.decide.return_value = {
                    "status": "ok",
                    "decision": decision,
                }
                outcome = coordinator_portfolio.run_pilot_slot(
                    config,
                    {"account_index": 0, "event_id": "event-abort-test"},
                    {"dialogue": {"0": "inventory"}},
                    snapshot,
                    root,
                    "agy",
                    str(fake_transport),
                    time.monotonic() + 1000,
                    source_receipt_reader=lambda expected, timeout: (changed_binding, "ok"),
                )

            self.assertTrue(prepared_marker.exists(), "Transport must have reported prepared")
            self.assertTrue(abort_marker.exists(), "Coordinator must have sent abort to transport")
            self.assertIn("abort", abort_marker.read_text())
            self.assertFalse(click_marker.exists(), "Click must never occur on aborted transport")
            self.assertEqual(
                outcome,
                {"outcome": "no_action", "reason": "source_changed_after_draft", "delivery_verified": False},
            )

    def test_wrapper_computes_outer_grace_period(self):
        # Inspect dot-portfolio-coordinator-wrapper.sh to ensure observe duration has + 120s grace
        with open(WRAPPER_SCRIPT, "r") as f:
            wrapper_content = f.read()
        self.assertIn("DEADLINE_SECS=$(( DURATION + 120 ))", wrapper_content)


if __name__ == "__main__":
    unittest.main()
