import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from pr_nudger_discovery import discover_owners


class DiscoveryTest(unittest.TestCase):
    def test_exact_paths_and_all_distinct_surfaces(self):
        with tempfile.TemporaryDirectory() as tmp:
            cwd = Path(tmp).resolve()
            surfaces = [{"ref": f"surface:{n}", "type": "terminal"} for n in range(1, 6)]
            surfaces.append({"ref": "surface:6", "type": "browser"})
            tree = {"windows": [{"workspaces": [{"ref": "workspace:1", "panes": [
                {"surfaces": surfaces}
            ]}]}]}
            binding = {"kind": "codex", "checkpoint_id": "session", "cwd": str(cwd)}

            def cmux(args, **kwargs):
                if args == ("cmux", "--id-format", "both", "tree", "--all", "--json"):
                    return json.dumps(tree)
                ws, sf = args[5], args[7]
                self.assertEqual(args, ("cmux", "surface", "resume", "show", "--workspace",
                                        ws, "--surface", sf, "--json"))
                self.assertNotEqual(sf, "surface:6")
                if sf == "surface:5":
                    raise subprocess.TimeoutExpired(args, 3)
                record = dict(binding)
                if sf == "surface:3":
                    record["cwd"] = str(cwd / "child")
                reply_ref = "surface:1" if sf == "surface:4" else sf
                restored = dict(record, working_directory=record["cwd"], launch_command={
                    "environment": {"CODEX_HOME": str(cwd / "profile")}
                })
                return json.dumps({"workspace_ref": ws, "surface_ref": reply_ref,
                                   "resume_binding": record, "restore_record": restored})

            with patch("pr_nudger_discovery.subprocess.check_output", side_effect=cmux):
                owners = discover_owners([cwd])
                with self.assertRaises(ValueError):
                    discover_owners([cwd], strict=True)
            self.assertEqual(owners[str(cwd)][0]["profile_dir"], str(cwd / "profile"))
            self.assertEqual(list(owners), [str(cwd)])
            self.assertEqual([o["surface"] for o in owners[str(cwd)]], ["surface:1", "surface:2"])
            self.assertTrue(all(o["session"] == "session" and o["cmux_discovered"]
                                and not o.get("headless_resume") for o in owners[str(cwd)]))

    def test_unreachable_inventory_yields_no_dynamic_binding(self):
        with patch("pr_nudger_discovery.subprocess.check_output", side_effect=FileNotFoundError):
            self.assertEqual(discover_owners([Path.cwd()]), {})
            with self.assertRaises(ValueError):
                discover_owners([Path.cwd()], strict=True)
