"""Deterministic, pure-function core of /web-advice.

This module extracts the parts of the /web-advice skill (see ../SKILL.md)
that are pure decision logic — transport ladder resolution, banned-substitute
detection, verdict-text parsing, seat accounting, and visual-review prompt
construction — into unit-testable functions with NO browser/network/subprocess
calls at import time or call time.

Everything here is a pure function over plain data (dict/str/list -> dict/str/bool).
Browser automation through aside-mcp or the `aside repl` Playwright API stays
in the skill's runtime instructions; this module never imports or calls it.

Hard-won lessons encoded here (2026-08-02 real runs — see SKILL.md HARD-FAIL
CONTRACT section for full provenance):

1. HARD-FAIL CONTRACT: /web-advice means real browser sessions on the real
   sites. Provider APIs, CLI models, subagents, and WebSearch are BANNED
   substitutes even with disclosure. If no transport is live: STOP.
   -> WebAdviceHardFail + resolve_transport_ladder()
2. TRANSPORT LADDER, in order: Aside browser automation first, then verified
   real-browser fallbacks. Every rung drives the vendor web UI; none invokes
   model inference outside that UI.
   -> resolve_transport_ladder()
6. Seats must be accounted for honestly: never present a partial panel as full.
   -> seat_accounting()
6/10. Visual-description-first prompting: for image/frame evidence, demand a
   literal pixel description BEFORE any verdict, then "what changed", then the
   verdict, then "what would change it". A model describing something not in
   the frame is itself a finding.
   -> build_visual_prompt()
10. Verdict scraping must tolerate real-world response formatting: markdown
   bold labels, plain colon-separated labels, and leading '>' blockquote
   markers (models sometimes quote their own structured answer back).
   -> parse_verdict()
12. ATTACHMENT VERIFICATION (bead wc-kjny, 2026-08-02 multi-vendor incident):
   an upload call that throws no exception and logs "files set" is NOT
   proof of a successful attachment -- a vendor page can expose multiple
   `input[type="file"]` elements and a naive `.first()` locator can
   silently grab the wrong one, attaching zero images while the model
   fabricates a confident, fully-formatted verdict for content that was
   never uploaded (a "9:41" status bar, a "hooded figure", "the scent of
   ozone" -- none of it real, zero exceptions raised). This pattern is
   not vendor-specific; it applies to any chat UI with multiple file
   inputs. -> AttachmentNotVerifiedError + assert_attachment_verified()
13. FRAME ORDER VERIFICATION (bead wc-kjny, Perplexity 2026-08-02): a model
   can read every frame's pixels correctly and still discuss them in the
   wrong sequence, which measurably weakens its verdict even though
   nothing it said was individually false (Perplexity's own "Frame 1/2/3"
   labels didn't match upload order, scrambling its causal narrative and
   landing it on PARTIALLY SUPPORTED where the remaining vendors reached
   SUPPORTED on identical evidence). -> verify_frame_order()
"""

from __future__ import annotations

import re

_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")

# ---------------------------------------------------------------------------
# Lesson 1 + 2: HARD-FAIL CONTRACT + TRANSPORT LADDER
# ---------------------------------------------------------------------------


class WebAdviceHardFail(Exception):
    """Raised when no approved /web-advice transport is live.

    Per the HARD-FAIL CONTRACT (SKILL.md), this must STOP the review — never
    silently substitute a provider API, CLI model, subagent, or WebSearch.
    """


# Ladder order is runtime-specific. An interactive app owns its browser state;
# a CLI run gets a new direct system-Chrome headless context so a shared GUI
# conversation cannot contaminate its review provenance.
_APP_LADDER = (
    ("builtin_browser", "builtin_browser"),
    ("aside_mcp", "aside_mcp"),
    ("aside_repl", "aside_repl"),
    ("chrome_headless_cookies", "chrome_headless_cookies"),
    ("playwright_mcp", "playwright_mcp"),
    ("chrome_headless_cdp", "chrome_headless_cdp"),
    ("chrome_extension", "chrome_extension"),
)

_CLI_LADDER = (
    ("chrome_headless_cookies", "chrome_headless_cookies"),
    ("playwright_mcp", "playwright_mcp"),
    ("chrome_headless_cdp", "chrome_headless_cdp"),
)


def resolve_transport_ladder(probe_results: dict, runtime: str = "app") -> str:
    """Return the highest-priority live transport, or hard-fail.

    Args:
        probe_results: dict with any subset of the approved transport keys.
            Missing keys are treated as False (probe not run / not live).
        runtime: ``app`` prefers an owned built-in browser; ``cli`` selects an
            isolated direct headless-Chrome route.

    Returns:
        The highest-priority live real-browser transport from the runtime's
        approved ladder.

    Raises:
        WebAdviceHardFail: when every probe is false/missing. Per the
        HARD-FAIL CONTRACT this must stop the review, not fall back to a
        banned substitute (provider API / CLI model / subagent / WebSearch).
    """
    ladders = {"app": _APP_LADDER, "cli": _CLI_LADDER}
    if runtime not in ladders:
        raise ValueError(f"Unsupported /web-advice runtime: {runtime!r}")

    ladder = ladders[runtime]
    for probe_key, transport_name in ladder:
        if probe_results.get(probe_key):
            return transport_name

    probed = ", ".join(f"{k}={probe_results.get(k, False)}" for k, _ in ladder)
    raise WebAdviceHardFail(
        "No live /web-advice transport ("
        f"{probed}). HARD FAIL per the /web-advice contract: real browser "
        "sessions on the real sites only. Do NOT substitute provider APIs, "
        "CLI models, in-session subagents, or WebSearch/WebFetch and call "
        "the result /web-advice. Stop and ask the user to fix/reconnect the "
        "authenticated browser transport."
    )


# ---------------------------------------------------------------------------
# Lesson 1: BANNED SUBSTITUTIONS
# ---------------------------------------------------------------------------

# Canonical, normalized (lowercase, spaces/hyphens -> underscore) identifiers
# for every mechanism the HARD-FAIL CONTRACT explicitly bans as a substitute
# for real-website /web-advice sessions, even with disclosure.
_BANNED_SUBSTITUTES = frozenset(
    {
        # Provider APIs
        "provider_api",
        "gemini_files_api",
        "gemini_generatecontent",
        "gemini_generatecontent_api",
        "gemini_api",
        "openai_api",
        "chatgpt_api",
        "xai_api",
        # CLI models
        "cli_model",
        "agy",
        "codex",
        "codex_cli",
        "gemini_cli",
        # Aside inference consumes token quota and bypasses web subscriptions.
        "aside_inference",
        "aside_exec",
        "aside_exec_m",
        "aside_effort_ultrabrowse",
        "aside_nl_agent",
        "aside_ultrabrowse",
        "aside_ai",
        # In-session subagents
        "subagent",
        "subagents",
        "in_session_subagent",
        # Web search/fetch synthesis
        "websearch",
        "web_search",
        "webfetch",
        "web_fetch",
    }
)

_PRIMARY_TRANSPORTS = frozenset({"builtin_browser", "aside_mcp", "aside_repl"})
_BROWSER_BACKUP_TRANSPORTS = frozenset(
    {
        "chrome_headless_cookies",
        "playwright_mcp",
        "chrome_headless_cdp",
        "chrome_extension",
    }
)
_ALLOWED_TRANSPORTS = _PRIMARY_TRANSPORTS | _BROWSER_BACKUP_TRANSPORTS
_FALLBACK_REASONS = frozenset(
    {"aside_unavailable", "unsupported_platform", "aside_upload_unavailable"}
)


def _normalize_mechanism(mechanism: str) -> str:
    return re.sub(r"[\s\-]+", "_", mechanism.strip().lower())


def is_banned_substitute(mechanism: str) -> bool:
    """True if `mechanism` is a banned /web-advice substitute.

    Banned categories (HARD-FAIL CONTRACT, lesson 1): provider APIs (Gemini
    Files API / generateContent, OpenAI API, xAI API), CLI models (agy,
    codex, gemini CLI), Aside inference (aside_exec, aside_nl_agent,
    aside_ultrabrowse), in-session subagents, and WebSearch/WebFetch
    synthesis. The separate allowlist accepts primary Aside transports and
    conditionally eligible real-browser fallbacks.
    """
    return _normalize_mechanism(mechanism) in _BANNED_SUBSTITUTES


def assert_allowed_transport(
    mechanism: str, fallback_reason: str | None = None
) -> None:
    """Raise unless ``mechanism`` is an eligible real-browser transport.

    Aside transports are always eligible and remain preferred. Browser backup
    transports require an explicit, deterministic reason so they cannot
    silently displace a working Aside route.
    """
    normalized = _normalize_mechanism(mechanism)
    if is_banned_substitute(mechanism) or normalized not in _ALLOWED_TRANSPORTS:
        raise WebAdviceHardFail(
            f"Unsupported /web-advice transport: {mechanism!r}. "
            "Use an approved real-browser transport; Aside inference and "
            "substitute review mechanisms are forbidden."
        )
    if normalized in _BROWSER_BACKUP_TRANSPORTS:
        normalized_reason = _normalize_mechanism(fallback_reason or "")
        if normalized_reason not in _FALLBACK_REASONS:
            raise WebAdviceHardFail(
                f"Browser backup transport {mechanism!r} requires "
                "fallback_reason=aside_unavailable, unsupported_platform, or "
                "aside_upload_unavailable. "
                "Probe and prefer aside-mcp/aside repl when they are usable."
            )


# ---------------------------------------------------------------------------
# Lessons 14-16: COMPLETE PACKET, RETRIEVAL, AND PUBLIC-SHARE PROOF
# ---------------------------------------------------------------------------


class ReviewPacketIncompleteError(Exception):
    """Raised when a code/evidence review packet omits full source or evidence."""


class RetrievalNotVerifiedError(Exception):
    """Raised when a reviewer cannot prove it retrieved the intended packet."""


class PublicShareNotVerifiedError(Exception):
    """Raised when a share is private, stale, or missing the final response."""


class PacketAttachmentsNotVerifiedError(Exception):
    """Raised when browser attachment chips do not match generated packets."""


def _file_manifest_map(entries: list, label: str) -> dict:
    result = {}
    for entry in entries or []:
        if not isinstance(entry, dict):
            raise ReviewPacketIncompleteError(f"{label} contains a non-object entry")
        path = entry.get("path")
        size = entry.get("size_bytes")
        digest = entry.get("sha256")
        if not path or path in result:
            raise ReviewPacketIncompleteError(
                f"{label} contains a missing or duplicate path: {path!r}"
            )
        if not isinstance(size, int) or size <= 0:
            raise ReviewPacketIncompleteError(
                f"{label} has invalid size_bytes for {path!r}: {size!r}"
            )
        if not isinstance(digest, str) or not _SHA256_PATTERN.fullmatch(digest):
            raise ReviewPacketIncompleteError(
                f"{label} has invalid sha256 for {path!r}: {digest!r}"
            )
        result[path] = {"size_bytes": size, "sha256": digest}
    return result


def _assert_exact_manifest(expected: dict, actual: dict, label: str) -> None:
    if set(expected) != set(actual):
        missing = sorted(set(expected) - set(actual))
        extra = sorted(set(actual) - set(expected))
        raise ReviewPacketIncompleteError(
            f"{label} coverage mismatch: missing={missing}, unexpected={extra}. "
            "A diff/patch is navigation only and never replaces full files."
        )
    mismatched = [path for path in expected if expected[path] != actual[path]]
    if mismatched:
        raise ReviewPacketIncompleteError(
            f"{label} metadata mismatch for {mismatched}: exact byte sizes and "
            "SHA-256 values are required"
        )


def assert_review_packet_complete(packet: dict) -> None:
    """Fail closed unless a PR/evidence packet contains every complete file.

    A patch may be attached as a navigation index, but it cannot satisfy any
    entry in ``full_code_files``. For evidence-bearing reviews, the complete
    raw evidence manifest and a focused checksum-bound review index are both
    required: the former is for auditability, the latter is the semantic
    review target.
    """
    packet = packet or {}
    if packet.get("manifest_source") != "build_review_packets.py/v1":
        raise ReviewPacketIncompleteError(
            "Packet manifest must be generated from the authoritative Git diff "
            "and evidence scan by build_review_packets.py/v1"
        )
    head_sha = packet.get("head_sha") or ""
    if not re.fullmatch(r"[0-9a-f]{40}", head_sha):
        raise ReviewPacketIncompleteError("head_sha must be an exact 40-char SHA")

    review_kind = packet.get("review_kind")
    if review_kind != "pr_with_evidence":
        raise ReviewPacketIncompleteError(
            f"Unsupported review_kind {review_kind!r}; this authoritative "
            "Git-diff packet gate supports pr_with_evidence only. Standalone "
            "documents/evidence use exact direct-attachment inventory plus "
            "retrieval proof; visual reviews use assert_attachment_verified()."
        )
    attachment_names = packet.get("packet_attachment_names") or []
    packet_attachments = packet.get("packet_attachments") or {}
    if (
        not attachment_names
        or set(attachment_names) != set(packet_attachments)
        or any(not isinstance(size, int) or size <= 0 for size in packet_attachments.values())
    ):
        raise ReviewPacketIncompleteError(
            "Generated packet attachment names and exact byte sizes are required"
        )

    authoritative_changed = _file_manifest_map(
        packet.get("authoritative_changed_files"),
        "authoritative_changed_files",
    )
    changed = _file_manifest_map(packet.get("changed_files"), "changed_files")
    full_code = _file_manifest_map(packet.get("full_code_files"), "full_code_files")
    if not authoritative_changed or not changed or not full_code:
        raise ReviewPacketIncompleteError(
            "Every PR review requires authoritative full changed files; "
            "a patch-only packet is invalid"
        )
    patch_paths = [
        path for path in authoritative_changed if path.endswith((".patch", ".diff"))
    ]
    if patch_paths:
        raise ReviewPacketIncompleteError(
            f"Diff/patch paths cannot satisfy full changed files: {patch_paths}"
        )
    _assert_exact_manifest(
        authoritative_changed, changed, "changed_files authority binding"
    )
    _assert_exact_manifest(authoritative_changed, full_code, "full_code_files")

    base_code = _file_manifest_map(packet.get("base_code_files"), "base_code_files")
    diff_index = _file_manifest_map(
        [packet.get("diff_index")] if packet.get("diff_index") else [],
        "diff_index",
    )
    if (
        packet.get("diff_index_attached") is not True
        or not diff_index
        or set(diff_index) != {"base...head.patch"}
    ):
        raise ReviewPacketIncompleteError(
            "PR reviews require exact base-file and diff provenance for "
            "changed/unchanged citations"
        )
    unknown_base_paths = sorted(set(base_code) - set(authoritative_changed))
    if unknown_base_paths:
        raise ReviewPacketIncompleteError(
            f"base_code_files contain paths outside the changed set: {unknown_base_paths}"
        )

    authoritative_evidence = _file_manifest_map(
        packet.get("authoritative_evidence_files"),
        "authoritative_evidence_files",
    )
    expected_evidence = _file_manifest_map(
        packet.get("expected_evidence_files"), "expected_evidence_files"
    )
    full_evidence = _file_manifest_map(
        packet.get("full_evidence_files"), "full_evidence_files"
    )
    if not authoritative_evidence or not expected_evidence or not full_evidence:
        raise ReviewPacketIncompleteError(
            "Evidence reviews require the complete raw /es evidence manifest"
        )
    _assert_exact_manifest(
        authoritative_evidence,
        expected_evidence,
        "expected_evidence_files authority binding",
    )
    _assert_exact_manifest(
        authoritative_evidence, full_evidence, "full_evidence_files"
    )

    index_paths = packet.get("evidence_index_paths") or []
    if not index_paths or "SHA256SUMS.txt" not in index_paths:
        raise ReviewPacketIncompleteError(
            "Evidence reviews require a focused checksum-bound review index"
        )
    unknown_index_paths = sorted(set(index_paths) - set(full_evidence))
    if unknown_index_paths:
        raise ReviewPacketIncompleteError(
            f"evidence_index_paths are absent from the raw bundle: {unknown_index_paths}"
        )


def assert_packet_attachments_verified(expected: dict, reported: dict) -> None:
    """Require the browser composer to show every generated packet by name/size."""
    expected = expected or {}
    reported = reported or {}
    expected_attachments = expected.get("packet_attachments") or {}
    reported_attachments = reported.get("packet_attachments") or {}
    visible_names = reported.get("visible_attachment_names") or []
    if not expected_attachments or reported_attachments != expected_attachments:
        raise PacketAttachmentsNotVerifiedError(
            "Browser packet attachment inventory mismatch: "
            f"expected={expected_attachments!r}, reported={reported_attachments!r}"
        )
    if reported.get("upload_verified") is not True or set(visible_names) != set(
        expected_attachments
    ) or len(visible_names) != len(expected_attachments):
        raise PacketAttachmentsNotVerifiedError(
            "Browser packet attachment names were not visibly verified: "
            f"expected={sorted(expected_attachments)!r}, "
            f"visible={visible_names!r}, "
            f"upload_verified={reported.get('upload_verified')!r}"
        )


def assert_retrieval_verified(expected: dict, reported: dict) -> None:
    """Fail unless a reviewer's post-response retrieval challenge is exact.

    This gate is deliberately separate from ``assert_attachment_verified``:
    the UI can show an uploaded file while the model's active context has
    evicted it, or while the model invents a plausible attachment inventory.
    """
    expected = expected or {}
    reported = reported or {}
    if reported.get("context_retained") is not True:
        note = reported.get("retention_note") or "no affirmative retention proof"
        raise RetrievalNotVerifiedError(
            f"Reviewer context was not retained: {note}. Discard the verdict."
        )

    exact_keys = ("head_sha", "attachment_names", "code_files", "evidence_paths")
    for key in exact_keys:
        expected_value = expected.get(key)
        reported_value = reported.get(key)
        if key in {"attachment_names", "evidence_paths"}:
            matches = set(reported_value or []) == set(expected_value or [])
        else:
            matches = reported_value == expected_value
        if not matches:
            raise RetrievalNotVerifiedError(
                f"Retrieval challenge {key} mismatch: expected={expected_value!r}, "
                f"reported={reported_value!r}. Discard the verdict."
            )

    required_fields = expected.get("required_fields") or {}
    reported_fields = reported.get("required_fields") or {}
    mismatched_fields = {
        key: {"expected": value, "reported": reported_fields.get(key)}
        for key, value in required_fields.items()
        if reported_fields.get(key) != value
    }
    if mismatched_fields:
        raise RetrievalNotVerifiedError(
            f"Retrieval challenge required_fields mismatch: {mismatched_fields}. "
            "Discard the verdict."
        )

    if expected.get("require_changed_and_unchanged_citations") and not (
        reported.get("changed_region_cited")
        and reported.get("unchanged_region_cited")
    ):
        raise RetrievalNotVerifiedError(
            "Retrieval challenge requires citations from changed and unchanged "
            "regions. Discard the verdict."
        )


def assert_public_share_verified(probe: dict) -> None:
    """Fail unless cookie-free public content contains this run's final turn.

    A header-only HTTP 200 proves reachability, not freshness. Conversely, an
    edge-generated curl 403 may coexist with a genuinely public page, so a
    cookie-free browser render containing the unique run marker and final
    verdict is authoritative.
    """
    probe = probe or {}
    url = probe.get("url") or ""
    allowed_share_patterns = (
        r"https://chatgpt\.com/share/[A-Za-z0-9_-]+",
        r"https://(?:g\.co/gemini/share|gemini\.google\.com/share)/[A-Za-z0-9_-]+(?:\?.*)?",
        r"https://(?:www\.)?perplexity\.ai/search/[A-Za-z0-9_-]+(?:\?.*)?",
    )
    if not any(re.fullmatch(pattern, url) for pattern in allowed_share_patterns):
        raise PublicShareNotVerifiedError(
            f"Missing or invalid public vendor share URL: {url!r}"
        )
    if probe.get("authenticated_session_used"):
        raise PublicShareNotVerifiedError(
            "Public share was checked only with an authenticated owner session; "
            "a cookie-free public probe is required"
        )
    if not (
        probe.get("cookie_free_browser_rendered")
        or probe.get("unauthenticated_http_content")
    ):
        raise PublicShareNotVerifiedError(
            "No cookie-free browser or unauthenticated content proof was captured"
        )

    turns = probe.get("public_turns") or []
    if len(turns) < 2:
        raise PublicShareNotVerifiedError(
            "Cookie-free share proof must contain structured conversation turns"
        )
    marker = probe.get("expected_run_marker") or ""
    verdict = probe.get("expected_verdict") or ""
    marker_turns = [
        turn
        for turn in turns
        if turn.get("role") == "user" and marker in (turn.get("content") or "")
    ]
    if not marker or not marker_turns:
        raise PublicShareNotVerifiedError(
            f"Public share is stale or incomplete: current run marker {marker!r} "
            "is absent from a public user retrieval-challenge turn"
        )
    final_turn = turns[-1]
    if final_turn.get("role") != "assistant":
        raise PublicShareNotVerifiedError(
            "Public share does not end with the final assistant response"
        )
    verdict_matches = re.findall(
        r"(?m)^\s*VERDICT:\s*([^\n]+?)\s*$",
        final_turn.get("content") or "",
    )
    final_verdict = verdict_matches[-1] if verdict_matches else ""
    if not verdict or final_verdict != verdict:
        raise PublicShareNotVerifiedError(
            "Public share final assistant verdict mismatch: "
            f"expected={verdict!r}, reported={final_verdict!r}"
        )


# ---------------------------------------------------------------------------
# Lesson 10: VERDICT SCRAPING
# ---------------------------------------------------------------------------

# Labels /web-advice looks for in a scraped DOM tree / response text, in the
# order the 4-section prompt (SKILL.md Step 0b) and the visual-evidence
# prompt (build_visual_prompt below) ask models to emit them.
_KNOWN_LABELS = (
    "OBSERVED TIMELINE",
    "REQUIRED CHECKS",
    "WEB SOURCES",
    "VERDICT",
    "REASONING",
    "RISK",
    "CONFIDENCE",
)

# Matches a label at the start of a line, tolerating:
#   - leading blockquote markers ('>'), bullet dashes, and whitespace
#   - markdown bold/italic markers wrapping the label on either side of the
#     colon (e.g. "**VERDICT:**", "**VERDICT**:", "*VERDICT*:")
#   - a required ':' separator (colon-separated format)
_LABEL_PATTERN = re.compile(
    r"(?im)^[ \t>\-]*\**[ \t]*("
    + "|".join(re.escape(label) for label in _KNOWN_LABELS)
    + r")[ \t]*\**[ \t]*:[ \t]*\**[ \t]*"
)


def _clean_verdict_value(raw: str) -> str:
    """Strip blockquote/markdown noise from a captured field value."""
    lines = []
    for line in raw.splitlines():
        line = line.strip()
        line = re.sub(r"^>+\s*", "", line)  # leading blockquote markers
        lines.append(line)
    text = "\n".join(lines).strip()
    return text.strip("*").strip()


def parse_verdict(tree_text: str) -> dict:
    """Extract structured fields from a scraped model response.

    Tolerates the real-world formats seen in 2026-08-02 runs: plain
    "LABEL: value" lines, markdown-bold labels ("**LABEL:**" or
    "**LABEL**:"), and leading '>' blockquote markers.

    Args:
        tree_text: scraped DOM tree text or raw response text.

    Returns:
        dict keyed by lowercase, underscore-joined label
        (e.g. "verdict", "reasoning", "confidence", "observed_timeline",
        "required_checks", "risk", "web_sources") for whichever labels were
        found. Empty dict if nothing matched or input is empty/falsy.
    """
    if not tree_text:
        return {}

    matches = list(_LABEL_PATTERN.finditer(tree_text))
    result: dict = {}
    for i, match in enumerate(matches):
        label = match.group(1).upper()
        value_start = match.end()
        value_end = matches[i + 1].start() if i + 1 < len(matches) else len(tree_text)
        value = _clean_verdict_value(tree_text[value_start:value_end])
        key = label.lower().replace(" ", "_")
        result[key] = value
    return result


# ---------------------------------------------------------------------------
# Lesson 11: HONEST SEAT ACCOUNTING
# ---------------------------------------------------------------------------


def seat_accounting(seats: dict) -> str:
    """Produce an honest "N-of-M" seat-accounting line.

    Never presents a partial panel as a full one (lesson 11): every missing
    seat is named along with the reason it was unavailable, and the
    in-policy paths already exhausted (if encoded in the reason string after
    a colon) are surfaced verbatim.

    Args:
        seats: dict mapping seat name -> status. Status "ok" means the seat
            answered. Any other status string is treated as the unavailable
            reason, e.g. "unavailable: cloudflare+cookie-hardening".

    Returns:
        A single-line honest accounting string, e.g.:
        "3-of-3: full panel (gemini, perplexity, chatgpt)"
        or, when every seat answered:
        "3-of-3: full panel (gemini, perplexity, chatgpt)"
    """
    total = len(seats)
    ok_seats = [name for name, status in seats.items() if status == "ok"]
    missing = [(name, status) for name, status in seats.items() if status != "ok"]
    n_ok = len(ok_seats)

    if not missing:
        return f"{n_ok}-of-{total}: full panel ({', '.join(ok_seats)})"

    missing_desc = []
    for name, status in missing:
        reason = status
        if ":" in status:
            _, reason = status.split(":", 1)
            reason = reason.strip()
        missing_desc.append(f"{name} because {reason}")

    return f"{n_ok}-of-{total}, missing {', '.join(missing_desc)}"


# ---------------------------------------------------------------------------
# Lesson 6: VISUAL-DESCRIPTION-FIRST PROMPTING
# ---------------------------------------------------------------------------


def build_visual_prompt(claim: str, frame_names: list) -> str:
    """Build the description-FIRST visual-evidence review prompt (lesson 6).

    Models that cannot ingest video (Perplexity) CAN ingest images.
    The correct prompt shape demands, in this fixed order:
      1. literal pixel description of each frame (before any verdict)
      2. what changed between frames
      3. the verdict
      4. what would change the verdict

    A model describing something not present in a frame is itself a finding
    — Step 1 exists specifically to surface that.

    Args:
        claim: the claim under review (e.g. "the sprite moves during the
            charge beat").
        frame_names: ordered list of frame filenames provided to the model.

    Returns:
        The full prompt string, sections in the order above.
    """
    frame_list = "\n".join(f"- {name}" for name in frame_names)

    return f"""You are reviewing frames of visual evidence for the following claim:

CLAIM: {claim}

Frames provided (in order):
{frame_list}

Step 1 — DESCRIBE (do this FIRST, before any verdict):
For EACH frame listed above, describe literally what you see. Report the \
pixels, shapes, colors, positions, and any on-screen text exactly as \
rendered. Do NOT infer intent and do NOT assume what "should" be there — \
describe only what is visibly present in that specific image. A \
description of something not actually present in the frame is itself a \
finding, so be precise.

Step 2 — WHAT CHANGED:
Compare the frames pairwise in the order given. State precisely what \
changed between each consecutive pair of frames (position, color, text, \
presence/absence of elements). If nothing changed between two frames, say \
so explicitly.

Step 3 — VERDICT:
Based ONLY on your answers to Step 1 and Step 2 above, state your verdict \
on whether the claim is supported by the frames.
VERDICT: MET | NOT MET | PARTIAL
REASONING: cite the specific frame(s) and pixel-level observation(s) from \
Step 1/2 that justify this verdict
CONFIDENCE: high | medium | low

Step 4 — WHAT WOULD CHANGE YOUR VERDICT:
State specifically what you would need to see in the frames to change your \
verdict (e.g. a different pixel state in a named frame, a different \
frame-to-frame delta)."""


# ---------------------------------------------------------------------------
# Lesson 12: ATTACHMENT VERIFICATION (bead wc-kjny, 2026-08-02 multi-vendor incident)
# ---------------------------------------------------------------------------


class AttachmentNotVerifiedError(Exception):
    """Raised when an upload action produced no affirmative proof of attachment.

    Fixes the 2026-08-02 multi-vendor incident (bead wc-kjny): a
    `page.locator('input[type="file"]').first()` call against a vendor page
    that exposes MULTIPLE `input[type="file"]` elements silently matched
    the wrong one. `set_input_files()` threw no exception and the caller
    logged "files set", but `document.querySelectorAll('img')` afterward
    showed zero uploaded images (only the vendor's profile avatar and a
    cookie-consent-banner logo). The model then produced a fully-formatted
    DESCRIPTION and `VERDICT: NOT SUPPORTED` for content that does not
    exist anywhere in the app (a "9:41" status bar, a "hooded figure", "the
    scent of ozone lingering", a "Roll Initiative" button) and claimed 2
    frames were pixel-identical although 3 were referenced -- a complete,
    confident, internally-consistent fabrication with no signal from the
    outside that anything was wrong.

    "No exception was thrown" and "the call logged success" are NEVER
    sufficient proof of a successful upload. This exception is the gate:
    `assert_attachment_verified()` must return cleanly BEFORE any prompt
    referencing uploaded frame/image content is submitted to a model, and
    BEFORE any response to that prompt is recorded as an image-grounded
    verdict.
    """


# Provider-attachment-CDN host substrings, verified 2026-08-02 real runs.
# Deliberately scoped to hosts that serve UPLOADED attachment content, not
# general avatar/profile-picture hosts (e.g. a plain googleusercontent.com
# avatar URL is intentionally excluded -- an avatar existing is not proof of
# an attachment). Extend this list as more providers are verified.
_ATTACHMENT_CDN_HOST_PATTERNS = (
    "oaiusercontent.com",
    "files.oaiusercontent.com",
    "pplx-res.cloudinary.com",
)

# Matches an explicit positive "N attachment(s)" / "N file(s) attached"
# indicator, e.g. Perplexity's "3 attachments" pill (proof artifact
# webvisual_us017_perplexity_response.jpeg, 2026-08-02). "0 attachments" or
# "no files attached" must NOT match -- the leading [1-9] enforces a
# positive count.
_ATTACHMENT_INDICATOR_PATTERN = re.compile(
    r"(?i)\b([1-9]\d*)\s+(?:attachment|file)s?\b(?:\s+attached)?"
)


def _is_attachment_cdn_url(url: str) -> bool:
    if not url:
        return False
    lowered = url.lower()
    return any(host in lowered for host in _ATTACHMENT_CDN_HOST_PATTERNS)


def assert_attachment_verified(dom_probe_result: dict) -> None:
    """Raise AttachmentNotVerifiedError unless an upload is affirmatively proven.

    Call this AFTER any upload action and BEFORE submitting a prompt that
    references the uploaded frame/image content, and again before recording
    any response as an image-grounded verdict. "The upload call didn't
    throw" is explicitly NOT one of the accepted signals -- see
    AttachmentNotVerifiedError's docstring for the exact incident this
    fixes.

    Args:
        dom_probe_result: dict describing what was observed in the DOM
            immediately after the upload action, with any subset of these
            keys (missing/falsy = no evidence for that signal):
              - "new_img_urls": list[str] of <img src> values that appeared
                in the composer/attachment-preview area SINCE the upload
                action. Do NOT pass a raw page-wide
                `querySelectorAll('img')` snapshot here -- that is exactly
                what fooled the caller in the 2026-08-02 incident, because
                it is non-empty BEFORE and AFTER a failed upload (it counts
                the model's own profile avatar and, on some sites, a
                cookie-consent-banner logo). Diff a pre-upload and
                post-upload `querySelectorAll('img')` src list, or scope
                the selector to the composer's attachment-thumbnail
                container, before passing this field.
              - "attachment_cdn_urls": list[str] of any URLs observed (img
                src or network requests) after the upload action. Matched
                against known provider attachment-CDN host patterns
                (oaiusercontent.com, pplx-res.cloudinary.com, ...).
              - "attachment_indicator_text": str -- text scraped near the
                composer, e.g. Perplexity's "3 attachments" pill. Checked
                for an explicit positive "N attachment(s)"/"N file(s)
                attached" count.

    Raises:
        AttachmentNotVerifiedError: if none of the three signals above is
        present.
    """
    probe = dom_probe_result or {}

    new_img_urls = [u for u in (probe.get("new_img_urls") or []) if u]
    cdn_urls = probe.get("attachment_cdn_urls") or []
    matched_cdn_urls = [u for u in cdn_urls if _is_attachment_cdn_url(u)]
    indicator_text = probe.get("attachment_indicator_text") or ""
    indicator_match = _ATTACHMENT_INDICATOR_PATTERN.search(indicator_text)

    if new_img_urls or matched_cdn_urls or indicator_match:
        return

    raise AttachmentNotVerifiedError(
        "Attachment NOT verified before prompting/recording a verdict: "
        f"new_img_urls={new_img_urls!r} (0 new attachment-area <img> "
        f"elements), attachment_cdn_urls matched 0 of {len(cdn_urls)} "
        "observed URL(s) against known provider CDN hosts, and "
        f"attachment_indicator_text={indicator_text!r} has no explicit "
        "positive 'N attachment(s)'/'N file(s) attached' count. A "
        "silently-failed upload (no exception, a logged 'files set' "
        "message, a page.locator(...).first() that grabbed the wrong one "
        "of multiple file inputs) is INDISTINGUISHABLE from a working one "
        "at every layer except this check -- see "
        "AttachmentNotVerifiedError.__doc__ for the exact 2026-08-02 "
        "multi-vendor incident this prevents. DISCARD any response "
        "obtained without a passing assert_attachment_verified() call; "
        "do not record its verdict, and do not submit a prompt referencing "
        "image content until this passes."
    )


# ---------------------------------------------------------------------------
# Lesson 13: FRAME ORDER VERIFICATION (bead wc-kjny, Perplexity 2026-08-02)
# ---------------------------------------------------------------------------


def verify_frame_order(prompt_frame_names: list, model_reported_order: list) -> dict:
    """Compare the frame order a prompt declared against what a model reported.

    A model can read every frame's pixels correctly and STILL discuss them
    in the wrong sequence -- this measurably weakens its verdict even
    though nothing it said about any single frame was individually false
    (2026-08-02: Perplexity's own "Frame 1/2/3" labels did not match the
    upload order `[presend, thinking, resolved]` -- it labeled `thinking`
    as "Frame 1" and `presend` as "Frame 2" -- which scrambled its causal
    narrative and landed it on `VERDICT: PARTIALLY SUPPORTED` where the
    other vendors reached `VERDICT: SUPPORTED` on the identical underlying
    evidence, read in the correct order). Call this after scraping a
    model's per-frame description labels and before trusting its "what
    changed between frames" narrative.

    Args:
        prompt_frame_names: ordered list of frame names/filenames as sent
            in the prompt (the ground truth upload order), e.g.
            ["US-017_frame_presend.png", "US-017_frame_thinking.png",
             "US-017_frame_resolved.png"].
        model_reported_order: ordered list of frame names/labels as the
            model referenced them in its response, in the order it
            discussed them.

    Returns:
        dict with:
          - "match": bool -- True iff the reported order exactly equals the
            prompt order (same names, same positions, same count).
          - "prompt_order": list[str] -- echo of prompt_frame_names.
          - "reported_order": list[str] -- echo of model_reported_order.
          - "missing_frames": list[str] -- frames sent in the prompt but
            never referenced by the model at all.
          - "extra_frames": list[str] -- names the model referenced that
            were not part of the frames actually sent (hallucinated frame
            names/labels).
          - "reordered_frames": list[tuple[str, int, int]] -- (frame_name,
            prompt_index, reported_index) for every frame present in BOTH
            lists but at a different position -- this is exactly the case
            that produced Perplexity's silent verdict downgrade: every
            frame present, none hallucinated, just discussed out of order.
    """
    prompt_order = list(prompt_frame_names or [])
    reported_order = list(model_reported_order or [])

    prompt_index = {name: i for i, name in enumerate(prompt_order)}
    reported_index = {name: i for i, name in enumerate(reported_order)}

    missing_frames = [n for n in prompt_order if n not in reported_index]
    extra_frames = [n for n in reported_order if n not in prompt_index]

    reordered_frames = [
        (name, prompt_index[name], reported_index[name])
        for name in prompt_order
        if name in reported_index and reported_index[name] != prompt_index[name]
    ]

    match = not missing_frames and not extra_frames and not reordered_frames

    return {
        "match": match,
        "prompt_order": prompt_order,
        "reported_order": reported_order,
        "missing_frames": missing_frames,
        "extra_frames": extra_frames,
        "reordered_frames": reordered_frames,
    }


def main(argv: list[str] | None = None) -> int:
    """Run deterministic transport guards from shell-driven workflows."""
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Validate /web-advice transport policy")
    subparsers = parser.add_subparsers(dest="command", required=True)
    transport_parser = subparsers.add_parser("assert-transport")
    transport_parser.add_argument("mechanism")
    transport_parser.add_argument(
        "--fallback-reason",
        choices=sorted(_FALLBACK_REASONS),
    )
    args = parser.parse_args(argv)

    try:
        assert_allowed_transport(args.mechanism, args.fallback_reason)
    except WebAdviceHardFail as exc:
        print(str(exc), file=sys.stderr)
        return 2

    reason = f" fallback_reason={args.fallback_reason}" if args.fallback_reason else ""
    print(
        f"allowed /web-advice transport: {_normalize_mechanism(args.mechanism)}"
        f"{reason}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
