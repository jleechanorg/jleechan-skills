"""Tests for web_advice_transport.py — the deterministic core of /web-advice.

Run from this directory: `python3 -m pytest test_web_advice_transport.py -q`.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from web_advice_transport import (
    AttachmentNotVerifiedError,
    PacketAttachmentsNotVerifiedError,
    PublicShareNotVerifiedError,
    RetrievalNotVerifiedError,
    ReviewPacketIncompleteError,
    WebAdviceHardFail,
    assert_allowed_transport,
    assert_attachment_verified,
    assert_packet_attachments_verified,
    assert_public_share_verified,
    assert_retrieval_verified,
    assert_review_packet_complete,
    build_visual_prompt,
    is_banned_substitute,
    parse_verdict,
    resolve_transport_ladder,
    seat_accounting,
    verify_frame_order,
)


def _file(path, size, digest=None):
    return {
        "path": path,
        "size_bytes": size,
        "sha256": digest or ("a" * 64),
    }


def _complete_pr_packet():
    changed = [
        _file("mvp_site/llm_providers/gemini_provider.py", 231799),
        _file("mvp_site/llm_service.py", 538015),
        _file(
            "mvp_site/tests/test_bq_streaming_response_parts_gemini.py",
            38573,
        ),
        _file("mvp_site/tests/test_cache_hit_rate_denominator.py", 4681),
        _file("mvp_site/tests/test_debug_mode_implicit_cache.py", 5183),
        _file(
            "testing_mcp/test_gemini_implicit_cache_utilization_es.py",
            24035,
        ),
    ]
    evidence = [
        _file("README.md", 1000),
        _file("SHA256SUMS.txt", 2000),
        _file("verification_report.json", 3000),
        _file("implicit_cache_utilization_bq.json", 4000),
        _file("raw/bq_readback.json", 5000),
    ]
    return {
        "manifest_source": "build_review_packets.py/v1",
        "review_kind": "pr_with_evidence",
        "head_sha": "4ea801ac830cdef9bdf56695bd060ebed55fde93",
        "changed_files": changed,
        "authoritative_changed_files": list(changed),
        "full_code_files": list(changed),
        "base_code_files": [
            _file("mvp_site/llm_providers/gemini_provider.py", 230000),
            _file("mvp_site/llm_service.py", 537000),
        ],
        "diff_index": _file("base...head.patch", 12000),
        "expected_evidence_files": evidence,
        "authoritative_evidence_files": list(evidence),
        "full_evidence_files": list(evidence),
        "evidence_index_paths": [
            "README.md",
            "SHA256SUMS.txt",
            "verification_report.json",
            "implicit_cache_utilization_bq.json",
        ],
        "diff_index_attached": True,
        "packet_attachment_names": [
            "PR9329_FULL_CODE_FILES.txt",
            "PR9329_BASE_CODE_FILES_AND_DIFF.txt",
            "PR9329_ES_REVIEW_INDEX.txt",
            "PR9329_FULL_ES_EVIDENCE.txt",
        ],
        "packet_attachments": {
            "PR9329_FULL_CODE_FILES.txt": 843548,
            "PR9329_BASE_CODE_FILES_AND_DIFF.txt": 855548,
            "PR9329_ES_REVIEW_INDEX.txt": 66027,
            "PR9329_FULL_ES_EVIDENCE.txt": 52173051,
        },
    }


# ---------------------------------------------------------------------------
# resolve_transport_ladder
# ---------------------------------------------------------------------------


class TestResolveTransportLadder:
    def test_hard_fail_when_all_probes_false(self):
        probes = {
            "aside_mcp": False,
            "aside_repl": False,
            "chrome_extension": False,
            "cdp_port": False,
            "chrome_cookies": False,
        }
        with pytest.raises(WebAdviceHardFail):
            resolve_transport_ladder(probes)

    def test_hard_fail_when_probes_dict_is_empty(self):
        with pytest.raises(WebAdviceHardFail):
            resolve_transport_ladder({})

    def test_hard_fail_message_names_no_substitution(self):
        with pytest.raises(WebAdviceHardFail) as exc_info:
            resolve_transport_ladder({})
        message = str(exc_info.value)
        assert "provider" in message.lower()
        assert "subagent" in message.lower()
        assert "websearch" in message.lower() or "web search" in message.lower()

    def test_prefers_aside_mcp_when_all_true(self):
        probes = {
            "aside_mcp": True,
            "aside_repl": True,
            "chrome_extension": True,
            "cdp_port": True,
            "chrome_cookies": True,
        }
        assert resolve_transport_ladder(probes) == "aside_mcp"

    def test_falls_back_to_aside_repl(self):
        probes = {
            "aside_mcp": False,
            "aside_repl": True,
            "chrome_extension": True,
            "cdp_port": True,
            "chrome_cookies": True,
        }
        assert resolve_transport_ladder(probes) == "aside_repl"

    def test_prefers_verified_chrome_headless_cookie_fallback_when_aside_is_down(self):
        probes = {
            "aside_mcp": False,
            "aside_repl": False,
            "chrome_headless_cookies": True,
            "playwright_mcp": True,
            "chrome_headless_cdp": True,
            "chrome_extension": True,
        }
        assert resolve_transport_ladder(probes) == "chrome_headless_cookies"

    @pytest.mark.parametrize(
        "probe",
        [
            "chrome_headless_cookies",
            "playwright_mcp",
            "chrome_headless_cdp",
            "chrome_extension",
        ],
    )
    def test_real_browser_backup_satisfies_ladder_when_aside_is_down(self, probe):
        assert resolve_transport_ladder({probe: True}) == probe

    def test_missing_keys_with_no_live_transport_still_hard_fails(self):
        probes = {"chrome_cookies": False}
        with pytest.raises(WebAdviceHardFail):
            resolve_transport_ladder(probes)


# ---------------------------------------------------------------------------
# is_banned_substitute
# ---------------------------------------------------------------------------


class TestIsBannedSubstitute:
    @pytest.mark.parametrize(
        "mechanism",
        [
            "gemini_files_api",
            "openai_api",
            "xai_api",
            "provider_api",
            "chatgpt_api",
        ],
    )
    def test_provider_apis_are_banned(self, mechanism):
        assert is_banned_substitute(mechanism) is True

    @pytest.mark.parametrize("mechanism", ["agy", "codex", "codex_cli", "gemini_cli", "cli_model"])
    def test_cli_models_are_banned(self, mechanism):
        assert is_banned_substitute(mechanism) is True

    @pytest.mark.parametrize(
        "mechanism",
        ["aside_inference", "aside_exec", "aside_nl_agent", "aside_ultrabrowse", "aside_ai"],
    )
    def test_aside_inference_is_banned(self, mechanism):
        assert is_banned_substitute(mechanism) is True

    @pytest.mark.parametrize("mechanism", ["subagent", "subagents", "in_session_subagent"])
    def test_subagents_are_banned(self, mechanism):
        assert is_banned_substitute(mechanism) is True

    @pytest.mark.parametrize("mechanism", ["websearch", "web_search", "webfetch", "web_fetch"])
    def test_websearch_and_webfetch_are_banned(self, mechanism):
        assert is_banned_substitute(mechanism) is True

    @pytest.mark.parametrize(
        "mechanism",
        [
            "aside_mcp",
            "aside_repl",
        ],
    )
    def test_real_browser_transports_are_not_banned(self, mechanism):
        assert is_banned_substitute(mechanism) is False

    @pytest.mark.parametrize(
        "mechanism,expected",
        [
            ("Gemini Files API", True),
            ("OpenAI-API", True),
            ("  Agy  ", True),
            ("WebSearch", True),
            ("aside exec -m", True),
            ("aside --effort ultrabrowse", True),
            ("Aside MCP", False),
        ],
    )
    def test_case_and_separator_insensitive(self, mechanism, expected):
        assert is_banned_substitute(mechanism) is expected


class TestAssertAllowedTransport:
    @pytest.mark.parametrize("mechanism", ["aside_mcp", "aside repl"])
    def test_accepts_only_aside_browser_automation(self, mechanism):
        assert_allowed_transport(mechanism)

    @pytest.mark.parametrize(
        "mechanism",
        [
            "chrome_headless_cookies",
            "playwright_mcp",
            "chrome_headless_cdp",
            "chrome_extension",
        ],
    )
    def test_accepts_browser_backup_when_aside_is_unavailable(self, mechanism):
        assert_allowed_transport(mechanism, fallback_reason="aside_unavailable")

    def test_accepts_browser_backup_on_unsupported_platform(self):
        assert_allowed_transport(
            "playwright_mcp", fallback_reason="unsupported_platform"
        )

    @pytest.mark.parametrize(
        "mechanism",
        [
            "chrome_headless_cookies",
            "playwright_mcp",
            "chrome_headless_cdp",
            "chrome_extension",
        ],
    )
    def test_rejects_browser_backup_without_fallback_reason(self, mechanism):
        with pytest.raises(WebAdviceHardFail):
            assert_allowed_transport(mechanism)

    @pytest.mark.parametrize(
        "mechanism",
        ["aside exec -m", "aside --effort ultrabrowse", "codex", "openai_api"],
    )
    def test_rejects_non_browser_substitutes_even_with_fallback_reason(self, mechanism):
        with pytest.raises(WebAdviceHardFail):
            assert_allowed_transport(mechanism, fallback_reason="aside_unavailable")

    def test_cli_guard_enforces_transport_before_labeling(self):
        script = Path(__file__).with_name("web_advice_transport.py")
        allowed = subprocess.run(
            [sys.executable, str(script), "assert-transport", "aside repl"],
            capture_output=True,
            text=True,
        )
        rejected = subprocess.run(
            [sys.executable, str(script), "assert-transport", "aside exec -m"],
            capture_output=True,
            text=True,
        )
        fallback = subprocess.run(
            [
                sys.executable,
                str(script),
                "assert-transport",
                "chrome_headless_cookies",
                "--fallback-reason",
                "aside_unavailable",
            ],
            capture_output=True,
            text=True,
        )

        assert allowed.returncode == 0
        assert fallback.returncode == 0
        assert rejected.returncode != 0
        assert "forbidden" in rejected.stderr.lower()


class TestE2ESmoke:
    def test_probes_only_aside_repl_browser_transport(self, tmp_path):
        fake_bin = tmp_path / "bin"
        fake_bin.mkdir()
        aside = fake_bin / "aside"
        aside.write_text("#!/usr/bin/env bash\nprintf '2\\n'\n")
        aside.chmod(0o755)

        script = Path(__file__).with_name("e2e_smoke.sh")
        env = os.environ.copy()
        env["HOME"] = str(tmp_path)
        env["PATH"] = f"{fake_bin}:/usr/bin:/bin"
        result = subprocess.run(["bash", str(script)], capture_output=True, text=True, env=env)

        assert result.returncode == 0
        assert "Aside REPL browser" in result.stdout
        assert "Chrome" not in result.stdout
        assert "cookie" not in result.stdout.lower()

    def test_falls_back_to_portable_chrome_headless_probe_when_aside_is_missing(
        self, tmp_path
    ):
        fake_bin = tmp_path / "bin"
        fake_bin.mkdir()
        chrome = fake_bin / "google-chrome"
        chrome.write_text(
            "#!/usr/bin/env bash\n"
            "printf '<html><title>Example Domain</title></html>\\n'\n"
        )
        chrome.chmod(0o755)

        script = Path(__file__).with_name("e2e_smoke.sh")
        env = os.environ.copy()
        env["HOME"] = str(tmp_path)
        env["PATH"] = f"{fake_bin}:/usr/bin:/bin"
        result = subprocess.run(
            ["bash", str(script)], capture_output=True, text=True, env=env
        )

        assert result.returncode == 0
        assert "Aside REPL browser: DOWN" in result.stdout
        assert "Chrome headless browser: UP" in result.stdout


# ---------------------------------------------------------------------------
# parse_verdict
# ---------------------------------------------------------------------------


class TestParseVerdict:
    def test_empty_string_returns_empty_dict(self):
        assert parse_verdict("") == {}

    def test_none_like_falsy_returns_empty_dict(self):
        assert parse_verdict(None) == {}

    def test_plain_colon_separated_format(self):
        text = (
            "VERDICT: APPROVED with notes\n"
            "REASONING: The design is sound and tests cover the edge cases.\n"
            "CONFIDENCE: high\n"
        )
        result = parse_verdict(text)
        assert result["verdict"] == "APPROVED with notes"
        assert (
            result["reasoning"]
            == "The design is sound and tests cover the edge cases."
        )
        assert result["confidence"] == "high"

    def test_markdown_bold_format_colon_inside_bold(self):
        text = (
            "**VERDICT:** CHANGES REQUESTED\n"
            "**REASONING:** Missing null check on line 42.\n"
            "**CONFIDENCE:** medium\n"
        )
        result = parse_verdict(text)
        assert result["verdict"] == "CHANGES REQUESTED"
        assert result["reasoning"] == "Missing null check on line 42."
        assert result["confidence"] == "medium"

    def test_markdown_bold_format_colon_outside_bold(self):
        text = (
            "**VERDICT**: REJECTED\n"
            "**REASONING**: Breaks backward compatibility.\n"
            "**CONFIDENCE**: low\n"
        )
        result = parse_verdict(text)
        assert result["verdict"] == "REJECTED"
        assert result["reasoning"] == "Breaks backward compatibility."
        assert result["confidence"] == "low"

    def test_leading_blockquote_marker_format(self):
        text = (
            "> VERDICT: APPROVED\n"
            "> REASONING: Solid implementation with good coverage.\n"
            "> CONFIDENCE: high\n"
        )
        result = parse_verdict(text)
        assert result["verdict"] == "APPROVED"
        assert result["reasoning"] == "Solid implementation with good coverage."
        assert result["confidence"] == "high"

    def test_observed_timeline_and_required_checks_when_present(self):
        text = (
            "OBSERVED TIMELINE: frame1 idle, frame2 mid-swing, frame3 landed\n"
            "REQUIRED CHECKS: pixel delta > 0 between frame1 and frame3\n"
            "VERDICT: MET\n"
            "CONFIDENCE: high\n"
        )
        result = parse_verdict(text)
        assert (
            result["observed_timeline"]
            == "frame1 idle, frame2 mid-swing, frame3 landed"
        )
        assert (
            result["required_checks"]
            == "pixel delta > 0 between frame1 and frame3"
        )
        assert result["verdict"] == "MET"

    def test_missing_fields_only_returns_present_ones(self):
        text = "VERDICT: APPROVED\n"
        result = parse_verdict(text)
        assert result == {"verdict": "APPROVED"}
        assert "reasoning" not in result
        assert "confidence" not in result

    def test_no_recognized_labels_returns_empty_dict(self):
        text = "This is just some prose with no structured fields at all."
        assert parse_verdict(text) == {}

    def test_multiline_reasoning_captured_up_to_next_label(self):
        text = (
            "VERDICT: APPROVED with notes\n"
            "REASONING: First sentence of reasoning.\n"
            "Second sentence continues here.\n"
            "CONFIDENCE: medium\n"
        )
        result = parse_verdict(text)
        assert "First sentence of reasoning." in result["reasoning"]
        assert "Second sentence continues here." in result["reasoning"]
        assert result["confidence"] == "medium"


# ---------------------------------------------------------------------------
# seat_accounting
# ---------------------------------------------------------------------------


class TestSeatAccounting:
    def test_full_panel_all_ok(self):
        seats = {"gemini": "ok", "perplexity": "ok", "chatgpt": "ok"}
        result = seat_accounting(seats)
        assert result.startswith("3-of-3")
        assert "full panel" in result
        for name in seats:
            assert name in result

    def test_missing_one_seat_names_it_and_the_reason(self):
        seats = {
            "gemini": "ok",
            "perplexity": "ok",
            "chatgpt": "unavailable: cloudflare+cookie-hardening",
        }
        result = seat_accounting(seats)
        assert result.startswith("2-of-3")
        assert "chatgpt" in result
        assert "cloudflare+cookie-hardening" in result
        assert "because" in result

    def test_never_reports_partial_panel_as_full(self):
        seats = {
            "gemini": "ok",
            "chatgpt": "unavailable: login required",
        }
        result = seat_accounting(seats)
        assert "full panel" not in result
        assert result.startswith("1-of-2")

    def test_missing_multiple_seats_all_named(self):
        seats = {
            "gemini": "ok",
            "perplexity": "unavailable: captcha",
            "chatgpt": "unavailable: cloudflare+cookie-hardening",
        }
        result = seat_accounting(seats)
        assert result.startswith("1-of-3")
        assert "perplexity because captcha" in result
        assert "chatgpt because cloudflare+cookie-hardening" in result

    def test_zero_seats_available(self):
        seats = {"gemini": "unavailable: down", "perplexity": "unavailable: down"}
        result = seat_accounting(seats)
        assert result.startswith("0-of-2")


# ---------------------------------------------------------------------------
# build_visual_prompt
# ---------------------------------------------------------------------------


class TestBuildVisualPrompt:
    def test_description_step_precedes_verdict_step(self):
        prompt = build_visual_prompt(
            "the sprite moves during the charge beat", ["frame1.png", "frame2.png"]
        )
        describe_idx = prompt.index("DESCRIBE")
        verdict_idx = prompt.index("VERDICT:")
        assert describe_idx < verdict_idx

    def test_full_step_ordering_describe_change_verdict_would_change(self):
        prompt = build_visual_prompt("claim text", ["a.png", "b.png", "c.png"])
        describe_idx = prompt.index("DESCRIBE")
        changed_idx = prompt.index("WHAT CHANGED")
        verdict_idx = prompt.index("Step 3")
        would_change_idx = prompt.index("WHAT WOULD CHANGE YOUR VERDICT")
        assert describe_idx < changed_idx < verdict_idx < would_change_idx

    def test_includes_claim_text(self):
        prompt = build_visual_prompt("dragon breathes fire on beat 3", ["f1.png"])
        assert "dragon breathes fire on beat 3" in prompt

    def test_includes_all_frame_names_in_order(self):
        frames = ["intro.png", "mid.png", "outro.png"]
        prompt = build_visual_prompt("claim", frames)
        last_idx = -1
        for frame in frames:
            assert frame in prompt
            idx = prompt.index(frame)
            assert idx > last_idx
            last_idx = idx

    def test_instructs_literal_pixel_description_not_inference(self):
        prompt = build_visual_prompt("claim", ["frame1.png"])
        assert "do not infer" in prompt.lower() or "do not assume" in prompt.lower()
        assert "pixels" in prompt.lower()

    def test_empty_frame_list_still_produces_valid_prompt(self):
        prompt = build_visual_prompt("claim with no frames", [])
        assert "CLAIM: claim with no frames" in prompt
        assert "DESCRIBE" in prompt


# ---------------------------------------------------------------------------
# assert_attachment_verified (bead wc-kjny — 2026-08-02 attachment-verification incident)
# ---------------------------------------------------------------------------


class TestAssertAttachmentVerified:
    def test_raises_when_probe_is_empty(self):
        with pytest.raises(AttachmentNotVerifiedError):
            assert_attachment_verified({})

    def test_raises_when_probe_is_none(self):
        with pytest.raises(AttachmentNotVerifiedError):
            assert_attachment_verified(None)

    def test_raises_when_only_avatar_and_cookie_banner_logo_present(self):
        # This is the exact false-positive trap from the incident: a raw
        # page-wide querySelectorAll('img') is non-empty even when the
        # upload silently failed, because it counts the model's own
        # profile avatar and a cookie-consent-banner logo. The caller must
        # scope new_img_urls to the attachment-preview area, NOT pass a
        # raw page-wide scan — an empty/absent new_img_urls here (as it
        # would be for those two unrelated images) must still raise.
        probe = {
            "new_img_urls": [],
            "attachment_cdn_urls": [
                "https://chatgpt.com/static/avatar.png",
                "https://consent.cookiebot.com/logo.svg",
            ],
            "attachment_indicator_text": "",
        }
        with pytest.raises(AttachmentNotVerifiedError):
            assert_attachment_verified(probe)

    def test_passes_when_new_img_url_present(self):
        probe = {"new_img_urls": ["https://files.oaiusercontent.com/abc123.png"]}
        assert assert_attachment_verified(probe) is None

    def test_passes_when_provider_cdn_url_present(self):
        probe = {
            "new_img_urls": [],
            "attachment_cdn_urls": ["https://oaiusercontent.com/uploads/frame1.png"],
        }
        assert assert_attachment_verified(probe) is None

    @pytest.mark.parametrize(
        "cdn_url",
        [
            "https://files.oaiusercontent.com/abc",
            "https://oaiusercontent.com/abc",
            "https://pplx-res.cloudinary.com/image/upload/frame2.jpg",
        ],
    )
    def test_passes_for_each_known_provider_cdn_host(self, cdn_url):
        probe = {"attachment_cdn_urls": [cdn_url]}
        assert assert_attachment_verified(probe) is None

    def test_raises_when_cdn_urls_present_but_none_match_known_hosts(self):
        probe = {
            "attachment_cdn_urls": [
                "https://chatgpt.com/static/avatar.png",
                "https://example.com/unrelated.png",
            ]
        }
        with pytest.raises(AttachmentNotVerifiedError):
            assert_attachment_verified(probe)

    def test_passes_when_explicit_attachment_indicator_present(self):
        # Perplexity's real "3 attachments" pill (proof artifact
        # webvisual_us017_perplexity_response.jpeg, 2026-08-02).
        probe = {"attachment_indicator_text": "3 attachments"}
        assert assert_attachment_verified(probe) is None

    @pytest.mark.parametrize(
        "indicator_text",
        ["1 attachment", "2 files attached", "5 Attachments", "3 files"],
    )
    def test_passes_for_various_indicator_text_phrasings(self, indicator_text):
        probe = {"attachment_indicator_text": indicator_text}
        assert assert_attachment_verified(probe) is None

    @pytest.mark.parametrize(
        "indicator_text",
        ["0 attachments", "no files attached", "attachments: none", ""],
    )
    def test_raises_for_zero_or_absent_indicator_text(self, indicator_text):
        probe = {"attachment_indicator_text": indicator_text}
        with pytest.raises(AttachmentNotVerifiedError):
            assert_attachment_verified(probe)

    def test_error_message_names_the_failed_signals_not_generic(self):
        with pytest.raises(AttachmentNotVerifiedError) as exc_info:
            assert_attachment_verified(
                {"attachment_indicator_text": "cookie banner dismissed"}
            )
        message = str(exc_info.value)
        assert "new_img_urls" in message
        assert "attachment_cdn_urls" in message
        assert "attachment_indicator_text" in message

    def test_error_message_warns_no_exception_is_not_proof(self):
        with pytest.raises(AttachmentNotVerifiedError) as exc_info:
            assert_attachment_verified({})
        message = str(exc_info.value).lower()
        assert "no exception" in message or "files set" in message

    def test_pins_the_attachment_verification_failure_shape(self):
        # Reproduces the real 2026-08-02 probe state verbatim: a vendor
        # page's first upload attempt used page.locator('input[type="file"]')
        # .first() against a page with SIX file inputs, grabbed the wrong
        # one, set_input_files() threw no exception and logged "files
        # set", and document.querySelectorAll('img') afterward showed
        # only the vendor's own avatar + a cookie-consent-banner logo —
        # zero uploaded images. The model still returned a confident, fully
        # formatted VERDICT: NOT SUPPORTED describing a "9:41" status
        # bar, a "hooded figure", and a "Roll Initiative" button — none
        # of which exist in the app or the source frames. The lesson is
        # vendor-agnostic — any chat UI with multiple file inputs can
        # reproduce it — so this pin uses a generic vendor URL rather than
        # a real one.
        attachment_failure_probe = {
            "new_img_urls": [],
            "attachment_cdn_urls": [
                "https://vendor.example.com/static/profile-avatar.png",
                "https://consent.cookiebot.com/uc.js",
            ],
            "attachment_indicator_text": "",
            # informational-only fields a real caller might also capture;
            # must NOT be treated as proof by themselves
            "upload_locator_used": 'input[type="file"]:first',
            "file_input_count_on_page": 6,
            "set_input_files_exception": None,
            "log_message": "files set",
        }
        with pytest.raises(AttachmentNotVerifiedError):
            assert_attachment_verified(attachment_failure_probe)


# ---------------------------------------------------------------------------
# verify_frame_order (bead wc-kjny — Perplexity 2026-08-02)
# ---------------------------------------------------------------------------


class TestVerifyFrameOrder:
    def test_exact_match_returns_match_true(self):
        frames = ["frame1.png", "frame2.png", "frame3.png"]
        result = verify_frame_order(frames, frames)
        assert result["match"] is True
        assert result["missing_frames"] == []
        assert result["extra_frames"] == []
        assert result["reordered_frames"] == []

    def test_pins_the_exact_perplexity_failure_shape(self):
        # Reproduces the real 2026-08-02 US-017 upload: prompt order was
        # [presend, thinking, resolved]. Perplexity read every frame's
        # pixels correctly but labeled `thinking` as its "Frame 1" and
        # `presend` as its "Frame 2" — every frame present, none
        # hallucinated, just discussed out of order. This measurably
        # weakened its verdict to PARTIALLY SUPPORTED vs. the SUPPORTED
        # that the other vendors reached reading the same evidence in order.
        prompt_order = [
            "US-017_frame_presend.png",
            "US-017_frame_thinking.png",
            "US-017_frame_resolved.png",
        ]
        perplexity_reported_order = [
            "US-017_frame_thinking.png",
            "US-017_frame_presend.png",
            "US-017_frame_resolved.png",
        ]
        result = verify_frame_order(prompt_order, perplexity_reported_order)
        assert result["match"] is False
        assert result["missing_frames"] == []
        assert result["extra_frames"] == []
        assert ("US-017_frame_presend.png", 0, 1) in result["reordered_frames"]
        assert ("US-017_frame_thinking.png", 1, 0) in result["reordered_frames"]
        # resolved.png stayed in position 2 in both — must NOT be flagged
        assert not any(
            name == "US-017_frame_resolved.png"
            for name, _, _ in result["reordered_frames"]
        )

    def test_detects_missing_frame(self):
        prompt_order = ["a.png", "b.png", "c.png"]
        reported_order = ["a.png", "c.png"]
        result = verify_frame_order(prompt_order, reported_order)
        assert result["match"] is False
        assert result["missing_frames"] == ["b.png"]
        assert result["extra_frames"] == []

    def test_detects_extra_hallucinated_frame(self):
        prompt_order = ["a.png", "b.png"]
        reported_order = ["a.png", "b.png", "phantom.png"]
        result = verify_frame_order(prompt_order, reported_order)
        assert result["match"] is False
        assert result["extra_frames"] == ["phantom.png"]
        assert result["missing_frames"] == []

    def test_reports_prompt_and_reported_order_echoed_back(self):
        prompt_order = ["x.png", "y.png"]
        reported_order = ["y.png", "x.png"]
        result = verify_frame_order(prompt_order, reported_order)
        assert result["prompt_order"] == prompt_order
        assert result["reported_order"] == reported_order

    def test_empty_lists_match(self):
        result = verify_frame_order([], [])
        assert result["match"] is True

    def test_none_inputs_treated_as_empty(self):
        result = verify_frame_order(None, None)
        assert result["match"] is True
        assert result["prompt_order"] == []
        assert result["reported_order"] == []


class TestAssertReviewPacketComplete:
    def test_complete_full_code_and_es_packet_passes(self):
        assert assert_review_packet_complete(_complete_pr_packet()) is None

    def test_patch_only_packet_fails_closed(self):
        packet = _complete_pr_packet()
        packet["full_code_files"] = []
        with pytest.raises(ReviewPacketIncompleteError, match="full changed files"):
            assert_review_packet_complete(packet)

    def test_self_declared_manifest_without_builder_authority_fails(self):
        packet = _complete_pr_packet()
        del packet["manifest_source"]
        with pytest.raises(ReviewPacketIncompleteError, match="authoritative Git diff"):
            assert_review_packet_complete(packet)

    def test_patch_named_as_full_changed_file_fails(self):
        patch = [_file("pr9329.patch", 100)]
        packet = _complete_pr_packet()
        packet["changed_files"] = patch
        packet["authoritative_changed_files"] = patch
        packet["full_code_files"] = patch
        with pytest.raises(ReviewPacketIncompleteError, match="cannot satisfy"):
            assert_review_packet_complete(packet)

    def test_wrong_sixth_path_fails(self):
        packet = _complete_pr_packet()
        packet["full_code_files"][-1] = _file(
            "mvp_site/tests/test_gemini_implicit_cache_utilization_es.py",
            24035,
        )
        with pytest.raises(ReviewPacketIncompleteError, match="coverage mismatch"):
            assert_review_packet_complete(packet)

    def test_wrong_byte_size_fails(self):
        packet = _complete_pr_packet()
        packet["full_code_files"][1] = _file("mvp_site/llm_service.py", 1)
        with pytest.raises(ReviewPacketIncompleteError, match="metadata mismatch"):
            assert_review_packet_complete(packet)

    def test_missing_base_and_diff_provenance_fails(self):
        packet = _complete_pr_packet()
        packet["diff_index_attached"] = False
        packet["base_code_files"] = []
        packet["diff_index"] = None
        with pytest.raises(ReviewPacketIncompleteError, match="base-file and diff"):
            assert_review_packet_complete(packet)

    @pytest.mark.parametrize("missing_key", ["full_evidence_files", "evidence_index_paths"])
    def test_missing_raw_evidence_or_focused_index_fails(self, missing_key):
        packet = _complete_pr_packet()
        packet[missing_key] = []
        with pytest.raises(ReviewPacketIncompleteError):
            assert_review_packet_complete(packet)

    @pytest.mark.parametrize("review_kind", ["visual", "unknown"])
    def test_non_packet_review_kinds_fail_closed(self, review_kind):
        packet = _complete_pr_packet()
        packet["review_kind"] = review_kind
        with pytest.raises(ReviewPacketIncompleteError, match="Unsupported"):
            assert_review_packet_complete(packet)


class TestAssertPacketAttachmentsVerified:
    def test_exact_browser_inventory_passes(self):
        inventory = {"FULL_CODE.txt": 100, "FULL_ES.txt": 200}
        assert (
            assert_packet_attachments_verified(
                {"packet_attachments": inventory},
                {"packet_attachments": inventory},
            )
            is None
        )

    def test_missing_or_wrong_size_attachment_fails(self):
        with pytest.raises(PacketAttachmentsNotVerifiedError, match="mismatch"):
            assert_packet_attachments_verified(
                {"packet_attachments": {"FULL_CODE.txt": 100, "FULL_ES.txt": 200}},
                {"packet_attachments": {"FULL_CODE.txt": 100}},
            )


class TestAssertRetrievalVerified:
    def _expected(self):
        packet = _complete_pr_packet()
        return {
            "head_sha": packet["head_sha"],
            "attachment_names": [
                "PR9329_FULL_CODE_FILES.txt",
                "PR9329_ES_REVIEW_INDEX.txt",
                "PR9329_FULL_ES_EVIDENCE.txt",
            ],
            "code_files": {
                item["path"]: item["size_bytes"] for item in packet["changed_files"]
            },
            "evidence_paths": [
                "verification_report.json",
                "implicit_cache_utilization_bq.json",
                "raw/bq_readback.json",
            ],
            "required_fields": {
                "verification_result": "PASS",
                "weighted_cache_hit_rate": "48.40%",
            },
            "require_changed_and_unchanged_citations": True,
        }

    def _reported(self):
        expected = self._expected()
        return {
            **expected,
            "context_retained": True,
            "changed_region_cited": True,
            "unchanged_region_cited": True,
        }

    def test_exact_retrieval_challenge_passes(self):
        assert assert_retrieval_verified(self._expected(), self._reported()) is None

    def test_upload_acknowledged_but_not_inventoried_fails(self):
        reported = self._reported()
        reported["code_files"] = {}
        with pytest.raises(RetrievalNotVerifiedError, match="code_files"):
            assert_retrieval_verified(self._expected(), reported)

    def test_context_eviction_fails_even_after_upload(self):
        reported = self._reported()
        reported["context_retained"] = False
        reported["retention_note"] = "not retained in the active context window"
        with pytest.raises(RetrievalNotVerifiedError, match="context was not retained"):
            assert_retrieval_verified(self._expected(), reported)

    def test_wrong_testing_mcp_path_fails(self):
        reported = self._reported()
        size = reported["code_files"].pop(
            "testing_mcp/test_gemini_implicit_cache_utilization_es.py"
        )
        reported["code_files"][
            "mvp_site/tests/test_gemini_implicit_cache_utilization_es.py"
        ] = size
        with pytest.raises(RetrievalNotVerifiedError, match="code_files"):
            assert_retrieval_verified(self._expected(), reported)

    def test_missing_load_bearing_field_fails(self):
        reported = self._reported()
        del reported["required_fields"]["weighted_cache_hit_rate"]
        with pytest.raises(RetrievalNotVerifiedError, match="required_fields"):
            assert_retrieval_verified(self._expected(), reported)


class TestAssertPublicShareVerified:
    def test_cookie_free_browser_with_current_marker_passes_despite_curl_403(self):
        probe = {
            "url": "https://www.perplexity.ai/search/example",
            "http_status": 403,
            "cookie_free_browser_rendered": True,
            "authenticated_session_used": False,
            "expected_run_marker": "WA-RUN-9329-004",
            "expected_verdict": "APPROVED with notes",
            "public_turns": [
                {"role": "user", "content": "RETRIEVAL WA-RUN-9329-004"},
                {
                    "role": "assistant",
                    "content": "Final retrieval passed.\nVERDICT: APPROVED with notes",
                },
            ],
        }
        assert assert_public_share_verified(probe) is None

    def test_http_200_with_stale_initial_turn_fails(self):
        probe = {
            "url": "https://chatgpt.com/share/example",
            "http_status": 200,
            "cookie_free_browser_rendered": True,
            "authenticated_session_used": False,
            "expected_run_marker": "WA-RUN-9329-004",
            "expected_verdict": "APPROVED",
            "public_turns": [
                {"role": "user", "content": "RETRIEVAL WA-RUN-9329-001"},
                {"role": "assistant", "content": "VERDICT: INSUFFICIENT"},
            ],
        }
        with pytest.raises(PublicShareNotVerifiedError, match="run marker"):
            assert_public_share_verified(probe)

    def test_owner_authenticated_only_check_fails(self):
        probe = {
            "url": "https://www.perplexity.ai/search/example",
            "http_status": 200,
            "cookie_free_browser_rendered": False,
            "authenticated_session_used": True,
            "expected_run_marker": "WA-RUN-9329-004",
            "expected_verdict": "APPROVED",
            "public_turns": [
                {"role": "user", "content": "WA-RUN-9329-004"},
                {"role": "assistant", "content": "VERDICT: APPROVED"},
            ],
        }
        with pytest.raises(PublicShareNotVerifiedError, match="cookie-free"):
            assert_public_share_verified(probe)

    def test_missing_url_fails(self):
        probe = {
            "url": "",
            "cookie_free_browser_rendered": True,
            "authenticated_session_used": False,
            "expected_run_marker": "WA-RUN-x",
            "expected_verdict": "APPROVED",
            "public_turns": [
                {"role": "user", "content": "WA-RUN-x"},
                {"role": "assistant", "content": "VERDICT: APPROVED"},
            ],
        }
        with pytest.raises(PublicShareNotVerifiedError, match="invalid"):
            assert_public_share_verified(probe)

    def test_old_expected_verdict_cannot_mask_wrong_final_verdict(self):
        probe = {
            "url": "https://chatgpt.com/share/example",
            "cookie_free_browser_rendered": True,
            "authenticated_session_used": False,
            "expected_run_marker": "WA-RUN-x",
            "expected_verdict": "APPROVED",
            "public_turns": [
                {"role": "assistant", "content": "VERDICT: APPROVED"},
                {"role": "user", "content": "WA-RUN-x"},
                {"role": "assistant", "content": "VERDICT: REJECTED"},
            ],
        }
        with pytest.raises(PublicShareNotVerifiedError, match="verdict mismatch"):
            assert_public_share_verified(probe)
