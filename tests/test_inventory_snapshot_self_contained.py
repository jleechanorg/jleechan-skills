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

from scripts.audit_command_skill_usage import audit, digest, inventory_text
from scripts.capture_command_skill_usage import command_inventory, skill_inventory
from tests.test_command_skill_usage_audit import build_audit_fixture

REPO_ROOT = Path(__file__).resolve().parents[1]


def _frozen_skill(path: Path, content: bytes) -> dict:
    return {
        "skill": "gcp",
        "path": str(path),
        "content_sha256": digest(content) if content else "",
        "content_encoding": "base64",
        "content_b64": base64.b64encode(content).decode("ascii"),
        "content_captured": True,
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

    def test_bytes_without_a_declared_digest_fail_closed(self):
        """Frozen bytes are only trusted when the row also attests their digest."""
        for missing in ({}, {"content_sha256": ""}):
            with self.subTest(missing=missing), TemporaryDirectory() as directory:
                root = Path(directory)
                path = root / "SKILL.md"
                captured = b"# captured bytes\n"
                path.write_bytes(captured)
                skill = _frozen_skill(path, captured)
                skill.pop("content_sha256")
                skill.update(missing)
                manifest = build_audit_fixture(root, events=[], skills=[skill])
                with self.assertRaisesRegex(ValueError, "missing attestation"):
                    audit(manifest, root / "out")

    def test_declared_digest_without_bytes_fails_closed(self):
        """A digest with an empty payload is an inconsistent row, not an empty file."""
        with TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "SKILL.md"
            path.write_bytes(b"# captured bytes\n")
            skill = _frozen_skill(path, b"")
            skill["content_sha256"] = digest(b"# captured bytes\n")
            manifest = build_audit_fixture(root, events=[], skills=[skill])
            with self.assertRaisesRegex(ValueError, "inventory content drift"):
                audit(manifest, root / "out")

    def test_empty_file_is_frozen_and_never_reread(self):
        """A zero-byte file is frozen too; it must not fall back to a live read."""
        with TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "SKILL.md"
            path.write_bytes(b"")
            manifest = build_audit_fixture(
                root, events=[], skills=[_frozen_skill(path, b"")]
            )
            path.write_bytes(b"rewritten after capture\n")
            audit(manifest, root / "out")
            rows = json.loads((root / "out/skill-usage-30d.json").read_text())["skills"]
            self.assertEqual([row["skill"] for row in rows], ["gcp"])

    def test_uncaptured_row_does_not_borrow_live_bytes(self):
        """A file capture could not read attests nothing and reads no disk."""
        with TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "SKILL.md"
            path.write_bytes(b"content that appeared after capture\n")
            skill = {
                "skill": "gcp",
                "path": str(path),
                "content_sha256": "",
                "content_encoding": "base64",
                "content_b64": "",
                "content_captured": False,
            }
            manifest = build_audit_fixture(root, events=[], skills=[skill])
            audit(manifest, root / "out")
            rows = json.loads((root / "out/skill-usage-30d.json").read_text())["skills"]
            self.assertEqual([row["skill"] for row in rows], ["gcp"])

    def test_symlink_retarget_does_not_break_a_frozen_row(self):
        """Symlink identity is attested at capture; the live target is not consulted."""
        with TemporaryDirectory() as directory:
            root = Path(directory)
            original = root / "original.md"
            original.write_bytes(b"---\nname: gcp\n---\n# original\n")
            link = root / "SKILL.md"
            link.symlink_to(original)
            skill = _frozen_skill(link, original.read_bytes())
            skill["resolved_target"] = str(original.resolve())
            manifest = build_audit_fixture(root, events=[], skills=[skill])

            other = root / "other.md"
            other.write_bytes(b"# somewhere else\n")
            link.unlink()
            link.symlink_to(other)

            audit(manifest, root / "out")
            rows = json.loads((root / "out/skill-usage-30d.json").read_text())["skills"]
            self.assertEqual([row["skill"] for row in rows], ["gcp"])

    def test_unknown_content_encoding_fails_closed(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "SKILL.md"
            captured = b"# captured bytes\n"
            path.write_bytes(captured)
            skill = _frozen_skill(path, captured)
            skill["content_encoding"] = "rot13"
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
            (root / "empty.md").write_bytes(b"")
            rows = {r["command"]: r for r in command_inventory(root)}
            row = rows["demo"]
            self.assertEqual(row["content_encoding"], "base64")
            self.assertTrue(row["content_captured"])
            self.assertEqual(base64.b64decode(row["content_b64"]), body)
            self.assertEqual(digest(base64.b64decode(row["content_b64"])), row["content_sha256"])

            empty = rows["empty"]
            self.assertEqual(empty["content_encoding"], "base64")
            self.assertTrue(empty["content_captured"])
            self.assertEqual(empty["content_b64"], "")
            self.assertEqual(empty["content_sha256"], "")

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

    def test_captured_empty_file_never_yields_post_capture_bytes(self):
        """A zero-byte file captured today must not read as tomorrow's content.

        This is the gap review found: an empty file was not frozen at all, so
        the audit silently used whatever the filesystem held at audit time.
        The assertion is on ``inventory_text`` directly because that is where
        the substitution happened.
        """
        with TemporaryDirectory() as directory:
            root = Path(directory)
            probe = root / "skills" / "probe" / "SKILL.md"
            probe.parent.mkdir(parents=True)
            probe.write_bytes(b"")
            row = next(
                r
                for r in skill_inventory(
                    inventory_roots=[{"scope": "home", "path": str(root / "skills")}]
                )
                if r["skill"] == "probe"
            )

            probe.write_bytes(b"Read `.claude/skills/target/SKILL.md`\n")

            self.assertEqual(
                inventory_text(row),
                "",
                "audit used post-capture live bytes from a zero-byte inventory file",
            )

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
