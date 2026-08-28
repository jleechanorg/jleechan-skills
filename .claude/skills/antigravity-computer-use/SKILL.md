---
name: antigravity-computer-use
description: Use Claude Code to control Google Antigravity IDE on macOS via Peekaboo. Explicitly supports targeting either the Agent Manager window or the Editor window (worktree/editor titles), plus auto routing. Covers workspaces, conversations, Knowledge/Browser/Settings panels, keyboard shortcuts, model selection, planning modes, artifacts, and menu bar. Trigger when the user asks to automate, click, send messages to, or interact with the Antigravity app, or to choose Manager vs Editor.
---

# Antigravity Computer Use (macOS via Peekaboo)

Google Antigravity is an AI-powered, agent-first IDE (a modified VS Code fork) by Google. It has two primary views: **Agent Manager** ("Mission Control") and **Editor** (VS Code-like). This skill controls it via Peekaboo's native macOS accessibility API.

For the core screenshot-decide-act loop, see the `claude-code-computer-use` skill.

**Official docs:** https://antigravity.google/docs
**CLI tool:** `agy`

---

## MANDATORY: Allow Dialog Check — After EVERY Screenshot

### Mandatory lesson log (most recent first)
- 2026-04-05: Sidebar spinner is UNRELIABLE for detecting active conversations — spinner ◌ persists even when conversation is dead/idle; MUST cross-check with red stop square in bottom-right of chat input area AND the status bar model indicator; three failure modes: (1) zombie spinner = spinner + no red square + send arrow → conversation dead, send "Continue"; (2) frozen-active = spinner + red square + timestamp >1h → stuck in loop, interrupt and redirect; (3) actually working = spinner + red square + timestamp <30m → leave alone; status bar shows "Claude Opus 4.6 (Thinking)" with red ■ = active, "Gemini 3.1 Pro (High)" with send → = idle
- 2026-04-05: VS Code "Remote Window" dialog can open in editor windows (shows SSH/container options) — blocks agent silently; press Escape to close, then verify red-stop still present to confirm agent resumes
- 2026-04-05: win 902 gutter FP — x≈2 (retina x=4) at left edge is always a VS Code diff/edit gutter indicator; add `cx//2 > 30` filter (logical x > 30) to PIL scan to skip all left-edge detections in editor windows
- 2026-04-05: Manager window IDs change every Antigravity relaunch — ALWAYS re-run `peekaboo window list` at session start; never cache window IDs across restarts; current session IDs: Manager=1191, worldai_claw editor=902
- 2026-04-05: Clicking conversation sidebar items by elem_N sometimes doesn't switch view when another conversation is actively generating — use coordinate click at approximate sidebar y position instead; if coord also fails, try a different y offset (items are ~25px apart logical)
- 2026-04-05: "New Conversation" (elem_22) click in Manager sometimes routes message to wrong conversation (the one already selected, not the new one) — after clicking New Conversation, verify the title bar changed before pasting; use `agy chat --mode agent --reuse-window "prompt"` from the target workspace directory as alternative
- 2026-04-05: Opening a workspace folder from Manager (clicking "Open Folder" or workspace item) closes the Manager floating window and opens an editor window with inline Agent panel — the Manager window_id becomes invalid; use "Open Agent Manager" button or "Switch to Agent Manager" in the editor to reopen
- 2026-04-05: Editor Agent panel text field coords: window at x=-28,y=-998,w=1189,h=857 → text input at logical x≈987, y≈390 → screen (959,-608); use these as starting coords, adjust if click misses
- 2026-04-05: Manager conversation input at screen (860,-230) when Manager is at x=429,y=-1005,w=1437,h=849 — reliable across sessions as long as Manager hasn't been resized
- 2026-04-05: Red stop square (active generation indicator) in editor Agent panel appears at retina x≈2312-2331, y≈1608-1627 (for win 902 1189x857) = logical x≈1156, y≈804 — bottom-right of Agent panel; filter right-side only (x > 80% of image width) to avoid false positives from left-side gutter
- 2026-04-05: win313/319/334 FPs — light-blue code highlights [136,201,245] and blue UI elements in non-Manager editor windows persist after click; muted blue with G>130 is NOT a button; add all persistent coords to FP_SET after first click-persist confirmation; check G<165 threshold before counting as real Allow
- 2026-04-05: win319 ($USER—list window at 186,-990) generates multiple stacked Allow dialogs — each click reveals next one; scan persists showing new coords; click each until CLEAN; FP after 2nd persistence
- 2026-04-04: Tab bar FP — Antigravity's blue active-tab indicator spans the full window width at retina y=0-120 (logical y=0-60); skip rows < 120 retina to avoid detecting tab bar blue as Allow dialogs; bottom status bar also fires at retina y>1600 with muted blue [70,127,161] — skip if B<165 or if G>130 (muted blue is not Allow button)
- 2026-04-04: PIL scan thresholds were too strict — B>150, R<150, B>R+50 missed Allow button with edge pixels having R up to 197; real Allow button had B~203, R~39 mean but gradients/edges up to R=197; CORRECT thresholds: B>130, R<180, B>R+30, G<B; also scan from row 0 (not h//2) since dialogs can appear anywhere; min pixel threshold raised to 200 to compensate for looser thresholds
- 2026-04-04: MANDATORY — keep 3 conversations active at all times; check at every cycle end; if <3 active, click idle 24h conversations in reverse-cron order and send continuation tasks until 3 are generating (confirmed via red stop square, not just A11y spinner which lags)
- 2026-04-04: PIL scan MUST cover ALL Antigravity editor windows dynamically — hardcoding only wt-task2 (WIN_X=186) missed Allow dialog in worldai_claw editor (WIN_X=-28, WIN_Y=-998) for >10 min; fix: run `osascript` to get ALL window positions each cycle, then scan each one; never hardcode a single window's bounds as the only scan target; the worldai_claw conversation is a SEPARATE editor window from wt-task2
- 2026-04-04: "Allow directory access to /Users/.../worldai_claw/.github/workflows?" dialog has TWO blue buttons ("Allow Once" + "Allow This Conversation") — both are valid click targets; the PIL scan still works because it finds the rightmost blue cluster; click the rightmost detected button (Allow This Conversation) for persistent permission
- 2026-04-03: FP at (1458,846) — persists after click; blue [99,147,199] "Open Editor" link text in Manager top bar; add to FP set
- 2026-04-03: Teal/cyan VS Code filter — add `G > B` rejection to PIL scan; [114,199,177] and similar teal pixels pass the B>R+50 filter but are VS Code editor syntax colors, not Allow buttons; check center pixel: if arr[cy*2,cx*2][1] > arr[cy*2,cx*2][2] (G>B) then skip; also add FP coords (1129,672) and (1115,674) to FP set for this region
- 2026-04-03: FPs at (1322,695), (1127,897), (1132,934) — persistent after click; (1322,695) in right-panel conversation text area, (1127,897) and (1132,934) near bottom ~y=900-940 which is the conversation input edge; add all to FP set
- 2026-04-03: FP at (968,887) — near-bottom of Manager window, persists after click; likely blue text in conversation input area or VS Code bleed-through; add `abs(scr_cx-968)<30 and abs(scr_cy-887)<30: continue` to FP filter
- 2026-04-03: FP at (1084,544) — VS Code editor blue Python import/type keywords bleeding through Manager window at mid-height; persists after multiple clicks; add `abs(scr_cx-1084)<30 and abs(scr_cy-544)<30: continue` to FP filter
- 2026-04-03: VS Code editor window overlapping Manager causes FP loop — editor Python syntax highlighting (blue keywords: import, from, def) triggers persistent detections at (1093,706), (1226,761), (1342,634); all in x=1050-1400, y=630-780 zone; add FP guards for each and raise min x to 1400+ when editor is overlapping, OR close editor before PIL scan
- 2026-04-03: blue hyperlink in Manager conversation panel at (964,626) — PR URL in text, NOT a dialog; add `abs(scr_cx-964)<50 and 580<scr_cy<680: continue` to FP filter; or better: raise minimum x for Manager to 1050 since real Allow dialogs appear in right portion of conversation panel
- 2026-04-03: CRITICAL coordinate bug — `screencapture -x` captures FULL SCREEN at retina 2x resolution; correct screen coord is `scr_cx = cx//2` and `scr_cy = cy//2` (NO WIN_X/WIN_Y offset); WIN offset is wrong because cx,cy are already full-screen pixel positions; the old formula `scr_cx = WIN_X + cx//2` was off by 100px and caused all Allow clicks to miss; update all PIL scans to use bare `cx//2, cy//2`; window bounds check still valid with logical coords: `if not (WIN_X < cx//2 < WIN_X+WIN_W and WIN_Y < cy//2 < WIN_Y+WIN_H): continue`
- 2026-04-03: PIL scan threshold should be 200+ pixels (not 50) to avoid artifact icon badges (small ~50px blue circles on file/code action icons in conversation); add window bounds check: `if not (WIN_X < scr_cx < WIN_X+WIN_W and WIN_Y < scr_cy < WIN_Y+WIN_H): continue` to exclude detections outside Antigravity window
- 2026-04-03: textField LABEL in peekaboo A11y shows the last SENT message content (aria-label pattern) — not current input. Check VALUE field to see what's currently typed. Empty label="text entry area" = field is empty.
- 2026-04-03: test keystrokes sent via `osascript -e 'tell application "System Events" to keystroke "..."'` ACCUMULATE in text field — always run cmd+a+delete FIRST, then paste, to ensure field is clean; osascript with colons in strings can fail with syntax errors — break message into pieces without colons
- 2026-04-03: peekaboo paste does NOT replace selected text in Antigravity's web-rendered textarea — use osascript to clear field: `osascript -e 'tell application "System Events" to tell process "Antigravity" to keystroke "a" using {command down}' && osascript -e 'tell application "System Events" to tell process "Antigravity" to key code 51'` then peekaboo paste; this reliably clears and replaces field content
- 2026-04-03: blue file-path hyperlinks in agent output appear as FPs at x≈1067, y≈660-720 — add `abs(scr_cx-1067)<50 and 660<scr_cy<720` to FP filter; prefer bottom-strip scan (y > 85% of h) for real Accept All buttons which have 500+ px
- 2026-04-03: persistent blue FP at (1247,689) — blue code/GraphQL text in conversation panel, same coord after click → add `abs(scr_cx-1247)<30 and abs(scr_cy-689)<30` to FP filter; consider raising x threshold from 1200→1250 to eliminate this zone
- 2026-04-03: persistent blue FP at (1579,782) — same coord fires after click, does not dismiss → add `abs(scr_cx-1579)<30 and abs(scr_cy-782)<30` to FP filter
- 2026-04-03: blue diff text / code in conversation panel triggers persistent FP at (1380,537) — add `abs(scr_cx-1380)<30 and abs(scr_cy-537)<30` to FP filter; if same coord fires 2+ times after clicking, it's a FP
- 2026-04-03: blue terminal text (worktree paths, highlighted lines) triggers FP at (1256,546-570) — add `abs(scr_cx-1256)<30 and 540<scr_cy<580` to FP filter; real Allow dialogs have 500+ blue pixels, not terminal text
- 2026-04-03: Manager conversation textField (elem_68) only appears in A11y after clicking at screen coords (480,905) — NOT at y=940+ (which hits Add context or model selector popups); click (480,905) first, THEN get fresh snapshot and click elem_68 to focus; TF label shows current text content (updated as you type)
- 2026-04-03: elem_30 input field accumulates unset text from multiple paste attempts across monitoring cycles → always click elem_30, osascript cmd+a+delete, THEN paste new message; inspect elem_30 label to detect residual text from prior sends
- 2026-04-03: (1746,849) FP — just outside abs(x-1707)<40 and y<840 guard (y=849>840); extend y threshold to y<860 to catch this zone: `if abs(scr_cx-1707)<40 and scr_cy<860: continue`
- 2026-04-03: x≈1707 full-column FP zone filtered real Accept All/Allow button at (1697,856) → FP zone must include y<840 guard; real button appears at y≈856

**This is the #1 cause of stuck agents. Check EVERY time you take a screenshot.**

After any `screencapture`, immediately run this PIL scan before doing anything else:

```bash
check_allow_dialog() {
  local IMG="$1" WIN_X="$2" WIN_Y="$3"
  python3 -c "
from PIL import Image
import numpy as np, os, sys
img = Image.open('$IMG')
arr = np.array(img)
h, w = arr.shape[:2]
for row_start in range(0, h, 20):
    region = arr[row_start:row_start+40, :]
    blue_mask = (region[:,:,2] > 130) & (region[:,:,0] < 180) & (region[:,:,2] > region[:,:,0] + 30) & (region[:,:,1] < region[:,:,2])
    if np.sum(blue_mask) > 200:
        coords = np.where(blue_mask)
        xs = coords[1]
        xs_sorted = np.sort(np.unique(xs))
        gaps = np.diff(xs_sorted)
        big_gaps = np.where(gaps > 15)[0]
        right_start = xs_sorted[big_gaps[-1]+1] if len(big_gaps) > 0 else xs_sorted[int(len(xs_sorted)*0.6)]
        cx = int((right_start + xs_sorted[-1]) / 2)
        cy = int(np.mean(coords[0][xs >= right_start])) + row_start
        scr_cx = int(os.environ.get('WIN_X',0)) + cx//2
        scr_cy = int(os.environ.get('WIN_Y',0)) + cy//2
        wx = int(os.environ.get('WIN_X',0))
        # FP zones (worldai_claw window x=70,y=81,w=1684,h=900):
        if scr_cx < wx+150: continue  # gutter FP
        if abs(scr_cx-1434)<40 and abs(scr_cy-629)<40: continue  # Review Changes link FP
        if abs(scr_cx-1707)<40 and scr_cy < 840: continue  # sidebar FP (y<840 only — real Allow/Accept button appears at y≈856)
        if abs(scr_cx-1504)<30 and abs(scr_cy-769)<30: continue  # PR URL link FP
        print(f'ALLOW:{scr_cx},{scr_cy}')
        break
" WIN_X=$WIN_X WIN_Y=$WIN_Y 2>/dev/null
}

ALLOW=$(check_allow_dialog /tmp/antig_screenshot.png $WIN_X $WIN_Y)
if [[ "$ALLOW" == ALLOW:* ]]; then
  COORDS="${ALLOW#ALLOW:}"
  peekaboo click --app Antigravity --window-id "$MANAGER_ID" --coords "$COORDS"
  sleep 1
  # Re-screenshot to confirm dismissed, then re-check
  screencapture -x -R${WIN_X},${WIN_Y},${WIN_W},${WIN_H} /tmp/antig_screenshot.png
fi
```

**When to run this check:**
1. After initial screenshot at start of any task
2. After sending any message (wait 3s, re-screenshot, check)
3. In every monitoring loop cycle

**CRITICAL — Scan ALL windows, not just one**: Every monitoring cycle MUST enumerate ALL Antigravity editor windows dynamically and scan each one. Hardcoding a single window's bounds is a bug — different workspaces open in different editor windows with different coordinates. Example:

```bash
# Get ALL Antigravity window positions (run each cycle)
ALL_WINS=$(osascript -e '
tell application "System Events"
  tell process "Antigravity"
    set wins to every window
    repeat with w in wins
      log (name of w) & "|" & (position of w as string) & "|" & (size of w as string)
    end repeat
  end tell
end tell
' 2>&1)

# Parse each window and scan it
echo "$ALL_WINS" | while IFS='|' read title pos size; do
  x=$(echo "$pos" | grep -oE '^-?[0-9]+')
  y=$(echo "$pos" | grep -oE -- '-?[0-9]+$')
  w=$(echo "$size" | grep -oE '^[0-9]+')
  h=$(echo "$size" | grep -oE '[0-9]+$')
  screencapture -x -R${x},${y},${w},${h} /tmp/antig_scan_${x}_${y}.png 2>/dev/null
  # Run PIL scan on /tmp/antig_scan_${x}_${y}.png with WIN_X=$x WIN_Y=$y
done
```

This was the root cause of the 2026-04-04 miss: scan was targeting only wt-task2 (x=186, y=-990) but the Allow dialog appeared in the worldai_claw editor window (x=-28, y=-998) — a completely different window never scanned.

**Why**: Allow dialogs are web-rendered (not in A11y tree). They block ALL agent progress silently. The agent shows `progress_activity` spinner but never executes commands. This was a real miss on 2026-04-03 — the agent was stalled until a human flagged it. It was also missed on 2026-04-04 for the same multi-window reason.

### Known False Positives — Add to FP dict

When using the PIL scan, these coordinates are recurring **false positives** (blue pixels from UI elements, not real Allow dialogs). Add them to a `FP` set and skip with `SKIP_FP:` prefix:

```python
FP = {
    # Manager window: TypeScript syntax highlighting in editor panel
    '1702,-514', '1543,-479', '1447,-493',
    # Editor window (174,139): VS Code Python interpreter notification (bottom right)
    '1000,672', '640,626', '726,628',
    # Editor window: persistent bottom notification bar
    '454,715',
    # Editor window: terminal "Relocate" button
    '928,595',
    # Fullscreen editor window (0,37,1728,1080): VS Code diff/edit indicators in left gutter
    # x < 100 range = always gutter FPs in fullscreen mode
    '83,623', '83,586', '91,585',
    # win313 (x=-28,y=-998): light blue [136,201,245] code highlights — G=201 is muted/sky blue, not button blue
    '556,-742', '560,-764',
    # win319 (x=186,y=-990): blue content in $USER—list workspace — persists after click
    '547,-682', '579,-767',
    # win334 stack (x=264+,y=159+): blue UI element at 713,781 — persists; real Allow cleared at win334
    '713,781',
}
```

**Gutter FP rule**: any coord with screen x < 100 in the fullscreen window (0,37,1728,1080) is a VS Code diff/edit gutter indicator — always skip. Real Allow dialogs appear in the center-right of the window (x > 300).

**Editor window left-edge rule (2026-04-05)**: in any editor window, `cx//2 < 30` (logical x < 30) is always a VS Code diff/edit gutter indicator — add `cx//2 > 30` to the PIL scan filter. This catches the recurring x≈2 FP in win 902.

**Detection rule**: if click does NOT dismiss the dialog (same coord detected again after click), add to FP. Real Allow dialogs disappear after click.

**Editor window bounds drift**: When the Agent Manager window closes (agent switches to editor-only mode), PIL scan bounds must switch from Manager bounds to editor window bounds. Re-fetch with `peekaboo window list` each cycle — do NOT hardcode Manager bounds.

---

## Conversation Activity Detection — Busy vs Idle

Two reliable indicators that a conversation is currently generating:

### 1. A11y label: `progress_activity` prefix (sidebar)
```bash
SNAPSHOT=$(peekaboo see --app Antigravity --window-id $MANAGER_ID 2>/dev/null)
# Busy conversations have "progress_activity" prefix in their label
ACTIVE=$(echo "$SNAPSHOT" | grep -c 'progress_activity.*button' || echo 0)
```

### 2. Red stop square in the input area (currently-viewed conversation only)
When a conversation is actively generating, a **red stop square** appears in the bottom-right of the input box (next to the microphone icon). Detect with PIL:

```python
def is_busy_red_square(img_path, win_x, win_y):
    """Returns True if red stop button is visible in input area."""
    from PIL import Image
    import numpy as np
    img = Image.open(img_path)
    arr = np.array(img)
    h, w = arr.shape[:2]
    # Input area = bottom 15% of window
    bottom = arr[int(h*0.85):, :]
    # Red square: R>160, G<100, B<100
    red_mask = (bottom[:,:,0] > 160) & (bottom[:,:,1] < 100) & (bottom[:,:,2] < 100)
    # IMPORTANT: filter to right 80% of image to avoid left-side gutter FPs
    right_mask = np.zeros_like(red_mask)
    right_mask[:, int(w*0.8):] = red_mask[:, int(w*0.8):]
    return np.sum(right_mask) > 30  # threshold: enough red pixels for a square button
```

The red square appears at approximately screen `(win_x + w*0.54, win_y + h*0.93)` in the Manager window (right side of input box).

**Known red-stop location (2026-04-05)**: in win 902 (x=-28, y=-998, w=1189, h=857), the red stop is at retina pixels x≈2312-2331, y≈1608-1627 (logical x≈1156, y≈804). Always filter x > 80% of image width to exclude gutter noise.

**Use A11y method first** (no screenshot needed). Use PIL red-square only to verify the currently-displayed conversation's state when A11y is ambiguous.

### 3. Conversation Health Classification (MANDATORY — use this, not spinner alone)

**The sidebar spinner icon (◌) is UNRELIABLE.** It persists after conversations die. Always cross-check with TWO additional signals:
- **Red stop square** (■) in bottom-right of chat input area — PIL detection
- **Status bar indicator** — bottom of window shows model name + button type

**Four conversation states:**

| State | Sidebar | Red ■ | Status bar | Timestamp | Action |
|-------|---------|-------|------------|-----------|--------|
| **Actually working** | spinner ◌ | YES | "Claude Opus 4.6 (Thinking)" + red ■ | < 30m | Leave alone |
| **Frozen-active** | spinner ◌ | YES | "...Thinking" + red ■ | > 1h | Interrupt: send "why did you freeze? Use a fresh terminal" |
| **Zombie spinner** | spinner ◌ | NO | "Gemini 3.1 Pro (High)" + send → | any | Dead conversation. Send "Continue with the next task" |
| **Cleanly idle** | no spinner | NO | model name + send → | any | Send new task if slot needed |

**Detection procedure (for each conversation):**
1. Click conversation in sidebar to select it
2. Screenshot the bottom 15% of the Manager window
3. Check for red stop square with `is_busy_red_square()`
4. Check status bar text: look for "Thinking" + red ■ vs model name + send arrow →
5. Read sidebar timestamp (Xm, Xh, Xd)
6. Classify using table above

**Status bar PIL detection — send arrow (→) vs red stop (■):**
```python
def classify_status_bar(img_path):
    """Returns 'generating' or 'idle' based on bottom status bar."""
    from PIL import Image
    import numpy as np
    img = Image.open(img_path)
    arr = np.array(img)
    h, w = arr.shape[:2]
    # Status bar = bottom 5% of window, right 30%
    bar = arr[int(h*0.95):, int(w*0.7):]
    # Red stop: R>160, G<100, B<100
    red = (bar[:,:,0] > 160) & (bar[:,:,1] < 100) & (bar[:,:,2] < 100)
    if np.sum(red) > 20:
        return 'generating'
    return 'idle'
```

**CRITICAL**: A conversation showing "Gemini 3.1 Pro (High)" with a send arrow (→) in the status bar is **IDLE** regardless of what the sidebar spinner shows. The spinner is a stale UI artifact.

---

## 24h Conversation Scanner — Keep 3 Active AT ALL TIMES

**HARD RULE: Always maintain exactly 3 conversations generating in parallel. This is not optional.**

At every cycle end, check the active count. If < 3:
1. Enumerate 24h conversations in reverse-cron order (most recent first)
2. Skip any with `progress_activity` spinner (already counting toward 3)
3. For each idle conversation until `active_count == 3`:
   - Click it
   - Verify busy with red stop square (A11y spinner lags by 5-10s)
   - If idle, send a continuation prompt
4. Report at cycle end: "Active: N/3 — [titles of active convos]"

**Detecting active vs idle (use health classification above, NOT spinner alone):**
- **DO NOT trust sidebar spinner (◌) alone** — it persists on dead conversations
- For each conversation, click it to select, then check:
  1. Red stop square in bottom-right of input area (PIL `is_busy_red_square()`)
  2. Status bar: "...Thinking" + red ■ = generating; model name + send → = idle
  3. Sidebar timestamp: if > 1h with red square = frozen-active (stuck in loop)
- Classify as: actually-working / frozen-active / zombie-spinner / cleanly-idle (see §3 above)
- **Zombie spinners** (spinner + no red square) are the most common failure — treat as idle, send "Continue"
- **Frozen-active** (spinner + red square + >1h) — interrupt with "why did you freeze? Use a fresh terminal"

**Sidebar click reliability (2026-04-05):**
- Clicking a conversation's `elem_N` in the Manager may NOT switch the view if another conversation is actively generating — the generating convo stays displayed
- Fallback: use coordinate click at the sidebar item's approximate y position; items are ~25px apart in logical coords
- If elem click and coord click both fail to switch, wait for the active convo to finish (or send it a message) then retry

**Reliable input field coordinates (2026-04-05):**
- Manager (x=429, y=-1005, w=1437, h=849): input at screen `(860, -230)` — reliable across sessions if Manager not resized
- Editor Agent panel win 902 (x=-28, y=-998, w=1189, h=857): input at screen `(959, -608)`
- Always cmd+a → delete to clear before pasting to avoid accumulated text

**Opening a workspace folder closes the Manager (2026-04-05):**
- Clicking a workspace item in the startup picker or using `agy chat --new-window` can open a new editor window and close the floating Manager window
- After opening a workspace, use "Switch to Agent Manager" (visible in left panel) or "Open Agent Manager" button in the title bar to restore the Manager
- Re-enumerate windows after any workspace open: `peekaboo window list --app Antigravity --json`

Scan conversations active in the last 24 hours, continue idle ones, keep 3 running at once.

```bash
scan_and_continue_convos() {
  local MANAGER_ID="$1"
  local MAX_ACTIVE="${2:-3}"
  
  # Step 1: Get conversation list
  local SNAP
  SNAP=$(peekaboo see --app Antigravity --window-id "$MANAGER_ID" 2>/dev/null)
  
  # Step 2: Parse 24h conversations (timestamps: now, Xm, Xh where X<24)
  # Exclude nav buttons, workspaces, settings
  local CONVOS
  CONVOS=$(echo "$SNAP" | grep -E '\(button\)' | grep -E '(now$|[0-9]+m$|[1-9]h$|1[0-9]h$|2[0-3]h$)' \
    | grep -v 'arrow_back\|arrow_forward\|New Conversation\|Conversation History\|Open Workspace\|See all\|settings\|Knowledge\|Feedback')
  
  # Step 3: Count active
  local ACTIVE_COUNT
  ACTIVE_COUNT=$(echo "$CONVOS" | grep -c 'progress_activity' 2>/dev/null || echo 0)
  local AVAILABLE=$(( MAX_ACTIVE - ACTIVE_COUNT ))
  
  echo "Convos in 24h: $(echo "$CONVOS" | wc -l | tr -d ' '), Active: $ACTIVE_COUNT, Slots: $AVAILABLE"
  
  if [ "$AVAILABLE" -le 0 ]; then
    echo "All $MAX_ACTIVE slots busy — skipping"
    return
  fi
  
  # Step 4: Reverse-cron idle convos (most recent first = already sorted)
  local IDLE_CONVOS
  IDLE_CONVOS=$(echo "$CONVOS" | grep -v 'progress_activity')
  
  # Step 5: Visit each idle convo and check if needs work
  local STARTED=0
  while IFS= read -r line && [ "$STARTED" -lt "$AVAILABLE" ]; do
    local ELEM
    ELEM=$(echo "$line" | grep -oE 'elem_[0-9]+')
    local TITLE
    TITLE=$(echo "$line" | sed 's/.*- //' | sed 's/ [0-9]*[mh]*$//' | sed 's/ now$//')
    
    echo "Visiting idle: $TITLE ($ELEM)"
    peekaboo click --app Antigravity --window-id "$MANAGER_ID" --element "$ELEM" 2>/dev/null
    sleep 2
    
    # Check if red stop square visible (conversation still generating)
    screencapture -x -R${WIN_X},${WIN_Y},${WIN_W},${WIN_H} /tmp/antig_convo_check.png
    if python3 -c "
from PIL import Image; import numpy as np
img=Image.open('/tmp/antig_convo_check.png')
arr=np.array(img); h,w=arr.shape[:2]
b=arr[int(h*0.85):,:]
rm=(b[:,:,0]>160)&(b[:,:,1]<100)&(b[:,:,2]<100)
print('busy' if np.sum(rm)>30 else 'idle')
" 2>/dev/null | grep -q 'busy'; then
      echo "  → Still generating (red square visible), skipping"
      continue
    fi
    
    # Read last message to determine if needs continuation
    local LAST_MSG
    LAST_MSG=$(peekaboo see --app Antigravity --window-id "$MANAGER_ID" 2>/dev/null \
      | grep -E 'staticText|text' | tail -5)
    
    # Send continuation if last message looks like it needs work
    # (Customize the continuation prompt per your use case)
    echo "  → Idle, sending continuation prompt"
    osascript -e 'tell application "System Events" to tell process "Antigravity" to keystroke "a" using {command down}' 2>/dev/null
    sleep 0.2
    osascript -e 'tell application "System Events" to tell process "Antigravity" to key code 51' 2>/dev/null
    sleep 0.2
    peekaboo paste --app Antigravity --text "Continue with the next task. What needs to be done?" 2>/dev/null
    sleep 0.3
    osascript -e 'tell application "System Events" to tell process "Antigravity" to key code 36' 2>/dev/null
    STARTED=$((STARTED+1))
    sleep 3  # give it a moment to start
  done <<< "$IDLE_CONVOS"
  
  echo "Started $STARTED new conversations (total active: $((ACTIVE_COUNT+STARTED)))"
}

# Usage:
MANAGER_ID=$(peekaboo window list --app Antigravity --json 2>/dev/null \
  | python3 -c "import json,sys; ws=json.load(sys.stdin).get('data',{}).get('windows',[]); m=[w for w in ws if w.get('window_title')=='Manager']; print(m[0]['window_id'] if m else '')")
WIN_X=429; WIN_Y=-1005; WIN_W=1437; WIN_H=849  # update dynamically each cycle
scan_and_continue_convos "$MANAGER_ID" 3
```

---

## Native CDP Execution (Preferred Approach)

The Antigravity runtime plugin now uses a direct Chrome DevTools Protocol (CDP) WebSocket connection as the primary driver, falling back to Peekaboo A11y only if CDP is unavailable.

**Why CDP?**
- Bypasses fragile A11y tree limits and unreliable web-rendered UI coordinate clicks.
- Connects directly to the electron renderer via `ws://localhost:9222`.
- Reliable UI manipulation and state reading using injected JS evaluating directly in the Antigravity context.

**How it works under the hood (`cdp-client.ts`):**
- Connects to the active page target via `http://localhost:9222/json`.
- **Finding Elements:** Uses DOM queries to find precise elements, ignoring accessibility tree limits.
- **Sending Messages:** Directly sets input values and fires `input` events, avoiding OS-level `paste` quirks.
- **Extracting Text:** Reads conversation threads precisely via DOM `.innerText`, much more reliable than snapshot OCR or A11y string joins.

---

## Architecture overview

| View | Purpose | Window title |
|------|---------|-------------|
| **Agent Manager** | Orchestrate AI agents, manage workspaces, monitor conversations | `Manager` |
| **Editor** | VS Code-like coding with AI side panel | `Antigravity` or `worktree_*` |
| **Launchpad** | Background/launcher window | `Launchpad` |
| **hidden-nova** | Internal background window | `hidden-nova` |

Toggle between views: **Cmd+E** or **Cmd+Shift+M**

---

## Window target: Agent Manager vs Editor (explicit control)

Antigravity exposes **two automation surfaces**. Pick one before driving UI:

| Target | `peekaboo` window title(s) | Best for |
|--------|------------------------------|----------|
| **Agent Manager** | `Manager` | New conversations, Chat History, multi-workspace list, Settings from sidebar, model/planning in new-convo view (A11y-rich) |
| **Editor** | `worktree_*`, `project_*`, or often `Antigravity` | Coding with Cmd+L side panel, Cmd+I inline AI, terminal ↔ agent, current workspace only |

**Environment variable (recommended):**

| `ANTIGRAVITY_WINDOW` | Behavior |
|----------------------|----------|
| `manager` | Use **only** the Manager window. If missing, try to surface it (see below) or fail with a clear message — do **not** silently use Editor. |
| `editor` | Use **only** an Editor window. Prefer `worktree_*` / `project_*`, then first window whose title is not `Manager`, `Launchpad`, or `hidden-nova`. |
| `auto` or unset | **Default:** prefer Manager; if not found, set `USE_EDITOR=1` and use Editor (same as legacy Step 0). |

Optional: `ANTIGRAVITY_EDITOR_TITLE` — substring or exact title to pick a **specific** editor window when multiple exist (e.g. `worktree_myrepo`).

**Single resolver — run once per task; exports `ANTIGRAVITY_TARGET`, `ANTIGRAVITY_WINDOW_ID`, `USE_EDITOR`:**

```bash
# Usage: ANTIGRAVITY_WINDOW=manager|editor|auto [ANTIGRAVITY_EDITOR_TITLE=...] source antigravity_resolve_window.sh
# Or paste inline:
antigravity_resolve_window() {
  local mode="${ANTIGRAVITY_WINDOW:-auto}"
  local json
  json=$(peekaboo window list --app Antigravity --json 2>/dev/null) || true
  ANTIGRAVITY_TARGET=""
  ANTIGRAVITY_WINDOW_ID=""
  USE_EDITOR=0

  _pick_manager() {
    echo "$json" | python3 -c "import json,sys; ws=json.load(sys.stdin).get('data',{}).get('windows',[]); m=[w for w in ws if w.get('window_title')=='Manager']; print(m[0]['window_id'] if m else '')"
  }
  _pick_editor() {
    export ANTIGRAVITY_EDITOR_TITLE="${ANTIGRAVITY_EDITOR_TITLE:-}"
    echo "$json" | python3 -c "
import json, os, sys
hint = (os.environ.get('ANTIGRAVITY_EDITOR_TITLE') or '').strip()
ws = json.load(sys.stdin).get('data',{}).get('windows',[])
if hint:
    for w in ws:
        t = w.get('window_title') or ''
        if hint in t or t == hint:
            print(w['window_id']); raise SystemExit
skip = {'Manager','Launchpad','hidden-nova'}
for w in ws:
    t = w.get('window_title') or ''
    if t.startswith('worktree_') or t.startswith('project_'):
        print(w['window_id']); raise SystemExit
for w in ws:
    t = w.get('window_title') or ''
    if t not in skip:
        print(w['window_id']); raise SystemExit
"
  }

  case "$mode" in
    manager)
      ANTIGRAVITY_WINDOW_ID="$(_pick_manager)"
      if [ -n "$ANTIGRAVITY_WINDOW_ID" ]; then
        ANTIGRAVITY_TARGET=manager
      else
        osascript -e 'tell application "Antigravity" to activate' 2>/dev/null
        sleep 1
        peekaboo press --app Antigravity --keys "cmd shift m" 2>/dev/null
        sleep 2
        json=$(peekaboo window list --app Antigravity --json 2>/dev/null) || true
        ANTIGRAVITY_WINDOW_ID="$(_pick_manager)"
        [ -n "$ANTIGRAVITY_WINDOW_ID" ] && ANTIGRAVITY_TARGET=manager
      fi
      USE_EDITOR=0
      ;;
    editor)
      ANTIGRAVITY_WINDOW_ID="$(_pick_editor)"
      [ -n "$ANTIGRAVITY_WINDOW_ID" ] && ANTIGRAVITY_TARGET=editor && USE_EDITOR=1
      ;;
    auto|*)
      ANTIGRAVITY_WINDOW_ID="$(_pick_manager)"
      if [ -n "$ANTIGRAVITY_WINDOW_ID" ]; then
        ANTIGRAVITY_TARGET=manager
        USE_EDITOR=0
      else
        ANTIGRAVITY_WINDOW_ID="$(_pick_editor)"
        [ -n "$ANTIGRAVITY_WINDOW_ID" ] && ANTIGRAVITY_TARGET=editor && USE_EDITOR=1
      fi
      ;;
  esac
}
antigravity_resolve_window
# After call: use ANTIGRAVITY_WINDOW_ID with peekaboo --window-id
# MANAGER_ID="$ANTIGRAVITY_WINDOW_ID" when ANTIGRAVITY_TARGET=manager
# EDITOR_ID="$ANTIGRAVITY_WINDOW_ID" when ANTIGRAVITY_TARGET=editor
```

**Routing after resolve:**

- **`ANTIGRAVITY_TARGET=manager`** — follow all **Manager window** sections below (`peekaboo see` on Manager, sidebar, new conversation, etc.). Use `MANAGER_ID=$ANTIGRAVITY_WINDOW_ID`.
- **`ANTIGRAVITY_TARGET=editor`** — follow **Editor fallback — sending messages via Cmd+L** (and Editor UI map). Use `EDITOR_ID=$ANTIGRAVITY_WINDOW_ID`. Do not assume `textField` in Manager A11y; use Cmd+L + paste + Return.
- **Failure** — if `ANTIGRAVITY_WINDOW_ID` is empty, report: Antigravity not running, wrong `ANTIGRAVITY_EDITOR_TITLE`, or no Editor window; suggest `agy /path/to/workspace` or opening Manager with Cmd+Shift+M.

---

## Step 0 — Routing: Agent Manager (preferred) → Editor (fallback)

**Auto mode (`ANTIGRAVITY_WINDOW=auto` or unset):** Prefer the Agent Manager for orchestration (new conversations, monitoring, steering). Use the **Editor's Cmd+L panel** when:

- The Manager window is not found in `peekaboo window list`
- The Manager A11y tree is hanging/timing out after 3 retries
- The user explicitly requests editor-mode interaction

**Explicit modes:** Use the **Window target** resolver above instead of this block when `ANTIGRAVITY_WINDOW` is `manager` or `editor`.

```bash
# Step 0a: Try Agent Manager first (legacy auto — same as antigravity_resolve_window auto)
MANAGER_ID=$(peekaboo window list --app Antigravity --json 2>/dev/null \
  | python3 -c "import json,sys; ws=[w for w in json.load(sys.stdin)['data']['windows'] if w['window_title']=='Manager']; print(ws[0]['window_id'] if ws else '')" 2>/dev/null)

if [ -z "$MANAGER_ID" ]; then
  echo "Manager window not found — falling back to Editor path"
  USE_EDITOR=1
else
  echo "Manager found: window $MANAGER_ID"
  USE_EDITOR=0
fi

# Step 0b: Editor fallback — get any editor window
if [ "$USE_EDITOR" = "1" ]; then
  EDITOR_ID=$(peekaboo window list --app Antigravity --json 2>/dev/null \
    | python3 -c "
import json,sys
ws=json.load(sys.stdin)['data']['windows']
# Prefer worktree windows, then any non-Manager/Launchpad window
for w in ws:
    t=w['window_title']
    if t.startswith('worktree_') or t.startswith('project_'):
        print(w['window_id']); exit()
for w in ws:
    t=w['window_title']
    if t not in ('Manager','Launchpad','hidden-nova'):
        print(w['window_id']); exit()
")
  # In Editor mode: send message via Cmd+L panel
  # osascript -e 'tell application "Antigravity" to activate'
  # peekaboo press --app Antigravity "cmd+l"  # focus agent panel
  # peekaboo paste --app Antigravity --text "your prompt"
  # peekaboo press "Return" --app Antigravity
fi
```

---

## [antig] Commit Prefix and PR Claim Convention

**All commits made by Antigravity agents MUST use the `[antig]` prefix** — analogous to `[agento]` for AO workers and `[worldai_claw]` for wc workers.

```
[antig] feat(parties): add name field and owner_id schema
[antig] fix(doctor): tighten Discord guard
```

**PR claim**: Include the PR number and worktree path in every Antigravity prompt so the agent knows what it owns:

```
You are working in /path/to/worktree on branch feat/xxx (PR #NNN).
Use [antig] prefix for ALL commits.
Push to origin feat/xxx after each logical unit of work.
```

**Zero-touch tracking**: `[antig]`-prefixed merged PRs count toward the Antigravity zero-touch rate, separate from `[agento]` (AO workers). This lets the eloop measure Antigravity's contribution independently.

**Fallback prefix**: If Antigravity agent doesn't use `[antig]`, the commit author `OpenClaw <openclaw@openclaw.ai>` identifies it as an agent commit — but the prefix is required for zero-touch counting.

---

---

## Manager window — complete UI element map (preferred path)

Use this section when **`ANTIGRAVITY_TARGET=manager`** (or auto resolved to Manager). Set `MANAGER_ID="${ANTIGRAVITY_WINDOW_ID}"` from the resolver; all `--window-id` examples below assume that ID.

### Top bar

| Element label | Role | Description |
|---------------|------|-------------|
| `dock_to_right` / `dock_to_left` | text | Dock position toggle |
| `Agent Manager` | text | Title |
| `Open Editor` | text | Switch to Editor view |
| `settings` | text | Settings icon (top bar) |

### Sidebar navigation buttons

| Element label | Role | Description |
|---------------|------|-------------|
| `add Start new conversation` | button | Creates new conversation (global) |
| `history Chat History` | button | Opens chat history panel |
| `Open Workspace` | button | Opens workspace picker/folder browser |
| `import_contacts Knowledge` | button | Opens Knowledge panel |
| `chrome_product Browser` | button | Opens Browser integration panel |
| `settings Settings` | button | Opens Settings panel |
| `lightbulb Provide Feedback` | button | Opens Feedback panel |

### Conversation list (dynamic)

| Pattern | Meaning |
|---------|---------|
| `progress_activity <Title> now` | Active/running conversation (status: **Running**) |
| `<Title> <N>m` / `<N>h` / `<N>d` | Completed/idle conversation with time-ago (status: **Idle**) |
| `See all (N)` | Expand to show all conversations |
| `See less` | Collapse conversation list |

### Conversation status indicators

Conversations have three states visible in the Manager:

| Status | Visual indicator | Meaning |
|--------|-----------------|---------|
| **Running** | `progress_activity` spinner prefix + `now` | Agent is actively working |
| **Idle** | Time-ago suffix (`5m`, `1h`, `12h`) | Agent finished or waiting |
| **Blocked** | May show warning icon or stalled state | Agent needs human input |

### Sidebar icon prefixes (Material Icons as text)

| Prefix | Icon |
|--------|------|
| `add` | Plus (new conversation) |
| `history` | Clock (chat history) |
| `import_contacts` | Contacts (knowledge) |
| `chrome_product` | Browser |
| `settings` | Gear |
| `lightbulb` | Bulb (feedback) |
| `progress_activity` | Spinner (active task) |
| `more_horiz` | Three dots (context menu) |
| `keyboard_arrow_down` / `keyboard_arrow_right` | Expand/collapse workspace |

### Workspace section elements

| Element label | Role | Description |
|---------------|------|-------------|
| `worktree_<name>` | other/text | Workspace header label |
| `project_<name>` | other/text | Project workspace header |
| `Playground` | other/text | Playground section header (scratch/test conversations) |
| `more_horiz` | text | Workspace options menu |
| `add` | button | Workspace-specific "+" button for new conversations (only for Playground section — workspace `+` icons are web-rendered) |
| `info` | other | Info icon (appears in Playground section) |

### Conversation view controls (appear when conversation is open)

| Element label | Role | Description |
|---------------|------|-------------|
| text entry area (textField) | textField | Message input area |
| `Planning` / `Fast` | button/text | Planning mode toggle |
| `Claude Opus 4.6 (Thinking)` etc. | button/text | Model selector |
| `Record voice memo` | button | Voice input |
| `Send` | button | Send message |
| `code Open editor` | button | Open in editor |
| `Use Playground` | button | Switch to playground mode |
| `Review` | button | Review mode toggle (top-right of conversation) |
| `Walkthrough` | tab | Walkthrough artifact view |

---

## Editor window — complete UI element map

Use this section when **`ANTIGRAVITY_TARGET=editor`** (or auto fell back to Editor). Set `EDITOR_ID="${ANTIGRAVITY_WINDOW_ID}"`; drive the agent via **Cmd+L** (see Editor fallback section) rather than Manager sidebar A11y.

All editor windows (`Antigravity`, `worktree_*`) share the same VS Code structure.

### Sidebar tabs

| Tab label | Keyboard shortcut |
|-----------|------------------|
| Explorer | Shift+Cmd+E |
| Code Search | Shift+Cmd+F |
| Source Control | Ctrl+Shift+G |
| Run and Debug | Shift+Cmd+D |
| Remote Explorer | — |
| Extensions | Shift+Cmd+X |
| Containers | — |
| GitHub Actions | — |

### AI-specific controls

| Control | How to access |
|---------|--------------|
| Agent side panel | Cmd+L (toggle/focus) |
| Inline AI command | Cmd+I (in editor and terminal) |
| `@` context inclusion | Type `@` in agent panel → files, dirs, MCP servers |
| `/` workflow invocation | Type `/` in agent panel → saved workflows |
| Artifacts button | Bottom-right of editor |
| "Explain and Fix" | Hover over problems |
| "Send all to Agent" | Problems panel → batch error resolution |
| Terminal output → agent | Select terminal output, press Cmd+L to send to agent |
| Tab-to-import | Auto-suggests missing dependency imports |
| Tab-to-jump | Navigates cursor to next logical code location |

---

## Menu bar items (Antigravity focused)

### Antigravity menu
- About Antigravity
- Quit Antigravity

### File menu
- **Start Conversation** — new conversation (Cmd+N equivalent)
- **New Editor** — new editor window
- **Open Folder** — open a workspace folder

### Edit menu
- Standard: Undo, Redo, Cut, Copy, Paste, Select All
- Writing Tools submenu (macOS): Proofread, Rewrite, Make Friendly/Professional/Concise, Summarize, Create Key Points, Make List/Table, Compose
- AutoFill submenu: Contact, Passwords

### View menu
- Toggle Fullscreen

---

## Keyboard shortcuts

### Antigravity-specific

| Shortcut | Action |
|----------|--------|
| **Cmd+E** | Toggle Agent Manager ↔ Editor |
| **Cmd+Shift+M** | Toggle Agent Manager ↔ Editor (alt) |
| **Cmd+L** | Toggle/focus agent side panel |
| **Cmd+I** | Inline AI command (editor + terminal) |
| **Cmd+B** | Toggle sidebar |
| **Tab** | Accept AI code completion |
| **Esc** | Dismiss AI suggestion |

### VS Code inherited (selection)

| Shortcut | Action |
|----------|--------|
| Cmd+P | Quick Open (file search) |
| Cmd+Shift+P | Command Palette |
| Cmd+Shift+F | Search across project |
| Ctrl+` | Toggle integrated terminal |
| Cmd+D | Select next occurrence |
| Cmd+Shift+L | Select all occurrences |
| Opt+Up/Down | Move current line |
| Cmd+Shift+K | Delete current line |
| Cmd+/ | Toggle line comment |
| Cmd+\ | Split editor vertically |
| Cmd+1/2/3 | Focus split editor groups |
| Ctrl+G | Go to line number |
| Cmd+Click | Go to definition |
| Ctrl+- | Navigate back |

---

## Development modes

Antigravity supports these execution modes (configured during onboarding or in Settings):

| Mode | Description |
|------|-------------|
| **Agent-driven (Autopilot)** | AI writes code, creates files, runs commands automatically |
| **Review-driven** (Recommended) | AI asks permission before actions |
| **Agent-assisted** | User stays in control; AI helps with safe automations |
| **Secure Mode** | Enhanced security restrictions |
| **Custom Configuration** | User-defined policy per action type |

### Execution policies

| Policy | Options |
|--------|---------|
| Terminal execution | Always Proceed (with deny list) / Request Review (with allowlist) |
| Review policy (artifacts) | Always Proceed / Agent Decides (default) / Request Review |
| JavaScript execution (browser) | Always Proceed / Request Review / Disabled |

---

## Planning modes

| Mode | Description |
|------|-------------|
| **Planning** | Agent builds task lists and implementation plans before executing. Use for complex tasks. |
| **Fast** | Agent executes directly without planning. Use for simple tasks. |

Toggle via the dropdown in the conversation input area (shows as `Planning` or `Fast` button).

**A11y access**: In the **new conversation creation** view, Planning/Fast buttons appear as A11y `button` elements. In active conversations, they are web-rendered. When clicking "Start new conversation", a conversation mode picker popover appears with Planning/Fast options — this popover is entirely web-rendered (NOT in A11y tree).

---

## Model selection

### Priority order (best first)

| Priority | Model | Notes |
|----------|-------|-------|
| 1 | **Claude Opus 4.6 (Thinking)** | Best code quality |
| 2 | **Gemini 3.1 Pro (High)** | Strong general purpose |
| 3 | **Gemini 3.1 Pro (Low)** | Same model, lower priority tier |
| 4 | **Gemini 3 Flash** | Fast but lower quality |
| 5 | **Claude Sonnet 4.6 (Thinking)** | Good quality, use when Opus exhausted |
| 6 | **GPT-OSS 120B (Medium)** | Last resort |

### Checking quota before starting conversations

Before starting a new conversation, check model quota via Settings > Models:

```bash
MANAGER_ID=<MANAGER_ID>

# Step 1: Navigate to Settings
SNAP=$(peekaboo see --app Antigravity --window-id "$MANAGER_ID" --json 2>/dev/null \
  | python3 -c "import json,sys; print(json.load(sys.stdin)['data']['snapshot_id'])")
SETTINGS_ID=$(peekaboo see --app Antigravity --window-id "$MANAGER_ID" --json 2>/dev/null | python3 -c "
import json,sys; data=json.load(sys.stdin)
for e in data['data']['ui_elements']:
    if 'Settings' in (e.get('label','') or '') and e.get('role') == 'button':
        print(e['id']); break")
peekaboo click --app Antigravity --window-id "$MANAGER_ID" --on "$SETTINGS_ID" --snapshot "$SNAP"
sleep 1

# Step 2: Click Models tab
SNAP2=$(peekaboo see --app Antigravity --window-id "$MANAGER_ID" --json 2>/dev/null \
  | python3 -c "import json,sys; print(json.load(sys.stdin)['data']['snapshot_id'])")
MODELS_ID=$(peekaboo see --app Antigravity --window-id "$MANAGER_ID" --json 2>/dev/null | python3 -c "
import json,sys; data=json.load(sys.stdin)
for e in data['data']['ui_elements']:
    if e.get('label','') == 'Models' and e.get('role') == 'button':
        print(e['id']); break")
peekaboo click --app Antigravity --window-id "$MANAGER_ID" --on "$MODELS_ID" --snapshot "$SNAP2"
sleep 1

# Step 3: Screenshot the Models page to read quota bars
BOUNDS=$(peekaboo window list --app Antigravity --json 2>/dev/null | python3 -c "
import json, sys
for w in json.load(sys.stdin)['data']['windows']:
    if w['window_id'] == $MANAGER_ID:
        b = w['bounds']
        print(f\"{b['x']},{b['y']},{b['width']},{b['height']}\")")
screencapture -x -R${BOUNDS} /tmp/antig_models.png
# Read the screenshot to check which models have quota remaining
```

**Quota bar colors**: Gray filled = quota available. Yellow/orange filled = quota used. Empty gray segments = quota remaining.

### Model selector in new conversation view

**A11y access**: In the **new conversation creation** view, the model selector appears as an A11y `button` (e.g., `Select model, current: Claude Opus 4.6 (Thinking)`). Click it to open the model dropdown — the dropdown options ARE A11y accessible as buttons.

**PROVEN WORKING FLOW (2026-03-31)**:
1. Click "New Conversation" button (A11y: `add New Conversation`)
2. After view loads, find model selector: `elem_66` or search for `'Select model' in label`
3. Click it — dropdown opens immediately with all models as A11y buttons
4. Click desired model (e.g., `Gemini 3.1 Pro (High) New`)
5. Verify: re-snapshot and check `'Select model, current: Gemini 3.1 Pro (High)'`

```bash
MANAGER_ID=<MANAGER_ID>

# Step 1: Open new conversation
SNAP_JSON=$(timeout 12 peekaboo see --app Antigravity --window-id "$MANAGER_ID" --json 2>/dev/null)
SNAP=$(echo "$SNAP_JSON" | python3 -c "import json,sys; print(json.load(sys.stdin)['data']['snapshot_id'])")
NEW_ID=$(echo "$SNAP_JSON" | python3 -c "
import json,sys; data=json.load(sys.stdin)
for e in data['data']['ui_elements']:
    if 'New Conversation' in (e.get('label','') or '') and e.get('role') == 'button':
        print(e['id']); break")
peekaboo click --app Antigravity --window-id "$MANAGER_ID" --on "$NEW_ID" --snapshot "$SNAP"
sleep 2

# Step 2: Find and click model selector
SNAP_JSON2=$(timeout 12 peekaboo see --app Antigravity --window-id "$MANAGER_ID" --json 2>/dev/null)
SNAP2=$(echo "$SNAP_JSON2" | python3 -c "import json,sys; print(json.load(sys.stdin)['data']['snapshot_id'])")
MODEL_BTN=$(echo "$SNAP_JSON2" | python3 -c "
import json,sys; data=json.load(sys.stdin)
for e in data['data']['ui_elements']:
    if 'Select model' in (e.get('label','') or '') and e.get('role') == 'button':
        print(e['id']); break")
peekaboo click --app Antigravity --window-id "$MANAGER_ID" --on "$MODEL_BTN" --snapshot "$SNAP2"
sleep 1.5

# Step 3: Dropdown is now open — pick model from A11y buttons
SNAP_JSON3=$(timeout 12 peekaboo see --app Antigravity --window-id "$MANAGER_ID" --json 2>/dev/null)
SNAP3=$(echo "$SNAP_JSON3" | python3 -c "import json,sys; print(json.load(sys.stdin)['data']['snapshot_id'])")
# Available: "Gemini 3.1 Pro (High) New", "Gemini 3.1 Pro (Low) New", "Gemini 3 Flash",
#            "Claude Sonnet 4.6 (Thinking)", "Claude Opus 4.6 (Thinking)"
GEMINI_BTN=$(echo "$SNAP_JSON3" | python3 -c "
import json,sys; data=json.load(sys.stdin)
for e in data['data']['ui_elements']:
    if 'Gemini 3.1 Pro (High)' in (e.get('label','') or '') and e.get('role') == 'button':
        print(e['id']); break")
peekaboo click --app Antigravity --window-id "$MANAGER_ID" --on "$GEMINI_BTN" --snapshot "$SNAP3"
sleep 1

# Step 4: Verify
SNAP_JSON4=$(timeout 12 peekaboo see --app Antigravity --window-id "$MANAGER_ID" --json 2>/dev/null)
echo "$SNAP_JSON4" | python3 -c "
import json,sys; data=json.load(sys.stdin)
for e in data['data']['ui_elements']:
    if 'Select model' in (e.get('label','') or ''):
        print('Model now:', e['label'])"
```

### Quota exhaustion recovery

When a conversation stalls with capacity errors ("Error You have exhausted your capacity on this model"):
1. **Do NOT try to change model in the stalled conversation** — model selector is web-rendered in active/idle convos
2. Start a **new conversation** using the flow above, select next model in priority order
3. Include context from the stalled conversation in the new prompt

**In active/idle conversations, the model selector is web-rendered and cannot be changed via A11y.**

### "Too much traffic" rate limiting

When Antigravity shows "Too much traffic — please try again in a few minutes.":
1. **Retry with backoff** — wait 30s, retry the same conversation (click Retry button)
2. **After 10 retries** — if still failing, switch to a different model (start new conversation with next model in priority)
3. **Max 3 NEW windows** — if workspace window count > 3, close excess Editor windows (keep Manager + max 2 Editor). NOT 3 total.
4. **Do NOT just stop** — the work items still need completion, try again when traffic subsides
5. **Switch workspace context** — try starting conversation in a different workspace to route to different backend

**Priority order**: Claude Opus 4.6 → Gemini 3.1 Pro (High) → Gemini 3.1 Pro (Low) → Gemini 3 Flash → Claude Sonnet 4.6

### Conversation monitoring loop (for /eloop)

When monitoring active Antigravity conversations:
1. **Scan all conversations** — capture Manager screenshot, identify active (spinner) vs idle
2. **Check window count** — ensure workspace windows ≤ 3 NEW windows (Editor + Manager). Count via `peekaboo window list` excluding Launchpad and empty. If >3, close excess Editor windows (keep Manager + max 2 Editor) until ≤3.
3. **Check for errors** — look for "Too much traffic", "Error", "Failed" in conversation content
4. **Retry on error** — if error detected, click Retry or restart conversation with same task
5. **After 10 retries** — if same error persists, switch model (start new conversation with different model)
6. **Max 3 parallel** — ensure no more than 3 active conversations at once
7. **Report status** — document which conversations are running, which PRs they're working on
8. **PR-Target verification (MANDATORY before sending messages)**:
   - User specifies "work on PR #177" → must send message to PR #177 conversation
   - If agent is on wrong PR (e.g., stuck on #178 when asked for #177), explicitly close wrong conversation and open new one for target PR
   - Before typing message: verify conversation title matches target PR number
9. **Health check for stuck agents**:
   - If `progress_activity` persists > 30 minutes with no Git commits pushed → agent is hung
   - Force restart: `osascript -e 'tell application "Antigravity" to quit'` then `open -a Antigravity`
   - Do NOT keep polling stuck agents — restart and start fresh conversation

### Clearing the text input field

`peekaboo press` does NOT support modifier key combos like `cmd+a` or `Command+a` — those throw "Unknown key" errors. To clear the input field before pasting:
- Click the text field by element ID or coordinates
- If field has existing text: paste the new content directly (it will append) — **avoid** trying to select-all with keyboard shortcuts
- Alternatively: open a fresh "New Conversation" which starts with an empty field

---

## Artifacts system

Types: Task Lists, Implementation Plans, Code Diffs, Walkthroughs, Screenshots, Browser Recordings.

- **Agent Manager:** toggle artifacts button (top-right)
- **Editor:** click "Artifacts" button (bottom-right)
- Supports Google Docs-style comments — agents ingest feedback and iterate

### Walkthrough mode

Post-completion artifact with: summary, task list, file changes, screenshots, testing instructions. Appears as a tab in conversation view.

---

## Configuration and customization

### Rules (agent guidelines)

| Scope | Path |
|-------|------|
| Global | `~/.gemini/GEMINI.md` |
| Workspace | `<workspace>/.agents/rules/` |

### Workflows (saved prompts, invoked with `/`)

| Scope | Path |
|-------|------|
| Global | `~/.gemini/antigravity/global_workflows/<NAME>.md` |
| Workspace | `<workspace>/.agents/workflows/` |

### Skills

| Scope | Path |
|-------|------|
| Global | `~/.gemini/antigravity/skills/` |
| Workspace | `<workspace>/.agents/skills/` |

Skill structure: `SKILL.md` (required, YAML frontmatter), optional `scripts/`, `references/`, `assets/`.

### Customization access

Editor mode: `(...) > Customizations`

---

## "Allow this conversation" dialog — always click Allow

Antigravity shows "Allow directory access to /path?" prompts with **Deny / Allow Once / Allow This Conversation** buttons when agents try to access workspace files. **Always click "Allow This Conversation" without asking the user** — pre-authorized.

### CRITICAL: These buttons are web-rendered

The Allow/Deny buttons are **web-rendered inside the conversation panel** and do NOT appear in the Peekaboo accessibility tree. `peekaboo see` only returns native macOS accessibility elements. The Allow prompt appears **every new conversation** for **every workspace** — not just the first time.

### Solution: Coordinate-based clicking via annotated screenshot

### Method 0: Simplified blue-button detection (FASTEST — proven 2026-03-27)

```bash
# One-liner: find and click "Allow This Conversation" (rightmost blue button)
WIN_X=832; WIN_Y=-1013; WIN_W=1025; WIN_H=904  # Manager window bounds
screencapture -x -R${WIN_X},${WIN_Y},${WIN_W},${WIN_H} /tmp/antig_allow.png
COORDS=$(python3 -c "
from PIL import Image; import numpy as np
img = np.array(Image.open('/tmp/antig_allow.png'))
blue_mask = (img[:,:,2] > 150) & (img[:,:,0] < 120) & (img[:,:,2] > img[:,:,1] + 30)
ys, xs = np.where(blue_mask)
if len(xs) > 0:
    right_mask = xs > (xs.max() - 250)
    cx, cy = int(np.mean(xs[right_mask])), int(np.mean(ys[right_mask]))
    print(f'${WIN_X}+{cx//2},${WIN_Y}+{cy//2}')
" 2>/dev/null | python3 -c "import sys; parts=sys.stdin.read().strip().split(','); print(f'{eval(parts[0])},{eval(parts[1])}')")
[ -n "$COORDS" ] && peekaboo click --app Antigravity --window-id MANAGER_ID --coords "$COORDS"
```

### Method 1: Programmatic blue-button detection (PROVEN — use this)

Uses `screencapture` + PIL pixel analysis to find blue button coordinates automatically:

```bash
MANAGER_ID=<MANAGER_ID>

# Step 1: Get window bounds
BOUNDS=$(peekaboo window list --app Antigravity --json 2>/dev/null | python3 -c "
import json, sys
for w in json.load(sys.stdin)['data']['windows']:
    if w['window_id'] == $MANAGER_ID:
        b = w['bounds']
        print(f\"{b['x']},{b['y']},{b['width']},{b['height']}\")
")
WIN_X=$(echo "$BOUNDS" | cut -d, -f1)
WIN_Y=$(echo "$BOUNDS" | cut -d, -f2)
WIN_W=$(echo "$BOUNDS" | cut -d, -f3)
WIN_H=$(echo "$BOUNDS" | cut -d, -f4)

# Step 2: Capture window region (retina = 2x pixels)
screencapture -x -R${WIN_X},${WIN_Y},${WIN_W},${WIN_H} /tmp/allow_check.png

# Step 3: Find blue button coordinates programmatically
python3 -c "
from PIL import Image
import numpy as np

img = Image.open('/tmp/allow_check.png')
arr = np.array(img)
h, w = arr.shape[:2]

# Find blue button pixels (bottom half of image)
for row_start in range(h//2, h, 30):
    region = arr[row_start:row_start+30, :]
    blue_mask = (region[:,:,2] > 150) & (region[:,:,0] < 150) & (region[:,:,2] > region[:,:,0] + 50)
    if np.sum(blue_mask) > 100:
        coords = np.where(blue_mask)
        xs = coords[1]
        xs_sorted = np.sort(np.unique(xs))
        # Find gap between buttons
        gaps = np.diff(xs_sorted)
        big_gaps = np.where(gaps > 15)[0]
        if len(big_gaps) > 0:
            # Rightmost button = 'Allow This Conversation'
            right_start = xs_sorted[big_gaps[-1] + 1]
            right_end = xs_sorted[-1]
        else:
            # Single button region — rightmost 40%
            right_start = xs_sorted[int(len(xs_sorted) * 0.6)]
            right_end = xs_sorted[-1]
        cx = int((right_start + right_end) / 2)
        cy = int(np.mean(coords[0][xs >= right_start])) + row_start
        # Convert 2x retina pixels to points
        print(f'{$WIN_X + cx//2},{$WIN_Y + cy//2}')
        break
"

# Step 4: Click at computed screen coordinates
CLICK_COORDS=$(python3 ...)  # capture output from step 3
peekaboo click --app Antigravity --window-id "$MANAGER_ID" --coords "$CLICK_COORDS"

# Step 5: Verify — re-capture and check blue pixels are gone
sleep 1
screencapture -x -R${WIN_X},${WIN_Y},${WIN_W},${WIN_H} /tmp/allow_verify.png
```

### Method 2: Visual inspection (fallback)

```bash
# Take annotated screenshot, visually identify button position
peekaboo see --app Antigravity --window-id "$MANAGER_ID" --annotate
# Read the annotated screenshot to identify coordinates
# Click by coordinates
peekaboo click --app Antigravity --window-id "$MANAGER_ID" --coords <x>,<y>
```

### Key facts about coordinate clicking

- `peekaboo click --coords` uses **screen-absolute** coordinates (not window-relative)
- macOS Retina displays use **point coordinates** (not pixel coordinates) — divide retina pixels by 2
- `screencapture -x -R` uses point coordinates for the region but captures at 2x pixel resolution
- External displays may have negative y coordinates (e.g., y=-1013 for a monitor above the primary)
- Window bounds from `peekaboo window list` are in point coordinates

### Alternative: Antigravity Settings

Configure execution policy to avoid Allow prompts entirely:
1. Open Settings (sidebar gear icon)
2. Set terminal execution to "Always Proceed" for known workspaces
3. **IMPORTANT**: "Always Proceed" does NOT eliminate per-conversation Allow prompts — those are separate (workspace directory access vs terminal command approval)
4. "Always Proceed" only applies to **new messages**. In-progress conversations keep the policy that was active when they started. If an agent is stuck on "Waiting for command completion", start a NEW conversation rather than trying to approve the stuck one.

### Terminal approval stuck state — start new conversation

If you see "The commit command is waiting for user approval" or "Waiting for command completion (up to 300 seconds)", the conversation started under "Request Review" mode. The "Always run ^" dropdown buttons are web-rendered and coordinate clicks rarely work reliably on them. Recovery:
1. Do NOT try to click "Always run" — it's unreliable
2. Verify Settings > Terminal > "Always Proceed" is set
3. Start a **new conversation** — it will use the updated policy
4. Include results from the stuck conversation's work (skip completed items)

### Agent crash recovery — start fresh

When "Agent terminated due to error" appears with Dismiss/Copy debug info/Retry buttons:
1. These buttons are web-rendered — Dismiss clicks often land on wrong elements (Knowledge panel, etc.)
2. Do NOT try Retry — it may restart with stale context (e.g., trying to fix already-merged PRs)
3. Instead: start a **new conversation** with updated task description
4. Check what the crashed agent accomplished: `git log`, `git branch -r`, `gh pr list`
5. Skip completed work in the new task prompt
6. Two conversations CAN run simultaneously — the crashed one becomes IDLE and won't block

### Detection pattern

After starting any conversation, check for Allow prompts:
1. Capture the Manager window with `screencapture -x -R<bounds>`
2. Use PIL to search for blue button pixels in the bottom half
3. If blue buttons found → run the programmatic click flow above
4. Re-capture to confirm the prompt dismissed

### Web-rendered content interaction — general technique

Antigravity uses web-rendered UI elements that don't appear in the A11y tree. For ANY web-rendered button/control:

1. **Capture**: `screencapture -x -R<window_bounds> /tmp/element.png`
2. **Analyze**: Use PIL/numpy to find the element by color, shape, or position
3. **Convert**: Divide retina pixels by 2, add window origin for screen coordinates
4. **Click**: `peekaboo click --app Antigravity --window-id <ID> --coords <screen_x>,<screen_y>`
5. **Verify**: Re-capture and confirm the element is gone/changed

This technique works for: Allow prompts, Review buttons, walkthrough controls, artifact interactions, and any other web-rendered UI that peekaboo `see` cannot expose.

**Note**: `peekaboo screenshot` does NOT exist — use `screencapture` (macOS built-in) instead.

---

## Starting a new conversation in a workspace

### Method 0: `agy` CLI (FASTEST — use for new workspaces)

The `agy` CLI (`~/.antigravity/antigravity/bin/agy`) opens a workspace directly and registers it with the Manager. **This is the best method for workspaces not yet visible in the Manager sidebar.**

```bash
# Open workspace — creates editor window AND registers in Manager
agy /path/to/workspace

# Verify window appeared
peekaboo window list --app Antigravity --json 2>/dev/null | python3 -c "
import json, sys
for w in json.load(sys.stdin)['data']['windows']:
    print(f'{w[\"window_id\"]:6}  {w[\"window_title\"]}')"
```

After `agy`, the workspace appears in `peekaboo window list` but may require **scrolling down** in the Manager sidebar to become visible as an `other` element. The Manager sidebar only shows a viewport — new workspaces appear at the bottom.

### Method 1: "Start new conversation" button (RECOMMENDED — tested and proven)

The global "add Start new conversation" button in the sidebar opens a new conversation creation view with full A11y support. **This is the most reliable method.**

**How to find it**: Scroll to the top of the sidebar — the button may be hidden below the fold. Use `peekaboo scroll --direction up --amount 10` then check for `add Start new conversation` in the A11y tree.

```bash
MANAGER_ID=<MANAGER_ID>

# Step 1: Scroll sidebar to top to reveal the button
peekaboo scroll --direction up --amount 10 --app Antigravity --window-id "$MANAGER_ID"

# Step 2: Find the "add Start new conversation" button
SNAP=$(peekaboo see --app Antigravity --window-id "$MANAGER_ID" --json 2>/dev/null \
  | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['data']['snapshot_id'])")
peekaboo see --app Antigravity --window-id "$MANAGER_ID" --json 2>/dev/null | python3 -c "
import json,sys; data=json.load(sys.stdin)
for e in data['data']['ui_elements']:
    if 'Start new conversation' in (e.get('label','') or ''):
        print(e['id'])"

# Step 3: Click it — opens new conversation creation view
peekaboo click --app Antigravity --window-id "$MANAGER_ID" --on <ADD_BUTTON_ID> --snapshot "$SNAP"
```

**The new conversation view exposes these A11y elements:**

| Element label | Role | Description |
|---------------|------|-------------|
| `keyboard_arrow_down <workspace>` | button | Workspace selector dropdown |
| `text entry area` | textField | Message input |
| `Send` | button | Send button (visible here, unlike in active conversations) |
| `Planning` / `Fast` | button | Planning mode toggle |
| `Claude Opus 4.6 (Thinking)` etc. | button | Model selector |
| `Record voice memo` | button | Voice input |
| `code Open editor` | button | Switch to editor |
| `Use Playground` | button | Switch to playground mode |
| `New conversation in` | other | Label text |

**Important**: The workspace selector dropdown (`keyboard_arrow_down`) is accessible in A11y but **clicking it does NOT reliably open the web-rendered dropdown menu**. The dropdown is web-rendered. Workaround: include the explicit workspace path in your prompt.

```bash
# Step 4: Click text field, paste prompt (include workspace path!)
SNAP2=$(peekaboo see --app Antigravity --window-id "$MANAGER_ID" --json 2>/dev/null \
  | python3 -c "import json,sys; print(json.load(sys.stdin)['data']['snapshot_id'])")

# Find text field and Send button
peekaboo see --app Antigravity --window-id "$MANAGER_ID" --json 2>/dev/null | python3 -c "
import json,sys; data=json.load(sys.stdin)
for e in data['data']['ui_elements']:
    label = e.get('label','') or ''
    role = e.get('role','')
    if label in ('text entry area','Send') or role == 'textField':
        print(e['id'], role, label)"

# Click text field, paste prompt with workspace context
peekaboo click --app Antigravity --window-id "$MANAGER_ID" --on <TEXT_FIELD_ID> --snapshot "$SNAP2"
peekaboo paste --app Antigravity --text "You are working in /path/to/worktree on branch X. <your task>"

# Step 5: Send — BOTH Return and Send button work
peekaboo press "Return" --app Antigravity
# OR: peekaboo click --on <SEND_BUTTON_ID> --snapshot "$SNAP2"

# Step 6: Verify conversation started
sleep 3
peekaboo see --app Antigravity --window-id "$MANAGER_ID" --json 2>/dev/null | python3 -c "
import json,sys; data=json.load(sys.stdin)
for e in data['data']['ui_elements']:
    label = e.get('label','') or ''
    if 'progress_activity' in label:
        print('ACTIVE:', label[:100])"
```

### Method 2: Click workspace label in Manager sidebar

Clicking a workspace `other` element or "No chats yet" text expands the workspace section. After expanding, a `+` icon appears next to the workspace name (web-rendered, requires coordinate clicking).

**Limitations**: Only the **currently focused workspace** label appears as an `other` element in the A11y tree. Other workspace labels are web-rendered and not directly clickable via A11y.

### Method 3: Click existing conversation to switch

Click any conversation button in the sidebar to switch to it. The conversation buttons ARE in the A11y tree (role=button, label includes title + time-ago).

### ⚠️ Known issues

- **"Open Workspace" dropdown scoping**: The `Open Workspace` sidebar button does NOT reliably scope to the selected workspace.
- **Workspace dropdown in new conversation view**: The `keyboard_arrow_down` button doesn't open its web-rendered dropdown via A11y click. Include workspace path in prompt as workaround.
- **Workspace-specific `+` icon**: Web-rendered, requires coordinate clicking which is unreliable due to dynamic sidebar layout.

### Full flow (Method 0 + Method 1 combined — most reliable)

```bash
MANAGER_ID=<MANAGER_ID>

# Step 1: If workspace not in Manager sidebar, open via CLI first
agy /path/to/workspace
sleep 2

# Step 2: Scroll sidebar to top and click "Start new conversation"
peekaboo scroll --direction up --amount 10 --app Antigravity --window-id "$MANAGER_ID"
SNAP=$(peekaboo see --app Antigravity --window-id "$MANAGER_ID" --json 2>/dev/null \
  | python3 -c "import json,sys; print(json.load(sys.stdin)['data']['snapshot_id'])")
# Find and click the button
ADD_ID=$(peekaboo see --app Antigravity --window-id "$MANAGER_ID" --json 2>/dev/null | python3 -c "
import json,sys; data=json.load(sys.stdin)
for e in data['data']['ui_elements']:
    if 'Start new conversation' in (e.get('label','') or ''):
        print(e['id']); break")
peekaboo click --app Antigravity --window-id "$MANAGER_ID" --on "$ADD_ID" --snapshot "$SNAP"
sleep 1

# Step 3: Click text field, paste prompt with workspace path
SNAP2=$(peekaboo see --app Antigravity --window-id "$MANAGER_ID" --json 2>/dev/null \
  | python3 -c "import json,sys; print(json.load(sys.stdin)['data']['snapshot_id'])")
TF_ID=$(peekaboo see --app Antigravity --window-id "$MANAGER_ID" --json 2>/dev/null | python3 -c "
import json,sys; data=json.load(sys.stdin)
for e in data['data']['ui_elements']:
    if e.get('role','') == 'textField' and 'text entry' in (e.get('label','') or ''):
        print(e['id']); break")
peekaboo click --app Antigravity --window-id "$MANAGER_ID" --on "$TF_ID" --snapshot "$SNAP2"
peekaboo paste --app Antigravity --text "You are working in /path/to/worktree on branch X. <task>"
peekaboo press "Return" --app Antigravity
```

### Important notes

- **Use `peekaboo paste` not `peekaboo type`** — paste avoids character drift in Antigravity's input field.
- **Both Return and Send button work** for sending messages. In active conversations, the Send button may NOT be in the A11y tree. In the new conversation view, it IS accessible.
- **Always include the explicit workspace path in your prompt** as a safety net for workspace scoping: "You are working in /path/to/worktree on branch X"
- **New workspaces need scrolling** — after `agy <path>`, the Manager sidebar may not show the workspace without scrolling down.
- **Conversations auto-rename** — after the first message, Antigravity renames the conversation based on content.

### Workspace scoping workaround — CRITICAL

The "New conversation in > [workspace]" dropdown is **web-rendered and cannot be switched via A11y or coordinate clicking reliably**. After 3 failed attempts to switch it, use this workaround:

**Don't fight the dropdown. Include the workspace path in your prompt text instead:**

```bash
# The dropdown says "agent-orchestrator" but you want worldai_claw? Don't try to switch it.
# Just include the workspace path explicitly in the prompt:
peekaboo paste --app Antigravity --text "You are working in $HOME/project_worldaiclaw/worldai_claw on branch main. <your task here>"
```

This works because Antigravity agents resolve the workspace from the path in the prompt, regardless of which workspace the dropdown shows. The dropdown only sets the default context — explicit paths override it.

### UI interaction retry cap

**After 3 failed attempts at the same UI interaction (coordinate clicks, element clicks, keyboard shortcuts), STOP.** Do not continue guessing. Instead:
1. Disclose to user: "I tried X 3 times and it's not working because Y"
2. Use a documented workaround (e.g., workspace path in prompt text)
3. If no workaround exists, ask user for help

This prevents the failure mode where the agent spends 15+ tool calls trying coordinate variations on web-rendered elements that are invisible to A11y.

### Manager window startup

The Manager window may not appear immediately after keyboard shortcuts. Reliable procedure:

1. `osascript -e 'tell application "Antigravity" to activate'` — ensure Antigravity is focused
2. `peekaboo press --app Antigravity --keys "cmd shift m"` — toggle Manager
3. `sleep 3` — Manager takes 2-3 seconds to initialize
4. Check `peekaboo window list` for a window titled "Manager"
5. If not found after ONE retry (total wait 6s), disclose to user: "Manager window isn't opening"

Do NOT loop Cmd+Shift+M or Cmd+E repeatedly — it toggles the window on/off.

---

## Sending messages to active conversations

To send a follow-up message to a conversation already open in the Manager:

```bash
MANAGER_ID=<MANAGER_ID>

# Step 1: Switch to the target conversation (click its sidebar button)
SNAP=$(peekaboo see --app Antigravity --window-id "$MANAGER_ID" --json 2>/dev/null \
  | python3 -c "import json,sys; print(json.load(sys.stdin)['data']['snapshot_id'])")
# Find conversation by title substring
CONVO_ID=$(peekaboo see --app Antigravity --window-id "$MANAGER_ID" --json 2>/dev/null | python3 -c "
import json,sys; data=json.load(sys.stdin)
for e in data['data']['ui_elements']:
    if e.get('role','') == 'button' and 'your search term' in (e.get('label','') or '').lower():
        print(e['id']); break")
peekaboo click --app Antigravity --window-id "$MANAGER_ID" --on "$CONVO_ID" --snapshot "$SNAP"
sleep 1

# Step 2: Click text field to focus
SNAP2=$(peekaboo see --app Antigravity --window-id "$MANAGER_ID" --json 2>/dev/null \
  | python3 -c "import json,sys; print(json.load(sys.stdin)['data']['snapshot_id'])")
TF_ID=$(peekaboo see --app Antigravity --window-id "$MANAGER_ID" --json 2>/dev/null | python3 -c "
import json,sys; data=json.load(sys.stdin)
for e in data['data']['ui_elements']:
    if e.get('role','') == 'textField' and 'text entry' in (e.get('label','') or ''):
        print(e['id']); break")
peekaboo click --app Antigravity --window-id "$MANAGER_ID" --on "$TF_ID" --snapshot "$SNAP2"

# Step 3: Paste and send
peekaboo paste --app Antigravity --text "your follow-up message"
peekaboo press "Return" --app Antigravity
```

**Tested behavior**: Messages sent via paste+Return are received and processed immediately. The conversation auto-renames based on the first message content.

**Note**: In active/idle conversations, the Send button does NOT appear in A11y. Use `peekaboo press "Return"` instead — confirmed working.

**Important**: The textField may NOT appear in the A11y tree initially when switching to a conversation. It becomes accessible **after clicking the input area** (either via coordinates or by clicking the conversation content area first). If `textField` is not in the A11y tree:
1. Click the input area coordinates (bottom of content pane, roughly `y=-140` relative to Manager window)
2. Re-snapshot — `textField` with label "text entry area" should now appear
3. Then paste + Return as usual

---

## Chat History panel

The Chat History panel shows a **flat list of ALL conversations** across all workspaces, with search and timestamps.

```bash
# Open Chat History
SNAP=$(peekaboo see --app Antigravity --window-id "$MANAGER_ID" --json 2>/dev/null \
  | python3 -c "import json,sys; print(json.load(sys.stdin)['data']['snapshot_id'])")
peekaboo click --app Antigravity --window-id "$MANAGER_ID" --on <CHAT_HISTORY_BUTTON> --snapshot "$SNAP"
```

The Chat History button is labeled `history Chat History` in A11y. It shows:
- Conversation title and workspace name
- Time-ago timestamps
- Blue dot for active/recent conversations
- Spinner icon for running conversations
- Search bar for filtering

**Use case**: When you need to find a specific conversation across workspaces, Chat History is faster than scrolling through each workspace section in the sidebar.

---

## MANDATORY: Monitor, read, and assess active conversations

**This is the most important part of the skill.** Starting a conversation is useless if you don't read what Gemini is actually producing and respond to it. Every interaction with Antigravity MUST include a read-assess-respond cycle.

### After starting or checking a conversation, ALWAYS:

1. **Read the conversation content** — conversation text is web-rendered and NOT in the A11y tree. Use `screencapture` + vision to read what Gemini wrote:

```bash
# Get window bounds for the Manager
MANAGER_ID=<MANAGER_ID>
BOUNDS=$(peekaboo window list --app Antigravity --json 2>/dev/null | python3 -c "
import json, sys
for w in json.load(sys.stdin)['data']['windows']:
    if w['window_id'] == $MANAGER_ID:
        b = w['bounds']
        print(f\"{b['x']},{b['y']},{b['width']},{b['height']}\")")

# Capture the conversation view
screencapture -x -R${BOUNDS} /tmp/convo_read.png

# Read the screenshot with Claude vision to extract content
# The A11y tree only gives sidebar buttons and menu items — NOT chat messages

# To scroll through long conversations:
peekaboo scroll --app Antigravity --window-id "$MANAGER_ID" --direction down --amount 10
# Or use keyboard after clicking the conversation area:
peekaboo click --app Antigravity --window-id "$MANAGER_ID" --coords <center_x>,<center_y>
peekaboo press "pagedown" --app Antigravity
```

**IMPORTANT**: `peekaboo see --json` on the Manager window returns sidebar elements (conversation titles, workspace labels, menu items) but NOT the web-rendered conversation content (chat messages, code blocks, progress updates). You MUST use screenshots to read what the agent is actually doing.

2. **Assess the agent's state** — determine what's happening:
   - Is it making progress on the task?
   - Is it stuck, asking a question, or hitting an error?
   - Has it drifted to side work (lint, formatting) while the primary task is undone?
   - Did it produce real output (commits, files) or just text?

3. **Check for real artifacts** — verify the agent actually did work:
```bash
# Check if agent pushed commits
cd /path/to/workspace && git log --oneline -5

# Check for new/modified files
git diff --stat HEAD~1
```

4. **Respond or redirect** — if the agent is stuck or drifting:
   - Paste a follow-up message with specific instructions
   - If idle, start a new message to continue the work
   - If erroring, paste the fix or adjust the prompt

### When monitoring for someone else (e.g., a subagent or /loop):

Report these fields:
- **Conversation title** (from Manager)
- **Status** (Running/Idle/Blocked — from Manager indicators)
- **Last visible output** (from conversation window `peekaboo see`)
- **Real artifacts** (commits, files, PRs — from git/gh)
- **Assessment** (on-track / drifting / stuck / done)
- **Recommended action** (continue / redirect / kill)

### Anti-pattern: "conversation started" without reading it

NEVER declare Exit Criterion B or similar "produces output" criteria PASS based solely on:
- Manager showing `progress_activity` (that just means Gemini is responding)
- A window existing with the workspace name
- A fibonacci test prompt getting a response

You MUST read the actual conversation content and verify it relates to the assigned task.

---

## Listing all workspaces and conversations

Use when the user asks "what's happening in Antigravity", "list conversations", "what are agents doing".

### Complete workspace inventory

`peekaboo window list` is the authoritative source for ALL workspaces (the A11y tree only shows the currently expanded workspace):

```bash
# Step 1: all workspaces from window list
peekaboo window list --app Antigravity --json 2>/dev/null | python3 -c "
import json, sys
wins = json.load(sys.stdin)['data']['windows']
print('All Antigravity windows:')
for w in wins:
    title = w['window_title']
    wid = w['window_id']
    is_ws = title.startswith('worktree_') or title.startswith('project_') or title.startswith('cmus_')
    tag = ' [workspace]' if is_ws else ''
    print(f'  {wid:6}  {title}{tag}')
"

# Step 2: conversation list + active status from Manager sidebar
MANAGER_ID=$(peekaboo window list --app Antigravity --json 2>/dev/null \
  | python3 -c "import json,sys; ws=[w for w in json.load(sys.stdin)['data']['windows'] if w['window_title']=='Manager']; print(ws[0]['window_id'])")

peekaboo see --app Antigravity --window-id "$MANAGER_ID" --json 2>/dev/null | python3 -c "
import json, sys, re
data = json.load(sys.stdin)
elems = data['data']['ui_elements']
SKIP = {'add Start new conversation','history Chat History','Open Workspace','See less',
        'Use Playground','import_contacts Knowledge','chrome_product Browser',
        'settings Settings','lightbulb Provide Feedback','close button',
        'full screen button','minimize button','pop up button','Record voice memo',
        'Send','code Open editor'}
print('Conversations visible in sidebar:')
for e in elems:
    label = e.get('label','') or ''
    if e.get('role') == 'button' and label not in SKIP and not label.startswith('See all'):
        active = 'now' in label or 'progress_activity' in label
        clean = re.sub(r'\s+\d+[mhd]$', '', label.replace('progress_activity ','').replace(' now','').strip())
        if clean:
            print(f'  {\"[ACTIVE] \" if active else \"\"}{clean}')
"

# Step 3: screenshot for visual workspace-to-conversation grouping
peekaboo see --app Antigravity --window-id "$MANAGER_ID" --annotate 2>/dev/null
```

**After running:** read the annotated screenshot to visually assign conversations to workspace sections. The A11y tree has no frame data for positional grouping — the screenshot is required.

### Output format

```
### worktree_jlcclawg
  - Reviewing Open Pull Requests [ACTIVE]
  - Testing System Functionality

### worktree_agentog3
  - Auditing Orchestration Component Wiring [ACTIVE]

---
**Summary:** ...
**Next steps:** ...
```

---

## Navigating panels

### Knowledge panel

Click `import_contacts Knowledge` button (A11y accessible). Opens a two-pane view:
- **Left pane**: Knowledge artifact list with checkbox items (web-rendered, NOT in A11y tree)
- **Right pane**: Artifact content viewer with placeholder "Open an artifact from the left pane to view its content here."

A11y elements in Knowledge panel:
- `elem_51` (other): "Knowledge" — panel title
- `elem_52` (other): "info" — info icon
- `elem_69` (other): placeholder text

**Limitation**: Knowledge item list (checkboxes, descriptions) is web-rendered — no A11y access. Must use coordinate clicking or screenshots to interact with individual knowledge items.

### Browser panel

Click `chrome_product Browser` button. Requires Chrome extension install. Supports: URL navigation, DOM manipulation, console access, page reading, video recording, JavaScript execution.

### Settings panel

**Opening**: The `settings Settings` sidebar button does NOT reliably navigate to Settings — it may require coordinate clicking at the sidebar position. The Settings panel only opens when NOT viewing an active conversation.

**How to open reliably**:
1. First click `import_contacts Knowledge` or `chrome_product Browser` to exit conversation view
2. Then click "Settings" text in sidebar via coordinates (approximately y=-128 in screen coords relative to Manager window bottom)

**Settings tab bar** (all A11y accessible as buttons):
| Tab | A11y element | Description |
|-----|-------------|-------------|
| Agent | `Agent` button | Security, artifact review, terminal execution policies |
| Browser | `Browser` button | Browser-specific settings |
| Notifications | `Notifications` button | Notification preferences |
| Models | `Models` button | Model configuration |
| Customizations | `Customizations` button | Custom rules, workflows, skills |
| Tab | `Tab` button | Tab behavior settings |
| Editor | `Editor` button | Editor preferences |
| Account | `Account` button | Account settings |
| Provide Feedback | `Provide Feedback` button | Feedback form |

**Agent tab controls** (all A11y accessible):
| Control | A11y role | Element pattern | Values |
|---------|-----------|----------------|--------|
| Strict Mode | checkbox (switch) | `switch` | On/Off toggle |
| Review Policy | button (dropdown) | `Always Proceeds keyboard_arrow_down` | Always Proceeds / Agent Decides / Asks for Review |
| Terminal Command Auto Execution | button (dropdown) | `Always Proceed keyboard_arrow_down` | Always Proceed / Request Review |

**Interaction pattern for dropdowns**:
```bash
# Click dropdown button to open menu
peekaboo click --app Antigravity --window-id "$MANAGER_ID" --on <dropdown_elem> --snapshot "$SNAP"
# Then click desired option (will appear as new A11y elements)
```

**Known issue**: Scrolling while Settings is open may dismiss the panel and return to Knowledge view.

### Chat History

Click `history Chat History` button. Opens a flat list of all conversations across all workspaces with a search field. Conversations are listed by title with time-ago stamps. Conversation items are A11y accessible as buttons.

---

## Browser integration

Setup: Agent Manager > Browser > give browser task > install Chrome extension.

Capabilities: URL navigation, DOM manipulation (click, scroll, type), console log access, page reading (DOM, screenshots, markdown), video recording, JavaScript execution (policy-controlled). Uses Gemini 2.5 Computer Use model for browser subagent.

---

## Scrolling and navigation in conversations

### Methods (all tested and working as of 2026-03-26)

| Method | Command | Notes |
|--------|---------|-------|
| `peekaboo scroll` | `peekaboo scroll --app Antigravity --window-id $ID --direction down --amount 10` | Works for both sidebar and conversation content |
| Keyboard Page Down | `peekaboo press "pagedown" --app Antigravity` | Click conversation area first to focus |
| Keyboard Down arrow | `peekaboo press "down" --app Antigravity` | Single line scroll |
| Keyboard End | `peekaboo press "end" --app Antigravity` | Jump to bottom |

### Key names for `peekaboo press`

Keys are **positional arguments** (not `--key`). Common working names: `pagedown`, `pageup`, `down`, `up`, `end`, `home`, `tab`, `return`, `escape`, `space`, `delete`. Modifiers use `+` syntax but **only some work**: `Command+w` works, `Command+end` does NOT.

### Scrolling strategy for reading long conversations

```bash
# Scroll to top first
peekaboo scroll --app Antigravity --window-id "$MANAGER_ID" --direction up --amount 50
screencapture -x -R${BOUNDS} /tmp/convo_top.png

# Read each page, scrolling down
for i in $(seq 1 10); do
  peekaboo scroll --app Antigravity --window-id "$MANAGER_ID" --direction down --amount 10
  sleep 0.3
  screencapture -x -R${BOUNDS} /tmp/convo_page_${i}.png
done
```

---

## A11y tree vs web-rendered content

### What the A11y tree exposes (via `peekaboo see --json`)

| Content | Available | Details |
|---------|-----------|---------|
| Sidebar conversation titles | Yes | `button` elements with labels like `progress_activity Title now` or `Title 3d` |
| Sidebar workspace labels | **Partial** | Only the **currently focused workspace** label appears as `other` element. Other workspace labels are web-rendered. |
| "No chats yet" text | Yes | `other` elements under empty workspace sections |
| `add Start new conversation` button | Yes (scroll up) | May be hidden below sidebar fold — scroll up to reveal |
| Menu bar items | Yes | `other`/`menu` elements |
| Text input field | **Click-activated** | `textField` with label `text entry area` — may NOT appear until the input area is clicked (via coordinates or A11y) |
| Send button | **View-dependent** | In new conversation view: YES (button). In active conversation view: NOT in A11y (web-rendered) |
| Planning/Fast toggle | Yes (new convo view) | `button` with label `Planning` or `Fast` |
| Model selector | Yes (new convo view) | `button` with label like `Claude Opus 4.6 (Thinking)` |
| Conversation mode picker | No | Popover shown by "Start new conversation" with Planning/Fast cards — entirely web-rendered |
| Workspace dropdown | Yes (new convo view) | `button` with label `keyboard_arrow_down <workspace>` — but clicking doesn't open web-rendered dropdown |
| Walkthrough artifact content | **Yes** | Unlike regular chat, walkthrough text appears as `other` elements in A11y tree |
| Chat History items | Yes | When Chat History is open, conversation items appear as `button` elements |
| Settings tab bar | **Yes** | Agent, Browser, Notifications, Models, Customizations, Tab, Editor, Account buttons |
| Settings controls | **Yes** | Strict Mode switch, Review Policy dropdown, Terminal Execution dropdown |
| Knowledge panel title | **Yes** | Panel title and placeholder text in A11y |
| Knowledge item list | No | Checkbox items and descriptions are web-rendered |

### What the A11y tree does NOT expose

| Content | Solution |
|---------|----------|
| Chat messages (agent output) | Screenshot + vision |
| Code blocks in conversations | Screenshot + vision |
| Progress Updates steps | Screenshot + vision |
| Allow/Deny buttons | Screenshot + PIL blue-button detection + coordinate click |
| Review buttons | Screenshot + coordinate click |
| Non-focused workspace labels | Click "No chats yet" to expand, or use Chat History |
| Workspace `+` icon (web-rendered) | Use "Start new conversation" button instead |
| Send button (in active convo) | Use `peekaboo press "Return"` instead |

### Key behavior differences by Manager state

| State | A11y elements available |
|-------|------------------------|
| **Idle (conversation selected)** | Sidebar buttons, focused workspace label. Text field appears after clicking input area. |
| **New conversation view** | All controls: Send, Planning, Model, Workspace dropdown, text field |
| **Chat History open** | All conversation items as buttons, search field |
| **Walkthrough artifact visible** | Full walkthrough text as `other` elements |
| **Settings open** | Tab bar buttons (Agent/Browser/Notifications/Models/etc.), controls (switches, dropdowns) |
| **Knowledge open** | Panel title, placeholder text. Knowledge items are web-rendered. |

**Rule**: If you need to READ what the agent wrote, use `screencapture`. If you need to CLICK sidebar/menu elements, use `peekaboo see` + `peekaboo click --on`.

---

## Element targeting rules

1. Always confirm `[win] Window: Manager` in `see` output before acting.
2. Use `--on elem_N` with `--snapshot <ID>` for reliability.
3. After clicking a workspace label, verify a `textField` appears before pasting.
4. After send, re-snapshot and confirm `progress_activity` or `now` on the new conversation.

---

## OAuth vs API key clarification

- OpenClaw agent auth inside Antigravity uses OAuth. Do not replace or reconfigure it.
- If `peekaboo see --analyze` fails with `OPENAI_API_KEY not found`, that is Peekaboo's optional image-analysis backend — **not** an Antigravity auth failure. Skip `--analyze` or set `OPENAI_API_KEY`.

---

## Known limitations

- Rate limits are aggressive (especially Gemini 3 Pro free tier)
- The A11y tree does NOT provide frame/position data — use screenshots for spatial layout
- Conversation scrolling in the Manager content pane DOES work with `peekaboo scroll --direction down/up --amount N` (tested 2026-03-26). Keyboard `pagedown`/`down`/`end` keys also work after clicking the conversation area first.
- No right-click context menus on sidebar conversations (delete/rename must be done from within conversation)
- `peekaboo hover` does not reliably reveal hidden controls in Antigravity
- Performance degrades over extended sessions; battery drain on laptops
- **Git commands can hang indefinitely** — Antigravity agents sometimes stall on git operations (push, fetch, checkout). See "Git command guidance" below.
- **`peekaboo see` hangs on large A11y trees** — when the Manager has 10+ conversations or many workspaces expanded, `peekaboo see` blocks indefinitely. See mitigation below.

### `peekaboo see` hang — root cause and fix

**Root cause**: Multiple concurrent or abandoned `peekaboo see` calls accumulate as zombie processes and block macOS A11y queries **systemwide** — not just for Antigravity. When this happens, `peekaboo see` times out for ALL apps including Finder.

**Diagnosis**:
```bash
pgrep -fl "peekaboo see"
# If multiple lines appear → stale processes are blocking A11y
```

**Fix (takes 5 seconds)**:
```bash
pkill -f "peekaboo see"   # kill all stale peekaboo see processes
sleep 1
# Now peekaboo see works again for all apps
```

**Prevention**: Never fire multiple `peekaboo see` calls in parallel. Always wait for one to complete before starting another. If a call is in a background task (`run_in_background`), kill it explicitly before issuing another.

**Antigravity restart is NOT needed** — the A11y blockage is in peekaboo, not Antigravity.

### `peekaboo see` hang mitigation — ALWAYS use timeout prefix

`peekaboo see` WILL hang indefinitely on large Manager windows (10+ conversations, many workspaces).

**Rule**: Always wrap `peekaboo see` with `timeout 12`:

```bash
# Standard pattern — NEVER call bare peekaboo see
SNAP_JSON=$(timeout 12 peekaboo see --app Antigravity --window-id "$MANAGER_ID" --json 2>/dev/null)
if [ -z "$SNAP_JSON" ]; then
  echo "A11y tree unavailable (hang/timeout) — switching to screenshot+coordinate approach"
  # Fall back to screencapture + pixel analysis for all interactions
fi
```

When `peekaboo see` hangs:
1. **Model selector**: use coordinate click from screenshot (model selector bottom of input area, ~y=395 in 455-tall image)
2. **Text field focus**: after coordinate click, probe with `peekaboo press "period"`, take screenshot to verify cursor is in field, then `peekaboo press "delete"` and paste
3. **Sending**: use `peekaboo press "Return"` — does NOT require A11y to be working
4. **Conversation monitoring**: use screenshot-only (`screencapture` + vision) — never requires `peekaboo see`

### Text field focus — PROVEN RELIABLE METHOD (2026-03-31)

**Key finding**: The `text entry area` textField element reports WRONG screen coordinates (e.g., y=927 when window is at y=-1013). Do NOT click it by its reported coordinates. Instead use the hardcoded coordinate approach below.

**The `group` textField elements** (elem_59, elem_60) also have unstable IDs — they shift when more conversations are added to the sidebar. Use coordinates instead.

**PROVEN: Clicking at (1473, -623) reliably focuses the text input for a Manager window at x=832, y=-1013.** This is the center-right area of the conversation pane where the "group" textField container is.

```bash
MANAGER_ID=<MANAGER_ID>
# WIN bounds: x=832, y=-1013, w=1025, h=904

# Step 1: Click at known-working coordinates to focus input
peekaboo click --app Antigravity --window-id "$MANAGER_ID" --coords "1473,-623"
sleep 0.3

# Step 2: Verify focus — probe with space, then check screenshot for cursor
peekaboo press "space" --app Antigravity
sleep 0.2
screencapture -x -R832,-1013,1025,904 /tmp/focus_probe.png
# If input has cursor (blinking line) and Send button turned blue → focused
# If input still shows placeholder text → not focused, try again

# Step 3: Delete probe and paste real text
peekaboo press "delete" --app Antigravity
peekaboo paste --app Antigravity --text "your actual prompt"
peekaboo press "return" --app Antigravity
```

**Why (1473,-623) works**: This is the location of the `group` textField container that spans the content pane. Clicking it delegates focus to the actual web-rendered text input. The y=-623 is approximately 43% from the top of the 904px-tall window.

**For different window positions**: Adjust x and y proportionally from window origin. The `group` textField is typically at ~63% across and ~43% down from the window top.

## Git command guidance for Antigravity prompts

Antigravity agents (Gemini-powered) sometimes hang on git commands — particularly `git push`, `git fetch`, and `git checkout` — causing the entire conversation to stall with no timeout. When composing prompts for Antigravity, **always include git command guidance** from `~/.gemini/GEMINI.md`:

### Rules to include in every Antigravity prompt that involves git:

```
Git rules:
- Always push after finishing any unit of work
- Always infer remote branch via `gh pr view <N> --json headRefName`
- Always report remote commit URL after pushing
- Never run destructive git commands (reset --hard, push --force) unless explicitly asked
- Never use `git add -A` — stage only files you changed
- Use `git mv` for moving files (preserves history)
- If a git command hangs for >30 seconds, cancel it (Ctrl+C) and retry with --no-verify or investigate the cause
- For git push: always use `git push origin <branch>` explicitly — never bare `git push`
- For git fetch: use `git fetch origin` — never bare `git fetch` which may fetch all remotes
- If git asks for credentials or passphrase interactively, cancel immediately — it will hang forever in Antigravity
```

### Why git hangs in Antigravity

1. **Credential prompts**: git may prompt for SSH passphrase or HTTPS credentials. Antigravity has no interactive stdin — the prompt blocks forever.
2. **Large fetches**: `git fetch` without specifying remote fetches all remotes, which can hang on unreachable upstreams.
3. **Hook scripts**: pre-push or pre-commit hooks may hang if they require network access or user input.
4. **Lock files**: concurrent git operations from other agents may leave `.git/index.lock`, causing subsequent operations to wait.

### Detection and recovery

When monitoring an Antigravity conversation (via the loop), detect hangs by:
1. Screenshot shows "Always run" or terminal output frozen for >2 minutes with no new progress
2. `progress_activity` spinner is still showing but no new "Files Edited" or "Progress Updates"
3. The same terminal command output is visible across 2+ monitoring cycles

Recovery: Send a follow-up message in the conversation: "The git command appears hung. Please cancel it with Ctrl+C and retry, or skip the push and move to the next task."

## Editor fallback — sending messages via Cmd+L AI panel

When **`ANTIGRAVITY_WINDOW=editor`** or **`ANTIGRAVITY_TARGET=editor`** (from the window resolver), this is the **primary** path — not a fallback. Set `EDITOR_ID="${ANTIGRAVITY_WINDOW_ID}"` and skip Manager-only flows.

When the Agent Manager window is unavailable (not running, or `MANAGER_ID` is empty after Step 0a), use the Editor's AI side panel (Cmd+L) to interact with conversations.

### When to use Editor fallback
- `peekaboo window list` returns no window with `window_title == "Manager"`
- Agent Manager crashed or was closed by user
- Task involves editing code directly in the IDE and launching a conversation from there

### Editor fallback interaction flow

```bash
USE_EDITOR="${USE_EDITOR:-0}"

if [ "$USE_EDITOR" = "1" ]; then
  # Step E1: Get the editor window ID (worktree or generic Antigravity window)
  EDITOR_ID=$(peekaboo window list --app Antigravity --json 2>/dev/null | python3 -c "
import json, sys
ws = json.load(sys.stdin)['data']['windows']
# Prefer worktree/project windows
for w in ws:
    t = w['window_title']
    if t.startswith('worktree_') or t.startswith('project_'):
        print(w['window_id']); exit()
# Fall back to first non-infrastructure window
for w in ws:
    t = w['window_title']
    if t not in ('Manager', 'Launchpad', 'hidden-nova'):
        print(w['window_id']); exit()
" 2>/dev/null)

  if [ -z "$EDITOR_ID" ]; then
    echo "ERROR: No Antigravity editor window found — is Antigravity running?"
    exit 1
  fi
  echo "Using Editor window: $EDITOR_ID"

  # Step E2: Focus Antigravity
  osascript -e 'tell application "Antigravity" to activate'
  sleep 0.5

  # Step E3: Open AI side panel with Cmd+L
  peekaboo press "cmd+l" --app Antigravity --window-id "$EDITOR_ID"
  sleep 1

  # Step E4: Verify panel opened (screenshot check)
  BOUNDS=$(peekaboo window list --app Antigravity --json 2>/dev/null | python3 -c "
import json, sys
for w in json.load(sys.stdin)['data']['windows']:
    if str(w['window_id']) == '$EDITOR_ID':
        b = w['bounds']
        print(f\"{b['x']},{b['y']},{b['width']},{b['height']}\")
")
  screencapture -x -R${BOUNDS} /tmp/editor_panel.png
  # If panel is open, the right side of the screenshot shows a chat-like UI

  # Step E5: Click into the AI input area (bottom of side panel — right ~30% of window)
  WIN_X=$(echo "$BOUNDS" | cut -d, -f1)
  WIN_Y=$(echo "$BOUNDS" | cut -d, -f2)
  WIN_W=$(echo "$BOUNDS" | cut -d, -f3)
  WIN_H=$(echo "$BOUNDS" | cut -d, -f4)
  INPUT_X=$(python3 -c "print(int($WIN_X + $WIN_W * 0.85))")
  INPUT_Y=$(python3 -c "print(int($WIN_Y + $WIN_H * 0.92))")
  peekaboo click --app Antigravity --window-id "$EDITOR_ID" --coords "${INPUT_X},${INPUT_Y}"
  sleep 0.3

  # Step E6: Paste prompt and send
  peekaboo paste --app Antigravity --text "You are working in /path/to/workspace on branch X. <your task>"
  peekaboo press "return" --app Antigravity
  sleep 2

  # Step E7: Verify — screenshot to check response started
  screencapture -x -R${BOUNDS} /tmp/editor_sent.png
fi
```

### Editor vs Manager — capability comparison

| Feature | Agent Manager | Editor (Cmd+L) |
|---------|--------------|---------------|
| New conversation with workspace picker | Yes (A11y) | No (always uses current workspace) |
| Model selector | Yes (A11y in new convo view) | Limited (depends on editor version) |
| Planning mode toggle | Yes (A11y) | No |
| Conversation history | Yes (Chat History panel) | Current session only |
| Allow prompt detection | Via screenshot (Manager viewport) | Via screenshot (Editor viewport) |
| Multi-workspace orchestration | Yes | No — scoped to open workspace |
| Inline code actions (Cmd+I) | N/A | Yes |
| Artifacts (Walkthrough, Diffs) | Yes | Yes (via Artifacts button) |

### Editor fallback notes
- **Workspace scoping**: Cmd+L opens AI for the current open workspace. To target a different workspace, open it first with `agy /path/to/workspace`.
- **Reading responses**: Use `screencapture` + vision — same as Manager (conversation content is web-rendered in both paths).
- **Input coordinates**: The Cmd+L panel is web-rendered. The 85%/92% heuristic works reliably; use screenshot analysis to confirm.
- **Allow prompts**: Same blue-button detection method applies (see "Allow this conversation" dialog section above).

### Screenshot flickering workaround

If screenshots show blank/white for Antigravity windows:
1. **Restart Antigravity**: `osascript -e 'tell application "Antigravity" to quit'` then `open -a Antigravity`
2. **Use A11y as backup**: `peekaboo see --json` still returns conversation status even when screenshots fail
3. **Check window count**: After restart, use `peekaboo window list` to count workspaces (exclude Launchpad/empty)
4. **If Manager missing**: use `agy /path/to/workspace` to trigger Manager window appearance

---

## Security note

Antigravity agents can read `.gitignore`, `.env`, and other sensitive files in the workspace. A documented vulnerability exists where hidden file instructions (e.g., in a cloned repo) can trigger credential exfiltration through image URL rendering. Be cautious when opening untrusted repositories.

---

## Completion criteria

Declare completion only when:
- Goal state is visible in screenshot evidence, or
- You are blocked and provide the exact blocker + required human input.

Always return: final status, last 3 step logs, screenshot/file references.

---

## Reference links

| Resource | URL |
|----------|-----|
| Official docs | https://antigravity.google/docs |
| Agent Manager docs | https://antigravity.google/docs/agent-manager |
| Panes docs | https://antigravity.google/docs/panes |
| Walkthrough docs | https://antigravity.google/docs/walkthrough |
| Settings docs | https://antigravity.google/docs/settings |
| CLI docs | https://antigravity.google/docs/command |
| Keyboard shortcuts guide | https://antigravitylab.net/en/articles/tips/keyboard-shortcuts-guide |
| Google Developers Blog | https://developers.googleblog.com/build-with-google-antigravity-our-new-agentic-development-platform/ |
| Codelab tutorial | https://codelabs.developers.google.com/getting-started-google-antigravity |
