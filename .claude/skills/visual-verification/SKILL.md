---
name: visual-verification
description: Verify images, sprites, screenshots, and videos with tools that can inspect visual content reliably; video and animation claims require all-frame analysis (decode and account for every frame).
---

# Visual Verification Skill

## Purpose

Handle visual verification with a currently available image-capable tool. Check
the active runtime's tool catalog and the current image's accessible path before
choosing a route; platform and tool availability can change.

Before capture or reviewer dispatch, apply [Reuse and scoped follow-up](#reuse-and-scoped-follow-up).

## The Problem

Some runtime Read tools may not render PNG/JPG files on some Linux versions.
Treat that as a limitation of the specific route: probe the available image
viewers or approved analysis tools before concluding that visual inspection is
unavailable. Do not generalize a past tool failure to every Linux host or runtime.

## Working Tools

### For Image Analysis
Use an image-capable tool available in the active runtime, such as its native
image viewer or an approved image-analysis MCP when present. Do not assume a
specific provider/tool is installed; verify availability before invoking it.

### For Browser Screenshots
Use the repository's supported browser automation route and save captures to a
directory allocated through the canonical [Scratch Space skill](../scratch-space/SKILL.md).

### For Video Frames — all-frame analysis

No current model perceives video continuously; every model, including Gemini and
the realtime APIs, samples frames. Motion review is therefore **all-frame
analysis**: decode every frame and account for each one yourself.

1. **Provenance.** Record the media SHA-256 (and the transcoded file's hash, if
   different), duration, frame rate, decoded frame count and presentation
   timestamps (`ffprobe -show_entries stream=r_frame_rate,nb_frames:format=duration`).
   Work in a directory from the [Scratch Space skill](../scratch-space/SKILL.md).
2. **Decode everything.** `ffmpeg -i clip.mp4 -vsync 0 frames/f%04d.png`. Confirm
   the file count equals the probed frame count.
3. **Partition mechanically.** Diff each frame against the previous one with a
   low threshold (for example, luma change >12 on >50 px). Consecutive frames
   above the threshold form *change runs*; the rest form *still runs*. Never
   raise the threshold to shrink the review. Uniform timestamps and the diff
   series also expose dropped or duplicated frames and cadence problems.
4. **View every change frame, in order, at readable detail.**
   - Overview: labelled sheets of at most 6 consecutive frames, each at least
     640 px wide, stamped with frame index and timestamp.
   - Moving subjects: full-resolution crops that follow the subject (track it by
     frame difference), about 12 frames per sheet.
   - Gait: 2× zooms on the feet and shadow for every travel direction. Check
     foot contact versus floating, sliding of a planted foot, passing poses held
     while the body translates, facing versus direction of travel, depth order,
     and overlap with props and characters.
   - Inspect suspicious frames at full resolution before deciding.
5. **Cover still runs.** A still run is mechanically proven unchanged. View its
   first frame and the full-resolution frames on both sides of every change
   point (for example, dialogue advances and UI changes). Read text and UI state
   at those boundaries.
6. **Separate layers.** Tell game UI apart from evidence overlays such as
   caption bars, provenance boxes and the OS cursor. Label any claim that comes
   from reading code rather than from pixels.
7. **Coverage manifest.** Keep running notes per frame range. Every frame index
   must be either a viewed change frame or inside a still run covered by viewed
   boundaries. Reconcile the manifest against the decoded count, with no gaps.
8. **Long clips.** Split the clip into disjoint contiguous ranges for cheap
   parallel lanes, with boundary frames shared by adjacent lanes. The parent
   integrates the findings and reconciles the manifest.
9. **Report.** Give each finding with its frame indices and timestamps and a
   severity. Consider whether capture cadence explains an apparent defect before
   blaming the product. Label the method "all-frame analysis"; do not claim
   subjective "feel". A sampled video-model pass (for example Gemini at its fps
   cap) is supplementary only; record the sampling it actually used. If anything
   could not be decoded or viewed, state the exact covered ranges.
10. In `/es` or `/er`, bind visual claims to the media SHA, frame rate, frame
    count, coverage manifest and the inspected images.

## Reuse and scoped follow-up

Before dispatch, apply [pr-lifecycle's SHA-binding rule](../pr-lifecycle/SKILL.md#sha-binding-rule-critical--applies-to-every-gate-in-this-chain)
to existing independent visual verdicts and artifact receipts. Keep original
reviewer, verdict, reviewed SHA, artifact hashes, observed ranges and limitations;
record applicability in the existing review record, not a new ledger.

- **Unchanged clip and claims:** when the complete delta and provenance show the
  prior coverage still applies, reuse it with zero reviewer redispatch. A new
  phase, receipt location or candidate hash alone does not require another viewing.
- **Ending-only change:** after verifying the earlier footage and its claims are
  unchanged, retain their valid coverage and request independent inspection only
  of the changed ending and enough preceding context to judge the transition and
  resulting state. Record exact source/output ranges and the retained receipt.
  If the change affects earlier meaning, timing, continuity or provenance, expand
  review to every affected range; uncertain applicability is not unchanged proof.
- **New or rejected footage:** new captures, changed cast/characters, changed
  behavior or unresolved rejection findings need affected independent review.
  Inspect new footage in full for its declared claims; an ending sample cannot
  approve a new capture. Preserve [continuous-source integrity](../evidence-standards/SKILL.md#continuous-video-only--slideshows-are-forbidden)
  and any stricter domain or repository proof.

Before each necessary visual dispatch, assign the artifact, claim, exact time/frame
ranges (all new frames and boundary overlap), required before/after context and output
fields: observed content, claim verdict, limitations and artifact/range references.
Ranges scope visual follow-up, not source approval: never combine partial source
readers into a full-scope vote. Existing lifecycle seat eligibility, independence,
quorum and authority remain unchanged.

The coordinator computes and fills mechanical receipt fields from retained primary
artifacts: hashes, frame indices and presentation timestamps (PTS), source/output
mapping and links. Attribute these as coordinator measurements, not reviewer
observations. Repair missing bookkeeping without redispatch when existing evidence
establishes the facts; retain the original verdict and clocks. Missing visual
judgment, ambiguous provenance or an unmet eligibility/deadline requirement is not
bookkeeping and cannot be repaired into approval by the coordinator. Request only
the missing or affected independent judgment through the governing review route.

## Verification Rule — FAIL LOUDLY

If visual verification remains unavailable after probing supported routes, state
the exact route(s) attempted and the limitation. Continue other authorized work;
do not infer that one unavailable tool means all visual inspection is impossible.

Bad behavior (DO NOT DO):
- "The sprite looks good based on pixel values" (you can't see it)
- Analyzing RGB numbers and claiming to assess visual quality
- Saying "I can see it" when Read returns null
- Using subagent pixel analysis as a substitute for actually seeing

Correct behavior:
- Use an available visual-capable tool and identify the method used.
- If it fails, try another supported route available in the active runtime.
- If all supported routes fail, report the exact limitation and leave the visual claim unproven.

## When Assessing Sprites/Game Graphics

1. Capture screenshot or locate sprite file
2. Use a visual-capable tool that is currently available.
3. Report observed content and any tool-derived analysis separately.
4. If no supported route can inspect the image, report that limitation without making a visual claim.

## Sprite Quality Claims

For sprite quality evaluations, use `/sprite-eval` when its current definition is available. Do not make sprite quality claims without actual visual inspection through a working tool.
