import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
LUNA_PATH = ROOT / ".claude/skills/luna/scripts/audit_prs.py"


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


audit_prs = load_module("audit_prs_contract", LUNA_PATH)
sys.path.insert(0, str(ROOT / ".claude/commands"))
from _copilot_modules import commentfetch, scratch_paths
import commentreply


class ScratchRoutingContracts(unittest.TestCase):
    def test_luna_uses_canonical_resolver_and_propagates_failure(self):
        failed = subprocess.CompletedProcess(
            [str(audit_prs.SCRATCH_RESOLVER)], 75, stdout="", stderr="Scratch unavailable"
        )
        with mock.patch.object(audit_prs.subprocess, "run", return_value=failed):
            with self.assertRaisesRegex(RuntimeError, "canonical Scratch resolver failed"):
                audit_prs._scratch_root()

    def test_luna_keeps_required_pending_checks_pending(self):
        payload = {
            "mergeable": "MERGEABLE",
            "mergeStateStatus": "BLOCKED",
            "statusCheckRollup": [
                {"__typename": "CheckRun", "name": "required-ci",
                 "status": "IN_PROGRESS", "conclusion": None}
            ],
            "files": [],
        }
        with mock.patch.object(audit_prs, "run_cmd", return_value=json.dumps(payload)):
            result = audit_prs.inspect_pr_status({"number": 7})
        self.assertEqual(result["category"], "PENDING_OR_BLOCKED")
        self.assertEqual(result["pending_checks"], ["required-ci"])

    def test_luna_green_requires_completed_required_checks_and_clean_merge_state(self):
        payload = {
            "mergeable": "MERGEABLE",
            "mergeStateStatus": "CLEAN",
            "statusCheckRollup": [
                {"__typename": "CheckRun", "name": "required-ci",
                 "status": "COMPLETED", "conclusion": "SUCCESS"}
            ],
            "files": [],
        }
        with mock.patch.object(audit_prs, "run_cmd", return_value=json.dumps(payload)):
            result = audit_prs.inspect_pr_status({"number": 8})
        self.assertEqual(result["category"], "CLEAN_GREEN")
        self.assertEqual(result["pending_checks"], [])

    def test_luna_rejects_unknown_or_incomplete_required_entries(self):
        entries = [
            {"name": "missing-type", "status": "COMPLETED", "conclusion": "SUCCESS"},
            {"__typename": "UnknownUnion", "name": "unknown-type", "status": "IN_PROGRESS"},
            {"__typename": "StatusContext", "name": "missing-state"},
            {"__typename": "CheckRun", "name": "missing-status", "conclusion": "SUCCESS"},
            {"__typename": "CheckRun", "name": "unknown-conclusion",
             "status": "COMPLETED", "conclusion": ""},
        ]
        for entry in entries:
            with self.subTest(entry=entry):
                payload = {
                    "mergeable": "MERGEABLE",
                    "mergeStateStatus": "CLEAN",
                    "statusCheckRollup": [entry],
                    "files": [],
                }
                with mock.patch.object(audit_prs, "run_cmd", return_value=json.dumps(payload)):
                    result = audit_prs.inspect_pr_status({"number": 9})
                self.assertEqual(result["category"], "PENDING_OR_BLOCKED")
                self.assertIn(entry["name"], result["pending_checks"])

    def test_luna_accepts_both_github_check_union_variants(self):
        entries = [
            {"__typename": "StatusContext", "name": "status-context",
             "state": "SUCCESS"},
            {"__typename": "CheckRun", "name": "check-run",
             "status": "COMPLETED", "conclusion": "SUCCESS"},
        ]
        for entry in entries:
            with self.subTest(entry=entry):
                payload = {
                    "mergeable": "MERGEABLE",
                    "mergeStateStatus": "CLEAN",
                    "statusCheckRollup": [entry],
                    "files": [],
                }
                with mock.patch.object(audit_prs, "run_cmd", return_value=json.dumps(payload)):
                    result = audit_prs.inspect_pr_status({"number": 10})
                self.assertEqual(result["category"], "CLEAN_GREEN")
                self.assertEqual(result["pending_checks"], [])

    def test_luna_keeps_unknown_merge_states_pending(self):
        for merge_state in ("BLOCKED", "UNKNOWN"):
            with self.subTest(merge_state=merge_state):
                payload = {
                    "mergeable": "MERGEABLE",
                    "mergeStateStatus": merge_state,
                    "statusCheckRollup": [
                        {"__typename": "CheckRun", "name": "required-ci",
                         "status": "COMPLETED", "conclusion": "SUCCESS"}
                    ],
                    "files": [],
                }
                with mock.patch.object(audit_prs, "run_cmd", return_value=json.dumps(payload)):
                    result = audit_prs.inspect_pr_status({"number": 11})
                self.assertEqual(result["category"], "PENDING_OR_BLOCKED")

    def test_luna_admits_report_scratch_before_provider_dispatch(self):
        item = {
            "number": 12,
            "title": "fixture",
            "branch": "fixture",
            "age_hours": 9,
            "url": "https://example.invalid/12",
            "category": "CLEAN_GREEN",
        }
        with mock.patch.object(
            audit_prs,
            "get_luna_review_dir",
            side_effect=RuntimeError("configured Scratch unavailable"),
        ), mock.patch.object(
            audit_prs.subprocess,
            "Popen",
            side_effect=AssertionError("provider must not be called"),
        ) as provider:
            with self.assertRaisesRegex(RuntimeError, "configured Scratch unavailable"):
                audit_prs.review_single_pr(item)
        provider.assert_not_called()

    def test_comment_fetch_and_reply_roundtrip_uses_same_non_tmp_root(self):
        with tempfile.TemporaryDirectory(dir="/var/tmp") as directory:
            root = (Path(directory) / "canonical-scratch").resolve()
            root.mkdir()
            with mock.patch.object(scratch_paths, "resolve_scratch_root", return_value=root),                  mock.patch.object(commentfetch.CommentFetch, "_get_pr_author", return_value=None),                  mock.patch.object(
                     commentfetch.subprocess,
                     "run",
                     return_value=subprocess.CompletedProcess(
                         ["git"], 0, stdout="feature/roundtrip\n", stderr=""
                     ),
                 ),                  mock.patch.object(
                     commentfetch.subprocess,
                     "check_output",
                     return_value=b"/repo/jleechan-skills\n",
                 ):
                fetcher = commentfetch.CommentFetch("42", "owner/repo")
            self.assertNotEqual(fetcher.cache_dir, Path("/tmp"))
            fetcher.cache_dir.mkdir(parents=True, exist_ok=True)
            responses = fetcher.cache_dir / "responses.json"
            responses.write_text(json.dumps({"responses": [{"comment_id": 1, "response": "fixed"}]}))
            with mock.patch.object(scratch_paths, "resolve_scratch_root", return_value=root):
                loaded = commentreply.load_claude_responses("feature/roundtrip", "jleechan-skills")
            self.assertEqual(loaded["responses"][0]["comment_id"], 1)
            self.assertTrue(str(fetcher.cache_dir).startswith(str(root)))
            self.assertFalse(str(fetcher.cache_dir).startswith("/tmp/"))

    def test_comment_docs_use_the_producer_path_and_response_filename(self):
        docs = [
            ROOT / ".claude/skills/commentcheck/SKILL.md",
            ROOT / ".claude/skills/commentfetch/SKILL.md",
            ROOT / ".claude/skills/commentreply/SKILL.md",
        ]
        for doc in docs:
            content = doc.read_text()
            self.assertNotIn("scratch-dir.sh tmp", content)
            self.assertIn("scratch-dir.sh", content)
        reply_doc = (ROOT / ".claude/skills/commentreply/SKILL.md").read_text()
        self.assertIn("responses.json", reply_doc)
        self.assertNotIn("replies.json", reply_doc)
        self.assertIn("/{repo}/{branch}/copilot/comments.json", reply_doc)
        self.assertIn("/{repo}/{branch}/copilot/responses.json", reply_doc)
        commentcheck_doc = (ROOT / ".claude/skills/commentcheck/SKILL.md").read_text()
        self.assertIn("original comment IDs", commentcheck_doc)
        self.assertIn("attributable response", commentcheck_doc)
        self.assertIn("generated intent only", commentcheck_doc)
        self.assertIn("POSTED_REPLY_IDS", commentcheck_doc)
        self.assertNotIn("length > 50", commentcheck_doc)
        self.assertNotIn("Thank you CodeRabbit", commentcheck_doc)

        with tempfile.TemporaryDirectory(dir="/var/tmp") as directory:
            fixture = Path(directory).resolve()
            home = fixture / "home"
            resolver = home / ".claude/skills/scratch-space/scripts/scratch-dir.sh"
            resolver.parent.mkdir(parents=True)
            resolver.write_text(f"#!/bin/sh\nprintf '%s\\n' {fixture / 'scratch'}\n")
            resolver.chmod(0o755)
            repo_name = "jleechan-skills"
            branch_name = "feature-roundtrip"
            reader_line = next(
                line.strip()
                for line in (ROOT / ".claude/skills/commentfetch/SKILL.md").read_text().splitlines()
                if line.strip().startswith("COPILOT_DIR=")
            )
            result = subprocess.run(
                ["bash", "-c", f"REPO_NAME={repo_name} BRANCH_NAME={branch_name}\n{reader_line}\nprintf '%s' \"$COPILOT_DIR\""],
                env={**os.environ, "HOME": str(home)},
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            expected = fixture / "scratch" / repo_name / branch_name / "copilot"
            self.assertEqual(Path(result.stdout), expected)

    def test_comment_paths_fail_closed_for_resolver_and_symlink_escape(self):
        with mock.patch.object(
            scratch_paths,
            "resolve_scratch_root",
            side_effect=RuntimeError("configured Scratch unavailable"),
        ):
            with self.assertRaisesRegex(RuntimeError, "configured Scratch unavailable"):
                scratch_paths.copilot_cache_dir("repo", "branch")
            with self.assertRaisesRegex(RuntimeError, "configured Scratch unavailable"):
                commentfetch.CommentFetch("42", "owner/repo")

        with tempfile.TemporaryDirectory(dir="/var/tmp") as directory:
            root = (Path(directory) / "canonical-scratch").resolve()
            root.mkdir()
            outside = (Path(directory) / "outside").resolve()
            outside.mkdir()
            (root / "repo").symlink_to(outside, target_is_directory=True)
            with mock.patch.object(scratch_paths, "resolve_scratch_root", return_value=root):
                with self.assertRaisesRegex(RuntimeError, "escaped canonical Scratch root"):
                    scratch_paths.copilot_cache_dir("repo", "branch")

    def test_comment_leaf_files_reject_external_symlinks(self):
        with tempfile.TemporaryDirectory(dir="/var/tmp") as directory:
            root = (Path(directory) / "canonical-scratch").resolve()
            outside = (Path(directory) / "outside").resolve()
            root.mkdir()
            outside.mkdir()
            cache_dir = root / "repo" / "branch" / "copilot"
            cache_dir.mkdir(parents=True)
            (outside / "comments.json").write_text('{"comments": []}')
            (outside / "responses.json").write_text('{"responses": []}')
            (cache_dir / "comments.json").symlink_to(outside / "comments.json")
            (cache_dir / "responses.json").symlink_to(outside / "responses.json")
            with mock.patch.object(scratch_paths, "resolve_scratch_root", return_value=root):
                for filename in ("comments.json", "responses.json"):
                    with self.subTest(filename=filename):
                        with self.assertRaisesRegex(RuntimeError, "escaped canonical"):
                            scratch_paths.copilot_cache_file("repo", "branch", filename)

                # The actual comment producer uses the same leaf validator;
                # it must reject an existing escape before any API fetch/write.
                with mock.patch.object(
                    commentfetch.CommentFetch,
                    "_get_pr_author",
                    return_value=None,
                ), mock.patch.object(
                    commentfetch.subprocess,
                    "run",
                    return_value=subprocess.CompletedProcess(
                        ["git"], 0, stdout="branch\n", stderr=""
                    ),
                ), mock.patch.object(
                    commentfetch.subprocess,
                    "check_output",
                    return_value=b"/repo/repo\n",
                ):
                    with self.assertRaisesRegex(RuntimeError, "escaped canonical"):
                        commentfetch.CommentFetch("42", "owner/repo")

    def test_media_skill_allocators_fail_before_mktemp(self):
        with tempfile.TemporaryDirectory(dir="/var/tmp") as directory:
            root = Path(directory).resolve()
            home = root / "home"
            resolver = home / ".claude/skills/scratch-space/scripts/scratch-dir.sh"
            resolver.parent.mkdir(parents=True)
            resolver.write_text("#!/bin/sh\nexit 75\n")
            resolver.chmod(0o755)
            mktemp_marker = root / "mktemp-invoked"
            fake_mktemp = root / "mktemp"
            fake_mktemp.write_text(
                f"#!/bin/sh\nprintf invoked > {mktemp_marker}\nexit 77\n"
            )
            fake_mktemp.chmod(0o755)
            env = {
                **os.environ,
                "HOME": str(home),
                "CLAUDE_HOME": str(home / ".claude"),
                "PATH": f"{root}:/usr/bin:/bin",
            }
            video = subprocess.run(
                [
                    "bash",
                    "-c",
                    'scratch_tmp="$("$HOME/.claude/skills/scratch-space/scripts/scratch-dir.sh" tmp)" || exit 75; frames_dir="$(mktemp -d "$scratch_tmp/video-frames.XXXXXX")" || exit 77',
                ],
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(video.returncode, 75)
            self.assertFalse(mktemp_marker.exists())

            # The game evidence recipe must fail closed on resolver failure too;
            # an empty-output guard alone would allow a failed command to reach mktemp.
            game_failed = subprocess.run(
                [
                    "bash",
                    "-c",
                    'scratch_root="$($HOME/.claude/skills/scratch-space/scripts/scratch-dir.sh)" || exit 75; if [ -z "$scratch_root" ]; then exit 75; fi; evidence_dir="$(mktemp -d "$scratch_root/game-er.XXXXXXXX")" || exit 77',
                ],
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(game_failed.returncode, 75)
            self.assertFalse(mktemp_marker.exists())

            resolver.write_text("#!/bin/sh\nprintf '%s\\n' ''\n")
            game = subprocess.run(
                [
                    "bash",
                    "-c",
                    'scratch_root="$("$HOME/.claude/skills/scratch-space/scripts/scratch-dir.sh")"; if [ -z "$scratch_root" ]; then exit 75; fi; evidence_dir="$(mktemp -d "$scratch_root/game-er.XXXXXXXX")" || exit 77',
                ],
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(game.returncode, 75)
            self.assertFalse(mktemp_marker.exists())

    def test_canonical_and_standalone_scratch_recipes_fail_before_allocation(self):
        with tempfile.TemporaryDirectory(dir="/var/tmp") as directory:
            root = Path(directory).resolve()
            home = root / "home"
            resolver = home / ".claude/skills/scratch-space/scripts/scratch-dir.sh"
            resolver.parent.mkdir(parents=True)
            resolver.write_text("#!/bin/sh\nexit 75\n")
            resolver.chmod(0o755)
            marker = root / "mktemp-invoked"
            fake_mktemp = root / "mktemp"
            fake_mktemp.write_text(f"#!/bin/sh\nprintf invoked > {marker}\nexit 77\n")
            fake_mktemp.chmod(0o755)
            env = {
                **os.environ,
                "HOME": str(home),
                "CLAUDE_HOME": str(home / ".claude"),
                "PATH": f"{root}:/usr/bin:/bin",
            }

            scratch_skill = (ROOT / ".claude/skills/scratch-space/SKILL.md").read_text()
            first = scratch_skill.index('SCRATCH_TMP="$(~/.claude/skills/scratch-space/scripts/scratch-dir.sh tmp)"')
            start = scratch_skill.index('SCRATCH_TMP="$(~/.claude/skills/scratch-space/scripts/scratch-dir.sh tmp)"', first + 1)
            end = scratch_skill.index("```", start)
            canonical = subprocess.run(
                ["bash", "-c", scratch_skill[start:end]],
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(canonical.returncode, 75, canonical.stderr)
            self.assertFalse(marker.exists())

            tmux = (ROOT / ".claude/skills/tmux-video-evidence/SKILL.md").read_text()
            start = tmux.index('  archive_scratch=')
            end = tmux.index('  zip_file=', start)
            archive = subprocess.run(
                ["bash", "-c", tmux[start:end]],
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(archive.returncode, 75, archive.stderr)
            self.assertFalse(marker.exists())

            start = tmux.index('SCRATCH_TMP="$(~/.claude/skills/scratch-space/scripts/scratch-dir.sh tmp)"', tmux.index("## Compression Guidance"))
            end = tmux.index("\n", tmux.index("ffmpeg -y", start))
            compression = subprocess.run(
                ["bash", "-c", tmux[start:end]],
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(compression.returncode, 75, compression.stderr)
            self.assertFalse(marker.exists())

    def test_commentcheck_coverage_requires_posted_readback(self):
        document = (ROOT / ".claude/skills/commentcheck/SKILL.md").read_text()
        start = document.index("set -o pipefail")
        end = document.index("\n```", start)
        step = document[start:end]

        def run_step(comments, responses):
            with tempfile.TemporaryDirectory(dir="/var/tmp") as directory:
                responses_path = Path(directory) / "responses.json"
                responses_path.write_text(json.dumps({"responses": responses}))
                comments_path = Path(directory) / "comments.json"
                comments_path.write_text(
                    json.dumps({"comments": comments, "metadata": {"repo": "owner/repo"}})
                )
                fake_bin = Path(directory) / "bin"
                fake_bin.mkdir()
                fake_gh = fake_bin / "gh"
                fake_gh.write_text("#!/bin/sh\nprintf '%s\\n' verified-bot\n")
                fake_gh.chmod(0o755)
                return subprocess.run(
                    ["bash", "-c", step],
                    env={
                        **os.environ,
                        "COMMENTS_FILE": str(comments_path),
                        "RESPONSES_FILE": str(responses_path),
                        "PR_NUMBER": "1",
                        "COPILOT_RESPONDER_LOGIN": "verified-bot",
                        "COMMENT_COMMANDS_DIR": str(ROOT / ".claude/commands"),
                        "PATH": f"{fake_bin}:/usr/bin:/bin",
                    },
                    capture_output=True,
                    text=True,
                    check=False,
                )

        original = {
            "id": 7,
            "body": "review point",
            "author": "reviewer",
            "type": "general",
            "html_url": "https://github.com/owner/repo/pull/1#discussion_r7",
            "already_replied": False,
        }
        generated = [{"comment_id": 7, "reply_text": "generated but not posted"}]
        coverage_footer = json.dumps(
            {
                "schema": "copilot-coverage/v1",
                "repo": "owner/repo",
                "pr": "1",
                "responses": [
                    {"comment_id": "7", "url": "https://github.com/owner/repo/pull/1#discussion_r7"},
                    {"comment_id": "8", "url": "https://github.com/owner/repo/pull/1#issuecomment-8"},
                ],
            },
            separators=(",", ":"),
        )
        unposted = run_step([original], generated)
        self.assertNotEqual(unposted.returncode, 0)
        self.assertIn("Missing original comment ID: 7", unposted.stdout + unposted.stderr)

        posted = run_step(
            [
                original,
                {
                    "id": 8,
                    "body": "[AI responder] fixed",
                    "author": "verified-bot",
                    "type": "general",
                    "in_reply_to_id": 7,
                },
            ],
            generated,
        )
        self.assertEqual(posted.returncode, 0, posted.stdout + posted.stderr)

        partial = run_step(
            [
                original,
                {"id": 8, "body": "second point", "author": "reviewer", "type": "general", "html_url": "https://github.com/owner/repo/pull/1#issuecomment-8"},
                {
                    "id": 9,
                    "body": "[AI responder] fixed first",
                    "author": "verified-bot",
                    "type": "general",
                    "in_reply_to_id": 7,
                },
            ],
            generated,
        )
        self.assertNotEqual(partial.returncode, 0)
        self.assertIn("Missing original comment ID: 8", partial.stdout)

        summary = run_step(
            [
                original,
                {"id": 8, "body": "second point", "author": "reviewer", "type": "general", "html_url": "https://github.com/owner/repo/pull/1#issuecomment-8"},
                {
                    "id": 99,
                    "body": f"## 🤖 [AI responder] Consolidated Comment Response Summary\n<!-- COPILOT_COVERAGE_V1 {coverage_footer} -->",
                    "author": "verified-bot",
                    "type": "general",
                },
            ],
            generated,
        )
        self.assertEqual(summary.returncode, 0, summary.stdout + summary.stderr)

        wrong_destination = run_step(
            [
                original,
                {
                    "id": 99,
                    "body": "## 🤖 [AI responder] Consolidated Comment Response Summary\n### 1. Re: [Comment #7](https://example.invalid/unrelated)",
                    "author": "verified-bot",
                    "type": "general",
                },
            ],
            generated,
        )
        self.assertNotEqual(wrong_destination.returncode, 0)
        self.assertIn("Missing original comment ID: 7", wrong_destination.stdout)

        quoted_summary = run_step(
            [
                original,
                {
                    "id": 99,
                    "body": "> ## 🤖 [AI responder] Consolidated Comment Response Summary\n> Re: [Comment #7](https://github.com/owner/repo/pull/1#discussion_r7)",
                    "author": "verified-bot",
                    "type": "general",
                },
            ],
            generated,
        )
        self.assertNotEqual(quoted_summary.returncode, 0)
        self.assertIn("Missing original comment ID: 7", quoted_summary.stdout)

        malformed = run_step(["not-a-comment"], generated)
        self.assertEqual(malformed.returncode, 2)
        self.assertIn("commentfetch records are malformed", malformed.stderr)

        unrelated = run_step(
            [
                original,
                {
                    "id": 8,
                    "body": "unrelated reviewer reply",
                    "author": "other-reviewer",
                    "type": "general",
                    "in_reply_to_id": 7,
                },
            ],
            generated,
        )
        self.assertNotEqual(unrelated.returncode, 0)
        self.assertIn("Missing original comment ID: 7", unrelated.stdout)

        prefix_collision = run_step(
            [
                original,
                {
                    "id": 70,
                    "body": "## 🤖 [AI responder] Consolidated Comment Response Summary\n### 1. Re: [Comment #70](https://github.com/owner/repo/pull/1#discussion_r70)",
                    "author": "verified-bot",
                    "type": "general",
                },
            ],
            generated,
        )
        self.assertNotEqual(prefix_collision.returncode, 0)
        self.assertIn("Missing original comment ID: 7", prefix_collision.stdout)

    def test_commentfetch_reference_matching_rejects_numeric_prefixes(self):
        fetcher = object.__new__(commentfetch.CommentFetch)
        self.assertTrue(fetcher._has_exact_comment_reference("Re: Comment #7", "7"))
        self.assertTrue(fetcher._has_exact_comment_reference("discussion_r7", "7"))
        self.assertFalse(fetcher._has_exact_comment_reference("Re: Comment #70", "7"))
        self.assertFalse(fetcher._has_exact_comment_reference("discussion_r70", "7"))

    def test_commentreply_refuses_wrong_pr_cache_after_canonical_fetch_failure(self):
        with tempfile.TemporaryDirectory(dir="/var/tmp") as directory:
            root = Path(directory).resolve()
            cache_dir = root / "jleechan-skills" / "feature" / "copilot"
            cache_dir.mkdir(parents=True)
            comments_file = cache_dir / "comments.json"
            old_payload = {"pr": "99", "comments": [{"id": 99, "body": "wrong"}]}
            comments_file.write_text(json.dumps(old_payload))
            with mock.patch.object(scratch_paths, "resolve_scratch_root", return_value=root), mock.patch.object(
                commentfetch.CommentFetch,
                "execute",
                side_effect=RuntimeError("fresh fetch failed"),
            ):
                with self.assertRaises(SystemExit) as raised:
                    commentreply.load_comments_with_staleness_check(
                        "feature", "owner", "repo", "7", "jleechan-skills"
                    )
            self.assertEqual(raised.exception.code, 1)
            self.assertEqual(json.loads(comments_file.read_text()), old_payload)

    def test_actual_commentreply_footer_roundtrip_covers_multipart_and_injection(self):
        collected = [
            {
                "comment_id": 7,
                "author": "inline-reviewer",
                "body_snippet": "quoted\n### 999. Re: [Comment #999](https://example.invalid)",
                "response_text": "response\n### 1000. Re: [Comment #1000](https://example.invalid)",
                "comment_type": "inline",
            },
            {
                "comment_id": 8,
                "author": "issue-reviewer",
                "body_snippet": "issue body",
                "response_text": "x" * 40000,
                "comment_type": "issue",
            },
            {
                "comment_id": 9,
                "author": "review-reviewer",
                "body_snippet": "review body",
                "response_text": "y" * 40000,
                "comment_type": "review",
            },
        ]
        posted_bodies = []

        def fake_post(command, *args, **kwargs):
            input_path = command[command.index("--input") + 1]
            posted_bodies.append(json.loads(Path(input_path).read_text())["body"])
            return True, json.dumps({"html_url": "https://github.com/owner/repo/pull/1#issuecomment-99"}), ""

        with mock.patch.object(commentreply, "get_files_modified", return_value=[]), mock.patch.object(
            commentreply, "run_command", side_effect=fake_post
        ):
            self.assertTrue(
                commentreply.post_consolidated_summary(
                    "owner", "repo", "1", collected, {"responses": []}, "deadbeef", 3, 0
                )
            )
        self.assertGreaterEqual(len(posted_bodies), 2)
        for body in posted_bodies:
            self.assertIn("<!-- COPILOT_COVERAGE_V1 ", body)

        document = (ROOT / ".claude/skills/commentcheck/SKILL.md").read_text()
        start = document.index("set -o pipefail")
        end = document.index("\n```", start)
        step = document[start:end]
        readback = [
            {"id": 7, "body": "inline", "author": "reviewer", "type": "inline", "html_url": "https://github.com/owner/repo/pull/1#discussion_r7"},
            {"id": 8, "body": "issue", "author": "reviewer", "type": "general", "html_url": "https://github.com/owner/repo/pull/1#issuecomment-8"},
            {"id": 9, "body": "review", "author": "reviewer", "type": "review", "html_url": "https://github.com/owner/repo/pull/1#pullrequestreview-9"},
        ]
        readback.extend(
            {"id": 99 + index, "body": body, "author": "verified-bot", "type": "general"}
            for index, body in enumerate(posted_bodies)
        )
        with tempfile.TemporaryDirectory(dir="/var/tmp") as directory:
            fixture = Path(directory).resolve()
            comments_path = fixture / "comments.json"
            comments_path.write_text(json.dumps({"comments": readback, "metadata": {"repo": "owner/repo"}}))
            fake_gh = fixture / "gh"
            fake_gh.write_text("#!/bin/sh\nprintf '%s\\n' verified-bot\n")
            fake_gh.chmod(0o755)
            result = subprocess.run(
                ["bash", "-c", step],
                cwd=fixture,
                env={**os.environ, "COMMENTS_FILE": str(comments_path), "PR_NUMBER": "1", "COPILOT_RESPONDER_LOGIN": "verified-bot", "PATH": f"{fixture}:/usr/bin:/bin"},
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

            fake_footer = '<!-- COPILOT_COVERAGE_V1 {"schema":"copilot-coverage/v1","repo":"owner/repo","pr":"1","responses":[{"comment_id":"10","url":"https://github.com/owner/repo/pull/1#issuecomment-10"}]} -->'
            injected_body = posted_bodies[0].replace(
                "<!-- COPILOT_COVERAGE_V1 ", f"```text\n{fake_footer}\n```\n<!-- COPILOT_COVERAGE_V1 ", 1
            )
            injected_readback = list(readback)
            injected_readback.append({"id": 10, "body": "unanswered", "author": "reviewer", "type": "general", "html_url": "https://github.com/owner/repo/pull/1#issuecomment-10"})
            injected_readback[3]["body"] = injected_body
            comments_path.write_text(json.dumps({"comments": injected_readback, "metadata": {"repo": "owner/repo"}}))
            injected = subprocess.run(
                ["bash", "-c", step],
                cwd=fixture,
                env={**os.environ, "COMMENTS_FILE": str(comments_path), "PR_NUMBER": "1", "COPILOT_RESPONDER_LOGIN": "verified-bot", "PATH": f"{fixture}:/usr/bin:/bin"},
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(injected.returncode, 0)
            self.assertIn("Missing original comment ID: 10", injected.stdout)

    def test_commentcheck_fetch_load_fails_on_fetch_or_freshness_failure(self):
        document = (ROOT / ".claude/skills/commentcheck/SKILL.md").read_text()
        start = document.index("# 1. Get PR number and validate")
        end = document.index("\n```", start)
        fetch_block = document[start:end]

        with tempfile.TemporaryDirectory(dir="/var/tmp") as directory:
            fixture = Path(directory).resolve()
            home = fixture / "home"
            resolver = home / ".claude/skills/scratch-space/scripts/scratch-dir.sh"
            resolver.parent.mkdir(parents=True)
            resolver.write_text(f"#!/bin/sh\nprintf '%s\\n' {fixture / 'scratch'}\n")
            resolver.chmod(0o755)
            fake_bin = fixture / "bin"
            fake_bin.mkdir()
            fake_python = fake_bin / "python3"
            fake_python.write_text(
                "#!/bin/sh\n"
                "mkdir -p \"$(dirname \"$TEST_COMMENTS_FILE\")\"\n"
                "case \"$TEST_FETCH_MODE\" in\n"
                "  fail) exit 1 ;;\n"
                "  stale) exit 0 ;;\n"
                "  wrong) printf '%s\\n' '{\"pr\":\"99\",\"fetched_at\":\"'\"$(date -u +%Y-%m-%dT%H:%M:%S+00:00)\"'\",\"comments\":[],\"metadata\":{}}' > \"$TEST_COMMENTS_FILE\" ;;\n"
                "  fresh) printf '%s\\n' '{\"pr\":\"7\",\"fetched_at\":\"'\"$(date -u +%Y-%m-%dT%H:%M:%S+00:00)\"'\",\"comments\":[],\"metadata\":{}}' > \"$TEST_COMMENTS_FILE\" ;;\n"
                "esac\n"
            )
            fake_python.chmod(0o755)
            branch = "".join(
                c
                for c in subprocess.check_output(
                    ["git", "branch", "--show-current"], cwd=ROOT, text=True
                ).strip()
                if c.isalnum() or c in "._-"
            )
            repo_name = "".join(c for c in ROOT.name if c.isalnum() or c in "._-")
            comments_file = fixture / "scratch" / repo_name / branch / "copilot" / "comments.json"
            comments_file.parent.mkdir(parents=True)
            comments_file.write_text(
                json.dumps(
                    {
                        "pr": "7",
                        "fetched_at": "2000-01-01T00:00:00+00:00",
                        "comments": [],
                        "metadata": {"total": 0, "by_type": {}},
                    }
                )
            )
            old_time = time.time() - 120
            os.utime(comments_file, (old_time, old_time))

            def run(mode):
                return subprocess.run(
                    ["bash", "-c", fetch_block, "--", "7"],
                    cwd=ROOT,
                    env={
                        **os.environ,
                        "HOME": str(home),
                        "PATH": f"{fake_bin}:/opt/homebrew/bin:/usr/bin:/bin",
                        "COMMENT_COMMANDS_DIR": str(ROOT / ".claude/commands"),
                        "TEST_FETCH_MODE": mode,
                        "TEST_COMMENTS_FILE": str(comments_file),
                    },
                    capture_output=True,
                    text=True,
                    check=False,
                )

            for mode in ("fail", "stale", "wrong"):
                with self.subTest(mode=mode):
                    result = run(mode)
                    self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                    self.assertIn("EXIT CODE: 2", result.stderr)

            fresh = run("fresh")
            self.assertEqual(fresh.returncode, 0, fresh.stdout + fresh.stderr)

    def test_commentfetch_preserves_cache_on_api_error_but_accepts_empty_success(self):
        with tempfile.TemporaryDirectory(dir="/var/tmp") as directory:
            root = Path(directory).resolve()

            def make_fetcher(name):
                fetcher = object.__new__(commentfetch.CommentFetch)
                fetcher.pr_number = "7"
                fetcher.repo = "owner/repo"
                fetcher.comments = []
                fetcher.fetch_errors = []
                fetcher.cache_dir = root / name
                fetcher.output_file = fetcher.cache_dir / "comments.json"
                fetcher.cache_metadata_file = fetcher.cache_dir / "cache_metadata.json"
                fetcher.per_comment_cache = mock.Mock()
                fetcher._get_inline_comments = lambda: fetcher.run_gh_command(
                    ["gh", "api", "repos/owner/repo/pulls/7/comments", "--paginate"]
                )
                fetcher._get_general_comments = lambda: []
                fetcher._get_review_comments = lambda: []
                fetcher._get_copilot_comments = lambda: []
                fetcher._get_ci_status = lambda: {"overall_state": "SUCCESS"}
                fetcher._save_cache_metadata = mock.Mock()
                return fetcher

            failing = make_fetcher("failing")
            failing.cache_dir.mkdir(parents=True)
            old_payload = '{"pr":"7","fetched_at":"2000-01-01T00:00:00+00:00"}'
            failing.output_file.write_text(old_payload)
            with mock.patch.object(
                commentfetch.subprocess,
                "run",
                side_effect=subprocess.CalledProcessError(
                    1, ["gh", "api"], stderr="rate limited"
                ),
            ):
                with self.assertRaisesRegex(RuntimeError, "preserving existing cache"):
                    failing.execute()
            self.assertEqual(failing.output_file.read_text(), old_payload)
            failing.per_comment_cache.save_comments.assert_not_called()

            empty = make_fetcher("empty")
            with mock.patch.object(
                commentfetch.subprocess,
                "run",
                return_value=subprocess.CompletedProcess(
                    ["gh", "api"], 0, stdout="", stderr=""
                ),
            ):
                result = empty.execute()
            self.assertTrue(result["success"])
            self.assertEqual(json.loads(empty.output_file.read_text())["comments"], [])
            self.assertEqual(empty.fetch_errors, [])

            for name, stdout in (("mixed", '{"id": 1}\nNOT_JSON\n'), ("malformed", "NOT_JSON\n")):
                malformed = make_fetcher(name)
                malformed.cache_dir.mkdir(parents=True)
                malformed.output_file.write_text(old_payload)
                with mock.patch.object(
                    commentfetch.subprocess,
                    "run",
                    return_value=subprocess.CompletedProcess(
                        ["gh", "api"], 0, stdout=stdout, stderr=""
                    ),
                ):
                    with self.assertRaisesRegex(RuntimeError, "preserving existing cache"):
                        malformed.execute()
                self.assertEqual(malformed.output_file.read_text(), old_payload)
                self.assertTrue(malformed.fetch_errors)

    def test_web_advice_smoke_stops_on_configured_resolver_failure(self):
        script = ROOT / ".claude/skills/web-advice/scripts/e2e_smoke.sh"
        with tempfile.TemporaryDirectory(dir="/var/tmp") as directory:
            root = Path(directory)
            fake_bin = root / "bin"
            fake_bin.mkdir()
            chrome = fake_bin / "google-chrome"
            chrome.write_text("#!/bin/sh\nexit 99\n")
            chrome.chmod(0o755)
            claude_home = root / "claude"
            resolver = claude_home / "skills/scratch-space/scripts/scratch-dir.sh"
            resolver.parent.mkdir(parents=True)
            resolver.write_text("#!/bin/sh\necho configured Scratch unavailable >&2\nexit 75\n")
            resolver.chmod(0o755)
            result = subprocess.run(
                ["bash", str(script)],
                env={
                    **__import__("os").environ,
                        "PATH": f"{fake_bin}:/usr/bin:/bin",
                    "CLAUDE_HOME": str(claude_home),
                    "DISKM_SCRATCH": str(root / "missing"),
                },
                capture_output=True,
                text=True,
            )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("configured Scratch unavailable", result.stderr)

    def test_comment_docs_import_canonical_commands_outside_target_cwd(self):
        with tempfile.TemporaryDirectory(dir="/var/tmp") as directory:
            fixture = Path(directory).resolve()
            commands = fixture / "canonical-commands"
            modules = commands / "_copilot_modules"
            modules.mkdir(parents=True)
            (modules / "__init__.py").write_text("")
            (modules / "commentfetch.py").write_text(
                "class CommentFetch:\n"
                "    def __init__(self, pr_number, repo=None):\n"
                "        self.pr_number = pr_number\n"
                "    def execute(self):\n"
                "        return {'success': True}\n"
            )
            env = {
                **os.environ,
                "COMMENT_COMMANDS_DIR": str(commands),
                "PR_NUMBER": "7",
                "PATH": "/usr/bin:/bin",
            }

            check_doc = (ROOT / ".claude/skills/commentcheck/SKILL.md").read_text()
            check_start = check_doc.index('COMMANDS_DIR="${COMMENT_COMMANDS_DIR')
            check_end = check_doc.index("\n# 3. Use structured JSON output", check_start)
            check_result = subprocess.run(
                ["bash", "-c", check_doc[check_start:check_end]],
                cwd=fixture,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(check_result.returncode, 0, check_result.stderr)

            fetch_doc = (ROOT / ".claude/skills/commentfetch/SKILL.md").read_text()
            fetch_start = fetch_doc.index('COMMANDS_DIR="${COMMENT_COMMANDS_DIR')
            fetch_end = fetch_doc.index("\n# If user requested inline display", fetch_start)
            fetch_result = subprocess.run(
                ["bash", "-c", fetch_doc[fetch_start:fetch_end]],
                cwd=fixture,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(fetch_result.returncode, 0, fetch_result.stderr)

    def test_commentfetch_caller_stops_before_display_on_fetch_failure(self):
        document = (ROOT / ".claude/skills/commentfetch/SKILL.md").read_text()
        start = document.index('echo "🚀 Fetching comments for PR #$PR_NUMBER..."')
        end = document.index("\n```", start)
        block = document[start:end]
        with tempfile.TemporaryDirectory(dir="/var/tmp") as directory:
            fixture = Path(directory).resolve()
            home = fixture / "home"
            resolver = home / ".claude/skills/scratch-space/scripts/scratch-dir.sh"
            resolver.parent.mkdir(parents=True)
            scratch = fixture / "scratch"
            resolver.write_text(f"#!/bin/sh\nprintf '%s\\n' {scratch}\n")
            resolver.chmod(0o755)
            commands = fixture / "commands/_copilot_modules"
            commands.mkdir(parents=True)
            (commands / "commentfetch.py").write_text("")
            fake_bin = fixture / "bin"
            fake_bin.mkdir()
            fake_python = fake_bin / "python3"
            fake_python.write_text("#!/bin/sh\nexit 1\n")
            fake_python.chmod(0o755)
            cache = scratch / "repo" / "branch" / "copilot"
            cache.mkdir(parents=True)
            (cache / "comments.json").write_text(
                json.dumps({"pr": "7", "comments": [{"body": "STALE_BODY"}]})
            )
            result = subprocess.run(
                ["bash", "-c", block],
                cwd=fixture,
                env={
                    **os.environ,
                    "HOME": str(home),
                    "COMMENT_COMMANDS_DIR": str(fixture / "commands"),
                    "PR_NUMBER": "7",
                    "PRINT_INLINE": "true",
                    "BRANCH_NAME": "branch",
                    "REPO_NAME": "repo",
                    "PATH": f"{fake_bin}:/usr/bin:/bin",
                },
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("STALE_BODY", result.stdout + result.stderr)
        self.assertIn("refusing to display or consume cached comments", result.stderr)

    def test_web_advice_smoke_falls_back_from_aside_to_chrome(self):
        script = ROOT / ".claude/skills/web-advice/scripts/e2e_smoke.sh"
        with tempfile.TemporaryDirectory(dir="/var/tmp") as directory:
            root = Path(directory).resolve()
            fake_bin = root / "bin"
            fake_bin.mkdir()
            aside = fake_bin / "aside"
            aside.write_text("#!/bin/sh\necho aside unavailable >&2\nexit 1\n")
            aside.chmod(0o755)
            for chrome_name in ("google-chrome-stable", "google-chrome", "chromium", "chromium-browser"):
                chrome = fake_bin / chrome_name
                chrome.write_text("#!/bin/sh\nprintf '%s\\n' '<title>Example Domain</title>'\n")
                chrome.chmod(0o755)
            claude_home = root / "claude"
            resolver = claude_home / "skills/scratch-space/scripts/scratch-dir.sh"
            resolver.parent.mkdir(parents=True)
            resolver.write_text(f"#!/bin/sh\nprintf '%s\\n' {root / 'scratch'}\n")
            resolver.chmod(0o755)
            (root / "scratch").mkdir()
            result = subprocess.run(
                ["bash", str(script)],
                env={
                    **os.environ,
                    "PATH": f"{fake_bin}:/usr/bin:/bin",
                    "CLAUDE_HOME": str(claude_home),
                },
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Aside REPL browser: DOWN", result.stdout)
        self.assertIn("Chrome headless browser: UP", result.stdout)

    def test_web_advice_smoke_stops_when_profile_allocation_fails(self):
        script = ROOT / ".claude/skills/web-advice/scripts/e2e_smoke.sh"
        with tempfile.TemporaryDirectory(dir="/var/tmp") as directory:
            root = Path(directory).resolve()
            fake_bin = root / "bin"
            fake_bin.mkdir()
            aside = fake_bin / "aside"
            aside.write_text("#!/bin/sh\nexit 1\n")
            aside.chmod(0o755)
            marker = root / "chrome-invoked"
            chrome = fake_bin / "google-chrome"
            chrome.write_text(
                "#!/bin/sh\nprintf '%s\\n' invoked > \"$CHROME_MARKER\"\n"
                "printf '%s\\n' '<title>Example Domain</title>'\n"
            )
            chrome.chmod(0o755)
            mktemp = fake_bin / "mktemp"
            mktemp.write_text("#!/bin/sh\nexit 77\n")
            mktemp.chmod(0o755)
            claude_home = root / "claude"
            resolver = claude_home / "skills/scratch-space/scripts/scratch-dir.sh"
            resolver.parent.mkdir(parents=True)
            resolver.write_text(f"#!/bin/sh\nprintf '%s\\n' {root / 'scratch'}\n")
            resolver.chmod(0o755)
            (root / "scratch").mkdir()
            result = subprocess.run(
                ["bash", str(script)],
                env={
                    **os.environ,
                    "PATH": f"{fake_bin}:/usr/bin:/bin",
                    "CLAUDE_HOME": str(claude_home),
                    "CHROME_MARKER": str(marker),
                },
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 77, result.stderr)
            self.assertIn("profile allocation failed", result.stderr)
            self.assertFalse(marker.exists(), "Chrome must not run after profile allocation failure")

if __name__ == "__main__":
    unittest.main()
