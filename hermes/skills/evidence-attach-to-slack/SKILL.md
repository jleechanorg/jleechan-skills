---
name: evidence-attach-to-slack
version: 1.12.0
description: |
  Attach local evidence files (PNG/JPG/GIF/MP4/PDF) to Slack threads so they
  render INLINE — not as bare file paths or `MEDIA:/path` text tokens.
  v1.3 cluster-anchor; v1.4 gist-raw-URL fallback; v1.5 Pre-Send Gate;
  v1.6 OAuth preflight + f-string pitfall; v1.7 misrouted-fix; v1.8 gist
  binary pitfall (clone-and-replace for PNG/MP4); v1.9 text-file gist delta
  (`gh gist create` works directly for `.patch`/`.diff`/`.json`/`.md`/`.txt`);
  v1.10 MP4 + curl-ARG_MAX quirks (subprocess.run arg-limit + clone-and-replace
  content-type for MP4 = `application/octet-stream`);
  v1.11 bot-side `files:write` scope closed (2026-07-19) — xoxp pending.
  v1.12 added 2 new pitfall rows: (a) `chat.delete` destroys evidence
  attachments if sorted by text-length heuristic (PR #8561 2026-07-24);
  (b) `page.evaluate()` computed style ≠ visual proof — always
  `vision_analyze` pixels before claiming visibility.
  Anti-trigger: plain-text evidence → fenced code blocks.

when_to_use: |
  When the user asks for "before/after", "screenshot", "GIF evidence", or
  any message claims visual proof that lives as a local file. Also fires
  when the user corrects you: "you forgot the screenshot" / "attach the
  proof as media" / "use /harness and fix it".

  **Auto-load contract (paired with SOUL.md `evidence-attach-presend-gate`):**
  Load THIS skill before invoking `mcp__slack__conversations_add_message`
  or `chat.postMessage` if your draft body contains any of:
    - `MEDIA:/absolute/path` token referencing a binary file
    - absolute path matching `/Users/[^ ]+\.(png|jpg|jpeg|gif|webp|mp4|pdf)`
    - "BEFORE"/"AFTER"/"screenshot"/"see attached"/"here's what it looks like"
      alongside any local path

triggers:
  - "attach proof as media"
  - "you forgot the screenshot"
  - "post the screenshot to the thread"
  - "MEDIA: not rendering"
  - "evidence didn't show up in slack"
  - "use /harness and fix it"
  - "use /learn and fix it"
  - "show before after in thread"
  - "show screenshots here"
  - "show me screenshots"
  - "see screenshots"
  - "with screenshots"
  - "and screenshots"
  - "and show screenshots"
  - "All PRs need attached media in PR desc and slack"
  - "evidence should be in gist urls"
  - "put evidence in a gist"
  - "don't commit screenshots to the PR"
  - "I need the media evidence on this thread"
  - "where are the screenshots"
  - "post evidence to this thread"
  - "you keep skipping the upload"
  - "you keep skipping this"
  - "/learn and remember this"
  - "before/after"
  - "BEFORE/AFTER"
  - "PNG"
  # PRE-SEND GATE TRIGGERS (v1.5.0)
  - "MEDIA:/path with .png/.jpg/.gif in draft body"
  - "/Users/.../path/.png in draft body"
  - "draft body says BEFORE / AFTER / screenshot / here is what it looks like"
  # RECURRING-CORRECTION PHRASES (v1.6.0)
  - "you always forget"
  - "you always fail to attach"
  - "you always do Y"
  - "stop forgetting"
  - "stop doing X"
  - "why do you always"
  # RECURRING-CORRECTION PHRASES (v1.7.0 — PR #7953, 2026-07-15)
  - "use /browser"
  - "use browser to fix your scopes"
  - "why are you struggling so much to show UI screenshots"
  - "fix your scopes"

allowed-tools:
  - mcp__slack__conversations_add_message
  - mcp__slack__conversations_replies
  - read_file
  - terminal

context: inline
---

# evidence-attach-to-slack

Attach local evidence files to Slack messages so the user can see them inline in the thread.

## ⚠️ Pre-Send Gate (NEW in v1.5.0 — paired with SOUL.md `## COMMIT: evidence-attach-presend-gate`)

**Before invoking `mcp__slack__conversations_add_message` or `chat.postMessage`, run this gate.**

The gate regex (lives in SOUL.md, mirrored here for quick check):

```python
import re

GATE_PATTERNS = {
    "media_token": re.compile(
        r"MEDIA:/[^\s]+\.(?:png|jpg|jpeg|gif|webp|mp4|pdf)\b", re.IGNORECASE),
    "absolute_path": re.compile(
        r"(?:^|\s)/Users/[^\s]+\.(?:png|jpg|jpeg|gif|webp|mp4|pdf)\b", re.IGNORECASE),
    "phrase_with_path": re.compile(
        r"(?i)\b(BEFORE|AFTER|screenshot|see attached|here'?s what it looks like)\b"),
}

def evidence_gate_fires(draft_text: str) -> bool:
    return any(p.search(draft_text) for p in GATE_PATTERNS.values())
```

**If the gate fires, you MUST run the recipe below BEFORE calling the message tool.** Skipping this gate is the exact failure mode that caused PRs #8139, #7953, #8337 to ship with text-only "evidence" that the user couldn't see. Verified by `tests/test_evidence_attach_presend_contract.py` (8 tests, all green).

**The principle:** when a recurring user correction has hit ≥3 times (as this one has), the fix must be a pre-send gate that intercepts the failure BEFORE the bad message is sent — not a post-hoc remediation rule that fires after the user complains. See `references/recurring-failure-pattern-2026-07.md` for the full 4-incident chain.

## OAuth Scope Preflight (NEW in v1.6.0)

**Before attempting Stage 1**, run the scope preflight:

```bash
python3 ~/.hermes/skills/evidence-attach-to-slack/scripts/check_token_scopes.py
```

The script probes `HERMES_SLACK_BOT_TOKEN` and `SLACK_USER_TOKEN` against `auth.test` and returns one of three states:

| State | Token | Action |
|---|---|---|
| `bot_has_scope` | bot has `files:write` | Use canonical 3-stage flow with bot token |
| `xoxp_has_scope` | bot fails, xoxp has `files:write:user` | Use xoxp token for Stage 1-3 |
| `neither_has_scope` | neither configured token has the required scope | Stop and report the exact scope blocker; do not switch to a gist or change credentials/scopes |

**Why this matters (verified 2026-07-14 on PR #8139):** I burned 4 curl calls discovering both tokens lacked `files:write` mid-flow. The preflight collapses that into 2 `auth.test` calls (one per token) and tells you the correct path upfront. Saves ~10s per evidence-attach cycle.

**Historical scope record:** Earlier checks found a missing `files:write` scope. That record is dated evidence, not proof of the current credential state and not authorization to access a personal browser, change scopes, or rotate credentials. Use the current preflight result; if no already-configured token has the required scope, stop and report the blocker.

## When to use

You MUST use this skill when **all** of these hold:

1. You have **local binary evidence** (PNG / JPG / WebP / GIF / MP4 / PDF) on disk — typically from a Playwright/Chromium screenshot, ffmpeg-converted GIF, browser recording, or audit-PDF generator.
2. The artifact is **central to the claim** in your Slack message — i.e. the message says "BEFORE/AFTER", "this is fixed", "here's what it looks like", etc., and the proof is the file itself, not the text around it.
3. The message will land in a **Slack thread** (most common case) or a Slack DM/channel where the user expects to see the evidence inline.

You MUST NOT use this skill when:

- You have only textual evidence (logs, command output, JSON, code diffs). Paste fenced code blocks instead — Slack renders them as native monospace.
- The file is on a remote URL. Markdown image syntax (`![alt](https://...)`) works for public URLs.
- The user already has the file (e.g. you uploaded it earlier and they're confirming receipt).

## The recipe — Slack `files.completeUploadExternal` flow

The `MEDIA:/path` inline convention does NOT WORK through the
`mcp__slack__conversations_add_message` tool — it renders as plain text and
the Slack client never receives an attachment. The correct path is the
3-stage Slack `files.upload` API.

### Stage 1 — Get upload URL

**MUST use `-F` form fields, NOT `-d` JSON.** Verified 2026-07-12 (PR #8337):
JSON-encoded body silently drops the form fields; the API returns `invalid_arguments`.

```bash
curl -fsS -X POST https://slack.com/api/files.getUploadURLExternal \
    -H "Authorization: Bearer ${SLACK_BOT_TOKEN}" \
    -F "filename=before-mobile-wizard-390x844.png" \
    -F "length=149206"
```

Returns `{ "ok": true, "upload_url": "https://files.slack.com/upload/v1/...", "file_id": "<SLACK_ID>" }`.

### Stage 2 — POST the file

```bash
curl -fsS -X POST "${upload_url}" \
    -F "file=@/absolute/path/to/before-mobile-wizard-390x844.png"
```

Returns `OK - <bytes_uploaded>` on success.

### Stage 3 — Complete upload + share to thread

**Use form-encoded body, NOT JSON.** Verified 2026-07-12: JSON parser is
strict about per-file extra properties; form-encoded parser is permissive.

```bash
curl -fsS -X POST https://slack.com/api/files.completeUploadExternal \
    -H "Authorization: Bearer ${SLACK_BOT_TOKEN}" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    --data-urlencode "$(python3 -c 'import json,urllib.parse; print(urllib.parse.urlencode({"files": json.dumps([{"id": "<SLACK_ID>", "title": "BEFORE: mobile wizard 390x844"}])}))')" \
    --data-urlencode "channel_id=<SLACK_ID>" \
    --data-urlencode "thread_ts=1783038068.695729"
```

Or use `scripts/upload_batch.py` (canonical parallel uploader) which handles the form-encoding for you.

### Stage 3½ — Post consolidated summary message (MANDATORY)

After uploading all the files, post a single text message in the thread that names each attachment file-by-file. **Do NOT skip this step.** The attachments themselves become separate bot messages in the thread, which — combined with the channel-bridge's tendency to echo internal narration into the same thread — can bury the screenshots under 4-8 bot messages. The summary message is the cluster anchor the user actually reads.

### Stage 4 — Re-verify (Pattern A: verify BEFORE summary, NOT after)

**Do NOT re-verify via `mcp__slack__conversations_replies` AFTER posting the summary** — every call to that tool echoes a `:gear: mcp__slack__conversations_replies:` line into the thread as a bot message, which lands AFTER the summary and contradicts the "ignore the chatter above" anchor. Verified failure 2026-07-11 PR #8139.

**Pattern A — verify before summary (preferred):** Inside the same `execute_code` that ran Stage 1+2+3 for all N files, call `conversations.replies` ONE time and assert the file_ids landed, THEN post the summary. Pattern B (skip verification) is OK only if you can see uploads succeed in the same turn.

**`chat.getPermalink` is the post-send verification that does NOT echo** (verified 2026-07-15, PR #7953). After posting the summary, call `chat.getPermalink?channel=X&message_ts=Y` — it returns the public URL without spamming the thread with bot messages. Use this for "did my message land?" checks after the summary is posted.

**`conversations.replies` `not_in_channel` is NOT a post failure** (NEW v1.8.0). If the bot has `chat:write.public` but is not a member of the channel, `chat.postMessage` succeeds and `chat.getPermalink` returns the URL, but `conversations.replies` and `conversations.history` return `not_in_channel`. Don't treat that error as evidence the post failed — verify via permalink instead.

## Token source

**Use `HERMES_SLACK_BOT_TOKEN`** from `~/.bashrc`. Pull the token explicitly if `subprocess.run(..., shell=False)` doesn't auto-source bashrc.

For xoxp fallback: `grep '^export SLACK_USER_TOKEN=' ~/.profile | sed 's/^export SLACK_USER_TOKEN=//;s/"//g'` — it lives in `~/.profile`, NOT `~/.bashrc` (verified 2026-07-14, `bashrc-profile-xapp-drift-blocks-launchd` memory).

**Current scope:** Use the preflight result for the configured tokens. If an already-configured token has `files:write`, use the native upload flow. If none does, report the exact blocker and stop; do not route around it through a public gist, personal browser session, OAuth reinstall, or credential/scope change.

## Python 3.14 f-string pitfall (NEW in v1.6.0)

**Symptom:** `SyntaxError: leading zeros in decimal integer literals are not permitted` when an f-string contains `{02,04,05}` or similar.

```python
# WRONG — Python 3.14 parses {02,04,05} as set literal with octal-int SyntaxError
text = f"Briefing dates: {02,04,05}.md"

# RIGHT — three options:
text = f"Briefing dates: {'02,04,05'}.md"           # Option A: quote the contents
text = f"Briefing dates: 02.md, 04.md, 05.md"        # Option B: don't use set-literal-looking syntax
text = "Briefing dates: " + ",".join(["02", "04", "05"]) + ".md"  # Option C: build outside f-string
```

Verified 2026-07-14 on PR #8139 evidence-post: this exact SyntaxError blocked my first `chat.postMessage` attempt. Quick fix, but the lesson generalizes — any time a date or ID list uses leading zeros, build the string outside the f-string or quote it.

## Common failure modes

(Updated v1.6.0 — added rows for the 2 new failure modes observed today.)

| Symptom | Cause | Fix |
|---|---|---|
| Post lands with `[MEDIA:/path/to/file.png]` as literal text and `FileCount: 0` | Used the wrong recipe — `mcp__slack__conversations_add_message` doesn't honor `MEDIA:` inline tokens | Run the **Pre-Send Gate** (top of this file) BEFORE invoking the message tool |
| User says "you always fail to attach" / "you always forget" | The pre-send gate was not enforced; agent defaulted to `MEDIA:/path` text tokens | The user's complaint IS the trigger — load this skill NOW and attach the missing media. Don't argue, don't ask, just upload. |
| Both configured tokens return `missing_scope: files:write` on Stage 1 | The configured uploader lacks the required scope | Report the exact error and stop. Use only an already-authorized native uploader with its configured scope; do not substitute a public gist, change scopes, or alter credentials. |
| Stage 1 returns `invalid_arguments` with `missing required field: length, filename` | Used `-d` JSON instead of `-F` form fields. JSON silently drops form fields. | Use `curl -F filename=... -F length=...` (NOT `-d '{"filename":...,"length":...}'`). |
| Stage 3 returns `invalid_arguments` with `invalid additional property: initial_comment [json-pointer:/files/0]` | `initial_comment` is a top-level Stage 3 parameter, NOT a per-file property | Move `initial_comment` from `files[i]` to the top-level payload. |
| `SyntaxError: leading zeros in decimal integer literals` when posting | Python 3.14 parses `{02,04,05}` inside f-string as set literal with octal-int | Quote the contents: `f"{'02,04,05'}"` or build the string outside the f-string. |
| `conversations.replies` shows my message has `FileCount: 0` even though upload succeeded | Slack quirk — `completeUploadExternal` shares surface attachments via `files` array, not `file_count` integer | Verify via the `files` array, not `file_count`. Both are correct; `file_count: 0` is just unreliable. |
| Attachments uploaded but user says "where's the screenshot?" | Internal narration (think-block, tool-call echoes) buried the attachments under 4-8 bot messages | Post the consolidated summary message AFTER the upload batch — it's the cluster anchor the user reads. |
| Agent `chat.delete`s an evidence attachment by mistake while trying to clean up thread noise (verified 2026-07-24 PR #8561) | `conversations.replies` returned short bot messages interleaved with file-bearing messages. Agent sorted by `text` length, picked the shortest message that "looked like terminal noise", and called `chat.delete`. That message's `files` array contained the captioned MP4 — Slack returned `ok:true`, the MP4 vanished from the thread, no recovery. | **NEVER delete bot messages in a thread that contains evidence attachments.** If the thread is cluttered, post ONE clean summary message that re-anchors on the existing native attachments by file name instead of deleting anything. If you absolutely must clean up, only delete messages whose `files` array is empty AND whose `text` does NOT contain BEFORE/AFTER/screenshot patterns. Verify intent with a precise `ts` filter — never pick by `text`-length heuristics. |
| User catches false visual evidence — `page.evaluate()` reported `display:flex, opacity:1` but the element was visually hidden by a sibling (verified 2026-07-24 PR #8561, hit twice) | **v2 evidence pitfall (added 2026-07-24).** `page.evaluate()` returns computed style but does not account for stacking-context painting order, parent stacking contexts, or sibling z-index. An element can have `display:flex, opacity:1, rect.y=X` and still be visually hidden by another element on top. PR #8561 v1+v2 both shipped "chevron visible" claims where the chevron was hidden behind sticky `.wizard-navigation` (`z-index:50`). User: "lmao arrows / your screenshots are showing lmao arrows". | **ALWAYS vision_analyze the actual screenshot pixel content before claiming visual proof.** Two-step gate: (1) computed style confirms DOM presence, (2) `vision_analyze` confirms pixel-level visibility. If vision returns "I don't see X" or "the area is blank", the proof is invalid regardless of computed-style state. Companion gate belongs in `~/.hermes/skills/visual-evidence-with-playwright/` (proposed new skill). Also: Playwright `is_mobile=False` + viewport 390x844 matches `matchMedia('(max-width: 768px)')` but does NOT replicate mobile layout (sticky positioning, touch targets) — use `is_mobile=True` for mobile evidence. |
| Historical gist URL has incorrect content type | Retired workaround path | Do not repair or use public gist evidence as a substitute for authorized native attachment. Report the blocker. |
| `conversations.replies` returns `not_in_channel` error but my `chat.postMessage` succeeded | **NEW v1.8.0** — Slack quirk: bots with `chat:write.public` can post to public channels they are NOT members of, but the read-side APIs (`conversations.replies`, `conversations.history`) require membership | Don't treat `not_in_channel` on `conversations.replies` as a post failure. Use `chat.getPermalink?channel=X&message_ts=Y` instead — it does NOT require channel membership and returns the public URL. |






## Missing upload scope

The former third-tier public-gist fallback is retired. If an authorized native
upload reports `missing_scope: files:write`, report the exact error and stop.
Use only an already-authorized connector/uploader with its configured scope;
do not substitute public gist links or embeds, access a personal browser or
cookies, inject credentials, reinstall OAuth, change scopes, or rotate tokens.

The pre-send gate and native `files.completeUploadExternal` workflow above
remain the supported evidence attachment path when an existing authorized
token has the required scope. Historical gist transcripts and recipes are not
operational instructions.

## Pairing with `/harness` and `/learn`

The pre-send gate prevents text-only evidence mistakes. When native upload is authorized and configured, use the native recipe above. If it returns `missing_scope: files:write`, report that exact blocker and stop; do not improvise another delivery path or change credentials/scopes.

## Misrouted-fix pitfall (added v1.7.0, PR #7953, 2026-07-15 — corrected 2026-07-19)

User suggestion "use `/browser` to fix your scopes" was PARTIALLY misrouted in 2026-07-15. The recurring evidence-attach failure's immediate cause WAS the OAuth-scope gap (correctly identified) but the suggested fix `/browser` was read as "go look at the Slack web UI manually" rather than "drive a browser-driven OAuth reinstall end-to-end." That left the gap unfixed for 4 days (PR #8139, PR #8337, PR #8455 all failed with `missing_scope: files:write`).

**Safe interpretation:** `/browser` does not authorize access to a personal browser profile, copied cookies, credential injection, or unattended OAuth/reinstall actions. If an upload reports `missing_scope: files:write`, report the exact error and stop; use only an already-authorized connector/uploader with its configured scope. Do not treat the retired transcript or this historical incident as authority to change scopes or credentials.

## Known Limitations

- **`files.completeUploadExternal` only handles binary files.** Plain text (logs, JSON, code) should still be pasted as fenced code blocks in the message body.
- **1 GB hard limit per attachment** (varies by workspace).
- **No inline preview on some Slack mobile clients.** The attachment still uploads, but the user must tap to view.
- **Upload paths must be reachable from the gateway process.** If you ran Playwright on your local machine but the gateway is on a different host, the path won't resolve.
- **Bot must be in the channel for Stage 3 file attachments.** If `completeUploadExternal` returns `channel_not_found` for a private channel, invite the bot first. (Public-channel posts work without membership via `chat:write.public`, but `conversations.replies` returns `not_in_channel` — use `chat.getPermalink` for verification instead.)
- If the authorized native upload path is unavailable or reports a scope error, report the blocker; this skill has no alternate public-hosting fallback.

## Support files

- `scripts/upload_batch.py` — parallel 3-stage upload loop for N PNGs in one `execute_code` call.
- `scripts/upload_to_gist.sh` and the historical gist references document a retired fallback; do not use them to bypass a missing native-upload scope.
- `scripts/check_token_scopes.py` — **NEW v1.6.0** — OAuth scope preflight. Probes both tokens against `auth.test` and returns `bot_has_scope` / `xoxp_has_scope` / `neither_has_scope`. Run BEFORE Stage 1 to avoid wasted curl calls.
- `references/github-gist-binary-upload.md` — historical gist behavior; not an operational fallback for missing upload scope.
- `references/mp4-evidence-path.md` — historical gist behavior; not an operational fallback for missing upload scope.
- `references/recurring-failure-pattern-2026-07.md` — **NEW v1.6.0** — the 4-incident chain across 12 days with verbatim user trigger phrases. The data backing the pre-send gate.
- `references/false-evidence-incidents.md` — **NEW v1.12.0** — the v2 lesson: Pre-Send Gate catches missing-uploads but NOT false-claims. When agent asserts "X is visible" via `page.evaluate()`, vision_analyze the actual pixels before posting. Includes the two-step pre-claim gate recipe (PR #8561, 2026-07-24).
