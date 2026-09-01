import argparse
import json
import pathlib
import re
import time

from playwright.sync_api import sync_playwright


class UploadGateError(RuntimeError):
    """Raised when the visible vendor UI refuses an upload before selection."""


CFG = {
    "chatgpt": {
        "url": "https://chatgpt.com/",
        "composer": ["#prompt-textarea", 'div[contenteditable="true"]', "textarea"],
        "login_markers": ["log in", "sign up", "Welcome back"],
        "upload_strategy": "direct_input",
        "upload_input": "#upload-files",
        "send_selector": 'button[aria-label="Send prompt"]',
        "resp": '[data-message-author-role="assistant"]',
    },
    "perplexity": {
        "url": "https://www.perplexity.ai/",
        "composer": ['[role="textbox"]', 'div[contenteditable="true"]'],
        "login_markers": ["Sign in", "Log in"],
        "upload_strategy": "menu",
        "upload_button": "Add files or tools",
        "upload_menu_item": "Upload files or images",
        "send_role": "Submit",
        "resp": '[class*="response"],[class*="message-bubble"],.prose',
    },
    "gemini": {
        "url": "https://gemini.google.com/app",
        "composer": [
            'div.ql-editor[contenteditable="true"]',
            'div[contenteditable="true"]',
            "rich-textarea",
        ],
        "login_markers": ["Sign in to continue", "Sign in"],
        "upload_strategy": "menu",
        "upload_button": "Upload & tools",
        "upload_menu_item": "Upload files. Documents, data, code files",
        "send_strategy": "press_enter",
        "resp": 'message-content,.model-response-text,[class*="model-response"]',
    },
}


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run one authenticated /web-advice web-chat seat headlessly."
    )
    parser.add_argument("--site", choices=sorted(CFG), required=True)
    parser.add_argument("--storage-state", type=pathlib.Path, required=True)
    parser.add_argument("--prompt-file", type=pathlib.Path, required=True)
    parser.add_argument("--attachment", type=pathlib.Path, action="append", default=[])
    parser.add_argument("--output", type=pathlib.Path, required=True)
    parser.add_argument("--screenshot", type=pathlib.Path)
    parser.add_argument("--timeout-seconds", type=int, default=180)
    return parser.parse_args()


def visible_attachment_names(page, expected_names):
    """Return exact filenames the web UI rendered before prompting."""
    if not expected_names:
        return []
    return sorted(
        page.evaluate(
            """expected => [...new Set([...document.querySelectorAll('*')]
                .flatMap(e => [e.textContent, e.getAttribute('aria-label')])
                .filter(Boolean).map(value => value.trim())
                .filter(value => expected.includes(value)))]""",
            expected_names,
        )
    )


def fill_composer(page, composer, prompt):
    """Fill a controlled editor, tolerating ChatGPT's false-negative fill check."""
    composer.click()
    try:
        composer.fill(prompt)
        return
    except Exception:
        if composer.inner_text().strip() == prompt.strip():
            return
    composer.click()
    page.keyboard.insert_text(prompt)


def upload_gate_reason(visible_text):
    """Classify visible vendor upload gates without attempting authentication."""
    text = visible_text.lower()
    if "sign in to upload files" in text:
        return "upload_login_required"
    if "upgrade for additional document analysis" in text:
        return "upload_plan_required"
    return None


def upload_attachments(page, site, attachments):
    """Upload packet files through the vendor's unambiguous visible control."""
    strategy = site.get("upload_strategy", "direct_input")
    if strategy == "menu":
        try:
            with page.expect_file_chooser() as chooser_info:
                page.get_by_role("button", name=site["upload_button"]).click()
                page.get_by_role("menuitem", name=site["upload_menu_item"]).click()
        except Exception as error:
            gate = upload_gate_reason(page.locator("body").inner_text())
            if gate:
                raise UploadGateError(gate) from error
            raise
        chooser_info.value.set_files(attachments)
        return

    if strategy != "direct_input":
        raise RuntimeError(f"Unsupported upload strategy: {strategy}")

    upload_selector = site["upload_input"]
    inputs = page.locator(upload_selector)
    if inputs.count() != 1:
        raise RuntimeError(
            "No unambiguous enabled document input was available "
            f"for {upload_selector!r} (count={inputs.count()}); do not use .first()."
        )
    inputs.set_input_files(attachments)


def submit_prompt(page, site):
    """Send a committed vendor prompt without guessing a generic icon button."""
    if site.get("send_strategy") == "press_enter":
        page.keyboard.press("Enter")
        return

    if send_role := site.get("send_role"):
        page.get_by_role("button", name=send_role).click()
        return

    send = page.locator(site["send_selector"])
    send.wait_for(state="visible", timeout=5_000)
    send.click()


def has_packet_echo(response, prompt, expected_names):
    """Require the requested SHA and every exact filename in the result."""
    expected_shas = re.findall(r"(?<![0-9a-f])[0-9a-f]{40}(?![0-9a-f])", prompt)
    return bool(expected_shas) and all(
        value in response for value in [expected_shas[-1], *expected_names]
    )


def report_is_complete(report):
    return bool(
        report.get("authenticated")
        and report.get("composer_writable")
        and report.get("upload_verified")
        and report.get("packet_echo_verified")
        and report.get("response")
    )


def main():
    args = parse_args()
    missing = [
        str(path)
        for path in [args.storage_state, args.prompt_file, *args.attachment]
        if not path.is_file()
    ]
    if missing:
        raise SystemExit(f"Required local files are missing: {missing}")
    if not args.attachment:
        raise SystemExit("At least one --attachment is required for a packet review")

    site = CFG[args.site]
    attachments = [path.resolve() for path in args.attachment]
    expected_names = [path.name for path in attachments]
    report = {
        "site": args.site,
        "transport": "chrome_headless_cookies",
        "authenticated": False,
        "composer_writable": False,
        "packet_attachments": {path.name: path.stat().st_size for path in attachments},
        "visible_attachment_names": [],
        "upload_verified": False,
        "packet_echo_verified": False,
        "reason": None,
        "response": "",
    }

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            channel="chrome",
            args=["--headless=new", "--disable-blink-features=AutomationControlled"],
            ignore_default_args=["--enable-automation"],
        )
        context = browser.new_context(
            storage_state=str(args.storage_state),
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.7778.96 "
                "Safari/537.36"
            ),
            viewport={"width": 1400, "height": 1000},
            locale="en-US",
        )
        context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
        )
        page = context.new_page()
        try:
            page.goto(site["url"], wait_until="domcontentloaded", timeout=45_000)
            composer = None
            for selector in site["composer"]:
                try:
                    candidate = page.locator(selector).first
                    candidate.wait_for(state="visible", timeout=8_000)
                    composer = candidate
                    break
                except Exception:
                    continue
            body = page.locator("body").inner_text(timeout=10_000).lower()
            if composer is None:
                report["reason"] = "no_writable_composer"
            elif any(marker.lower() in body for marker in site["login_markers"]):
                report["reason"] = "login_required"
            else:
                report["authenticated"] = True
                report["composer_writable"] = True
                upload_attachments(page, site, [str(path) for path in attachments])
                page.wait_for_timeout(1_000)
                report["visible_attachment_names"] = visible_attachment_names(
                    page, expected_names
                )
                report["upload_verified"] = (
                    set(report["visible_attachment_names"]) == set(expected_names)
                    and len(report["visible_attachment_names"]) == len(expected_names)
                )
                if not report["upload_verified"]:
                    report["reason"] = "upload_not_visible_in_composer"
                else:
                    prompt = args.prompt_file.read_text(encoding="utf-8")
                    fill_composer(page, composer, prompt)
                    page.wait_for_timeout(750)
                    submit_prompt(page, site)
                    deadline = time.monotonic() + args.timeout_seconds
                    previous = ""
                    stable = 0
                    while time.monotonic() < deadline:
                        texts = []
                        for selector in site["resp"].split(","):
                            texts.extend(page.locator(selector).all_inner_texts())
                        current = texts[-1].strip() if texts else ""
                        stable = stable + 1 if current and current == previous else 0
                        if stable >= 2 and len(current) > 40:
                            report["response"] = current
                            report["packet_echo_verified"] = has_packet_echo(
                                current, prompt, expected_names
                            )
                            if not report["packet_echo_verified"]:
                                report["reason"] = "packet_echo_not_observed"
                            break
                        previous = current
                        time.sleep(3)
                    if not report["response"]:
                        report["reason"] = "response_not_observed"
        except UploadGateError as error:
            report["reason"] = str(error)
        except Exception as error:
            report["reason"] = f"browser_error:{type(error).__name__}:{error}"
        finally:
            if args.screenshot:
                page.screenshot(path=str(args.screenshot), full_page=False)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(
                json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
            browser.close()

    return 0 if report_is_complete(report) else 2


if __name__ == "__main__":
    raise SystemExit(main())
