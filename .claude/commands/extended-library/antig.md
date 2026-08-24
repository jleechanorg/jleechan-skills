---
description: Antigravity computer use via Peekaboo — interact with the Antigravity macOS app. Also used by /eloop to babysit the Antigravity IDE and self-improve this skill.
---

Use the `antigravity-computer-use` skill to complete the following task in Antigravity:

$ARGUMENTS

---

## Self-improvement protocol (for /eloop and monitoring loops)

When you encounter a new failure mode or workaround while using Antigravity:

1. **Document the lesson** as a dated note at the top of the MANDATORY section in the skill:
   ```
   - YYYY-MM-DD: <what failed> → <what works instead>
   ```

2. **Update the skill file** at `$HOME/.claude/skills/antigravity-computer-use/SKILL.md`:
   - Add the new workaround to the relevant section
   - Update the "MANDATORY" section if it's a universal check
   - Keep entries concise and actionable

3. **Report the improvement** in your recap: `skill_updated=true, section=<section name>`

### Known lessons (update as we learn more)

| Date | Failure | Fix added to skill |
|------|---------|-------------------|
| 2026-04-06 | Terminal commands (git, gh) hang — root cause: FSEvents flood from home-dir workspace | Workspace must be scoped to project dirs, never ~/. Renderer saturates at 99% CPU when watching ~/. Beads: bd-e1wo, bd-ru3r |
| 2026-04-06 | Gemini 3.1 Pro 429 RESOURCE_EXHAUSTED creates zombie conversations | Quota exhaustion causes retry loops; switch to Claude Opus or wait for reset. Bead: bd-vh4j |
| 2026-04-06 | "continue" on old conversations references deleted paths/PRs | Prefer new conversations; stale context causes cascade failures. Bead: bd-ee9k |
| 2026-04-05 | Sidebar spinner (◌) persists on dead conversations — unreliable indicator | Added 4-state health classification: zombie-spinner/frozen-active/actually-working/cleanly-idle; must cross-check with red ■ + status bar |
| 2026-04-05 | VS Code "Remote Window" dialog silently blocks agent | Press Escape to close; verify red-stop resumes after |
| 2026-04-05 | x≈2 left-edge gutter FP in editor win 902 | Add `cx//2 > 30` filter to PIL scan |
| 2026-04-05 | Window IDs change every Antigravity relaunch | Always re-run `peekaboo window list`; never cache IDs |
| 2026-04-05 | Sidebar elem click doesn't switch view when another convo generating | Use coordinate click instead; items ~25px logical apart |
| 2026-04-05 | New Conversation message routed to wrong convo | Verify title bar changed; use `agy chat --reuse-window` from workspace dir as fallback |
| 2026-04-05 | Opening workspace folder closes Manager window | Use "Switch to Agent Manager" in editor to restore |
| 2026-04-05 | Editor Agent panel input coords | win 902 (-28,-998,1189,857): screen (959,-608); Manager (429,-1005,1437,849): input at (860,-230) |
| 2026-04-04 | Allow dialog missed after send | MANDATORY section added — PIL blue-button scan after every screenshot |
| 2026-04-03 | Editor FPs: VS Code Python interpreter (726,628), bottom notification (454,715), terminal Relocate (928,595) | Known FP dict added to SKILL.md — add to FP set; real dialogs dismiss on click, FPs do not |
| 2026-04-03 | Manager window closed; old bounds captured wrong window (Claude usage page) | Re-fetch window list each cycle; switch PIL bounds to editor when Manager absent |
| 2026-04-03 | Fullscreen editor window (0,37,1728,1080) triggers FP at (83,623) — VS Code diff gutter indicators | Added '83,623' to FP dict; PIL must divide by 2 for retina (cx//2, cy//2) |
| 2026-04-03 | x<100 coords in fullscreen always gutter FPs — 83,586 and 91,585 also triggered in successive scans | Gutter FP rule added: x<100 in fullscreen = always skip; real Allow dialogs appear at x>300 |
