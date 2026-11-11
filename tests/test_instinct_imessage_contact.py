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
import tempfile
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


class SymlinkedInstallTest(unittest.TestCase):
    """An installed copy is a symlink; it must still run the CLI.

    import.meta.url reports the path the module was LOADED from, which for an
    installed skill is the link, not the target. Comparing that raw against
    argv[1] failed, so the module exported without running the CLI and printed
    nothing while exiting 0 — a probe or send that looked successful and did
    nothing at all.
    """

    def test_symlinked_invocation_still_prints_whoami(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            link = Path(tmp) / "instinct-link.mjs"
            link.symlink_to(SCRIPT)
            result = subprocess.run(
                ["node", str(link), "whoami"],
                capture_output=True,
                text=True,
                env=_clean_env(),
                timeout=120,
                check=False,
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(
            result.stdout.strip(),
            "a symlinked invocation printed nothing; the entry-point check did not "
            "resolve the link",
        )
        self.assertIn("transport_order", result.stdout)


class BubbleAttributionTest(unittest.TestCase):
    """Our own text must never be attributed to the peer.

    WhatsApp re-emits one long message as several nested nodes sharing a data-id.
    Only the FIRST carries the real sender label; continuations carry garbage like
    "1.". Truncating the node list before deduplication keeps the tail (garbage
    labels), so an outgoing message — including a literal "VERDICT: PASS" string a
    watcher greps for — was attributed to the peer.
    """

    NODES = [
        {"meta": "[12:00, 11/10/2026] Me: ", "text": "my outgoing VERDICT: PASS", "id": "A"},
        {"meta": "[12:00, 11/10/2026] 1. ", "text": "continuation of my own text", "id": "A"},
    ]

    def test_first_node_wins_attribution(self) -> None:
        script = (
            "const m = await import(process.argv[1]);"
            f"const n = {self.NODES!r};"
            "process.stdout.write(JSON.stringify(m.reduceBubbles(n)));"
        )
        result = subprocess.run(
            ["node", "--input-type=module", "-e", script, str(SCRIPT)],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        bubbles = json.loads(result.stdout.strip().splitlines()[-1])
        self.assertEqual(len(bubbles), 1, "continuation nodes must collapse")
        self.assertEqual(bubbles[0]["sender"], "Me")

    def test_read_messages_does_not_truncate_before_dedup(self) -> None:
        """The raw node list must be deduped before any limit is applied.

        Truncating inside the page evaluate kept only the tail continuation nodes,
        whose sender label is garbage, so the real sender was lost and our own
        outgoing text was attributed to the peer. This is the actual defect; the
        reduceBubbles behaviour was always correct.
        """
        source = SCRIPT.read_text(encoding="utf-8")
        # The evaluate must not slice; the slice belongs after reduceBubbles.
        self.assertNotIn(
            "return out.slice(-lim)",
            source,
            "readMessages truncates the raw node list before deduplication",
        )
        self.assertIn(
            "reduceBubbles(raw).slice(-limit)",
            source,
            "the limit must be applied AFTER reduceBubbles",
        )

    def test_slicing_after_dedup_preserves_attribution(self) -> None:
        """Dedup must happen before truncation, or the sender label is lost."""
        script = (
            "const m = await import(process.argv[1]);"
            f"const n = {self.NODES!r};"
            "const one = m.reduceBubbles(n).slice(-1);"
            "process.stdout.write(JSON.stringify(one));"
        )
        result = subprocess.run(
            ["node", "--input-type=module", "-e", script, str(SCRIPT)],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        one = json.loads(result.stdout.strip().splitlines()[-1])
        self.assertEqual(len(one), 1)
        self.assertEqual(
            one[0]["sender"],
            "Me",
            "slicing before dedup loses the real sender and attributes our own "
            "text to the peer",
        )


class CollapsedBubbleExpansionTest(unittest.TestCase):
    """A collapsed bubble must be expanded before its text is read.

    WhatsApp renders a long message as a short visible prefix followed by a
    "… Read more" caption button. The hidden remainder is NOT in the DOM:
    ``innerText`` and ``textContent`` measure the same length, so the text is
    not merely visually clipped, it is absent until the button is clicked.

    Before the fix ``readMessages`` scraped the nodes directly, so every bubble
    over roughly 700 characters came back ending in "… Read more". A reply whose
    ``VERDICT: PASS`` line sat at the end therefore read as *absent* to the
    verdict-grepping callers this skill exists to serve — the failure was silent,
    because the truncated text is well-formed and simply stops early.
    """

    SCRIPT_SRC = SCRIPT.read_text(encoding="utf-8")

    def test_read_messages_clicks_the_read_more_button(self) -> None:
        """The expander must target the real caption button selector."""
        self.assertIn(
            'caption-read-more-button',
            self.SCRIPT_SRC,
            "readMessages no longer references the read-more caption button, so a "
            "collapsed bubble is read truncated",
        )

    def test_expansion_happens_before_the_nodes_are_scraped(self) -> None:
        """Click first, scrape second. Order is the whole fix.

        If the expansion runs after the scrape, the nodes are already truncated
        and clicking is pointless.
        """
        rm_at = self.SCRIPT_SRC.find("async function readMessages")
        self.assertGreater(rm_at, -1, "readMessages is gone")
        # Anchor on the actual locator CALL, not on the bare selector string: the
        # selector also appears in the comment explaining it, and matching that
        # would only prove the comment exists.
        expand_at = self.SCRIPT_SRC.find(
            "caption-read-more-button", rm_at
        )
        scrape_at = self.SCRIPT_SRC.find(
            "querySelectorAll('[data-pre-plain-text]')", rm_at
        )
        self.assertGreater(expand_at, -1, "no read-more expansion in the script")
        self.assertGreater(scrape_at, -1, "no bubble scrape in the script")
        self.assertLess(
            expand_at,
            scrape_at,
            "the read-more expansion must run BEFORE the bubbles are scraped",
        )

    def test_read_messages_still_dedupes_after_scraping(self) -> None:
        """The expansion must not have replaced the attribution fix."""
        self.assertIn(
            "reduceBubbles(raw).slice(-limit)",
            self.SCRIPT_SRC,
            "readMessages must still dedupe before applying the limit",
        )

    def test_expansion_is_skipped_when_nothing_is_collapsed(self) -> None:
        """No collapsed bubbles must mean no click, so short reads stay cheap.

        The count is taken first and the click is guarded by it; an unconditional
        click sequence would pay a round trip on every read.
        """
        idx = self.SCRIPT_SRC.find("caption-read-more-button")
        window = self.SCRIPT_SRC[idx : idx + 700]
        self.assertIn(
            "if (collapsed > 0)",
            window,
            "the expansion must be conditional on at least one collapsed bubble",
        )
