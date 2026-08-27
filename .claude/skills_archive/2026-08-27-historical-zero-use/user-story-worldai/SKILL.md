---
name: user-story-worldai
description: your-project.com-specific practice for the no-code visual user-story spec — where the docset lives, which evidence sources settle which claim, the traps that have produced false claims here, and the claims already refuted. Use with (not instead of) the user-scope user-story skill.
---

# /user-story — your-project.com specifics

**This file is self-contained** — the general-law summary below covers what a fresh clone, CI job, or automation account needs. If `~/.claude/skills/user-story/SKILL.md` exists on the machine you're running on (a user-scope personal skill, not part of this repo), read it too for the full rationale and worked examples; treat it as a supplement, not a hard dependency.

### General law (inline summary)

- **Rewritability Test**: the docset passes when an adversarial reader can answer, for every flow, *what the user sees, what they can do, what happens next, what failure looks like* — from the docs alone. Verdicts: REWRITABLE-AS-IS / REWRITABLE-WITH-GAPS (listed precisely) / NOT-REWRITABLE.
- **Story form**: `As a <user>, I want <goal>, So that <benefit>` + 3–6 checkbox acceptance criteria, INVEST-compliant. Split stories with >6 criteria.
- **Zero-code ban**: no API names, schemas, function/class/file names, service/model names, database/infra terms, or "the system validates/processes..." — every criterion must name something the user can SEE, HEAR, or DO on screen, verifiable without interpretation.
- **Negative/failure states are mandatory content**, not an appendix — every wait has a visible state, every error has a face.
- **Visual mandate**: a real capture per distinct screen/moment is required if the screen exists in the running product; a hand-drawn mock is NOT a substitute (it launders assumption into evidence) and is only valid for screens that don't exist yet, labelled as proposals. Coverage invariant: every screen in the flow map has either a real capture or an explicit "not photographed" note — silence is not allowed.
- **Evidence-class matching**: a still settles what a screen looks like; a claim about behavior over time (streaming, animation, scroll, a transition, anything "across scenes/sessions") needs a frame PAIR, a recording, or a transcript excerpt from two distant points. Match the evidence class to the claim being made, not the cheapest one available.
- **Anti-patterns**: code pointers as acceptance criteria; bug-repro fixtures counted as UI mocks; a mock standing in for a photographable screen; "the feature works correctly" (untestable vagueness); a disclaimer that doesn't match the image when reopened; a citation fixed but the surrounding prose left stale; a rewritability verdict from link-checks alone with zero images opened.

## Where things are

| | |
|---|---|
| Docset | `docs/user-stories-ui/` — 111 story docs (US=63, NEW=48 — re-derive by counting `docs/user-stories-ui/`, do not hardcode), 6 journeys, `INDEX.md`, `NEW_STORIES_INDEX.md` |
| Captures | `docs/user-stories-ui/screenshots/` + `MANIFEST.md` (what each image literally shows) |
| Video | `docs/user-stories-ui/videos/` — git LFS tracked |
| Audits | `docs/user-stories-ui/reviews/` — `VERDICT*.md`, `BEHAVIORAL_EVIDENCE.md`, `CAPTURE_PLAN.md`, `DISCLAIMER_TRIAGE.md` |
| Canonical repo | Derive dynamically: `git -C <checkout> rev-parse --show-toplevel` (or run it from inside the checkout). If more than one `your-project.com` checkout exists on the machine, verify you're in the one whose `git remote -v` and current branch match what you expect before trusting anything in it — a stale sibling checkout has caused at least one wrong-tree audit. |

**Read `reviews/BEHAVIORAL_EVIDENCE.md` before testing any claim.** It records what has already been settled, with scene numbers. Re-litigating settled ground wastes a pass.

**Read `docs/user-stories-ui/METHODOLOGY.md` before extending the spec.** It records how the material was acquired, which evidence class settles which claim here, how it was reviewed, and what went wrong at each stage — including the failures that produced the rules below. It is also the page to update when a new failure teaches something.

## The spec has two halves — do not audit them by the same standard

| Half | Pages | Evidence |
|---|---|---|
| **Visual** | `US-*`, `NEW-*`, `journeys/` | Real captures, frame pairs, transcripts, clips |
| **Non-visual** | `ARCHITECTURE-*.md` | **Prose only. No screenshots by design.** |

The non-visual half — the data model, persistence, the backend-versus-model responsibility split, the machine-facing integration surface, the rules corpus, mobile layout, and the canonical turn composition — exists because the user asked for "everything including data model and persistence and what the backend handles vs llm", and explicitly said that part "doesn't have to be visual". A coverage audit that reports these as missing captures is measuring the wrong thing; they are indexed under a "non-visual half" heading in `INDEX.md` for exactly that reason.

**`ARCHITECTURE-rules-corpus.md` is load-bearing.** Roughly half the combat and progression criteria say a value must be "correct" or "match the table" without restating the table. That page names the fifth-edition tabletop rules as normative and lists the dependent stories. If you add a mechanics criterion, link it there — a criterion saying "correct" with no corpus is a placeholder, not a criterion.

## Never capture against a deployment

`/api/waitlist/status` is rate-limited **per client IP, not per user**, and the app re-checks access on every page load, sign-in, token refresh, and tab refocus. Capture automation from one machine exhausts the bucket for every human on that IP — and the client then renders the failure as *"you are not approved for access."* This locked the repo owner out of the dev site on 2026-07-26.

Capture against a **local server** only:

```bash
export WORLDAI_DEV_MODE=true TESTING_AUTH_BYPASS=true
export WAITLIST_STATUS_RATE_LIMIT="100000 per hour, 10000 per minute"
./run_local_server.sh --no-log-stream --force-default-port   # serves :8081
```

Verify before trusting it: `GET /health` → 200 **and** the landing page renders real content (title `WorldAI`, "YOUR AI-POWERED DUNGEON MASTER"). A 200 on `/health` does not mean the app paints.

**The port is NOT reliably 8081.** The script prints "Flask:8081" up front, then — absent `--force-default-port` — computes a **branch-specific hash port** and binds there instead (observed: 8036, 8066). Always discover the real port from the log rather than assuming:

```bash
grep "Flask Backend:" /tmp/<your-log>.log | tail -1     # or: grep -m1 -A3 "Server Configuration:" ...
```

Do **not** pass `--force-default-port` when other agents may be running — it kills whatever holds 8081/3002, including their servers. Before starting one at all, check whether a server is already up and reuse it; four concurrent lanes each started their own during one pass.

**Headless capture setup** (Playwright is *not* in the canonical venvs; `venv/` is recreated by the server script):

```bash
python3 -m venv /tmp/pw_venv && /tmp/pw_venv/bin/python -m pip install -q playwright
# chromium binaries are usually already warm in ~/Library/Caches/ms-playwright/
```

Phone captures: 390×844 viewport, `device_scale_factor=3`, `is_mobile=True`, touch enabled — see `ARCHITECTURE-mobile-layout.md` for what is and is not captured. Note that navigating to a signed-in route while signed out silently returns the landing page, so verify the *content* of every capture before naming it after the screen you intended.

Known unrelated breakage: a dirty canonical checkout can crash the MCP sub-server on an import error without preventing Flask from serving pages. Ignore it unless you specifically need that sub-server.

**Match the server to the claim.** `run_local_server.sh` uses Flask's dev server; production uses gunicorn with threaded workers (`$PROJECT_ROOT/Dockerfile` → `gunicorn -c gunicorn.conf.py`). A streaming or concurrency claim tested against the dev server proves nothing about production — a lane measured "streaming does not stream" on the dev server and was wrong; under gunicorn the same turn arrived as 45 chunks over ~7s.

Running gunicorn locally on macOS needs four workarounds, none obvious — it took seven attempts to find them (bead `rev-tgc04`, logs in the evidence bundle):

```bash
OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES \
no_proxy='*' NO_PROXY='*' \
GRPC_DNS_RESOLVER=native \
gunicorn -c gunicorn.conf.py 'main:create_app()'      # NO --preload
```

Each omission has its own failure signature: without the ObjC var the worker aborts on fork (a thread start in the post-fork warmup path); with `--preload` the data-store client is created pre-fork and every call hangs at 0% CPU inside grpc; without the proxy vars you get a SIGSEGV crash-loop; without the native DNS resolver the store hangs even once stable. A hang is not a timeout to wait out — sample the process.

## Evidence sources, by claim type

| Claim | Settled by |
|---|---|
| What a screen looks like | Screenshot |
| A transition / in-flight state | Before-after frame pair, or video |
| Streaming, animation, scroll | Video — and verify the frames, not the caption |
| Anything holding "across scenes" | **Campaign transcript excerpts**, two distant scene numbers |

**CHECK THE DATE BEFORE YOU TRUST A TRANSCRIPT.** The corpus spans years. A defect visible in an old campaign may be long fixed, and a "not found" against old campaigns says nothing about now — both were real errors here. Four findings once rested on a campaign last played **thirteen months** earlier, and two `NOT FOUND` verdicts turned out to be false negatives that fresh play immediately contradicted.

```bash
# rank the whole corpus by when it was last played
cd ~/llm_wiki/raw/campaigns
for f in */*game_state.json; do
  python3 -c "import json,sys;print(json.load(open('$f'))['last_state_update_timestamp'][:10],'$f')" 2>/dev/null
done | sort -r | head -20
```

Prefer campaigns played within the last month; state the date of every transcript you cite. Note also that campaign *archetype* skews results — god-mode/deity runs show no player damage at all, while traditional combat runs show 12–33%. Sample across archetypes before generalising.

Long campaigns live at `~/llm_wiki/raw/campaigns/<ID>/*.txt`. Scenes are delimited by lines reading `SCENE <N>`; turns are marked `Game Master:`, `You:`, `God Mode:`, `Location:`. Files are 1–3.5 MB — grep to locate, then read only that range. Never read one whole into context.

Four long campaigns are copied under `<your-email@gmail.com>` for live use:

| Campaign | Scenes | Rich in |
|---|---|---|
| `CqqQtPrqRfu6ecbRDOVi` Itachi Evil 2 | 527 | gold, time-skips, nat-1s |
| `7Ptv1Z5iKrKIHNAenZi1` Vespera Thul | 700 | siege runs, HP lines |
| `Vk9qjPWdSQ4WjziyWMBl` aurelius caesar | 490 | factions, world dials |
| `aPP5Nj10LiC91ofA9gwT` Thay trader | 424 | companions |

Copying more: `scripts/copy_campaign.py` **fail-closes** when the source is resolved via `--find-by-id`/`--source-email` and neither `--dest-email` nor `--allow-same-user` is given — it prints `refusing copy: no --dest-email and no --allow-same-user flag` and exits 1 (`scripts/copy_campaign.py:718-733`). Always pass `--dest-email <your-email@gmail.com>` explicitly rather than relying on the refusal path. `$USER@gmail.com` is read-only.

## Traps that have produced false claims here

- **A matched string is not a matched meaning.** `HP 5/8` in these transcripts is usually **`Social HP`** — a different mechanic from physical HP. Check which field a number belongs to before concluding anything from it.
- **The story log is one continuously-growing scrollable area.** Clicking a panel toggle does *not* scroll to the content it produces, so a capture named for a panel often shows a different part of the page. Scroll to the produced content and confirm it is in frame.

- **A control's state and the log's content are from different moments — never read them as one event.** The Character/Think-Plan/God radios report what is selected *right now*; the log above reports what *earlier* turns produced. So a frame showing "Think/Plan selected" beside a God-mode reply is not a bug, a mislabelled file, or two swapped screenshots — it is one scrollback position photographed with a different radio clicked. Proof on file: `levelup_flow_hp_step.png` has **Character** selected while displaying a God Mode Response, and `gameplay_god_mode_response_deep_campaign.png` and `gameplay_mode_selector_thinkplan.png` have identical log content with only the lit radio differing. A five-lens review plus an adversarial verifier plus an Opus judge all read this as "the mocks are swapped" and recommended swapping the citations, which would have produced two new false captions (2026-07-26). **To photograph a mode's output you must capture the reply and its own radio in one frame** — otherwise the capture proves the selector exists, not what the selection does.

- **Every gameplay capture in this repo was taken with the "Debug Mode Active" badge lit.** Anything visible in one may be a debug affordance rather than something a player sees: the "🔍 Debug Info / 🤖 Agent: <name>" footers definitely are. Before documenting an in-log element as player-facing, either capture it with debug off or record its gating as **undetermined** — do not infer "always on" from "present in every capture we happen to hold", because every capture shares the same confound.

- **`GodModeCacheRepro` is a bug-reproduction fixture, not a campaign.** Frames captured in it (including `gameplay_mode_selector_thinkplan.png` and `gameplay_god_mode_response_deep_campaign.png`) show real behavior, but the general skill bans repro fixtures as mocks. Corroborate anything sourced from it against an ordinary campaign — e.g. the god-mode-reply-duplicated-as-numbered-scene defect reproduces in "My Epic Adventure" via `levelup_flow_hp_step.png` — and state the provenance wherever the frame is cited.
- **Filenames lie.** Open every image before writing a sentence about it. Multiple reviewers here have been misled by a filename that did not match its pixels.
- **Grep false-negatives are frequent** in this docset, because correction notes quote the text they replaced. Run a positive control before any absence claim, and read surrounding context before concluding from a count.

## Claims already refuted — do not re-assert

Each of these was well-formed, observable, correctly cited, and **wrong**. All four survived four rounds of adversarial document review; transcripts refuted them in one pass.

| Claim as written | Reality |
|---|---|
| Gold never updates (documented as a shipped gap) | Six distinct values, 75 → 7495 GP, scenes 99–351 |
| World-dials checkpoint appears ~every 10 scenes | Appears in 489 of 490 — essentially per scene |
| A bad roll produces a narrated HP drop | 0/400 and 1/697 player HP losses; enemy HP loss *is* tracked |
| In-world time contradiction "not observed in any capture" | Observed at scenes 458/466; the narrator calls it a repeated failure |
| God-mode reply "never visually confusable with in-character narration" | Rendered **twice** — once in its labelled block, then verbatim below as plain "Scene #395:" narration. Reproduces in a second campaign as "Scene #6:" |
| A god-mode edit "must never silently consume a story turn" | The duplicate carries a **scene number**, so the edit visibly occupies a numbered slot — in the same frame that promises no time passed |
| Wizard: "a required field left blank keeps Next disabled" (asserted in 4 places, 3 of them state-table rows) | Character and Setting are documented-optional and both empty in `wizard_step1_choose_type.png` with Next rendered active. No disabled-Next state is photographed anywhere |
| Wizard is 5–6 steps | **Two.** The capture reads "Step 1 of 2" |
| The launch summary echoes the fields the player reviewed | The saved Title ("My Epic Adventure") and the summary's in-fiction Title ("Secrets of the Chultan Wilds") are both on screen and differ |

The fourth is the most instructive: an unverified **negative** shipped as settled fact. *"Not observed" is a claim, not a hedge* — it needs evidence exactly like a positive does. Distinguish it from benign `## Mock` boilerplate meaning "no screenshot exists," which is fine and expected.

## Evidence bar for code changes

`AGENTS.md` (§ Evidence for mvp_site Production Changes) governs any non-test `$PROJECT_ROOT/**` change: unit tests are supporting checks only and do **not** satisfy `/es`; a user-visible or interactive change needs captioned video tied to the PR HEAD SHA; `N/A` is valid only for comments, docs, formatting, type hints, and import order. Scoping an `N/A` around the population a change doesn't affect is not a valid use of it.

Evidence bucket: `gs://wa-test-evidence/` (private, `pr-NNNN/` convention, gcloud auth already works).

## Keeping this file honest

When a session learns something durable about documenting *this* product — a new trap, a refuted claim, a better evidence source — add it here rather than to the user-scope skill. General practice goes up to `~/.claude/skills/user-story/SKILL.md`; product specifics stay here. Cite provenance (scene numbers, PR, bead) so the next reader can verify without re-deriving.
