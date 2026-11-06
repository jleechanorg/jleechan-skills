"""Fail-closed contract for the portable-skill disposition ledger.

Replaces pinning the raw 7/19/3 counts (an audit snapshot that every reconciliation PR would
have to edit). Instead: every portable manifest entry must have a disposition row, and the
portable tree may only be deleted once every row is resolved. Reviewers (Codex + Opus)
required this guard on 2026-10-13.
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "portable" / "manifest.json"
LEDGER = ROOT / "docs" / "superpowers" / "skill-inventory-dispositions.json"


class SkillInventoryDispositionsContract(unittest.TestCase):
    def ledger(self) -> dict:
        if not LEDGER.exists():
            self.fail(f"missing disposition ledger {LEDGER}; run "
                      "scripts/report_skill_inventory_divergence.py --write-ledger")
        return json.loads(LEDGER.read_text())

    def test_every_portable_skill_has_a_disposition_row(self):
        if not MANIFEST.exists():
            self.skipTest("portable manifest absent - ledger is the historical record")
        names = set(json.loads(MANIFEST.read_text())["skills"])
        rows = {e["name"] for e in self.ledger()["entries"]}
        self.assertEqual(set(), names - rows, "portable skills with no disposition row")

    def test_dispositions_are_from_the_allowed_set(self):
        d = self.ledger()
        for e in d["entries"]:
            if e["disposition"] is not None:
                self.assertIn(e["disposition"], d["allowed_dispositions"], e["name"])

    def test_portable_tree_removal_requires_every_row_resolved(self):
        """The deletion gate: if portable/** is gone, no row may still be unresolved."""
        if MANIFEST.exists():
            self.skipTest("portable bundle still present (pre-collapse)")
        unresolved = [e["name"] for e in self.ledger()["entries"] if not e.get("resolved")]
        self.assertEqual([], unresolved,
                         "portable/** was deleted with unresolved dispositions - each skill must "
                         "be keep-claude/keep-portable/merge/drop and resolved first")


if __name__ == "__main__":
    unittest.main()
