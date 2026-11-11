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

    def test_read_messages_dedupes_before_applying_the_limit(self) -> None:
        """The limit must be applied AFTER deduplication, not before.

        Truncating the raw node list kept only the tail continuation nodes, whose
        sender label is garbage ("1."), so the real sender was lost and our own
        outgoing text was attributed to the peer.

        Driven behaviourally: with limit 1 the single returned bubble must still be
        the one carrying the real sender label. Slicing the raw list first would
        return the continuation node instead.
        """
        script = (
            "const mod = await import(process.argv[1]);"
            "const nodes = ["
            '  { meta: "[12:00, 11/10/2026] Me: ", text: "my outgoing VERDICT: PASS", id: "A" },'
            '  { meta: "[12:00, 11/10/2026] 1. ", text: "continuation of my text", id: "A" }'
            "];"
            "const page = {"
            "  locator: () => ({ count: async () => 0, evaluateAll: async () => {} }),"
            "  waitForTimeout: async () => {},"
            "  evaluate: async () => nodes,"
            "};"
            "const out = await mod.readMessages(page, 1);"
            'process.stdout.write("__RESULT__" + JSON.stringify(out));'
        )
        result = subprocess.run(
            ["node", "--input-type=module", "-e", script, str(SCRIPT)],
            capture_output=True,
            text=True,
            env=_clean_env(),
            timeout=120,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        line = next(
            (l for l in result.stdout.splitlines() if l.startswith("__RESULT__")), None
        )
        self.assertIsNotNone(line, f"harness produced no result: {result.stdout!r}")
        out = json.loads(line[len("__RESULT__") :])
        self.assertEqual(len(out), 1, "limit 1 must return exactly one message")
        self.assertEqual(
            out[0]["sender"],
            "Me",
            "slicing before dedup keeps the tail continuation node (garbage label) "
            "and attributes our own text to the peer",
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
    """A collapsed bubble must be expanded BEFORE its text is read.

    WhatsApp renders a long message as a short prefix plus a "… Read more" caption
    button. The hidden remainder is NOT in the DOM until that button is clicked:
    innerText and textContent measure the same length, so the text is absent rather
    than merely clipped.

    This drives the real readMessages() with a fake page, because the user-visible
    failure is the returned text, not the shape of the source. The fake models one
    fact: until the expander runs, a long bubble reports truncated text.
    """

    # The fake records the selector readMessages asked for, and yields truncated
    # text unless a click already happened on that selector.
    HARNESS = """
const mod = await import(process.argv[1]);
const collapsedCount = Number(process.env.FAKE_COLLAPSED ?? "2");
const clicks = [];
const selectors = [];
const nodes = [
  { meta: "[12:00, 11/10/2026] Peer: ", text: "long reply ending in VERDICT: PASS", id: "A" },
];
let expanded = false;
const page = {
  locator(sel) {
    selectors.push(sel);
    return {
      count: async () => (expanded ? 0 : collapsedCount),
      evaluateAll: async (fn) => {
        fn(Array.from({ length: collapsedCount }, () => ({ click: () => { clicks.push(sel); expanded = true; } })));
      },
    };
  },
  async waitForTimeout() {},
  async evaluate() {
    return nodes.map((n) => ({
      ...n,
      text: expanded ? n.text : n.text + " … Read more",
    }));
  },
};
const out = await mod.readMessages(page, 5);
process.stdout.write("__RESULT__" + JSON.stringify({ clicks: clicks.length, selectors, out }));
"""

    def _run(self, **overrides: str) -> dict:
        result = subprocess.run(
            ["node", "--input-type=module", "-e", self.HARNESS, str(SCRIPT)],
            capture_output=True,
            text=True,
            env=_clean_env(**overrides),
            timeout=120,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        marker = "__RESULT__"
        line = next(
            (l for l in result.stdout.splitlines() if l.startswith(marker)), None
        )
        self.assertIsNotNone(line, f"harness produced no result: {result.stdout!r}")
        return json.loads(line[len(marker) :])

    def test_collapsed_bubbles_are_expanded_before_text_is_read(self) -> None:
        payload = self._run()
        self.assertEqual(
            payload["clicks"], 2, "every collapsed bubble must be clicked before the read"
        )
        # Assert the content, not just the loop: an empty result would otherwise
        # pass without checking anything.
        self.assertEqual(len(payload["out"]), 1, "the read returned no bubbles")
        for bubble in payload["out"]:
            self.assertNotIn(
                "Read more",
                bubble["text"],
                "a truncated bubble was returned; the expansion did not run before "
                "the scrape, so a reply ending in VERDICT reads as absent",
            )
            self.assertIn("VERDICT: PASS", bubble["text"])

    def test_expander_selects_the_read_more_caption_button(self) -> None:
        """The click must target the real caption button, scoped to the open chat.

        A typo'd testid matches nothing in WhatsApp, so the fix would silently do
        nothing while every other test still passed. The selector is a literal token
        the program hands to a browser API, so pinning it is mechanical, not prose.
        """
        payload = self._run()
        self.assertTrue(payload["selectors"], "readMessages queried no selector")
        for sel in payload["selectors"]:
            self.assertIn(
                'data-testid="caption-read-more-button"',
                sel,
                f"unexpected expander selector {sel!r}",
            )
            # Require scoping as a PREFIX, not a substring: "#main" appearing anywhere
            # would also pass for an unscoped or oddly-composed selector.
            self.assertTrue(
                sel.lstrip().startswith("#main "),
                f"expander selector {sel!r} is not scoped to the open conversation; a "
                "page-wide match could click another chat's button",
            )

    def test_warning_fires_only_on_the_real_truncation_marker(self) -> None:
        """A message that merely ends in the words "read more" must not warn.

        The warning exists so silent truncation becomes loud. If it fired on
        ordinary prose, callers would learn to ignore it - so the pattern must
        require the ellipsis WhatsApp actually renders.
        """
        script = """
const mod = await import(process.argv[1]);
const text = process.env.FAKE_TEXT;
let warned = false;
const write = process.stderr.write.bind(process.stderr);
process.stderr.write = (s) => { warned = true; return true; };
const page = {
  locator: () => ({ count: async () => 0, evaluateAll: async () => {} }),
  waitForTimeout: async () => {},
  evaluate: async () => [{ meta: "[T] Peer: ", text, id: "A" }],
};
await mod.readMessages(page, 5, { warnIfTruncated: true });
process.stderr.write = write;
process.stdout.write("__RESULT__" + JSON.stringify({ warned }));
"""
        cases = [
            ("prose ending in the words", "I will read more", False),
            ("real marker with ellipsis", "long reply\u2026 Read more", True),
            ("prose mid-sentence", "please read more carefully next time", False),
        ]
        for name, text, expect in cases:
            with self.subTest(name):
                result = subprocess.run(
                    ["node", "--input-type=module", "-e", script, str(SCRIPT)],
                    capture_output=True,
                    text=True,
                    env=_clean_env(FAKE_TEXT=text),
                    timeout=120,
                    check=False,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                line = next(
                    (l for l in result.stdout.splitlines() if l.startswith("__RESULT__")),
                    None,
                )
                self.assertIsNotNone(line, result.stdout)
                warned = json.loads(line[len("__RESULT__") :])["warned"]
                self.assertEqual(warned, expect, f"warning mismatch for {name!r}")

    def test_warning_is_silent_for_callers_that_do_not_opt_in(self) -> None:
        """send/open read a tail for display; they must not emit the read warning.

        The warning exists for callers that grep bubble text for a verdict. Emitting
        it from send's 3-bubble tail would add unrelated stderr noise to a success
        path and dilute the signal.
        """
        script = """
const mod = await import(process.argv[1]);
let warned = false;
const write = process.stderr.write.bind(process.stderr);
process.stderr.write = (s) => { warned = true; return true; };
const page = {
  locator: () => ({ count: async () => 0, evaluateAll: async () => {} }),
  waitForTimeout: async () => {},
  evaluate: async () => [{ meta: "[T] Peer: ", text: "tail\u2026 Read more", id: "A" }],
};
await mod.readMessages(page, 3);          // no opt-in, as send/open call it
process.stderr.write = write;
process.stdout.write("__RESULT__" + JSON.stringify({ warned }));
"""
        result = subprocess.run(
            ["node", "--input-type=module", "-e", script, str(SCRIPT)],
            capture_output=True,
            text=True,
            env=_clean_env(),
            timeout=120,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        line = next(
            (l for l in result.stdout.splitlines() if l.startswith("__RESULT__")), None
        )
        self.assertIsNotNone(line, result.stdout)
        self.assertFalse(
            json.loads(line[len("__RESULT__") :])["warned"],
            "a non-opting caller emitted the truncation warning",
        )

    def test_read_with_nothing_collapsed_skips_the_click(self) -> None:
        """No collapsed bubbles must mean no click, so short reads stay cheap."""
        payload = self._run(FAKE_COLLAPSED="0")
        self.assertEqual(payload["clicks"], 0, "clicked with nothing collapsed")
        self.assertEqual(len(payload["out"]), 1)
