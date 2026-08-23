#!/usr/bin/env python3
"""
Matrix-style tests for /exportcommands functionality.
Tests the complete export workflow with comprehensive coverage.
"""

import os
import re
import sys
import tempfile
import shutil
import unittest
from unittest.mock import Mock, patch

# Add the parent directory ('.claude/commands') to path for importing
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Import using importlib to avoid try/except pattern
import importlib.util

spec = importlib.util.find_spec("exportcommands")
if spec is not None:
    from exportcommands import ClaudeCommandsExporter
else:
    ClaudeCommandsExporter = None


class TestExportCommandsMatrix(unittest.TestCase):
    """
    Matrix-style tests covering all export dimensions:
    - Export Types: [Commands, Hooks, Scripts, Orchestration]
    - Content States: [Empty, Normal, Large]
    - Filtering: [With/Without project-specific content]
    - GitHub Operations: [Success, Failure, No Token]
    - Directory Exclusions: [Applied, Not Applied]
    """

    def setUp(self):
        """Set up test environment with temporary directories."""
        self.temp_dir = tempfile.mkdtemp(prefix="test_export_")
        self.project_root = os.path.join(self.temp_dir, "test_project")
        self.export_dir = os.path.join(self.temp_dir, "export")
        self.repo_dir = os.path.join(self.temp_dir, "repo")

        # Create test project structure
        os.makedirs(self.project_root)
        os.makedirs(os.path.join(self.project_root, ".claude", "commands"))
        os.makedirs(os.path.join(self.project_root, ".claude", "hooks"))
        os.makedirs(os.path.join(self.project_root, "orchestration"))
        os.makedirs(self.repo_dir)

        # Create test files with project-specific content
        self._create_test_files()

        # Mock git operations
        self.git_patcher = patch("subprocess.run")
        self.mock_subprocess = self.git_patcher.start()
        self.mock_subprocess.return_value.returncode = 0
        self.mock_subprocess.return_value.stdout = self.project_root

        # Setup exporter if available
        if ClaudeCommandsExporter:
            with patch.object(
                ClaudeCommandsExporter,
                "_get_project_root",
                return_value=self.project_root,
            ):
                self.exporter = ClaudeCommandsExporter()
                self.exporter.export_dir = self.export_dir
                self.exporter.repo_dir = self.repo_dir

    def tearDown(self):
        """Clean up test environment."""
        self.git_patcher.stop()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _create_test_files(self):
        """Create test files with various content types including skip list files."""
        # Test command with project-specific content
        with open(
            os.path.join(self.project_root, ".claude", "commands", "test_command.md"),
            "w",
        ) as f:
            f.write("""# Test Command

This command uses $PROJECT_ROOT/ paths and references $USER.
Also mentions your-project.com and TESTING=true python.
""")

        # Create files that should be skipped according to COMMANDS_SKIP_LIST
        skip_files = [
            "conv.md",
            "orchconverge.md",
            "converge.md",
            "orchc.md",
            "testi.sh",
            "run_tests.sh",
        ]
        for skip_file in skip_files:
            with open(
                os.path.join(self.project_root, ".claude", "commands", skip_file), "w"
            ) as f:
                f.write(f"""# {skip_file} - Should be skipped
This file should be excluded from exports per COMMANDS_SKIP_LIST.
Contains orchestration/testing content specific to original project.
""")

        # Test hook with project-specific content
        hook_content = """#!/bin/bash
# Test hook
export PROJECT_PATH="$PROJECT_ROOT/"
export OWNER="$USER"
export DOMAIN="your-project.com"
TESTING=true python test.py
"""
        os.makedirs(os.path.join(self.project_root, ".claude", "hooks"), exist_ok=True)
        with open(
            os.path.join(self.project_root, ".claude", "hooks", "test_hook.sh"), "w"
        ) as f:
            f.write(hook_content)
        os.chmod(
            os.path.join(self.project_root, ".claude", "hooks", "test_hook.sh"), 0o755
        )

        # Test infrastructure script
        with open(os.path.join(self.project_root, "claude_start.sh"), "w") as f:
            f.write("""#!/bin/bash
# Claude startup script
export DOMAIN="your-project.com"
export USER="$USER"
""")

        # Test orchestration files with excluded directories
        for excluded_dir in [
            "analysis",
            "claude-bot-commands",
            "coding_prompts",
            "prototype",
        ]:
            os.makedirs(
                os.path.join(self.project_root, "orchestration", excluded_dir),
                exist_ok=True,
            )
            with open(
                os.path.join(
                    self.project_root, "orchestration", excluded_dir, "test.py"
                ),
                "w",
            ) as f:
                f.write(f"# {excluded_dir} test file - should be excluded")

        # Test orchestration core files (should be included)
        with open(
            os.path.join(self.project_root, "orchestration", "core.py"), "w"
        ) as f:
            f.write("# Core orchestration - should be included")

    @unittest.skipIf(
        ClaudeCommandsExporter is None, "ClaudeCommandsExporter not available"
    )
    def test_commands_export_matrix(self):
        """Test command export across different content states."""
        test_cases = [
            {"state": "empty", "file_count": 0, "expect_warning": True},
            {"state": "normal", "file_count": 1, "expect_warning": False},
            {"state": "large", "file_count": 50, "expect_warning": False},
        ]

        for case in test_cases:
            with self.subTest(case=case):
                # Setup test state
                commands_dir = os.path.join(self.project_root, ".claude", "commands")
                # Clear directory (including the pre-created test_command.md)
                for f in os.listdir(commands_dir):
                    os.remove(os.path.join(commands_dir, f))

                # Reset counter
                self.exporter.commands_count = 0

                # Create test files based on state
                if case["state"] != "empty":
                    for i in range(case["file_count"]):
                        with open(os.path.join(commands_dir, f"cmd_{i}.md"), "w") as f:
                            f.write(f"# Command {i}\nContent with $PROJECT_ROOT/ references")

                # Create staging directory
                staging_dir = os.path.join(self.export_dir, "staging")
                os.makedirs(staging_dir, exist_ok=True)

                # Test export
                self.exporter._export_commands(staging_dir)

                # Validate results
                target_dir = os.path.join(staging_dir, "commands")
                if case["expect_warning"]:
                    # Should handle empty directory gracefully
                    self.assertEqual(self.exporter.commands_count, 0)
                else:
                    # Should export files and apply filtering
                    self.assertEqual(self.exporter.commands_count, case["file_count"])

                    # Check content filtering
                    if case["file_count"] > 0:
                        test_file = os.path.join(target_dir, "cmd_0.md")
                        if os.path.exists(test_file):
                            with open(test_file, "r") as f:
                                content = f.read()
                                # Project-specific content should be filtered
                                self.assertNotIn("$PROJECT_ROOT/", content)
                                self.assertIn("$PROJECT_ROOT/", content)

    @unittest.skipIf(
        ClaudeCommandsExporter is None, "ClaudeCommandsExporter not available"
    )
    def test_commands_skip_list_functionality(self):
        """Test that COMMANDS_SKIP_LIST properly excludes specified files."""
        # Create staging directory
        staging_dir = os.path.join(self.export_dir, "staging")
        os.makedirs(staging_dir, exist_ok=True)

        # Reset counter
        self.exporter.commands_count = 0

        # Get initial count (should include test_command.md but exclude skip list files)
        commands_dir = os.path.join(self.project_root, ".claude", "commands")
        total_files = len(
            [f for f in os.listdir(commands_dir) if f.endswith((".md", ".py", ".sh"))]
        )
        skip_files = [
            "conv.md",
            "orchconverge.md",
            "converge.md",
            "orchc.md",
            "testi.sh",
            "run_tests.sh",
        ]
        expected_count = total_files - len(skip_files)

        # Test export
        self.exporter._export_commands(staging_dir)

        # Validate skip list worked correctly
        self.assertEqual(self.exporter.commands_count, expected_count)

        # Check that skip list files were not exported
        target_commands_dir = os.path.join(staging_dir, "commands")
        exported_files = (
            os.listdir(target_commands_dir)
            if os.path.exists(target_commands_dir)
            else []
        )

        for skip_file in skip_files:
            self.assertNotIn(
                skip_file,
                exported_files,
                f"Skip list file {skip_file} should not be exported",
            )

        # Check that regular files were exported
        self.assertIn(
            "test_command.md",
            exported_files,
            "Regular command files should be exported",
        )

    @unittest.skipIf(
        ClaudeCommandsExporter is None, "ClaudeCommandsExporter not available"
    )
    def test_dynamic_placeholder_replacement(self):
        """Test the new dynamic placeholder replacement functionality."""
        # Test various placeholder patterns
        test_content = """
        This export contains **144 commands** that transform Claude Code.
        Also mentions **118 commands** in another section.
        Export statistics show **145 Commands** total.
        And **22 Hooks** with **5 Scripts** available.
        """

        # Set test counts
        self.exporter.commands_count = 100
        self.exporter.hooks_count = 15
        self.exporter.scripts_count = 8

        # Apply dynamic replacement
        result = self.exporter._replace_dynamic_placeholders(test_content)

        # Verify replacements
        self.assertIn("**100 commands**", result)
        self.assertNotIn("**144 commands**", result)
        self.assertNotIn("**118 commands**", result)
        self.assertIn("**100 Commands**", result)
        self.assertIn("**15 Hooks**", result)
        self.assertIn("**8 Scripts**", result)

    @unittest.skipIf(
        ClaudeCommandsExporter is None, "ClaudeCommandsExporter not available"
    )
    def test_copy_directory_with_filtering(self):
        """Test the fixed _copy_directory_with_filtering method uses centralized skip list."""
        # Create source directory with mixed files
        source_dir = os.path.join(self.temp_dir, "source")
        os.makedirs(source_dir, exist_ok=True)

        # Create files including some from skip list
        all_files = [
            "test_command.md",
            "conv.md",
            "orchconverge.md",
            "normal_file.py",
            "testi.sh",
        ]
        for file_name in all_files:
            with open(os.path.join(source_dir, file_name), "w") as f:
                f.write(f"Content of {file_name}")

        # Create target directory
        target_dir = os.path.join(self.temp_dir, "target")
        os.makedirs(target_dir, exist_ok=True)

        # Test the copy with filtering
        self.exporter._copy_directory_with_filtering(source_dir, target_dir)

        # Check results
        copied_files = os.listdir(target_dir)

        # Should include normal files
        self.assertIn("test_command.md", copied_files)
        self.assertIn("normal_file.py", copied_files)

        # Should exclude skip list files
        self.assertNotIn("conv.md", copied_files)
        self.assertNotIn("orchconverge.md", copied_files)
        self.assertNotIn("testi.sh", copied_files)

    @unittest.skipIf(
        ClaudeCommandsExporter is None, "ClaudeCommandsExporter not available"
    )
    def test_hooks_export_matrix(self):
        """Test hook export with different file types and permissions."""
        test_cases = [
            {"type": "shell", "ext": ".sh", "expect_executable": True},
            {"type": "python", "ext": ".py", "expect_executable": True},
            {"type": "markdown", "ext": ".md", "expect_executable": False},
        ]

        for case in test_cases:
            with self.subTest(case=case):
                # Create test hook
                hooks_dir = os.path.join(self.project_root, ".claude", "hooks")
                test_hook = os.path.join(hooks_dir, f"test_hook{case['ext']}")

                with open(test_hook, "w") as f:
                    if case["type"] == "shell":
                        f.write("#!/bin/bash\necho 'test with $PROJECT_ROOT/ path'")
                    elif case["type"] == "python":
                        f.write("#!/usr/bin/env python3\nprint('test with $USER')")
                    else:
                        f.write("# Test markdown\nContent with your-project.com")

                if case["expect_executable"]:
                    os.chmod(test_hook, 0o755)

                # Create staging directory and test export
                staging_dir = os.path.join(self.export_dir, "staging")
                os.makedirs(staging_dir, exist_ok=True)

                # Mock rsync for hooks export
                with patch("subprocess.run") as mock_rsync:
                    mock_rsync.return_value.returncode = 0
                    self.exporter._export_hooks(staging_dir)

                    # Should call rsync with correct parameters
                    mock_rsync.assert_called()
                    args = mock_rsync.call_args[0][0]
                    self.assertIn("rsync", args[0])
                    self.assertIn("-av", args)

    @unittest.skipIf(
        ClaudeCommandsExporter is None, "ClaudeCommandsExporter not available"
    )
    def test_content_filtering_matrix(self):
        """Test content filtering across different transformation patterns."""
        test_cases = [
            {"input": "$PROJECT_ROOT/test.py", "expected": "$PROJECT_ROOT/test.py"},
            {"input": "your-project.com", "expected": "your-project.com"},
            {"input": "$USER", "expected": "$USER"},
            {"input": "TESTING=true python", "expected": "TESTING=true python"},
            {"input": "Your Project", "expected": "Your Project"},
        ]

        for case in test_cases:
            with self.subTest(case=case):
                # Create test file with content to filter
                test_file = os.path.join(self.temp_dir, "test_content.txt")
                with open(test_file, "w") as f:
                    f.write(case["input"])

                # Apply filtering
                self.exporter._apply_content_filtering(test_file)

                # Check result
                with open(test_file, "r") as f:
                    result = f.read()
                    self.assertEqual(result, case["expected"])

    @unittest.skipIf(
        ClaudeCommandsExporter is None, "ClaudeCommandsExporter not available"
    )
    def test_content_filtering_only_skips_tests_directory_python_files(self):
        tests_dir = os.path.join(self.temp_dir, "nested", "tests")
        os.makedirs(tests_dir, exist_ok=True)

        repo_root_test = os.path.join(self.temp_dir, "test_mobile_campaigns.py")
        tests_dir_test = os.path.join(tests_dir, "test_literal_paths.py")
        literal_content = "your-project.com\njleechan\n"

        with open(repo_root_test, "w", encoding="utf-8") as f:
            f.write(literal_content)
        with open(tests_dir_test, "w", encoding="utf-8") as f:
            f.write(literal_content)

        self.exporter._apply_content_filtering(repo_root_test)
        self.exporter._apply_content_filtering(tests_dir_test)

        with open(repo_root_test, encoding="utf-8") as f:
            self.assertEqual(f.read(), "your-project.com\n$USER\n")
        with open(tests_dir_test, encoding="utf-8") as f:
            self.assertEqual(f.read(), literal_content)

    @unittest.skipIf(
        ClaudeCommandsExporter is None, "ClaudeCommandsExporter not available"
    )
    def test_directory_exclusions_matrix(self):
        """Test directory exclusion patterns."""
        excluded_dirs = [
            "analysis",
            "claude-bot-commands",
            "coding_prompts",
            "prototype",
        ]

        for excluded_dir in excluded_dirs:
            with self.subTest(directory=excluded_dir):
                # Create staging directory
                staging_dir = os.path.join(self.export_dir, "staging")
                os.makedirs(staging_dir, exist_ok=True)

                # Mock rsync to capture exclusion patterns
                with patch("subprocess.run") as mock_rsync:
                    mock_rsync.return_value.returncode = 0
                    self.exporter._export_orchestration(staging_dir)

                    if mock_rsync.called:
                        args = mock_rsync.call_args[0][0]
                        exclusion_found = any(
                            f"--exclude={excluded_dir}/" in arg for arg in args
                        )
                        self.assertTrue(
                            exclusion_found, f"Should exclude {excluded_dir}/"
                        )

    @unittest.skipIf(
        ClaudeCommandsExporter is None, "ClaudeCommandsExporter not available"
    )
    def test_readme_generation_matrix(self):
        """Test README generation with different count combinations."""
        test_cases = [
            {"commands": 0, "hooks": 0, "scripts": 0},
            {"commands": 5, "hooks": 3, "scripts": 2},
            {"commands": 85, "hooks": 8, "scripts": 7},
        ]

        for case in test_cases:
            with self.subTest(case=case):
                # Set test counts
                self.exporter.commands_count = case["commands"]
                self.exporter.hooks_count = case["hooks"]
                self.exporter.scripts_count = case["scripts"]

                # Generate README
                self.exporter._generate_readme()

                # Check generated content
                readme_path = os.path.join(self.export_dir, "README.md")
                self.assertTrue(os.path.exists(readme_path))

                with open(readme_path, "r") as f:
                    content = f.read()

                    # Should contain dynamic counts
                    self.assertIn(f"**{case['commands']} commands**", content)
                    self.assertIn(f"**{case['hooks']} hooks**", content)

                    # Should contain proper structure - check for installation content
                    self.assertTrue(
                        "Installation" in content
                        or "install" in content.lower()
                        or "MANUAL INSTALLATION" in content
                    )
                    self.assertIn("REFERENCE EXPORT", content)

    @unittest.skipIf(
        ClaudeCommandsExporter is None, "ClaudeCommandsExporter not available"
    )
    def test_export_workflow_without_install_script(self):
        """Test export workflow without deprecated install script generation."""
        # Test that export works without install script
        self.exporter.phase1_local_export()

        # Verify export structure created successfully
        staging_dir = os.path.join(self.export_dir, "staging")
        self.assertTrue(os.path.exists(staging_dir))

        # Check that README was generated (fallback mode)
        readme_path = os.path.join(self.export_dir, "README.md")
        self.assertTrue(os.path.exists(readme_path))

        with open(readme_path, "r") as f:
            content = f.read()
            # Should contain export contents information
            self.assertIn("Export Contents", content)
            # Should use manual installation instead of install script
            self.assertIn("MANUAL INSTALLATION", content)
            self.assertNotIn("install.sh", content)

    @unittest.skipIf(
        ClaudeCommandsExporter is None, "ClaudeCommandsExporter not available"
    )
    def test_github_operations_matrix(self):
        """Test GitHub operations with different scenarios."""
        test_cases = [
            {"token_present": True, "expect_success": True},
            {"token_present": False, "expect_success": False},
        ]

        for case in test_cases:
            with self.subTest(case=case):
                # Setup GitHub token
                if case["token_present"]:
                    self.exporter.github_token = "test_token"
                else:
                    self.exporter.github_token = None

                # Mock GitHub API calls
                with patch("requests.post") as mock_post:
                    mock_post.return_value.status_code = 201
                    mock_post.return_value.json.return_value = {
                        "html_url": "https://github.com/test/pr/1"
                    }

                    if not case["expect_success"]:
                        with self.assertRaises(Exception):
                            self.exporter.phase2_github_publish()
                    else:
                        # Should succeed with proper token
                        # _create_pull_request uses gh CLI; mock subprocess.run to return PR URL
                        self.mock_subprocess.return_value.stdout = (
                            "https://github.com/test/pr/1\n"
                        )
                        self.mock_subprocess.return_value.returncode = 0
                        with (
                            patch.object(self.exporter, "_clone_repository"),
                            patch.object(self.exporter, "_create_export_branch"),
                            patch.object(self.exporter, "_copy_to_repository"),
                            patch.object(self.exporter, "_verify_exclusions"),
                            patch.object(self.exporter, "_commit_and_push"),
                            patch.object(
                                self.exporter,
                                "_create_pull_request",
                                return_value="https://github.com/test/pr/1",
                            ),
                        ):
                            result = self.exporter.phase2_github_publish()
                            self.assertIn("github.com", result)

    def test_error_handling_matrix(self):
        """Test error handling across different failure scenarios."""
        if ClaudeCommandsExporter is None:
            self.skipTest("ClaudeCommandsExporter not available")

        test_cases = [
            {"scenario": "missing_commands_dir", "expect_warning": True},
            {"scenario": "missing_hooks_dir", "expect_warning": True},
            {"scenario": "missing_orchestration_dir", "expect_skip": True},
        ]

        for case in test_cases:
            with self.subTest(scenario=case["scenario"]):
                # Remove directory to trigger error handling
                if case["scenario"] == "missing_commands_dir":
                    shutil.rmtree(
                        os.path.join(self.project_root, ".claude", "commands")
                    )
                elif case["scenario"] == "missing_hooks_dir":
                    shutil.rmtree(os.path.join(self.project_root, ".claude", "hooks"))
                elif case["scenario"] == "missing_orchestration_dir":
                    shutil.rmtree(os.path.join(self.project_root, "orchestration"))

                # Create staging directory
                staging_dir = os.path.join(self.export_dir, "staging")
                os.makedirs(staging_dir, exist_ok=True)

                # Test graceful handling
                try:
                    if case["scenario"] == "missing_commands_dir":
                        self.exporter._export_commands(staging_dir)
                        self.assertEqual(self.exporter.commands_count, 0)
                    elif case["scenario"] == "missing_hooks_dir":
                        self.exporter._export_hooks(staging_dir)
                        self.assertEqual(self.exporter.hooks_count, 0)
                    elif case["scenario"] == "missing_orchestration_dir":
                        self.exporter._export_orchestration(staging_dir)
                        # Should not raise exception

                except Exception as e:
                    self.fail(f"Should handle missing directory gracefully: {e}")


class TestExportCommandsIntegration(unittest.TestCase):
    """Integration tests for end-to-end export workflow."""

    def setUp(self):
        """Set up integration test environment."""
        if ClaudeCommandsExporter is None:
            self.skipTest("ClaudeCommandsExporter not available")

        self.temp_dir = tempfile.mkdtemp(prefix="test_export_integration_")
        self.project_root = os.path.join(self.temp_dir, "test_project")

        # Create realistic project structure
        self._create_realistic_project()

    def tearDown(self):
        """Clean up integration test environment."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _create_realistic_project(self):
        """Create a realistic project structure for testing."""
        # Create directory structure
        dirs = [
            ".claude/commands",
            ".claude/hooks",
            "orchestration/core",
            "orchestration/automation",  # Now included (no longer excluded)
            "orchestration/analysis",  # Should be excluded
        ]

        for dir_path in dirs:
            os.makedirs(os.path.join(self.project_root, dir_path), exist_ok=True)

        # Create test commands
        commands = [
            "execute.md",
            "pr.md",
            "copilot.md",
            "testproject.sh",
        ]  # testproject.sh should be excluded
        for cmd in commands:
            with open(
                os.path.join(self.project_root, ".claude/commands", cmd), "w"
            ) as f:
                f.write(f"""# {cmd}
Test command with $PROJECT_ROOT/ references
User: $USER
Domain: your-project.com
TESTING=true python test.py
""")

        # Create test hooks
        hooks = ["post_commit_sync.sh", "anti_demo_check.py"]
        for hook in hooks:
            hook_path = os.path.join(self.project_root, ".claude/hooks", hook)
            with open(hook_path, "w") as f:
                if hook.endswith(".sh"):
                    f.write(f"""#!/bin/bash
# {hook} - Essential Claude Code hook
export PROJECT_ROOT="$PROJECT_ROOT/"
export USER="$USER"
""")
                else:
                    f.write(f"""#!/usr/bin/env python3
# {hook} - Essential Claude Code hook
PROJECT_ROOT = "$PROJECT_ROOT/"
USER = "$USER"
""")
            os.chmod(hook_path, 0o755)

        # Create infrastructure scripts
        scripts = ["claude_start.sh", "claude_mcp.sh"]
        for script in scripts:
            with open(os.path.join(self.project_root, script), "w") as f:
                f.write(f"""#!/bin/bash
# {script} infrastructure
export DOMAIN="your-project.com"
""")

        # Create orchestration files (some to exclude, some to keep)
        with open(
            os.path.join(self.project_root, "orchestration/core/main.py"), "w"
        ) as f:
            f.write("# Core orchestration - should be included")

        with open(
            os.path.join(self.project_root, "orchestration/analysis/report.py"), "w"
        ) as f:
            f.write("# Analysis - should be excluded")

    @patch.dict(os.environ, {"GITHUB_TOKEN": "test_token"})
    @patch("subprocess.run")
    def test_full_export_workflow(self, mock_subprocess):
        """Test the complete export workflow end-to-end."""
        # Mock git operations
        mock_subprocess.return_value.returncode = 0
        mock_subprocess.return_value.stdout = self.project_root

        # Create exporter
        with patch.object(
            ClaudeCommandsExporter, "_get_project_root", return_value=self.project_root
        ):
            exporter = ClaudeCommandsExporter()

        # Create a mock rsync that actually creates files
        def mock_rsync_side_effect(*args, **kwargs):
            if "rsync" in args[0] and args[0][0] == "rsync":
                # This is a hooks export rsync call
                target_dir = args[0][-1].rstrip("/")  # Last argument is target
                if "hooks" in target_dir:
                    # Create mock hook files for testing
                    os.makedirs(target_dir, exist_ok=True)
                    for hook in ["post_commit_sync.sh", "anti_demo_check.py"]:
                        hook_path = os.path.join(target_dir, hook)
                        with open(hook_path, "w") as f:
                            f.write(f"# Test hook: {hook}")
                        if hook.endswith(".sh"):
                            os.chmod(hook_path, 0o755)

            mock_result = Mock()
            mock_result.returncode = 0
            mock_result.stdout = ""
            mock_result.stderr = ""
            return mock_result

        # Mock GitHub operations and subprocess for hooks
        with (
            patch.object(
                exporter,
                "phase2_github_publish",
                return_value="https://github.com/test/pr/1",
            ) as mock_github,
            patch(
                "subprocess.run", side_effect=mock_rsync_side_effect
            ) as mock_subprocess,
        ):
            # Run phase 1 (local export)
            exporter.phase1_local_export()

            # Verify local export results
            self.assertTrue(
                os.path.exists(os.path.join(exporter.export_dir, "staging"))
            )
            self.assertTrue(
                os.path.exists(os.path.join(exporter.export_dir, "README.md"))
            )

            # Verify install script is not generated (deprecated functionality)
            self.assertFalse(
                os.path.exists(os.path.join(exporter.export_dir, "install.sh"))
            )

            # Check counts are reasonable
            self.assertGreater(exporter.commands_count, 0)
            self.assertGreater(exporter.hooks_count, 0)

            # Verify content filtering
            commands_dir = os.path.join(exporter.export_dir, "staging", "commands")
            if os.path.exists(commands_dir):
                for cmd_file in os.listdir(commands_dir):
                    if cmd_file.endswith(".md"):
                        with open(os.path.join(commands_dir, cmd_file), "r") as f:
                            content = f.read()
                            # Project-specific content should be filtered
                            self.assertNotIn("$PROJECT_ROOT/", content)
                            self.assertNotIn("$USER", content)
                            self.assertNotIn("your-project.com", content)
                            # Should contain generic replacements
                            self.assertIn("$PROJECT_ROOT/", content)
                            self.assertIn("$USER", content)

            # Test GitHub phase would be called
            mock_github.return_value = "https://github.com/test/pr/1"


class TestGenericDirectoryExport(unittest.TestCase):
    """TDD tests for generic directory export refactor."""

    def setUp(self):
        """Set up test environment for generic export tests."""
        if ClaudeCommandsExporter is None:
            self.skipTest("ClaudeCommandsExporter not available")

        self.temp_dir = tempfile.mkdtemp(prefix="test_generic_export_")
        self.project_root = os.path.join(self.temp_dir, "test_project")
        self.export_dir = os.path.join(self.temp_dir, "export")

        os.makedirs(self.project_root)

        # Mock git operations
        self.git_patcher = patch("subprocess.run")
        self.mock_subprocess = self.git_patcher.start()
        self.mock_subprocess.return_value.returncode = 0
        self.mock_subprocess.return_value.stdout = self.project_root

        # Setup exporter
        with patch.object(
            ClaudeCommandsExporter, "_get_project_root", return_value=self.project_root
        ):
            self.exporter = ClaudeCommandsExporter()
            self.exporter.export_dir = self.export_dir

    def tearDown(self):
        """Clean up test environment."""
        self.git_patcher.stop()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @unittest.skipIf(
        ClaudeCommandsExporter is None, "ClaudeCommandsExporter not available"
    )
    def test_export_directory_config_exists(self):
        """Test that EXPORT_DIRECTORIES configuration exists."""
        self.assertTrue(hasattr(self.exporter, "EXPORT_DIRECTORIES"))
        self.assertIsInstance(self.exporter.EXPORT_DIRECTORIES, dict)

    @unittest.skipIf(
        ClaudeCommandsExporter is None, "ClaudeCommandsExporter not available"
    )
    def test_export_directory_has_required_keys(self):
        """Test that each export config has required keys."""
        required_configs = ["commands", "hooks", "orchestration", "automation"]

        for config_name in required_configs:
            self.assertIn(config_name, self.exporter.EXPORT_DIRECTORIES)
            config = self.exporter.EXPORT_DIRECTORIES[config_name]
            self.assertIn("source", config)
            self.assertIsInstance(config.get("exclude_dirs", []), list)
            self.assertIsInstance(config.get("exclude_files", []), list)

    @unittest.skipIf(
        ClaudeCommandsExporter is None, "ClaudeCommandsExporter not available"
    )
    def test_generic_export_directory_method_exists(self):
        """Test that _export_directory generic method exists."""
        self.assertTrue(hasattr(self.exporter, "_export_directory"))
        self.assertTrue(callable(getattr(self.exporter, "_export_directory")))

    @unittest.skipIf(
        ClaudeCommandsExporter is None, "ClaudeCommandsExporter not available"
    )
    def test_export_directory_with_file_exclusions(self):
        """Test generic export with file exclusions."""
        # Create test directory with files to exclude
        source_dir = os.path.join(self.project_root, "test_source")
        os.makedirs(source_dir)

        # Create test files
        files = ["include.py", "exclude.pyc", "include.md", "exclude.tmp"]
        for f in files:
            with open(os.path.join(source_dir, f), "w") as file:
                file.write(f"Content of {f}")

        # Export config
        config = {"source": "test_source", "exclude_files": ["*.pyc", "*.tmp"]}

        staging_dir = os.path.join(self.export_dir, "staging")
        os.makedirs(staging_dir, exist_ok=True)

        # Force manual copy by making rsync raise FileNotFoundError
        with patch("subprocess.run", side_effect=FileNotFoundError("rsync not found")):
            self.exporter._export_directory("test", config, staging_dir)

        # Verify only included files were copied
        target_dir = os.path.join(staging_dir, "test")
        copied_files = os.listdir(target_dir)

        self.assertIn("include.py", copied_files)
        self.assertIn("include.md", copied_files)
        self.assertNotIn("exclude.pyc", copied_files)
        self.assertNotIn("exclude.tmp", copied_files)

    @unittest.skipIf(
        ClaudeCommandsExporter is None, "ClaudeCommandsExporter not available"
    )
    def test_export_directory_with_dir_exclusions(self):
        """Test generic export with directory exclusions."""
        # Create test directory structure
        source_dir = os.path.join(self.project_root, "test_source")
        os.makedirs(os.path.join(source_dir, "include_dir"))
        os.makedirs(os.path.join(source_dir, "__pycache__"))

        # Create test files
        with open(os.path.join(source_dir, "include_dir", "file.py"), "w") as f:
            f.write("Included")
        with open(os.path.join(source_dir, "__pycache__", "file.pyc"), "w") as f:
            f.write("Excluded")

        # Export config
        config = {"source": "test_source", "exclude_dirs": ["__pycache__"]}

        staging_dir = os.path.join(self.export_dir, "staging")
        os.makedirs(staging_dir, exist_ok=True)

        # Force manual copy by making rsync raise FileNotFoundError
        with patch("subprocess.run", side_effect=FileNotFoundError("rsync not found")):
            self.exporter._export_directory("test", config, staging_dir)

        # Verify directory structure
        target_dir = os.path.join(staging_dir, "test")
        self.assertTrue(
            os.path.exists(os.path.join(target_dir, "include_dir", "file.py"))
        )
        self.assertFalse(os.path.exists(os.path.join(target_dir, "__pycache__")))

    @unittest.skipIf(
        ClaudeCommandsExporter is None, "ClaudeCommandsExporter not available"
    )
    def test_export_directory_uses_rsync_when_available(self):
        """Test that generic export uses rsync when available."""
        source_dir = os.path.join(self.project_root, "test_source")
        os.makedirs(source_dir)

        config = {"source": "test_source", "exclude_dirs": ["test_exclude"]}

        staging_dir = os.path.join(self.export_dir, "staging")
        os.makedirs(staging_dir, exist_ok=True)

        # Mock subprocess to capture rsync call
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            self.exporter._export_directory("test", config, staging_dir)

            # Verify rsync was called with correct exclusions
            if mock_run.called:
                args = mock_run.call_args[0][0]
                self.assertEqual(args[0], "rsync")
                self.assertIn("-av", args)
                self.assertIn("--exclude=test_exclude/", args)

    @unittest.skipIf(
        ClaudeCommandsExporter is None, "ClaudeCommandsExporter not available"
    )
    def test_copy_to_repository_preserves_codex_layout(self):
        """Codex staging entries must publish back into .codex/ paths."""
        temp_dir = tempfile.mkdtemp(prefix="test_codex_publish_")
        try:
            project_root = os.path.join(temp_dir, "project")
            export_dir = os.path.join(temp_dir, "export")
            repo_dir = os.path.join(temp_dir, "repo")
            os.makedirs(project_root)
            os.makedirs(repo_dir)

            with patch.object(
                ClaudeCommandsExporter,
                "_get_project_root",
                return_value=project_root,
            ):
                exporter = ClaudeCommandsExporter()
                exporter.export_dir = export_dir
                exporter.repo_dir = repo_dir

            staging_dir = os.path.join(export_dir, "staging")
            os.makedirs(os.path.join(staging_dir, "codex_skills"), exist_ok=True)
            os.makedirs(os.path.join(staging_dir, "codex_hooks"), exist_ok=True)

            with open(os.path.join(staging_dir, "codex_skills", "skill.md"), "w") as f:
                f.write("# skill")
            with open(os.path.join(staging_dir, "codex_hooks", "hook.sh"), "w") as f:
                f.write("#!/bin/bash\n")
            with open(os.path.join(staging_dir, "codex_hooks.json"), "w") as f:
                f.write('{"hooks": []}\n')
            with open(os.path.join(export_dir, "README.md"), "w") as f:
                f.write("# export\n")

            exporter._copy_to_repository()

            self.assertTrue(
                os.path.exists(os.path.join(repo_dir, ".codex", "skills", "skill.md"))
            )
            self.assertTrue(
                os.path.exists(os.path.join(repo_dir, ".codex", "hooks", "hook.sh"))
            )
            self.assertTrue(
                os.path.exists(os.path.join(repo_dir, ".codex", "hooks.json"))
            )
            self.assertFalse(os.path.exists(os.path.join(repo_dir, "codex_skills")))
            self.assertFalse(os.path.exists(os.path.join(repo_dir, "codex_hooks")))
            self.assertFalse(os.path.exists(os.path.join(repo_dir, "codex_hooks.json")))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


class TestExportScriptIntegrity(unittest.TestCase):
    """Verify that every script referenced by export logic exists in the source tree.

    These tests catch the class of bug where export code references a script that
    was moved, renamed, or never committed - resulting in silent omissions in the
    exported claude-commands repo.
    """

    @classmethod
    def setUpClass(cls):
        """Locate project root relative to this test file."""
        cls.project_root = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..", "..")
        )
        cls.scripts_root = os.path.join(cls.project_root, "scripts")
        cls.claude_scripts = os.path.join(cls.project_root, ".claude", "scripts")

    def test_auth_cli_mjs_present_in_claude_scripts(self):
        """auth-cli.mjs must exist in .claude/scripts/ (source for export)."""
        path = os.path.join(self.claude_scripts, "auth-cli.mjs")
        self.assertTrue(
            os.path.isfile(path),
            "Missing .claude/scripts/auth-cli.mjs — required by secondo-cli.sh and /secondo",
        )

    def test_secondo_cli_sh_present_in_claude_scripts(self):
        """secondo-cli.sh must exist in .claude/scripts/ (source for export)."""
        path = os.path.join(self.claude_scripts, "secondo-cli.sh")
        self.assertTrue(
            os.path.isfile(path),
            "Missing .claude/scripts/secondo-cli.sh — required by /secondo command",
        )

    @unittest.skipIf(
        ClaudeCommandsExporter is None, "ClaudeCommandsExporter not available"
    )
    def test_claude_scripts_mjs_files_are_exported(self):
        """_export_claude_scripts must include *.mjs in its glob patterns.

        Regression guard: previously only *.py and *.sh were exported, silently
        dropping all *.mjs files (auth-cli.mjs, auth-aiuniverse.mjs, etc.).
        """
        exporter_path = os.path.join(
            os.path.dirname(__file__), "..", "exportcommands.py"
        )
        with open(exporter_path) as f:
            source = f.read()

        # Find the _export_claude_scripts method and verify *.mjs is present
        # We look for the tuple/sequence of patterns passed to glob
        self.assertIn(
            "*.mjs",
            source,
            "_export_claude_scripts must include '*.mjs' glob pattern; "
            "auth-cli.mjs and other .mjs files were being silently skipped",
        )

    def test_secondo_scripts_in_export_scripts_exist_in_scripts_root(self):
        """Every script listed in secondo_scripts (scripts/ root) must exist there."""
        # These are the scripts that _export_scripts looks for in scripts/
        # (auth-cli.mjs and secondo-cli.sh belong to .claude/scripts/ and are
        #  excluded from this list since #PR that fixed the path mismatch)
        secondo_scripts_in_root = ["test_secondo_pr.sh"]
        for script_name in secondo_scripts_in_root:
            path = os.path.join(self.scripts_root, script_name)
            self.assertTrue(
                os.path.isfile(path),
                f"secondo script listed in _export_scripts not found: scripts/{script_name}",
            )

    @unittest.skipIf(
        ClaudeCommandsExporter is None, "ClaudeCommandsExporter not available"
    )
    def test_no_mjs_files_in_secondo_scripts_pointing_to_wrong_dir(self):
        """auth-cli.mjs must NOT be in the secondo_scripts list that looks in scripts/.

        auth-cli.mjs lives in .claude/scripts/, not scripts/.  If it appears in
        secondo_scripts it will never be found there and will be silently omitted
        from the export.
        """
        exporter_path = os.path.join(
            os.path.dirname(__file__), "..", "exportcommands.py"
        )
        with open(exporter_path) as f:
            source = f.read()

        # Find the secondo_scripts assignment line
        match = re.search(r"secondo_scripts\s*=\s*\[([^\]]*)\]", source)
        self.assertIsNotNone(
            match, "Could not find secondo_scripts list in exportcommands.py"
        )
        list_contents = match.group(1)
        self.assertNotIn(
            "auth-cli.mjs",
            list_contents,
            "auth-cli.mjs must not be in secondo_scripts (lives in .claude/scripts/, "
            "not scripts/); it is exported by _export_claude_scripts instead",
        )
        self.assertNotIn(
            "secondo-cli.sh",
            list_contents,
            "secondo-cli.sh must not be in secondo_scripts (lives in .claude/scripts/, "
            "not scripts/); it is exported by _export_claude_scripts instead",
        )


if __name__ == "__main__":
    # Run tests with verbose output
    unittest.main(verbosity=2)
