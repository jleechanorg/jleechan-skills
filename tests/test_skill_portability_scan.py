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

        def run_check(bundle_dir: Path) -> subprocess.CompletedProcess[str]:
            # Replace placeholder with bundle_dir path
            snippet = raw_snippet.replace("'<bundle_dir>'", f"'{bundle_dir}'").replace('"<bundle_dir>"', f'"{bundle_dir}"')
            return subprocess.run(
                ["bash", "-c", snippet],
                capture_output=True, text=True, timeout=10,
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

                # --- Block 1: Release create / upload / view ---

                # 1. Unset PR_NUMBER must fail informatively before calling gh and exit non-zero
                res_unset = subprocess.run(
                    ["bash", "-c", "unset PR_NUMBER PR_NUMBER_OR_URL\n" + block1],
                    capture_output=True, text=True,
                )
                self.assertNotEqual(res_unset.returncode, 0, f"Unset PR_NUMBER must fail in {skill_file.name}")
                self.assertIn("PR_NUMBER", res_unset.stderr)

                # 2. Placeholder <PR_NUMBER> must fail informatively before calling gh
                res_placeholder = subprocess.run(
                    ["bash", "-c", 'PR_NUMBER="<PR_NUMBER>"\n' + block1],
                    capture_output=True, text=True,
                )
                self.assertNotEqual(res_placeholder.returncode, 0, f"Placeholder PR_NUMBER must fail in {skill_file.name}")
                self.assertIn("PR_NUMBER", res_placeholder.stderr)

                # 3. Missing video or preview file must fail before calling gh (stub gh sees 0 calls)
                test_dir = self.tmp_path / f"pub_test_{skill_file.name}_{skill_file.parent.name}"
                test_dir.mkdir(parents=True, exist_ok=True)
                calls_file = test_dir / "gh-calls.jsonl"
                stub_dir = test_dir / "bin"
                stub_dir.mkdir(exist_ok=True)
                fake_gh = stub_dir / "gh"
                fake_gh.write_text(f"""#!{sys.executable}
import json, sys
with open({repr(str(calls_file))}, "a") as f:
    f.write(json.dumps(sys.argv[1:]) + "\\n")
if "view" in sys.argv:
    print(json.dumps({{"url": "https://github.com/example/repo/releases/tag/v1", "assets": [{{"name": "a", "url": "https://example.com/a"}}]}}))
sys.exit(0)
""")
                fake_gh.chmod(0o755)
                env = {**os.environ, "PATH": f"{stub_dir}:{os.environ['PATH']}"}

                # Video file missing
                res_missing_video = subprocess.run(
                    ["bash", "-c", f'PR_NUMBER="42"\nVIDEO_FILE="{test_dir}/nonexistent.mp4"\n' + block1],
                    env=env, capture_output=True, text=True,
                )
                self.assertNotEqual(res_missing_video.returncode, 0)
                self.assertFalse(calls_file.exists(), "gh must not be called when video file is missing")

                # Missing caption file when specified
                dummy_video = test_dir / "video.mp4"
                dummy_video.write_bytes(b"dummy video data")
                dummy_preview = test_dir / "preview.gif"
                dummy_preview.write_bytes(b"dummy gif data")
                res_missing_caption = subprocess.run(
                    ["bash", "-c", f'PR_NUMBER="42"\nVIDEO_FILE="{dummy_video}"\nPREVIEW_FILE="{dummy_preview}"\nCAPTION_FILE="{test_dir}/missing.vtt"\n' + block1],
                    env=env, capture_output=True, text=True,
                )
                self.assertNotEqual(res_missing_caption.returncode, 0)
                self.assertFalse(calls_file.exists(), "gh must not be called when declared caption file is missing")

                # Positive test for Block 1 with valid inputs and caption sidecar
                dummy_caption = test_dir / "captions.vtt"
                dummy_caption.write_text("WEBVTT\n\n00:00.000 --> 00:01.000\nCaption\n")
                zip_out = test_dir / "archive.zip"
                res_pos1 = subprocess.run(
                    ["bash", "-c", f'PR_NUMBER="42"\nVIDEO_FILE="{dummy_video}"\nPREVIEW_FILE="{dummy_preview}"\nCAPTION_FILE="{dummy_caption}"\nZIP_FILE="{zip_out}"\n' + block1],
                    env=env, capture_output=True, text=True,
                )
                self.assertEqual(res_pos1.returncode, 0, res_pos1.stderr + res_pos1.stdout)
                self.assertTrue(zip_out.exists(), "Zip artifact must be created")
                self.assertTrue(calls_file.exists())
                logged_calls = [json.loads(line) for line in calls_file.read_text().splitlines()]
                self.assertEqual(len(logged_calls), 3)
                self.assertEqual(logged_calls[0], ["release", "create", "evidence-pr-42", "--draft", "--title", "PR #42 Evidence", "--notes", ""])
                self.assertEqual(logged_calls[1], ["release", "upload", "evidence-pr-42", str(zip_out), str(dummy_preview), str(dummy_caption), "--clobber"])
                self.assertEqual(logged_calls[2], ["release", "view", "evidence-pr-42", "--json", "assets,url"])

                # Caller survival on Block 1 failure
                res_caller1 = subprocess.run(
                    ["bash", "-c", f'set -e\nstatus=0\nPR_NUMBER=""\n' + block1 + ' || status=$?\nprintf "CALLER1_SURVIVED:%s\\n" "$status"'],
                    env=env, capture_output=True, text=True,
                )
                self.assertEqual(res_caller1.returncode, 0)
                self.assertIn("CALLER1_SURVIVED:1\n", res_caller1.stdout)

                # --- Block 2: PR comment / edit ---
                calls_file.unlink()

                # Unset PR_NUMBER fails in Block 2
                res_unset2 = subprocess.run(
                    ["bash", "-c", "unset PR_NUMBER PR_NUMBER_OR_URL\n" + block2],
                    env=env, capture_output=True, text=True,
                )
                self.assertNotEqual(res_unset2.returncode, 0)
                self.assertFalse(calls_file.exists())

                # Missing or empty body file fails in Block 2
                empty_body = test_dir / "empty_body.md"
                empty_body.write_text("")
                res_empty_body = subprocess.run(
                    ["bash", "-c", f'PR_NUMBER="42"\nBODY_FILE="{empty_body}"\nCOMMENT_FILE="{empty_body}"\n' + block2],
                    env=env, capture_output=True, text=True,
                )
                self.assertNotEqual(res_empty_body.returncode, 0)
                self.assertFalse(calls_file.exists())

                # Positive test for Block 2 with non-empty body
                valid_body = test_dir / "valid_body.md"
                valid_body.write_text("## Verified Evidence Content\n")
                res_pos2 = subprocess.run(
                    ["bash", "-c", f'PR_NUMBER="42"\nBODY_FILE="{valid_body}"\nCOMMENT_FILE="{valid_body}"\n' + block2],
                    env=env, capture_output=True, text=True,
                )
                self.assertEqual(res_pos2.returncode, 0, res_pos2.stderr + res_pos2.stdout)
                self.assertTrue(calls_file.exists())
                logged_calls2 = [json.loads(line) for line in calls_file.read_text().splitlines()]
                self.assertEqual(len(logged_calls2), 1)
                expected_subcmd = "edit" if "ui-video-evidence" in str(skill_file) else "comment"
                self.assertEqual(logged_calls2[0], ["pr", expected_subcmd, "42", "--body-file", str(valid_body)])

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
                stub_dir = test_dir / "bin"
                stub_dir.mkdir(exist_ok=True)
                fake_gh = stub_dir / "gh"
                fake_gh.write_text(f"""#!{sys.executable}
import json, os, sys
mode = os.environ.get("GH_STUB_MODE", "first_run")
with open({repr(str(calls_file))}, "a") as f:
    f.write(json.dumps({{"mode": mode, "argv": sys.argv[1:]}}) + "\\n")
if len(sys.argv) >= 3 and sys.argv[1:3] == ["release", "create"]:
    if mode == "first_run":
        sys.exit(0)
    elif mode in ("repeat_draft", "conflicting_published", "fail_view"):
        sys.exit(1)
if len(sys.argv) >= 3 and sys.argv[1:3] == ["release", "view"]:
    if mode == "fail_view":
        sys.exit(1)
    if "--jq" in sys.argv:
        jq_idx = sys.argv.index("--jq")
        if sys.argv[jq_idx + 1] == ".isDraft":
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
if len(sys.argv) >= 3 and sys.argv[1:3] == ["release", "upload"]:
    if mode == "fail_upload":
        sys.exit(1)
    sys.exit(0)
if len(sys.argv) >= 3 and sys.argv[1] == "pr":
    sys.exit(0)
sys.exit(0)
""")
                fake_gh.chmod(0o755)
                env = {**os.environ, "PATH": f"{stub_dir}:{os.environ['PATH']}"}

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
                    f'VIDEO_FILE="{dummy_video}"\n'
                    f'PREVIEW_FILE="{dummy_preview}"\n'
                    f'CAPTION_FILE="{dummy_caption}"\n'
                    f'ZIP_FILE="{zip_out}"\n'
                    f'BODY_FILE="{body_file}"\n'
                    f'COMMENT_FILE="{body_file}"\n'
                )

                # 1. Repeat draft upload: release create fails (already exists), but view confirms draft
                if calls_file.exists():
                    calls_file.unlink()
                env_repeat = {**env, "GH_STUB_MODE": "repeat_draft"}
                res_repeat = subprocess.run(
                    ["bash", "-c", base_cmd + block1],
                    env=env_repeat, capture_output=True, text=True,
                )
                self.assertEqual(res_repeat.returncode, 0, res_repeat.stderr + res_repeat.stdout)
                self.assertTrue(calls_file.exists())
                logged_repeat = [json.loads(line) for line in calls_file.read_text().splitlines()]
                argvs_repeat = [c["argv"] if isinstance(c, dict) and "argv" in c else c for c in logged_repeat]
                self.assertEqual(len(argvs_repeat), 4)
                self.assertEqual(argvs_repeat[0], ["release", "create", "evidence-pr-42", "--draft", "--title", "PR #42 Evidence", "--notes", ""])
                self.assertEqual(argvs_repeat[1], ["release", "view", "evidence-pr-42", "--json", "isDraft", "--jq", ".isDraft"])
                self.assertEqual(argvs_repeat[2], ["release", "upload", "evidence-pr-42", str(zip_out), str(dummy_preview), str(dummy_caption), "--clobber"])
                self.assertEqual(argvs_repeat[3], ["release", "view", "evidence-pr-42", "--json", "assets,url"])

                # 2. Conflicting published release: release create fails, view reports isDraft == false
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
                self.assertEqual(argvs_conflict[0][:3], ["release", "create", "evidence-pr-42"])
                self.assertEqual(argvs_conflict[1][:3], ["release", "view", "evidence-pr-42"])
                self.assertFalse(any(c[:2] == ["release", "upload"] for c in argvs_conflict), "Must not upload on published release conflict")

                # 3. View failure after create failure
                if calls_file.exists():
                    calls_file.unlink()
                env_fail_view = {**env, "GH_STUB_MODE": "fail_view"}
                res_fail_view = subprocess.run(
                    ["bash", "-c", base_cmd + block1],
                    env=env_fail_view, capture_output=True, text=True,
                )
                self.assertNotEqual(res_fail_view.returncode, 0, "View failure must propagate error")
                logged_fail_view = [json.loads(line) for line in calls_file.read_text().splitlines()]
                argvs_fail_view = [c["argv"] if isinstance(c, dict) and "argv" in c else c for c in logged_fail_view]
                self.assertFalse(any(c[:2] == ["release", "upload"] for c in argvs_fail_view), "Must not upload when view fails")

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
                self.assertFalse(any(c[:3] == ["release", "view", "evidence-pr-42"] and "--json" in c and "assets,url" in c for c in argvs_fail_upload), "Must not view assets when upload fails")

                # 5. Failures must not trigger downstream comment/body action
                for fail_mode in ("conflicting_published", "fail_view", "fail_upload"):
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
                    self.assertFalse(any(c[:1] == ["pr"] for c in argvs_pipe), f"PR action must not run on {fail_mode}")


if __name__ == "__main__":
    unittest.main()
