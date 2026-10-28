import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
UI_DOC = ROOT / ".claude/skills/ui-video-evidence/SKILL.md"
WEB_SCRIPT = ROOT / ".claude/skills/web-advice/scripts/e2e_smoke.sh"
CAPTION_DOC = ROOT / ".claude/skills/video-caption/SKILL.md"


def code_block(document: Path | str, marker: str, start_at: int = 0) -> str:
    content = document.read_text() if isinstance(document, Path) else document
    start = content.index(marker, start_at)
    end = content.index("```", start)
    return content[start:end]


class MediaEmptyResolverTests(unittest.TestCase):
    def run_block(self, block: str, resolver_body: str, *, web_script: bool = False):
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
            for command in ("mktemp", "ffmpeg", "google-chrome", "chromium", "chromium-browser"):
                stub = fake_bin / command
                stub.write_text(f"#!/bin/sh\nprintf called > {marker}\nexit 99\n")
                stub.chmod(0o755)
            result = subprocess.run(
                ["bash", str(WEB_SCRIPT)] if web_script else ["bash", "-c", block],
                env={
                    **os.environ,
                    "HOME": str(home),
                    "CLAUDE_HOME": str(home / ".claude"),
                    "PATH": f"{fake_bin}:/usr/bin:/bin",
                },
                capture_output=True,
                text=True,
                check=False,
            )
            downstream_called = marker.exists()
            allocated_names = tuple(
                path.name for path in root.rglob("*")
                if path.name.startswith(("evidence_archive", "web-advice-chrome-smoke", "video-frames"))
            )
            return result, downstream_called, allocated_names

    def test_all_media_allocators_fail_closed_on_resolver_error_or_empty_output(self):
        ui_content = UI_DOC.read_text()
        caption_content = CAPTION_DOC.read_text()
        blocks = (
            ("ui-archive", code_block(ui_content, 'archive_scratch="')),
            (
                "caption-frames",
                code_block(caption_content, 'scratch_tmp="', caption_content.index("## 2. Extract frames")),
            ),
            ("web-profile", None),
        )
        for label, resolver_body in (
            ("resolver-error", "#!/bin/sh\necho unavailable >&2\nexit 75\n"),
            ("empty-output", "#!/bin/sh\nprintf '\\n'\nexit 0\n"),
        ):
            for name, block in blocks:
                with self.subTest(case=f"{name}-{label}"):
                    result, downstream_called, allocated_names = self.run_block(
                        block or "", resolver_body, web_script=block is None
                    )
                    self.assertEqual(result.returncode, 75, result.stderr)
                    self.assertFalse(downstream_called)
                    self.assertEqual(allocated_names, ())
