"""An undeclared peer must never look like a verified transport.

The iMessage bridge is the primary transport and it refuses to run without
``INSTINCT_IMSG_CONTACT``. That refusal is correct. What was wrong is what the
caller did next: ``probe`` swallowed the refusal and reported the WhatsApp
fallback's success as a plain signed-in verdict, so a caller could not tell

  * "iMessage is configured and the peer's chat exists"  from
  * "iMessage was never usable here, I answered on WhatsApp instead".

A peer-verdict watcher that reads that output cannot distinguish a transport
that verified the intended person from one that never looked. These tests pin
the distinction, and pin that the refusal is not a silent one.
"""

from __future__ import annotations

import json
import os
import platform
import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INSTINCT = ROOT / ".claude" / "skills" / "instinct"
SCRIPT = INSTINCT / "scripts" / "instinct.mjs"
BRIDGE = INSTINCT / "scripts" / "imsg-bridge.sh"
SKILL = INSTINCT / "SKILL.md"

# The bridge refuses to run off macOS at its own platform guard ("iMessage is
# macOS-only", exit 3) BEFORE it ever looks at the contact. That is correct
# behaviour, so the contact-refusal assertions only mean anything where iMessage
# can exist at all. CI runs these suite on Linux, where exit 3 is the right
# answer and exit 5 is unreachable -- skip rather than encode the wrong platform.
_IS_MACOS = platform.system() == "Darwin"
_PEER = "+15550100"  # used only on the --dry-run path, which never delivers
_MACOS_ONLY = unittest.skipUnless(
    _IS_MACOS, "iMessage bridge is macOS-only; its platform guard exits 3 first"
)

# Every inherited variable that could change behaviour under test.
_ENV_KEYS = (
    "INSTINCT_IMSG_CONTACT",
    "IMSG_CONTACT_HANDLE",
    "INSTINCT_IMSG_BRIDGE",
    "INSTINCT_TRANSPORT",
    "INSTINCT_CONTACT",
    "INSTINCT_READ_THEIRS",
    "IMSG_CHAT_DB",
)


def _clean_env(**overrides: str) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if k not in _ENV_KEYS}
    env.update(overrides)
    return env


def _bridge(verb: str, **overrides: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["/bin/bash", str(BRIDGE), verb],
        capture_output=True,
        text=True,
        env=_clean_env(**overrides),
        timeout=60,
        check=False,
    )


class UndeclaredPeerTest(unittest.TestCase):
    """The bridge fails closed; the docs must not supply a default."""

    @_MACOS_ONLY
    def test_bridge_refuses_probe_without_a_declared_peer(self) -> None:
        result = _bridge("probe")
        self.assertEqual(result.returncode, 5, result.stderr)
        self.assertIn("INSTINCT_IMSG_CONTACT", result.stderr)
        self.assertNotIn('"signed_in":true', result.stdout)

    @_MACOS_ONLY
    def test_bridge_refuses_read_without_a_declared_peer(self) -> None:
        result = _bridge("read")
        self.assertEqual(result.returncode, 5, result.stderr)
        self.assertIn("INSTINCT_IMSG_CONTACT", result.stderr)

    @_MACOS_ONLY
    def test_bridge_refuses_send_without_a_declared_peer(self) -> None:
        with tempfile_message("probe") as path:
            result = subprocess.run(
                ["/bin/bash", str(BRIDGE), "send", "--file", str(path)],
                capture_output=True,
                text=True,
                env=_clean_env(),
                timeout=60,
                check=False,
            )
        self.assertEqual(result.returncode, 5, result.stderr)
        self.assertIn("INSTINCT_IMSG_CONTACT", result.stderr)

    def test_compat_alias_alone_is_still_a_declaration(self) -> None:
        """IMSG_CONTACT_HANDLE is an accepted alias, not a second default."""
        bridge_text = BRIDGE.read_text(encoding="utf-8")
        self.assertIn("IMSG_CONTACT_HANDLE", bridge_text)
        # The alias must be an alternative *source*, never a fallback value.
        self.assertRegex(
            bridge_text,
            r'CONTACT_HANDLE="\$\{INSTINCT_IMSG_CONTACT:-\$\{IMSG_CONTACT_HANDLE:-\}\}"',
        )


class NoHardcodedPeerTest(unittest.TestCase):
    """A default peer is indistinguishable from a declared one."""

    def test_bridge_has_no_default_handle(self) -> None:
        text = BRIDGE.read_text(encoding="utf-8")
        # The alias form is legitimate: INSTINCT_IMSG_CONTACT first, then
        # IMSG_CONTACT_HANDLE, then nothing. What must never appear is a literal
        # handle in either slot, because a default is indistinguishable from a
        # declaration and can point at anyone.
        assignment = re.search(
            r'CONTACT_HANDLE="\$\{INSTINCT_IMSG_CONTACT:-(.*?)\}"\s*$',
            text,
            re.MULTILINE,
        )
        self.assertIsNotNone(assignment, "CONTACT_HANDLE assignment not found")
        inner = assignment.group(1)
        self.assertIn("${IMSG_CONTACT_HANDLE:-}", inner)
        # No digits or @ in the whole assignment: that would be a literal handle.
        self.assertNotRegex(inner, r"[0-9]|@")

    def test_skill_documents_no_default_peer(self) -> None:
        text = SKILL.read_text(encoding="utf-8")
        self.assertNotRegex(
            text,
            r"INSTINCT_IMSG_CONTACT[^\n|]*\|[^\n|]*\+?1?[0-9]{7,}",
            "SKILL.md must not document a default handle for INSTINCT_IMSG_CONTACT",
        )


class ProbeDistinguishesFallbackTest(unittest.TestCase):
    """A probe answered by a fallback is not an iMessage verification."""

    def test_probe_source_reports_which_transport_answered(self) -> None:
        source = SCRIPT.read_text(encoding="utf-8")
        # The WhatsApp fallback path must emit a transport marker, so a caller
        # reading stdout can never mistake it for the iMessage primary.
        self.assertIn("transport", source)
        self.assertRegex(
            source,
            r"transport:\s*['\"]whatsapp['\"]|transport=whatsapp",
            "the WhatsApp fallback must identify itself as the transport that answered",
        )

    def test_probe_source_makes_the_imessage_refusal_visible(self) -> None:
        source = SCRIPT.read_text(encoding="utf-8")
        # The refusal reason must reach stderr rather than being swallowed.
        self.assertRegex(
            source,
            r"imessage probe failed rc=",
            "a failed iMessage probe must be reported, not silently replaced",
        )


class DryRunTest(unittest.TestCase):
    """Proving the wire must never require nominating a real recipient."""

    @_MACOS_ONLY
    def test_dry_run_stops_before_delivery_and_says_so(self) -> None:
        """--dry-run must be a real CLI flag that short-circuits before sending.

        Passing "--dry-run" through _bridge's env overrides would set a bogus
        environment variable and run a plain `send`, whose only observable is an
        unrelated exit 2 ("send requires --file"). That passes even if the flag
        were deleted, so it proves nothing. This passes the real flag and asserts
        the bridge's own dry-run marker, which only exists on the no-delivery path.
        """
        peer = os.environ.get("INSTINCT_TEST_PEER_HANDLE", "")
        if not peer:
            self.skipTest(
                "set INSTINCT_TEST_PEER_HANDLE to a handle with a real chat row; the "
                "bridge resolves the stored chat BEFORE the dry-run arm, so a synthetic "
                "handle exits 5 and never reaches the marker"
            )
        with tempfile_message("dry run probe") as path:
            result = subprocess.run(
                ["/bin/bash", str(BRIDGE), "send", "--file", str(path), "--dry-run"],
                capture_output=True,
                text=True,
                env=_clean_env(INSTINCT_IMSG_CONTACT=peer),
                timeout=60,
                check=False,
            )
        # The marker is emitted by the --dry-run arm and nowhere else.
        self.assertIn("dry-run: would send", result.stderr)
        self.assertIn("no message delivered", result.stderr)
        # And it must NOT be the unrelated missing-file error.
        self.assertNotIn("requires --file", result.stderr)

    def test_dry_run_flag_is_parsed_by_the_bridge(self) -> None:
        """The flag must exist in the option parser, not merely in docs."""
        text = BRIDGE.read_text(encoding="utf-8")
        self.assertRegex(
            text,
            r"--dry-run\).*DRY_RUN=1",
            "--dry-run must set DRY_RUN=1 in the bridge option parser",
        )
        # And the value must be initialised before any send reads it, or `set -u`
        # aborts a real send for callers who never exported it.
        self.assertRegex(
            text, r"(?m)^DRY_RUN=0$", "DRY_RUN must default to 0"
        )

    @_MACOS_ONLY
    def test_dry_run_refuses_an_undeclared_peer(self) -> None:
        """A dry run must not bypass the declared-peer requirement."""
        with tempfile_message("dry run probe") as path:
            result = subprocess.run(
                ["/bin/bash", str(BRIDGE), "send", "--file", str(path), "--dry-run"],
                capture_output=True,
                text=True,
                env=_clean_env(),
                timeout=60,
                check=False,
            )
        self.assertEqual(result.returncode, 5, result.stderr)
        self.assertIn("INSTINCT_IMSG_CONTACT", result.stderr)

    def test_skill_documents_dry_run(self) -> None:
        text = SKILL.read_text(encoding="utf-8")
        self.assertIn("--dry-run", text)
        self.assertIn("Never test the transport by sending to somebody", text)


class tempfile_message:  # noqa: N801 - used as a context manager, not a class
    """Write a throwaway message file for send-path tests."""

    def __init__(self, text: str) -> None:
        self._text = text

    def __enter__(self) -> Path:
        import tempfile

        handle = tempfile.NamedTemporaryFile(
            "w", suffix=".txt", delete=False, encoding="utf-8"
        )
        handle.write(self._text)
        handle.close()
        self._path = Path(handle.name)
        return self._path

    def __exit__(self, *_exc: object) -> None:
        self._path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
