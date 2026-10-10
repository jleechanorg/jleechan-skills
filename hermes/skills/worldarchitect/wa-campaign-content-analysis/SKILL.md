---
name: wa-campaign-content-analysis
description: "Analyze existing Your Project campaigns in place to diagnose prompt, agent, or quality issues — without copying or exporting. Per-scene content classification with agent attribution via debug_info.agent_name. Use when the user asks 'why is the LLM doing X in my campaigns', 'do a regression review across the last N campaigns', 'audit dialog/NPC behavior', 'compare heavy-dialog vs story-mode scenes', or wants prompt-side root-cause diagnosis. Distinct from download-campaign (which exports to disk) and wa-prod-data-query (which analyzes real-user activity)."
when_to_use: "Use when the user says: analyze the last N campaigns, review dialog quality, audit NPC behavior, regression review, per-scene analysis, agent attribution, why does the LLM X in my campaigns, do all the dialog scenes have Y, find scenes where Z is missing, per-agent breakdown. Do NOT use for: downloading/exporting single campaigns (use download-campaign); real-user activity/retention reports (use wa-prod-data-query); single-bug repros (use repro)."
arguments:
  - query
  - campaign_filter
argument-hint: "[<analysis target>] [--last N] [--min-entries M] [--since-days D]"
context: inline
allowed-tools: terminal, file
---

# wa-campaign-content-analysis — analyze existing WA campaigns in place

Canonical home for the "look at content already in Firestore and tell me what's happening" workflow. Differs from `download-campaign` (which exports to disk) and `wa-prod-data-query` (which analyzes user activity, not scene content). This skill is for **prompt / agent / content quality analysis** across many existing campaigns without copying or mutating anything.

When to use this skill vs others:

| Question class | Skill |
|---|---|
| "Why does the LLM do X in my campaigns?" | **THIS SKILL** |
| "Pull this campaign so I can read it" | `download-campaign` |
| "How many real users touched WA last week?" | `wa-prod-data-query` |
| "This specific scene has a bug" | `repro` |
| "What changed in the prompt last week?" | read git log of `$PROJECT_ROOT/prompts/` directly |

## When to fire this skill

Triggers (any one):

- User asks "review the last N campaigns with M+ scenes" or similar cross-campaign content review
- User asks "do all my dialog scenes have Y" / "audit NPC behavior" / "is X actually being applied"
- User asks "compare heavy-dialog vs story-mode scenes" / per-agent breakdown
- User asks "why are NPCs silent" / "why does the PC not speak" / "which agent is generating the response"
- After a prompt change — "verify the change actually lands in new scenes"
- **User names a specific campaign or setting ("the Danerys campaign in Meereen", "the Bran campaign", "the second Visenya run")** — see Phase 8 for the user-named-campaign lookup recipe. This is the most common intake shape and the one most likely to mis-route on a literal-name lookup. Do NOT skip to a literal `.where("name", "==", ...)` query; users often describe by setting/character rather than exact title.

## Phase 1 — Confirm environment (reuse `download-campaign` phases 1-3)

Same venv + auth + clock-skew setup as `download-campaign`. **Do not duplicate it here** — read `~/.hermes/skills/download-campaign/SKILL.md` Phases 1-3 verbatim and execute them. The firestore connection, `WORLDAI_DEV_MODE=true`, `apply_clock_skew_patch()`, and `auth.get_user_by_email("$USER@gmail.com")` boilerplate are identical.

Key environment facts:

- Project ID: `worldarchitecture-ai` (with `-ture-`), NOT `worldarchitect-ai`
- Service account: `~/serviceAccountKey.json`
- UID for $USER: `vnLp2G3m21PJL6kxcuAqmWSOtm73`
- Subcollection name is **`story`**, NOT `story_entries` (Pitfall from `download-campaign`)

## Phase 2 — Build the candidate campaign list

For "last N campaigns with ≥M scenes":

```python
db = firestore.client()
camps = db.collection("users").document(uid).collection("campaigns").stream()
camp_list = []
for c in camps:
    cid = c.id
    cd = c.to_dict() or {}
    name = cd.get("name") or cd.get("title") or "Untitled"
    # Aggregation count is the cheap+correct path; .limit(2000).stream() caps at 2000
    agg = db.collection("users").document(uid).collection("campaigns").document(cid).collection("story").count().get()
    entry_count = int(agg[0][0].value)
    if entry_count < MIN_ENTRIES:
        continue
    # Fetch last activity timestamp for sorting
    q = (db.collection("users").document(uid).collection("campaigns").document(cid)
         .collection("story").order_by("timestamp", direction=firestore.Query.DESCENDING).limit(1).stream())
    docs = list(q)
    last_ts_raw = None
    if docs:
        d = docs[0].to_dict() or {}
        last_ts_raw = d.get("timestamp") or d.get("created_at")
    camp_list.append({"id": cid, "name": name, "entries": entry_count, "last_ts": norm(last_ts_raw)})

camp_list.sort(key=lambda c: c["last_ts"], reverse=True)
last_n = camp_list[:N]
```

**`norm()` helper — Firestore timestamps are mixed types** in this DB. Some docs store `DatetimeWithNanoseconds`, others store epoch seconds as int/float. Handle both:

```python
def norm(v):
    if v is None: return 0.0
    if hasattr(v, "timestamp"):
        try: return float(v.timestamp())
        except Exception: pass
    if isinstance(v, (int, float)):
        if v > 1e12: return float(v) / 1000.0  # millis → seconds
        return float(v)
    return 0.0
```

Don't sort directly on raw values — `TypeError: '<' not supported between instances of 'int' and 'DatetimeWithNanoseconds'` fires.

**De-duplication note**: titles alone are not unique (e.g. "Bran the broken" vs "Bran the broken (ignore directive)" — these are *intentional* distinct campaigns the user is running, not copies). Only de-duplicate on `campaign_id`. The `download-campaign` Pitfall #6 (slug collision on duplicate titles) applies — but for in-place analysis you don't need to worry about it, since you're reading live data.

## Phase 3 — Per-scene extraction (the schema insight)

**Critical schema facts (verified 2026-07-13 from 2,464 gemini scenes across 10 campaigns):**

| Field | Meaning | Example values |
|---|---|---|
| `actor` | Who authored this doc | `"user"`, `"gemini"` (LLM), sometimes `"system"` |
| `mode` | **USER INTENT mode** — what the player typed | `"character"`, `"god"`, `"think"`, `"(unset)"` |
| `text` | Scene content (markdown narrative + quoted speech) | `"[CHARACTER CREATION - Review]\n\nVisenya..."` |
| `debug_info.agent_name` | **THE ACTUAL AGENT that produced the scene** | `"HeavyDialogAgent"`, `"DialogAgent"`, `"StoryModeAgent"`, `"GodModeAgent"`, `"CombatAgent"`, `"LevelUpAgent"`, `"CharacterCreationAgent"`, `"PlanningAgent"`, `"FactionManagementAgent"`, `"RewardsAgent"`, `"InfoAgent"`, `"SpicyModeAgent"`, `"CampaignUpgradeAgent"` |
| `debug_info.llm_model` | LLM model identifier | `"gemini-3.8-flash"` |
| `debug_info.system_instruction_files` | Which prompt files were loaded | (list of file basenames) |
| `full_state_updates` | State changes emitted this turn | nested dict |
| `planning_block` | Choices offered to the player | nested dict |

**THE TRAP**: `mode` field is **NOT** which agent wrote the scene. It records what *intent mode* the user's input triggered. Across 2,464 scenes in 10 long campaigns, only 3 distinct `mode` values appeared: `character` (73%), `god` (19%), `think` (7%). **Zero** scenes have `mode=dialog` or `mode=heavydialog` even though 38% of all scenes are written by `DialogAgent` or `HeavyDialogAgent`.

**Always attribute by `debug_info.agent_name`, not `mode`.** This is the single most important rule for any cross-campaign analysis.

**Schema-zero case (verified 2026-07-26 on Visenya v9, `qoQtHsU7DxZnR24VNU9w`, 412 scenes):** Some campaigns return story docs with `debug_info = {}` (empty dict — no `agent_name`, no `llm_model`, no `system_instruction_files`) AND `full_state_updates = {}` (empty dict). Symptom: every per-scene `debug_info.agent_name` lookup returns `None`, every per-agent histogram collapses to "unknown", and the typical agent distribution table is meaningless. The narrative quality is fine — the schema fields simply were never written.

Detection before per-agent analysis (cheap, mandatory):

```python
sample = next(camp.collection("story").limit(5).stream()).to_dict() or {}
has_agent_tracking = bool((sample.get("debug_info") or {}).get("agent_name"))
has_state_updates = bool(sample.get("full_state_updates"))
if not has_agent_tracking:
    print("WARN: empty debug_info — per-agent attribution unavailable")
    print("Fallback: analyze raw .txt export at ~/llm_wiki/raw/campaigns/<id8>/")
if not has_state_updates:
    print("WARN: empty full_state_updates — level / NPC timeline unavailable")
    print("Fallback: parse `Status: Lvl N` headers from raw .txt scenes")
```

When either is empty, **do not pretend per-agent findings are real.** Report "schema-zero: per-agent attribution unavailable; analyzing raw text export instead." The fallback chain is detailed in `references/visenya-v9-raw-text-analyzer.md` and the regex patterns in `references/personal-scale-challenge-pattern.md`.

## Phase 4 — Content classifiers

Common per-scene metrics:

### Quoted-speech attribution (PC vs NPC)

```python
DIALOG_PATTERNS = [
    re.compile(r'"([^"\n]{2,500})"'),   # straight double
    re.compile(r"'([^'\n]{2,500})'"),   # straight single
    re.compile(r'"([^"\n]{2,500})"'),   # curly double
    re.compile(r"'([^'\n]{2,500})'"),   # curly single
]
VERB_DIALOG_RE = re.compile(
    r"\b([A-Z][a-zA-Z'\-]+(?:\s+[A-Z][a-zA-Z'\-]+)?)\s+"
    r"(?:said|asked|replied|shouted|whispered|cried|answered|murmured|muttered|stated|declared|"
    r"exclaimed|gasped|snapped|hissed|sneered|smiled|laughed|grumbled|rejoined|added|continued|noted|"
    r"remarked|observed|responded|countered|suggested|insisted|protested|begged|pleaded|warned|"
    r"told|commanded|ordered|demanded|inquired|queried|wondered|breathed|sighed|drawled|babbled)\b"
    r"[^.!?\n]{0,80}",
    flags=re.MULTILINE,
)
NAME_COLON_RE = re.compile(r"^\s*([A-Z][a-zA-Z'\-]+(?:\s+[A-Z][a-zA-Z'\-]+)?)\s*:\s*([^\n]{2,500})",
                            flags=re.MULTILINE)
FIRST_PERSON_RE = re.compile(r"^(I |I'm |I've |I'll |I'd |My |We |Our |Me |Im |Ive |Ill |Id )",
                              re.IGNORECASE)

def count_dialog(text, pc_name, npc_names_set):
    """Return (pc_lines, npc_lines, speakers_list) for a single scene text."""
    if not text:
        return 0, 0, []
    pc_lines = npc_lines = 0
    speakers = []
    MECHANIC_LABELS = {"Intelligence Check","Wisdom Check","Charisma Check","Persuasion Check",
                       "Deception Check","Intimidation Check","Performance Check","Insight Check",
                       "Social HP","Resistance","Objective","Outcome","IMMUNITIES","DISSONANCE",
                       "IDENTITY","DIVINE BONUSES","LEVEL","DIVINE LEVERAGE","XP",
                       "Administrative Log","Strategic Note","Session Summary"}
    # 1. Quoted speech (dedupe straight+curly overlap)
    seen = set()
    quoted = []
    for pat in DIALOG_PATTERNS:
        for m in pat.finditer(text):
            line = m.group(1).strip()
            key = line[:50]
            if key in seen: continue
            seen.add(key); quoted.append(line)
    for q in quoted:
        if FIRST_PERSON_RE.match(q):
            pc_lines += 1
        else:
            npc_lines += 1
    # 2. Name-prefixed dialog ("Name: '...'")
    for m in NAME_COLON_RE.finditer(text):
        sn = m.group(1).strip()
        line_text = m.group(2).strip().strip("'\"")
        if not line_text: continue
        if sn in MECHANIC_LABELS: continue
        if pc_name and sn.lower() == pc_name.lower():
            pc_lines += 1
        else:
            npc_lines += 1
            speakers.append(sn)
    # 3. Indirect speech ("Name said that...")
    for m in VERB_DIALOG_RE.finditer(text):
        sn = m.group(1).strip()
        if sn in MECHANIC_LABELS: continue
        if pc_name and sn.lower() == pc_name.lower():
            pc_lines += 1
        else:
            npc_lines += 1
            speakers.append(sn)
    return pc_lines, npc_lines, list(set(speakers))
```

**Limitations** of this classifier (verified 2026-07-13):

- Misses *paraphrased* NPC speech (no quotes, no `Name said`). For PC-silent analysis this is fine (NPC paraphrases still get attributed via verb patterns and NAME_COLON).
- First-person quoted lines are heuristic-PC. False positives: third-person narration with self-quoted thought ("My mother always said, 'Don't trust X'"). False negatives: PC speaks in third person ("Bran Stark replies, 'I am the Three-Eyed Raven'"). For long-campaign diagnosis the false-positive rate is acceptable (median PC=0 stays 0 in any case).
- Per-game-state `pc_name` resolution is needed for NAME_COLON/VERB_DIALOG attribution. Pull from `users/{uid}/campaigns/{cid}/game_states/current_state.player_character_data.name`.

### Other useful per-scene metrics

- **Word count** — `len(text.split())`. Median words/scene per agent reveals scene depth (Combat ~345, HeavyDialog ~436, PlanningAgent ~50).
- **Distinct NPC speakers** — count unique values in `speakers` list. 0 = pure narration, 1 = single-NPC reply, 3+ = roundtable.
- **Quoted-line density** — `(pc_lines + npc_lines) / words` × 100. Low = action-only; high = dialog-heavy.
- **Scene-bucket histograms** — bucket by NPC line count `[(0,0),(1,1),(2,3),(4,7),(8,15),(16,31),(32,63),(64+)]`.

## Phase 5 — Per-agent aggregation

Group scenes by `debug_info.agent_name` (not `mode`):

```python
from collections import defaultdict
import statistics

by_agent = defaultdict(list)
for s in all_scenes:
    by_agent[s["agent"]].append(s)

for agent, sl in sorted(by_agent.items(), key=lambda kv: -len(kv[1])):
    if len(sl) < 10: continue
    n = len(sl)
    print(f"{agent}: scenes={n}  med_pc={statistics.median([s['pc_lines'] for s in sl])}  "
          f"med_npc={statistics.median([s['npc_lines'] for s in sl])}  "
          f"%pc_silent={100*sum(1 for s in sl if s['pc_lines']==0)/n:.1f}%  "
          f"%two_way={100*sum(1 for s in sl if s['pc_lines']>=1 and s['npc_lines']>=1)/n:.1f}%")
```

Typical distribution across long campaigns:

| Agent | % of scenes | Notes |
|---|---:|---|
| HeavyDialogAgent | 25-30% | "high-stakes conversations" — should have 2-way dialog; rarely does |
| GodModeAgent | 18-22% | Directive queries; 99%+ PC-silent (player asks, AI answers) |
| StoryModeAgent | 12-16% | Default narrative mode |
| DialogAgent | 10-14% | Active dialog turns (routed via `matches_game_state` or `MODE_DIALOG`) |
| LevelUpAgent | 6-10% | Level-up modal — minimal dialog |
| PlanningAgent | 5-8% | Choice generation only — 100% PC-silent, <100 words |
| CharacterCreationAgent | 3-5% | First scene only |
| CombatAgent | 2-4% | Combat — short scenes, NPC monologue for villain banter |
| FactionManagementAgent | 3-4% | Faction minigame |

**Diagnostic pattern**: if a "dialog agent" has % PC-silent > 50%, the prompt is biased toward NPC monologue and needs fixing (see `references/pc-silent-prompt-diagnosis.md`).

## Phase 6 — Verify a previously-shipped fix actually took effect

When the user asks "is the dialog fix working?" / "let me check after deploy" / "is X actually being applied" AFTER a prompt-fix PR has merged, run this verification phase BEFORE assuming the fix worked. The full verification recipe (with regex tightening, pre/post comparison, and 5-cause taxonomy) lives in `references/prompt-fix-effectiveness-verification.md`. Summary:

1. Find the merge SHA timestamp from `git log` of the changed prompt file.
2. Locate the user's most-recent campaign via `users/{uid}/campaigns` subcollection (NOT top-level `campaigns` — that's test fixtures only, per `wa-prod-data-query` Pitfall #1).
3. Stream `story` subcollection and split by merge time. Use the same `actor=gemini + mode=<relevant>` filter for both sides.
4. Compute NPC-attributed direct quotes (requires `"..."` AFTER speech verb within 80 chars — NOT just "Name said" paraphrase, which inflates counts).
5. Read 2-3 sample scenes verbatim to confirm the classifier isn't fooled by italicized action (`*Florent swallows...*`) or HUD panels.
6. If pre/post are statistically indistinguishable, the prompt fix landed but the LLM isn't following. Five causes, in priority order: wrong place in prompt, structural panels crowd, model capacity, wrong bug class fixed, cache miss on prompt update.
7. Report findings as a pre/post delta + the cause list as options for the user to choose from.

**Class-level lesson**: prompt-fix-shipped-but-LLM-ignores-it is a distinct bug class from prompt-bug-detected. Verification ≠ detection. The earlier recipe (`references/pc-silent-prompt-diagnosis.md`) covered detection; this phase covers verification.

## Phase 7 — Root-cause diagnosis → prompt files

When per-agent analysis reveals a content-quality regression (e.g. "PC is silent in 70% of dialog scenes"), the cause is almost always in one of three prompt files:

1. **`$PROJECT_ROOT/prompts/dialog_system_instruction.md`** — dialog-specific guidance. Check for NPC-only bias. Search for `player character`, `speak as the PC`, `PC voice`, `on behalf of the player` — if all zero hits, the prompt never instructs the LLM to put words in the PC's mouth.
2. **`$PROJECT_ROOT/prompts/narrative_system_instruction.md`** (L60-80) and **`narrative_lite_system_instruction.md`** (L65-80) — look for "Narrative Authority" / "Player describes / GM describes" blocks. If the GM side reserves NPC reactions without explicitly granting PC dialogue, the LLM defaults to PC-silent.
3. **`$PROJECT_ROOT/agents.py`** — check each agent's `REQUIRED_PROMPT_ORDER` for whether any PC-voice prompt slot exists. HeavyDialogAgent at L2686-2697 has none.

**Don't add backend enforcement.** Per `root-cause-first` skill discipline, fix the prompt layer first. Adding a server-side "PC must speak N times" re-prompt loop is a tail-risk: it doubles token cost on every dialog scene and the LLM will eventually find a way to bypass.

## Phase 7 — Persist findings

Three artifacts to produce:

1. **Per-scene JSONL dump** at `~/.hermes/<topic>_<date>/all_scenes_by_agent.jsonl` — one row per scene with campaign_id, agent, pc_lines, npc_lines, speakers, word count.
2. **Per-agent summary JSON** at `~/.hermes/<topic>_<date>/agent_summary.json` — aggregated medians + % silent + % two-way.
3. **Wiki source page** at `~/llm_wiki/wiki/sources/<topic>-<date>.md` — YAML frontmatter + diagnosis + verbatim sample scenes + prompt citations. Future agents can search this.

Also open a follow-up bead:

```bash
cd $HOME/your-project.com && br create "<one-line summary>" \
  --type bug --priority 2 --description "<file paths + line numbers + link to wiki page>"
```

## Pitfalls (this list IS the skill — review before running)

10. **Don't de-duplicate by title** — "Bran the broken" and "Bran the broken (ignore directive)" are intentionally distinct campaigns the user is running. De-dup only on `campaign_id`.
11. **Campaign doc `name` vs `title`** — the campaign-level document uses `title` (not `name`) for real-user campaigns. A `.where("name", "==", ...)` query returns 0 hits even when the campaign exists. See `references/campaign-doc-field-naming.md` and always read `cd.get("title") or cd.get("name")`. Verified 2026-07-15, $USER's account.
12. **User-named lookup ≠ literal title** — "the Danerys campaign in Meereen" is almost never a literal title match; use the Phase 8 three-step recipe (title pre-filter → scene-level keyword confirmation → opening-scene verification). Don't burn a clarifying menu on the user when the top match is 95% likely correct.
2. **Mixed timestamp types** — `DatetimeWithNanoseconds` vs `int` epoch vs `float` epoch-millis. Normalize via the `norm()` helper before sorting. Sorting raw fails with `TypeError: '<' not supported`.
3. **`/tmp` is sandbox-scoped per `execute_code` call** — write artifacts to `~/.hermes/<topic>_<date>/` or `~/llm_wiki/wiki/sources/` instead. Path returned by one execute_code call is gone in the next.
4. **f-string `{VAR}` in `execute_code`** — the sandbox f-string parser doesn't handle braces inside strings used inside an f-string literal. Write the wiki content via `write_file` (cleanest) or escape `{{`/`}}` everywhere.
5. **Per-campaign PC name resolution** — for accurate NAME_COLON/VERB_DIALOG attribution you need `player_character_data.name` from each campaign's `game_states/current_state`. Without it, all NAME_COLON lines fall to NPC counter and inflate the npc count. Some campaigns have None for pc_name; fall back to "unknown PC" and accept the inflated NPC count.
6. **First-person PC classifier misses third-person PC speech** — fine for PC-silent analysis (median stays 0), bad for quantifying how much PC *does* speak. If you need precise PC speech counts, sample 10-20 scenes manually.
7. **Test users pollute the data** — same as `wa-prod-data-query` Pitfall 3. For $USER's account this is mostly fine (we filter by `uid`), but if you ever broaden to multi-uid scans, apply the test-user filter (emails containing `test`, `anon`, `dev-runner`, `example.com`, `jleechantest`).
8. **Schema field drift** — story-doc schema has evolved over time. Older campaigns may use `narrative_text` instead of `text`, `created_at` instead of `timestamp`, `part` instead of `id`. Normalize field reads: `text = d.get("scene_text") or d.get("narrative_text") or d.get("text") or d.get("content")`. Same fallback chain for timestamps.
9. **User-intent "mode" vs agent "mode"** — these are TWO DIFFERENT FIELDS with the same name. `story_doc.mode` is user intent. `agents.py` also uses `MODE` class constant for agent identity. Don't conflate them.
10. **Don't de-duplicate by title** — "Bran the broken" and "Bran the broken (ignore directive)" are intentionally distinct campaigns the user is running. De-dup only on `campaign_id`.

13. **Schema-zero story docs (`debug_info = {}`, `full_state_updates = {}`)** — verified 2026-07-26 on Visenya v9. Per-agent attribution falls back to "unknown" for *every* scene; per-agent histograms and per-agent percentages become meaningless. **Detection**: run a 5-doc sample probe before the full per-agent aggregation — if `(sample.get("debug_info") or {}).get("agent_name")` returns `None` for all 5, the campaign is schema-zero. **Fallback**: analyze the raw `.txt` export at `~/llm_wiki/raw/campaigns/<id8>/<title>_<id8>.txt` (use `download-campaign` first). The raw text has `====== SCENE N ======` delimiters and `Status: Lvl N ...` headers per scene. Patterns documented in `references/personal-scale-challenge-pattern.md`. Reporting fabricated per-agent percentages (e.g. "HeavyDialogAgent: 25-30%") when the underlying `debug_info` is empty is dishonest analysis, not a number to summarize.

## Sample driver script

See `scripts/per_scene_dialog_audit.py` (in this skill) for a working end-to-end implementation:

- Pulls last N campaigns ≥ M scenes
- Streams `story` subcollection per campaign in ASC timestamp order
- Classifies each gemini scene via `count_dialog()`
- Aggregates per-agent
- Writes summary JSON + JSONL dump

## Related

- `download-campaign` — exports a single campaign (or batch) to disk. Use when the user wants to *read* campaign content; this skill is for *analyzing* content in place.
- `wa-prod-data-query` — real-user engagement/retention reports. Wrong domain (user activity, not scene content).
- `repro` — single-bug repro for one specific user-reported scene. This skill is the cross-campaign version.
- `references/pc-silent-prompt-diagnosis.md` — worked example of taking a per-agent breakdown ("PC silent 67%") and tracing it to specific prompt lines.
- `references/prompt-fix-effectiveness-verification.md` — verification recipe for AFTER a prompt fix has shipped: pre/post comparison, regex tightening (NPC-attributed quotes require `"..."` AFTER speech verb), and 5-cause taxonomy for "PR merged but LLM still not following."
- `references/personal-scale-challenge-pattern.md` — when the LLM auto-escalates to mythic-tier antagonists as the PC scales past the parity band; prompt-only fixes to preserve personal-scale challenge at high tier. Includes the five-prompt-edit recipe (Tier Compression, Consequence-Hiding Heuristic, mythic-NPC personhood, Force-a-Trade, anti-creep on major events) and the regex patterns for measuring personal-scale challenge density from raw text.
- `references/visenya-v9-raw-text-analyzer.md` — pipeline reference for analyzing a campaign whose `debug_info` is empty; walks through `/tmp/analyze_visenya_v9_v2.py` style implementation against the `download-campaign` raw `.txt` export.

## Tests

- `tests/test_dialog_classifier.py` — quote / name-colon / verb-indirect attribution, dedupe, first-person PC classification, mechanic-label skip.
- `tests/test_agent_attribution.py` — verify `debug_info.agent_name` precedence over `mode` field.
- `scripts/test_user_named_campaign_lookup.py` — Phase 8 three-step recipe (`get_campaign_title`, `title_prefilter`, `keyword_scan`, `confirm_opening_scene`) + the campaign-level `name` vs `title` field fallback + the "guess and verify, no clarification menu" output contract.

Run: `cd ~/.hermes/skills/worldarchitect/wa-campaign-content-analysis && python3 -m unittest discover -s tests && python3 scripts/test_user_named_campaign_lookup.py`

Run: `cd ~/.hermes/skills/worldarchitect/wa-campaign-content-analysis && python3 -m unittest discover -s tests`