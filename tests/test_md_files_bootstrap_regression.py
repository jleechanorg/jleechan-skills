"""Regression tests for the md_files/ shared-policy bootstrap.

Locks in the three findings from the 2026-09-13 Codex review of PR #433:

1. **Idempotent re-run + mtime preservation**: re-running the bootstrap on a
   machine whose policy already matches the template must not create backups
   and must not bump the destination mtime.

2. **Path-with-spaces correctness**: when ``CODEX_HOME`` (or any path) contains
   whitespace, the bash function ``backup_and_copy`` must still back up the
   divergent existing file before overwriting. The earlier ``for pair in
   "src dst"; do set -- $pair; ...`` shape word-split on whitespace and
   silently skipped the AGENTS.md backup when ``CODEX_HOME`` had a space.

3. **Portability scan grep-error handling**: when ``grep`` exits with a code
   other than 0 or 1 (e.g. 2 — the target is a directory instead of a regular
   file), the scan must print ``scan: ERROR`` and a non-zero exit code, never
   ``portable: clean``. The earlier ``if grep ...; then rc=$?`` shape always
   captured the if-test result (0) and silently swallowed the grep error.
"""

import os
import re
import shutil
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
README_PATH = REPO_ROOT / "md_files" / "README.md"
SRC_DIR = REPO_ROOT / "md_files"


def _extract_bash_blocks(md_text: str) -> list[str]:
    """Pull every ```bash ... ``` block from a markdown file in order."""
    return re.findall(r"```bash\n(.*?)\n```", md_text, re.DOTALL)


def _run(script_text: str, env: dict, cwd: str | None = None) -> subprocess.CompletedProcess:
    """Write a one-shot bash wrapper and run it; return the completed process."""
    path = "/tmp/md_files_bootstrap_test.sh"
    with open(path, "w") as f:
        f.write("#!/usr/bin/env bash\nset +e\n" + script_text)
    os.chmod(path, 0o755)
    return subprocess.run(["bash", path], capture_output=True, text=True, env=env, cwd=cwd)


@unittest.skipUnless(README_PATH.exists(), "md_files/README.md not present")
class MdFilesBootstrapRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.readme = README_PATH.read_text()
        blocks = _extract_bash_blocks(cls.readme)
        # Bootstrap is the first bash block, scan is the second.
        cls.bootstrap = blocks[0].replace(
            "md_files/AGENTS.shared.md", str(SRC_DIR / "AGENTS.shared.md")
        ).replace(
            "md_files/CLAUDE.adapter.md", str(SRC_DIR / "CLAUDE.adapter.md")
        )
        cls.scan = blocks[1]

    # ----- Bootstrap: idempotent re-run preserves mtime -----

    def test_idempotent_rerun_preserves_mtime(self):
        home = tempfile.mkdtemp(prefix="md_bootstrap_idem_")
        try:
            env = os.environ.copy()
            env["HOME"] = home
            env.pop("CODEX_HOME", None)
            env.pop("CLAUDE_HOME", None)

            # First install.
            r1 = _run(self.bootstrap, env)
            self.assertEqual(r1.returncode, 0, f"first install failed: {r1.stderr}")
            ag = f"{home}/.codex/AGENTS.md"
            self.assertTrue(os.path.exists(ag))
            m1 = os.stat(ag).st_mtime

            # Sleep so a real mtime bump would be detectable.
            time.sleep(1.2)

            # Second install (identical content).
            r2 = _run(self.bootstrap, env)
            self.assertEqual(r2.returncode, 0, f"second install failed: {r2.stderr}")
            m2 = os.stat(ag).st_mtime

            self.assertEqual(
                m1, m2,
                "idempotent re-run bumped mtime (would break mtime-based watchers)",
            )

            # No backup files created on identical re-run.
            backups = [f for f in os.listdir(f"{home}/.codex") if ".bak." in f]
            self.assertEqual(backups, [], f"unexpected backups from identical re-run: {backups}")
        finally:
            shutil.rmtree(home, ignore_errors=True)

    # ----- Bootstrap: divergent file is backed up before overwrite -----

    def test_divergent_file_is_backed_up(self):
        home = tempfile.mkdtemp(prefix="md_bootstrap_bak_")
        try:
            env = os.environ.copy()
            env["HOME"] = home
            env.pop("CODEX_HOME", None)
            env.pop("CLAUDE_HOME", None)
            os.makedirs(f"{home}/.codex", exist_ok=True)
            os.makedirs(f"{home}/.claude", exist_ok=True)
            with open(f"{home}/.codex/AGENTS.md", "w") as f:
                f.write("LOCAL CODEX POLICY\n")
            with open(f"{home}/.claude/CLAUDE.md", "w") as f:
                f.write("LOCAL CLAUDE POLICY\n")

            r = _run(self.bootstrap, env)
            self.assertEqual(r.returncode, 0, f"bootstrap failed: {r.stderr}")

            codex_baks = [f for f in os.listdir(f"{home}/.codex") if ".bak." in f]
            claude_baks = [f for f in os.listdir(f"{home}/.claude") if ".bak." in f]
            self.assertEqual(len(codex_baks), 1, f"AGENTS.md backup missing: {codex_baks}")
            self.assertEqual(len(claude_baks), 1, f"CLAUDE.md backup missing: {claude_baks}")
            with open(f"{home}/.codex/{codex_baks[0]}") as f:
                self.assertEqual(f.read(), "LOCAL CODEX POLICY\n")
            with open(f"{home}/.claude/{claude_baks[0]}") as f:
                self.assertEqual(f.read(), "LOCAL CLAUDE POLICY\n")
        finally:
            shutil.rmtree(home, ignore_errors=True)

    # ----- Bootstrap: CODEX_HOME with whitespace (Codex Bug #2 regression) -----

    def test_codex_home_with_whitespace(self):
        home = tempfile.mkdtemp(prefix="md_bootstrap_space_")
        try:
            codex_dir = f"{home}/my codex"  # SPACE!
            claude_dir = f"{home}/claude"
            os.makedirs(codex_dir)
            os.makedirs(claude_dir)
            with open(f"{codex_dir}/AGENTS.md", "w") as f:
                f.write("LOCAL CODEX POLICY\n")
            with open(f"{claude_dir}/CLAUDE.md", "w") as f:
                f.write("LOCAL CLAUDE POLICY\n")

            env = os.environ.copy()
            env["HOME"] = home
            env["CODEX_HOME"] = codex_dir
            env["CLAUDE_HOME"] = claude_dir

            r = _run(self.bootstrap, env)
            self.assertEqual(r.returncode, 0, f"bootstrap failed: {r.stderr}")

            codex_baks = [f for f in os.listdir(codex_dir) if ".bak." in f]
            self.assertEqual(
                len(codex_baks), 1,
                "AGENTS.md backup skipped when CODEX_HOME contained a space — "
                "this is the Codex 2026-09-13 regression (set -- $pair word-splits)",
            )
        finally:
            shutil.rmtree(home, ignore_errors=True)

    # ----- Bootstrap: non-default CODEX_HOME rewires adapter import -----

    def test_non_default_codex_home_rewires_import(self):
        home = tempfile.mkdtemp(prefix="md_bootstrap_alt_")
        try:
            codex_dir = f"{home}/my_codex"
            claude_dir = f"{home}/claude"
            env = os.environ.copy()
            env["HOME"] = home
            env["CODEX_HOME"] = codex_dir
            env["CLAUDE_HOME"] = claude_dir

            r = _run(self.bootstrap, env)
            self.assertEqual(r.returncode, 0, f"bootstrap failed: {r.stderr}")

            ad = open(f"{claude_dir}/CLAUDE.md").read()
            self.assertIn(
                f"@{codex_dir}/AGENTS.md", ad,
                "non-default CODEX_HOME was not rewired into Claude's @import",
            )
        finally:
            shutil.rmtree(home, ignore_errors=True)

    # ----- Scan: clean file -> portable: clean -----

    def test_scan_clean(self):
        tmp = tempfile.mkdtemp(prefix="md_scan_clean_")
        try:
            md = f"{tmp}/md_files"
            os.makedirs(md)
            open(f"{md}/AGENTS.shared.md", "w").write("# clean\n")
            open(f"{md}/CLAUDE.adapter.md", "w").write("# clean\n")
            r = _run(self.scan, env={}, cwd=tmp)
            self.assertEqual(r.returncode, 0, f"scan failed: {r.stderr}")
            self.assertIn("portable: clean", r.stdout)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    # ----- Scan: HIT -> scan: HIT + non-zero exit -----

    def test_scan_hit(self):
        tmp = tempfile.mkdtemp(prefix="md_scan_hit_")
        try:
            md = f"{tmp}/md_files"
            os.makedirs(md)
            open(f"{md}/AGENTS.shared.md", "w").write("# /Users/john/foo\n")
            open(f"{md}/CLAUDE.adapter.md", "w").write("# clean\n")
            r = _run(self.scan, env={}, cwd=tmp)
            self.assertNotEqual(r.returncode, 0, "scan on HIT must exit non-zero")
            self.assertIn("HIT", r.stdout + r.stderr)
            self.assertNotIn("portable: clean", r.stdout)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    # ----- Scan: missing file -> scan: ERROR + non-zero exit -----

    def test_scan_missing_file(self):
        tmp = tempfile.mkdtemp(prefix="md_scan_missing_")
        try:
            patched = self.scan.replace(
                "files=(md_files/AGENTS.shared.md md_files/CLAUDE.adapter.md)",
                "files=(/nonexistent/foo.md)",
            )
            r = _run(patched, env={}, cwd=tmp)
            self.assertNotEqual(r.returncode, 0, "scan on missing file must exit non-zero")
            self.assertIn("ERROR", r.stdout + r.stderr)
            self.assertNotIn("portable: clean", r.stdout)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    # ----- Scan: directory as file -> scan: ERROR (Codex Bug #3 regression) -----

    def test_scan_directory_not_false_clean(self):
        tmp = tempfile.mkdtemp(prefix="md_scan_dir_")
        try:
            as_dir = f"{tmp}/fakefile.md"
            os.makedirs(as_dir)  # Path is a directory; grep exits 2 on it.
            patched = self.scan.replace(
                "files=(md_files/AGENTS.shared.md md_files/CLAUDE.adapter.md)",
                f"files=({as_dir})",
            )
            r = _run(patched, env={}, cwd=tmp)
            self.assertIn(
                "ERROR", r.stdout + r.stderr,
                "scan on a directory path must print ERROR, not silently print "
                "'portable: clean' (Codex 2026-09-13 grep exit-2 swallowing)",
            )
            self.assertNotIn(
                "portable: clean", r.stdout,
                "scan on a directory path printed 'portable: clean' — false-positive "
                "regression of Codex 2026-09-13 finding #3",
            )
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
