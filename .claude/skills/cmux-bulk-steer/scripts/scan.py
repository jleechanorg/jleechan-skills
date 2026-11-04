#!/usr/bin/env python3
"""cmux-bulk-steer — ZFC mechanical 10,000-word fleet capture (Phase 1).

Zero-Framework Cognition (/zfc) compliant:
- Contains ZERO regex/keyword semantic classifiers.
- Performs only deterministic I/O: queries `cmux tree --all --json` and
  `cmux top --all --flat`, captures `--scrollback --lines 4000` for every
  terminal surface, slices the last 10,000 words (preserving line breaks),
  and writes `/tmp/cmux_fleet_<ts>/ws_<ws_id>_sf_<sf_id>.txt` plus
  `manifest.json`.
- Model-owned semantic classification and cross-surface deduplication belong
  in Phase 2 (/parallel subagents reading the 10k-word files).
"""
from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import subprocess
import sys
from typing import Any

SCROLLBACK_LINES = 4000
DEFAULT_MAX_WORDS = 10000
TAIL_PREVIEW_LINES = 10


def truncate_to_last_n_words(
    text: str, max_words: int = DEFAULT_MAX_WORDS
) -> tuple[str, int, int]:
    """Keep the trailing lines of `text` up to `max_words` words, preserving line breaks."""
    non_empty_lines = [line.rstrip() for line in text.splitlines() if line.strip()]
    if not non_empty_lines:
        return "", 0, 0

    line_word_counts = [len(line.split()) for line in non_empty_lines]
    total_words = sum(line_word_counts)
    if total_words <= max_words:
        return "\n".join(non_empty_lines), total_words, total_words

    kept_lines: list[str] = []
    captured_words = 0
    for line, count in zip(reversed(non_empty_lines), reversed(line_word_counts)):
        if kept_lines and captured_words + count > max_words:
            break
        if not kept_lines and count > max_words:
            words = line.split()[-max_words:]
            kept_lines.append(" ".join(words))
            captured_words = len(words)
            break
        kept_lines.append(line)
        captured_words += count

    kept_lines.reverse()
    return "\n".join(kept_lines), total_words, captured_words


def _ref_suffix(ref: str) -> str:
    return ref.split(":", 1)[1] if ":" in ref else ref


def list_terminal_surfaces(tree_data: dict[str, Any]) -> list[dict[str, str]]:
    """Extract terminal surfaces from `cmux tree --all --json` without regexes."""
    out: list[dict[str, str]] = []
    for window in tree_data.get("windows", []):
        for workspace in window.get("workspaces", []):
            ws_ref = str(workspace.get("ref") or "")
            ws_title = str(workspace.get("title") or ws_ref)
            for pane in workspace.get("panes", []):
                for surface in pane.get("surfaces", []):
                    sf_type = str(surface.get("type") or "")
                    if sf_type != "terminal" or surface.get("is_browser_surface"):
                        continue
                    sf_ref = str(surface.get("ref") or "")
                    sf_title = str(surface.get("title") or "")
                    if ws_ref and sf_ref:
                        out.append(
                            {
                                "workspace": ws_title,
                                "workspace_ref": ws_ref,
                                "surface": sf_ref,
                                "surface_ref": sf_ref,
                                "surface_title": sf_title,
                            }
                        )
    return out


def parse_top_cpu_by_surface(top_output: str) -> dict[str, float]:
    """Extract deterministic CPU% per surface ref from `cmux top --all --flat`."""
    cpu_by_surface: dict[str, float] = {}
    for raw_line in top_output.splitlines():
        parts = raw_line.split("\t")
        if len(parts) >= 5 and parts[3] == "surface":
            try:
                cpu_by_surface[parts[4]] = float(parts[0])
            except ValueError:
                continue
    return cpu_by_surface


def load_pi_sessions_by_cwd(home_dir: Path | None = None) -> dict[str, Path]:
    """Map resolved and raw cwd paths to the newest ~/.pi/agent/sessions/*/*.jsonl file."""
    base_home = home_dir or Path.home()
    sessions_root = base_home / ".pi" / "agent" / "sessions"
    if not sessions_root.is_dir():
        return {}
    by_cwd: dict[str, Path] = {}
    session_files = sorted(
        sessions_root.glob("*/*.jsonl"), key=lambda p: p.stat().st_mtime
    )
    for session_path in session_files:
        try:
            with session_path.open(encoding="utf-8") as fh:
                first_line = fh.readline().strip()
            if not first_line:
                continue
            header = json.loads(first_line)
            cwd = header.get("cwd")
            if isinstance(cwd, str) and cwd.strip():
                by_cwd[cwd.strip()] = session_path
                by_cwd[str(Path(cwd.strip()).expanduser().resolve())] = session_path
        except (OSError, ValueError, KeyError):
            continue
    return by_cwd


def match_pi_session_for_tail(
    tail_lines: list[str],
    by_cwd: dict[str, Path],
    home_dir: Path | None = None,
) -> Path | None:
    """Match a pi TUI footer cwd line (`~/path (branch)` or `/path (branch)`) to its JSONL session."""
    if not by_cwd or not tail_lines:
        return None
    base_home = home_dir or Path.home()
    has_tui_rule = any("───" in line for line in tail_lines[-8:])
    for raw_line in reversed(tail_lines[-8:]):
        stripped = raw_line.strip()
        if not (stripped.startswith("~/") or stripped.startswith("/")):
            continue
        if " (" not in stripped and not has_tui_rule:
            continue
        raw_path = stripped.split(" (", 1)[0].strip()
        if raw_path.startswith("~/"):
            candidate = base_home / raw_path[2:]
        else:
            candidate = Path(raw_path)
        for key in (raw_path, str(candidate), str(candidate.resolve())):
            if key in by_cwd:
                return by_cwd[key]
    return None


def render_pi_session_transcript(jsonl_path: Path) -> str:
    """Extract chronological message text/thinking/toolCall entries from a pi session JSONL."""
    rendered_lines: list[str] = []
    try:
        with jsonl_path.open(encoding="utf-8") as fh:
            for raw_line in fh:
                raw_line = raw_line.strip()
                if not raw_line:
                    continue
                try:
                    entry = json.loads(raw_line)
                except ValueError:
                    continue
                if entry.get("type") != "message":
                    continue
                msg = entry.get("message") or {}
                role = str(msg.get("role") or "unknown")
                content = msg.get("content")
                if isinstance(content, str) and content.strip():
                    rendered_lines.append(f"[{role}] {content.strip()}")
                elif isinstance(content, list):
                    for block in content:
                        if not isinstance(block, dict):
                            continue
                        btype = block.get("type")
                        if btype == "text":
                            text_val = str(block.get("text") or "").strip()
                            if text_val:
                                rendered_lines.append(f"[{role}] {text_val}")
                        elif btype == "thinking":
                            think_val = str(block.get("thinking") or "").strip()
                            if think_val:
                                rendered_lines.append(f"[{role}:thinking] {think_val}")
                        elif btype == "toolCall":
                            name = str(block.get("name") or "")
                            args = json.dumps(
                                block.get("arguments") or {}, ensure_ascii=False
                            )
                            rendered_lines.append(f"[{role}:toolCall {name}] {args}")
    except OSError:
        return ""
    return "\n".join(rendered_lines)


def capture_fleet(
    out_dir: Path,
    max_words: int = DEFAULT_MAX_WORDS,
    scrollback_lines: int = SCROLLBACK_LINES,
    with_gh: bool = False,
    readonly: bool = False,
    home_dir: Path | None = None,
) -> dict[str, Any]:
    """Capture 10k-word scrollback files and write `manifest.json`."""
    out_dir.mkdir(parents=True, exist_ok=True)
    pi_sessions_by_cwd = load_pi_sessions_by_cwd(home_dir=home_dir)

    tree_proc = subprocess.run(
        ["cmux", "tree", "--all", "--json"],
        capture_output=True,
        text=True,
        check=False,
    )
    tree_data = json.loads(tree_proc.stdout) if tree_proc.stdout.strip() else {"windows": []}

    top_proc = subprocess.run(
        ["cmux", "top", "--all", "--flat"],
        capture_output=True,
        text=True,
        check=False,
    )
    (out_dir / "top_flat.tsv").write_text(top_proc.stdout or "", encoding="utf-8")
    cpu_by_surface = parse_top_cpu_by_surface(top_proc.stdout or "")

    surfaces_manifest: list[dict[str, Any]] = []
    for item in list_terminal_surfaces(tree_data):
        ws_ref = item["workspace_ref"]
        sf_ref = item["surface_ref"]
        cap_proc = subprocess.run(
            [
                "cmux",
                "capture-pane",
                "--workspace",
                ws_ref,
                "--surface",
                sf_ref,
                "--scrollback",
                "--lines",
                str(scrollback_lines),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        combined_err = (cap_proc.stderr or "") + (cap_proc.stdout or "")
        if cap_proc.returncode != 0 or "Surface is not a terminal" in combined_err:
            continue

        raw_stdout = cap_proc.stdout or ""
        non_empty_lines = [line.rstrip() for line in raw_stdout.splitlines() if line.strip()]
        truncated_text, total_words, captured_words = truncate_to_last_n_words(
            raw_stdout, max_words=max_words
        )
        pi_session_jsonl: str | None = None
        if captured_words < max_words:
            matched_jsonl = match_pi_session_for_tail(
                non_empty_lines[-TAIL_PREVIEW_LINES:],
                pi_sessions_by_cwd,
                home_dir=home_dir,
            )
            if matched_jsonl is not None:
                pi_transcript = render_pi_session_transcript(matched_jsonl)
                if pi_transcript:
                    pi_session_jsonl = str(matched_jsonl.resolve())
                    remaining_budget = max(1, max_words - captured_words - 12)
                    pi_slice, pi_total_words, _ = truncate_to_last_n_words(
                        pi_transcript, max_words=remaining_budget
                    )
                    truncated_text = (
                        f"=== PI SESSION TRANSCRIPT ({pi_session_jsonl}) ===\n"
                        f"{pi_slice}\n\n"
                        f"=== LIVE TERMINAL PANE ===\n"
                        f"{truncated_text}"
                    )
                    total_words = pi_total_words + total_words
                    captured_words = len(truncated_text.split())
                    non_empty_lines = [
                        line.rstrip()
                        for line in truncated_text.splitlines()
                        if line.strip()
                    ]

        ws_id = _ref_suffix(ws_ref)
        sf_id = _ref_suffix(sf_ref)
        file_10k = out_dir / f"ws_{ws_id}_sf_{sf_id}.txt"
        file_10k.write_text(truncated_text + ("\n" if truncated_text else ""), encoding="utf-8")

        surfaces_manifest.append(
            {
                "workspace": item["workspace"],
                "workspace_ref": ws_ref,
                "surface": sf_ref,
                "surface_ref": sf_ref,
                "surface_title": item["surface_title"],
                "cpu_percent": cpu_by_surface.get(sf_ref, 0.0),
                "file_10k": str(file_10k.resolve()),
                "pi_session_jsonl": pi_session_jsonl,
                "total_words": total_words,
                "captured_words": captured_words,
                "lines_read": len(non_empty_lines),
                "tail_lines": non_empty_lines[-TAIL_PREVIEW_LINES:],
            }
        )

    gh_prs_file: str | None = None
    if with_gh:
        gh_proc = subprocess.run(
            [
                "gh",
                "pr",
                "list",
                "--state",
                "open",
                "--limit",
                "50",
                "--json",
                "number,title,headRefName,headRefOid,isDraft,mergeable,mergeStateStatus,updatedAt",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if gh_proc.returncode == 0 and gh_proc.stdout.strip():
            gh_path = out_dir / "gh_prs.json"
            gh_path.write_text(gh_proc.stdout, encoding="utf-8")
            gh_prs_file = str(gh_path.resolve())

    manifest: dict[str, Any] = {
        "out_dir": str(out_dir.resolve()),
        "mode": "readonly" if readonly else "steer-capable",
        "scrollback_lines": scrollback_lines,
        "max_words": max_words,
        "surface_count": len(surfaces_manifest),
        "gh_prs_file": gh_prs_file,
        "surfaces": surfaces_manifest,
    }
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(
        description="ZFC mechanical 10,000-word fleet capture for cmux-bulk-steer."
    )
    parser.add_argument(
        "--out-dir",
        "--output-dir",
        dest="out_dir",
        type=Path,
        default=None,
        help="Output directory for ws_*_sf_*.txt and manifest.json (default: /tmp/cmux_fleet_<HHMMSS>).",
    )
    parser.add_argument(
        "--max-words",
        type=int,
        default=DEFAULT_MAX_WORDS,
        help="Maximum trailing words to save per terminal surface (default: 10000).",
    )
    parser.add_argument(
        "--scrollback-lines",
        "--lines",
        dest="scrollback_lines",
        type=int,
        default=SCROLLBACK_LINES,
        help="Scrollback lines passed to cmux capture-pane (default: 4000).",
    )
    parser.add_argument(
        "--with-gh",
        action="store_true",
        help="Also capture open GitHub PR metadata to <out-dir>/gh_prs.json.",
    )
    parser.add_argument(
        "--readonly",
        action="store_true",
        help=(
            "Record a read-only audit sweep in manifest.json ('mode': 'readonly'). "
            "The collector never mutates a surface; this flag is the provenance marker "
            "for runs that must not steer (see SKILL.md § Read-only mode)."
        ),
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print full manifest JSON to stdout.",
    )
    args = parser.parse_args()

    out_dir = args.out_dir or Path(f"/tmp/cmux_fleet_{datetime.now().strftime('%H%M%S')}")
    manifest = capture_fleet(
        out_dir=out_dir,
        max_words=args.max_words,
        scrollback_lines=args.scrollback_lines,
        with_gh=args.with_gh,
        readonly=args.readonly,
    )

    if args.json:
        print(json.dumps(manifest, indent=2))
        return 0

    print(
        f"out_dir={manifest['out_dir']} mode={manifest['mode']} terminals={manifest['surface_count']} "
        f"manifest={Path(manifest['out_dir']) / 'manifest.json'}"
    )
    for row in manifest["surfaces"]:
        last_line = row["tail_lines"][-1][:90] if row["tail_lines"] else "<empty>"
        print(
            f"  [{row['workspace']} | {row['workspace_ref']} / {row['surface_ref']}] "
            f"words={row['captured_words']}/{row['total_words']} "
            f"lines={row['lines_read']} cpu={row['cpu_percent']:.1f}% "
            f"file={row['file_10k']} | tail={last_line}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
