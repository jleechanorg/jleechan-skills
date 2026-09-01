import subprocess
import sys
from pathlib import Path

from playwright_cookie_driver import (
    CFG,
    fill_composer,
    has_packet_echo,
    report_is_complete,
    upload_gate_reason,
    upload_attachments,
)


def test_help_is_general_and_has_no_stale_session_dependency():
    script = Path(__file__).with_name("playwright_cookie_driver.py")
    result = subprocess.run(
        [sys.executable, str(script), "--help"],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "--storage-state" in result.stdout
    assert "--attachment" in result.stdout
    assert "jeff-ubuntu-crash-3wk" not in result.stdout + result.stderr


def test_chatgpt_uses_the_general_document_input_not_an_ambiguous_first_input():
    assert CFG["chatgpt"]["upload_input"] == "#upload-files"


def test_chatgpt_uses_its_send_button_after_filling_the_composer():
    assert CFG["chatgpt"]["send_selector"] == 'button[aria-label="Send prompt"]'


def test_only_a_received_response_makes_a_browser_seat_complete():
    base = {
        "authenticated": True,
        "composer_writable": True,
        "upload_verified": True,
        "packet_echo_verified": True,
    }
    assert report_is_complete({**base, "response": ""}) is False
    assert report_is_complete({**base, "response": "VERDICT: APPROVED"}) is True


def test_a_response_without_the_requested_packet_echo_is_not_a_complete_seat():
    report = {
        "authenticated": True,
        "composer_writable": True,
        "upload_verified": True,
        "packet_echo_verified": False,
        "response": "VERDICT: APPROVED",
    }

    assert report_is_complete(report) is False


def test_packet_echo_requires_the_requested_sha_and_every_attachment_name():
    prompt = "Review commit 0123456789abcdef0123456789abcdef01234567."
    attachments = ["head.txt", "diff.txt"]

    assert has_packet_echo(
        "PACKET ECHO: 0123456789abcdef0123456789abcdef01234567 head.txt diff.txt",
        prompt,
        attachments,
    )
    assert not has_packet_echo(
        "PACKET ECHO: 0123456789abcdef0123456789abcdef01234567 head.txt",
        prompt,
        attachments,
    )


def test_upload_sign_in_dialog_is_reported_as_an_authentication_gate():
    assert (
        upload_gate_reason("Sign in to upload files Continue with Google")
        == "upload_login_required"
    )
    assert (
        upload_gate_reason("Upgrade for additional document analysis")
        == "upload_plan_required"
    )
    assert upload_gate_reason("Choose a file") is None


def test_perplexity_menu_upload_does_not_fall_back_to_an_ambiguous_file_input():
    class FileChooser:
        def __init__(self):
            self.files = None

        def set_files(self, files):
            self.files = files

    class ChooserContext:
        def __init__(self, chooser):
            self.value = chooser

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

    class Locator:
        def __init__(self, name, calls):
            self.name = name
            self.calls = calls

        def click(self):
            self.calls.append(("click", self.name))

    class Page:
        def __init__(self):
            self.calls = []
            self.chooser = FileChooser()

        def locator(self, selector):
            raise AssertionError(f"ambiguous direct input queried: {selector}")

        def get_by_role(self, role, name):
            return Locator(f"{role}:{name}", self.calls)

        def expect_file_chooser(self):
            return ChooserContext(self.chooser)

    page = Page()
    upload_attachments(page, CFG["perplexity"], ["head.txt", "diff.txt"])

    assert page.calls == [
        ("click", "button:Add files or tools"),
        ("click", "menuitem:Upload files or images"),
    ]
    assert page.chooser.files == ["head.txt", "diff.txt"]


def test_fill_composer_accepts_a_visible_value_after_chatgpt_raises_on_fill():
    class Composer:
        value = ""

        def click(self):
            return None

        def fill(self, value):
            self.value = value
            raise RuntimeError("contenteditable fill confirmation failed")

        def inner_text(self):
            return self.value

    class Keyboard:
        def insert_text(self, value):
            raise AssertionError(f"unexpected fallback insertion: {value}")

    class Page:
        keyboard = Keyboard()

    fill_composer(Page(), Composer(), "review this packet")
