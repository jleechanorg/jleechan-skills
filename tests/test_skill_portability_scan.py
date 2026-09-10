"""Contract test for scripts/skill_portability_scan.py.

The scanner classifies every skill entry under a root directory into four
buckets: "proper" (a directory holding a SKILL.md with name/description
frontmatter), "improper" (a directory holding a SKILL.md with invalid or
missing name/description frontmatter, mapped to a reason string), "orphan"
(a loose <name>.md with no sibling directory), and "duplicate" (a loose
<name>.md shadowed by a sibling directory of the same name). A directory
with a SKILL.md must land in "proper" or "improper" -- never neither.

The scanner is imported lazily so pytest can still collect these tests while
scripts/skill_portability_scan.py does not exist yet.
"""

import importlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

FRONTMATTER = "---\nname: {name}\ndescription: {name} does a thing\n---\n\n# {name}\n"


def scan(root: Path) -> dict:
    return importlib.import_module("scripts.skill_portability_scan").scan(root)


def make_proper(root: Path, name: str) -> None:
    directory = root / name
    directory.mkdir(parents=True)
    (directory / "SKILL.md").write_text(FRONTMATTER.format(name=name), encoding="utf-8")


def make_loose(root: Path, name: str) -> None:
    (root / f"{name}.md").write_text(FRONTMATTER.format(name=name), encoding="utf-8")


class SkillPortabilityScanTest(unittest.TestCase):
    def setUp(self):
        self.tmp_path = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp_path, ignore_errors=True)

    def test_directory_with_valid_frontmatter_is_proper(self):
        make_proper(self.tmp_path, "alpha")
        result = scan(self.tmp_path)
        self.assertEqual(result["proper"], ["alpha"])
        self.assertEqual(result["orphan"], [])
        self.assertEqual(result["duplicate"], [])

    def test_loose_md_without_sibling_directory_is_orphan(self):
        make_loose(self.tmp_path, "beta")
        result = scan(self.tmp_path)
        self.assertEqual(result["orphan"], ["beta"])
        self.assertEqual(result["duplicate"], [])
        self.assertNotIn("beta", result["proper"])

    def test_loose_md_shadowed_by_sibling_directory_is_duplicate(self):
        make_proper(self.tmp_path, "gamma")
        make_loose(self.tmp_path, "gamma")
        result = scan(self.tmp_path)
        self.assertEqual(result["duplicate"], ["gamma"])
        self.assertEqual(result["orphan"], [])
        self.assertEqual(result["proper"], ["gamma"])

    def test_mixed_tree_separates_all_three_buckets(self):
        make_proper(self.tmp_path, "alpha")
        make_proper(self.tmp_path, "gamma")
        make_loose(self.tmp_path, "gamma")
        make_loose(self.tmp_path, "beta")
        result = scan(self.tmp_path)
        self.assertEqual(result["proper"], ["alpha", "gamma"])
        self.assertEqual(result["orphan"], ["beta"])
        self.assertEqual(result["duplicate"], ["gamma"])

    def test_directory_without_frontmatter_is_improper_not_silently_dropped(self):
        directory = self.tmp_path / "delta"
        directory.mkdir()
        (directory / "SKILL.md").write_text("# delta\n\nno frontmatter\n", encoding="utf-8")
        result = scan(self.tmp_path)
        self.assertNotIn("delta", result["proper"])
        self.assertIn("delta", result["improper"])
        self.assertIn("missing name", result["improper"]["delta"])
        self.assertIn("missing description", result["improper"]["delta"])

    def test_skill_md_missing_name_is_improper_with_reason(self):
        directory = self.tmp_path / "epsilon"
        directory.mkdir()
        (directory / "SKILL.md").write_text(
            "---\ndescription: epsilon does a thing\n---\n\n# epsilon\n", encoding="utf-8"
        )
        result = scan(self.tmp_path)
        self.assertNotIn("epsilon", result["proper"])
        self.assertEqual(result["improper"]["epsilon"], "missing name")

    def test_skill_md_missing_description_is_improper_with_reason(self):
        directory = self.tmp_path / "zeta"
        directory.mkdir()
        (directory / "SKILL.md").write_text(
            "---\nname: zeta\n---\n\n# zeta\n", encoding="utf-8"
        )
        result = scan(self.tmp_path)
        self.assertNotIn("zeta", result["proper"])
        self.assertEqual(result["improper"]["zeta"], "missing description")

    def test_skill_md_empty_name_is_improper_with_reason(self):
        directory = self.tmp_path / "eta"
        directory.mkdir()
        (directory / "SKILL.md").write_text(
            "---\nname: \ndescription: eta does a thing\n---\n\n# eta\n", encoding="utf-8"
        )
        result = scan(self.tmp_path)
        self.assertNotIn("eta", result["proper"])
        self.assertEqual(result["improper"]["eta"], "empty name")

    def test_proper_directory_is_not_also_improper(self):
        make_proper(self.tmp_path, "alpha")
        result = scan(self.tmp_path)
        self.assertNotIn("alpha", result["improper"])

    def test_scanner_exposes_scan_entry_point(self):
        module = importlib.import_module("scripts.skill_portability_scan")
        self.assertTrue(callable(module.scan))


class RealSkillsRootValidityContractTest(unittest.TestCase):
    """Repository-wide contract: no active SKILL.md package is silently dropped."""

    def test_every_skill_md_directory_lands_in_proper_or_improper(self):
        real_root = REPO_ROOT / ".claude" / "skills"
        result = scan(real_root)
        classified = set(result["proper"]) | set(result["improper"])
        skill_md_dirs = {
            entry.name
            for entry in real_root.iterdir()
            if entry.is_dir() and (entry / "SKILL.md").is_file()
        }
        self.assertEqual(
            skill_md_dirs - classified,
            set(),
            msg="every directory with a SKILL.md must classify as proper or improper",
        )

    def test_improper_packages_carry_nonempty_reasons_when_present(self):
        # Any package the scanner marks improper must have an explicit, non-empty
        # reason -- it must never be silently dropped. The count itself is not
        # asserted here: it legitimately reaches zero once every active package
        # is repaired (see acceptance criteria for bd-skill-catalog-optimization-tsg.3).
        # Prove the universal contract invariant: tolerates zero improper packages
        # (empty mapping) as well as any populated mapping of string reasons.
        def assert_improper_mapping_contract(mapping: dict) -> None:
            self.assertIsInstance(mapping, dict)
            for name, reason in mapping.items():
                self.assertIsInstance(reason, str)
                self.assertTrue(reason, msg=f"{name} improper reason must not be empty")

        with tempfile.TemporaryDirectory() as empty_dir:
            empty_result = scan(Path(empty_dir))
            self.assertEqual(empty_result["improper"], {})
            assert_improper_mapping_contract(empty_result["improper"])

        real_root = REPO_ROOT / ".claude" / "skills"
        result = scan(real_root)
        assert_improper_mapping_contract(result["improper"])


class PolicyFilesContractTest(unittest.TestCase):
    """Regression test for command and skill policy files."""

    def test_er_command_and_draft_first_pr_skill_contracts(self):
        er_path = REPO_ROOT / ".claude" / "commands" / "er.md"
        er_content = er_path.read_text(encoding="utf-8")
        self.assertIn("evidence-review/SKILL.md", er_content)
        self.assertIn("draft-first-pr/SKILL.md", er_content)
        self.assertNotIn("Two-Tier Verdicts", er_content)

        draft_pr_path = REPO_ROOT / ".claude" / "skills" / "draft-first-pr" / "SKILL.md"
        draft_pr_content = draft_pr_path.read_text(encoding="utf-8")
        self.assertIn("gh api", draft_pr_content)
        self.assertIn("clone_url", draft_pr_content)
        self.assertIn("${BASE_REMOTE}/${BASE_BRANCH}...HEAD", draft_pr_content)
        self.assertNotIn("origin/$BASE_BRANCH...HEAD", draft_pr_content)
        self.assertNotIn("origin/${BASE_BRANCH}...HEAD", draft_pr_content)
        self.assertNotIn("origin/main...HEAD", draft_pr_content)

    def test_documented_base_resolution_works_without_origin_or_main(self):
        skill_path = REPO_ROOT / ".claude" / "skills" / "draft-first-pr" / "SKILL.md"
        skill_content = skill_path.read_text(encoding="utf-8")
        section = skill_content.split("### Documentation-only `/er` exception", 1)[1]
        script = section.split("```bash\n", 1)[1].split("\n```", 1)[0]

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            remote_path = root / "example" / "skills.git"
            remote_path.parent.mkdir()
            subprocess.run(["git", "init", "--bare", remote_path], check=True, capture_output=True)

            repo = root / "repo"
            subprocess.run(["git", "init", repo], check=True, capture_output=True)
            for key, value in (("user.email", "fixture@localhost"), ("user.name", "Test User")):
                subprocess.run(["git", "-C", repo, "config", key, value], check=True, capture_output=True)
            (repo / "README.md").write_text("base\n", encoding="utf-8")
            subprocess.run(["git", "-C", repo, "add", "README.md"], check=True, capture_output=True)
            subprocess.run(["git", "-C", repo, "commit", "-m", "base"], check=True, capture_output=True)
            subprocess.run(["git", "-C", repo, "remote", "add", "upstream", remote_path], check=True, capture_output=True)
            subprocess.run(["git", "-C", repo, "push", "upstream", "HEAD:release"], check=True, capture_output=True)
            (repo / "README.md").write_text("feature\n", encoding="utf-8")
            subprocess.run(["git", "-C", repo, "commit", "-am", "feature"], check=True, capture_output=True)

            bin_dir = root / "bin"
            bin_dir.mkdir()
            fake_gh = bin_dir / "gh"
            fake_gh.write_text(
                "#!/usr/bin/env bash\n"
                "case \"$*\" in\n"
                "  *baseRepository*) exit 64 ;;\n"
                f"  api\\ *) printf 'release\\t{remote_path}\\t{remote_path}\\n' ;;\n"
                "  *) printf '42\\n' ;;\n"
                "esac\n",
                encoding="utf-8",
            )
            fake_gh.chmod(0o755)
            env = {**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}"}
            result = subprocess.run(
                ["bash", "-c", script, "base-resolution", "42"],
                cwd=repo,
                env=env,
                text=True,
                capture_output=True,
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "README.md")

    def test_documented_base_resolution_rejects_same_repo_on_foreign_host(self):
        skill_path = REPO_ROOT / ".claude" / "skills" / "draft-first-pr" / "SKILL.md"
        skill_content = skill_path.read_text(encoding="utf-8")
        section = skill_content.split("### Documentation-only `/er` exception", 1)[1]
        script = section.split("```bash\n", 1)[1].split("\n```", 1)[0]

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            approved_root = root / "approved.example"
            foreign_root = root / "foreign.example"
            approved_bare = approved_root / "example" / "skills.git"
            foreign_bare = foreign_root / "example" / "skills.git"
            approved_bare.parent.mkdir(parents=True)
            foreign_bare.parent.mkdir(parents=True)
            subprocess.run(["git", "init", "--bare", approved_bare], check=True, capture_output=True)
            subprocess.run(["git", "init", "--bare", foreign_bare], check=True, capture_output=True)

            repo = root / "repo"
            subprocess.run(["git", "init", repo], check=True, capture_output=True)
            for key, value in (
                ("user.email", "fixture@localhost"),
                ("user.name", "Test User"),
                (f"url.file://{approved_root}/.insteadOf", "https://approved.example/"),
                (f"url.file://{foreign_root}/.insteadOf", "https://foreign.example/"),
            ):
                subprocess.run(["git", "-C", repo, "config", key, value], check=True, capture_output=True)
            (repo / "README.md").write_text("base\n", encoding="utf-8")
            subprocess.run(["git", "-C", repo, "add", "README.md"], check=True, capture_output=True)
            subprocess.run(["git", "-C", repo, "commit", "-m", "base"], check=True, capture_output=True)
            subprocess.run(
                ["git", "-C", repo, "remote", "add", "a-foreign", "https://foreign.example/example/skills.git"],
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "-C", repo, "remote", "add", "z-upstream", "https://approved.example/example/skills.git"],
                check=True,
                capture_output=True,
            )
            subprocess.run(["git", "-C", repo, "push", "z-upstream", "HEAD:release"], check=True, capture_output=True)
            (repo / "README.md").write_text("feature\n", encoding="utf-8")
            subprocess.run(["git", "-C", repo, "commit", "-am", "feature"], check=True, capture_output=True)

            bin_dir = root / "bin"
            bin_dir.mkdir()
            fake_gh = bin_dir / "gh"
            fake_gh.write_text(
                "#!/usr/bin/env bash\n"
                "case \"$*\" in\n"
                "  *baseRepository*) exit 64 ;;\n"
                "  api\\ *) printf 'release\\thttps://approved.example/example/skills.git"
                "\\tgit@approved.example:example/skills.git\\n' ;;\n"
                "  *) printf '42\\n' ;;\n"
                "esac\n",
                encoding="utf-8",
            )
            fake_gh.chmod(0o755)
            env = {**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}"}
            result = subprocess.run(
                ["bash", "-c", script, "base-resolution", "42"],
                cwd=repo,
                env=env,
                text=True,
                capture_output=True,
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "README.md")



class DocumentedShellExamplesTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="skill-shell-")
        self.addCleanup(temporary.cleanup)
        self.tmp_path = Path(temporary.name)

        self._orig_env = dict(os.environ)
        self.addCleanup(self._restore_env)

        isolated_home = self.tmp_path / "fixture_home"
        isolated_home.mkdir(parents=True, exist_ok=True)
        isolated_bin = self.tmp_path / "fixture_bin"
        isolated_bin.mkdir(parents=True, exist_ok=True)
        gh_config = isolated_home / "gh"
        gh_config.mkdir(parents=True, exist_ok=True)

        self.gh_calls_file = self.tmp_path / "fixture-gh-calls.jsonl"
        gh_stub = isolated_bin / "gh"
        gh_stub.write_text(
            f"#!{sys.executable}\n"
            "import json, sys\n"
            f"with open({repr(str(self.gh_calls_file))}, 'a') as f:\n"
            "    f.write(json.dumps(sys.argv[1:]) + '\\n')\n"
            "print('FIXTURE_GH_STUB_REFUSED: external GitHub commands are disabled', file=sys.stderr)\n"
            "sys.exit(86)\n"
        )
        gh_stub.chmod(0o755)

        for key in list(os.environ):
            upper = key.upper()
            if any(part in upper for part in ("TOKEN", "SECRET", "CREDENTIAL", "API_KEY", "PASSWORD")) or key in (
                "SSH_AUTH_SOCK", "GIT_ASKPASS", "SSH_ASKPASS"
            ):
                os.environ.pop(key, None)
            if key.startswith("BASH_FUNC_gh") or key == "GH_TOKEN":
                os.environ.pop(key, None)

        os.environ["HOME"] = str(isolated_home)
        os.environ["CLAUDE_HOME"] = str(isolated_home / ".claude")
        os.environ["CODEX_HOME"] = str(isolated_home / ".codex")
        os.environ["GH_CONFIG_DIR"] = str(gh_config)
        os.environ["XDG_CONFIG_HOME"] = str(isolated_home / ".config")
        os.environ["GIT_CONFIG_GLOBAL"] = os.devnull
        os.environ["GIT_CONFIG_NOSYSTEM"] = "1"
        os.environ["GH_PROMPT_DISABLED"] = "1"
        os.environ["BASH_ENV"] = os.devnull
        os.environ["ENV"] = os.devnull
        os.environ["PATH"] = f"{isolated_bin}:{os.environ.get('PATH', '/usr/bin:/bin')}"

    def _restore_env(self):
        os.environ.clear()
        os.environ.update(self._orig_env)

    def test_claw_resolved_skill_options_are_not_invocation_options(self):
        content = (REPO_ROOT / ".claude/skills/claw-dispatch/SKILL.md").read_text()
        execution = content.split("```bash\n", 1)[1].split("\n```", 1)[0]
        # Omit only gateway setup; execute task initialization and expansion.
        script = execution.split('LOGDIR="', 1)[0]
        script += 'TASK_WITH_RESOLVED="$TASK_DESCRIPTION"' + execution.split(
            'TASK_WITH_RESOLVED="$TASK_DESCRIPTION"', 1
        )[1].split("# General AO-dispatch directive", 1)[0]
        definition = (
            REPO_ROOT / ".claude/skills/orchconverge/SKILL.md"
        ).read_text()
        repo = self.tmp_path / "dispatch repo"
        owner = repo / ".claude/skills/orchconverge/SKILL.md"
        owner.parent.mkdir(parents=True)
        owner.write_text(definition)
        home = self.tmp_path / "dispatch home"
        home.mkdir()
        task = "/orchconverge repair the selected task"
        cases = (
            (task, None, "", "false||false", task),
            ("--max-attempts 7 " + task, None, "7", "false||false", task),
            (task + " --max-attempts=12", None, "12", "false||false", task),
            (task, "4", "4", "false||false", task),
            ("--max-attempts 7 " + task, "4", "7", "false||false", task),
            ("--max-attempts 3junk " + task, None, None, "", task),
            ("--bidi " + task, None, "", "true||false", task),
            ("--hermes " + task, None, "", "false||true", task),
            (
                "--continue previous " + task, None, "", "false|previous|false",
                "--continue previous " + task,
            ),
            ("--bidi --max-attempts 7 " + task, None, "7", "true||false", task),
            ("--hermes " + task + " --max-attempts=12", None, "12",
             "false||true", task),
            ("--bidiography " + task, None, "", "false||false",
             "--bidiography " + task),
            ("--hermesize " + task, None, "", "false||false",
             "--hermesize " + task),
            ("--continuefoo " + task, None, "", "false||false",
             "--continuefoo " + task),
        )
        for arguments, inherited, expected, controls, requested in cases:
            with self.subTest(arguments=arguments, inherited=inherited):
                env = {**os.environ, "HOME": str(home), "ARGUMENTS": arguments}
                env.pop("CLAW_MAX_ATTEMPTS", None)
                if inherited is not None:
                    env["CLAW_MAX_ATTEMPTS"] = inherited
                result = subprocess.run(
                    ["bash", "-c", script
                     + '\nprintf "CONTROLS:%s|%s|%s\\n" '
                     + '"$BIDI_MODE" "$CONTINUE_SESSION" "$FORCE_HERMES"'
                     + '\nprintf "DISPATCH:%s\\n%s\\n" '
                     + '"${CLAW_MAX_ATTEMPTS:-}" "$TASK_WITH_RESOLVED"'],
                    cwd=repo, env=env, text=True, capture_output=True, timeout=10,
                    check=False,
                )
                if expected is None:
                    self.assertNotEqual(result.returncode, 0)
                    self.assertNotIn("DISPATCH:", result.stdout)
                    continue
                self.assertEqual(result.returncode, 0, result.stderr)
                actual_controls = result.stdout.split("CONTROLS:", 1)[1].splitlines()[0]
                self.assertEqual(actual_controls, controls)
                payload = result.stdout.split("DISPATCH:" + expected + "\n", 1)[1]
                self.assertTrue(
                    payload.startswith("The user asked: " + requested + "\n")
                )
                self.assertIn("\n---\n" + definition.rstrip("\n") + "\n---", payload)
                directive = "This worker invocation has an explicitly configured limit"
                self.assertEqual(payload.count(directive), 1 if expected else 0)

    def test_dark_factory_prerequisite_propagates_binary_failure(self):
        content = (REPO_ROOT / ".claude/skills/dark-factory/SKILL.md").read_text()
        resolver = content.split("resolve_dark_factory_home() {", 1)[1]
        resolver = "resolve_dark_factory_home() {" + resolver.split("\n```", 1)[0]
        verification = content.split("1. **Verify binary install**", 1)[1]
        verification = verification.split("```bash\n", 1)[1].split("\n   ```", 1)[0]
        for index, help_status in enumerate((0, 42, None)):
            with self.subTest(help_status=help_status):
                home = self.tmp_path / f"factory home {index}"
                binary = home / ".local/bin/dark-factory"
                binary.parent.mkdir(parents=True)
                installed = home / "factory/bin/dark-factory"
                installed.parent.mkdir(parents=True)
                installed.write_text("#!/bin/sh\nexit 0\n")
                installed.chmod(0o755)
                if help_status is not None:
                    binary.write_text(
                        '#!/bin/sh\n[ "$1" = "--help" ] || exit 99\n'
                        + f"exit {help_status}\n"
                    )
                    binary.chmod(0o755)
                result = subprocess.run(
                    ["/bin/bash", "-c", resolver + "\n" + verification
                     + '\nprintf "PIPELINE_START\\n"'],
                    env={
                        **os.environ, "HOME": str(home), "PATH": "/usr/bin:/bin",
                        "DARK_FACTORY_HOME": str(home / "factory"),
                    },
                    text=True, capture_output=True, timeout=10, check=False,
                )
                if help_status == 0:
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertIn("PIPELINE_START", result.stdout)
                else:
                    self.assertNotEqual(result.returncode, 0)
                    self.assertNotIn("PIPELINE_START", result.stdout)

    def test_claw_attempt_option_rejects_malformed_limits_before_dispatch(self):
        content = (REPO_ROOT / ".claude/skills/claw-dispatch/SKILL.md").read_text()
        parser = content.split("# An explicit max-attempts option", 1)[1]
        parser = "# An explicit max-attempts option" + parser.split(
            "export CLAW_MAX_ATTEMPTS", 1
        )[0] + "export CLAW_MAX_ATTEMPTS\n"

        def execute(task, inherited_limit=None):
            env = {**os.environ, "TASK_DESCRIPTION": task}
            env.pop("CLAW_MAX_ATTEMPTS", None)
            if inherited_limit is not None:
                env["CLAW_MAX_ATTEMPTS"] = inherited_limit
            return subprocess.run(
                ["bash", "-c", "set -euo pipefail\n" + parser
                 + '\nprintf "DISPATCH:%s\\n%s\\n" '
                 + '"${CLAW_MAX_ATTEMPTS:-}" "$TASK_DESCRIPTION"'],
                env=env, text=True, capture_output=True, timeout=10,
            )

        cases = (
            ("do the task", True, ""),
            ("--max-attempts 7 do the task", True, "7"),
            ("do the task --max-attempts=12", True, "12"),
            ("--max-attempts\n9 do the task", True, "9"),
            ("--max-attempts", False, ""),
            ("--max-attempts=", False, ""),
            ("--max-attempts 0", False, ""),
            ("--max-attempts -2", False, ""),
            ("--max-attempts nope", False, ""),
            ("--max-attempts 3junk", False, ""),
            ("--max-attempts 3.5", False, ""),
            ("--max-attempts 3 --max-attempts 4", False, ""),
            ("--max-attempts 3", False, ""),
        )
        for task, valid, expected_limit in cases:
            with self.subTest(task=task):
                result = execute(task)
                if valid:
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertIn("DISPATCH:" + expected_limit + "\n", result.stdout)
                    self.assertIn("do the task", result.stdout)
                    self.assertNotIn("--max-attempts", result.stdout)
                    if not expected_limit:
                        self.assertNotIn("configured limit", result.stdout)
                else:
                    self.assertNotEqual(result.returncode, 0)
                    self.assertNotIn("DISPATCH:", result.stdout)
        for inherited in ("4", "0", "invalid"):
            with self.subTest(inherited=inherited):
                result = execute("do the task", inherited)
                if inherited == "4":
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertIn("DISPATCH:4\n", result.stdout)
                else:
                    self.assertNotEqual(result.returncode, 0)
                    self.assertNotIn("DISPATCH:", result.stdout)
        override = execute("--max-attempts 7 do the task", "4")
        self.assertEqual(override.returncode, 0, override.stderr)
        self.assertIn("DISPATCH:7\n", override.stdout)

        for empty_task in ("", "   ", "\t\n"):
            with self.subTest(empty_task=repr(empty_task)):
                for inherited in (None, "5"):
                    res = execute(empty_task, inherited)
                    self.assertNotEqual(res.returncode, 0)
                    self.assertNotIn("DISPATCH:", res.stdout)

    def test_documented_gh_resolution_prefers_path_then_local_executable(self):
        content = (
            REPO_ROOT / ".claude/skills/github-cli-reference/SKILL.md"
        ).read_text()
        section = content.split("### Step 0:", 1)[1]
        script = section.split("```bash\n", 1)[1].split("\n```", 1)[0]
        for index, (on_path, local_executable) in enumerate(
            ((True, True), (False, True), (False, False))
        ):
            with self.subTest(on_path=on_path, local=local_executable):
                home = self.tmp_path / f"gh home {index}"
                bin_dir = home / "path bin"
                bin_dir.mkdir(parents=True)
                local_gh = home / ".local/bin/gh"
                local_gh.parent.mkdir(parents=True)
                local_gh.write_text("#!/bin/sh\nprintf 'local-gh\\n'\n")
                local_gh.chmod(0o755 if local_executable else 0o644)
                path_gh = bin_dir / "gh"
                if on_path:
                    path_gh.write_text("#!/bin/sh\nprintf 'path-gh\\n'\n")
                    path_gh.chmod(0o755)
                env = {**os.environ, "HOME": str(home), "PATH": str(bin_dir)}
                env.pop("GH", None)
                result = subprocess.run(
                    ["/bin/bash", "-c", script
                     + '\nprintf "RESOLVED=%s\\n" "${GH:-}"'],
                    env=env, text=True, capture_output=True, timeout=10,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                expected = path_gh if on_path else local_gh if local_executable else ""
                self.assertIn(f"RESOLVED={expected}\n", result.stdout)

    def test_documented_worktree_creation_uses_explicit_base_or_head(self):
        content = (
            REPO_ROOT / ".claude/skills/superpowers-using-git-worktrees/SKILL.md"
        ).read_text()
        section = content.split("### 1. Create Worktree", 1)[1]
        script = section.split("```bash\n", 1)[1].split("\n```", 1)[0]
        repo = self.tmp_path / "base repo"
        env = {
            **os.environ, "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
        }

        def git(*args):
            return subprocess.run(
                ["git", "-c", "core.hooksPath=/dev/null", "-C", str(repo), *args],
                env=env, text=True, capture_output=True, check=True, timeout=30,
            ).stdout.strip()

        repo.mkdir()
        git("init")
        git("config", "user.email", "fixture@localhost")
        git("config", "user.name", "Fixture")
        git("config", "core.hooksPath", "/dev/null")
        (repo / "README.md").write_text("base\n")
        git("add", "README.md")
        git("commit", "-m", "base")
        base = git("rev-parse", "HEAD")
        git("update-ref", "refs/remotes/origin/main", base)
        (repo / "README.md").write_text("later\n")
        git("commit", "-am", "later")
        head = git("rev-parse", "HEAD")
        for index, base_ref in enumerate((None, "", "origin/main")):
            with self.subTest(base_ref=base_ref):
                run_env = {
                    **env, "LOCATION": str(self.tmp_path / "worktree area"),
                    "BRANCH_NAME": f"fixture-{index}",
                }
                run_env.pop("BASE_REF", None)
                if base_ref is not None:
                    run_env["BASE_REF"] = base_ref
                result = subprocess.run(
                    ["bash", "-c", "set -eu\n" + script
                     + '\nprintf "ACTUAL=%s\\n" "$(git rev-parse HEAD)"'],
                    cwd=repo, env=run_env, text=True, capture_output=True, timeout=30,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("ACTUAL=" + (base if base_ref else head), result.stdout)

    def test_documented_evidence_review_bundle_integrity_snippet_behavior(self):
        content = (
            REPO_ROOT / ".claude/skills/evidence-review/SKILL.md"
        ).read_text()
        section = content.split("### 1. Bundle integrity", 1)[1]
        raw_snippet = section.split("```bash\n", 1)[1].split("\n```", 1)[0]

        def run_check(bundle_dir: Path, extra_env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
            # Replace placeholder with bundle_dir path
            snippet = raw_snippet.replace("'<bundle_dir>'", f"'{bundle_dir}'").replace('"<bundle_dir>"', f'"{bundle_dir}"')
            env = {**os.environ, **extra_env} if extra_env else None
            return subprocess.run(
                ["bash", "-c", snippet],
                capture_output=True, text=True, timeout=10,
                env=env,
            )

        # 1. Absent bundle directory -> non-zero exit code (1)
        res_absent = run_check(self.tmp_path / "absent_bundle")
        self.assertNotEqual(res_absent.returncode, 0)
        self.assertIn("Failed to enter bundle directory", res_absent.stderr)

        # 2. Valid checksum with spaces in directory and file names -> exit 0
        bundle = self.tmp_path / "bundle with spaces"
        bundle.mkdir()
        sub = bundle / "nested dir"
        sub.mkdir()
        target_file = sub / "file with spaces.txt"
        target_file.write_text("valid payload content\n")
        cs_file = sub / "item.sha256"
        sha = subprocess.run(["sha256sum", target_file.name], cwd=sub, capture_output=True, text=True, check=True).stdout
        cs_file.write_text(sha)

        res_valid = run_check(bundle)
        self.assertEqual(res_valid.returncode, 0, res_valid.stderr + res_valid.stdout)

        # 3. Failing nested checksum -> must propagate non-zero exit code (1), not exit 0
        cs_file.write_text("0000000000000000000000000000000000000000000000000000000000000000  file with spaces.txt\n")
        res_fail = run_check(bundle)
        self.assertNotEqual(res_fail.returncode, 0, "Nested checksum failure must not exit 0")

        # 4. No checksum files found -> exit 2
        empty_bundle = self.tmp_path / "empty_bundle"
        empty_bundle.mkdir()
        res_empty = run_check(empty_bundle)
        self.assertEqual(res_empty.returncode, 2)

        # 5. Stub find yields valid NUL path then exits 7 -> must fail closed (non-zero)
        stub_dir = self.tmp_path / "find_stub_bin"
        stub_dir.mkdir(parents=True, exist_ok=True)
        stub_find = stub_dir / "find"
        stub_find.write_text(f"""#!/bin/sh
printf '%s\\0' './nested dir/item.sha256'
exit 7
""")
        stub_find.chmod(0o755)
        cs_file.write_text(sha)
        res_find_fail = run_check(bundle, extra_env={"PATH": f"{stub_dir}:{os.environ.get('PATH', '')}"})
        self.assertNotEqual(res_find_fail.returncode, 0, "Find traversal error (exit 7) must propagate non-zero exit code even when checksum file was found")


    def test_documented_worktree_safety_verification_ignore_snippet_behavior(self):
        content = (
            REPO_ROOT / ".claude/skills/superpowers-using-git-worktrees/SKILL.md"
        ).read_text()
        section = content.split("### For Project-Local Directories (.worktrees or worktrees)", 1)[1]
        raw_snippet = section.split("```bash\n", 1)[1].split("\n```", 1)[0]

        repo = self.tmp_path / "wt_repo"
        repo.mkdir()
        env = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}
        subprocess.run(["git", "init"], cwd=repo, env=env, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test.local"], cwd=repo, env=env, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, env=env, check=True, capture_output=True)
        (repo / "README.md").write_text("repo root\n")
        subprocess.run(["git", "add", "."], cwd=repo, env=env, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=repo, env=env, check=True, capture_output=True)

        exclude_file = repo / ".git/info/exclude"

        def run_verify(location_str: str, cwd: Path = repo) -> subprocess.CompletedProcess[str]:
            return subprocess.run(
                ["bash", "-c", raw_snippet],
                cwd=cwd,
                env={**env, "LOCATION": location_str},
                capture_output=True, text=True, timeout=10,
            )

        # 1. Relative in-repo path (.worktrees) that is unignored must be handled and added to info/exclude
        run_verify(".worktrees")
        self.assertTrue(exclude_file.exists(), "info/exclude should exist after checking unignored relative path")
        self.assertIn(".worktrees", exclude_file.read_text())

        # 2. Absolute in-repo path that is unignored must also be handled and added to info/exclude
        exclude_file.write_text("")
        run_verify(str(repo / "worktrees"))
        self.assertEqual(exclude_file.read_text().strip(), "worktrees")

        # 3. External mktemp directory outside repo must NOT modify info/exclude
        exclude_file.write_text("")
        external_mktemp = self.tmp_path / "external_wt_temp"
        external_mktemp.mkdir()
        res_ext = run_verify(str(external_mktemp))
        self.assertEqual(res_ext.returncode, 0)
        self.assertEqual(exclude_file.read_text().strip(), "", "External path must not write to info/exclude")

        # 4. Running outside a git repo must fail informatively with non-zero exit code
        res_nogit = run_verify(str(self.tmp_path / "wt"), cwd=self.tmp_path)
        self.assertNotEqual(res_nogit.returncode, 0, "Running outside a git repo must fail")

        # 5. Git call failure (e.g. invalid git dir) must exit non-zero without modifying exclude
        exclude_file.write_text("")
        fake_git_dir = repo / "broken_git"
        res_err = subprocess.run(
            ["bash", "-c", raw_snippet],
            cwd=repo,
            env={**env, "LOCATION": ".worktrees", "GIT_DIR": str(fake_git_dir)},
            capture_output=True, text=True, timeout=10,
        )
        self.assertNotEqual(res_err.returncode, 0, "Git failure must exit non-zero")
        self.assertEqual(exclude_file.read_text().strip(), "", "Git failure must not write to info/exclude")

        # 6. LOCATION exactly equal to repository root must be rejected before child classification
        exclude_file.write_text("")
        res_root = run_verify(str(repo))
        self.assertNotEqual(res_root.returncode, 0, "LOCATION equal to repository root must fail")
        self.assertIn("repository root", res_root.stderr)
        self.assertEqual(exclude_file.read_text().strip(), "", "Exact repository root must not write to info/exclude")

        # Relative '.' resolving to repository root must also be rejected
        res_dot = run_verify(".")
        self.assertNotEqual(res_dot.returncode, 0, "LOCATION equal to '.' (repo root) must fail")
        self.assertIn("repository root", res_dot.stderr)
        self.assertEqual(exclude_file.read_text().strip(), "", "Repo root '.' must not write to info/exclude")

    def test_documented_shell_fixture_enforces_gh_containment_and_credential_isolation(self):
        # 1. Verify sensitive tokens are stripped from os.environ
        for key in os.environ:
            upper = key.upper()
            self.assertFalse(
                any(part in upper for part in ("TOKEN", "SECRET", "CREDENTIAL", "API_KEY", "PASSWORD")),
                f"Sensitive variable {key} must not be present in fixture environment",
            )
        # 2. Verify gh fails closed with exit code 86 and fixture marker
        res = subprocess.run(["gh", "release", "create", "test-fixture-check"], capture_output=True, text=True)
        self.assertEqual(res.returncode, 86)
        self.assertIn("FIXTURE_GH_STUB_REFUSED", res.stderr)
        # 3. Verify gh in subshell bash -c also fails closed
        res_bash = subprocess.run(["bash", "-c", "gh release create test-fixture-check-bash"], capture_output=True, text=True)
        self.assertEqual(res_bash.returncode, 86)
        self.assertIn("FIXTURE_GH_STUB_REFUSED", res_bash.stderr)
        self.assertTrue(self.gh_calls_file.exists())
        self.assertGreaterEqual(len(self.gh_calls_file.read_text().splitlines()), 2)

    def test_writing_plans_markdown_code_fence_structure(self):
        content = (REPO_ROOT / ".claude/skills/superpowers-writing-plans/SKILL.md").read_text()
        lines = content.splitlines()
        in_fence = False
        fence_char = None
        fence_len = 0
        remember_in_fence = None
        handoff_in_fence = None

        for line in lines:
            stripped = line.strip()
            if stripped.startswith("```") or stripped.startswith("~~~"):
                c = stripped[0]
                flen = len(stripped) - len(stripped.lstrip(c))
                if not in_fence:
                    in_fence = True
                    fence_char = c
                    fence_len = flen
                else:
                    if c == fence_char and flen >= fence_len:
                        in_fence = False
                        fence_char = None
                        fence_len = 0
            if stripped.startswith("## Remember"):
                remember_in_fence = in_fence
            if stripped.startswith("## Execution Handoff"):
                handoff_in_fence = in_fence

        self.assertFalse(in_fence, "File must not end inside an open code fence")
        self.assertFalse(remember_in_fence, "## Remember must not be inside a code fence")
        self.assertFalse(handoff_in_fence, "## Execution Handoff must not be inside a code fence")

    def test_engplan_concurrency_query_validation_and_uniqueness(self):
        content = (REPO_ROOT / ".claude/skills/engplan/SKILL.md").read_text()
        section = content.split("### Rule 1: File-exclusive ownership", 1)[1]
        raw_snippet = section.split("```bash\n", 1)[1].split("\n```", 1)[0]

        # 1. Default raw snippet (TARGET_FILES=()) must fail before calling gh
        res_default = subprocess.run(["bash", "-c", raw_snippet], capture_output=True, text=True)
        self.assertNotEqual(res_default.returncode, 0, "Default empty TARGET_FILES must fail before gh")
        self.assertIn("TARGET_FILES", res_default.stderr)

        # 2. Angle placeholder target files must fail before calling gh
        fail_placeholder = 'TARGET_FILES=("<FILE_LIST>")\n' + raw_snippet.split("TARGET_FILES=", 1)[1].split("\n", 1)[1]
        res_placeholder = subprocess.run(["bash", "-c", fail_placeholder], capture_output=True, text=True)
        self.assertNotEqual(res_placeholder.returncode, 0, "Placeholder TARGET_FILES must fail before gh")
        self.assertIn("TARGET_FILES", res_placeholder.stderr)

        # 3. Dummy path/to/ placeholder target files must fail before calling gh
        fail_dummy = 'TARGET_FILES=("path/to/file1.py")\n' + raw_snippet.split("TARGET_FILES=", 1)[1].split("\n", 1)[1]
        res_dummy = subprocess.run(["bash", "-c", fail_dummy], capture_output=True, text=True)
        self.assertNotEqual(res_dummy.returncode, 0, "Dummy path/to/ TARGET_FILES must fail before gh")
        self.assertIn("TARGET_FILES", res_dummy.stderr)

        # 4. Caller survival on failure (subshell protects caller)
        caller_script = (
            "set -e\n"
            "status=0\n"
            + raw_snippet + " || status=$?\n"
            "printf 'CALLER_SURVIVED:%s\\n' \"$status\"\n"
        )
        res_caller = subprocess.run(["bash", "-c", caller_script], capture_output=True, text=True)
        self.assertEqual(res_caller.returncode, 0, res_caller.stderr)
        self.assertIn("CALLER_SURVIVED:1\n", res_caller.stdout)

        # 5. Unique PR numbers when stub returns duplicate hits
        stub_dir = self.tmp_path / "stub_gh_bin"
        stub_dir.mkdir(exist_ok=True)
        fake_gh = stub_dir / "gh"
        calls_file = self.tmp_path / "engplan-stub-calls.jsonl"
        fake_gh.write_text(f"""#!{sys.executable}
import json, sys
with open({repr(str(calls_file))}, "a") as f:
    f.write(json.dumps(sys.argv[1:]) + "\\n")
print(json.dumps([
  {{"number": 101, "files": [{{"path": "a.py"}}, {{"path": "b.py"}}]}},
  {{"number": 102, "files": [{{"path": "c.py"}}]}}
]))
""")
        fake_gh.chmod(0o755)

        run_env = {**os.environ, "PATH": f"{stub_dir}:{os.environ['PATH']}"}
        test_snippet = 'TARGET_FILES=("a.py" "b.py")\n' + raw_snippet.split("TARGET_FILES=", 1)[1].split("\n", 1)[1]
        res_unique = subprocess.run(["bash", "-c", test_snippet], env=run_env, capture_output=True, text=True)
        self.assertEqual(res_unique.returncode, 0, res_unique.stderr + res_unique.stdout)
        nums = [line.strip() for line in res_unique.stdout.splitlines() if line.strip().isdigit()]
        self.assertEqual(nums, ["101"])
        self.assertTrue(calls_file.exists())
        self.assertGreaterEqual(len(calls_file.read_text().splitlines()), 1)

        # 6. Propagate actual gh failures rather than reporting zero overlap
        fake_gh.write_text(f"""#!{sys.executable}
import sys
sys.stderr.write("GH_NETWORK_FAILURE\\n")
sys.exit(1)
""")
        fake_gh.chmod(0o755)
        res_gh_fail = subprocess.run(["bash", "-c", test_snippet], env=run_env, capture_output=True, text=True)
        self.assertNotEqual(res_gh_fail.returncode, 0, "gh failure must propagate non-zero exit")
        self.assertNotIn("No overlapping", res_gh_fail.stdout)

        # 7. Propagate actual jq failures rather than reporting zero overlap
        fake_gh.write_text(f"""#!{sys.executable}
print("NOT_VALID_JSON")
""")
        fake_gh.chmod(0o755)
        res_jq_fail = subprocess.run(["bash", "-c", test_snippet], env=run_env, capture_output=True, text=True)
        self.assertNotEqual(res_jq_fail.returncode, 0, "jq failure must propagate non-zero exit")
        self.assertNotIn("No overlapping", res_jq_fail.stdout)

        # 8. Plan template section references Rule 1 rather than duplicating the full query
        template_section = content.split("### Concurrency Rule (template)", 1)[1].split("### Size Constraints", 1)[0]
        self.assertNotIn("gh pr list --state open", template_section, "Plan template must not duplicate full gh query")
        self.assertIn("Rule 1", template_section, "Plan template must reference Rule 1")

    def test_tmux_and_ui_non_runnable_templates(self):
        standalone = REPO_ROOT / ".claude/skills/tmux-video-evidence/SKILL.md"
        companion = REPO_ROOT / ".claude/skills/evidence-standards/tmux-video-evidence.md"
        ui_skill = REPO_ROOT / ".claude/skills/ui-video-evidence/SKILL.md"

        standalone_content = standalone.read_text(encoding="utf-8")
        companion_content = companion.read_text(encoding="utf-8")
        ui_content = ui_skill.read_text(encoding="utf-8")

        # 1. tmux template must use text fence, not bash
        self.assertIn("## Evidence Script Template", standalone_content)
        self.assertIn("/tmp/${WORK_NAME:-work}_evidence.sh", standalone_content)
        script_sec = standalone_content.split("## Evidence Script Template", 1)[1].split("## Recording", 1)[0]
        self.assertIn("```text\n", script_sec, "tmux Evidence Script Template must be non-runnable text fence")
        self.assertNotIn("```bash\n", script_sec, "tmux Evidence Script Template must not be bash fence")

        # 2. No invented defaults ${PR_NUMBER:-1} or ${TEST_COMMAND:-pytest}
        self.assertNotIn("${PR_NUMBER:-1}", script_sec)
        self.assertNotIn("${TEST_COMMAND:-pytest}", script_sec)
        self.assertIn("<PR_NUMBER>", script_sec)
        self.assertIn("<SCOPED_TEST_COMMAND>", script_sec)

        # 3. Companion copy agrees with standalone
        self.assertEqual(standalone_content, companion_content, "Companion tmux-video-evidence.md must match standalone SKILL.md")

        # 4. Slack upload template in ui-video-evidence must use text fence, not bash
        slack_sec = ui_content.split("## Slack Distribution", 1)[1]
        self.assertIn("```text\n", slack_sec, "Slack upload template must use text fence")
        self.assertNotIn("```bash\n", slack_sec, "Slack upload template must not use bash fence")

        # 5. Diff truncation under pipefail must not use head -80; must use sed -n '1,80p'
        self.assertNotIn("| head -80", script_sec, "tmux script diff pipeline must not pipe to head under pipefail")
        self.assertIn("sed -n '1,80p'", script_sec, "tmux script diff pipeline must use sed -n '1,80p'")

        # 6. Sanitization pipeline must redact Linux /home, CI /workspace, and /tmp
        self.assertIn("s#/home/[^/]+/#/home/REDACTED/#g", script_sec)
        self.assertIn("s#/workspace/[^[:space:]]+#/workspace/REDACTED#g", script_sec)
        self.assertIn("s#/tmp/[^[:space:]]+#/tmp/REDACTED#g", script_sec)

    def test_tmux_diff_truncation_pipefail_behavior_and_sanitization(self):
        large_diff_cmd = (
            "set -euo pipefail; "
            "python3 -c 'import sys; [sys.stdout.write(f\"diff line {i}\\n\") for i in range(1000)]' "
            "| sed -n '1,80p'; "
            "echo 'POST_DIFF_SENTINEL'"
        )
        res_diff = subprocess.run(["bash", "-c", large_diff_cmd], capture_output=True, text=True)
        self.assertEqual(res_diff.returncode, 0)
        self.assertIn("POST_DIFF_SENTINEL", res_diff.stdout)
        lines = [line for line in res_diff.stdout.splitlines() if line.startswith("diff line")]
        self.assertEqual(len(lines), 80)

        sed_pipeline = (
            "sed -E "
            "-e 's#/Users/[^/]+/#/Users/REDACTED/#g' "
            "-e 's#/home/[^/]+/#/home/REDACTED/#g' "
            "-e 's#/private/var/folders/[^[:space:]]+#/private/var/folders/REDACTED#g' "
            "-e 's#/workspace/[^[:space:]]+#/workspace/REDACTED#g' "
            "-e 's#/tmp/[^[:space:]]+#/tmp/REDACTED#g'"
        )
        test_payload = (
            "mac: /Users/alice/repo/a.py\n"
            "mac_space_user: /Users/alice smith/repo/b.py\n"
            "mac_var: /private/var/folders/2b/xyz123/T/test.log\n"
            "linux: /home/bob/repo/c.py\n"
            "linux_space_user: /home/bob builder/repo/d.py\n"
            "workspace: /workspace/project/e.py\n"
            "workspace_space_surrounding: running /workspace/job-123/task in parallel\n"
            "tmp: /tmp/scratch_dir/f.py\n"
            "tmp_space_surrounding: output written to /tmp/build-456/summary.txt successfully\n"
        )
        res_sed = subprocess.run(
            ["bash", "-c", f"cat << 'EOF' | {sed_pipeline}\n{test_payload}EOF"],
            capture_output=True, text=True,
        )
        self.assertEqual(res_sed.returncode, 0)
        out = res_sed.stdout
        self.assertIn("mac: /Users/REDACTED/repo/a.py", out)
        self.assertIn("mac_space_user: /Users/REDACTED/repo/b.py", out)
        self.assertIn("mac_var: /private/var/folders/REDACTED", out)
        self.assertIn("linux: /home/REDACTED/repo/c.py", out)
        self.assertIn("linux_space_user: /home/REDACTED/repo/d.py", out)
        self.assertIn("workspace: /workspace/REDACTED", out)
        self.assertIn("workspace_space_surrounding: running /workspace/REDACTED in parallel", out)
        self.assertIn("tmp: /tmp/REDACTED", out)
        self.assertIn("tmp_space_surrounding: output written to /tmp/REDACTED successfully", out)


    def _create_gh_test_env(self, test_dir: Path, calls_file: Path) -> dict[str, str]:
        disposable_home = test_dir / "disposable_home"
        disposable_home.mkdir(parents=True, exist_ok=True)
        gh_config = disposable_home / "gh"
        gh_config.mkdir(parents=True, exist_ok=True)
        stub_dir = test_dir / "bin"
        stub_dir.mkdir(parents=True, exist_ok=True)

        fake_ffprobe = stub_dir / "ffprobe"
        fake_ffprobe.write_text(f"""#!{sys.executable}
import os, sys

mode = os.environ.get("FFPROBE_STUB_MODE", "normal")
if mode == "fail":
    sys.exit(1)
if mode == "empty_stream":
    sys.exit(0)

args = sys.argv[1:]
filepath = args[-1] if args else ""
if filepath.endswith((".vtt", ".srt")):
    print("subtitle")
    sys.exit(0)
elif filepath.endswith((".mp4", ".gif", ".mov")):
    print("video")
    sys.exit(0)
else:
    print("unknown")
    sys.exit(0)
""")
        fake_ffprobe.chmod(0o755)

        fake_gh = stub_dir / "gh"
        fake_gh.write_text(f"""#!{sys.executable}
import json, os, sys

calls_file = {repr(str(calls_file))}
mode = os.environ.get("GH_STUB_MODE", "first_run")
with open(calls_file, "a") as f:
    f.write(json.dumps({{"mode": mode, "argv": sys.argv[1:]}}) + "\\n")

args = sys.argv[1:]
if len(args) >= 2 and args[0] == "release":
    subcmd = args[1]
    if subcmd == "create":
        if mode == "first_run":
            sys.exit(0)
        elif mode in ("repeat_draft", "conflicting_published", "fail_view"):
            sys.exit(1)
        sys.exit(0)
    elif subcmd == "view":
        if mode == "fail_view":
            sys.exit(1)
        if "--jq" in args:
            jq_idx = args.index("--jq")
            if args[jq_idx + 1] == ".isDraft":
                if mode in ("repeat_draft", "first_run"):
                    print("true")
                    sys.exit(0)
                elif mode == "conflicting_published":
                    print("false")
                    sys.exit(0)
                else:
                    print("false")
                    sys.exit(0)
        print(json.dumps({{"url": "https://github.com/example/repo/releases/tag/v1", "assets": [{{"name": "a", "url": "https://example.com/a"}}]}}))
        sys.exit(0)
    elif subcmd == "upload":
        if mode == "fail_upload":
            sys.exit(1)
        import shutil
        tag = None
        assets = []
        i = 2
        while i < len(args):
            if args[i] == "--repo":
                i += 2
            elif args[i].startswith("-"):
                i += 1
            elif tag is None:
                tag = args[i]
                i += 1
            else:
                assets.append(args[i])
                i += 1
        if tag:
            upload_store = os.path.join(os.path.dirname(calls_file), "mock_releases", tag)
            os.makedirs(upload_store, exist_ok=True)
            for a in assets:
                if os.path.exists(a):
                    shutil.copy2(a, os.path.join(upload_store, os.path.basename(a)))
        sys.exit(0)
    else:
        print(f"STUB_REFUSED: unknown release command {{subcmd}}", file=sys.stderr)
        sys.exit(86)
elif len(args) >= 2 and args[0] == "pr":
    subcmd = args[1]
    if subcmd == "view":
        if mode == "fail_pr_view":
            sys.exit(1)
        pr_num = "42"
        for a in args:
            if a.isdigit():
                pr_num = a
        head_sha = os.environ.get("GH_STUB_PR_HEAD", "0123456789abcdef0123456789abcdef01234567")
        if head_sha == "__EMPTY__":
            head_val = ""
        elif head_sha == "__MALFORMED__":
            head_val = "not-40-hex"
        else:
            head_val = head_sha
        pr_data = {{
            "number": int(pr_num),
            "headRefOid": head_val,
            "url": "https://github.com/intended/repo/pull/" + str(pr_num)
        }}
        body_sentinel = os.environ.get("PR_BODY_SENTINEL_FILE")
        if body_sentinel and os.path.exists(body_sentinel):
            with open(body_sentinel) as bf:
                pr_data["body"] = bf.read()
        print(json.dumps(pr_data))
        sys.exit(0)
    elif subcmd == "comment":
        sys.exit(0)
    elif subcmd == "edit":
        deny_edit = os.environ.get("GH_STUB_DENY_EDIT", "0")
        if deny_edit == "1":
            print("STUB_REFUSED: gh pr edit is forbidden in evidence workflow", file=sys.stderr)
            sys.exit(86)
        body_sentinel = os.environ.get("PR_BODY_SENTINEL_FILE")
        if body_sentinel and os.path.exists(body_sentinel):
            bf_idx = args.index("--body-file") if "--body-file" in args else -1
            if bf_idx != -1 and bf_idx + 1 < len(args):
                with open(args[bf_idx + 1]) as nbf:
                    with open(body_sentinel, "w") as obf:
                        obf.write(nbf.read())
        sys.exit(0)
    else:
        print("STUB_REFUSED: unknown pr command " + str(subcmd), file=sys.stderr)
        sys.exit(86)
else:
    print("STUB_REFUSED: unknown command " + str(args), file=sys.stderr)
    sys.exit(86)
""")
        fake_gh.chmod(0o755)

        clean_env = {
            k: v for k, v in os.environ.items()
            if not any(part in k.upper() for part in ("TOKEN", "SECRET", "CREDENTIAL", "API_KEY", "PASSWORD"))
            and not k.startswith("BASH_FUNC_gh")
            and k != "GH_TOKEN"
        }
        clean_env["HOME"] = str(disposable_home)
        clean_env["CLAUDE_HOME"] = str(disposable_home / ".claude")
        clean_env["CODEX_HOME"] = str(disposable_home / ".codex")
        clean_env["GH_CONFIG_DIR"] = str(gh_config)
        clean_env["XDG_CONFIG_HOME"] = str(disposable_home / ".config")
        clean_env["GIT_CONFIG_GLOBAL"] = os.devnull
        clean_env["GIT_CONFIG_NOSYSTEM"] = "1"
        clean_env["GH_PROMPT_DISABLED"] = "1"
        clean_env["BASH_ENV"] = os.devnull
        clean_env["ENV"] = os.devnull
        clean_env["PATH"] = f"{stub_dir}:{clean_env.get('PATH', '/usr/bin:/bin')}"
        return clean_env

    def test_video_evidence_publication_snippets_guard_unset_pr_and_contained(self):
        owners = [
            REPO_ROOT / ".claude/skills/tmux-video-evidence/SKILL.md",
            REPO_ROOT / ".claude/skills/evidence-standards/tmux-video-evidence.md",
            REPO_ROOT / ".claude/skills/ui-video-evidence/SKILL.md",
        ]
        for skill_file in owners:
            with self.subTest(owner=skill_file.name):
                content = skill_file.read_text()
                section = content.split("## Evidence access and authorized publication", 1)[1]
                blocks = section.split("```bash\n")
                self.assertGreaterEqual(len(blocks), 3, f"{skill_file.name} must split publication into two bash blocks")
                block1 = blocks[1].split("\n```", 1)[0]
                block2 = blocks[2].split("\n```", 1)[0]

                test_dir = self.tmp_path / f"pub_test_{skill_file.name}_{skill_file.parent.name}"
                test_dir.mkdir(parents=True, exist_ok=True)
                calls_file = test_dir / "gh-calls.jsonl"
                env = self._create_gh_test_env(test_dir, calls_file)

                # 0. Task-local stub must refuse unknown commands
                res_unk = subprocess.run(["gh", "repo", "delete", "some/repo"], env=env, capture_output=True, text=True)
                self.assertEqual(res_unk.returncode, 86)
                self.assertIn("STUB_REFUSED", res_unk.stderr)
                if calls_file.exists():
                    calls_file.unlink()

                # --- Block 1: Release create / upload / view ---

                # 1. Unset PR_NUMBER must fail informatively before calling gh and exit non-zero
                res_unset = subprocess.run(
                    ["bash", "-c", "unset PR_NUMBER PR_NUMBER_OR_URL\n" + block1],
                    env=env, capture_output=True, text=True,
                )
                self.assertNotEqual(res_unset.returncode, 0, f"Unset PR_NUMBER must fail in {skill_file.name}")
                self.assertIn("PR_NUMBER", res_unset.stderr)
                self.assertFalse(calls_file.exists())

                # 2. Placeholder <PR_NUMBER> must fail informatively before calling gh
                res_placeholder = subprocess.run(
                    ["bash", "-c", 'PR_NUMBER="<PR_NUMBER>"\n' + block1],
                    env=env, capture_output=True, text=True,
                )
                self.assertNotEqual(res_placeholder.returncode, 0, f"Placeholder PR_NUMBER must fail in {skill_file.name}")
                self.assertIn("PR_NUMBER", res_placeholder.stderr)
                self.assertFalse(calls_file.exists())

                # 3. Unset REPO must fail informatively before calling gh
                res_unset_repo = subprocess.run(
                    ["bash", "-c", 'PR_NUMBER="42"\nunset REPO PR_NUMBER_OR_URL\n' + block1],
                    env=env, capture_output=True, text=True,
                )
                self.assertNotEqual(res_unset_repo.returncode, 0, f"Unset REPO must fail in {skill_file.name}")
                self.assertIn("REPO", res_unset_repo.stderr)
                self.assertFalse(calls_file.exists())

                # 4. Placeholder REPO must fail informatively before calling gh
                res_placeholder_repo = subprocess.run(
                    ["bash", "-c", 'PR_NUMBER="42"\nREPO="<owner/repo>"\n' + block1],
                    env=env, capture_output=True, text=True,
                )
                self.assertNotEqual(res_placeholder_repo.returncode, 0, f"Placeholder REPO must fail in {skill_file.name}")
                self.assertIn("REPO", res_placeholder_repo.stderr)
                self.assertFalse(calls_file.exists())

                # 5. Conflicting target repository must fail before calling gh
                res_conflict_repo = subprocess.run(
                    ["bash", "-c", 'PR_NUMBER="42"\nREPO="intended/repo"\nPR_NUMBER_OR_URL="https://github.com/conflicting/repo/pull/42"\n' + block1],
                    env=env, capture_output=True, text=True,
                )
                self.assertNotEqual(res_conflict_repo.returncode, 0)
                self.assertIn("Conflicting", res_conflict_repo.stderr)
                self.assertFalse(calls_file.exists())

                # 6. Conflicting PR number must fail before calling gh
                res_conflict_pr = subprocess.run(
                    ["bash", "-c", 'PR_NUMBER="42"\nREPO="intended/repo"\nPR_NUMBER_OR_URL="https://github.com/intended/repo/pull/99"\n' + block1],
                    env=env, capture_output=True, text=True,
                )
                self.assertNotEqual(res_conflict_pr.returncode, 0)
                self.assertIn("Conflicting", res_conflict_pr.stderr)
                self.assertFalse(calls_file.exists())

                # 7. Missing video or preview file must fail before calling gh (stub gh sees 0 calls)
                dummy_video = test_dir / "video.mp4"
                dummy_video.write_bytes(b"dummy video data")
                dummy_preview = test_dir / "preview.gif"
                dummy_preview.write_bytes(b"dummy gif data")
                dummy_caption = test_dir / "captions.vtt"
                dummy_caption.write_text("WEBVTT\n\n00:00.000 --> 00:01.000\nCaption\n")

                res_missing_video = subprocess.run(
                    ["bash", "-c", f'PR_NUMBER="42"\nREPO="intended/repo"\nVIDEO_FILE="{test_dir}/nonexistent.mp4"\nPREVIEW_FILE="{dummy_preview}"\nCAPTION_FILE="{dummy_caption}"\n' + block1],
                    env=env, capture_output=True, text=True,
                )
                self.assertNotEqual(res_missing_video.returncode, 0)
                self.assertFalse(calls_file.exists(), "gh must not be called when video file is missing")

                # Empty video file must fail
                empty_video = test_dir / "empty_video.mp4"
                empty_video.write_bytes(b"")
                res_empty_video = subprocess.run(
                    ["bash", "-c", f'PR_NUMBER="42"\nREPO="intended/repo"\nVIDEO_FILE="{empty_video}"\nPREVIEW_FILE="{dummy_preview}"\nCAPTION_FILE="{dummy_caption}"\n' + block1],
                    env=env, capture_output=True, text=True,
                )
                self.assertNotEqual(res_empty_video.returncode, 0)
                self.assertFalse(calls_file.exists(), "gh must not be called when video file is empty")

                # Empty preview file must fail
                empty_preview = test_dir / "empty_preview.gif"
                empty_preview.write_bytes(b"")
                res_empty_preview = subprocess.run(
                    ["bash", "-c", f'PR_NUMBER="42"\nREPO="intended/repo"\nVIDEO_FILE="{dummy_video}"\nPREVIEW_FILE="{empty_preview}"\nCAPTION_FILE="{dummy_caption}"\n' + block1],
                    env=env, capture_output=True, text=True,
                )
                self.assertNotEqual(res_empty_preview.returncode, 0)
                self.assertFalse(calls_file.exists(), "gh must not be called when preview file is empty")

                # Missing caption file when specified
                res_missing_caption = subprocess.run(
                    ["bash", "-c", f'PR_NUMBER="42"\nREPO="intended/repo"\nVIDEO_FILE="{dummy_video}"\nPREVIEW_FILE="{dummy_preview}"\nCAPTION_FILE="{test_dir}/missing.vtt"\n' + block1],
                    env=env, capture_output=True, text=True,
                )
                self.assertNotEqual(res_missing_caption.returncode, 0)
                self.assertFalse(calls_file.exists(), "gh must not be called when declared caption file is missing")

                # Empty caption file when specified
                empty_caption = test_dir / "empty.vtt"
                empty_caption.write_bytes(b"")
                res_empty_caption = subprocess.run(
                    ["bash", "-c", f'PR_NUMBER="42"\nREPO="intended/repo"\nVIDEO_FILE="{dummy_video}"\nPREVIEW_FILE="{dummy_preview}"\nCAPTION_FILE="{empty_caption}"\n' + block1],
                    env=env, capture_output=True, text=True,
                )
                self.assertNotEqual(res_empty_caption.returncode, 0)
                self.assertFalse(calls_file.exists(), "gh must not be called when caption file is empty")

                # Missing caption choice entirely (neither CAPTION_FILE nor burned mode)
                res_no_caption_choice = subprocess.run(
                    ["bash", "-c", f'PR_NUMBER="42"\nREPO="intended/repo"\nRUN_ID="run-1"\nVIDEO_FILE="{dummy_video}"\nPREVIEW_FILE="{dummy_preview}"\n' + block1],
                    env=env, capture_output=True, text=True,
                )
                self.assertNotEqual(res_no_caption_choice.returncode, 0)
                self.assertFalse(calls_file.exists(), "gh must not be called when caption choice is missing")

                # Rejected caption aliases must fail
                for bad_cap in ('BURNED_CAPTIONS="true"', 'CAPTION_MODE="burned-in"', 'CAPTION_FILE="burned"'):
                    if calls_file.exists():
                        calls_file.unlink()
                    res_bad_cap = subprocess.run(
                        ["bash", "-c", f'PR_NUMBER="42"\nREPO="intended/repo"\nRUN_ID="run-1"\nVIDEO_FILE="{dummy_video}"\nPREVIEW_FILE="{dummy_preview}"\n{bad_cap}\n' + block1],
                        env=env, capture_output=True, text=True,
                    )
                    self.assertNotEqual(res_bad_cap.returncode, 0, f"Alias {bad_cap} must be rejected")
                    self.assertFalse(calls_file.exists(), f"gh must not be called on bad caption alias {bad_cap}")

                # Simultaneous nonempty CAPTION_FILE and CAPTION_MODE=burned must fail before calling gh
                if calls_file.exists():
                    calls_file.unlink()
                valid_sha = "0123456789abcdef0123456789abcdef01234567"
                res_both_captions = subprocess.run(
                    ["bash", "-c", f'PR_NUMBER="42"\nREPO="intended/repo"\nRUN_ID="run-1"\nCAPTURED_SHA="{valid_sha}"\nVIDEO_FILE="{dummy_video}"\nPREVIEW_FILE="{dummy_preview}"\nCAPTION_FILE="{dummy_caption}"\nCAPTION_MODE="burned"\n' + block1],
                    env=env, capture_output=True, text=True,
                )
                self.assertNotEqual(res_both_captions.returncode, 0, "Simultaneous CAPTION_FILE and CAPTION_MODE=burned must be rejected")
                self.assertFalse(calls_file.exists(), "gh must not be called when both CAPTION_FILE and CAPTION_MODE=burned are set")

                # Placeholder CAPTION_FILE with CAPTION_MODE=burned must also fail before calling gh (no placeholder exception in XOR)
                if calls_file.exists():
                    calls_file.unlink()
                res_ph_both = subprocess.run(
                    ["bash", "-c", f'PR_NUMBER="42"\nREPO="intended/repo"\nRUN_ID="run-1"\nCAPTURED_SHA="{valid_sha}"\nVIDEO_FILE="{dummy_video}"\nPREVIEW_FILE="{dummy_preview}"\nCAPTION_FILE="<caption.vtt>"\nCAPTION_MODE="burned"\n' + block1],
                    env=env, capture_output=True, text=True,
                )
                self.assertNotEqual(res_ph_both.returncode, 0, "Placeholder CAPTION_FILE with CAPTION_MODE=burned must be rejected")
                self.assertFalse(calls_file.exists(), "gh must not be called when placeholder CAPTION_FILE and CAPTION_MODE=burned are set")

                # Unsupported CAPTION_MODE with provided CAPTION_FILE must fail before calling gh
                for unsupported_mode in ('CAPTION_MODE="burned-in"', 'CAPTION_MODE="sidecar"', 'CAPTION_MODE="auto"'):
                    if calls_file.exists():
                        calls_file.unlink()
                    res_unsupported_cap = subprocess.run(
                        ["bash", "-c", f'PR_NUMBER="42"\nREPO="intended/repo"\nRUN_ID="run-1"\nCAPTURED_SHA="{valid_sha}"\nVIDEO_FILE="{dummy_video}"\nPREVIEW_FILE="{dummy_preview}"\nCAPTION_FILE="{dummy_caption}"\n{unsupported_mode}\n' + block1],
                        env=env, capture_output=True, text=True,
                    )
                    self.assertNotEqual(res_unsupported_cap.returncode, 0, f"Unsupported {unsupported_mode} with sidecar must be rejected")
                    self.assertFalse(calls_file.exists(), f"gh must not be called on unsupported {unsupported_mode} with sidecar")

                # Missing RUN_ID fails before calling gh
                res_unset_run_id = subprocess.run(
                    ["bash", "-c", f'PR_NUMBER="42"\nREPO="intended/repo"\nVIDEO_FILE="{dummy_video}"\nPREVIEW_FILE="{dummy_preview}"\nCAPTION_MODE="burned"\n' + block1],
                    env=env, capture_output=True, text=True,
                )
                self.assertNotEqual(res_unset_run_id.returncode, 0)
                self.assertIn("RUN_ID", res_unset_run_id.stderr)
                self.assertFalse(calls_file.exists(), "gh must not be called when RUN_ID is missing")

                # Missing CAPTURED_SHA fails before calling gh
                res_unset_captured_sha = subprocess.run(
                    ["bash", "-c", f'PR_NUMBER="42"\nREPO="intended/repo"\nRUN_ID="run-1"\nVIDEO_FILE="{dummy_video}"\nPREVIEW_FILE="{dummy_preview}"\nCAPTION_MODE="burned"\n' + block1],
                    env=env, capture_output=True, text=True,
                )
                self.assertNotEqual(res_unset_captured_sha.returncode, 0)
                self.assertIn("CAPTURED_SHA", res_unset_captured_sha.stderr)
                self.assertFalse(calls_file.exists(), "gh must not be called when CAPTURED_SHA is missing")

                # Mismatched CAPTURED_SHA fails before release create
                if calls_file.exists():
                    calls_file.unlink()
                res_mismatch_sha = subprocess.run(
                    ["bash", "-c", f'PR_NUMBER="42"\nREPO="intended/repo"\nRUN_ID="run-1"\nCAPTURED_SHA="deadbeef1234567890abcdef0123456789abcdef"\nVIDEO_FILE="{dummy_video}"\nPREVIEW_FILE="{dummy_preview}"\nCAPTION_MODE="burned"\n' + block1],
                    env=env, capture_output=True, text=True,
                )
                self.assertNotEqual(res_mismatch_sha.returncode, 0)
                self.assertIn("CAPTURED_SHA", res_mismatch_sha.stderr)
                logged_mismatch = [json.loads(line)["argv"] for line in calls_file.read_text().splitlines()]
                self.assertEqual(len(logged_mismatch), 1)
                self.assertEqual(logged_mismatch[0][:2], ["pr", "view"])
                self.assertFalse(any(c[:2] == ["release", "create"] for c in logged_mismatch), "Must not create release on SHA mismatch")

                # Format validation failure via ffprobe
                if calls_file.exists():
                    calls_file.unlink()
                env_ffprobe_fail = {**env, "FFPROBE_STUB_MODE": "fail"}
                res_format_fail = subprocess.run(
                    ["bash", "-c", f'PR_NUMBER="42"\nREPO="intended/repo"\nRUN_ID="run-1"\nCAPTURED_SHA="0123456789abcdef0123456789abcdef01234567"\nVIDEO_FILE="{dummy_video}"\nPREVIEW_FILE="{dummy_preview}"\nCAPTION_FILE="{dummy_caption}"\n' + block1],
                    env=env_ffprobe_fail, capture_output=True, text=True,
                )
                self.assertNotEqual(res_format_fail.returncode, 0)
                self.assertFalse(calls_file.exists(), "gh must not be called when media format validation fails")

                # Malformed PR URL / target variants must fail before calling gh (assert ZERO gh calls)
                malformed_targets_b1 = [
                    'PR_NUMBER_OR_URL="https://evil.example/github.com/acme/widgets/pull/42"',
                    'PR_NUMBER_OR_URL="github.com/acme/widgets/pull/42"',
                    'PR_NUMBER_OR_URL="https://github.com/acme/widgets/pull/42/junk"',
                    'PR_NUMBER_OR_URL="https://github.com/acme/widgets/pull/42junk"',
                    'PR_NUMBER_OR_URL="https://github.com/acme/widgets/pull/0"',
                    'PR_NUMBER="42"\nPR_NUMBER_OR_URL="99"\nREPO="intended/repo"',
                    'PR_NUMBER="0"\nREPO="intended/repo"',
                    'PR_NUMBER="42"\nREPO="invalid_no_slash"',
                    'PR_NUMBER="42"\nREPO="too/many/slashes/repo"',
                ]
                for target_env in malformed_targets_b1:
                    if calls_file.exists():
                        calls_file.unlink()
                    res_mal1 = subprocess.run(
                        ["bash", "-c", f'{target_env}\nRUN_ID="run-1"\nCAPTURED_SHA="0123456789abcdef0123456789abcdef01234567"\nVIDEO_FILE="{dummy_video}"\nPREVIEW_FILE="{dummy_preview}"\nCAPTION_FILE="{dummy_caption}"\n' + block1],
                        env=env, capture_output=True, text=True,
                    )
                    self.assertNotEqual(res_mal1.returncode, 0, f"Malformed target must fail in Block 1: {target_env}")
                    self.assertFalse(calls_file.exists(), f"gh must not be called on malformed target in Block 1: {target_env}")

                # 8. Positive test for Block 1 with valid inputs and caption sidecar; verifies clean zip isolation
                if calls_file.exists():
                    calls_file.unlink()
                preexisting_zip = Path(str(dummy_video) + ".zip")
                with zipfile.ZipFile(preexisting_zip, "w") as zf:
                    zf.writestr("unrelated.txt", "unrelated old content\n")

                # Demonstrate old behavior: updating preexisting zip retains unrelated entries
                subprocess.run(["zip", "-j", str(preexisting_zip), str(dummy_video)], check=True, capture_output=True)
                with zipfile.ZipFile(preexisting_zip, "r") as zf:
                    self.assertIn("unrelated.txt", zf.namelist(), "Demonstrating old defect: zip -j retained unrelated old entry")
                    self.assertIn(dummy_video.name, zf.namelist())

                # Reset preexisting_zip with ONLY unrelated entry to test after-fix isolation
                with zipfile.ZipFile(preexisting_zip, "w") as zf:
                    zf.writestr("unrelated.txt", "unrelated old content\n")

                valid_sha = "0123456789abcdef0123456789abcdef01234567"
                res_pos1 = subprocess.run(
                    ["bash", "-c", f'PR_NUMBER="42"\nREPO="intended/repo"\nRUN_ID="run-1"\nCAPTURED_SHA="{valid_sha}"\nVIDEO_FILE="{dummy_video}"\nPREVIEW_FILE="{dummy_preview}"\nCAPTION_FILE="{dummy_caption}"\n' + block1],
                    env=env, capture_output=True, text=True,
                )
                self.assertEqual(res_pos1.returncode, 0, res_pos1.stderr + res_pos1.stdout)
                self.assertTrue(calls_file.exists())
                logged_calls = [json.loads(line)["argv"] for line in calls_file.read_text().splitlines()]
                expected_tag = "evidence-pr-42-0123456789ab-run-1"
                self.assertEqual(len(logged_calls), 4)
                self.assertEqual(logged_calls[0], ["pr", "view", "42", "--repo", "intended/repo", "--json", "number,headRefOid,url"])
                self.assertEqual(logged_calls[1], ["release", "create", expected_tag, "--repo", "intended/repo", "--draft", "--title", "PR #42 Evidence", "--notes", ""])
                mock_releases = calls_file.parent / "mock_releases" / expected_tag
                uploaded_zip = mock_releases / f"{dummy_video.name}.zip"
                self.assertTrue(uploaded_zip.exists())
                with zipfile.ZipFile(uploaded_zip, "r") as zf:
                    uploaded_names = zf.namelist()
                    self.assertNotIn("unrelated.txt", uploaded_names, "Uploaded archive must not retain unrelated preexisting entries")
                    self.assertIn(dummy_video.name, uploaded_names, "Uploaded archive must contain intended video capture")
                with zipfile.ZipFile(preexisting_zip, "r") as zf:
                    self.assertEqual(zf.namelist(), ["unrelated.txt"], "User's preexisting archive must remain untouched")
                self.assertEqual(logged_calls[3], ["release", "view", expected_tag, "--repo", "intended/repo", "--json", "assets,url"])

                # Distinct run IDs produce distinct tags without --clobber
                if calls_file.exists():
                    calls_file.unlink()
                res_run_a = subprocess.run(
                    ["bash", "-c", f'PR_NUMBER="42"\nREPO="intended/repo"\nRUN_ID="run-alpha"\nCAPTURED_SHA="{valid_sha}"\nVIDEO_FILE="{dummy_video}"\nPREVIEW_FILE="{dummy_preview}"\nCAPTION_MODE="burned"\n' + block1],
                    env=env, capture_output=True, text=True,
                )
                self.assertEqual(res_run_a.returncode, 0, res_run_a.stderr + res_run_a.stdout)
                calls_a = [json.loads(line)["argv"] for line in calls_file.read_text().splitlines()]
                tag_a = calls_a[1][2]
                self.assertIn("run-alpha", tag_a)
                self.assertNotIn("--clobber", calls_a[2])

                if calls_file.exists():
                    calls_file.unlink()
                res_run_b = subprocess.run(
                    ["bash", "-c", f'PR_NUMBER="42"\nREPO="intended/repo"\nRUN_ID="run-beta"\nCAPTURED_SHA="{valid_sha}"\nVIDEO_FILE="{dummy_video}"\nPREVIEW_FILE="{dummy_preview}"\nCAPTION_MODE="burned"\n' + block1],
                    env=env, capture_output=True, text=True,
                )
                self.assertEqual(res_run_b.returncode, 0, res_run_b.stderr + res_run_b.stdout)
                calls_b = [json.loads(line)["argv"] for line in calls_file.read_text().splitlines()]
                tag_b = calls_b[1][2]
                self.assertIn("run-beta", tag_b)
                self.assertNotEqual(tag_a, tag_b)
                self.assertNotIn("--clobber", calls_b[2])

                # Positive test with burned caption mode
                if calls_file.exists():
                    calls_file.unlink()
                res_burned1 = subprocess.run(
                    ["bash", "-c", f'PR_NUMBER="42"\nREPO="intended/repo"\nRUN_ID="run-1"\nCAPTURED_SHA="{valid_sha}"\nVIDEO_FILE="{dummy_video}"\nPREVIEW_FILE="{dummy_preview}"\nCAPTION_MODE="burned"\n' + block1],
                    env=env, capture_output=True, text=True,
                )
                self.assertEqual(res_burned1.returncode, 0, res_burned1.stderr + res_burned1.stdout)
                logged_burned1 = [json.loads(line)["argv"] for line in calls_file.read_text().splitlines()]
                self.assertEqual(len(logged_burned1), 4)
                self.assertEqual(logged_burned1[2][:5], ["release", "upload", expected_tag, "--repo", "intended/repo"])
                self.assertIn(dummy_preview, [Path(p) for p in logged_burned1[2][5:]])

                # Positive test with paths with spaces
                if calls_file.exists():
                    calls_file.unlink()
                space_video = test_dir / "space video.mp4"
                space_video.write_bytes(b"space video bytes")
                space_preview = test_dir / "space preview.gif"
                space_preview.write_bytes(b"space preview bytes")
                space_caption = test_dir / "space caption.vtt"
                space_caption.write_text("WEBVTT\n\n00:00.000 --> 00:01.000\nCaption\n")
                res_spaces1 = subprocess.run(
                    ["bash", "-c", f'PR_NUMBER="42"\nREPO="intended/repo"\nRUN_ID="run-1"\nCAPTURED_SHA="{valid_sha}"\nVIDEO_FILE="{space_video}"\nPREVIEW_FILE="{space_preview}"\nCAPTION_FILE="{space_caption}"\n' + block1],
                    env=env, capture_output=True, text=True,
                )
                self.assertEqual(res_spaces1.returncode, 0, res_spaces1.stderr + res_spaces1.stdout)
                space_uploaded_zip = calls_file.parent / "mock_releases" / expected_tag / f"{space_video.name}.zip"
                self.assertTrue(space_uploaded_zip.exists())

                # Valid PR URL with trailing slash in Block 1
                if calls_file.exists():
                    calls_file.unlink()
                res_slash1 = subprocess.run(
                    ["bash", "-c", f'PR_NUMBER_OR_URL="https://github.com/intended/repo/pull/42/"\nRUN_ID="run-1"\nCAPTURED_SHA="{valid_sha}"\nVIDEO_FILE="{dummy_video}"\nPREVIEW_FILE="{dummy_preview}"\nCAPTION_FILE="{dummy_caption}"\n' + block1],
                    env=env, capture_output=True, text=True,
                )
                self.assertEqual(res_slash1.returncode, 0, res_slash1.stderr + res_slash1.stdout)
                self.assertTrue(calls_file.exists())
                logged_slash1 = [json.loads(line)["argv"] for line in calls_file.read_text().splitlines()]
                self.assertEqual(len(logged_slash1), 4)
                self.assertEqual(logged_slash1[0], ["pr", "view", "42", "--repo", "intended/repo", "--json", "number,headRefOid,url"])
                self.assertEqual(logged_slash1[1], ["release", "create", expected_tag, "--repo", "intended/repo", "--draft", "--title", "PR #42 Evidence", "--notes", ""])

                # 9. Wrong CWD test: Block 1 executed from a different repo binds intended repo via --repo
                if calls_file.exists():
                    calls_file.unlink()
                wrong_cwd = test_dir / "wrong_cwd"
                wrong_cwd.mkdir(exist_ok=True)
                git_env = {**env, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}
                subprocess.run(["git", "init"], cwd=wrong_cwd, env=git_env, check=True, capture_output=True)
                subprocess.run(["git", "remote", "add", "origin", "git@github.com:wrong-owner/wrong-repo.git"], cwd=wrong_cwd, env=git_env, check=True, capture_output=True)

                res_wrong_cwd = subprocess.run(
                    ["bash", "-c", f'PR_NUMBER="42"\nREPO="intended/repo"\nRUN_ID="run-1"\nCAPTURED_SHA="{valid_sha}"\nVIDEO_FILE="{dummy_video}"\nPREVIEW_FILE="{dummy_preview}"\nCAPTION_FILE="{dummy_caption}"\n' + block1],
                    cwd=wrong_cwd, env=env, capture_output=True, text=True,
                )
                self.assertEqual(res_wrong_cwd.returncode, 0, res_wrong_cwd.stderr + res_wrong_cwd.stdout)
                self.assertTrue(calls_file.exists())
                calls_wrong = [json.loads(line)["argv"] for line in calls_file.read_text().splitlines()]
                for call in calls_wrong:
                    self.assertIn("--repo", call)
                    self.assertIn("intended/repo", call)
                    self.assertNotIn("wrong-repo", call)

                # Caller survival on Block 1 failure
                res_caller1 = subprocess.run(
                    ["bash", "-c", f'set -e\nstatus=0\nPR_NUMBER=""\n' + block1 + ' || status=$?\nprintf "CALLER1_SURVIVED:%s\\n" "$status"'],
                    env=env, capture_output=True, text=True,
                )
                self.assertEqual(res_caller1.returncode, 0)
                self.assertIn("CALLER1_SURVIVED:1\n", res_caller1.stdout)

                # --- Block 2: PR comment / edit ---
                if calls_file.exists():
                    calls_file.unlink()

                # Unset PR_NUMBER fails in Block 2
                res_unset2 = subprocess.run(
                    ["bash", "-c", "unset PR_NUMBER PR_NUMBER_OR_URL\n" + block2],
                    env=env, capture_output=True, text=True,
                )
                self.assertNotEqual(res_unset2.returncode, 0)
                self.assertFalse(calls_file.exists())

                # Unset REPO fails in Block 2
                res_unset_repo2 = subprocess.run(
                    ["bash", "-c", 'PR_NUMBER="42"\nunset REPO PR_NUMBER_OR_URL\n' + block2],
                    env=env, capture_output=True, text=True,
                )
                self.assertNotEqual(res_unset_repo2.returncode, 0)
                self.assertIn("REPO", res_unset_repo2.stderr)
                self.assertFalse(calls_file.exists())

                # Placeholder REPO fails in Block 2
                res_ph_repo2 = subprocess.run(
                    ["bash", "-c", 'PR_NUMBER="42"\nREPO="<owner/repo>"\n' + block2],
                    env=env, capture_output=True, text=True,
                )
                self.assertNotEqual(res_ph_repo2.returncode, 0)
                self.assertIn("REPO", res_ph_repo2.stderr)
                self.assertFalse(calls_file.exists())

                # Conflicting target repo in Block 2 fails before gh
                res_conflict_repo2 = subprocess.run(
                    ["bash", "-c", 'PR_NUMBER="42"\nREPO="intended/repo"\nPR_NUMBER_OR_URL="https://github.com/conflicting/repo/pull/42"\n' + block2],
                    env=env, capture_output=True, text=True,
                )
                self.assertNotEqual(res_conflict_repo2.returncode, 0)
                self.assertIn("Conflicting", res_conflict_repo2.stderr)
                self.assertFalse(calls_file.exists())

                # Missing or empty body file fails in Block 2 before any gh call
                empty_body = test_dir / "empty_body.md"
                empty_body.write_text("")
                res_empty_body = subprocess.run(
                    ["bash", "-c", f'PR_NUMBER="42"\nREPO="intended/repo"\nBODY_FILE="{empty_body}"\nCOMMENT_FILE="{empty_body}"\n' + block2],
                    env=env, capture_output=True, text=True,
                )
                self.assertNotEqual(res_empty_body.returncode, 0)
                self.assertFalse(calls_file.exists(), "gh must not be called when body/comment file is empty")

                # Malformed PR URL / target variants must fail before calling gh in Block 2 (assert ZERO gh calls)
                valid_body = test_dir / "valid_body.md"
                valid_body.write_text("## Verified Evidence Content\n")
                malformed_targets_b2 = [
                    f'PR_NUMBER_OR_URL="https://evil.example/github.com/acme/widgets/pull/42"\nBODY_FILE="{valid_body}"\nCOMMENT_FILE="{valid_body}"',
                    f'PR_NUMBER_OR_URL="github.com/acme/widgets/pull/42"\nBODY_FILE="{valid_body}"\nCOMMENT_FILE="{valid_body}"',
                    f'PR_NUMBER_OR_URL="https://github.com/acme/widgets/pull/42/junk"\nBODY_FILE="{valid_body}"\nCOMMENT_FILE="{valid_body}"',
                    f'PR_NUMBER_OR_URL="https://github.com/acme/widgets/pull/42junk"\nBODY_FILE="{valid_body}"\nCOMMENT_FILE="{valid_body}"',
                    f'PR_NUMBER_OR_URL="https://github.com/acme/widgets/pull/0"\nBODY_FILE="{valid_body}"\nCOMMENT_FILE="{valid_body}"',
                    f'PR_NUMBER="42"\nPR_NUMBER_OR_URL="99"\nREPO="intended/repo"\nBODY_FILE="{valid_body}"\nCOMMENT_FILE="{valid_body}"',
                    f'PR_NUMBER="0"\nREPO="intended/repo"\nBODY_FILE="{valid_body}"\nCOMMENT_FILE="{valid_body}"',
                    f'PR_NUMBER="42"\nREPO="invalid_no_slash"\nBODY_FILE="{valid_body}"\nCOMMENT_FILE="{valid_body}"',
                    f'PR_NUMBER="42"\nREPO="too/many/slashes/repo"\nBODY_FILE="{valid_body}"\nCOMMENT_FILE="{valid_body}"',
                ]
                for target_env in malformed_targets_b2:
                    if calls_file.exists():
                        calls_file.unlink()
                    res_mal2 = subprocess.run(
                        ["bash", "-c", f'{target_env}\n' + block2],
                        env=env, capture_output=True, text=True,
                    )
                    self.assertNotEqual(res_mal2.returncode, 0, f"Malformed target must fail in Block 2: {target_env}")
                    self.assertFalse(calls_file.exists(), f"gh must not be called on malformed target in Block 2: {target_env}")

                # Block 2: CAPTURED_SHA validation tests across all 3 owners
                # Missing CAPTURED_SHA fails before calling gh
                if calls_file.exists():
                    calls_file.unlink()
                res_unset_cap2 = subprocess.run(
                    ["bash", "-c", f'PR_NUMBER="42"\nREPO="intended/repo"\nCOMMENT_FILE="{valid_body}"\nBODY_FILE="{valid_body}"\n' + block2],
                    env=env, capture_output=True, text=True,
                )
                self.assertNotEqual(res_unset_cap2.returncode, 0)
                self.assertIn("CAPTURED_SHA", res_unset_cap2.stderr)
                self.assertFalse(calls_file.exists(), "gh must not be called when CAPTURED_SHA is missing in Block 2")

                # Empty CAPTURED_SHA fails before calling gh
                if calls_file.exists():
                    calls_file.unlink()
                res_empty_cap2 = subprocess.run(
                    ["bash", "-c", f'PR_NUMBER="42"\nREPO="intended/repo"\nCAPTURED_SHA=""\nCOMMENT_FILE="{valid_body}"\nBODY_FILE="{valid_body}"\n' + block2],
                    env=env, capture_output=True, text=True,
                )
                self.assertNotEqual(res_empty_cap2.returncode, 0)
                self.assertIn("CAPTURED_SHA", res_empty_cap2.stderr)
                self.assertFalse(calls_file.exists(), "gh must not be called when CAPTURED_SHA is empty in Block 2")

                # Placeholder CAPTURED_SHA fails before calling gh
                if calls_file.exists():
                    calls_file.unlink()
                res_ph_cap2 = subprocess.run(
                    ["bash", "-c", f'PR_NUMBER="42"\nREPO="intended/repo"\nCAPTURED_SHA="<sha>"\nCOMMENT_FILE="{valid_body}"\nBODY_FILE="{valid_body}"\n' + block2],
                    env=env, capture_output=True, text=True,
                )
                self.assertNotEqual(res_ph_cap2.returncode, 0)
                self.assertIn("CAPTURED_SHA", res_ph_cap2.stderr)
                self.assertFalse(calls_file.exists(), "gh must not be called when CAPTURED_SHA is placeholder in Block 2")

                # Invalid CAPTURED_SHA (not 40-hex) fails before calling gh
                if calls_file.exists():
                    calls_file.unlink()
                res_inv_cap2 = subprocess.run(
                    ["bash", "-c", f'PR_NUMBER="42"\nREPO="intended/repo"\nCAPTURED_SHA="invalid-sha"\nCOMMENT_FILE="{valid_body}"\nBODY_FILE="{valid_body}"\n' + block2],
                    env=env, capture_output=True, text=True,
                )
                self.assertNotEqual(res_inv_cap2.returncode, 0)
                self.assertIn("CAPTURED_SHA", res_inv_cap2.stderr)
                self.assertFalse(calls_file.exists(), "gh must not be called when CAPTURED_SHA is invalid in Block 2")

                # Newer/mismatched headRefOid: fails before mutation, performs only read-only pr view
                if calls_file.exists():
                    calls_file.unlink()
                env_newer_head = {**env, "GH_STUB_PR_HEAD": "fedcba9876543210fedcba9876543210fedcba98"}
                res_mismatch_head2 = subprocess.run(
                    ["bash", "-c", f'PR_NUMBER="42"\nREPO="intended/repo"\nCAPTURED_SHA="{valid_sha}"\nCOMMENT_FILE="{valid_body}"\nBODY_FILE="{valid_body}"\n' + block2],
                    env=env_newer_head, capture_output=True, text=True,
                )
                self.assertNotEqual(res_mismatch_head2.returncode, 0, "Stale CAPTURED_SHA must be rejected against newer PR head")
                self.assertIn("CAPTURED_SHA", res_mismatch_head2.stderr)
                self.assertTrue(calls_file.exists())
                logged_mismatch2 = [json.loads(line)["argv"] for line in calls_file.read_text().splitlines()]
                self.assertEqual(len(logged_mismatch2), 1, "Mismatched head must only call pr view")
                self.assertEqual(logged_mismatch2[0][:2], ["pr", "view"])

                # Empty headRefOid from pr view fails before mutation
                if calls_file.exists():
                    calls_file.unlink()
                env_empty_head = {**env, "GH_STUB_PR_HEAD": "__EMPTY__"}
                res_empty_head2 = subprocess.run(
                    ["bash", "-c", f'PR_NUMBER="42"\nREPO="intended/repo"\nCAPTURED_SHA="{valid_sha}"\nCOMMENT_FILE="{valid_body}"\nBODY_FILE="{valid_body}"\n' + block2],
                    env=env_empty_head, capture_output=True, text=True,
                )
                self.assertNotEqual(res_empty_head2.returncode, 0, "Empty headRefOid must be rejected")
                logged_empty_head = [json.loads(line)["argv"] for line in calls_file.read_text().splitlines()]
                self.assertEqual(len(logged_empty_head), 1)
                self.assertEqual(logged_empty_head[0][:2], ["pr", "view"])

                # Malformed headRefOid from pr view fails before mutation
                if calls_file.exists():
                    calls_file.unlink()
                env_malformed_head = {**env, "GH_STUB_PR_HEAD": "__MALFORMED__"}
                res_mal_head2 = subprocess.run(
                    ["bash", "-c", f'PR_NUMBER="42"\nREPO="intended/repo"\nCAPTURED_SHA="{valid_sha}"\nCOMMENT_FILE="{valid_body}"\nBODY_FILE="{valid_body}"\n' + block2],
                    env=env_malformed_head, capture_output=True, text=True,
                )
                self.assertNotEqual(res_mal_head2.returncode, 0, "Malformed headRefOid must be rejected")
                logged_mal_head = [json.loads(line)["argv"] for line in calls_file.read_text().splitlines()]
                self.assertEqual(len(logged_mal_head), 1)
                self.assertEqual(logged_mal_head[0][:2], ["pr", "view"])

                # Positive test for Block 2 with non-empty body and matching CAPTURED_SHA
                if calls_file.exists():
                    calls_file.unlink()
                pr_body_sentinel = test_dir / "pr_body_sentinel.txt"
                sentinel_content = "ORIGINAL_PR_DESCRIPTION_DO_NOT_OVERWRITE\n"
                pr_body_sentinel.write_text(sentinel_content)
                env_b2_pos = {**env, "PR_BODY_SENTINEL_FILE": str(pr_body_sentinel), "GH_STUB_DENY_EDIT": "1"}

                res_pos2 = subprocess.run(
                    ["bash", "-c", f'PR_NUMBER="42"\nREPO="intended/repo"\nCAPTURED_SHA="{valid_sha}"\nBODY_FILE="{valid_body}"\nCOMMENT_FILE="{valid_body}"\n' + block2],
                    env=env_b2_pos, capture_output=True, text=True,
                )
                self.assertEqual(res_pos2.returncode, 0, res_pos2.stderr + res_pos2.stdout)
                self.assertTrue(calls_file.exists())
                logged_calls2 = [json.loads(line)["argv"] for line in calls_file.read_text().splitlines()]
                self.assertEqual(len(logged_calls2), 2)
                self.assertEqual(logged_calls2[0], ["pr", "view", "42", "--repo", "intended/repo", "--json", "number,headRefOid,url"])
                self.assertEqual(logged_calls2[1], ["pr", "comment", "42", "--repo", "intended/repo", "--body-file", str(valid_body)])
                self.assertFalse(any(c[:2] == ["pr", "edit"] for c in logged_calls2), "Must never use pr edit in evidence publication")
                self.assertEqual(pr_body_sentinel.read_text(), sentinel_content, "PR body sentinel must remain untouched")

                # Full PR URL derives REPO in Block 2
                if calls_file.exists():
                    calls_file.unlink()
                res_url2 = subprocess.run(
                    ["bash", "-c", f'PR_NUMBER_OR_URL="https://github.com/intended/repo/pull/42"\nCAPTURED_SHA="{valid_sha}"\nBODY_FILE="{valid_body}"\nCOMMENT_FILE="{valid_body}"\n' + block2],
                    env=env_b2_pos, capture_output=True, text=True,
                )
                self.assertEqual(res_url2.returncode, 0, res_url2.stderr + res_url2.stdout)
                logged_url2 = [json.loads(line)["argv"] for line in calls_file.read_text().splitlines()]
                self.assertEqual(len(logged_url2), 2)
                self.assertEqual(logged_url2[0], ["pr", "view", "42", "--repo", "intended/repo", "--json", "number,headRefOid,url"])
                self.assertEqual(logged_url2[1], ["pr", "comment", "42", "--repo", "intended/repo", "--body-file", str(valid_body)])

                # Full PR URL with trailing slash in Block 2
                if calls_file.exists():
                    calls_file.unlink()
                res_url2_slash = subprocess.run(
                    ["bash", "-c", f'PR_NUMBER_OR_URL="https://github.com/intended/repo/pull/42/"\nCAPTURED_SHA="{valid_sha}"\nBODY_FILE="{valid_body}"\nCOMMENT_FILE="{valid_body}"\n' + block2],
                    env=env_b2_pos, capture_output=True, text=True,
                )
                self.assertEqual(res_url2_slash.returncode, 0, res_url2_slash.stderr + res_url2_slash.stdout)
                logged_url2_slash = [json.loads(line)["argv"] for line in calls_file.read_text().splitlines()]
                self.assertEqual(len(logged_url2_slash), 2)
                self.assertEqual(logged_url2_slash[0], ["pr", "view", "42", "--repo", "intended/repo", "--json", "number,headRefOid,url"])
                self.assertEqual(logged_url2_slash[1], ["pr", "comment", "42", "--repo", "intended/repo", "--body-file", str(valid_body)])

                # Wrong-CWD for Block 2
                if calls_file.exists():
                    calls_file.unlink()
                res_wrong_cwd2 = subprocess.run(
                    ["bash", "-c", f'PR_NUMBER="42"\nREPO="intended/repo"\nCAPTURED_SHA="{valid_sha}"\nBODY_FILE="{valid_body}"\nCOMMENT_FILE="{valid_body}"\n' + block2],
                    cwd=wrong_cwd, env=env_b2_pos, capture_output=True, text=True,
                )
                self.assertEqual(res_wrong_cwd2.returncode, 0, res_wrong_cwd2.stderr + res_wrong_cwd2.stdout)
                logged_wrong2 = [json.loads(line)["argv"] for line in calls_file.read_text().splitlines()]
                self.assertEqual(len(logged_wrong2), 2)
                self.assertEqual(logged_wrong2[0], ["pr", "view", "42", "--repo", "intended/repo", "--json", "number,headRefOid,url"])
                self.assertEqual(logged_wrong2[1], ["pr", "comment", "42", "--repo", "intended/repo", "--body-file", str(valid_body)])

                # Caller survival on Block 2 failure
                res_caller2 = subprocess.run(
                    ["bash", "-c", f'set -e\nstatus=0\nPR_NUMBER=""\n' + block2 + ' || status=$?\nprintf "CALLER2_SURVIVED:%s\\n" "$status"'],
                    env=env, capture_output=True, text=True,
                )
                self.assertEqual(res_caller2.returncode, 0)
                self.assertIn("CALLER2_SURVIVED:1\n", res_caller2.stdout)

    def test_video_evidence_publication_repeat_draft_upload_and_failure_guards(self):
        owners = [
            REPO_ROOT / ".claude/skills/tmux-video-evidence/SKILL.md",
            REPO_ROOT / ".claude/skills/evidence-standards/tmux-video-evidence.md",
            REPO_ROOT / ".claude/skills/ui-video-evidence/SKILL.md",
        ]
        for skill_file in owners:
            with self.subTest(owner=skill_file.name):
                content = skill_file.read_text(encoding="utf-8")
                section = content.split("## Evidence access and authorized publication", 1)[1]
                blocks = section.split("```bash\n")
                self.assertGreaterEqual(len(blocks), 3, f"{skill_file.name} must split publication into two bash blocks")
                block1 = blocks[1].split("\n```", 1)[0]
                block2 = blocks[2].split("\n```", 1)[0]

                test_dir = self.tmp_path / f"rep_pub_{skill_file.name}_{skill_file.parent.name}"
                test_dir.mkdir(parents=True, exist_ok=True)
                calls_file = test_dir / "gh-calls.jsonl"
                env = self._create_gh_test_env(test_dir, calls_file)

                dummy_video = test_dir / "video.mp4"
                dummy_video.write_bytes(b"dummy video data")
                dummy_preview = test_dir / "preview.gif"
                dummy_preview.write_bytes(b"dummy gif data")
                dummy_caption = test_dir / "captions.vtt"
                dummy_caption.write_text("WEBVTT\n\n00:00.000 --> 00:01.000\nCaption\n")
                zip_out = test_dir / "archive.zip"
                body_file = test_dir / "body.md"
                body_file.write_text("## Verified Evidence Content\n")

                base_cmd = (
                    f'PR_NUMBER="42"\n'
                    f'REPO="intended/repo"\n'
                    f'RUN_ID="run-1"\n'
                    f'CAPTURED_SHA="0123456789abcdef0123456789abcdef01234567"\n'
                    f'VIDEO_FILE="{dummy_video}"\n'
                    f'PREVIEW_FILE="{dummy_preview}"\n'
                    f'CAPTION_FILE="{dummy_caption}"\n'
                    f'ZIP_FILE="{zip_out}"\n'
                    f'BODY_FILE="{body_file}"\n'
                    f'COMMENT_FILE="{body_file}"\n'
                )
                expected_tag = "evidence-pr-42-0123456789ab-run-1"

                # 1. Repeat draft / existing release fails closed without uploading or retrying ambiguous write
                if calls_file.exists():
                    calls_file.unlink()
                env_repeat = {**env, "GH_STUB_MODE": "repeat_draft"}
                res_repeat = subprocess.run(
                    ["bash", "-c", base_cmd + block1],
                    env=env_repeat, capture_output=True, text=True,
                )
                self.assertNotEqual(res_repeat.returncode, 0, "Failed create must exit non-zero")
                self.assertTrue(calls_file.exists())
                logged_repeat = [json.loads(line) for line in calls_file.read_text().splitlines()]
                argvs_repeat = [c["argv"] if isinstance(c, dict) and "argv" in c else c for c in logged_repeat]
                self.assertEqual(len(argvs_repeat), 2)
                self.assertEqual(argvs_repeat[0], ["pr", "view", "42", "--repo", "intended/repo", "--json", "number,headRefOid,url"])
                self.assertEqual(argvs_repeat[1], ["release", "create", expected_tag, "--repo", "intended/repo", "--draft", "--title", "PR #42 Evidence", "--notes", ""])
                self.assertFalse(any(c[:2] == ["release", "upload"] for c in argvs_repeat), "Must not upload on create failure")
                self.assertFalse(any(c[:2] == ["release", "view"] for c in argvs_repeat[1:]), "Must not run dead release view on create failure")
                self.assertFalse(any("--clobber" in c for c in argvs_repeat), "Must never use --clobber")

                # 2. Conflicting published release: release create fails
                if calls_file.exists():
                    calls_file.unlink()
                env_conflict = {**env, "GH_STUB_MODE": "conflicting_published"}
                res_conflict = subprocess.run(
                    ["bash", "-c", base_cmd + block1],
                    env=env_conflict, capture_output=True, text=True,
                )
                self.assertNotEqual(res_conflict.returncode, 0, "Conflicting published release must fail")
                logged_conflict = [json.loads(line) for line in calls_file.read_text().splitlines()]
                argvs_conflict = [c["argv"] if isinstance(c, dict) and "argv" in c else c for c in logged_conflict]
                self.assertEqual(len(argvs_conflict), 2)
                self.assertEqual(argvs_conflict[0], ["pr", "view", "42", "--repo", "intended/repo", "--json", "number,headRefOid,url"])
                self.assertEqual(argvs_conflict[1], ["release", "create", expected_tag, "--repo", "intended/repo", "--draft", "--title", "PR #42 Evidence", "--notes", ""])
                self.assertFalse(any(c[:2] == ["release", "upload"] for c in argvs_conflict), "Must not upload on published release conflict")

                # 3. View failure
                if calls_file.exists():
                    calls_file.unlink()
                env_fail_view = {**env, "GH_STUB_MODE": "fail_pr_view"}
                res_fail_view = subprocess.run(
                    ["bash", "-c", base_cmd + block1],
                    env=env_fail_view, capture_output=True, text=True,
                )
                self.assertNotEqual(res_fail_view.returncode, 0, "View failure must propagate error")
                logged_fail_view = [json.loads(line) for line in calls_file.read_text().splitlines()]
                argvs_fail_view = [c["argv"] if isinstance(c, dict) and "argv" in c else c for c in logged_fail_view]
                self.assertFalse(any(c[:2] == ["release", "upload"] for c in argvs_fail_view), "Must not upload when view fails")
                self.assertFalse(any(c[:2] == ["release", "create"] for c in argvs_fail_view), "Must not create when view fails")

                # 4. Upload failure
                if calls_file.exists():
                    calls_file.unlink()
                env_fail_upload = {**env, "GH_STUB_MODE": "fail_upload"}
                res_fail_upload = subprocess.run(
                    ["bash", "-c", base_cmd + block1],
                    env=env_fail_upload, capture_output=True, text=True,
                )
                self.assertNotEqual(res_fail_upload.returncode, 0, "Upload failure must propagate error")
                logged_fail_upload = [json.loads(line) for line in calls_file.read_text().splitlines()]
                argvs_fail_upload = [c["argv"] if isinstance(c, dict) and "argv" in c else c for c in logged_fail_upload]
                self.assertFalse(any(c[:3] == ["release", "view", expected_tag] and "--json" in c and "assets,url" in c for c in argvs_fail_upload), "Must not view assets when upload fails")

                # 5. Failures must not trigger downstream comment/body action
                for fail_mode in ("repeat_draft", "conflicting_published", "fail_pr_view", "fail_upload"):
                    if calls_file.exists():
                        calls_file.unlink()
                    env_fail_pipeline = {**env, "GH_STUB_MODE": fail_mode}
                    res_pipe = subprocess.run(
                        ["bash", "-c", f"set -e\n{base_cmd}\n{block1}\n{block2}"],
                        env=env_fail_pipeline, capture_output=True, text=True,
                    )
                    calls_in_fail = [json.loads(line) for line in calls_file.read_text().splitlines()] if calls_file.exists() else []
                    argvs_pipe = [c["argv"] if isinstance(c, dict) and "argv" in c else c for c in calls_in_fail]
                    self.assertNotEqual(res_pipe.returncode, 0, f"Pipeline must fail on {fail_mode}: out={res_pipe.stdout!r}, err={res_pipe.stderr!r}, calls={calls_in_fail!r}")
                    self.assertFalse(any(c[:2] == ["pr", "comment"] or c[:2] == ["pr", "edit"] for c in argvs_pipe), f"PR action must not run on {fail_mode}")

    def test_ffprobe_real_fixtures_validation(self):
        import shutil
        if not shutil.which("ffprobe"):
            self.skipTest("ffprobe not available in PATH")
        with tempfile.TemporaryDirectory() as td:
            vtt = Path(td) / "fixture.vtt"
            vtt.write_text("WEBVTT\n\n00:00.000 --> 00:01.000\nHello\n", encoding="utf-8")
            srt = Path(td) / "fixture.srt"
            srt.write_text("1\n00:00:00,000 --> 00:00:01,000\nHello\n", encoding="utf-8")
            txt = Path(td) / "invalid.txt"
            txt.write_text("not a subtitle", encoding="utf-8")

            cmd = ["ffprobe", "-v", "error", "-show_entries", "stream=codec_type", "-of", "default=noprint_wrappers=1:nokey=1"]
            res_vtt = subprocess.run(cmd + [str(vtt)], capture_output=True, text=True)
            self.assertEqual(res_vtt.returncode, 0)
            self.assertEqual(res_vtt.stdout.strip(), "subtitle")

            res_srt = subprocess.run(cmd + [str(srt)], capture_output=True, text=True)
            self.assertEqual(res_srt.returncode, 0)
            self.assertEqual(res_srt.stdout.strip(), "subtitle")

            res_txt = subprocess.run(cmd + [str(txt)], capture_output=True, text=True)
            self.assertNotEqual(res_txt.stdout.strip(), "subtitle")


if __name__ == "__main__":
    unittest.main()
