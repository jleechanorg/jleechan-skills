"""Contracts for exported workflow command and skill pairs."""

import os
import shlex
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
COMMANDS = REPO_ROOT / ".claude" / "commands"
SKILLS = REPO_ROOT / ".claude" / "skills"

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.skill_portability_scan import owner_roots, parse_frontmatter  # noqa: E402


class WorkflowCommandPairTest(unittest.TestCase):
    def test_core_workflows_export_complete_packages(self):
        for name in ("nextsteps", "plan-micro", "ready"):
            with self.subTest(workflow=name):
                command = COMMANDS / f"{name}.md"
                skill = SKILLS / name / "SKILL.md"
                self.assertTrue(command.is_file(), command)
                self.assertTrue(skill.is_file(), skill)
                self.assertIn(
                    f"${{CLAUDE_HOME:-$HOME/.claude}}/skills/{name}/SKILL.md",
                    command.read_text(encoding="utf-8"),
                )

    def test_plan_micro_exports_its_required_command_dependencies(self):
        plan_micro = (SKILLS / "plan-micro" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        for name in ("e", "ironclad", "p"):
            with self.subTest(command=name):
                self.assertIn(f"/{name}", plan_micro)
                self.assertTrue((COMMANDS / f"{name}.md").is_file())

        self.assertTrue((SKILLS / "ironclad" / "SKILL.md").is_file())
        self.assertTrue(
            (SKILLS / "parallelize-to-ceiling" / "SKILL.md").is_file()
        )

    def test_parallel_contract_uses_configurable_claude_home(self):
        paths = (
            COMMANDS / "extended-library" / "parallel.md",
            COMMANDS / "p.md",
            SKILLS / "parallelize-to-ceiling" / "SKILL.md",
            REPO_ROOT / ".claude" / "agents" / "agy-pair-coder.md",
            REPO_ROOT / ".claude" / "agents" / "agy-pair-verifier.md",
        )
        for path in paths:
            content = path.read_text(encoding="utf-8")
            with self.subTest(path=path):
                self.assertNotIn("~/.claude/", content)
        for path in paths[:3]:
            self.assertIn(
                "${CLAUDE_HOME:-$HOME/.claude}",
                path.read_text(encoding="utf-8"),
            )

    def test_retry_contract_forbids_conversation_reuse_flags(self):
        paths = (
            SKILLS / "parallelize-to-ceiling" / "SKILL.md",
            REPO_ROOT / ".claude" / "agents" / "agy-pair-coder.md",
            REPO_ROOT / ".claude" / "agents" / "agy-pair-verifier.md",
        )
        for path in paths:
            content = path.read_text(encoding="utf-8")
            with self.subTest(path=path):
                self.assertNotIn("--continue", content)
                self.assertNotIn("--conversation", content)

    def test_initial_coder_worktree_is_pinned_to_callers_revision(self):
        coder = (REPO_ROOT / ".claude" / "agents" / "agy-pair-coder.md").read_text(
            encoding="utf-8"
        )
        launch = coder.split("Direct CLI (primary)", 1)[1].split(
            "**Flag reference", 1
        )[0]
        base_capture = 'if ! BASE_REVISION="$(git rev-parse HEAD)" ||'
        clean_check = 'if [ -n "$CALLER_STATUS" ]; then'
        attempt_id = 'ATTEMPT_ID="<fresh unique attempt identifier>"'
        attempt_branch = 'ATTEMPT_BRANCH="agy-coder-$ATTEMPT_ID"'
        attempt_name = 'ATTEMPT_NAME="agy-coder-$ATTEMPT_ID"'
        worktree_start = 'diskm worktree-new <repo-path> "$ATTEMPT_BRANCH" \\'
        head_check = 'git -C "$CODER_WORKTREE" rev-parse HEAD'

        self.assertIn(base_capture, launch)
        self.assertIn(clean_check, launch)
        self.assertIn(attempt_id, launch)
        self.assertIn(attempt_branch, launch)
        self.assertIn(attempt_name, launch)
        self.assertIn('--base "$BASE_REVISION"', launch)
        self.assertIn('--name "$ATTEMPT_NAME"', launch)
        self.assertIn(head_check, launch)
        self.assertIn('if [ "$CODER_HEAD" != "$BASE_REVISION" ]; then', launch)
        self.assertLess(launch.index(base_capture), launch.index(worktree_start))
        self.assertLess(launch.index(clean_check), launch.index(worktree_start))
        self.assertLess(launch.index(worktree_start), launch.index(head_check))

    def test_verifier_captures_each_attempt_to_unique_output_path(self):
        verifier = (
            REPO_ROOT / ".claude" / "agents" / "agy-pair-verifier.md"
        ).read_text(encoding="utf-8")
        self.assertIn("> \"$AGY_OUT\" 2>&1", verifier)
        self.assertIn("AGY_OUT=", verifier)

    def test_retry_handoff_repeats_checks_and_pins_prior_revision(self):
        coder = (REPO_ROOT / ".claude" / "agents" / "agy-pair-coder.md").read_text(
            encoding="utf-8"
        )
        retry = coder.split("If verifier sends VERIFICATION_FAILED:", 1)[1]
        self.assertIn("PRIOR_REVISION", retry)
        self.assertIn(
            'RETRY_ATTEMPT_ID="<fresh unique retry identifier>"', retry
        )
        self.assertIn('RETRY_BRANCH="agy-coder-$RETRY_ATTEMPT_ID"', retry)
        self.assertIn(
            'RETRY_WORKTREE_NAME="agy-coder-$RETRY_ATTEMPT_ID"', retry
        )
        self.assertIn(
            'diskm worktree-new <repo-path> "$RETRY_BRANCH" \\', retry
        )
        self.assertIn('--base "$PRIOR_REVISION"', retry)
        self.assertIn('--name "$RETRY_WORKTREE_NAME"', retry)
        self.assertIn('cd "$CODER_WORKTREE"', retry)
        self.assertIn('git -C "$CODER_WORKTREE" rev-parse HEAD', retry)
        self.assertIn("git add <explicit scoped paths>", retry)
        self.assertIn("git commit", retry)

    def test_verifier_worktree_setup_fails_closed_and_checks_revision(self):
        verifier = (
            REPO_ROOT / ".claude" / "agents" / "agy-pair-verifier.md"
        ).read_text(encoding="utf-8")
        self.assertIn(
            'VERIFIER_ATTEMPT_ID="<fresh unique attempt identifier>"', verifier
        )
        self.assertIn(
            'diskm worktree-new <repo-path> "$VERIFIER_BRANCH" \\', verifier
        )
        self.assertIn('--base "$REVISION"', verifier)
        self.assertIn('--name "$VERIFIER_WORKTREE_NAME"', verifier)
        self.assertIn(
            'if ! VERIFIER_STATUS="$(git -C "$VERIFIER_WORKTREE" status --porcelain)";',
            verifier,
        )
        self.assertIn(
            'git -C "$VERIFIER_WORKTREE" rev-parse HEAD',
            verifier,
        )
        self.assertIn('if [ "$VERIFIER_HEAD" != "$REVISION" ]; then', verifier)
        self.assertIn('if [ -n "$VERIFIER_STATUS" ]; then', verifier)

    def test_verifier_rejects_inherited_status_failure(self):
        verifier = (
            REPO_ROOT / ".claude" / "agents" / "agy-pair-verifier.md"
        ).read_text(encoding="utf-8")
        setup = verifier.split(
            "# Refuse to inherit uncommitted state", 1
        )[1].split('REVISION="<exact git SHA from IMPLEMENTATION_READY>"', 1)[0]
        self.assertIn(
            'if ! INHERITED_STATUS="$(git status --porcelain)"; then',
            setup,
        )
        self.assertIn('if [ -n "$INHERITED_STATUS" ]; then', setup)

        with tempfile.TemporaryDirectory() as temp_dir:
            fake_git = Path(temp_dir) / "git"
            fake_git.write_text("#!/bin/sh\nexit 17\n", encoding="utf-8")
            fake_git.chmod(0o755)
            env = os.environ.copy()
            # BASH_ENV=~/.bashrc would re-source the developer profile inside
            # `bash -c` and restore the real git, defeating this fixture.
            env["BASH_ENV"] = os.devnull
            env["ENV"] = os.devnull
            env["PATH"] = f"{temp_dir}:/usr/bin:/bin"
            env["LOG_DIR"] = temp_dir
            result = subprocess.run(
                ["/bin/bash", "-c", setup],
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertNotEqual(result.returncode, 0)

    def test_pair_worktree_recipes_reject_branch_reference_inspection_errors(self):
        coder = (REPO_ROOT / ".claude" / "agents" / "agy-pair-coder.md").read_text(
            encoding="utf-8"
        )
        verifier = (
            REPO_ROOT / ".claude" / "agents" / "agy-pair-verifier.md"
        ).read_text(encoding="utf-8")
        coder_initial = coder.split("#   ATTEMPT_ID=", 1)[1].split(
            "# Otherwise, verify cwd", 1
        )[0]
        coder_initial = "#   ATTEMPT_ID=" + coder_initial
        coder_initial = "\n".join(
            line[2:] if line.startswith("# ") else line
            for line in coder_initial.splitlines()
        )

        def fenced_from(text, marker, end_marker=None):
            start = text.index(marker)
            end = (
                text.index(end_marker, start)
                if end_marker
                else text.index("\n```", start)
            )
            return text[start:end]

        recipes = (
            ("coder-initial", coder_initial),
            (
                "coder-retry",
                fenced_from(coder, 'RETRY_ATTEMPT_ID="<fresh unique retry identifier>"'),
            ),
            (
                "verifier-initial",
                fenced_from(
                    verifier,
                    'VERIFIER_ATTEMPT_ID="<fresh unique attempt identifier>"',
                    "# Enter the fresh branch worktree",
                ),
            ),
            (
                "verifier-retry",
                fenced_from(verifier, 'VERIFIER_ATTEMPT_ID="<fresh unique retry identifier>"'),
            ),
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            repo = root / "repo"
            repo.mkdir()
            subprocess.run(
                ["git", "init", "-q", "-b", "main"], cwd=repo, check=True
            )
            home = root / "home"
            (home / ".worktrees").mkdir(parents=True)
            bindir = root / "bin"
            bindir.mkdir()
            fake_git = bindir / "git"
            fake_git.write_text(
                "#!/bin/sh\n"
                "case \"$1\" in\n"
                "  rev-parse) printf '%s\\n' \"$BASE_REVISION\" ;;\n"
                "  status) exit 0 ;;\n"
                "  show-ref) exit 128 ;;\n"
                "  *) exit 1 ;;\n"
                "esac\n",
                encoding="utf-8",
            )
            fake_git.chmod(0o755)
            fake_diskm = bindir / "diskm"
            fake_diskm.write_text(
                "#!/bin/sh\nprintf called > \"$DISKM_CALLED\"\n",
                encoding="utf-8",
            )
            fake_diskm.chmod(0o755)

            for name, recipe in recipes:
                with self.subTest(recipe=name):
                    script = recipe.replace(
                        "<repo-path>", shlex.quote(str(repo))
                    )
                    env = {
                        **os.environ,
                        "HOME": str(home),
                        "PATH": f"{bindir}:/usr/bin:/bin",
                        "BASE_REVISION": "a" * 40,
                        "PRIOR_REVISION": "a" * 40,
                        "REVISION": "a" * 40,
                        "DISKM_CALLED": str(root / f"{name}.diskm"),
                    }
                    result = subprocess.run(
                        ["/bin/bash", "-c", script],
                        cwd=repo,
                        env=env,
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    self.assertNotEqual(result.returncode, 0, result.stdout)
                    self.assertFalse(Path(env["DISKM_CALLED"]).exists())

    def test_verifier_retries_are_read_only_and_do_not_commit(self):
        verifier = (
            REPO_ROOT / ".claude" / "agents" / "agy-pair-verifier.md"
        ).read_text(encoding="utf-8")
        retry = verifier.split("### Retry handling", 1)[1].split(
            "## Communication Protocol", 1
        )[0]
        self.assertIn(
            'diskm worktree-new <repo-path> "$VERIFIER_BRANCH" \\', retry
        )
        self.assertIn('--base "$REVISION"', retry)
        self.assertIn('--name "$VERIFIER_WORKTREE_NAME"', retry)
        self.assertIn(
            'VERIFIER_ATTEMPT_ID="<fresh unique retry identifier>"', retry
        )
        self.assertIn(
            'VERIFIER_BRANCH="agy-verifier-$VERIFIER_ATTEMPT_ID"', retry
        )
        self.assertIn('cd "$VERIFIER_WORKTREE"', retry)

    def test_verifier_launch_is_background_and_surfaces_unique_output(self):
        verifier = (
            REPO_ROOT / ".claude" / "agents" / "agy-pair-verifier.md"
        ).read_text(encoding="utf-8")
        normalized = " ".join(verifier.split())
        self.assertIn("run_in_background: true", normalized)
        self.assertIn("agy --dangerously-skip-permissions", verifier)
        self.assertIn("--new-project", verifier)
        self.assertIn("&", verifier)
        self.assertIn("AGY_PID=$!", verifier)
        self.assertIn('wait "$AGY_PID"', verifier)
        self.assertIn('echo "AGY_OUT=$AGY_OUT"', verifier)
        self.assertIn('cat "$AGY_OUT"', verifier)

    def test_every_copyable_agy_launch_starts_a_new_project(self):
        for path in (
            REPO_ROOT / ".claude" / "agents" / "agy-pair-coder.md",
            REPO_ROOT / ".claude" / "agents" / "agy-pair-verifier.md",
        ):
            content = path.read_text(encoding="utf-8")
            lines = content.splitlines()
            launches = []
            for index, line in enumerate(lines):
                if not line.startswith("agy --dangerously-skip-permissions \\"):
                    continue
                launch = [line]
                while (
                    launch[-1].endswith("\\")
                    and index + len(launch) < len(lines)
                ):
                    launch.append(lines[index + len(launch)])
                launches.append("\n".join(launch))
            launches.extend(
                line.strip("`")
                for line in lines
                if line.strip().startswith("agy --print --new-project --sandbox")
            )
            self.assertTrue(launches, path)
            for launch in launches:
                with self.subTest(path=path, launch=launch):
                    self.assertIn("--new-project", launch)

    def test_coder_and_verifier_logs_are_unique_per_attempt(self):
        coder = (REPO_ROOT / ".claude" / "agents" / "agy-pair-coder.md").read_text(
            encoding="utf-8"
        )
        verifier = (
            REPO_ROOT / ".claude" / "agents" / "agy-pair-verifier.md"
        ).read_text(encoding="utf-8")
        self.assertIn('mktemp "$LOG_DIR/coder-attempt.XXXXXX.log"', coder)
        self.assertIn('mktemp "$LOG_DIR/verifier-attempt.XXXXXX.log"', verifier)
        self.assertNotIn("LOG=$LOG_DIR/coder.log", coder)
        self.assertNotIn("LOG=$LOG_DIR/verifier.log", verifier)

    def test_code_standards_and_cs_commands_target_valid_global_skill(self):
        for name in ("code-standards", "cs"):
            with self.subTest(command=name):
                command = COMMANDS / f"{name}.md"
                self.assertTrue(
                    command.is_file(),
                    f"Command {command} must exist as an active top-level command",
                )
                content = command.read_text(encoding="utf-8")
                self.assertNotIn("~/.claude/", content)
                self.assertNotIn(".claude/skills/", content)
                self.assertIn(
                    "${CLAUDE_HOME:-$HOME/.claude}/skills/code-standards/SKILL.md",
                    content,
                )

        skill = SKILLS / "code-standards" / "SKILL.md"
        self.assertTrue(skill.is_file(), f"Skill {skill} must exist")
        skill_content = skill.read_text(encoding="utf-8")
        self.assertNotIn("~/.claude/", skill_content)
        # Mandatory core lanes: loaded from the global export, and present in-tree.
        for required_lane in (
            "ponytail",
            "zero-framework-cognition",
            "root-cause-first",
        ):
            with self.subTest(lane=required_lane):
                self.assertIn(
                    f"${{CLAUDE_HOME:-$HOME/.claude}}/skills/{required_lane}/SKILL.md",
                    skill_content,
                )
                self.assertTrue(
                    (SKILLS / required_lane / "SKILL.md").is_file(),
                    f"Required lane skill {required_lane} must exist in repo",
                )

        # ZFC leveling is a product specialization, optional by review scope: the
        # workflow must not claim it from the global export, and when it names the
        # companion that companion resolves from a declared plugin owner.
        leveling_export = "${CLAUDE_HOME:-$HOME/.claude}/skills/zfc-leveling-roadmap/SKILL.md"
        self.assertNotIn(leveling_export, skill_content)
        self.assertFalse(
            (SKILLS / "zfc-leveling-roadmap").exists(),
            "the product leveling companion must stay out of the core export",
        )
        if "zfc-leveling-roadmap" in skill_content:
            owners = [
                root / "zfc-leveling-roadmap" / "SKILL.md"
                for root in owner_roots(REPO_ROOT)
                if root != SKILLS
            ]
            existing = [path for path in owners if path.is_file()]
            self.assertTrue(
                existing,
                "the workflow names zfc-leveling-roadmap, so a declared plugin must own it",
            )
            for path in existing:
                self.assertEqual(
                    parse_frontmatter(path.read_text(encoding="utf-8")).get("name"),
                    "zfc-leveling-roadmap",
                    path,
                )


class ParallelCommandPointerTest(unittest.TestCase):
    def test_parallel_command_dispatches_to_parallelize_to_ceiling_skill(self):
        parallel = (COMMANDS / "extended-library" / "parallel.md").read_text(encoding="utf-8")
        self.assertIn("${CLAUDE_HOME:-$HOME/.claude}/skills/parallelize-to-ceiling/SKILL.md", parallel)
        self.assertTrue((SKILLS / "parallelize-to-ceiling" / "SKILL.md").is_file())


if __name__ == "__main__":
    unittest.main()
