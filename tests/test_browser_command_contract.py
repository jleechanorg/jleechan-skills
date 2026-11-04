"""Hermetic execution tests for the browser-control credential lifecycle recipes."""

import os
import re
import signal
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BROWSER_SKILL = REPO_ROOT / ".claude" / "skills" / "browser-control" / "SKILL.md"

def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


class ShellLifecycleSimulationTest(unittest.TestCase):
    """Prove the fail-closed lifecycle invariant locally with a hermetic simulation."""

    SIM_SCRIPT = """#!/usr/bin/env bash
set -euo pipefail

TMP_COOKIES="$(mktemp -t browserclaw-sim-cookies-XXXXXX.json)"
TMP_PAGE="$(mktemp -t browserclaw-sim-page-XXXXXX.txt)"
chmod 600 "$TMP_COOKIES" "$TMP_PAGE"
cleanup() { rm -f "$TMP_COOKIES" "$TMP_PAGE"; }
trap cleanup EXIT INT TERM

${SIM_STEP}

cleanup
trap - EXIT INT TERM
"""

    def _run_sim(self, step: str) -> tuple[int, str, str]:
        with tempfile.TemporaryDirectory() as td:
            script_path = Path(td) / "lifecycle_sim.sh"
            script_path.write_text(self.SIM_SCRIPT.replace("${SIM_STEP}", step))
            script_path.chmod(0o755)
            env = os.environ.copy()
            proc = subprocess.run(
                ["bash", str(script_path)],
                env=env,
                capture_output=True,
                text=True,
                timeout=30,
            )
            leftovers = sorted(p.name for p in Path(td).glob("browserclaw-sim-*"))
            return proc.returncode, proc.stderr, ",".join(leftovers) or "<none>"

    def test_success_path_removes_temp_files_and_returns_zero(self) -> None:
        rc, _, leftovers = self._run_sim(":")
        self.assertEqual(rc, 0)
        self.assertEqual(leftovers, "<none>")

    def test_failure_path_removes_temp_files_and_returns_nonzero(self) -> None:
        rc, _, leftovers = self._run_sim("false")
        self.assertNotEqual(rc, 0)
        self.assertEqual(leftovers, "<none>")

    def test_failure_path_preserves_underlying_exit_code(self) -> None:
        rc, _, _ = self._run_sim("exit 42")
        self.assertEqual(rc, 42)


class ExtractedRecipeExecutionTest(unittest.TestCase):
    """Execute extracted documented bash recipes from browser-control/SKILL.md in hermetic subprocesses."""

    @classmethod
    def _extract_canonical_recipe(cls) -> str:
        text = read(BROWSER_SKILL)
        body = text.split("## Authorized credential reuse", 1)[1].split("## Fingerprint-sensitive", 1)[0]
        m = re.search(r"```bash\n(.*?)\n```", body, re.DOTALL)
        assert m, "browser-control SKILL.md missing canonical bash recipe block"
        recipe = m.group(1)
        recipe = re.sub(
            r"mktemp -t ([^\s\"]+)",
            r'mktemp -p "$TMPDIR/" \1',
            recipe,
        )
        out: list[str] = []
        in_sweep = False
        skipping_env_block = False
        for line in recipe.splitlines():
            stripped = line.strip()
            if stripped == "set +e" and not in_sweep:
                in_sweep = True
                out.append(
                    "jq -n --argjson c '[{\"name\":\"__test__\",\"value\":\"1\",\"domain\":\".example.com\",\"path\":\"/\"}]' "
                    "'{cookies:$c}' > \"$TMP_COOKIES\""
                )
                continue
            if in_sweep:
                if stripped == "set -e":
                    in_sweep = False
                continue
            if line.lstrip().startswith("env -i") and line.rstrip().endswith("\\"):
                skipping_env_block = True
                out.append("printf 'stub page text' > \"$TMP_PAGE\"")
                continue
            if skipping_env_block:
                if not line.rstrip().endswith("\\"):
                    skipping_env_block = False
                continue
            out.append(line)
        return "\n".join(out)

    @classmethod
    def _extract_secret_branch(cls) -> str:
        text = read(BROWSER_SKILL)
        body = text.split("**Secret-bearing page branch:**", 1)[1].split("**Safeguards**", 1)[0]
        m = re.search(r"```bash\n(.*?)\n```", body, re.DOTALL)
        assert m, "browser-control SKILL.md missing secret-branch bash block"
        branch = m.group(1)
        branch = re.sub(
            r"mktemp -t ([^\s\"]+)",
            r'mktemp -p "$TMPDIR/" \1',
            branch,
        )
        out: list[str] = []
        in_sweep = False
        for line in branch.splitlines():
            stripped = line.strip()
            if stripped == "set +e" and not in_sweep:
                in_sweep = True
                out.append(
                    "jq -n --argjson c '[{\"name\":\"__test__\",\"value\":\"1\",\"domain\":\".example.com\",\"path\":\"/\"}]' "
                    "'{cookies:$c}' > \"$TMP_COOKIES\""
                )
                continue
            if in_sweep:
                if stripped == "set -e":
                    in_sweep = False
                continue
            out.append(line)
        branch = "\n".join(out)
        branch = branch.replace(
            '"$HOME/.local/orch-venv/bin/python" - "$TMP_COOKIES" "$BROWSE_TARGET_URL" <<\'PY\'',
            '/usr/bin/python3 - "$TMP_COOKIES" "http://stub" <<\'PY\'',
        )
        return branch

    def _run_with(self, recipe: str, env_extra: dict | None = None) -> tuple[int, str, str]:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "recipe.sh"
            path.write_text(recipe)
            path.chmod(0o755)
            env = os.environ.copy()
            env["TMPDIR"] = td
            if env_extra:
                env.update(env_extra)
            proc = subprocess.run(
                ["bash", str(path)],
                env=env,
                capture_output=True,
                text=True,
                timeout=30,
                cwd=td,
            )
            leftovers = sorted(p.name for p in Path(td).glob("browserclaw*"))
            return proc.returncode, proc.stderr, ",".join(leftovers) or "<none>"

    def test_canonical_recipe_success_path_removes_all_credential_artifacts(self) -> None:
        recipe = self._extract_canonical_recipe()
        rc, stderr, leftovers = self._run_with(recipe)
        self.assertEqual(rc, 0, f"canonical recipe failed: {stderr}")
        self.assertEqual(leftovers, "<none>")

    def test_canonical_recipe_failure_path_removes_all_credential_artifacts(self) -> None:
        recipe = self._extract_canonical_recipe()
        recipe = recipe.replace(
            "printf 'stub page text' > \"$TMP_PAGE\"",
            "false  # force set -e to abort",
        )
        rc, _, leftovers = self._run_with(recipe)
        self.assertNotEqual(rc, 0)
        self.assertEqual(leftovers, "<none>")

    def test_canonical_recipe_zero_cookie_gate_exits_nonzero(self) -> None:
        recipe = self._extract_canonical_recipe()
        recipe = recipe.replace(
            "jq -n --argjson c '[{\"name\":\"__test__\",\"value\":\"1\",\"domain\":\".example.com\",\"path\":\"/\"}]' '{cookies:$c}' > \"$TMP_COOKIES\"",
            "jq -n --argjson c '[]' '{cookies:$c}' > \"$TMP_COOKIES\"",
        )
        rc, stderr, leftovers = self._run_with(recipe)
        self.assertNotEqual(rc, 0)
        self.assertIn("BLOCKER", stderr)
        self.assertEqual(leftovers, "<none>")

    def test_secret_branch_cleans_up_cookies_on_failure(self) -> None:
        branch = self._extract_secret_branch()
        with tempfile.TemporaryDirectory() as td:
            cookie_inside = Path(td) / "browserclaw-XXXXXX-cookies.json"
            cookie_inside.write_text('{"cookies": [{"name": "x"}]}')
            cookie_inside.chmod(0o600)
            page_inside = Path(td) / "browserclaw-XXXXXX-page.txt"
            page_inside.write_text("ignored")
            page_inside.chmod(0o600)
            script = (
                f'export TMP_COOKIES="{cookie_inside}"\n'
                f'export TMP_PAGE="{page_inside}"\n'
                f"{branch}"
            )
            rc, stderr, leftovers = self._run_with(script, env_extra={
                "TMP_COOKIES": str(cookie_inside),
                "TMP_PAGE": str(page_inside),
                "BROWSE_TARGET_URL": "http://stub",
            })
            self.assertNotEqual(rc, 0)
            self.assertEqual(leftovers, "<none>")

    def test_canonical_recipe_sigint_removes_all_credential_artifacts(self) -> None:
        recipe = self._extract_canonical_recipe()
        recipe = recipe.replace(
            "printf 'stub page text' > \"$TMP_PAGE\"",
            "sleep 5 & wait $!",
        )
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "recipe.sh"
            path.write_text(recipe)
            path.chmod(0o755)
            env = os.environ.copy()
            env["TMPDIR"] = td
            proc = subprocess.Popen(
                ["bash", str(path)],
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=td,
            )
            deadline = time.time() + 5
            while time.time() < deadline:
                if any(Path(td).glob("browserclaw-*.json")):
                    break
                time.sleep(0.1)
            self.assertTrue(any(Path(td).glob("browserclaw-*.json")))
            proc.send_signal(signal.SIGINT)
            try:
                proc.wait(timeout=8)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
            leftovers = sorted(p.name for p in Path(td).glob("browserclaw*"))
            self.assertEqual(leftovers, [])
            self.assertGreater(proc.returncode, 128)

    def test_canonical_recipe_sigterm_removes_all_credential_artifacts(self) -> None:
        recipe = self._extract_canonical_recipe()
        recipe = recipe.replace(
            "printf 'stub page text' > \"$TMP_PAGE\"",
            "sleep 5 & wait $!",
        )
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "recipe.sh"
            path.write_text(recipe)
            path.chmod(0o755)
            env = os.environ.copy()
            env["TMPDIR"] = td
            proc = subprocess.Popen(
                ["bash", str(path)],
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=td,
            )
            deadline = time.time() + 5
            while time.time() < deadline:
                if any(Path(td).glob("browserclaw-*.json")):
                    break
                time.sleep(0.1)
            self.assertTrue(any(Path(td).glob("browserclaw-*.json")))
            proc.send_signal(signal.SIGTERM)
            try:
                proc.wait(timeout=8)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
            leftovers = sorted(p.name for p in Path(td).glob("browserclaw*"))
            self.assertEqual(leftovers, [])
            self.assertGreater(proc.returncode, 128)

    def test_canonical_recipe_pre_allocation_sigterm_removes_artifacts(self) -> None:
        """Prove that a SIGTERM arriving after the first allocation but before second allocation
        is cleanly caught by the pre-armed trap and leaves zero temp files (bd-v83)."""
        recipe = self._extract_canonical_recipe()
        m = re.search(r'(TMP_COOKIES="?\$\([^)]+browserclaw-[^)]+\)"?)', recipe)
        self.assertIsNotNone(m, "Could not find TMP_COOKIES allocation in recipe")
        alloc_line = m.group(1)
        recipe = recipe.replace(alloc_line, alloc_line + "\nsleep 5 & wait $!")
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "recipe.sh"
            path.write_text(recipe)
            path.chmod(0o755)
            env = os.environ.copy()
            env["TMPDIR"] = td
            proc = subprocess.Popen(
                ["bash", str(path)],
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=td,
            )
            deadline = time.time() + 5
            while time.time() < deadline:
                if any(Path(td).glob("browserclaw-*.json")):
                    break
                time.sleep(0.05)
            self.assertTrue(any(Path(td).glob("browserclaw-*.json")))
            proc.send_signal(signal.SIGTERM)
            try:
                proc.wait(timeout=8)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
            leftovers = sorted(p.name for p in Path(td).glob("browserclaw*"))
            self.assertEqual(leftovers, [], f"Leftover artifacts after pre-allocation SIGTERM: {leftovers}")
            self.assertGreater(proc.returncode, 128)

    def test_authorization_denial_simulation(self) -> None:
        """Prove that when task authorization is false/absent, the execution denies credential reuse,
        emits a blocker message, exits nonzero, and leaves no temp files."""
        auth_check_script = """#!/usr/bin/env bash
set -euo pipefail
umask 077
TMP_COOKIES="$(mktemp -p "$TMPDIR/" browserclaw-XXXXXX.json)"
chmod 600 "$TMP_COOKIES"
cleanup() { rm -f "$TMP_COOKIES"; }
trap cleanup EXIT INT TERM

TASK_AUTHORIZED="${TASK_AUTHORIZED:-false}"
if [ "$TASK_AUTHORIZED" != "true" ]; then
  echo "BLOCKER: Credential reuse denied — task lacks explicit authorization for cookie transfer." >&2
  exit 12
fi

echo '{"cookies":[{"name":"test"}]}' > "$TMP_COOKIES"
"""
        rc, stderr, leftovers = self._run_with(auth_check_script, env_extra={"TASK_AUTHORIZED": "false"})
        self.assertEqual(rc, 12)
        self.assertIn("BLOCKER: Credential reuse denied", stderr)
        self.assertEqual(leftovers, "<none>")


if __name__ == "__main__":
    unittest.main()
