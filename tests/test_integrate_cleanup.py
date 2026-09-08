"""Integration cleanup reporting and lifecycle tests for scripts/integrate.sh."""

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
INTEGRATE_SCRIPT = REPO_ROOT / "scripts" / "integrate.sh"


class IntegrateCleanupTests(unittest.TestCase):
    def create_isolated_repo(self, base_dir: Path) -> tuple[Path, Path, dict[str, str]]:
        origin = base_dir / "origin.git"
        work = base_dir / "work"
        fake_home = base_dir / "fake_home"
        fake_home.mkdir(parents=True)
        fake_bin = fake_home / "bin"
        fake_bin.mkdir(parents=True)

        fake_gh = fake_bin / "gh"
        fake_gh.write_text("#!/bin/sh\necho '[]'\nexit 0\n", encoding="utf-8")
        fake_gh.chmod(0o755)

        env = os.environ.copy()
        env["HOME"] = str(fake_home)
        path_val = env.get("PATH", "")
        env["PATH"] = f"{fake_bin}:{path_val}"
        env["CI"] = "1"
        env["NONINTERACTIVE"] = "1"
        env["HERMES_SKIP_EXAMPLE_COM_GUARD"] = "1"
        env["GIT_CONFIG_NOSYSTEM"] = "1"
        env["GIT_CONFIG_GLOBAL"] = "/dev/null"
        env["GIT_AUTHOR_NAME"] = "Jeffrey Lee-Chan"
        env["GIT_AUTHOR_EMAIL"] = "jleechan2015@users.noreply.github.com"
        env["GIT_COMMITTER_NAME"] = "Jeffrey Lee-Chan"
        env["GIT_COMMITTER_EMAIL"] = "jleechan2015@users.noreply.github.com"

        subprocess.run(["git", "init", "--bare", str(origin)], check=True, capture_output=True, env=env, timeout=30)
        subprocess.run(["git", "init", str(work)], check=True, capture_output=True, env=env, timeout=30)
        subprocess.run(["git", "-C", str(work), "config", "user.name", "Jeffrey Lee-Chan"], check=True, env=env, timeout=30)
        subprocess.run(["git", "-C", str(work), "config", "user.email", "jleechan2015@users.noreply.github.com"], check=True, env=env, timeout=30)
        subprocess.run(["git", "-C", str(work), "checkout", "-b", "main"], check=True, capture_output=True, env=env, timeout=30)
        (work / "README.md").write_text("initial repo content\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(work), "add", "README.md"], check=True, env=env, timeout=30)
        subprocess.run(["git", "-C", str(work), "commit", "-m", "initial commit"], check=True, capture_output=True, env=env, timeout=30)
        subprocess.run(["git", "-C", str(work), "remote", "add", "origin", str(origin)], check=True, env=env, timeout=30)
        subprocess.run(["git", "-C", str(work), "push", "-u", "origin", "main"], check=True, capture_output=True, env=env, timeout=30)
        subprocess.run(["git", "-C", str(work), "checkout", "-b", "feature/cleanup-target"], check=True, capture_output=True, env=env, timeout=30)

        return origin, work, env

    def test_absent_manager_skips_and_continues(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            base = Path(tmp_dir)
            _, work, env = self.create_isolated_repo(base)
            self.assertFalse((work / "test_server_manager.sh").exists())

            res = subprocess.run(
                ["bash", str(INTEGRATE_SCRIPT)],
                cwd=str(work),
                env=env,
                capture_output=True,
                text=True,
                timeout=60,
            )
            self.assertEqual(res.returncode, 0, f"integrate.sh failed: {res.stdout}\n{res.stderr}")
            combined = res.stdout + "\n" + res.stderr
            self.assertIn("SKIPPED", combined)

            current_branch = subprocess.run(
                ["git", "-C", str(work), "branch", "--show-current"],
                capture_output=True,
                text=True,
                check=True,
                env=env,
                timeout=30,
            ).stdout.strip()
            self.assertNotEqual(current_branch, "feature/cleanup-target")
            self.assertTrue(current_branch.startswith("dev"))

    def test_successful_manager_reports_success_and_continues(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            base = Path(tmp_dir)
            _, work, env = self.create_isolated_repo(base)
            mgr = work / "test_server_manager.sh"
            mgr_args_file = work / "manager_args.txt"
            mgr.write_text(
                "#!/bin/sh\n"
                f"printf '%s\\n' \"$@\" > '{mgr_args_file}'\n"
                "if [ \"$1\" != \"stop\" ] || [ \"$2\" != \"feature/cleanup-target\" ]; then\n"
                "    echo \"invalid args: $@\" >&2\n"
                "    exit 2\n"
                "fi\n"
                "echo 'mock stopping server for $2'\n"
                "exit 0\n",
                encoding="utf-8",
            )
            mgr.chmod(0o755)

            res = subprocess.run(
                ["bash", str(INTEGRATE_SCRIPT)],
                cwd=str(work),
                env=env,
                capture_output=True,
                text=True,
                timeout=60,
            )
            self.assertEqual(res.returncode, 0, f"integrate.sh failed: {res.stdout}\n{res.stderr}")
            combined = res.stdout + "\n" + res.stderr
            self.assertIn("Test server manager returned success", combined)
            self.assertNotIn("no orphaned server processes", combined.lower())
            self.assertTrue(mgr_args_file.exists())
            self.assertEqual(
                mgr_args_file.read_text(encoding="utf-8").splitlines(),
                ["stop", "feature/cleanup-target"],
            )

            current_branch = subprocess.run(
                ["git", "-C", str(work), "branch", "--show-current"],
                capture_output=True,
                text=True,
                check=True,
                env=env,
                timeout=30,
            ).stdout.strip()
            self.assertNotEqual(current_branch, "feature/cleanup-target")

    def test_failing_manager_reports_error_with_stderr_and_fails_before_checkout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            base = Path(tmp_dir)
            _, work, env = self.create_isolated_repo(base)
            mgr = work / "test_server_manager.sh"
            mgr_stderr_marker = "critical manager failure: stop timeout on pid 9999"
            mgr.write_text(f"#!/bin/sh\necho '{mgr_stderr_marker}' >&2\nexit 1\n", encoding="utf-8")
            mgr.chmod(0o755)

            head_before = subprocess.run(
                ["git", "-C", str(work), "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                check=True,
                env=env,
                timeout=30,
            ).stdout.strip()

            res = subprocess.run(
                ["bash", str(INTEGRATE_SCRIPT)],
                cwd=str(work),
                env=env,
                capture_output=True,
                text=True,
                timeout=60,
            )
            self.assertNotEqual(res.returncode, 0, "integrate.sh should fail when manager fails")
            combined = res.stdout + "\n" + res.stderr
            self.assertIn(mgr_stderr_marker, combined, "Expected manager stderr in output")

            current_branch = subprocess.run(
                ["git", "-C", str(work), "branch", "--show-current"],
                capture_output=True,
                text=True,
                check=True,
                env=env,
                timeout=30,
            ).stdout.strip()
            self.assertEqual(current_branch, "feature/cleanup-target")

            head_after = subprocess.run(
                ["git", "-C", str(work), "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                check=True,
                env=env,
                timeout=30,
            ).stdout.strip()
            self.assertEqual(head_before, head_after)

    def test_nonexecutable_manager_reports_error_and_fails_before_checkout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            base = Path(tmp_dir)
            _, work, env = self.create_isolated_repo(base)
            mgr = work / "test_server_manager.sh"
            mgr.write_text("#!/bin/sh\necho 'should not run'\nexit 0\n", encoding="utf-8")
            mgr.chmod(0o644)

            head_before = subprocess.run(
                ["git", "-C", str(work), "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                check=True,
                env=env,
                timeout=30,
            ).stdout.strip()

            res = subprocess.run(
                ["bash", str(INTEGRATE_SCRIPT)],
                cwd=str(work),
                env=env,
                capture_output=True,
                text=True,
                timeout=60,
            )
            self.assertNotEqual(res.returncode, 0, "integrate.sh should fail on nonexecutable manager")
            combined = res.stdout + "\n" + res.stderr
            self.assertTrue(
                "not executable" in combined.lower() or "permission denied" in combined.lower(),
                f"Expected not executable error, got: {combined}",
            )

            current_branch = subprocess.run(
                ["git", "-C", str(work), "branch", "--show-current"],
                capture_output=True,
                text=True,
                check=True,
                env=env,
                timeout=30,
            ).stdout.strip()
            self.assertEqual(current_branch, "feature/cleanup-target")

            head_after = subprocess.run(
                ["git", "-C", str(work), "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                check=True,
                env=env,
                timeout=30,
            ).stdout.strip()
            self.assertEqual(head_before, head_after)

    def test_subdirectory_invocation_resolves_manager_relative_to_git_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            base = Path(tmp_dir)
            _, work, env = self.create_isolated_repo(base)
            sub = work / "deep" / "nested" / "subdir"
            sub.mkdir(parents=True)

            mgr = work / "test_server_manager.sh"
            mgr.write_text(
                "#!/bin/sh\n"
                "if [ ! -f README.md ]; then\n"
                "    echo 'manager failed: README.md not found in working directory' >&2\n"
                "    exit 3\n"
                "fi\n"
                "echo 'root manager called successfully from cwd containing README.md'\n"
                "exit 0\n",
                encoding="utf-8",
            )
            mgr.chmod(0o755)

            res = subprocess.run(
                ["bash", str(INTEGRATE_SCRIPT)],
                cwd=str(sub),
                env=env,
                capture_output=True,
                text=True,
                timeout=60,
            )
            self.assertEqual(res.returncode, 0, f"integrate.sh failed from subdir: {res.stdout}\n{res.stderr}")
            combined = res.stdout + "\n" + res.stderr
            self.assertIn("Test server manager returned success", combined)


if __name__ == "__main__":
    unittest.main()
