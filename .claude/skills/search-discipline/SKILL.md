---
name: search-discipline
description: "Scope recursive searches so they cannot pin a CPU core for tens of minutes. Use before any find|xargs grep, recursive grep, or history lookup over agent transcript trees (~/.claude/projects, ~/.pi/agent/sessions, ~/.codex/sessions, ~/.hermes), and whenever a machine is reported as CPU-saturated but no single lane looks busy."
---

# Search discipline — never grep the transcript corpus recursively

## The failure this exists for

On 2026-11-02 this Mac ran at **0.0% CPU idle with load average 244**, and the top consumers were not agent
lanes doing work. They were recursive greps over the agent transcript tree:

```
cd ~/.claude/projects && find . -name '*.jsonl' … | xargs grep -l -E 'PASSWORD|TEST_P…'   → ~88% of a core, 50+ min
rtk-wrapped grep over the same tree                                                       → ~57% of a core, 21+ min
grep -l "out-parameter" ~/.claude/projects/*/*.jsonl ~/.claude-wa-api/… ~/.pi/agent/…      → same shape
```

Measured corpus size: **23 GB across 13,750 JSONL files**.

`find … | xargs grep` spawns a fresh `grep` per file, so a "quick history lookup" becomes one core pinned for the
better part of an hour. Downstream damage that was observed:

- A lane's own CPU-admission gate (needs 10% idle) read `0.2%`–`0.73%` and refused to launch for **over an hour**.
- Another lane explicitly wrote *"the Mac has fallen below the required CPU headroom for launching another browser"*.
- `ui cutover` had already decided its grep was *"moot now that the Keychain account works"* and never killed it —
  so 88% of a core burned on a search whose answer was no longer wanted.

## The rule

**Never run a recursive search across a whole transcript corpus.** That tree is append-only, unbounded, and mostly
irrelevant to any single question.

Instead, in order of preference:

1. **Ask the source of truth instead of the transcript.** GitHub (`gh pr view`, `gh api`), the bead store (`br`), the
   roadmap docs, or the live service. Transcripts are a last resort.
2. **Target one session file.** If you know which session, read `…/sessions/<dir>/<file>.jsonl` directly, or the
   newest one for a cwd: `ls -t ~/.claude/projects/<slug>/*.jsonl | head -1`.
3. **Bounded scope when you must sweep.** Always add a time window AND a size cap, and prefer `--include`:
   ```bash
   find ~/.claude/projects/<slug> -name '*.jsonl' -newermt '2 hours ago' -size -5M -print0 \
     | head -50 | xargs -0 -n1 -P2 grep -l -- "$pattern"
   ```
   `-newermt`, `-size`, and a hard `head` are not optional. `-P2` caps parallelism so you cannot saturate the box.
4. **Kill what you abandoned.** If you decided a search is moot, stop it in the same turn — do not leave it running
   in the background. A backgrounded grep with no owner is invisible to you and visible to everyone else as CPU.

## Check before you launch

```bash
# corpus size — if this is GB-scale, do not recurse into it
du -sh ~/.claude/projects ~/.pi/agent/sessions ~/.codex/sessions 2>/dev/null
find ~/.claude/projects -name '*.jsonl' | wc -l

# is the box already saturated? a search that would have been fine alone is not fine now
top -l 2 -n 0 -s 2 | grep 'CPU usage' | tail -1     # macOS
top -bn2 -d1 | grep '%Cpu' | tail -1                # Linux
```

## Diagnosing "the machine is busy but no lane looks busy"

When CPU is saturated and every agent surface reads idle, attribute before you act. `cmux top --flat` can report
`0.0` for every row including `total`, so do not trust it:

```bash
ps -Ao pid,pcpu,etime,tty,args -r | head -15          # find hot pids AND their tty
lsof -p <pid> | awk '$4=="cwd"{print $9}'             # what it is working on
cmux tree --all --json                                # maps surface_ref -> tty
```

A `grep`, `xargs`, `find`, or `rtk` process at high CPU with a cwd under a transcript tree is this failure, not real
work. Name it, then stop it or scope it — do not "move the lane", because the search is not what the lane is for.

## Anti-patterns

- `grep -r pattern ~/.claude` or any unbounded recurse into a sessions tree.
- `find … | xargs grep` over thousands of files with no `-newermt`, `-size`, or `head`.
- Leaving a backgrounded search running after you decide its answer is moot.
- Recommending a lane move (`/lm`, `/cc`) to fix CPU that a local abandoned grep is consuming — moving the lane does
  not move the grep, and the grep's corpus does not exist on the remote host.
- Trusting a `0.0` CPU column as proof of idleness when the `total` row also reads `0.0`.
