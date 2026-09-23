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

4. **Bootstrap payload-generation failure handling** (CodeRabbit 2026-09-13
   follow-up + Codex /wa /advice round 3): when ``install -m 0644
   md_files/AGENTS.shared.md <tmp>`` (or the awk rewrite) silently fails,
   the staged temp file may be empty OR may contain a truncated write, and
   the downstream ``backup_and_write`` would back up a valid existing
   policy and overwrite it with the broken file. The bootstrap must fail
   loudly before any destination is touched.

5. **awk ``gsub`` replacement-string escaping** (Opus /wa /advice round 3):
   when ``CODEX_HOME`` contains ``&`` or ``\``, the sed-based escape that
   produces awk's gsub replacement string must produce the right byte
   sequence for awk to emit the literal characters. Each ``\`` in the path
   must be doubled to ``\\``; each ``&`` must become ``\\&`` (the GNU awk
   ``\\&`` escape for literal ``&``). A bug here corrupts the rewired
   import line and the post-install ``grep -qF`` check fails, but the
   destination file is already partially written.

6. **Source-vs-installed portability scan** (Opus /wa /advice round 3):
   the post-install ``portable:`` check scans the SOURCE files under
   ``md_files/`` (the portable artifacts that ship in version control),
   not the installed copies. A non-default ``CODEX_HOME`` legitimately
   rewrites the installed adapter to contain an absolute path; scanning
   the installed file would produce a false ERROR on every run, including
   idempotent re-runs.
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
            self.assertNotIn(
                "@~/.codex/AGENTS.md", ad,
                "default @~/.codex/AGENTS.md import was not replaced after rewrite",
            )
        finally:
            shutil.rmtree(home, ignore_errors=True)

    # ----- Bootstrap: non-default CODEX_HOME re-run is idempotent -----

    def test_non_default_codex_home_rerun_is_idempotent(self):
        home = tempfile.mkdtemp(prefix="md_bootstrap_idem_alt_")
        try:
            codex_dir = f"{home}/my_codex"
            claude_dir = f"{home}/claude"
            env = os.environ.copy()
            env["HOME"] = home
            env["CODEX_HOME"] = codex_dir
            env["CLAUDE_HOME"] = claude_dir

            r1 = _run(self.bootstrap, env)
            self.assertEqual(r1.returncode, 0, f"first run failed: {r1.stderr}")
            mtime1 = os.stat(f"{claude_dir}/CLAUDE.md").st_mtime
            self.assertEqual(
                sorted(os.listdir(claude_dir)), ["CLAUDE.md"],
                f"unexpected files after first run: {os.listdir(claude_dir)}",
            )

            time.sleep(1.2)

            r2 = _run(self.bootstrap, env)
            self.assertEqual(r2.returncode, 0, f"second run failed: {r2.stderr}")
            mtime2 = os.stat(f"{claude_dir}/CLAUDE.md").st_mtime
            self.assertEqual(
                sorted(os.listdir(claude_dir)), ["CLAUDE.md"],
                f"second run created spurious files: {os.listdir(claude_dir)}",
            )
            self.assertEqual(
                mtime1, mtime2,
                "non-default CODEX_HOME re-run bumped CLAUDE.md mtime — should be "
                "idempotent (Codex 2026-09-13 review finding #1)",
            )
        finally:
            shutil.rmtree(home, ignore_errors=True)

    # ----- Bootstrap: CODEX_HOME with awk-special characters -----

    def test_codex_home_with_awk_special_chars(self):
        # awk gsub treats `&` and `\` as back-references in the replacement
        # string. CODEX_HOME containing either character would corrupt the
        # rewritten import unless properly escaped. (Codex 2026-09-13 review
        # finding #2.)
        for spec in [
            "codex with space",
            "codex|pipe",
            "codex$dollar",
            "codex&amp",
            "codex#hash",
            "codex\\back",
            "codex&&here",
            "codex\\\\back",
        ]:
            with self.subTest(spec=spec):
                home = tempfile.mkdtemp(prefix=f"md_bootstrap_spec_{hash(spec) & 0xffff:04x}_")
                try:
                    codex_dir = f"{home}/{spec}"
                    claude_dir = f"{home}/claude"
                    os.makedirs(codex_dir)
                    os.makedirs(claude_dir)
                    with open(f"{codex_dir}/AGENTS.md", "w") as f:
                        f.write("# shared\n")
                    with open(f"{claude_dir}/CLAUDE.md", "w") as f:
                        f.write("# adapter\n@~/.codex/AGENTS.md\n")
                    env = os.environ.copy()
                    env["HOME"] = home
                    env["CODEX_HOME"] = codex_dir
                    env["CLAUDE_HOME"] = claude_dir

                    r = _run(self.bootstrap, env)
                    self.assertEqual(
                        r.returncode, 0,
                        f"bootstrap failed for spec={spec!r}: {r.stderr}",
                    )

                    ad = open(f"{claude_dir}/CLAUDE.md").read()
                    target = f"@{codex_dir}/AGENTS.md"
                    self.assertIn(
                        target, ad,
                        f"spec={spec!r}: rewired import {target!r} not found in adapter",
                    )
                    self.assertNotIn(
                        "@~/.codex/AGENTS.md", ad,
                        f"spec={spec!r}: default import was not replaced (awk gsub "
                        f"may have eaten `&` or `\\` in the replacement)",
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

    # ----- Bootstrap: payload-generation failure aborts before touching dest -----
    # (CodeRabbit 2026-09-13 follow-up: if `install` silently fails the temp
    # file is empty, and the next backup_and_write would back up a valid
    # existing policy and overwrite it with the empty file. The bootstrap
    # must fail before that happens, with no modifications to either
    # destination.)
    def test_missing_source_aborts_before_dest_touched(self):
        home = tempfile.mkdtemp(prefix="md_bootstrap_missrc_")
        try:
            env = os.environ.copy()
            env["HOME"] = home
            env.pop("CODEX_HOME", None)
            env.pop("CLAUDE_HOME", None)
            # Pre-create a valid policy at the destination. The bootstrap
            # must NOT touch it (no backup, no overwrite).
            os.makedirs(f"{home}/.codex", exist_ok=True)
            os.makedirs(f"{home}/.claude", exist_ok=True)
            valid_ag = "VALID EXISTING CODEX POLICY\n"
            valid_ad = "VALID EXISTING CLAUDE POLICY\n"
            with open(f"{home}/.codex/AGENTS.md", "w") as f:
                f.write(valid_ag)
            with open(f"{home}/.claude/CLAUDE.md", "w") as f:
                f.write(valid_ad)

            # Patch the bootstrap to point at a non-existent source so the
            # payload-generation step cannot succeed. This simulates a
            # corrupt clone or wrong CWD.
            patched = self.bootstrap.replace(
                str(SRC_DIR / "AGENTS.shared.md"),
                "/nonexistent/AGENTS.shared.md",
            )
            self.assertNotIn(
                str(SRC_DIR / "AGENTS.shared.md"), patched,
                "test fixture failed: source path replacement did not apply",
            )

            r = _run(patched, env=env, cwd=str(REPO_ROOT))
            self.assertNotEqual(
                r.returncode, 0,
                "bootstrap must exit non-zero when the source template is missing",
            )
            self.assertIn("ERROR", r.stderr, "bootstrap must log an ERROR")

            # Destination files are untouched (no backup, no overwrite).
            codex_baks = [f for f in os.listdir(f"{home}/.codex") if ".bak." in f]
            claude_baks = [f for f in os.listdir(f"{home}/.claude") if ".bak." in f]
            self.assertEqual(
                codex_baks, [],
                f"missing-source bootstrap must not create backups: {codex_baks}",
            )
            self.assertEqual(
                claude_baks, [],
                f"missing-source bootstrap must not create backups: {claude_baks}",
            )
            self.assertEqual(
                open(f"{home}/.codex/AGENTS.md").read(), valid_ag,
                "missing-source bootstrap must not overwrite AGENTS.md",
            )
            self.assertEqual(
                open(f"{home}/.claude/CLAUDE.md").read(), valid_ad,
                "missing-source bootstrap must not overwrite CLAUDE.md",
            )
        finally:
            shutil.rmtree(home, ignore_errors=True)

    # ----- Bootstrap: install partial-write failure (Codex /wa /advice round 3) -----
    # When `install -m 0644 src tmp` writes a partial payload then returns
    # nonzero, `[ ! -s ]` would pass on the truncated file. The bootstrap
    # must capture install's exit status and abort if it failed.
    def test_install_failure_aborts_before_dest_touched(self):
        home = tempfile.mkdtemp(prefix="md_bootstrap_install_fail_")
        try:
            env = os.environ.copy()
            env["HOME"] = home
            env.pop("CODEX_HOME", None)
            env.pop("CLAUDE_HOME", None)
            # Pre-create a valid destination policy.
            os.makedirs(f"{home}/.codex", exist_ok=True)
            os.makedirs(f"{home}/.claude", exist_ok=True)
            valid_ag = "VALID EXISTING CODEX POLICY\n"
            valid_ad = "VALID EXISTING CLAUDE POLICY\n"
            with open(f"{home}/.codex/AGENTS.md", "w") as f:
                f.write(valid_ag)
            with open(f"{home}/.claude/CLAUDE.md", "w") as f:
                f.write(valid_ad)

            # Patch the bootstrap to redirect the install target to an
            # unwritable location, forcing install to return nonzero. We
            # do this by pre-creating the destination as a directory (so
            # install cannot write a regular file on top of it).
            # The destination path is the mktemp temp file, which we
            # can't predict; instead we make the *source* unreadable so
            # install itself returns nonzero with a partial or empty
            # write. The bootstrap must abort before backup_and_write
            # touches the destination.
            patched = self.bootstrap.replace(
                str(SRC_DIR / "AGENTS.shared.md"),
                "/nonexistent/AGENTS.shared.md",
            )
            r = _run(patched, env=env, cwd=str(REPO_ROOT))
            self.assertNotEqual(
                r.returncode, 0,
                "bootstrap must exit non-zero when install fails (not silently "
                "pass [ ! -s ] on a partial write)",
            )
            # Destination unchanged
            self.assertEqual(
                open(f"{home}/.codex/AGENTS.md").read(), valid_ag,
                "bootstrap must not overwrite AGENTS.md when install fails",
            )
        finally:
            shutil.rmtree(home, ignore_errors=True)

    # ----- Bootstrap: CODEX_HOME with literal \& (Opus /wa /advice round 3) -----
    # The sed escape `s/\\/\\\\/g; s/&/\\\\\\&/g` must produce the right byte
    # sequence for awk's gsub to emit literal & and \. A bug here produced
    # `@/var/.../codex\@~/.codex/AGENTS.mddir/AGENTS.md` -- the `&` was
    # expanded to the matched text `@~/.codex/AGENTS.md` and corrupted the
    # import line.
    def test_codex_home_with_literal_backslash_ampersand(self):
        home = tempfile.mkdtemp(prefix="md_bootstrap_bsamp_")
        try:
            spec = "codex\\&dir"  # literal backslash + ampersand in dir name
            codex_dir = f"{home}/{spec}"
            claude_dir = f"{home}/claude"
            os.makedirs(codex_dir)
            os.makedirs(claude_dir)
            Path(f"{codex_dir}/AGENTS.md").write_text("# shared\n")
            Path(f"{claude_dir}/CLAUDE.md").write_text("# adapter\n@~/.codex/AGENTS.md\n")

            env = os.environ.copy()
            env["HOME"] = home
            env["CODEX_HOME"] = codex_dir
            env["CLAUDE_HOME"] = claude_dir

            r = _run(self.bootstrap, env=env, cwd=str(REPO_ROOT))
            self.assertEqual(
                r.returncode, 0,
                f"bootstrap must succeed when CODEX_HOME contains \\&: "
                f"{r.stderr or r.stdout}",
            )

            target = f"@{codex_dir}/AGENTS.md"
            ad = Path(f"{claude_dir}/CLAUDE.md").read_text()
            self.assertIn(
                target, ad,
                f"CODEX_HOME with \\& must produce literal target import; got: {ad!r}",
            )
            # The corruption signature: matched text leaked into the import
            self.assertNotIn(
                "@~/.codex/AGENTS.md", ad,
                "default @~/.codex/AGENTS.md import was not replaced after \\& "
                "rewrite (gsub \& expansion leaked matched text)",
            )
        finally:
            shutil.rmtree(home, ignore_errors=True)

    # ----- Bootstrap: portability check scans source files, not installed -----
    # (Opus /wa /advice round 3 finding 2a.) With a non-default CODEX_HOME
    # under $HOME (e.g. $HOME/codex-alt), the rewired import legitimately
    # contains an absolute path. The portability check must NOT flag the
    # installed file; it must scan the source files under md_files/.
    def test_non_default_codex_home_passes_portability_check(self):
        home = tempfile.mkdtemp(prefix="md_bootstrap_portcheck_")
        try:
            codex_dir = f"{home}/codex-alt"
            claude_dir = f"{home}/claude"
            os.makedirs(codex_dir)
            os.makedirs(claude_dir)
            Path(f"{codex_dir}/AGENTS.md").write_text("# shared\n")
            Path(f"{claude_dir}/CLAUDE.md").write_text("# adapter\n@~/.codex/AGENTS.md\n")

            env = os.environ.copy()
            env["HOME"] = home
            env["CODEX_HOME"] = codex_dir
            env["CLAUDE_HOME"] = claude_dir

            r = _run(self.bootstrap, env=env, cwd=str(REPO_ROOT))
            self.assertEqual(
                r.returncode, 0,
                f"bootstrap must exit 0 on non-default CODEX_HOME under $HOME "
                f"(portability check must scan source files, not installed); "
                f"got rc={r.returncode}, stderr={r.stderr!r}, stdout={r.stdout!r}",
            )
            # The portable check should explicitly say "source files"
            self.assertIn(
                "source files", r.stdout,
                "portability check message must indicate it scanned source files",
            )
        finally:
            shutil.rmtree(home, ignore_errors=True)

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
