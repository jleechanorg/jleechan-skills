import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
DOCS = (
    ROOT / ".claude/skills/tmux-video-evidence/SKILL.md",
    ROOT / ".claude/skills/evidence-standards/tmux-video-evidence.md",
)
RESOLVER = '~/.claude/skills/scratch-space/scripts/scratch-dir.sh tmp'


def recording_block(document: Path) -> str:
    content = document.read_text()
    start = content.index(f'SCRATCH_TMP="$({RESOLVER})"', content.index("## Recording"))
    end = content.index("```", start)
    return content[start:end]


class TmuxScratchFailClosedTests(unittest.TestCase):
    def run_recording_block(self, document: Path, resolver_body: str):
        with tempfile.TemporaryDirectory(dir="/var/tmp") as directory:
            root = Path(directory)
            home = root / "home"
            resolver = home / ".claude/skills/scratch-space/scripts/scratch-dir.sh"
            resolver.parent.mkdir(parents=True)
            resolver.write_text(resolver_body)
            resolver.chmod(0o755)
            fake_bin = root / "bin"
            fake_bin.mkdir()
            marker = root / "downstream-called"
            for command in ("asciinema", "agg", "ffmpeg"):
                stub = fake_bin / command
                stub.write_text(f"#!/bin/sh\nprintf called > {marker}\nexit 99\n")
                stub.chmod(0o755)
            result = subprocess.run(
                ["bash", "-c", recording_block(document)],
                env={
                    **os.environ,
                    "HOME": str(home),
                    "PATH": f"{fake_bin}:/usr/bin:/bin",
                    "WORK_NAME": "tmux-failure-fixture",
                },
                capture_output=True,
                text=True,
                check=False,
            )
            downstream_called = marker.exists()
            media_created = tuple(
                (root / f"tmux-failure-fixture{suffix}").exists()
                for suffix in (".cast", ".gif", ".mp4")
            )
            return result, downstream_called, media_created

    def test_recording_blocks_fail_before_downstream_commands_on_resolver_error(self):
        for document in DOCS:
            with self.subTest(document=document.name):
                result, downstream_called, media_created = self.run_recording_block(
                    document, "#!/bin/sh\necho resolver-failed >&2\nexit 75\n"
                )
                self.assertEqual(result.returncode, 75, result.stderr)
                self.assertIn("refusing recording", result.stderr)
                self.assertFalse(downstream_called)
                self.assertEqual(media_created, (False, False, False))

    def test_recording_blocks_fail_before_downstream_commands_on_empty_path(self):
        for document in DOCS:
            with self.subTest(document=document.name):
                result, downstream_called, media_created = self.run_recording_block(
                    document, "#!/bin/sh\nprintf '\\n'\nexit 0\n"
                )
                self.assertEqual(result.returncode, 75, result.stderr)
                self.assertIn("empty path", result.stderr)
                self.assertFalse(downstream_called)
                self.assertEqual(media_created, (False, False, False))
