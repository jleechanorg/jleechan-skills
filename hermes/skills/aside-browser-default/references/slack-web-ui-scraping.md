# Slack Web UI scraping — verified recipes

Captured 2026-07-14 driving the Slack "Later" reminders page (https://app.slack.com/client/T09FXQ4LCQP/later) via Aside headless browser. Generalizes to any Slack web view (Later, Activity, Saved items, custom channel history) where Slack renders a virtualized list with a fixed header + tabs pattern.

Apply `~/.claude/skills/browser-control/SKILL.md` before using this historical recipe. Navigate only in an already-running, verified agent-owned background context. Do not use a personal browser window, profile, cookie, or login state. Do not launch or activate Aside for this task. If the required authenticated context is unavailable, stop and report the blocker; use cookie transfer only when the task explicitly authorizes exactly one named agent-owned source profile, under the guarded browser-control lifecycle. Never probe an internal API with copied browser credentials.

## Why browser, not Web API

The Slack Web API is blocked from several read paths the user expects "their reminders" to expose. For `reminders.list` specifically, the only path is the web UI. Verified 2026-07-14:

```bash
curl -fsS -X POST "https://slack.com/api/reminders.list" \
  -H "Authorization: Bearer $SLACK_USER_TOKEN" \
  --data "limit=100"
# → {"ok":false,"error":"missing_scope","needed":"reminders:read",
#    "provided":"identify,channels:history,groups:history,im:history,..."}
```

→ Use the Slack web UI only in an already-running, verified agent-owned background context. Otherwise stop and report the auth/context blocker; do not fall through to a personal signed-in browser or launch Aside.

## Slack Later page structure

Three tabs (**In progress**, **Archived**, **Completed**), each with a virtualized item list inside a fixed-position scrollable container. Each item has the structure:

```
<status marker>     ← "Incomplete • 7 days ago"  OR  "Due in 14 minutes"
<channel name>      ← "worldai-bugs"  (single-line, no children)
<author>            ← "Jeffrey Lee-Chan" or "hermes" or "MCP Agent Mail"
<message text>      ← the reminder body, may wrap multiple lines
```

## Pitfall — `body.innerText` only captures the visible viewport, NOT the whole virtualized list

The first capture (2026-07-14, this page) used `document.body.innerText` after a single scroll-to-bottom and looked complete: 25 items visible, tab badge "99+". It was NOT complete — Slack renders items in a `.c-virtual_list` whose rows are virtualized; `body.innerText` only returns what's currently in the DOM viewport. Calling `scrollTop = scrollHeight` once either left the scroll position at the bottom without triggering Slack's incremental row-fetcher, or fetched only the next viewport.

User-visible symptom: *"why did you stop wtf"* after seeing 25 reminders when the actual backlog was **365 items** (101 In Progress + 264 Completed).

**Fix:** scroll in 0.85 × `clientHeight` increments and re-extract on every tick until `scrollTop` stops changing. Use the `.c-virtual_list__item` row class for per-row extraction — it's stable across Slack views and survives scrolling without re-querying.

## Verified REPL script — INC First scroll dump (2026-07-14, got 25 items — DO NOT REPEAT)

The full flow — open tab, click each tab, scroll the virtualized list, parse text — must run inside ONE `aside repl` call. State doesn't survive between invocations (see gotchas §8).

```bash
# Write the script to a file first (avoid bash escaping issues — see gotchas §12)
cat > /tmp/slack_later_dump.js <<'JS'
const p = await openTab('https://app.slack.com/client/T09FXQ4LCQP/later');
await new Promise(r => setTimeout(r, 5000));  // hydration

// Tab discovery (just for inspection)
const tabInfo = await p.evaluate(() => {
  const out = [];
  document.querySelectorAll('*').forEach(el => {
    const t = el.textContent.trim();
    if (['In progress','Completed','Incomplete','Archived'].includes(t) &&
        t.length < 30 && el.children.length === 0) {
      const r = el.getBoundingClientRect();
      out.push({ tag: el.tagName, text: t, role: el.getAttribute('role'),
                 cls: (el.className||'').toString().slice(0,80),
                 y: Math.round(r.y), w: Math.round(r.width) });
    }
  });
  return out;
});
console.log('TABS_FOUND:', JSON.stringify(tabInfo));

// Click each tab + scroll + dump
const tabs = ['In progress', 'Completed', 'Archived'];
const results = {};
for (const tabName of tabs) {
  // Tab buttons are <button class="c-tabs__tab"> — NOT the inner <span>
  const clicked = await p.evaluate((name) => {
    const btn = [...document.querySelectorAll('button.c-tabs__tab')]
      .find(b => b.textContent.trim().startsWith(name));
    if (btn) { btn.click(); return true; }
    return false;
  }, tabName);
  await new Promise(r => setTimeout(r, 3500));

  // Scroll virtualized list to bottom (scrollHeight often ~5-10x clientHeight)
  await p.evaluate(() => {
    const candidates = [...document.querySelectorAll('*')].filter(el => {
      const s = getComputedStyle(el);
      return (s.overflowY === 'auto' || s.overflowY === 'scroll') &&
             el.scrollHeight > el.clientHeight + 50;
    });
    // Pick the one that contains known reminder text
    const target = candidates.find(el =>
      el.textContent.includes('Incomplete') || el.textContent.includes('voyage')
    ) || candidates[candidates.length-1];
    if (target) target.scrollTop = target.scrollHeight;
  });
  await new Promise(r => setTimeout(r, 3000));

  results[tabName] = {
    clicked,
    text: await p.evaluate(() => document.body.innerText)
  };
}
for (const k of Object.keys(results)) {
  console.log('=== TAB:', k, 'clicked=', results[k].clicked, '===');
  console.log(results[k].text);
  console.log('=== END', k, '===');
}
JS

aside repl "$(cat /tmp/slack_later_dump.js)"
```

**Pitfall — `button.c-tabs__tab` vs inner `<span>`:** the inner `<span class="c-tabs__tab_content">` is also matched by `textContent.includes('In progress')` but clicking it does nothing. Always click the `<button>` parent. `startsWith(name)` ensures you don't false-match "In progress" inside "In progress99+" (the badge counter).

**Pitfall — tab click sometimes shows the wrong tab's content** if the click is too fast or the previous tab is still hydrating. The 3.5s `setTimeout` between clicks is the minimum that worked reliably; bump to 5s for slow networks.

## Parser (Python, regex-based)

The `document.body.innerText` output is stable and line-oriented. Parse with these two regexes:

```python
import re

def parse_reminders(text: str) -> list[dict]:
    """Parse 'In Progress / Incomplete' tab output."""
    chunks = re.split(
        r'(?=Incomplete • \d+ (?:day|hour)s? ago'
        r'|Due in \d+ (?:minute|hour)s?(?: •)?'
        r'|Incomplete • (?:just now|an? hour ago))',
        text
    )
    items = []
    for chunk in chunks:
        chunk = chunk.strip()
        if not chunk: continue
        m = re.match(
            r'^(Incomplete • (\d+ (?:day|hour)s? ago)'
            r'|Due in (\d+ (?:minute|hour)s?))',
            chunk
        )
        if not m: continue
        marker = m.group(1)
        rest = re.sub(r'^[•·\s]+', '', chunk[m.end():]).strip()
        lines = [l.strip() for l in rest.split('\n') if l.strip()]
        if len(lines) >= 3:
            channel, author, body = lines[0], lines[1], ' '.join(lines[2:])
        elif len(lines) == 2:
            channel, author, body = '-', lines[0], lines[1]
        else:
            channel, author, body = '-', '-', lines[0] if lines else ''
        items.append({'marker': marker, 'channel': channel,
                      'author': author, 'text': body[:400]})
    # Strip Slack sidebar chrome that bled into innerText
    CHROME = {'Home','DMs','Activity','Files','Later','More','Admin',
              'JA','Describe what you are looking for'}
    return [it for it in items
            if it['channel'] not in CHROME
            and not it['channel'].isdigit()
            and it['channel'] != '99+']


def parse_completed(text: str) -> list[dict]:
    """Parse 'Completed' tab — no age markers, just channel + author + text."""
    CHANNELS = {'worldai-bugs','worldai','all-$USER-ai','voyage',
                'life','ai-universe','cmux','agent-orchestrator','agentf'}
    chunks = re.split(r'(?=' + '|'.join(CHANNELS) + r')', text)
    items = []
    for chunk in chunks:
        lines = [l.strip() for l in chunk.strip().split('\n') if l.strip()]
        if len(lines) >= 3 and lines[0] in CHANNELS:
            items.append({
                'channel': lines[0],
                'author': lines[1],
                'text': ' '.join(lines[2:])[:400]
            })
    return items
```

**Pitfall — `body.innerText` includes Slack sidebar text** (`Home`, `DMs`, `Activity`, `Files`, `Later`, `More`, `Admin`, channel badges like `1`, `99+`, the search-box placeholder). Always strip CHROME before treating parsed items as real reminders. The user may also have `JA` (avatar initials) leak in.

## Categorization (stale vs needs attention)

Recommended buckets — verified useful 2026-07-14:

| Bucket | Marker | Action |
|---|---|---|
| 🔴 STALE | `Incomplete • \d+ days? ago` (≥1 day) | Triage or archive |
| 🟡 RECENT | `Incomplete • \d+ hours? ago` (<24h) | Likely top of user's mind |
| 🔵 UPCOMING | `Due in \d+ (?:minute\|hour)s?` | Will fire imminently, prioritize |
| ✅ COMPLETED | (no marker on this tab) | Archive or clear |

## Aside ultrabrowse times out — use direct REPL

The `aside --effort ultrabrowse "..."` NL agent is too slow for multi-step Slack flows. Verified 2026-07-14: a single "navigate, list reminders, categorize" prompt timed out at 180s with no useful output. Direct REPL with the script above completes in ~15-25s per tab.

**Rule of thumb:** if the task needs more than ~2 sequential browser steps AND has a deterministic structure (open URL → click N tabs → scrape text), use direct `aside repl`. If the task is genuinely exploratory ("find a contact who knows X"), use `ultrabrowse`.

## Posting results back to Slack

After scraping, you'll want to post a summary back. The `mcp__slack__conversations_add_message` (bot token) is blocked with `not_in_channel` for `C09GRLXF9GR` (operator-direct channel) — see SOUL.md `slack-cross-workspace-fallback-xoxp` for the XOX-P fallback recipe:

```python
import subprocess, json, re
profile = open('$HOME/.profile').read()
m = re.search(r'^export SLACK_USER_TOKEN="([^"]+)"', profile, re.MULTILINE)
TOKEN = m.group(1)
payload = {"channel": "C09GRLXF9GR", "thread_ts": "<parent_ts>",
           "text": "<your summary>"}
with open('/tmp/payload.json', 'w') as f: json.dump(payload, f)
r = subprocess.run(['curl', '-fsS', '-X', 'POST',
                    'https://slack.com/api/chat.postMessage',
                    '-H', f'Authorization: Bearer {TOKEN}',
                    '-H', 'Content-Type: application/json',
                    '-d', '@/tmp/payload.json'],
                   capture_output=True, text=True, timeout=30)
# Verify: response includes "ok":true and a ts
print(r.stdout)
```

**Pitfall — XOX-P posts appear as `$USER`, not as the hermes bot.** Say so in the body if the user might be confused. The `conversations.replies` will show `bot_id: B0BGY53L8N8` only for bot-token posts.

## Screenshot evidence (optional)

If you need to attach visual evidence to the Slack reply, see the `evidence-attach-to-slack` skill for the 3-stage `files.completeUploadExternal` recipe. Bare `MEDIA:/path` text tokens render as literal text — do not use them.

## Other Slack web views this pattern applies to

The same openTab → click tabs → scroll virtualized list → parse `body.innerText` flow works for:

- **Activity** (`/activity`) — mentions, reactions, threads
- **All DMs** (`/messages`) — DM list with preview text
- **Saved items** (`/saved`) — bookmarked messages
- **Channel member lists** — click "View members" modal
- **Custom left-rail sections** (Pinned channels, Starred) — sidebar `data-qa="<...>"` selectors

What does NOT work via this pattern: file uploads, message composition, search (`/search` has its own URL pattern `/search?q=...` and result rendering that needs different selectors).

## Verified REPL script — CORRECTED incremental-scroll loop (2026-07-14, got 365 items)

This is the actually-working pattern. Scroll 0.85× `clientHeight` per tick, accumulate unique `.c-virtual_list__item` rows from the visible viewport, stop when `scrollTop` doesn't change.

```js
// Open tab + click In progress
const p = await openTab('https://app.slack.com/client/T09FXQ4LCQP/later');
await new Promise(r => setTimeout(r, 5000));
await p.evaluate(() => {
  const btn = [...document.querySelectorAll('button.c-tabs__tab')]
    .find(b => b.textContent.trim().startsWith('In progress'));
  if (btn) btn.click();
});
await new Promise(r => setTimeout(r, 3500));

const all = [];  // dedup'd rows
for (let i = 0; i < 60; i++) {  // 60 ticks × ~1.5s = 90s max, well under REPL timeout
  const rows = await p.evaluate(() => {
    const items = document.querySelectorAll('.c-virtual_list__item');
    const out = [];
    items.forEach(item => {
      if (item.offsetParent === null) return;
      const r = item.getBoundingClientRect();
      if (r.y < 60 || r.y > 760) return;  // outside viewport
      const t = item.textContent.trim();
      if (t.length < 30 || t.length > 600) return;
      const k = t.slice(0, 200);
      if (out.find(x => x.startsWith(k))) return;
      out.push(k);
    });
    return out;
  });
  rows.forEach(r => { if (!all.includes(r)) all.push(r); });

  // Scroll 0.85× clientHeight — leaves a small overlap so rows at the edge
  // get a chance to re-extract if Slack swaps them in mid-tick.
  const r = await p.evaluate(() => {
    const cands = [...document.querySelectorAll('*')].filter(el => {
      const s = getComputedStyle(el);
      return (s.overflowY === 'auto' || s.overflowY === 'scroll') &&
             el.scrollHeight > el.clientHeight + 50 && el.scrollHeight > 500;
    });
    const t = cands.find(el => /Incomplete|Due in/.test(el.textContent)) || cands[cands.length-1];
    if (!t) return null;
    const before = t.scrollTop;
    t.scrollTop = t.scrollTop + t.clientHeight * 0.85;
    return { before, after: t.scrollTop, sh: t.scrollHeight, ch: t.clientHeight };
  });
  if (!r) break;
  await new Promise(r => setTimeout(r, 1500));
  if (r.after === r.before) break;                              // no scroll progress
  if (r.after + r.ch * 0.3 >= r.sh) break;                      // near end
}
console.log(`FINAL: ${all.length} unique items`);
all.forEach((t, i) => console.log(`[${i}] ${t}`));
```

**Why this works (and the one-shot doesn't):**
- `.c-virtual_list__item` rows are the actual per-item DOM nodes Slack renders. They get added/removed by Slack's virtualization as you scroll.
- `body.innerText` re-serializes whatever is currently mounted, but if Slack's virtualization has already unmounted rows above the viewport, they don't come back into `innerText` until you scroll back up.
- Iterative scroll + per-row dedup means you see every row that was ever mounted during your scroll pass.

**Completed-tab variant (no `Incomplete`/`Due in` markers — no anchor needed, just pull every visible row):**

```js
await p.evaluate(() => {
  const btn = [...document.querySelectorAll('button.c-tabs__tab')]
    .find(b => b.textContent.trim().startsWith('Completed'));
  if (btn) btn.click();
});
await new Promise(r => setTimeout(r, 4000));

const all = [];
for (let i = 0; i < 80; i++) {
  const items = await p.evaluate(() => {
    const items = document.querySelectorAll('.c-virtual_list__item');
    const out = [];
    items.forEach(item => {
      if (item.offsetParent === null) return;
      const r = item.getBoundingClientRect();
      if (r.y < 60 || r.y > 760) return;
      const t = item.textContent.trim();
      if (t.length < 30 || t.length > 600) return;
      out.push(t.slice(0, 400));
    });
    return out;
  });
  items.forEach(t => { if (!all.includes(t)) all.push(t); });
  // ... same scroll loop as above
}
```

**Stop conditions** (any one ends the loop):
1. `scrollTop` stops changing between ticks (`before === after`) — Slack stopped loading rows.
2. `scrollTop + clientHeight × 0.3 ≥ scrollHeight` — close enough to the end.
3. Tick counter exceeds 60-80 — defensive timeout.

## Per-row parser (handles `channelhermes` concatenation)

Slack sometimes concatenates `channel` and `hermes` author into one word (e.g. `worldaihermes`, `all-$USER-aihermes`). The regex below splits them back:

```python
import re
def parse_row(text: str) -> dict:
    # Split the leading "channelauthor" prefix if author is known
    m = re.match(
        r'^([a-z][a-z0-9\-_]*?)'                            # channel (lowercase + hyphens)
        r'(Jeffrey Lee-Chan|hermes|MCP Agent Mail|Claude|codex|Hermes)'  # author
        r'(.*)$',
        text, re.DOTALL
    )
    if m:
        return {'channel': m.group(1), 'author': m.group(2), 'text': m.group(3).strip()[:400]}
    # Fallback: channel + first-name-only author (e.g. "Jeffrey" alone when
    # "Lee-Chan" got eaten by another extractor)
    m = re.match(r'^([a-z][a-z0-9\-_]+)(Jeffrey|hermes)(.*)$', text, re.DOTALL)
    if m:
        author = 'Jeffrey Lee-Chan' if m.group(2) == 'Jeffrey' else 'hermes'
        return {'channel': m.group(1), 'author': author, 'text': m.group(3).strip()[:400]}
    return {'channel': '?', 'author': '?', 'text': text[:400]}
```

**Chrome lines to strip before parsing:** `Home`, `DMs`, `Activity`, `Files`, `Later`, `More`, `Admin`, `JA`, `Describe what you are looking for`, channel badges (`1`, `99+`, `0`), `Direct Message` (Slack DM items use that as a "channel" name).
