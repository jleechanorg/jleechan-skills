# Worked Example: /sidekick + /swarm Skill Announcement (2026-07-15)

Reference run for **commentary/opinion drafts about a third-party capability the user built on top of it** (NOT a project announcement, NOT a benchmark). Documents the canonical workflow when the source is a LinkedIn post about a personal workflow tip + skills released as a gist.

## Source

LinkedIn URL: `https://www.linkedin.com/posts/jeffrey-lee-chan_ive-been-able-to-use-fable-without-destroying-share-7483325930719858688-9C6X/`

Extracted via `curl -A "Mozilla/5.0 ... Chrome/126.0.0.0 Safari/537.36" <url>` + Python regex on `<meta property="og:description">`. The og:description had the full post body embedded, including:

- The hook ("I've been able to use fable without destroying the token budget")
- The concrete numbers (2-3 terminals, 10-20 agents per terminal, 8 hours, $200/mo, 20-30% quota)
- The mechanism names (/sidekick, /swarm)
- The pattern source ("devin fusion approach")
- The CTA (gist at `https://lnkd.in/grkPuRWK`)

## What the templater would have gotten wrong

The naive `draft_social_post.py` invocation with `intent="announce /sidekick and /swarm Hermes skills..."` + key-points would have produced drafts that:

- Stuffed every key-point into "What it does" / "Stack" / "Repo:" sections (project-announcement shape, wrong for commentary)
- Used "Hermes" or "jleechanclaw" as the project name instead of treating /sidekick + /swarm as the load-bearing subject
- Built the wrong CTA ("visit the repo" instead of "open the gist and try it")
- Lost the user's voice (the source is personal and uses casual phrasing like "kills the quota")

Root cause: same as the Fable 2D-game 2026-07-11 example — the template treats every intent as "announce a project." When the source is "here's a workflow trick that worked for me," the template needs personal-voice commentary that links to the artifact (gist, video, post).

## What worked: hand-author + MCP-down fallback

### Step 1: Extract source body

Use `curl` + Python regex on `og:description`. `web_extract` cannot fetch LinkedIn (lesson 12) — neither the `ddgs` backend nor `tavily` returns the og:description cleanly.

### Step 2: Hand-author drafts

13 `.md` files in `/tmp/drafts/fable-quota-skill-2026-07-15/`. Each platform got a tailored take:

| Platform | Approach |
|---|---|
| LinkedIn | Personal voice, hook in first 210 chars, gist link, ends with question to drive engagement |
| Hacker News | Show HN format, focus on the failure mode (burned quota first) + 10x cost reduction |
| Twitter/X | 5-tweet thread; hashtags only in final tweet (#AIAgents #Hermes #Fable) |
| Threads | Casual single paragraph, gist "in the comments 👇" |
| Facebook | Long-form personal, same as LinkedIn but no hashtag discipline |
| Instagram | Caption + 30 hashtags; surfaced for mobile (no web compose) |
| Mastodon | Short, single paragraph |
| Dev.to | Markdown article with `/sidekick` + `/swarm` sections, install instructions |
| r/LocalLLaMA | Methodology-focused (local/open model routing) |
| r/OpenAI | OpenAI-specific angle (Codex Spark as primary cheap worker) |
| r/ClaudeAI | Claude Team as comms backbone for /sidekick |
| r/MachineLearning | Research-grade framing with reproducibility table |
| r/singularity | Brief observation, not announcement |

### Step 3: Stage via Aside + base64 stdout capture (NEW pattern, lesson 15)

The Aside REPL cannot `require('fs')`. Capturing a screenshot to disk requires base64-via-stdout:

```bash
aside repl "
const p = await openTab('<url>');
await sleep(3000);
const ss = await p.screenshot();
console.log('SCREENSHOT_B64:' + ss.toString('base64'));
" > /tmp/out.txt 2>&1
grep '^SCREENSHOT_B64:' /tmp/out.txt | sed 's/^SCREENSHOT_B64://' | base64 --decode > /tmp/shot.png
```

For multi-platform loops, use `subprocess.run(["aside", "repl", js], capture_output=True, text=True)` from Python and grep the `SCREENSHOT_B64:` line from `r.stdout` per iteration.

### Step 4: Vision-verify each platform

Per lesson 0 + 11 — DOM-only detection lies. Vision-verify at least one compose-ready screenshot per platform before claiming staged.

**Vision-verify results (2026-07-15):**

| Platform | DOM-detect | Vision verdict | Actual state |
|---|---|---|---|
| Hacker News | compose-ready | compose-ready | ✅ title + url + text fields visible |
| Twitter/X | compose-ready | compose-ready | ✅ "What's happening?" modal, @jleechan2015 signed in |
| Reddit r/LocalLLaMA | compose-ready | compose-ready | ✅ text tab, title + body fields, signed in as jl23423f23r323223r3 |
| Reddit r/OpenAI | compose-ready | compose-ready | ✅ text tab, signed in |
| Reddit r/ClaudeAI | compose-ready | compose-ready | ✅ text tab, signed in |
| Reddit r/MachineLearning | compose-ready | compose-ready | ✅ text tab, signed in |
| DEV.to | compose-ready | compose-ready | ✅ title + markdown editor, signed in |
| Facebook | compose-ready | compose-ready | ✅ "What's on your mind, Jeffrey?" box visible |
| Threads | compose-ready | compose-ready | ✅ "New thread" modal opened via "New thread" button click |
| LinkedIn | compose-ready | feed-loaded | ⚠️ obfuscated classes defeat programmatic click (lesson 17) |
| Mastodon | compose-ready | preview-only | ⚠️ mastodon.social/compose → 404; /publish shows preview but login required (lesson 16) |
| Instagram | n/a | login-wall | ⚠️ no web compose, mobile-only |

### Step 5: Post summary to Slack with MCP-down fallback (NEW path, Phase 3.5)

After staging + vision-verify, post the summary to the originating thread. **When `mcp__slack__conversations_add_message` returns `not_in_channel` or the server reports "unreachable after N consecutive failures", fall back to XOX-P**:

```bash
TOKEN="$SLACK_USER_TOKEN"
curl -fsS -X POST "https://slack.com/api/chat.postMessage" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json; charset=utf-8" \
  --data-binary @<(jq -n --arg txt "$BODY" \
    '{channel: "<chan>", thread_ts: "<ts>", text: $txt}')
```

Reply appears as `$USER` (not Hermes bot). Say so in the body if it might confuse the user. Do NOT stall on "iteration budget exhausted" — the fallback path always works.

## Pitfalls avoided

1. **Did NOT trust `web_extract`** for LinkedIn (per lesson 12). Used curl + og:description regex instead, which returned the full post body.
2. **Did NOT trust `draft_social_post.py`** for commentary/opinion (per Fable worked example). Hand-authored all 13 drafts into `/tmp/drafts/fable-quota-skill-2026-07-15/*.md`.
3. **Did NOT attempt programmatic paste** on Twitter/LinkedIn/Facebook/Threads (per lessons 3 + 11). User pastes manually from `.md` files.
4. **Did NOT waste more than 2 attempts** clicking LinkedIn's "Start a post" trigger (per lesson 17). Stopped after `.locator()` returned 0 matches AND click-by-text returned 0 matches.
5. **Did NOT stall on Slack MCP failure.** Fell back to XOX-P curl immediately per SOUL.md `slack-cross-workspace-fallback-xoxp`.

## File inventory

```
/tmp/drafts/fable-quota-skill-2026-07-15/
├── linkedin.md (945 bytes)
├── hackernews.md (1064 bytes)
├── twitter.md (938 bytes) — 5-tweet thread
├── threads.md (365 bytes)
├── facebook.md (868 bytes)
├── instagram.md (663 bytes) — caption + 30 hashtags
├── mastodon.md (378 bytes)
├── devto.md (1530 bytes)
├── reddit_localllama.md (1496 bytes)
├── reddit_openai.md (980 bytes)
├── reddit_claudeai.md (1125 bytes)
├── reddit_machinelearning.md (1776 bytes)
├── reddit_singularity.md (288 bytes)
├── manifest.json
├── load_results.json
└── screenshots/
    ├── hackernews_load.png (54 KB)
    ├── twitter_load.png (624 KB)
    ├── reddit_localllama_load.png (491 KB)
    ├── reddit_openai_load.png (512 KB)
    ├── reddit_claudeai_load.png (452 KB)
    ├── reddit_machinelearning_load.png (555 KB)
    ├── threads_load.png (432 KB) + threads_compose.png (294 KB)
    ├── facebook_load.png (1.3 MB)
    ├── devto_load.png (164 KB)
    ├── linkedin_load.png (1.1 MB) + linkedin_compose.png (1.0 MB)
    └── mastodon_load.png (184 KB, 404) + mastodon_publish.png (279 KB, preview-only)
```

## Recommended workflow for future commentary runs

1. Extract the source URL body (LinkedIn og:description, Twitter card meta, etc.) via `curl` + Python regex. `web_extract` cannot fetch LinkedIn.
2. Run `draft_social_post.py` once to scaffold the directory + manifest, but READ every generated `.md` file. If templating misfires (hallucinated project name, wrong CTA, stuffed bullets), hand-author the drafts directly into the same files.
3. Stage with the base64-via-stdout pattern (lesson 15). Capture `SCREENSHOT_B64:` per platform, decode to disk.
4. Vision-verify with explicit questions ("Is the compose form visible with title input and body textarea? Or login wall?").
5. Do NOT trust programmatic paste. Tell the user the drafts are in `/tmp/drafts/<run>/<platform>.md` and the compose tabs are open — they'll paste manually.
6. Post the summary with MCP-down fallback (Phase 3.5) — XOX-P curl if MCP unreachable.
7. Surface 3 next-step options:
   - Sign in to login-walled platforms
   - POST APPROVED the compose-ready ones (after manual paste)
   - Revise any draft

## Decision log

- **Single-tweet vs thread**: chose 5-tweet thread because the source has 4 distinct claims (mechanism names, quota numbers, pattern source, CTA) — fits Twitter's per-tweet structure better than a single wall of text.
- **r/Rag not used**: the source isn't about retrieval. Skipped.
- **Reddit 5 subs chosen on their relevance to the mechanism**: LocalLLaMA (model routing), OpenAI (Codex Spark), ClaudeAI (Claude Team), MachineLearning (research-grade reproducibility), singularity (observation).
- **r/singularity only got one short paragraph** because that sub bans zero self-promo announcements (verified 2026-07-05 rule set in `references/subreddit-rules.md`).
- **Mastodon URL correction**: hit the 404 on `/compose`, switched to `/publish`, then caught the login requirement via vision. Documented as lesson 16.
- **LinkedIn manual click**: 2 attempts failed, switched to manual-paste guidance. Did NOT keep retrying — 3 attempts is the budget per skill rule.
