"""Contract tests for the /browser command and the browser-control skill.

The /browser command is a thin dispatcher forwarding to
`.claude/skills/browser-control/SKILL.md`, which defines the authoritative
routing order and the safe browser credential lifecycle behind explicit task
authorization:

1. Aside-MCP first (when the active runtime exposes it).
2. Aside CLI (`aside repl` / `aside "<prompt>"`) — drives the already-running
   Aside.app profile.
3. `browserclaw cookies decrypt + inject` for headless auth on fingerprint-tolerant
   sites, ONLY when explicit task authorization has been granted. Re-decrypt from the
   local Chromium profile (Aside → Chrome Default → Profile 1 → Profile 2 → Brave → Edge).
4. Playwright headless for unauthenticated / deterministic flows.
5. Visible/headed browser only when the user explicitly asks for it.

These tests protect against:
- Treating existing sign-in as sufficient authorization without explicit task authorization.
- Thick command regression in /browser (command must remain a thin dispatcher).
- Reordering of the routing priorities.
- Browserclaw HAR-based capture being reintroduced on credential flows
  (the `capture`/`learn`/`reverse` ban).
- Loss of the fingerprint-sensitive outlier exception (LinkedIn / banks /
  Cloudflare-protected sites that bind cookies to the running browser).
- Loss of the explicit credential-reuse safeguards (private /tmp only,
  --summary, never commit, never log values).
- Loss of the clean-the-cookie-JSON-after-use step and fail-closed trap.
- Reintroducing fixed `/tmp/<x>.json` paths in the referenced recipes that
  leak credentials across processes.
- Allowing fingerprint-sensitive sites (LinkedIn, banks, Cloudflare) to
  fall through to cookie injection on a headless host.
- Reintroducing `--print-text`, screenshots, or HARs on secret-bearing
  pages (API keys, tokens, banking, recovery codes).
- Loss of the fail-closed shell lifecycle (`set -euo pipefail`, EXIT
  trap on both success and failure, nonzero exit preserved on cleanup,
  signal traps for INT/TERM/HUP).
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
    starting with `<n>. **<RouteName>**`.
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

DISALLOWED_PHRASES = [
    (r"never.*copy\s+cookies\s+between\s+profiles", "old 'never copy cookies between profiles' ban contradicts the browserclaw fallback"),
    (r"do\s+not\s+copy\s+cookies", "old 'do not copy cookies' ban contradicts the browserclaw fallback"),
]

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
    cmd_text: str = ""
    skill_text: str = ""


class BrowserCommandContractTest(_BrowserFilesBase):
    """The /browser command MUST be a thin dispatcher forwarding to the canonical skill."""

    @classmethod
    def setUpClass(cls) -> None:
        assert BROWSER_CMD.is_file(), f"browser.md missing at {BROWSER_CMD}"
        cls.cmd_text = read(BROWSER_CMD)

    def test_command_is_thin_dispatcher(self) -> None:
        lines = [l for l in self.cmd_text.splitlines() if l.strip()]
        self.assertLessEqual(
            len(lines),
            20,
            f"browser.md must be a thin dispatcher; got {len(lines)} non-empty lines",
        )
        self.assertIn("browser-control/SKILL.md", self.cmd_text)
        self.assertNotIn("```bash", self.cmd_text, "browser.md must not contain thick bash recipes")
        self.assertNotIn("browserclaw cookies decrypt", self.cmd_text)

    def test_command_requires_explicit_task_authorization(self) -> None:
        self.assertIn(
            "user has explicitly authorized access",
            self.cmd_text,
            "browser.md must require explicit user authorization for cookie transfer",
        )

    def test_command_references_playwright_testing(self) -> None:
        self.assertIn("playwright-ui-testing", self.cmd_text)
        self.assertNotIn(
            "~/.claude/skills/",
            self.cmd_text,
            "browser.md must use relative/discovery skill pointers",
        )


class BrowserSkillContractTest(_BrowserFilesBase):
    """The browser-control skill MUST encode the full routing order and safe credential lifecycle."""

    @classmethod
    def setUpClass(cls) -> None:
        assert BROWSER_SKILL.is_file(), f"browser-control SKILL.md missing at {BROWSER_SKILL}"
        cls.skill_text = read(BROWSER_SKILL)

    def test_routing_order_anchors_present(self) -> None:
        missing = assert_any_match(self.skill_text, SKILL_ROUTING_PATTERNS)
        self.assertEqual(
            missing,
            [],
            "browser-control/SKILL.md is missing required routing-order anchors:\n"
            + "\n".join(f"  - {m}" for m in missing),
        )

    def test_routing_order_lists_aside_mcp_first(self) -> None:
        first_aside_mcp = first_index(self.skill_text, r"aside-mcp|aside\s*mcp|Aside-MCP")
        first_aside_cli = first_index(self.skill_text, r"aside\s+repl|aside\s+account\s+list")
        self.assertGreaterEqual(first_aside_mcp, 0, "Aside-MCP must be referenced in the skill")
        self.assertGreaterEqual(first_aside_cli, 0, "Aside CLI must be referenced in the skill")
        self.assertLess(
            first_aside_mcp,
            first_aside_cli,
            "Aside-MCP must appear before the Aside CLI mention in the skill",
        )

    def test_routing_order_lists_browserclaw_before_playwright_fallback(self) -> None:
        first_browserclaw = first_index(self.skill_text, r"browserclaw")
        first_playwright = first_index(self.skill_text, r"Playwright\s+headless")
        self.assertGreaterEqual(first_browserclaw, 0, "browserclaw must be referenced")
        self.assertGreaterEqual(first_playwright, 0, "Playwright headless fallback must be referenced")
        self.assertLess(
            first_browserclaw,
            first_playwright,
            "browserclaw must be a higher-priority fallback than Playwright headless",
        )

    def test_full_routing_order_sequence(self) -> None:
        entries = parse_numbered_route_order(self.skill_text)
        sigs = [route_label_signature(label) for _, _, label in entries]
        sigs = [s for s in sigs if s]
        expected_sigs = [sig for sig, _ in EXPECTED_ROUTE_ORDER]
        head = sigs[: len(expected_sigs)]
        self.assertEqual(
            head,
            expected_sigs,
            f"Numbered routing order does not match expected sequence.\n got: {head}\n expected: {expected_sigs}",
        )

    def test_credential_reuse_requires_explicit_authorization(self) -> None:
        self.assertIn(
            "Credential reuse requires explicit task authorization",
            self.skill_text,
            "Skill must state that credential reuse requires explicit task authorization",
        )
        self.assertIn(
            "An existing sign-in alone is NOT sufficient authorization",
            self.skill_text,
            "Skill must explicitly reject treating existing sign-in as sufficient authorization",
        )
        self.assertIn(
            "credential reuse MUST be denied",
            self.skill_text,
            "Skill must state that without explicit authorization credential reuse must be denied",
        )
        self.assertIn("explicitly authorizes local cookie transfer", self.skill_text)

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
            self.assertIn(kw, self.skill_text, f"Safeguard missing from skill: {kw!r}")
        section = self.skill_text.split("## Authorized credential reuse", 1)[1].split("## Fingerprint-sensitive", 1)[0]
        shell_block = section.split("```bash", 1)[1].split("```", 1)[0]
        self.assertNotIn("--screenshot", shell_block)

    def test_fail_closed_lifecycle_present(self) -> None:
        self.assertIn("set -euo pipefail", self.skill_text)
        self.assertIn("exit_on_signal", self.skill_text)
        self.assertIn("trap 'exit_on_signal INT' INT", self.skill_text)
        self.assertIn("trap 'exit_on_signal TERM' TERM", self.skill_text)
        self.assertIn("trap 'exit_on_signal HUP' HUP", self.skill_text)
        self.assertIn("trap cleanup_browser_creds EXIT", self.skill_text)
        canonical_block = self.skill_text.split(
            "## Authorized credential reuse", 1)[1].split(
            "## Fingerprint-sensitive", 1)[0]
        self.assertNotIn("trap -", canonical_block, "Canonical recipe must NOT disarm its trap")

    def test_no_screenshot_in_any_documented_bash_block(self) -> None:
        blocks = re.findall(r"```bash\n(.*?)\n```", self.skill_text, re.DOTALL)
        self.assertGreater(len(blocks), 0, "Skill must contain documented bash blocks")
        for i, block in enumerate(blocks):
            active = [
                line for line in block.splitlines()
                if not line.lstrip().startswith("#")
                and ("--screenshot" in line or "--capture-har" in line)
            ]
            self.assertEqual(
                active,
                [],
                f"Bash block #{i} must not contain an active --screenshot or --capture-har; found: {active!r}",
            )

    def test_secret_page_branch_safeguards(self) -> None:
        section = self.skill_text.split("**Secret-bearing page branch:**", 1)[1].split("**Safeguards**", 1)[0]
        self.assertIn("MUST NOT execute the generic `--print-text` recipe", section)
        self.assertIn("persist neither DOM text nor images", section)
        self.assertIn("minimum safe non-secret DOM state in memory", section)
        self.assertIn("set -euo pipefail", section)
        self.assertIn("sys.stdout.write", section)
        self.assertIn("exit_on_signal", section)
        self.assertNotIn("trap -", section)
        bare_write_text_calls = [
            line for line in section.splitlines()
            if not line.lstrip().startswith("#") and ".write_text(" in line
        ]
        self.assertEqual(bare_write_text_calls, [])

    def test_no_har_for_credential_flows(self) -> None:
        har_ban_pattern = re.compile(
            r"(?:capture|learn|reverse).{0,80}(?:capture|learn|reverse).{0,80}(?:capture|learn|reverse)",
            re.IGNORECASE | re.DOTALL,
        )
        self.assertTrue(
            har_ban_pattern.search(self.skill_text),
            "Skill must explicitly ban capture/learn/reverse for credential flows",
        )

    def test_fingerprint_sensitive_outlier_named(self) -> None:
        for kw in ("LinkedIn", "Cloudflare", "Akamai"):
            self.assertIn(kw, self.skill_text, f"{kw!r} missing from skill")
        self.assertIn("ONE-LINE BLOCKER", self.skill_text)

    def test_no_disallowed_phrases(self) -> None:
        found = assert_none_match(self.skill_text, DISALLOWED_PHRASES)
        self.assertEqual(found, [], f"Skill contains disallowed phrases: {found}")


class BrowserclawReferenceSafetyTest(unittest.TestCase):
    """Browserclaw reference recipes MUST use guarded mktemp lifecycle and require explicit authorization."""

    @classmethod
    def setUpClass(cls) -> None:
        assert GEMINI_REF.is_file(), f"gemini reference missing at {GEMINI_REF}"
        assert MULTI_REF.is_file(), f"multi-profile reference missing at {MULTI_REF}"
        cls.gemini_text = read(GEMINI_REF)
        cls.multi_text = read(MULTI_REF)

    def test_gemini_reference_no_fixed_tmp_paths(self) -> None:
        for pat, msg in UNSAFE_FIXED_TMP_PATHS:
            self.assertFalse(re.search(pat, self.gemini_text), f"gemini ref has unsafe path: {msg}")

    def test_multi_profile_reference_no_fixed_tmp_paths(self) -> None:
        for pat, msg in UNSAFE_FIXED_TMP_PATHS:
            self.assertFalse(re.search(pat, self.multi_text), f"multi ref has unsafe path: {msg}")

    def test_references_delegate_to_canonical_lifecycle(self) -> None:
        for path, text in ((GEMINI_REF, self.gemini_text), (MULTI_REF, self.multi_text)):
            self.assertIn("browser-control/SKILL.md", text, f"{path} must point to canonical skill")

    def test_references_require_explicit_authorization(self) -> None:
        for path, text in ((GEMINI_REF, self.gemini_text), (MULTI_REF, self.multi_text)):
            self.assertIn(
                "Credential reuse requires explicit task authorization",
                text,
                f"{path} must state explicit task authorization requirement",
            )


class AsideBrowserDefaultReconciliationTest(unittest.TestCase):
    """The aside-browser-default skill must state Aside is a real GUI browser (not headless)."""

    @classmethod
    def setUpClass(cls) -> None:
        assert ASIDE_SKILL.is_file(), f"aside-browser-default SKILL.md missing at {ASIDE_SKILL}"
        cls.text = read(ASIDE_SKILL)

    def test_aside_is_not_headless(self) -> None:
        self.assertIn("not headless", self.text.lower())
        self.assertTrue("real" in self.text.lower() and "gui" in self.text.lower())

    def test_headless_only_default_refers_to_fallback(self) -> None:
        m = re.search(
            r"show_browser.*headed mode.*headless-only default",
            self.text,
            re.IGNORECASE | re.DOTALL,
        )
        self.assertTrue(m, "anti-pattern line about headed mode + headless-only default missing")
        context = self.text[max(0, m.start() - 100): m.end() + 100].lower()
        self.assertTrue(
            ("playwright" in context) or ("browserclaw" in context) or ("fallback" in context),
            "aside-browser-default SKILL.md must clarify headless-only default applies to fallback",
        )


class ShellLifecycleSimulationTest(unittest.TestCase):
    """Prove the fail-closed lifecycle invariant locally with a hermetic simulation."""

    SIM_SCRIPT = """#!/usr/bin/env bash
set -euo pipefail

TMP_COOKIES="$(mktemp -t browserclaw-sim-cookies-XXXXXX.json)"
TMP_PAGE="$(mktemp -t browserclaw-sim-page-XXXXXX.txt)"
chmod 600 "$TMP_COOKIES" "$TMP_PAGE"
cleanup() { rm -f "$TMP_COOKIES" "$TMP_PAGE"; }
trap cleanup EXIT INT TERM

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
            leftovers = sorted(p.name for p in Path(td).glob("browserclaw-sim-*"))
            return proc.returncode, proc.stderr, ",".join(leftovers) or "<none>"

    def test_success_path_removes_temp_files_and_returns_zero(self) -> None:
        rc, _, leftovers = self._run_sim(":")
        self.assertEqual(rc, 0)
        self.assertEqual(leftovers, "<none>")

    def test_failure_path_removes_temp_files_and_returns_nonzero(self) -> None:
        rc, _, leftovers = self._run_sim("false")
        self.assertNotEqual(rc, 0)
        self.assertEqual(leftovers, "<none>")

    def test_failure_path_preserves_underlying_exit_code(self) -> None:
        rc, _, _ = self._run_sim("exit 42")
        self.assertEqual(rc, 42)


class ExtractedRecipeExecutionTest(unittest.TestCase):
    """Execute extracted documented bash recipes from browser-control/SKILL.md in hermetic subprocesses."""

    @classmethod
    def _extract_canonical_recipe(cls) -> str:
        text = read(BROWSER_SKILL)
        body = text.split("## Authorized credential reuse", 1)[1].split("## Fingerprint-sensitive", 1)[0]
        m = re.search(r"```bash\n(.*?)\n```", body, re.DOTALL)
        assert m, "browser-control SKILL.md missing canonical bash recipe block"
        recipe = m.group(1)
        recipe = re.sub(
            r"mktemp -t ([^\s\"]+)",
            r'mktemp -p "$TMPDIR/" \1',
            recipe,
        )
        out: list[str] = []
        in_sweep = False
        skipping_env_block = False
        for line in recipe.splitlines():
            stripped = line.strip()
            if stripped == "set +e" and not in_sweep:
                in_sweep = True
                out.append(
                    "jq -n --argjson c '[{\"name\":\"__test__\",\"value\":\"1\",\"domain\":\".example.com\",\"path\":\"/\"}]' "
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
        branch = re.sub(
            r"mktemp -t ([^\s\"]+)",
            r'mktemp -p "$TMPDIR/" \1',
            branch,
        )
        out: list[str] = []
        in_sweep = False
        for line in branch.splitlines():
            stripped = line.strip()
            if stripped == "set +e" and not in_sweep:
                in_sweep = True
                out.append(
                    "jq -n --argjson c '[{\"name\":\"__test__\",\"value\":\"1\",\"domain\":\".example.com\",\"path\":\"/\"}]' "
                    "'{cookies:$c}' > \"$TMP_COOKIES\""
                )
                continue
            if in_sweep:
                if stripped == "set -e":
                    in_sweep = False
                continue
            out.append(line)
        branch = "\n".join(out)
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

    def test_canonical_recipe_success_path_removes_all_credential_artifacts(self) -> None:
        recipe = self._extract_canonical_recipe()
        rc, stderr, leftovers = self._run_with(recipe)
        self.assertEqual(rc, 0, f"canonical recipe failed: {stderr}")
        self.assertEqual(leftovers, "<none>")

    def test_canonical_recipe_failure_path_removes_all_credential_artifacts(self) -> None:
        recipe = self._extract_canonical_recipe()
        recipe = recipe.replace(
            "printf 'stub page text' > \"$TMP_PAGE\"",
            "false  # force set -e to abort",
        )
        rc, _, leftovers = self._run_with(recipe)
        self.assertNotEqual(rc, 0)
        self.assertEqual(leftovers, "<none>")

    def test_canonical_recipe_zero_cookie_gate_exits_nonzero(self) -> None:
        recipe = self._extract_canonical_recipe()
        recipe = recipe.replace(
            "jq -n --argjson c '[{\"name\":\"__test__\",\"value\":\"1\",\"domain\":\".example.com\",\"path\":\"/\"}]' '{cookies:$c}' > \"$TMP_COOKIES\"",
            "jq -n --argjson c '[]' '{cookies:$c}' > \"$TMP_COOKIES\"",
        )
        rc, stderr, leftovers = self._run_with(recipe)
        self.assertNotEqual(rc, 0)
        self.assertIn("BLOCKER", stderr)
        self.assertEqual(leftovers, "<none>")

    def test_secret_branch_cleans_up_cookies_on_failure(self) -> None:
        branch = self._extract_secret_branch()
        with tempfile.TemporaryDirectory() as td:
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
            self.assertNotEqual(rc, 0)
            self.assertEqual(leftovers, "<none>")

    def test_canonical_recipe_sigint_removes_all_credential_artifacts(self) -> None:
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
            self.assertTrue(any(Path(td).glob("browserclaw-*.json")))
            proc.send_signal(signal.SIGINT)
            try:
                proc.wait(timeout=8)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
            leftovers = sorted(p.name for p in Path(td).glob("browserclaw*"))
            self.assertEqual(leftovers, [])
            self.assertGreater(proc.returncode, 128)

    def test_canonical_recipe_sigterm_removes_all_credential_artifacts(self) -> None:
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
            self.assertTrue(any(Path(td).glob("browserclaw-*.json")))
            proc.send_signal(signal.SIGTERM)
            try:
                proc.wait(timeout=8)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
            leftovers = sorted(p.name for p in Path(td).glob("browserclaw*"))
            self.assertEqual(leftovers, [])
            self.assertGreater(proc.returncode, 128)

    def test_canonical_recipe_has_signal_handlers(self) -> None:
        section = self._extract_canonical_recipe()
        self.assertIn("exit_on_signal", section)
        self.assertTrue("INT" in section and "TERM" in section and "HUP" in section)

    def test_authorization_denial_simulation(self) -> None:
        """Prove that when task authorization is false/absent, the execution denies credential reuse,
        emits a blocker message, exits nonzero, and leaves no temp files."""
        auth_check_script = """#!/usr/bin/env bash
set -euo pipefail
umask 077
TMP_COOKIES="$(mktemp -p "$TMPDIR/" browserclaw-XXXXXX.json)"
chmod 600 "$TMP_COOKIES"
cleanup() { rm -f "$TMP_COOKIES"; }
trap cleanup EXIT INT TERM

TASK_AUTHORIZED="${TASK_AUTHORIZED:-false}"
if [ "$TASK_AUTHORIZED" != "true" ]; then
  echo "BLOCKER: Credential reuse denied — task lacks explicit authorization for cookie transfer." >&2
  exit 12
fi

echo '{"cookies":[{"name":"test"}]}' > "$TMP_COOKIES"
"""
        rc, stderr, leftovers = self._run_with(auth_check_script, env_extra={"TASK_AUTHORIZED": "false"})
        self.assertEqual(rc, 12)
        self.assertIn("BLOCKER: Credential reuse denied", stderr)
        self.assertEqual(leftovers, "<none>")


if __name__ == "__main__":
    unittest.main()
