# File-watcher cron pattern — for portals you can't drive headlessly

Some tax portals (Schwab, Fidelity, Morgan Stanley, Wells Fargo, E*TRADE, Wealthfront) refuse headless Chromium connections even when the user is signed in via their visible Chrome. TLS-fingerprint mismatch.

For these portals the only durable path is **let the user download, then watch the folder**. Verified 2026-07-19: 14 PDFs from Morgan Stanley / Schwab / Fidelity / Wells Fargo / Snap / Wealthfront landed in `~/Downloads/tax 2025/` and were auto-mirrored to Drive + TaxDome + Slack within one cron tick.

## Cron prompt template

The cron job runs as an LLM tick. Keep the prompt self-contained because cron jobs run in fresh sessions without the chat context.

```
You are a file-watcher for the <preparer> <year> tax-return document drive.

Every tick, run these checks IN PARALLEL:

1. Check for new PDFs in ~/Downloads/<preparer slug> <year>/ (added in the last 5 min).
   The Hermes terminal wrapper strips find's -printf and compound predicates, so use:
   env -i HOME="$HOME" PATH="$HOME/.local/orch-venv/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin" \
     /usr/bin/find "$HOME/Downloads/<preparer slug> <year>" -maxdepth 1 -name "*.pdf" -mmin -5 -print

2. If new files found:
   a. Mirror to /tmp/<preparer>-<year>/raw/
      cp "$HOME/Downloads/<preparer slug> <year>/$FILE" /tmp/<preparer>-<year>/raw/
   b. Upload to Drive folder <year>/
      gog -a $USER@gmail.com drive upload "$HOME/Downloads/<preparer slug> <year>/$FILE" --parent=<DRIVE_FOLDER_ID>
   c. Upload to TaxDome Documents folder headlessly via Playwright + TaxDome cookies:
      - ~/.local/orch-venv/bin/python3 + bundled Chromium-for-Testing (channel=chromium, headless=True)
      - Cookies from /tmp/<preparer>-<year>-cookies-chrome.json (filtered taxdome.com)
      - Navigate to https://orenheneainc.taxdome.com/app/documents
      - Use the data-test selector [data-test="DocumentsDropzone-UploadFiles-Button"] (NOT generic "Upload files" — there are 3 matches and Playwright strict mode will trip)
      - Pick the LAST non-webkitdirectory <input type="file"> (4 inputs exist on the page, 1 is the "Upload folder" webkitdirectory picker)
      - Click the modal's exact-text "Upload" button (substring "Upload" matches the page "Upload files" button behind the modal)
      - Wait for modal "Done" button to appear (5s single, 8s multi-file)
      - The script ~/.hermes/skills/productivity/personal-tax-prep-coordination/scripts/taxdome_upload_documents.py codifies all of the above; CALL IT instead of re-deriving
      - Set PLAYWRIGHT_BROWSERS_PATH="$HOME/Library/Caches/ms-playwright" so the full Chromium-for-Testing binary is found (NOT ~/.cache/ms-playwright)
   d. POST single Slack line per file using mcp__slack__conversations_add_message:
      channel_id=C09GRLXF9GR  (NOT #ai-general C0AJQ5M0A0Y — the cron bot isn't a member there; #all-$USER-ai is the bot's safe fallback per slack-thread-routing-investigation Failure 5g)
      text=":white_check_mark: Uploaded <portal> <year> <form-type> → Drive <year>/ + TaxDome"
      (One message per file — do NOT batch multiple files into one line; do NOT trust the cron's --deliver slack:CHAN field, it only affects LLM end-of-tick narration, not in-prompt conversations_add_message calls.)

3. Self-cancel after 4h OR after all 10 portal forms present. Use:
   hermes cron remove $CRON_JOB_ID
   Then post single ":wave: file watcher done, N PDFs collected, self-cancelling." to channel C09GRLXF9GR.

CONSTRAINTS:
- env -i HOME="$HOME" PATH="$HOME/.local/orch-venv/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin" for browserclaw AND for /usr/bin/find (bashrc-profile-xapp-drift memory + rtk-find-scrub pitfall).
- NEVER post raw cookies to Slack.
- NEVER send email to <preparer> (email-approved-gate).
- ALWAYS headless for browser work.
```

## Cron create command

```bash
hermes cron create \
  --name '<preparer>-<year>-file-watcher (2m)' \
  --deliver 'slack:<channel_id>' \
  --model minimax:MiniMax-M3 \
  --prompt-file /tmp/<preparer>-<year>-cron-prompt.md \
  'every 2m' \
  --repeat forever
```

Confirmed working invocation (do NOT use the `--at` flag for recurring crons — it conflicts):

```python
cronjob(action='create', schedule='every 2m', name='tax-2025-file-watcher (2m)',
         prompt='<prompt>', deliver='slack:C0AMM2B4319', model={'provider':'minimax','model':'MiniMax-M3'})
```

Returns `job_id` like `ad5ed0137d89`. Use this to manually run, pause, or remove.

## Tradeoffs

- **Silent by default** — if no new files in the last 5 min, the cron should not post anything. This avoids Slack spam during long stretches where the user hasn't downloaded yet.
- **Self-cancel after 4h** — the cron has a finite useful life. Once all 10 portal forms are present, the user can review manually and the cron should exit. Watchdog: `scripts/babysit_stale_watchdog.py` catches babysit crons that linger past 30 min.
- **Don't fight the user's other chat** — if another Aside chat is driving the same portals, the file-watcher cron will pick up files it downloaded. That's fine; cron just mirrors + uploads. Don't try to coordinate at the cron level.

## TaxDome Documents upload — concrete recipe

The cron prompt above ("Navigate to TaxDome Documents and use the file input to upload each PDF") is underspecified. The actual recipe (verified 2026-07-19 against `orenheneainc.taxdome.com`) has FIVE gotchas that the script at `scripts/taxdome_upload_documents.py` codifies. Do NOT re-derive these in cron prompts:

1. **Open-modal button selector** — the page has THREE elements with role=button and text overlapping "Upload files" (the dashed dropzone `<div>`, the dropzone inner `<div>`, and the actual button). Use the data-test selector: `[data-test="DocumentsDropzone-UploadFiles-Button"]`. Generic `button:has-text("Upload files")` resolves to 3 elements and fails with `strict mode violation`.
2. **The webkitdirectory trap** — after clicking, the DOM contains FOUR `<input type="file">` elements. The LAST one is `webkitdirectory="true"` (the "Upload folder" file-picker); the others are regular file inputs. Setting files on the webkitdirectory input raises `Error: [webkitdirectory] input requires passing a path to a directory`. Iterate from the back, pick the first non-webkitdirectory.
3. **Modal vs page "Upload" button** — the modal's Upload button text is exactly `"Upload"`. But `:has-text("Upload")` is a substring match, so it ALSO matches the page's "Upload files" button behind the modal. Click always lands on the wrong target and the modal stalls. Use `button.filter(has_text=re.compile(r'^Upload$'))` or `page.get_by_role("button", name="Upload", exact=True)`.
4. **Done button = success sentinel** — after the modal's Upload click, wait for the modal's "Done" button to appear (visible text "Done"). That confirms the upload completed. If you instead wait on the upload button disappearing, you'll race-condition on the 1–3s server-side latency.
5. **Multi-file is supported** — `set_input_files([pdf_a, pdf_b, ...])` uploads all in one modal round trip. Modal title becomes "Upload N documents". Wait at least 8s (vs 5s for single) before checking for the Done button.

Verified end-to-end 2026-07-19: 13 PDFs (Wells Fargo 1098 + 1099-INT, Fidelity 1099-R ×2, Morgan Stanley ×4, Schwab ×2, Snap W-2, Wealthfront 1099-B ×2) all uploaded with `OK  <name>  (done shown)` from one Playwright session.

To run from a cron tick:

```bash
env -i HOME="$HOME" PATH="$HOME/.local/orch-venv/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin" \
  PLAYWRIGHT_BROWSERS_PATH="$HOME/Library/Caches/ms-playwright" \
  "$HOME/.local/orch-venv/bin/python3" \
  ~/.hermes/skills/productivity/personal-tax-prep-coordination/scripts/taxdome_upload_documents.py \
  "$HOME/Downloads/<preparer slug> <year>"/*.pdf
```

Playwright path note: bundled Chromium-for-Testing lives at
`~/Library/Caches/ms-playwright/chromium-1223/chrome-mac-arm64/Google Chrome for Testing.app` (NOT `~/Library/Caches/ms-playwright/chromium_headless_shell-…` — the headless_shell binary does not pass TaxDome's vanilla checks; use the full browser binary via `channel='chromium', headless=True`).

Verify Drive + portal uploads landed before declaring success — the gold test is reading back the TaxDome folder listing via Playwright (not just trusting the modal's "Uploaded" badge, which only confirms the HTTP POST reached TaxDome, not that the file is queryable in the folder list).

```bash
# Drive verification
gog -a $USER@gmail.com drive ls --parent=$DRIVE_FOLDER_ID --max=100 | wc -l   # expect: prior + N

# TaxDome verification (file list scrape of /app/documents)
~/.hermes/skills/productivity/personal-tax-prep-coordination/scripts/taxdome_verify_documents.py
```

## Pitfalls

- **Folder with spaces** (e.g. `tax 2025`) requires careful quoting in shell scripts. Always use double quotes around paths.
- **`-mmin -5` is `find` syntax, not `ls -lt | head`** — the latter doesn't survive pagination when the user downloads many files at once.
- **Don't write to `~/Downloads/` root** — always write into a year-named subfolder so the cron doesn't pick up unrelated downloads.
- **Don't symlink** — the file-watcher should see real files, not links.
- **No dedup state = Drive duplicates** — verified 2026-07-19. The cron has no persistent marker of "already uploaded". If the user's earlier manual sessions (or prior cron ticks) uploaded any of the same files to the same Drive folder, this tick will re-upload them, causing `drive ls` to show 2× entries. After 1 cycle: `gog -a $USER@gmail.com drive ls --parent=$DRIVE_FOLDER_ID --max=200`, scan for basename dupes, keep newest (largest mtime), `gog drive rm` the rest. TaxDome deduplicates by filename inside a folder, so the dupes are Drive-specific.
- **`-printf '%f'` does NOT exist on macOS BSD find** — the BSD find on this Mac returns `find: -printf: unknown primary or operator`. Verified 2026-07-19. The `cron-file-watch-prompt.md` template uses `-printf` which fails silently on this Mac; the working command in this reference is `find … -print | while read f; do basename "$f"; done` (or use `find ... -print0 | while IFS= read -r -d '' f` for null-separated safety). Note the BSD-find-only restriction applies to Ventura+ macOS — GNU find via `brew install findutils` and `PATH=...:$HOMEBREW/opt/findutils/libexec/gnubin` works but is not installed by default.
- **The Hermes terminal wrapper (`rtk`) strips even BSD-valid find flags** — verified tick 2 of `ad5ed0137d89` (2026-07-19). The default `find` invocation in the cron prompt (`find "$HOME/Downloads/..." -maxdepth 1 -name "*.pdf" -mmin -5 -printf '%f\n'`) returns `rtk: rtk find does not support compound predicates or actions (e.g. -not, -exec).` and exits 1. The wrapper scrubs both `-printf` AND compound predicates (`-not`, `-exec`, `-execdir`). Workaround: invoke `/usr/bin/find` directly under a clean env so the wrapper can't see it: `env -i HOME="$HOME" PATH="$HOME/.local/orch-venv/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin" /usr/bin/find "$HOME/Downloads/tax 2025" -maxdepth 1 -name "*.pdf" -mmin -5 -print`. The wrapper's own disclaimer ("Use `find` directly.") is the hint to do this — copy the recipe from this pitfall verbatim, do NOT improvise. The cron prompt template at the top of this reference already uses the right shell so `tick 2` recovered; future cron prompts derived from this template MUST keep the `env -i … /usr/bin/find -print` shape.
- **`-mmin -5` matches all files newer than 5 min even if they were placed by the cron itself on a prior tick** — combined with no dedup state, this is what creates the duplicate Drive files. The right fix is to mark processed copies (`touch -d "1970-01-01" /tmp/<preparer>-<year>/raw/<file>`) and skip filenames already marked. The current cron prompt does NOT do this; flag for the next rev.
- **Bundled Chromium-for-Testing path** — `PLAYWRIGHT_BROWSERS_PATH=~/Library/Caches/ms-playwright` (NOT `~/.cache/ms-playwright`). Verified 2026-07-19. Setting the wrong path gives `playwright._impl._errors.Error: Executable doesn't exist at …/chromium-*/chrome-linux/chrome`.
- **`gog drive upload` returns 0-exit `link\thttps://...` even on partial-failure** — always parse for the `link\thttps://drive.google.com/` line; if missing on stdout, treat as FAIL and retry once with `--no-input -y`.
- **The cron prompt's "POST single Slack line per file" produces duplicate identical lines** when multiple PDFs share a (portal, form-type) tuple — 4× Morgan Stanley 1099 statements = 4 identical Slack messages. Consider changing the cron prompt to use a single batched line per (portal, form-type) with a file count, e.g. `:white_check_mark: Uploaded 4× morgan stanley 2025 1099 → Drive + TaxDome`. The current prompt writes one line per file which matches the literal interpretation but reads as noise in busy threads.
- **The cron prompt's "POST single Slack line per file" does NOT name a channel** — verified tick 2 of `ad5ed0137d89` (2026-07-19). The SOUL.md `slack-channel-routing-policy` rule names `#ai-general` (C0AJQ5M0A0Y) as the home channel for cron-initiated posts, but the MCP Agent Mail bot that runs the cron prompt (`B0A450AF9NF`) is NOT a member of `#ai-general` — `mcp__slack__conversations_add_message(channel_id=C0AJQ5M0A0Y, ...)` returns `{"error":"not_in_channel"}` (Failure 5g per `slack-thread-routing-investigation`). On tick 2, posting fell back to `#all-$USER-ai` (C09GRLXF9GR) where the bot IS a member, by inspecting the channel list after the home-channel rejection. Hardened cron prompts MUST name a fallback channel explicitly. Two viable shapes: (a) `#all-$USER-ai` (C09GRLXF9GR) for crons that are personal-system-internal; (b) the originating user thread specified in the cron prompt body (matches the PR-babysit cron pattern). For file-watcher crons specifically, the right pickup channel is `#all-$USER-ai` (C09GRLXF9GR) — never `#ai-general` — and the cron prompt should specify `POST one-line Slack to channel C09GRLXF9GR` instead of the current "POST single Slack line per file" phrasing.
- **Cron-driven `mcp__slack__conversations_add_message` cannot use the cron `--deliver` channel** — verified tick 2. The cron was created with `--deliver 'slack:C0AMM2B4319'` (#life) per the `hermes cron create` example, but the `deliver` field only routes the cron job's NATIVE end-of-tick output (LLM narration) — it does NOT cause individual `conversations_add_message` calls inside the cron prompt body to inherit that channel. The cron still has to explicitly pass `channel_id` to each `mcp__slack__conversations_add_message` call. If the cron prompt forgets the channel_id (like this one does), the post lands wherever the MCP tool defaulted to. Verified: tick 2's `:wave:` closeout and `:white_check_mark:` lines all went to C09GRLXF9GR, not the deliver-channel C0AMM2B4319. Cron prompt templates should call `mcp__slack__conversations_add_message(channel_id=C09GRLXF9GR, ...)` explicitly for every per-file message, or use the path-B curl fallback in `slack-thread-routing-investigation` (Path B with `SLACK_MCP_XOXP_TOKEN`) if the MCP slack tool isn't loaded in the cron runtime.