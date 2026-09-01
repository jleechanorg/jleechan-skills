"""Contracts for exported workflow command and skill pairs."""

import os
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
COMMANDS = REPO_ROOT / ".claude" / "commands"
SKILLS = REPO_ROOT / ".claude" / "skills"


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

        self.assertTrue(
            (
                SKILLS
                / "plan-micro"
                / "references"
                / "history-baseline-2026-08-04-06.md"
            ).is_file()
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

    def test_parallel_command_points_to_canonical_lane_routing_contract(self):
        parallel = (COMMANDS / "extended-library" / "parallel.md").read_text(
            encoding="utf-8"
        )
        skill = (SKILLS / "parallelize-to-ceiling" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            "${CLAUDE_HOME:-$HOME/.claude}/skills/parallelize-to-ceiling/SKILL.md",
            parallel,
        )
        self.assertNotIn("## Coding and verification lane routing", parallel)
        self.assertNotIn("## Fallback precedence", parallel)
        self.assertNotIn("## Isolation contract", parallel)
        for required in (
            "## Coding and verification lane routing",
            "${CLAUDE_HOME:-$HOME/.claude}/agents/agy-pair-coder.md",
            "${CLAUDE_HOME:-$HOME/.claude}/agents/agy-pair-verifier.md",
            (
                "FALLBACK: if an AGY lane concretely fails, retry that lane with "
                "codexs, claudem, or an own cheap agent while preserving "
                "isolation and independent verification."
            ),
            "## Codex model routing",
            "## Fallback precedence",
            "`FALLBACK` template above is governed by this order:",
            "retry the same bounded lane with",
            "invoke the Codex CLI explicitly with `-m gpt-5.6-luna`, then",
            "Use `claudem` or an own cheap agent only when the ordered Codex",
            "unavailable; preserve the same bounded scope",
            "## Isolation contract",
            "distinct lanes and contexts",
            "disjoint workspace/output",
            "verifier must",
            "independently rerun focused checks before signaling completion",
        ):
            with self.subTest(required=required):
                self.assertIn(required, skill)

        normalized_skill = " ".join(skill.split())
        self.assertIn(
            "`codexs` as the Spark fallback; codexs is not a multi-model router",
            normalized_skill,
        )
        self.assertIn(
            "`gpt-5.3-codex-spark` → `gpt-5.6-luna` → "
            "`gpt-5.6-terra` → `gpt-5.6-sol`",
            normalized_skill,
        )
        self.assertIn(
            "retry the same bounded lane with the next explicit model",
            normalized_skill,
        )
        self.assertIn(
            "advancing only after a concrete failure in that lane",
            normalized_skill,
        )

    def test_retry_isolation_covers_every_attempt_and_prior_attempts(self):
        skill = (SKILLS / "parallelize-to-ceiling" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        normalized_skill = " ".join(skill.split())
        self.assertIn(
            "Every attempt, including initial execution and each retry, uses a "
            "fresh workspace (either an allocated detached worktree or "
            "caller-provided clean workspace) and unique output/log paths "
            "disjoint from both coder and verifier lanes and from all previous "
            "attempts.",
            normalized_skill,
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

    def test_retry_contract_forbids_conversation_reuse(self):
        skill = (SKILLS / "parallelize-to-ceiling" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        coder = (REPO_ROOT / ".claude" / "agents" / "agy-pair-coder.md").read_text(
            encoding="utf-8"
        )
        verifier = (
            REPO_ROOT / ".claude" / "agents" / "agy-pair-verifier.md"
        ).read_text(encoding="utf-8")
        for name, content in (
            ("skill", skill),
            ("coder", coder),
            ("verifier", verifier),
        ):
            with self.subTest(document=name):
                self.assertNotIn("--continue", content)
                self.assertNotIn("--conversation", content)
        normalized_skill = " ".join(skill.split())
        self.assertIn(
            "every retry uses a fresh detached worktree and unique output/log paths",
            normalized_skill,
        )
        self.assertIn("fresh `agy --new-project`", normalized_skill)

    def test_implementation_ready_carries_exact_revision_handoff(self):
        skill = (SKILLS / "parallelize-to-ceiling" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        coder = (REPO_ROOT / ".claude" / "agents" / "agy-pair-coder.md").read_text(
            encoding="utf-8"
        )
        for name, content in (("skill", skill), ("coder", coder)):
            with self.subTest(document=name):
                self.assertIn("Revision: <exact git SHA>", content)
                self.assertIn("Worktree: <absolute path>", content)
        self.assertIn("git rev-parse HEAD", coder)

    def test_codexs_fallback_does_not_claim_multi_model_routing(self):
        skill = (SKILLS / "parallelize-to-ceiling" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        normalized_skill = " ".join(skill.split())
        self.assertIn(
            "`codexs` as the Spark fallback; codexs is not a multi-model router.",
            normalized_skill,
        )
        self.assertIn(
            "invoke the Codex CLI explicitly with `-m gpt-5.6-luna`, then "
            "`-m gpt-5.6-terra`, then `-m gpt-5.6-sol`",
            normalized_skill,
        )

    def test_initial_pair_attempts_enter_fresh_disjoint_worktrees(self):
        coder = (REPO_ROOT / ".claude" / "agents" / "agy-pair-coder.md").read_text(
            encoding="utf-8"
        )
        verifier = (
            REPO_ROOT / ".claude" / "agents" / "agy-pair-verifier.md"
        ).read_text(encoding="utf-8")
        for name, content in (("coder", coder), ("verifier", verifier)):
            normalized = " ".join(content.split())
            with self.subTest(document=name):
                self.assertIn("allocate a fresh worktree", normalized.lower())
                self.assertIn("enter the fresh", normalized.lower())
                self.assertIn("before", normalized.lower())
                if name == "coder":
                    self.assertIn("creating or changing", normalized.lower())
                else:
                    self.assertIn("before reading files", normalized.lower())
                self.assertIn("unique per-attempt output", normalized.lower())
                self.assertIn("disjoint from", normalized.lower())
                self.assertIn("other lane", normalized.lower())

    def test_coder_handoff_requires_scoped_committed_clean_revision(self):
        coder = (REPO_ROOT / ".claude" / "agents" / "agy-pair-coder.md").read_text(
            encoding="utf-8"
        )
        skill = (SKILLS / "parallelize-to-ceiling" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        normalized_coder = " ".join(coder.split())
        normalized_skill = " ".join(skill.split())
        self.assertIn("stage explicit file paths only", normalized_coder.lower())
        self.assertIn("git status --porcelain", coder)
        self.assertIn("git commit", coder)
        self.assertIn("must be empty", normalized_coder.lower())
        self.assertIn("final scoped commit", normalized_coder.lower())
        self.assertIn(
            "`Revision` is the committed clean implementation revision",
            normalized_skill,
        )

    def test_verifier_rejects_dirty_state_and_pins_clean_detached_revision(self):
        verifier = (
            REPO_ROOT / ".claude" / "agents" / "agy-pair-verifier.md"
        ).read_text(encoding="utf-8")
        normalized = " ".join(verifier.split())
        self.assertIn("reject dirty inherited state", normalized.lower())
        self.assertIn("fresh detached worktree pinned to", normalized.lower())
        self.assertIn("git worktree add", verifier)
        self.assertIn("--detach", verifier)
        self.assertIn("git status --porcelain", verifier)

    def test_verifier_captures_each_attempt_to_unique_output_path(self):
        verifier = (
            REPO_ROOT / ".claude" / "agents" / "agy-pair-verifier.md"
        ).read_text(encoding="utf-8")
        normalized = " ".join(verifier.split())
        self.assertIn(
            "allocate a unique per-attempt output path",
            normalized.lower(),
        )
        self.assertIn("> \"$AGY_OUT\" 2>&1", verifier)
        self.assertIn("AGY_OUT=", verifier)

    def test_retry_handoff_repeats_checks_and_pins_prior_revision(self):
        coder = (REPO_ROOT / ".claude" / "agents" / "agy-pair-coder.md").read_text(
            encoding="utf-8"
        )
        retry = coder.split("If verifier sends VERIFICATION_FAILED:", 1)[1]
        normalized = " ".join(retry.split())
        self.assertIn("exact prior `Revision`", normalized)
        self.assertIn(
            'git worktree add --detach "$CODER_WORKTREE" "$PRIOR_REVISION"',
            retry,
        )
        self.assertIn("git rev-parse HEAD", retry)
        self.assertIn("Run the focused tests again", normalized)
        self.assertIn("git add <explicit scoped paths>", retry)
        self.assertIn("git commit", retry)
        self.assertIn("git status --porcelain", normalized)
        self.assertIn("must be empty", normalized)

        skill = (SKILLS / "parallelize-to-ceiling" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        normalized_skill = " ".join(skill.split())
        self.assertIn(
            "retry must carry the exact prior `Revision`",
            normalized_skill,
        )
        self.assertIn("rerun focused checks", normalized_skill)
        self.assertIn("final scoped commit", normalized_skill)

    def test_coder_retry_allocates_and_enters_a_unique_pinned_worktree(self):
        coder = (REPO_ROOT / ".claude" / "agents" / "agy-pair-coder.md").read_text(
            encoding="utf-8"
        )
        retry = coder.split("If verifier sends VERIFICATION_FAILED:", 1)[1]
        self.assertIn(
            'CODER_WORKTREE="$(mktemp -d -t agy_coder_retry_worktree.XXXXXX)"',
            retry,
        )
        self.assertIn(
            'if ! git worktree add --detach "$CODER_WORKTREE" "$PRIOR_REVISION";',
            retry,
        )
        self.assertIn('cd "$CODER_WORKTREE"', retry)
        self.assertIn(
            'git -C "$CODER_WORKTREE" rev-parse HEAD',
            retry,
        )
        self.assertIn("equals `PRIOR_REVISION`", retry)

    def test_verifier_worktree_setup_fails_closed_and_checks_revision(self):
        verifier = (
            REPO_ROOT / ".claude" / "agents" / "agy-pair-verifier.md"
        ).read_text(encoding="utf-8")
        self.assertIn(
            'if ! git worktree add --detach "$VERIFIER_WORKTREE" "$REVISION";',
            verifier,
        )
        self.assertIn(
            'if ! VERIFIER_STATUS="$(git -C "$VERIFIER_WORKTREE" status --porcelain)";',
            verifier,
        )
        self.assertIn(
            'git -C "$VERIFIER_WORKTREE" rev-parse HEAD',
            verifier,
        )
        self.assertIn("must equal `$REVISION`", verifier)

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

    def test_verifier_retries_are_read_only_and_do_not_commit(self):
        verifier = (
            REPO_ROOT / ".claude" / "agents" / "agy-pair-verifier.md"
        ).read_text(encoding="utf-8")
        normalized_verifier = " ".join(verifier.split())
        self.assertIn(
            "Every verifier retry carries the handed-off `Revision`",
            normalized_verifier,
        )
        self.assertIn(
            "reruns focused checks read-only",
            normalized_verifier,
        )
        self.assertIn(
            "Never modify files or create a commit",
            normalized_verifier,
        )
        skill = (SKILLS / "parallelize-to-ceiling" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        normalized_skill = " ".join(skill.split())
        self.assertIn("Each coder retry must carry", normalized_skill)
        self.assertIn("Verifier retries must carry", normalized_skill)
        self.assertIn("rerun focused checks read-only", normalized_skill)
        self.assertIn("never modify files or create a commit", normalized_skill)

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


if __name__ == "__main__":
    unittest.main()
