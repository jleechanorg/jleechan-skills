"""Executable behavior checks for the PR creation quantity hook."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
HOOK = REPO / ".claude/hooks/protect-pr-create.sh"


def open_pr(number, head="other", base="main"):
    return {"number": number, "headRefName": head, "baseRefName": base}


class ProtectPrCreateHookTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(
            prefix="protect-pr-create-", dir="/tmp"
        )
        self.temp_dir = Path(self.temp.name)
        self.gh_stub_dir = self.temp_dir / "bin"
        self.gh_stub_dir.mkdir()
        self.gh_call_marker = self.temp_dir / "gh-called"
        self.gh_fixture = self.temp_dir / "open-prs.json"
        gh_stub = self.gh_stub_dir / "gh"
        gh_stub.write_text(
            "#!/bin/sh\n"
            "printf '%s\\n' \"$*\" >> \"$GH_CALL_MARKER\"\n"
            "if [ \"$1\" = pr ] && [ \"$2\" = list ]; then\n"
            "  cat \"$GH_STUB_JSON\"\n"
            "  exit 0\n"
            "fi\n"
            "exit 91\n"
        )
        gh_stub.chmod(0o755)
        self.path = os.pathsep.join(
            [str(self.gh_stub_dir), str(Path(sys.executable).parent), os.defpath]
        )

    def tearDown(self):
        self.temp.cleanup()

    def hook_environment(self, open_prs, *, override_env=False, extra_env=None):
        self.gh_fixture.write_text(json.dumps(open_prs), encoding="utf-8")
        environment = dict(os.environ)
        environment.pop("PROTECT_PR_CREATE_MOCK_JSON", None)
        environment.pop("CLAUDE_PROJECT_DIR", None)
        environment["GH_STUB_JSON"] = str(self.gh_fixture)
        environment["BASH_ENV"] = "/dev/null"
        environment["PATH"] = self.path
        environment["GH_CALL_MARKER"] = str(self.gh_call_marker)
        if override_env:
            environment["ALLOW_PR_STACK_OVERRIDE"] = "1"
        else:
            environment.pop("ALLOW_PR_STACK_OVERRIDE", None)
        if extra_env:
            environment.update(extra_env)
        return environment

    def run_hook(
        self,
        command,
        open_prs,
        *,
        override_env=False,
        extra_env=None,
        cwd=None,
    ):
        environment = self.hook_environment(
            open_prs, override_env=override_env, extra_env=extra_env
        )
        working_directory = cwd or REPO
        payload = {
            "tool_name": "Bash",
            "tool_input": {"command": command},
            "cwd": str(working_directory),
        }
        return subprocess.run(
            [str(HOOK)],
            input=json.dumps(payload),
            text=True,
            capture_output=True,
            cwd=working_directory,
            env=environment,
            timeout=5,
            check=False,
        )

    def assert_mocked_github(self):
        if self.gh_call_marker.exists():
            calls = self.gh_call_marker.read_text(encoding="utf-8").splitlines()
            self.assertTrue(calls)
            self.assertTrue(all(call.startswith("pr list ") for call in calls), calls)

    def test_registered_project_hook_invokes_pr_create_guard(self):
        settings = json.loads((REPO / ".claude/settings.json").read_text())
        pre_tool_use = settings.get("hooks", {}).get("PreToolUse", [])
        matches = [entry for entry in pre_tool_use if entry.get("matcher") == "Bash"]
        self.assertEqual(len(matches), 1)
        command = matches[0]["hooks"][0]["command"]

        scenarios = [
            ("plain", "gh pr create --head feature --base parent", 9),
            (
                "command-substitution",
                'url="$(gh pr create --head feature --base parent)"',
                9,
            ),
            (
                "compound-calls",
                "gh pr create --head first --base parent; "
                "gh pr create --head second --base parent",
                8,
            ),
        ]
        for project_dir in (str(REPO), None):
            for name, command_text, count in scenarios:
                with self.subTest(project_dir=project_dir, scenario=name):
                    self.gh_call_marker.unlink(missing_ok=True)
                    payload = {
                        "tool_name": "Bash",
                        "tool_input": {"command": command_text},
                        "cwd": str(REPO),
                    }
                    extra_env = (
                        {"CLAUDE_PROJECT_DIR": project_dir}
                        if project_dir is not None
                        else None
                    )
                    existing = [open_pr(i, base="parent") for i in range(count)]
                    result = subprocess.run(
                        ["bash", "-c", command],
                        input=json.dumps(payload),
                        text=True,
                        capture_output=True,
                        cwd=REPO,
                        env=self.hook_environment(existing, extra_env=extra_env),
                        timeout=5,
                        check=False,
                    )
                    self.assertEqual(result.returncode, 2, result.stderr)
                    self.assertIn("stacked PR ceiling", result.stderr)
                    self.assertIn(
                        "pr list", self.gh_call_marker.read_text(encoding="utf-8")
                    )

    def test_quoted_punctuation_flag_values_do_not_split_pr_invocation(self):
        existing = [open_pr(i, f"split/widget/{i}") for i in range(5)]
        for flag in ("--title", "--body"):
            for value in (";", "&&", "|", "(", ")", ">"):
                with self.subTest(flag=flag, value=value):
                    command = (
                        f'gh pr create {flag} "{value}" '
                        "--head split/widget/new --base main"
                    )
                    result = self.run_hook(command, existing)
                    self.assert_mocked_github()
                    self.assertEqual(result.returncode, 2, result.stderr)
                    self.assertIn("split PR quantity cap", result.stderr)

    def test_legacy_mock_environment_variable_does_not_replace_gh_results(self):
        existing = [open_pr(i, base="parent") for i in range(9)]
        result = self.run_hook(
            "gh pr create --head feature --base parent",
            existing,
            extra_env={"PROTECT_PR_CREATE_MOCK_JSON": "[]"},
        )
        self.assert_mocked_github()
        self.assertEqual(result.returncode, 2)
        self.assertIn("stacked PR ceiling", result.stderr)

    def test_command_substitution_executes_pr_create(self):
        existing = [open_pr(i, base="parent") for i in range(9)]
        result = self.run_hook(
            'url="$(gh pr create --head feature --base parent)"', existing
        )
        self.assert_mocked_github()
        self.assertEqual(result.returncode, 2)
        self.assertIn("stacked PR ceiling", result.stderr)

    def test_single_quoted_command_substitution_text_is_not_executed(self):
        command = "printf '%s\\n' '$(gh pr create --head feature --base parent)'"
        result = self.run_hook(command, [])
        self.assert_mocked_github()
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_unquoted_heredoc_command_substitution_executes_pr_create(self):
        command = """cat <<EOF
$(gh pr create --head feature --base parent)
EOF"""
        result = self.run_hook(command, [open_pr(i, base="parent") for i in range(9)])
        self.assert_mocked_github()
        self.assertEqual(result.returncode, 2)
        self.assertIn("stacked PR ceiling", result.stderr)

    def test_quoted_heredoc_command_substitution_text_is_literal(self):
        command = """cat <<'EOF'
$(gh pr create --head feature --base parent)
EOF"""
        result = self.run_hook(command, [])
        self.assert_mocked_github()
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_child_shell_pr_create_is_checked(self):
        result = self.run_hook(
            "bash -c 'gh pr create --head feature --base parent'",
            [open_pr(i, base="parent") for i in range(9)],
        )
        self.assert_mocked_github()
        self.assertEqual(result.returncode, 2)
        self.assertIn("stacked PR ceiling", result.stderr)

    def test_nested_child_shell_pr_create_is_checked(self):
        command = "bash -c 'sh -c \"gh pr create --head feature --base parent\"'"
        result = self.run_hook(command, [open_pr(i, base="parent") for i in range(9)])
        self.assert_mocked_github()
        self.assertEqual(result.returncode, 2)
        self.assertIn("stacked PR ceiling", result.stderr)

    def test_child_shell_quoted_command_mention_is_not_executed(self):
        command = "bash -c 'printf \"%s\\n\" \"gh pr create --base parent\"'"
        result = self.run_hook(command, [])
        self.assert_mocked_github()
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_compound_stacked_creates_project_the_open_pr_count(self):
        existing = [open_pr(i, base="parent") for i in range(8)]
        command = (
            "gh pr create --head first --base parent; "
            "gh pr create --head second --base parent"
        )
        result = self.run_hook(command, existing)
        self.assert_mocked_github()
        self.assertEqual(result.returncode, 2)
        self.assertIn("stacked PR ceiling", result.stderr)

    def test_compound_split_creates_project_the_open_pr_count(self):
        existing = [open_pr(i, f"split/widget/{i}") for i in range(4)]
        command = (
            "gh pr create --head split/widget/first --base main; "
            "gh pr create --head split/widget/second --base main"
        )
        result = self.run_hook(command, existing)
        self.assert_mocked_github()
        self.assertEqual(result.returncode, 2)
        self.assertIn("split PR quantity cap", result.stderr)

    def test_earlier_overridden_split_create_counts_for_later_create(self):
        existing = [open_pr(i, f"split/widget/{i}") for i in range(4)]
        command = (
            "ALLOW_PR_STACK_OVERRIDE=1 gh pr create --head split/widget/first --base main; "
            "gh pr create --head split/widget/second --base main"
        )
        result = self.run_hook(command, existing)
        self.assert_mocked_github()
        self.assertEqual(result.returncode, 2)
        self.assertIn("split PR quantity cap", result.stderr)

    def test_earlier_overridden_stacked_create_counts_for_later_create(self):
        existing = [open_pr(i, base="parent") for i in range(8)]
        command = (
            "ALLOW_PR_STACK_OVERRIDE=1 gh pr create --head first --base parent; "
            "gh pr create --head second --base parent"
        )
        result = self.run_hook(command, existing)
        self.assert_mocked_github()
        self.assertEqual(result.returncode, 2)
        self.assertIn("stacked PR ceiling", result.stderr)

    def test_later_overridden_split_create_does_not_block_earlier_create(self):
        existing = [open_pr(i, f"split/widget/{i}") for i in range(4)]
        command = (
            "gh pr create --head split/widget/first --base main; "
            "ALLOW_PR_STACK_OVERRIDE=1 gh pr create --head split/widget/second --base main"
        )
        result = self.run_hook(command, existing)
        self.assert_mocked_github()
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_projected_caps_preserve_order_across_supported_shell_contexts(self):
        def invocation(cap, position, override):
            if cap == "split":
                head = f"split/widget/{position}"
                base = "main"
            else:
                head = position
                base = "parent"
            command = f"gh pr create --head {head} --base {base}"
            return f"ALLOW_PR_STACK_OVERRIDE=1 {command}" if override else command

        def in_context(command, context):
            if context == "direct":
                return command
            if context == "child":
                return f"bash -c '{command}'"
            if context == "nested child":
                return f"bash -c 'sh -c \"{command}\"'"
            if context == "substitution":
                return f'url="$({command})"'
            return f"cat <<EOF\n$({command})\nEOF"

        contexts = ("direct", "child", "nested child", "substitution", "heredoc")
        cases = []
        for cap in ("split", "stacked"):
            rows = (
                [open_pr(i, f"split/widget/{i}") for i in range(4)]
                if cap == "split"
                else [open_pr(i, base="parent") for i in range(8)]
            )
            message = (
                "split PR quantity cap" if cap == "split" else "stacked PR ceiling"
            )
            for context in contexts:
                first = in_context(invocation(cap, "first", True), context)
                second = invocation(cap, "second", False)
                cases.append(
                    (
                        f"{cap}: {context} before direct",
                        f"{first}; {second}",
                        rows,
                        message,
                    )
                )
                first = invocation(cap, "first", True)
                second = in_context(invocation(cap, "second", False), context)
                cases.append(
                    (
                        f"{cap}: direct before {context}",
                        f"{first}; {second}",
                        rows,
                        message,
                    )
                )
        for name, command, existing, message in cases:
            with self.subTest(scenario=name):
                result = self.run_hook(command, existing)
                self.assert_mocked_github()
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn(message, result.stderr)

    def test_main_target_does_not_enforce_stack_caps(self):
        result = self.run_hook("gh pr create --head feature --base main", [])
        self.assert_mocked_github()
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_split_below_cap_is_allowed(self):
        existing = [open_pr(i, f"split/widget/{i}") for i in range(4)]
        result = self.run_hook(
            "gh pr create --head split/widget/new --base main", existing
        )
        self.assert_mocked_github()
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_bare_split_feature_does_not_count_other_prefixes(self):
        existing = [open_pr(i, f"split/other/{i}") for i in range(5)]
        result = self.run_hook(
            "gh pr create --head split/auth --base main", existing
        )
        self.assert_mocked_github()
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_split_at_cap_is_blocked(self):
        existing = [open_pr(i, f"split/widget/{i}") for i in range(5)]
        result = self.run_hook(
            "gh pr create --head split/widget/new --base main", existing
        )
        self.assert_mocked_github()
        self.assertEqual(result.returncode, 2)
        self.assertIn("split PR quantity cap", result.stderr)

    def test_stacked_below_cap_is_allowed(self):
        existing = [open_pr(i, base="parent") for i in range(8)]
        result = self.run_hook(
            "gh pr create --head feature --base parent", existing
        )
        self.assert_mocked_github()
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_stacked_at_cap_is_blocked(self):
        existing = [open_pr(i, base="parent") for i in range(9)]
        result = self.run_hook(
            "gh pr create --head feature --base parent", existing
        )
        self.assert_mocked_github()
        self.assertEqual(result.returncode, 2)
        self.assertIn("stacked PR ceiling", result.stderr)

    def test_inline_override_allows_authorized_split(self):
        existing = [open_pr(i, f"split/widget/{i}") for i in range(5)]
        command = (
            "ALLOW_PR_STACK_OVERRIDE=1 "
            "gh pr create --head split/widget/new --base main"
        )
        result = self.run_hook(
            command, existing
        )
        self.assert_mocked_github()
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_env_prefix_allows_authorized_stack(self):
        existing = [open_pr(i, base="parent") for i in range(9)]
        result = self.run_hook(
            "env ALLOW_PR_STACK_OVERRIDE=1 gh pr create --head feature --base parent",
            existing,
        )
        self.assert_mocked_github()
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_environment_override_allows_authorized_stack(self):
        existing = [open_pr(i, base="parent") for i in range(9)]
        result = self.run_hook(
            "gh pr create --head feature --base parent", existing, override_env=True
        )
        self.assert_mocked_github()
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_text_mention_does_not_authorize_override(self):
        existing = [open_pr(i, f"split/widget/{i}") for i in range(5)]
        command = (
            "echo ALLOW_PR_STACK_OVERRIDE=1 && "
            "gh pr create --head split/widget/new --base main"
        )
        result = self.run_hook(
            command, existing
        )
        self.assert_mocked_github()
        self.assertEqual(result.returncode, 2)
        self.assertIn("split PR quantity cap", result.stderr)

    def test_attached_repo_short_option_does_not_hide_pr_create(self):
        existing = [open_pr(i, base="parent") for i in range(9)]
        result = self.run_hook(
            "gh -Rowner/repo pr create --head feature --base parent", existing
        )
        self.assert_mocked_github()
        self.assertEqual(result.returncode, 2)
        self.assertIn("stacked PR ceiling", result.stderr)

    def test_command_prefix_does_not_hide_split_create(self):
        existing = [open_pr(i, f"split/widget/{i}") for i in range(5)]
        result = self.run_hook(
            "command gh pr create --head split/widget/new --base main", existing
        )
        self.assert_mocked_github()
        self.assertEqual(result.returncode, 2)
        self.assertIn("split PR quantity cap", result.stderr)

    def test_command_prefix_does_not_hide_stacked_create(self):
        existing = [open_pr(i, base="parent") for i in range(9)]
        result = self.run_hook(
            "command gh pr create --head feature --base parent", existing
        )
        self.assert_mocked_github()
        self.assertEqual(result.returncode, 2)
        self.assertIn("stacked PR ceiling", result.stderr)

    def test_comment_line_does_not_hide_following_pr_create(self):
        existing = [open_pr(i, base="parent") for i in range(9)]
        command = (
            "echo preparing\n# Create the PR\n"
            "gh pr create --head feature --base parent"
        )
        result = self.run_hook(
            command, existing
        )
        self.assert_mocked_github()
        self.assertEqual(result.returncode, 2)
        self.assertIn("stacked PR ceiling", result.stderr)

    def test_later_main_invocation_does_not_override_stacked_invocation(self):
        existing = [open_pr(i, base="parent") for i in range(9)]
        command = (
            "gh pr create --head feature --base parent; "
            "gh pr create --head feature --base main"
        )
        result = self.run_hook(command, existing)
        self.assert_mocked_github()
        self.assertEqual(result.returncode, 2)
        self.assertIn("stacked PR ceiling", result.stderr)

    def test_override_on_later_invocation_does_not_authorize_prior_request(self):
        existing = [open_pr(i, base="parent") for i in range(9)]
        command = (
            "gh pr create --head feature --base parent; "
            "ALLOW_PR_STACK_OVERRIDE=1 gh pr create --head feature --base parent"
        )
        result = self.run_hook(command, existing)
        self.assert_mocked_github()
        self.assertEqual(result.returncode, 2)
        self.assertIn("stacked PR ceiling", result.stderr)

    def test_configured_merge_base_applies_when_base_is_omitted(self):
        git_repo = self.temp_dir / "configured-base"
        git_repo.mkdir()
        git_environment = dict(os.environ, BASH_ENV="/dev/null", PATH=self.path)
        subprocess.run(
            ["git", "init", "--quiet", "--initial-branch=topic"],
            cwd=git_repo,
            env=git_environment,
            text=True,
            capture_output=True,
            check=True,
            timeout=10,
        )
        subprocess.run(
            ["git", "config", "branch.topic.gh-merge-base", "parent"],
            cwd=git_repo,
            env=git_environment,
            text=True,
            capture_output=True,
            check=True,
            timeout=10,
        )
        existing = [open_pr(i, base="parent") for i in range(9)]
        result = self.run_hook(
            "gh pr create", existing, cwd=git_repo
        )
        self.assert_mocked_github()
        self.assertEqual(result.returncode, 2)
        self.assertIn("stacked PR ceiling", result.stderr)

    def test_quoted_hash_does_not_start_comment(self):
        result = self.run_hook('echo "# still a string"', [])
        self.assert_mocked_github()
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
