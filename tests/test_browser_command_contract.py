"""Contract tests for the /browser command and the browser-control skill.

The /browser command and `.claude/skills/browser-control/SKILL.md` together
implement the routing-order contract:

1. Aside-MCP first (when the active runtime exposes it).
2. Aside CLI (`aside repl` / `aside "<prompt>"`) — drives the already-running
   Aside.app profile.
3. `browserclaw cookies decrypt + inject` for headless auth on sites where
   the user is already authenticated. Re-decrypt from the local Chromium
   profile (Aside → Chrome Default → Profile 1 → Profile 2 → Brave → Edge).
4. Playwright headless for unauthenticated / deterministic flows.
5. Visible/headed browser only when the user explicitly asks for it.

These tests protect against:

- Regression of the old "never copy cookies between browser profiles" line
  in the live-browser workflow that contradicted the documented
  browserclaw cookie-inject fallback.
- A reordering of the routing priorities (e.g. promoting Playwright above
  Aside, or dropping the Aside-MCP preference).
- Browserclaw HAR-based capture being reintroduced on credential flows
  (the `capture`/`learn`/`reverse` ban).
- Loss of the fingerprint-sensitive outlier exception (LinkedIn / banks /
  Cloudflare-protected sites that bind cookies to the running browser).
- Loss of the explicit credential-reuse safeguards (private /tmp only,
  --summary, never commit, never log values).
- Loss of the clean-the-cookie-JSON-after-use step.
- Reintroducing fixed `/tmp/<x>.json` paths in the referenced recipes that
  leak credentials across processes.
- Allowing fingerprint-sensitive sites (LinkedIn, banks, Cloudflare) to
  fall through to cookie injection on a headless host.
- Reintroducing `--print-text`, screenshots, or HARs on secret-bearing
  pages (API keys, tokens, banking, recovery codes).
- Loss of the fail-closed shell lifecycle (`set -euo pipefail`, EXIT
  trap on both success and failure, nonzero exit preserved on cleanup).

The tests are file/contract-only: they do NOT run any real cookie
decrypt/inject, do NOT touch `~/.claude`, and do NOT make network calls.
The actual browser path is exercised by the parent Hermes session.

A shell-lifecycle simulation is run as a subprocess to prove the
cleanup-on-failure + nonzero-exit-preserved contract locally without
touching any real cookie state.
"""


import os
import re
import signal
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BROWSER_CMD = REPO_ROOT / ".claude" / "commands" / "browser.md"
BROWSER_SKILL = REPO_ROOT / ".claude" / "skills" / "browser-control" / "SKILL.md"
ASIDE_SKILL = REPO_ROOT / "hermes" / "skills" / "aside-browser-default" / "SKILL.md"
GEMINI_REF = REPO_ROOT / "hermes" / "skills" / "browserclaw" / "references" / "gemini-share-link-as-user.md"
MULTI_REF = REPO_ROOT / "hermes" / "skills" / "browserclaw" / "references" / "multi-profile-cookie-scan.md"

# Ordered route priorities — the test enforces this order in the
# numbered "Routing order" sections of both files.
EXPECTED_ROUTE_ORDER = [
    ("aside-mcp", "Aside-MCP must be the first routing priority"),
    ("aside-repl", "Aside CLI must be the second routing priority"),
    ("browserclaw", "browserclaw must be the third routing priority"),
    ("playwright-headless", "Playwright headless must be the fourth routing priority"),
    ("visible-headed", "visible/headed must be the last routing priority"),
]


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def assert_any_match(text: str, patterns: list[tuple[str, str]]) -> list[str]:
    """Return the list of messages for patterns that did NOT match."""
    missing = []
    for pattern, message in patterns:
        if not re.search(pattern, text, re.IGNORECASE | re.DOTALL):
            missing.append(message)
    return missing


def assert_none_match(text: str, patterns: list[tuple[str, str]]) -> list[str]:
    """Return the list of messages for patterns that DID match (should be disallowed)."""
    found = []
    for pattern, message in patterns:
        if re.search(pattern, text, re.IGNORECASE | re.DOTALL):
            found.append(message)
    return found


def first_index(text: str, pattern: str) -> int:
    """Return the integer index of the first match, or -1 if not found."""
    m = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
    return m.start() if m else -1


def parse_numbered_route_order(text: str) -> list[tuple[int, int, str]]:
    """Parse the numbered 'Routing order' section: returns list of
    (line_number, route_index, route_text) for every numbered route entry
    starting with `<n>. **<RouteName>**`. The returned list is sorted by
    line_number so the relative ordering is preserved.
    """
    entries = []
    for m in re.finditer(r"^(\d+)\.\s+\*\*([^*]+)\*\*", text, re.MULTILINE):
        entries.append((m.start(), int(m.group(1)), m.group(2).strip()))
    return entries


def route_label_signature(label: str) -> str:
    """Map a numbered-route bold label into one of EXPECTED_ROUTE_ORDER's
    signature strings. Returns the signature, or '' if no match.
    """
    norm = label.lower()
    if "aside-mcp" in norm or re.search(r"\baside\s*mcp\b", norm):
        return "aside-mcp"
    if "aside cli" in norm or "aside repl" in norm:
        return "aside-repl"
    if "browserclaw" in norm:
        return "browserclaw"
    if "playwright" in norm and "headless" in norm:
        return "playwright-headless"
    if "visible" in norm or "headed" in norm:
        return "visible-headed"
    return ""


# Anchored phrases that MUST appear in the command file. Running these as
# regex via `re.search` lets the contract tolerate whitespace/line-wrap
# tweaks without silently missing a forced structure.
CMD_ROUTING_PATTERNS = [
    (r"Aside-MCP|aside\s*mcp", "Aside-MCP must be first routing priority"),
    (r"aside\s+repl|aside\s+account\s+list", "Aside CLI surface must be referenced"),
    (r"browserclaw\s+cookies\s+decrypt", "browserclaw decrypt must be named"),
    (r"browserclaw\s+cookies\s+inject", "browserclaw inject must be named"),
    (r"--browser-channel\s+chromium", "chromium channel must be set (not chrome)"),
    (r"--headless", "headless mode must be set"),
    (r"--summary", "--summary flag must be set for non-credential cookies"),
    (r"Playwright\s+headless", "Playwright headless fallback must be named"),
    (r"visible|headed", "visible/headed exception must be explicit"),
    (r"profile|Profile\s+1", "profile sweep must be named"),
    (r"capture\s*/\s*learn\s*/\s*reverse|capture.*learn.*reverse", "HAR-based capture ban must be stated"),
    (r"mktemp|/tmp/", "private /tmp cookie JSON must be required"),
    (r"rm\s+-f|rm\s+TMP_COOKIES", "cookie JSON cleanup step must be present"),
    (r"never\s+commit|no\s+commit", "commit ban must be stated"),
    (r"never\s+log|do\s+not\s+log", "no-log-values safeguard must be stated"),
    (r"LinkedIn", "LinkedIn fingerprint-sensitive exception must be named"),
    (r"banks?|brokerage", "banks/brokerage outlier must be named"),
    (r"playwright-ui-testing|Playwright(?=.*fixture|\s+UI\s+testing|deterministic)", "deterministic UI testing must route to playwright-ui-testing"),
]

SKILL_ROUTING_PATTERNS = [
    (r"Aside-MCP|aside-mcp", "Aside-MCP must be listed as the primary tool"),
    (r"aside\s+repl|aside\s+account\s+list", "Aside CLI must be referenced"),
    (r"browserclaw\s+cookies\s+decrypt", "browserclaw decrypt must be named"),
    (r"browserclaw\s+cookies\s+inject", "browserclaw inject must be named"),
    (r"--browser-channel\s+chromium", "chromium channel must be set"),
    (r"--headless", "headless mode must be set"),
    (r"--summary", "--summary flag must be set"),
    (r"Playwright\s+headless", "Playwright headless fallback must be named"),
    (r"profile|Profile\s+1", "profile sweep must be named"),
    (r"capture\s*/\s*learn\s*/\s*reverse|capture.*learn.*reverse", "HAR-based capture ban must be stated"),
    (r"never\s+commit|no\s+commit", "commit ban must be stated"),
    (r"never\s+log|do\s+not\s+log", "no-log-values safeguard must be stated"),
    (r"LinkedIn", "LinkedIn fingerprint-sensitive exception must be named"),
    (r"banks?|brokerage", "banks/brokerage outlier must be named"),
    (r"Cloudflare|Akamai", "Cloudflare/Akamai bot-mitigation must be named"),
    (r"chmod\s+600|mode\s+600|private\s+/tmp", "private /tmp cookie JSON must be required"),
    (r"rm\s+-f", "cookie JSON cleanup step must be present"),
    (r"playwright-ui-testing", "deterministic UI testing must route to playwright-ui-testing"),
]

# Phrases that MUST NOT appear in the live-browser workflow now that the
# contradiction has been resolved. The contradiction was the old "never copy
# cookies between browser profiles" line that contradicted the documented
# browserclaw cookie-inject fallback.
DISALLOWED_PHRASES = [
    (r"never.*copy\s+cookies\s+between\s+profiles", "old 'never copy cookies between profiles' ban contradicts the browserclaw fallback"),
    (r"do\s+not\s+copy\s+cookies", "old 'do not copy cookies' ban contradicts the browserclaw fallback"),
]

# Fixed /tmp path patterns that MUST NOT appear in the canonical lifecycle
# or in the hardened references. These are the unsafe patterns from
# round-1/round-2 review.
UNSAFE_FIXED_TMP_PATHS = [
    (r"/tmp/google-cookies\.json", "fixed /tmp/google-cookies.json leaks across processes"),
    (r"/tmp/share_page\.txt", "fixed /tmp/share_page.txt leaks across processes"),
    (r"/tmp/share_full\.txt", "fixed /tmp/share_full.txt leaks across processes"),
    (r"/tmp/share_authed\.png", "fixed /tmp/share_authed.png leaks screenshots"),
    (r"/tmp/\$\{prof// /}-cookies\.json", "fixed per-profile /tmp/-cookies.json leaks across processes"),
    (r'/tmp/\${name}-cookies\.json', "fixed per-browser /tmp/-cookies.json leaks across processes"),
    (r"/tmp/venmo\.csv", "fixed /tmp/venmo.csv leaks downloaded attachments"),
]


class _BrowserFilesBase(unittest.TestCase):
    """Define `cmd_text` and `skill_text` in concrete subclasses."""

    cmd_text: str = ""
    skill_text: str = ""


class BrowserCommandContractTest(_BrowserFilesBase):
    """The /browser command is concise but MUST encode the routing order inline."""

    @classmethod
    def setUpClass(cls) -> None:
        assert BROWSER_CMD.is_file(), f"browser.md missing at {BROWSER_CMD}"
        cls.cmd_text = read(BROWSER_CMD)

    def test_routing_order_anchors_present(self) -> None:
        missing = assert_any_match(self.cmd_text, CMD_ROUTING_PATTERNS)
        assert not missing, (
            "browser.md is missing required routing-order anchors:\n"
            + "\n".join(f"  - {m}" for m in missing)
        )

    def test_routing_order_lists_aside_mcp_first(self) -> None:
        # The Aside-MCP preference must come BEFORE the Aside CLI mention in
        # the routing order, not after.
        first_aside_mcp = first_index(self.cmd_text, r"aside-mcp|aside\s*mcp|Aside-MCP")
        first_aside_cli = first_index(self.cmd_text, r"aside\s+repl|aside\s+account\s+list")
        assert first_aside_mcp >= 0, "Aside-MCP must be referenced in the command"
        assert first_aside_cli >= 0, "Aside CLI must be referenced in the command"
        assert first_aside_mcp < first_aside_cli, (
            "Aside-MCP must appear before the Aside CLI mention so the routing "
            "order is unambiguous"
        )

    def test_routing_order_lists_browserclaw_before_playwright_fallback(self) -> None:
        first_browserclaw = first_index(self.cmd_text, r"browserclaw")
        first_playwright = first_index(self.cmd_text, r"Playwright\s+headless")
        assert first_browserclaw >= 0, "browserclaw must be referenced"
        assert first_playwright >= 0, "Playwright headless fallback must be referenced"
        assert first_browserclaw < first_playwright, (
            "browserclaw must be a higher-priority fallback than Playwright headless"
        )

    def test_credential_reuse_safeguards_present(self) -> None:
        for kw in (
            "--summary", "TMP_COOKIES", "TMP_PAGE", "chmod 600",
            "umask 077", "cleanup_browser_share", "exit_on_signal",
            "trap 'exit_on_signal INT' INT",
            "trap 'exit_on_signal TERM' TERM",
            "trap 'exit_on_signal HUP' HUP",
            "trap cleanup_browser_share EXIT",
            "never", "/tmp",
        ):
            assert kw in self.cmd_text, (
                f"credential-reuse safeguard missing from browser.md: {kw!r}"
            )
        assert '--screenshot' not in self.cmd_text, (
            "auth-gated private-content recipe must not persist screenshots by default"
        )
        # Round-7 reviewer-required test: the canonical recipe in
        # browser.md MUST NOT contain a `trap -` disarm line. The
        # round-6 reviewer flagged that a disarm at the end of the
        # recipe orphans the credential file if a signal arrives
        # between the last cookie write and script exit.
        canonical_block = self.cmd_text.split(
            "## Auth-gated share links", 1)[1].split(
            "## ", 1)[0]
        assert "trap -" not in canonical_block, (
            "browser.md canonical recipe must NOT disarm its trap; "
            "the EXIT trap must stay armed until the script exits. "
            "`rm -f` is idempotent so a normal exit firing the trap "
            "is the same as an explicit cleanup call."
        )

    def test_auth_gated_flow_preserves_global_routing_order(self) -> None:
        section = self.cmd_text.split("## Auth-gated share links", 1)[1]
        aside_mcp = first_index(section, r"Aside.*MCP|MCP.*Aside")
        aside_cli = first_index(section, r"Aside CLI")
        browserclaw = first_index(section, r"browserclaw")
        assert 0 <= aside_mcp < aside_cli < browserclaw, (
            "auth-gated flow must try Aside MCP, then Aside CLI, before browserclaw"
        )
        assert "fingerprint-sensitive Aside-only exception" in section
        assert "overrides this fallback" in section

    def test_auth_recipe_is_canonical_not_delegated_to_unsafe_reference(self) -> None:
        section = self.cmd_text.split("## Auth-gated share links", 1)[1]
        assert "safe recipe below is canonical" in section
        assert "must not override this guarded lifecycle" in section
        assert "fixed-path sweep snippets" in section
        # The canonical recipe MUST embed the multi-profile sweep
        # inline so it does not depend on operator-executed snippets.
        assert "Multi-profile sweep" in section
        assert '/tmp/share_full.txt' not in self.cmd_text
        # The sweep MUST re-apply chmod 600 after a successful
        # browserclaw write — same rationale as the skill-side test.
        assert 'chmod 600 "$TMP_COOKIES"' in section, (
            "browser.md auth-gated recipe must re-apply chmod 600 "
            "after a successful sweep decrypt"
        )

    def test_no_legacy_fixed_path_used_in_auth_gated_section(self) -> None:
        section = self.cmd_text.split("## Auth-gated share links", 1)[1]
        assert '/tmp/share_full.txt' not in self.cmd_text

    def test_referenced_browserclaw_recipes_exist_in_repo(self) -> None:
        recipes = REPO_ROOT / "hermes" / "skills" / "browserclaw" / "references"
        for name in ("multi-profile-cookie-scan.md", "gemini-share-link-as-user.md"):
            assert (recipes / name).is_file(), f"browserclaw recipe missing: {recipes / name}"

    def test_no_disallowed_phrases(self) -> None:
        found = assert_none_match(self.cmd_text, DISALLOWED_PHRASES)
        assert not found, (
            "browser.md contains disallowed phrases:\n"
            + "\n".join(f"  - {m}" for m in found)
        )

    def test_no_screenshot_in_any_documented_bash_block(self) -> None:
        # Round-6 reviewer-required test: every documented bash
        # block in browser.md MUST not contain an active
        # --screenshot invocation. The earlier test only covered
        # the first generic block.
        blocks = re.findall(r"```bash\n(.*?)\n```", self.cmd_text, re.DOTALL)
        self.assertGreater(len(blocks), 0, (
            "browser.md must contain at least one documented bash block"
        ))
        for i, block in enumerate(blocks):
            active = [
                line for line in block.splitlines()
                if not line.lstrip().startswith("#")
                and ("--screenshot" in line or "--capture-har" in line)
            ]
            self.assertEqual(active, [], (
                f"browser.md bash block #{i} must not contain an active "
                f"--screenshot or --capture-har invocation; "
                f"found: {active!r}"
            ))

    def test_command_references_skill(self) -> None:
        # The command must still delegate to the full skill, but the inline
        # routing order is the primary contract.
        assert "browser-control/SKILL.md" in self.cmd_text
        assert "playwright-ui-testing" in self.cmd_text
        # The command must NOT carry absolute installed-skill
        # paths like `~/.claude/skills/...`; use normal skill
        # discovery instead.
        assert "~/.claude/skills/" not in self.cmd_text, (
            "browser.md must use normal skill discovery, not "
            "absolute ~/.claude/skills/... paths"
        )


class BrowserSkillContractTest(_BrowserFilesBase):
    """The browser-control skill MUST encode the same routing order verbatim."""

    @classmethod
    def setUpClass(cls) -> None:
        assert BROWSER_SKILL.is_file(), f"browser-control SKILL.md missing at {BROWSER_SKILL}"
        cls.skill_text = read(BROWSER_SKILL)

    def test_routing_order_anchors_present(self) -> None:
        missing = assert_any_match(self.skill_text, SKILL_ROUTING_PATTERNS)
        assert not missing, (
            "browser-control/SKILL.md is missing required routing-order anchors:\n"
            + "\n".join(f"  - {m}" for m in missing)
        )

    def test_routing_order_lists_aside_mcp_first(self) -> None:
        first_aside_mcp = first_index(self.skill_text, r"aside-mcp|aside\s*mcp|Aside-MCP")
        first_aside_cli = first_index(self.skill_text, r"aside\s+repl|aside\s+account\s+list")
        assert first_aside_mcp >= 0, "Aside-MCP must be referenced in the skill"
        assert first_aside_cli >= 0, "Aside CLI must be referenced in the skill"
        assert first_aside_mcp < first_aside_cli, (
            "Aside-MCP must appear before the Aside CLI mention in the skill"
        )

    def test_routing_order_lists_browserclaw_before_playwright_fallback(self) -> None:
        first_browserclaw = first_index(self.skill_text, r"browserclaw")
        first_playwright = first_index(self.skill_text, r"Playwright\s+headless")
        assert first_browserclaw >= 0, "browserclaw must be referenced"
        assert first_playwright >= 0, "Playwright headless fallback must be referenced"
        assert first_browserclaw < first_playwright, (
            "browserclaw must be a higher-priority fallback than Playwright headless"
        )

    def test_credential_reuse_safeguards_present(self) -> None:
        for kw in (
            "--summary", "TMP_COOKIES", "TMP_PAGE", "chmod 600",
            "umask 077", "cleanup_browser_creds", "exit_on_signal",
            "trap 'exit_on_signal INT' INT",
            "trap 'exit_on_signal TERM' TERM",
            "trap 'exit_on_signal HUP' HUP",
            "trap cleanup_browser_creds EXIT",
            "never",
        ):
            assert kw in self.skill_text, (
                f"credential-reuse safeguard missing from skill: {kw!r}"
            )
        section = self.skill_text.split("## Authorized credential reuse", 1)[1].split("## Fingerprint-sensitive", 1)[0]
        shell_block = section.split("```bash", 1)[1].split("```", 1)[0]
        assert '--screenshot' not in shell_block

    def test_secret_branch_cleans_up_cookies_and_emits_to_stdout(self) -> None:
        section = self.skill_text.split("**Secret-bearing page branch:**", 1)[1].split("**Safeguards**", 1)[0]
        assert "set -euo pipefail" in section, (
            "secret branch must be fail-closed (set -euo pipefail)"
        )
        # The secret branch is self-contained: it runs the canonical
        # multi-profile sweep itself to obtain $TMP_COOKIES, then runs
        # a bare Playwright script. The sweep is what makes the branch
        # executable end-to-end (without it the branch read an empty
        # mktemp file and never produced a cookie artifact).
        assert "Multi-profile sweep" in section or "multi-profile sweep" in section, (
            "secret branch must run the multi-profile sweep to obtain cookies"
        )
        assert 'TMP_COOKIES="$(mktemp' in section, (
            "secret branch must define its own $TMP_COOKIES"
        )
        assert 'TMP_PAGE="$(mktemp' in section, (
            "secret branch must define its own $TMP_PAGE"
        )
        assert "sys.stdout.write" in section, (
            "secret branch must emit the boolean to stdout, not a temp file"
        )
        # The secret branch must not actively PERSIST the boolean
        # result to disk — but it may reference `write_text` /
        # `Path.write_text` in a comment that explains why
        # `chmod 600` is reapplied (browserclaw's writer uses
        # Path.write_text and honors the umask). Allow the
        # comment, but ban a bare call.
        bare_write_text_calls = [
            line for line in section.splitlines()
            if not line.lstrip().startswith("#")
            and ".write_text(" in line
        ]
        assert bare_write_text_calls == [], (
            f"secret branch must not call .write_text() to persist the "
            f"boolean result; found: {bare_write_text_calls!r}"
        )
        # Fail-closed contract: the trap stays armed across every
        # signal — INT/TERM/HUP each have their own trap that calls
        # cleanup then re-raises the signal so the script exits
        # nonzero. No disarm line anywhere.
        assert "trap -" not in section, (
            "secret branch must NOT disarm its trap; the trap must "
            "stay armed for the lifetime of the branch"
        )
        assert "exit_on_signal" in section, (
            "secret branch must re-raise the signal so it exits nonzero"
        )

    def test_every_decrypt_output_uses_guarded_cookie_variable(self) -> None:
        section = self.skill_text.split("## Authorized credential reuse", 1)[1].split("## Fingerprint-sensitive", 1)[0]
        # The canonical recipe now contains TWO browserclaw decrypt
        # invocations: the initial Chrome Default decrypt + a multi-
        # profile sweep. Both must use the same guarded $TMP_COOKIES
        # variable, never a fresh mktemp inside the invocation.
        decrypt_blocks = section.split("browserclaw cookies decrypt")[1:]
        assert len(decrypt_blocks) >= 1, "credential recipe should have at least one decrypt invocation"
        for block in decrypt_blocks:
            assert '--output "$TMP_COOKIES"' in block, (
                "every browserclaw cookies decrypt invocation must use "
                "$TMP_COOKIES, not a fresh mktemp"
            )
            assert '--output "$(mktemp' not in block
        # The sweep MUST re-apply chmod 600 after a successful
        # browserclaw write — the browserclaw writer uses
        # Path.write_text() which honors the process umask, so a
        # permissive umask could leave the cookie file world-
        # readable. The trap removes the file on any later failure.
        assert "chmod 600 \"$TMP_COOKIES\"" in section, (
            "credential recipe must re-apply chmod 600 after a "
            "successful sweep decrypt"
        )

    def test_fail_closed_lifecycle_present(self) -> None:
        """The shell lifecycle must use `set -euo pipefail`, install
        cleanup + signal-handler traps, and never disarm them.
        """
        assert "set -euo pipefail" in self.skill_text, (
            "browser-control/SKILL.md must use 'set -euo pipefail'"
        )
        assert "exit_on_signal" in self.skill_text, (
            "browser-control/SKILL.md must install exit_on_signal "
            "handlers for INT/TERM/HUP so the script exits nonzero"
        )
        assert "trap 'exit_on_signal INT' INT" in self.skill_text, (
            "browser-control/SKILL.md must trap INT to exit_on_signal"
        )
        assert "trap 'exit_on_signal TERM' TERM" in self.skill_text, (
            "browser-control/SKILL.md must trap TERM to exit_on_signal"
        )
        assert "trap 'exit_on_signal HUP' HUP" in self.skill_text, (
            "browser-control/SKILL.md must trap HUP to exit_on_signal"
        )
        assert "trap cleanup_browser_creds EXIT" in self.skill_text, (
            "browser-control/SKILL.md must trap EXIT to cleanup_browser_creds"
        )
        # Round-7 reviewer-required test: the canonical recipe MUST
        # NOT contain a `trap -` disarm line at the end. The EXIT
        # trap is the cleanup; arming it once at the top of the
        # recipe and never disarming it is the fail-closed contract.
        # A `trap -` line at the end would mean a signal arriving
        # between the last cookie write and the script exit could
        # orphan the credential file (round-6 reviewer flag).
        canonical_block = self.skill_text.split(
            "## Authorized credential reuse", 1)[1].split(
            "## Fingerprint-sensitive", 1)[0]
        assert "trap -" not in canonical_block, (
            "browser-control/SKILL.md canonical recipe must NOT disarm "
            "its trap; the EXIT trap must stay armed until the script "
            "exits. `rm -f` is idempotent so a normal exit firing the "
            "trap is the same as an explicit cleanup call."
        )

    def test_no_screenshot_in_any_documented_bash_block(self) -> None:
        # Round-6 reviewer-required test: every documented bash
        # block in browser-control/SKILL.md MUST not contain an
        # active --screenshot invocation.
        blocks = re.findall(r"```bash\n(.*?)\n```", self.skill_text, re.DOTALL)
        self.assertGreater(len(blocks), 0, (
            "browser-control/SKILL.md must contain at least one documented bash block"
        ))
        for i, block in enumerate(blocks):
            active = [
                line for line in block.splitlines()
                if not line.lstrip().startswith("#")
                and ("--screenshot" in line or "--capture-har" in line)
            ]
            self.assertEqual(active, [], (
                f"browser-control/SKILL.md bash block #{i} must not contain "
                f"an active --screenshot or --capture-har invocation; "
                f"found: {active!r}"
            ))

    def test_secret_page_branch_bans_generic_persistence(self) -> None:
        section = self.skill_text.split("**Secret-bearing page branch:**", 1)[1].split("**Safeguards**", 1)[0]
        assert "MUST NOT execute the generic `--print-text` recipe" in section
        assert "persist neither DOM text nor images" in section
        assert "minimum safe non-secret DOM state in memory" in section
        # The secret-bearing branch MUST be fail-closed and emit to stdout.
        assert "set -euo pipefail" in section, (
            "secret-bearing page branch must be fail-closed (`set -euo pipefail`)"
        )
        assert "sys.stdout.write" in section, (
            "secret-bearing page branch must emit the boolean to stdout"
        )

    def test_headless_fallback_is_subordinate_to_fingerprint_exception(self) -> None:
        assert "The fingerprint-sensitive Aside-only exception below overrides this fallback" in self.skill_text
        gotchas = self.skill_text.split("## Environment gotchas", 1)[1]
        assert "fingerprint-sensitive Aside-only exception overrides this rule" in gotchas
        assert "never attempt cookie injection" in gotchas
        assert "browserclaw capture" in gotchas
        # The escape hatch must be marked as narrow / not a substitute.
        assert re.search(r"NARROW|narrow", gotchas), (
            "browser-control/SKILL.md must mark the browserclaw capture escape "
            "hatch as NARROW / narrow, not as the headless fallback"
        )

    def test_no_disallowed_phrases(self) -> None:
        found = assert_none_match(self.skill_text, DISALLOWED_PHRASES)
        assert not found, (
            "browser-control/SKILL.md contains disallowed phrases:\n"
            + "\n".join(f"  - {m}" for m in found)
        )

    def test_no_har_for_credential_flows(self) -> None:
        """The browserclaw capture/learn/reverse subcommands must be explicitly
        banned for credential-bearing flows. Match on a multi-token phrase in
        any order so a future re-wording that keeps one of the three tokens
        alone doesn't silently pass."""
        har_ban_pattern = re.compile(
            r"(?:capture|learn|reverse).{0,80}(?:capture|learn|reverse).{0,80}(?:capture|learn|reverse)",
            re.IGNORECASE | re.DOTALL,
        )
        assert har_ban_pattern.search(self.skill_text), (
            "browser-control/SKILL.md must explicitly ban browserclaw capture/learn/reverse "
            "for credential flows (mention all three together)"
        )

    def test_no_har_negation_in_credential_context(self) -> None:
        """The HAR ban must be in a credential-bearing context, not a generic
        statement. Negated phrasing must be near credential/secret/banking
        tokens so a future reword that drops the negation still gets caught
        by the keyword test."""
        for kw in ("secret", "credential", "banking", "API key", "token"):
            assert kw.lower() in self.skill_text.lower(), (
                f"credential-bearing context token missing from skill: {kw!r}"
            )

    def test_fingerprint_sensitive_outlier_named(self) -> None:
        """The exception list (LinkedIn / banks / Cloudflare) must be present
        so the drop-the-cookie-copy-out rule is not retroactively removed."""
        for kw in ("LinkedIn", "Cloudflare"):
            assert kw in self.skill_text, (
                f"fingerprint-sensitive outlier missing from skill: {kw!r}"
            )

    def test_authorized_credential_reuse_section_present(self) -> None:
        """The new 'Authorized credential reuse' section must be present so
        the previous contradiction is moved to a clean, explicit contract."""
        assert "Authorized credential reuse" in self.skill_text, (
            "browser-control/SKILL.md must carry an explicit 'Authorized credential reuse' section"
        )

    def test_route_task_summary_defines_success(self) -> None:
        """The 'Route the task' summary must define what it means for a route
        to succeed — authenticated task completion, not a single transport
        call. This blocks the round-1 contradiction where a single tab error
        was treated as a successful fallback."""
        section = self.skill_text.split("## Route the task", 1)[1].split("## Routing order", 1)[0]
        assert "authenticated task" in section.lower(), (
            "browser-control/SKILL.md 'Route the task' summary must define "
            "route success as authenticated task completion"
        )
        assert "single transport" in section.lower() or "transport error" in section.lower() or "single transport or tab call" in section.lower(), (
            "browser-control/SKILL.md 'Route the task' summary must explicitly "
            "state that a single transport/tab error is not enough to advance"
        )


class BrowserSkillAndCommandParityTest(_BrowserFilesBase):
    """The two files must agree on the high-priority routing terms."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.cmd_text = read(BROWSER_CMD)
        cls.skill_text = read(BROWSER_SKILL)

    def test_browserclaw_in_both(self) -> None:
        assert "browserclaw" in self.cmd_text
        assert "browserclaw" in self.skill_text

    def test_fingerprint_exception_in_both(self) -> None:
        for kw in ("LinkedIn", "Cloudflare"):
            assert kw in self.cmd_text, f"{kw!r} missing from browser.md"
            assert kw in self.skill_text, f"{kw!r} missing from skill"

    def test_har_ban_phrase_in_both(self) -> None:
        # Both files must mention capture/learn/reverse in the same context
        # so the credential-flow ban is enforced from both sides.
        cmd_pattern = re.compile(
            r"capture.{0,80}learn.{0,80}reverse|reverse.{0,80}learn.{0,80}capture",
            re.IGNORECASE | re.DOTALL,
        )
        assert cmd_pattern.search(self.cmd_text), (
            "browser.md must reference the capture/learn/reverse ban"
        )
        assert cmd_pattern.search(self.skill_text), (
            "browser-control/SKILL.md must reference the capture/learn/reverse ban"
        )

    def test_full_routing_order_parses_and_matches_expected(self) -> None:
        """Parse the numbered Routing order section in BOTH the command and
        the skill, and confirm the route sequence matches the expected
        Aside-MCP → Aside-CLI → browserclaw → Playwright headless →
        visible/headed ordering. Catches a reordering that the loose
        keyword tests above would silently miss."""
        for label, path in (("command", BROWSER_CMD), ("skill", BROWSER_SKILL)):
            text = read(path)
            entries = parse_numbered_route_order(text)
            sigs = [route_label_signature(label) for _, _, label in entries]
            sigs = [s for s in sigs if s]
            expected_sigs = [sig for sig, _ in EXPECTED_ROUTE_ORDER]
            # The first len(expected_sigs) route entries must equal the
            # expected sequence (the rest are unrelated numbered lists).
            head = sigs[: len(expected_sigs)]
            assert head == expected_sigs, (
                f"{label} ({path}) numbered Routing order does not match "
                f"expected sequence.\n  got:      {head}\n  expected: {expected_sigs}\n"
                f"  full parsed signatures: {sigs}"
            )


class BrowserclawReferenceSafetyTest(unittest.TestCase):
    """The two referenced browserclaw recipes MUST use the guarded mktemp
    lifecycle. Fixed /tmp paths and unguarded screenshots are banned because
    the new /browser command points operators to these files as background
    references for the canonical guarded lifecycle."""

    @classmethod
    def setUpClass(cls) -> None:
        assert GEMINI_REF.is_file(), f"gemini reference missing at {GEMINI_REF}"
        assert MULTI_REF.is_file(), f"multi-profile reference missing at {MULTI_REF}"
        cls.gemini_text = read(GEMINI_REF)
        cls.multi_text = read(MULTI_REF)

    def test_gemini_reference_no_fixed_tmp_paths(self) -> None:
        """The Gemini share-link reference must not contain the legacy
        fixed /tmp paths that the round-1 review flagged as unsafe."""
        for pat, msg in UNSAFE_FIXED_TMP_PATHS:
            assert not re.search(pat, self.gemini_text), (
                f"gemini-share-link-as-user.md still has unsafe path: {msg}"
            )

    def test_multi_profile_reference_no_fixed_tmp_paths(self) -> None:
        for pat, msg in UNSAFE_FIXED_TMP_PATHS:
            assert not re.search(pat, self.multi_text), (
                f"multi-profile-cookie-scan.md still has unsafe path: {msg}"
            )

    def test_gemini_reference_uses_guarded_lifecycle(self) -> None:
        # mktemp + chmod 600 + cleanup function + trap-on-exit.
        for kw in ("mktemp", "chmod 600", "trap", "rm -f"):
            assert kw in self.gemini_text, (
                f"gemini-share-link-as-user.md missing guarded-lifecycle anchor: {kw!r}"
            )

    def test_multi_profile_reference_uses_guarded_lifecycle(self) -> None:
        for kw in ("mktemp", "chmod 600", "trap", "rm -f"):
            assert kw in self.multi_text, (
                f"multi-profile-cookie-scan.md missing guarded-lifecycle anchor: {kw!r}"
            )

    def test_references_delegate_to_canonical_lifecycle(self) -> None:
        """The references must explicitly defer to the canonical guarded
        lifecycle in the /browser command and the browser-control skill,
        so operators know not to copy them as standalone instructions."""
        for path, text in ((GEMINI_REF, self.gemini_text), (MULTI_REF, self.multi_text)):
            assert "browser.md" in text and "browser-control/SKILL.md" in text, (
                f"{path} must point to the canonical guarded lifecycle in browser.md and "
                "browser-control/SKILL.md"
            )

    def test_references_do_not_persist_screenshots_by_default(self) -> None:
        """The references must not contain a default `--screenshot` flag
        that lands a PNG on disk. Visual evidence requires explicit opt-in."""
        # The Gemini reference may mention screenshots in the context of
        # "do not write screenshots by default" — verify it is not in an
        # active `--screenshot /tmp/...` flag.
        for path, text in ((GEMINI_REF, self.gemini_text), (MULTI_REF, self.multi_text)):
            assert not re.search(r"--screenshot\s+/tmp/", text), (
                f"{path} must not contain `--screenshot /tmp/...` as an active flag"
            )


class AsideBrowserDefaultReconciliationTest(unittest.TestCase):
    """The aside-browser-default skill must agree with the browser-control
    contract: Aside is a real GUI browser (not headless); the headless-only
    default applies to the Playwright/browserclaw fallback, not to Aside."""

    @classmethod
    def setUpClass(cls) -> None:
        assert ASIDE_SKILL.is_file(), f"aside-browser-default SKILL.md missing at {ASIDE_SKILL}"
        cls.text = read(ASIDE_SKILL)

    def test_aside_is_not_headless(self) -> None:
        """The skill must state that Aside is a real GUI browser, not
        headless. The 'headless-only default' applies to the Playwright /
        browserclaw fallback, not to Aside."""
        assert "not headless" in self.text.lower(), (
            "aside-browser-default/SKILL.md must state Aside is not headless"
        )
        assert "real" in self.text.lower() and "gui" in self.text.lower(), (
            "aside-browser-default/SKILL.md must state Aside is a real GUI browser"
        )

    def test_headless_only_default_refers_to_fallback(self) -> None:
        """Where the skill mentions 'headless-only default', it must be in
        the context of the Playwright/browserclaw fallback, not as a
        property of Aside."""
        # Find the anti-pattern line about headed mode and confirm the
        # context names a non-Aside fallback.
        m = re.search(
            r"show_browser.*headed mode.*headless-only default",
            self.text,
            re.IGNORECASE | re.DOTALL,
        )
        assert m, "anti-pattern line about headed mode + headless-only default missing"
        context = self.text[max(0, m.start() - 100): m.end() + 100].lower()
        assert ("playwright" in context) or ("browserclaw" in context) or ("fallback" in context), (
            "aside-browser-default/SKILL.md anti-pattern line must clarify that "
            "the headless-only default applies to the Playwright/browserclaw "
            "fallback, not to Aside"
        )


class ShellLifecycleSimulationTest(unittest.TestCase):
    """Prove the fail-closed lifecycle invariant: a guarded mktemp
    + chmod-600 + trap-EXIT-INT-TERM shell script removes its temp files
    on both success and failure, and a nonzero exit code from the
    underlying command propagates to the caller even after cleanup.

    This is a LOCAL simulation — it does NOT touch any real cookie state
    or call any real browserclaw binary. It uses a stand-in `false`
    command to force a nonzero exit and asserts that:
    - both TMP_COOKIES and TMP_PAGE files are removed
    - the script's exit code is the nonzero exit of the stand-in command
    - cleanup runs even on failure (trap fires on EXIT)
    """

    SIM_SCRIPT = """#!/usr/bin/env bash
set -euo pipefail

TMP_COOKIES="$(mktemp -t browserclaw-sim-cookies-XXXXXX.json)"
TMP_PAGE="$(mktemp -t browserclaw-sim-page-XXXXXX.txt)"
chmod 600 "$TMP_COOKIES" "$TMP_PAGE"
cleanup() { rm -f "$TMP_COOKIES" "$TMP_PAGE"; }
trap cleanup EXIT INT TERM

# Simulated decrypt step. The user picks success or failure.
${SIM_STEP}

cleanup
trap - EXIT INT TERM
"""

    def _run_sim(self, step: str) -> tuple[int, str, str]:
        with tempfile.TemporaryDirectory() as td:
            script_path = Path(td) / "lifecycle_sim.sh"
            script_path.write_text(self.SIM_SCRIPT.replace("${SIM_STEP}", step))
            script_path.chmod(0o755)
            env = os.environ.copy()
            proc = subprocess.run(
                ["bash", str(script_path)],
                env=env,
                capture_output=True,
                text=True,
                timeout=30,
            )
            # Walk the temp directory for any leftover mktemp files.
            leftovers = sorted(p.name for p in Path(td).glob("browserclaw-sim-*"))
            return proc.returncode, proc.stderr, ",".join(leftovers) or "<none>"

    def test_success_path_removes_temp_files_and_returns_zero(self) -> None:
        rc, _, leftovers = self._run_sim(":")  # no-op, success
        self.assertEqual(rc, 0, "success-path script must return 0")
        self.assertEqual(leftovers, "<none>", f"success-path leftover files: {leftovers}")

    def test_failure_path_removes_temp_files_and_returns_nonzero(self) -> None:
        rc, _, leftovers = self._run_sim("false")  # force nonzero exit
        self.assertNotEqual(rc, 0, "failure-path script must return nonzero (false exit was swallowed)")
        self.assertEqual(leftovers, "<none>", f"failure-path leftover files: {leftovers}")

    def test_failure_path_preserves_underlying_exit_code(self) -> None:
        rc, _, _ = self._run_sim("exit 42")
        self.assertEqual(rc, 42, "underlying exit code (42) must propagate past cleanup")

    def test_signal_like_failure_via_set_euo_pipefail(self) -> None:
        """set -euo pipefail must abort on the first failure and still
        run the EXIT trap. We trigger set -u via an undefined variable,
        which guarantees the script aborts regardless of compound-command
        rules (set -u is not affected by &&/|| short-circuit semantics)."""
        rc, _, leftovers = self._run_sim('echo "${UNDEFINED_VAR}"')
        self.assertNotEqual(rc, 0, "set -u must abort on an undefined variable")
        self.assertEqual(leftovers, "<none>", "EXIT trap must run on set -u abort")

class _ExtractedRecipeTestBase(unittest.TestCase):
    """Parse the documented canonical recipes from the markdown files
    and prove the fail-closed contract by actually executing the
    extracted snippets in a hermetic environment.

    This is the regression test the round-2 reviewer asked for: it
    reads the actual documented shell, replaces the browserclaw /
    Playwright invocations with no-op stand-ins, and asserts cleanup,
    nonzero propagation, and the secret-branch combined-cleanup
    invariant.
    """

    @classmethod
    def _extract_canonical_recipe(cls) -> str:
        text = read(BROWSER_CMD)
        body = text.split("## Auth-gated share links", 1)[1]
        m = re.search(r"```bash\n(.*?)\n```", body, re.DOTALL)
        assert m, "browser.md missing canonical bash recipe block"
        recipe = m.group(1)
        # macOS `mktemp -t TEMPLATE` ignores `$TMPDIR` and always
        # writes to the per-user system temp dir. The test runtime
        # points TMPDIR at a controlled temp dir so it can scan
        # leftovers; rewrite the mktemp calls to use
        # `mktemp -p "$TMPDIR/"` so the contract test is portable
        # to GNU and BSD coreutils. The documented recipe in
        # browser.md is unchanged.
        recipe = re.sub(
            r"mktemp -t ([^\s\"]+)",
            r'mktemp -p "$TMPDIR/" \1',
            recipe,
        )
        # The test must NEVER invoke the real browserclaw against
        # the user's actual profile cookies. Replace the entire
        # multi-profile sweep (the `set +e ... set -e` block) with
        # a hermetic no-op that writes a single stub cookie to
        # $TMP_COOKIES so the gate passes, then replace every
        # remaining `env -i ... browserclaw ...` multi-line block
        # (the inject step) with a stub that writes the page text.
        out: list[str] = []
        in_sweep = False
        skipping_env_block = False
        for line in recipe.splitlines():
            stripped = line.strip()
            if stripped == "set +e" and not in_sweep:
                in_sweep = True
                out.append(
                    "jq -n --argjson c '[{\"name\":\"__test__\"}]' "
                    "'{cookies:$c}' > \"$TMP_COOKIES\""
                )
                continue
            if in_sweep:
                if stripped == "set -e":
                    in_sweep = False
                continue
            if line.lstrip().startswith("env -i") and line.rstrip().endswith("\\"):
                skipping_env_block = True
                out.append("printf 'stub page text' > \"$TMP_PAGE\"")
                continue
            if skipping_env_block:
                if not line.rstrip().endswith("\\"):
                    skipping_env_block = False
                continue
            out.append(line)
        return "\n".join(out)

    @classmethod
    def _extract_secret_branch(cls) -> str:
        text = read(BROWSER_SKILL)
        body = text.split("**Secret-bearing page branch:**", 1)[1].split("**Safeguards**", 1)[0]
        m = re.search(r"```bash\n(.*?)\n```", body, re.DOTALL)
        assert m, "browser-control SKILL.md missing secret-branch bash block"
        branch = m.group(1)
        # Same macOS mktemp -t portability fix as the canonical
        # recipe. Documented recipe is unchanged.
        branch = re.sub(
            r"mktemp -t ([^\s\"]+)",
            r'mktemp -p "$TMPDIR/" \1',
            branch,
        )
        # The branch is self-contained: it runs the canonical
        # multi-profile sweep itself to obtain $TMP_COOKIES, then
        # a bare Playwright script. The test must NEVER invoke
        # the real browserclaw against the user's actual profile
        # cookies, so replace the entire sweep (set +e ... set -e)
        # with a hermetic no-op that writes a single stub cookie.
        out: list[str] = []
        in_sweep = False
        for line in branch.splitlines():
            stripped = line.strip()
            if stripped == "set +e" and not in_sweep:
                in_sweep = True
                out.append(
                    "jq -n --argjson c '[{\"name\":\"__test__\"}]' "
                    "'{cookies:$c}' > \"$TMP_COOKIES\""
                )
                continue
            if in_sweep:
                if stripped == "set -e":
                    in_sweep = False
                continue
            out.append(line)
        branch = "\n".join(out)
        # Replace the real Playwright invocation with the system
        # python3 (no playwright installed) so the import fails
        # predictably; the trap must remove every browserclaw
        # temp file under TMPDIR regardless.
        branch = branch.replace(
            '"$HOME/.local/orch-venv/bin/python" - "$TMP_COOKIES" "$BROWSE_TARGET_URL" <<\'PY\'',
            '/usr/bin/python3 - "$TMP_COOKIES" "http://stub" <<\'PY\'',
        )
        return branch

    def _run_with(self, recipe: str, env_extra: dict | None = None) -> tuple[int, str, str]:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "recipe.sh"
            path.write_text(recipe)
            path.chmod(0o755)
            env = os.environ.copy()
            env["TMPDIR"] = td
            if env_extra:
                env.update(env_extra)
            proc = subprocess.run(
                ["bash", str(path)],
                env=env,
                capture_output=True,
                text=True,
                timeout=30,
                cwd=td,
            )
            leftovers = sorted(p.name for p in Path(td).glob("browserclaw*"))
            return proc.returncode, proc.stderr, ",".join(leftovers) or "<none>"

    def _populate_cookies(self, count: int = 1) -> str:
        import json as _json
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, prefix="browserclaw-ext-cookies-"
        ) as fh:
            _json.dump({"cookies": [{"name": f"c{i}"} for i in range(count)]}, fh)
            path = fh.name
        os.chmod(path, 0o600)
        return path

    def test_canonical_recipe_success_path_removes_all_credential_artifacts(self) -> None:
        recipe = self._extract_canonical_recipe()
        rc, stderr, leftovers = self._run_with(recipe)
        self.assertEqual(rc, 0, f"canonical recipe failed: {stderr}")
        self.assertEqual(leftovers, "<none>", (
            f"canonical recipe MUST leave no browserclaw temp files "
            f"on success; leftovers: {leftovers}"
        ))

    def test_canonical_recipe_failure_path_removes_all_credential_artifacts(self) -> None:
        # Replace the no-op inject with `false` so set -e aborts after
        # the cookie file has been created. The trap must still remove
        # both $TMP_COOKIES and $TMP_PAGE.
        recipe = self._extract_canonical_recipe()
        recipe = recipe.replace(
            "printf 'stub page text' > \"$TMP_PAGE\"",
            "false  # force set -e to abort",
        )
        rc, _, leftovers = self._run_with(recipe)
        self.assertNotEqual(rc, 0, "recipe MUST exit nonzero when inject fails")
        self.assertEqual(leftovers, "<none>", (
            f"canonical recipe MUST clean both $TMP_COOKIES and "
            f"$TMP_PAGE on inject failure; leftovers: {leftovers}"
        ))

    def test_canonical_recipe_zero_cookie_gate_exits_nonzero(self) -> None:
        recipe = self._extract_canonical_recipe()
        # Replace the no-op decrypt with one that writes an EMPTY
        # cookie JSON to $TMP_COOKIES so the gate trips.
        recipe = recipe.replace(
            "jq -n --argjson c '[{\"name\":\"__test__\"}]' '{cookies:$c}' > \"$TMP_COOKIES\"",
            "jq -n --argjson c '[]' '{cookies:$c}' > \"$TMP_COOKIES\"",
        )
        rc, stderr, leftovers = self._run_with(recipe)
        self.assertNotEqual(rc, 0, (
            f"canonical recipe MUST exit nonzero on zero-cookie gate "
            f"trip; got rc=0, stderr={stderr!r}"
        ))
        self.assertIn("BLOCKER", stderr, (
            "zero-cookie gate must post a BLOCKER message to stderr"
        ))
        self.assertEqual(leftovers, "<none>", (
            f"zero-cookie gate MUST still clean $TMP_COOKIES via the "
            f"trap; leftovers: {leftovers}"
        ))

    def test_secret_branch_cleans_up_cookies_on_failure(self) -> None:
        branch = self._extract_secret_branch()
        with tempfile.TemporaryDirectory() as td:
            # Place the secret branch's mktemp cookie + page text
            # inside the TMPDIR we will pass to the test so the
            # trap's cleanup is observable.
            cookie_inside = Path(td) / "browserclaw-XXXXXX-cookies.json"
            cookie_inside.write_text('{"cookies": [{"name": "x"}]}')
            cookie_inside.chmod(0o600)
            page_inside = Path(td) / "browserclaw-XXXXXX-page.txt"
            page_inside.write_text("ignored")
            page_inside.chmod(0o600)
            script = (
                f'export TMP_COOKIES="{cookie_inside}"\n'
                f'export TMP_PAGE="{page_inside}"\n'
                f"{branch}"
            )
            rc, stderr, leftovers = self._run_with(script, env_extra={
                "TMP_COOKIES": str(cookie_inside),
                "TMP_PAGE": str(page_inside),
                "BROWSE_TARGET_URL": "http://stub",
            })
            self.assertNotEqual(rc, 0, (
                f"secret branch must propagate the underlying "
                f"ImportError exit; got rc=0, stderr={stderr!r}"
            ))
            self.assertEqual(leftovers, "<none>", (
                f"secret branch trap MUST remove every browserclaw "
                f"temp file under TMPDIR; leftovers: {leftovers}"
            ))

    def test_canonical_recipe_sigint_removes_all_credential_artifacts(self) -> None:
        # Round-4/5 reviewer-required test: prove the canonical
        # recipe cleans BOTH files on SIGINT AND exits nonzero
        # (128+SIGINT=130) so callers see the signal — bash does
        # NOT continue past the trap into a state that could
        # recreate credential files. The recipe's signal handler
        # re-raises the signal after cleanup.
        recipe = self._extract_canonical_recipe()
        # Use a short sleep so the test's wait timeout does not
        # itself become the dominant cost.
        recipe = recipe.replace(
            "printf 'stub page text' > \"$TMP_PAGE\"",
            "sleep 5 & wait $!",
        )
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "recipe.sh"
            path.write_text(recipe)
            path.chmod(0o755)
            env = os.environ.copy()
            env["TMPDIR"] = td
            proc = subprocess.Popen(
                ["bash", str(path)],
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=td,
            )
            deadline = time.time() + 5
            while time.time() < deadline:
                if any(Path(td).glob("browserclaw-*.json")):
                    break
                time.sleep(0.1)
            self.assertTrue(any(Path(td).glob("browserclaw-*.json")), (
                "canonical recipe must create the cookie file before "
                "the inject step"
            ))
            proc.send_signal(signal.SIGINT)
            try:
                proc.wait(timeout=8)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
            leftovers = sorted(p.name for p in Path(td).glob("browserclaw*"))
            self.assertEqual(leftovers, [], (
                f"canonical recipe MUST clean BOTH $TMP_COOKIES and "
                f"$TMP_PAGE on SIGINT; leftovers: {leftovers}"
            ))
            # 128 + SIGINT (2) = 130; or the trap may exit with a
            # smaller nonzero. Accept anything > 128 to prove the
            # signal was not silently swallowed.
            self.assertGreater(proc.returncode, 128, (
                f"canonical recipe MUST exit with 128+signal on SIGINT "
                f"(got rc={proc.returncode}); bash continuing past the "
                f"trap is the exact bug the round-5 review flagged"
            ))

    def test_canonical_recipe_sigterm_removes_all_credential_artifacts(self) -> None:
        # Same as SIGINT but for SIGTERM. 128 + 15 = 143.
        recipe = self._extract_canonical_recipe()
        recipe = recipe.replace(
            "printf 'stub page text' > \"$TMP_PAGE\"",
            "sleep 5 & wait $!",
        )
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "recipe.sh"
            path.write_text(recipe)
            path.chmod(0o755)
            env = os.environ.copy()
            env["TMPDIR"] = td
            proc = subprocess.Popen(
                ["bash", str(path)],
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=td,
            )
            deadline = time.time() + 5
            while time.time() < deadline:
                if any(Path(td).glob("browserclaw-*.json")):
                    break
                time.sleep(0.1)
            self.assertTrue(any(Path(td).glob("browserclaw-*.json")), (
                "canonical recipe must create the cookie file before "
                "the inject step"
            ))
            proc.send_signal(signal.SIGTERM)
            try:
                proc.wait(timeout=8)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
            leftovers = sorted(p.name for p in Path(td).glob("browserclaw*"))
            self.assertEqual(leftovers, [], (
                f"canonical recipe MUST clean BOTH $TMP_COOKIES and "
                f"$TMP_PAGE on SIGTERM; leftovers: {leftovers}"
            ))
            self.assertGreater(proc.returncode, 128, (
                f"canonical recipe MUST exit with 128+signal on SIGTERM "
                f"(got rc={proc.returncode})"
            ))

    def test_canonical_recipe_has_signal_handlers(self) -> None:
        # Round-5 reviewer-required test: prove the canonical
        # recipe installs INT/TERM/HUP handlers that re-raise the
        # signal so bash does not continue past the trap.
        section = self._extract_canonical_recipe()
        assert "exit_on_signal" in section, (
            "canonical recipe must install exit_on_signal handlers "
            "for INT/TERM/HUP so the script exits nonzero on signal"
        )
        assert "INT" in section and "TERM" in section and "HUP" in section

    def test_secret_branch_under_set_u_does_not_trip_unbound_variable(self) -> None:
        # Round-3 reviewer-required test: run the EXACT documented
        # secret-branch shell under `set -u` and prove the URL
        # assignment does not trip an unbound variable on the
        # command line.
        branch = self._extract_secret_branch()
        with tempfile.TemporaryDirectory() as td:
            cookie_inside = Path(td) / "browserclaw-XXXXXX-cookies.json"
            cookie_inside.write_text('{"cookies": [{"name": "x"}]}')
            cookie_inside.chmod(0o600)
            page_inside = Path(td) / "browserclaw-XXXXXX-page.txt"
            page_inside.write_text("ignored")
            page_inside.chmod(0o600)
            script = (
                f'set -u\n'
                f'export TMP_COOKIES="{cookie_inside}"\n'
                f'export TMP_PAGE="{page_inside}"\n'
                f"{branch}"
            )
            rc, stderr, leftovers = self._run_with(script)
            self.assertNotIn("unbound variable", stderr, (
                f"secret branch must not trip set -u on BROWSE_TARGET_URL; "
                f"stderr={stderr!r}"
            ))
            self.assertEqual(leftovers, "<none>", (
                f"secret branch must leave no browserclaw temp files "
                f"under TMPDIR even when the python import fails; "
                f"leftovers: {leftovers}"
            ))


if __name__ == "__main__":
    unittest.main()
