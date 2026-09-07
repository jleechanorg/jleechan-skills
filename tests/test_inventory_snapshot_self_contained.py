"""The inventory snapshot must be a self-contained frozen input.

The audit declares ``inventory-snapshot.json`` a frozen, hash-pinned input, but
``inventory_text`` re-read every inventory file from the live filesystem and
aborted the whole run on any difference.  Capture and audit are separate phases
minutes apart, so any concurrent write anywhere under the inventory roots
destroyed the run.  These cases pin the frozen-input contract: the snapshot
carries the bytes it attests, and the audit reads them from the snapshot.
"""

from __future__ import annotations

import base64
import configparser
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from scripts.audit_command_skill_usage import audit, digest
from scripts.capture_command_skill_usage import command_inventory, skill_inventory
from tests.test_command_skill_usage_audit import build_audit_fixture

REPO_ROOT = Path(__file__).resolve().parents[1]


def _frozen_skill(path: Path, content: bytes) -> dict:
    return {
        "skill": "gcp",
        "path": str(path),
        "content_sha256": digest(content),
        "content_encoding": "base64",
        "content_b64": base64.b64encode(content).decode("ascii"),
    }


class InventorySnapshotSelfContainedTest(unittest.TestCase):
    def test_frozen_content_survives_concurrent_rewrite(self):
        """A live write after capture must not abort the audit."""
        with TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "SKILL.md"
            captured = b"---\nname: gcp\n---\n# captured bytes\n"
            path.write_bytes(captured)
            manifest = build_audit_fixture(
                root, events=[], skills=[_frozen_skill(path, captured)]
            )

            # A concurrent writer touches the live file between capture and audit.
            path.write_bytes(b"rewritten by a concurrent session\n")

            audit(manifest, root / "out")
            rows = json.loads((root / "out/skill-usage-30d.json").read_text())["skills"]
            self.assertEqual([row["skill"] for row in rows], ["gcp"])

    def test_frozen_content_must_match_declared_hash(self):
        """Snapshot bytes that disagree with the declared digest fail closed."""
        with TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "SKILL.md"
            captured = b"# captured bytes\n"
            path.write_bytes(captured)
            skill = _frozen_skill(path, captured)
            skill["content_b64"] = base64.b64encode(b"tampered\n").decode("ascii")
            manifest = build_audit_fixture(root, events=[], skills=[skill])
            with self.assertRaisesRegex(ValueError, "inventory content drift"):
                audit(manifest, root / "out")

    def test_undecodable_frozen_content_fails_closed(self):
        """A malformed base64 payload is drift, not a silent empty document."""
        with TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "SKILL.md"
            captured = b"# captured bytes\n"
            path.write_bytes(captured)
            skill = _frozen_skill(path, captured)
            skill["content_b64"] = "not valid base64!!"
            manifest = build_audit_fixture(root, events=[], skills=[skill])
            with self.assertRaisesRegex(ValueError, "inventory content drift"):
                audit(manifest, root / "out")

    def test_legacy_snapshot_without_content_still_fails_closed_on_drift(self):
        """Historical snapshots carry no bytes and keep the live-read guard."""
        with TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "SKILL.md"
            path.write_text("original")
            manifest = build_audit_fixture(
                root,
                events=[],
                skills=[
                    {
                        "skill": "gcp",
                        "path": str(path),
                        "content_sha256": digest(path.read_bytes()),
                    }
                ],
            )
            path.write_text("changed after capture")
            with self.assertRaisesRegex(ValueError, "inventory content drift"):
                audit(manifest, root / "out")

    def test_legacy_snapshot_without_content_still_reads_live_bytes(self):
        """An unchanged legacy snapshot keeps working against the live tree."""
        with TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "SKILL.md"
            path.write_text("---\nname: gcp\n---\n# body\n")
            manifest = build_audit_fixture(
                root,
                events=[],
                skills=[
                    {
                        "skill": "gcp",
                        "path": str(path),
                        "content_sha256": digest(path.read_bytes()),
                    }
                ],
            )
            audit(manifest, root / "out")
            rows = json.loads((root / "out/skill-usage-30d.json").read_text())["skills"]
            self.assertEqual([row["skill"] for row in rows], ["gcp"])


class CaptureEmbedsInventoryContentTest(unittest.TestCase):
    def test_command_inventory_embeds_verifiable_content(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            body = b"---\ndescription: /demo\n---\n# /demo\n"
            (root / "demo.md").write_bytes(body)
            row = next(r for r in command_inventory(root) if r["command"] == "demo")
            self.assertEqual(row["content_encoding"], "base64")
            self.assertEqual(base64.b64decode(row["content_b64"]), body)
            self.assertEqual(digest(base64.b64decode(row["content_b64"])), row["content_sha256"])

    def test_skill_inventory_embeds_verifiable_content(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            skill = root / "demo" / "SKILL.md"
            skill.parent.mkdir(parents=True)
            body = b"---\nname: demo\n---\n# demo\n"
            skill.write_bytes(body)
            rows = skill_inventory(inventory_roots=[{"scope": "home", "path": str(root)}])
            row = next(r for r in rows if r["skill"] == "demo")
            self.assertEqual(row["content_encoding"], "base64")
            self.assertEqual(base64.b64decode(row["content_b64"]), body)
            self.assertEqual(digest(base64.b64decode(row["content_b64"])), row["content_sha256"])

    def test_captured_snapshot_audits_after_the_source_tree_is_rewritten(self):
        """End-to-end: capture then rewrite every source file, audit still runs."""
        with TemporaryDirectory() as directory:
            root = Path(directory)
            skill = root / "skills" / "demo" / "SKILL.md"
            skill.parent.mkdir(parents=True)
            skill.write_bytes(b"---\nname: demo\n---\n# demo\n")
            rows = skill_inventory(
                inventory_roots=[{"scope": "home", "path": str(root / "skills")}]
            )
            manifest = build_audit_fixture(root, events=[], skills=rows)
            skill.write_bytes(b"rewritten\n")
            audit(manifest, root / "out")
            audited = json.loads((root / "out/skill-usage-30d.json").read_text())["skills"]
            self.assertEqual([row["skill"] for row in audited], ["demo"])


class PytestPathContractTest(unittest.TestCase):
    def test_pytest_ini_declares_repo_root_on_the_import_path(self):
        """Bare ``pytest`` must collect; tests import the ``scripts`` package."""
        parser = configparser.ConfigParser()
        parser.read(REPO_ROOT / "pytest.ini")
        self.assertIn("pythonpath", parser["pytest"])
        self.assertIn(".", parser["pytest"]["pythonpath"].split())


if __name__ == "__main__":
    unittest.main()
