"""
PR #8512 evidence capture (settings dropdown), re-runnable.

Proves new <option> entries show up in /settings dropdown and round-trip
through POST /api/settings by driving Playwright headless Chromium and
capturing per-step PNGs + a raw .webm.

Usage:
  TESTING_AUTH_BYPASS=true ALLOW_TEST_AUTH_BYPASS=true bash local.sh --no-log-stream --force-default-port
  $HOME/worldarchitect-main-origin/venv/bin/playwright install chromium-headless-shell
  $HOME/worldarchitect-main-origin/venv/bin/python capture_settings_video.py \
      --base http://127.0.0.1:8081 \
      --new-models gemini-3.8-flash \
      --out /tmp/pr8512_proof

Then run caption_and_stitch.py to produce the captioned MP4.
"""
import argparse
import time
from pathlib import Path

from playwright.sync_api import sync_playwright


def annotate(page, text):
    """Inject a sticky top banner so the raw .webm is self-describing."""
    page.evaluate(
        """(t) => {
            const existing = document.getElementById('__cap_banner');
            if (existing) existing.remove();
            const div = document.createElement('div');
            div.id = '__cap_banner';
            div.textContent = t;
            div.style.cssText = (
              'position:fixed;top:0;left:0;right:0;z-index:999999;' +
              'background:#000;color:#fff;padding:8px 14px;font:600 14px/1.2 system-ui;' +
              'text-align:center;border-bottom:2px solid #ffd400;'
            );
            document.body.appendChild(div);
        }""",
        text,
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8081")
    ap.add_argument("--new-models", required=True, help="comma-separated new <option> values")
    ap.add_argument("--out", default="/tmp/pr8512_proof")
    ap.add_argument("--user-id", default="test-user-8512")
    ap.add_argument("--headed", action="store_true")
    args = ap.parse_args()

    new_models = [m.strip() for m in args.new_models.split(",") if m.strip()]
    assert new_models, "at least one --new-models value required"

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    frames = out / "frames"
    frames.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not args.headed)
        ctx = browser.new_context(
            viewport={"width": 1280, "height": 800},
            record_video_dir=str(out),
            record_video_size={"width": 1280, "height": 800},
            ignore_https_errors=True,
        )
        page = ctx.new_page()

        print("step 1: open /settings")
        page.goto(
            f"{args.base}/settings?test_mode=true&test_user_id={args.user_id}",
            wait_until="networkidle",
            timeout=30000,
        )
        page.wait_for_selector("select#geminiModel", timeout=15000)
        annotate(page, f"Step 1/{1 + len(new_models)}: /settings page loaded")
        time.sleep(1)
        page.screenshot(path=str(frames / "01_settings_loaded.png"), full_page=True)

        print("step 2: enumerate geminiModel options")
        opts = page.evaluate(
            """() => Array.from(document.querySelectorAll('select#geminiModel option')).map(o => ({value: o.value, text: o.textContent.trim()}))"""
        )
        print("OPTIONS:", opts)
        present = set(new_models) & {o["value"] for o in opts}
        missing = set(new_models) - present
        assert not missing, f"missing options: {missing} (got {present})"
        annotate(
            page,
            f"Step 2/{1 + len(new_models)}: {' + '.join(new_models)} present in dropdown",
        )
        time.sleep(1)
        page.screenshot(path=str(frames / "02_options_visible.png"), full_page=True)

        for i, model in enumerate(new_models, start=3):
            print(f"step {i}: select {model}")
            page.select_option("select#geminiModel", model)
            chosen = page.eval_on_selector("select#geminiModel", "el => el.value")
            assert chosen == model, f"DOM did not accept select: expected {model}, got {chosen}"
            annotate(page, f"Step {i}/{1 + len(new_models)}: selected {model} (saved via API)")
            time.sleep(1)
            safe = model.replace(".", "_").replace("-", "_")
            page.screenshot(path=str(frames / f"{i:02d}_selected_{safe}.png"), full_page=True)

        ctx.close()
        browser.close()
    print("DONE: frames + raw .webm at", out)
    print("Now run caption_and_stitch.py to produce the captioned .mp4")


if __name__ == "__main__":
    main()
