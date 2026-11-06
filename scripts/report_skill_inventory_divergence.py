#!/usr/bin/env python3
"""Report divergence between a portable bundle set and the .claude/skills source.

The 2026-10-13 consolidation audit found that portable/skills/** was NOT a duplicate of
.claude/skills/** : most entries diverged and several existed only in the portable set.
Any plan that assumes "portable == duplicate" is wrong; run this first.

Usage: python3 scripts/report_skill_inventory_divergence.py [--json]
Exit code 0 always (report only); the contract test pins the current counts.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "portable" / "manifest.json"


def digest(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _pkg_files(base: Path) -> set[str]:
    """Every file in a skill package, relative to the package dir (whole-package compare)."""
    if not base.exists():
        return set()
    ignore = ("__pycache__", ".pyc", ".pyo", ".DS_Store")
    return {p.relative_to(base).as_posix() for p in base.rglob("*")
            if p.is_file() and not any(k in p.as_posix() for k in ignore)}


def report() -> dict:
    if not MANIFEST.exists():
        return {"status": "no-portable-manifest"}
    names = json.loads(MANIFEST.read_text())["skills"]
    missing, identical, differing = [], [], []
    detail = {}
    for name in names:
        src = ROOT / "portable" / "skills" / name
        snap = ROOT / ".claude" / "skills" / name
        pf, cf = _pkg_files(src), _pkg_files(snap)
        if not snap.exists():
            missing.append(name)
            detail[name] = {"portable_files": sorted(pf), "claude_files": []}
            continue
        # whole-package: any file differing, added, or removed counts as divergence
        changed = sorted(f for f in (pf | cf) if f not in pf or f not in cf
                         or digest(src / f) != digest(snap / f))
        detail[name] = {"portable_files": sorted(pf), "claude_files": sorted(cf), "changed_files": changed}
        (identical if not changed else differing).append(name)
    return {
        "status": "ok",
        "portable_skills": len(names),
        "missing_in_claude_skills": sorted(missing),
        "identical_bodies": sorted(identical),
        "differing_bodies": sorted(differing),
        "per_skill": detail,
    }


LEDGER = ROOT / "docs" / "superpowers" / "skill-inventory-dispositions.json"


def write_ledger(r: dict) -> dict:
    """Evidence-derived disposition ledger: one row per portable skill, unresolved by default."""
    allowed = ["keep-claude", "keep-portable", "merge", "drop"]
    existing = {}
    if LEDGER.exists():
        for e in json.loads(LEDGER.read_text()).get("entries", []):
            existing[e["name"]] = e
    entries = []
    for name in sorted(r["missing_in_claude_skills"] + r["identical_bodies"] + r["differing_bodies"]):
        status = ("portable-only" if name in r["missing_in_claude_skills"]
                  else "identical" if name in r["identical_bodies"] else "divergent")
        prev = existing.get(name, {})
        entries.append({
            "name": name,
            "evidence": {"status": status,
                         "changed_files": r["per_skill"].get(name, {}).get("changed_files", [])},
            "disposition": prev.get("disposition"),
            "reason": prev.get("reason"),
            "resolved": bool(prev.get("resolved", False)),
        })
    doc = {"format": "jleechan-skill-dispositions-v1",
           "generated_from": {"manifest": "portable/manifest.json",
                              "tool": "scripts/report_skill_inventory_divergence.py"},
           "allowed_dispositions": allowed,
           "entries": entries}
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    LEDGER.write_text(json.dumps(doc, indent=2) + "\n")
    return doc


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--write-ledger", action="store_true")
    a = ap.parse_args()
    r = report()
    if a.write_ledger and r["status"] == "ok":
        doc = write_ledger(r)
        print(f"ledger written: {LEDGER} ({len(doc['entries'])} entries)")
        return 0
    if a.json:
        print(json.dumps(r, indent=2))
        return 0
    if r["status"] != "ok":
        print(f"portable manifest absent ({r['status']}) - nothing to reconcile")
        return 0
    print(f"portable skills: {r['portable_skills']}")
    print(f"  MISSING from .claude/skills ({len(r['missing_in_claude_skills'])}): {r['missing_in_claude_skills']}")
    print(f"  IDENTICAL bodies            ({len(r['identical_bodies'])}): {r['identical_bodies']}")
    print(f"  DIFFERING packages          ({len(r['differing_bodies'])}): {r['differing_bodies']}")
    print("\n=> portable/** is a DIVERGENT VARIANT SET, not a duplicate. Reconcile before collapsing.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
