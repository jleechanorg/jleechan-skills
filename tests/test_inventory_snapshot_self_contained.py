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
import os
import subprocess
import sys
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
            # A captured empty document attests its own digest. Only a row that
            # was never read carries a blank one.
            self.assertEqual(empty["content_sha256"], digest(b""))

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


class DeterministicAuditTest(unittest.TestCase):
    """The same frozen snapshot must classify the same way in any process."""

    CLOSURE_SCRIPT = """
import json, sys
sys.path.insert(0, {root!r})
from scripts.audit_command_skill_usage import compute_bfs_closure
parents = [f"parent-{{i}}" for i in range(12)]
edges = {{p: {{"shared-target"}} for p in parents}}
_, _, _, reasons = compute_bfs_closure(
    set(), set(parents), set(), set(parents) | {{"shared-target"}},
    {{}}, {{}}, edges, {{}}, {{}},
)
print(json.dumps(reasons["shared-target"]))
"""

    def _reasons(self, seed: str) -> str:
        proc = subprocess.run(
            [sys.executable, "-c", self.CLOSURE_SCRIPT.format(root=str(REPO_ROOT))],
            capture_output=True,
            text=True,
            env=dict(os.environ, PYTHONHASHSEED=seed),
            cwd=str(REPO_ROOT),
            check=True,
        )
        return proc.stdout.strip()

    def test_reachability_reasons_do_not_depend_on_hash_randomization(self):
        """Twelve parents claim one node; which one wins must not be luck.

        Reachability reasons record the first parent to reach a node, so
        iterating unordered sets made attribution depend on per-process string
        hash randomization: two audits of one frozen snapshot could disagree.
        """
        results = {self._reasons(seed) for seed in ("0", "1", "7", "12345", "99991")}
        self.assertEqual(
            len(results),
            1,
            f"reachability attribution varied with PYTHONHASHSEED: {results}",
        )
        self.assertEqual(
            json.loads(results.pop())[0],
            "referenced by skill:parent-0",
            "attribution should follow sorted order, not set order",
        )


class EmptyDocumentAttestationTest(unittest.TestCase):
    """An empty document is still a document: its digest must round-trip.

    The first cut rejected the empty document that carried its own correct
    digest while accepting the one that carried none — the rule inverted
    exactly where it should have been strictest.
    """

    EMPTY_DIGEST = digest(b"")

    def _row(self, path: Path, sha: str | None) -> dict:
        row = {
            "skill": "gcp",
            "path": str(path),
            "content_encoding": "base64",
            "content_b64": "",
            "content_captured": True,
        }
        if sha is not None:
            row["content_sha256"] = sha
        return row

    def test_empty_document_with_its_own_digest_is_accepted(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "SKILL.md"
            path.write_bytes(b"")
            self.assertEqual(inventory_text(self._row(path, self.EMPTY_DIGEST)), "")

    def test_empty_document_with_absent_or_blank_digest_is_accepted(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "SKILL.md"
            path.write_bytes(b"")
            for sha in (None, ""):
                with self.subTest(content_sha256=sha):
                    self.assertEqual(inventory_text(self._row(path, sha)), "")

    def test_empty_document_with_a_foreign_digest_fails_closed(self):
        """An empty payload claiming some other document's digest is drift."""
        with TemporaryDirectory() as directory:
            path = Path(directory) / "SKILL.md"
            path.write_bytes(b"")
            row = self._row(path, digest(b"# a completely different document\n"))
            with self.assertRaisesRegex(ValueError, "inventory content drift"):
                inventory_text(row)

    def test_capture_attests_the_empty_document(self):
        """Capture emits the empty digest so both halves spell it the same way."""
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "empty.md").write_bytes(b"")
            row = next(r for r in command_inventory(root) if r["command"] == "empty")
            self.assertEqual(row["content_sha256"], self.EMPTY_DIGEST)
            self.assertTrue(row["content_captured"])
            self.assertEqual(inventory_text(row), "")

    def test_legacy_blank_digest_snapshots_still_round_trip(self):
        """Snapshots written before capture attested the empty document."""
        with TemporaryDirectory() as directory:
            root = Path(directory)
            skill = root / "demo" / "SKILL.md"
            skill.parent.mkdir(parents=True)
            skill.write_bytes(b"")
            rows = skill_inventory(inventory_roots=[{"scope": "home", "path": str(root)}])
            legacy = dict(next(r for r in rows if r["skill"] == "demo"))
            legacy["content_sha256"] = ""
            legacy["hash"] = ""
            manifest = build_audit_fixture(root, events=[], skills=[legacy])
            audit(manifest, root / "out")
            audited = json.loads((root / "out/skill-usage-30d.json").read_text())["skills"]
            self.assertEqual([r["skill"] for r in audited], ["demo"])


class UncapturedRowFailsClosedTest(unittest.TestCase):
    """`content_captured: False` must not become a validation bypass."""

    def test_uncaptured_row_carrying_a_payload_fails_closed(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "SKILL.md"
            path.write_bytes(b"# real\n")
            row = {
                "skill": "gcp",
                "path": str(path),
                "content_encoding": "base64",
                "content_b64": base64.b64encode(b"SMUGGLED PAYLOAD\n").decode("ascii"),
                "content_sha256": "",
                "content_captured": False,
            }
            with self.assertRaisesRegex(ValueError, "inventory content drift"):
                inventory_text(row)

    def test_uncaptured_row_carrying_a_digest_fails_closed(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "SKILL.md"
            path.write_bytes(b"# real\n")
            row = {
                "skill": "gcp",
                "path": str(path),
                "content_encoding": "base64",
                "content_b64": "",
                "content_sha256": digest(b"# real\n"),
                "content_captured": False,
            }
            with self.assertRaisesRegex(ValueError, "inventory content drift"):
                inventory_text(row)

    def test_genuinely_uncaptured_row_still_returns_empty_without_a_live_read(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "SKILL.md"
            path.write_bytes(b"content that appeared after capture\n")
            row = {
                "skill": "gcp",
                "path": str(path),
                "content_encoding": "base64",
                "content_b64": "",
                "content_sha256": "",
                "content_captured": False,
            }
            self.assertEqual(inventory_text(row), "")


class UncapturedInventoryIsCountedTest(unittest.TestCase):
    def test_uncaptured_rows_are_reported_not_silently_empty(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "SKILL.md"
            path.write_bytes(b"# present at audit time\n")
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
            payload = json.loads((root / "out/skill-usage-30d.json").read_text())
            self.assertEqual(payload["uncaptured_inventory_count"], 1)
            self.assertEqual(payload["uncaptured_inventory_paths"], [str(path)])

    def test_fully_captured_snapshot_reports_zero_uncaptured(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "SKILL.md"
            body = b"# body\n"
            path.write_bytes(body)
            manifest = build_audit_fixture(
                root, events=[], skills=[_frozen_skill(path, body)]
            )
            audit(manifest, root / "out")
            payload = json.loads((root / "out/skill-usage-30d.json").read_text())
            self.assertEqual(payload["uncaptured_inventory_count"], 0)
            self.assertEqual(payload["uncaptured_inventory_paths"], [])


class PytestPathContractTest(unittest.TestCase):
    def test_pytest_ini_declares_repo_root_on_the_import_path(self):
        """``pytest.ini`` must put the repo root on the import path.

        Without it, collection of ``tests/test_archive_dependency_contract.py``
        fails on ``ModuleNotFoundError: No module named 'scripts'``.  This case
        asserts the declaration; the suite actually running under a bare
        ``pytest`` is what demonstrates the effect.
        """
        parser = configparser.ConfigParser()
        parser.read(REPO_ROOT / "pytest.ini")
        self.assertIn("pythonpath", parser["pytest"])
        self.assertIn(".", parser["pytest"]["pythonpath"].split())


if __name__ == "__main__":
    unittest.main()
