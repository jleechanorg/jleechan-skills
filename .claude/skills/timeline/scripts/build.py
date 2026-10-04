#!/usr/bin/env python3
"""Build a timeline HTML from a JSON spec and print the matching text Gantt.

Usage: build.py spec.json out.html
Spec: {title, snapshot, subtitle, done:[str], span, phases:[{title, rows:[
  {id, name, detail, start, lo, hi, label}]}], flow:[[group...] | "‖" | str]}
Minutes throughout. hi=null means unknown (grey). Color is chosen from hi.
"""
import html
import json
import math
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

TEMPLATE = Path(__file__).resolve().parent.parent / "assets" / "template.html"
COLS = 60


def color(hi):
    if hi is None:
        return "grey", "unk"
    return ("green", "green") if hi < 10 else ("yellow", "yellow") if hi <= 30 else ("red", "red")


def fmt_est(r):
    if r.get("label"):
        return r["label"]
    lo, hi = r["lo"], r.get("hi")
    if r.get("unknown"):
        return "unknown"
    if hi is None:
        return f"{lo}m+"
    return f"{lo}m" if hi == lo else f"{lo}–{hi}m"


def finish_text(snapshot, mins):
    m = re.match(r"(\d{4}-\d\d-\d\d)[ T~]+(\d\d:\d\d)\s*(\S*)", snapshot or "")
    if not m:
        return None
    t = datetime.strptime(f"{m[1]} {m[2]}", "%Y-%m-%d %H:%M") + timedelta(minutes=mins)
    return t.strftime("%H:%M ") + m[3]


def main(spec_path, out_path):
    spec = json.loads(Path(spec_path).read_text())
    rows = [(p["title"], r) for p in spec["phases"] for r in p["rows"]]
    for _, r in rows:
        # lo: null = duration unknown; draw a short grey stub, exclude from totals.
        r["unknown"] = r["lo"] is None
        if r["unknown"]:
            r["lo"], r["hi"] = 10, None
        r.setdefault("hi", r["lo"])
    known = [r for _, r in rows if not r["unknown"]] or [r for _, r in rows]
    lo_end = max(r["start"] + r["lo"] for r in known)
    hi_end = max(r["start"] + (r["hi"] if r["hi"] is not None else r["lo"]) for r in known)
    span = spec.get("span") or max(10, int(math.ceil(hi_end / 10.0) * 10))
    est = f"≈ {lo_end}–{hi_end} min" if hi_end != lo_end else f"≈ {lo_end} min"
    f_lo, f_hi = finish_text(spec.get("snapshot"), lo_end), finish_text(spec.get("snapshot"), hi_end)
    finish = f" → finish ~{f_lo}–{f_hi}" if f_lo else ""
    head = f"Snapshot {spec.get('snapshot', '')} · estimate {est}{finish}"

    css = re.search(r"<style>(.*?)</style>", TEMPLATE.read_text(), re.S)[1]
    css = re.sub(r"calc\(100%/\d+\)", f"calc(100%/{span // 10})", css)
    e = html.escape
    pct = lambda v: f"{100.0 * v / span:.2f}%"
    out = [f'<!doctype html><html><head><meta charset="utf-8"><title>{e(spec["title"])}</title>',
           f"<style>{css}</style></head><body>", f"<h1>{e(spec['title'])}</h1>",
           f'<div class="sub">{e(head)}' + (f" · {e(spec['subtitle'])}" if spec.get("subtitle") else "") + "</div>"]
    if spec.get("done"):
        items = "".join(f"<div>✓ {e(d)}</div>" for d in spec["done"])
        out.append(f'<div class="status"><div class="card"><b>Done</b>{items}</div></div>')
    out.append('<div class="gantt">')
    last = None
    for ph, r in rows:
        if ph != last:
            out.append(f'<div class="phase">{e(ph)}</div>')
            last = ph
        _, var = color(r["hi"])
        det = f"<small>{e(r['detail'])}</small>" if r.get("detail") else ""
        out.append(f'<div class="lbl">{e(str(r.get("id", "")))} · {e(r["name"])}{det}</div>')
        bar = (f'<div class="bar" style="left:{pct(r["start"])};width:{pct(r["lo"])};'
               f'background:var(--{var})">{e(fmt_est(r))}</div>')
        if r["hi"] is not None and r["hi"] > r["lo"]:
            bar += (f'<div class="ext" style="left:{pct(r["start"] + r["lo"])};'
                    f'width:{pct(r["hi"] - r["lo"])};background:var(--{var})"></div>')
        out.append(f'<div class="track">{bar}</div>')
    out.append("</div>")
    ticks = "".join(f"<span>{t}{' min' if t == span else ''}</span>" for t in range(0, span + 1, 10))
    out.append(f'<div class="axis"><div></div><div class="ticks">{ticks}</div></div>')
    sw = lambda v, t: f'<span><span class="sw" style="background:var(--{v})"></span>{t}</span>'
    out.append('<div class="legend">' + sw("green", "&lt; 10 min") + sw("yellow", "10–30 min")
               + sw("red", "30+ min") + sw("unk", "unknown")
               + "<span>color = HIGH estimate · solid = low estimate, faded = up to high</span>"
               + "<span>0 = snapshot time</span></div>")
    if spec.get("flow"):
        out.append('<div class="flow">')
        for g in spec["flow"]:
            if isinstance(g, list):
                out.append('<div class="par">' + "".join(f'<div class="node">{e(n)}</div>' for n in g) + "</div>")
            elif g in ("→", "‖"):
                out.append(f'<span class="arr">{g}</span>')
            else:
                out.append(f'<div class="node">{e(g)}</div>')
        out.append("</div>")
    out.append("</body></html>")
    Path(out_path).write_text("\n".join(out))

    # Text Gantt (same rows, axis, totals)
    w = max(len(f"{r.get('id', '')} {r['name']}") for _, r in rows)
    cell = lambda v: int(round(v * COLS / span))
    print(f"{spec['title']}\n{head}\n")
    last = None
    for ph, r in rows:
        if ph != last:
            print(f"-- {ph}")
            last = ph
        a, b = cell(r["start"]), cell(r["start"] + r["lo"])
        c = cell(r["start"] + r["hi"]) if r["hi"] is not None else b
        b = max(b, a + 1)
        bar = " " * a + "█" * (b - a) + "░" * max(0, c - b)
        word = color(r["hi"])[0]
        print(f"{(str(r.get('id', '')) + ' ' + r['name']).ljust(w)} |{bar.ljust(COLS)}| {fmt_est(r)} {word}")
    axis = [" "] * (COLS + 8)
    for t in range(0, span + 1, 10):
        s = str(t)
        for i, ch in enumerate(s):
            axis[min(cell(t) + i, len(axis) - 1)] = ch
    print(" " * w + " |" + "".join(axis).rstrip() + " min")
    print("█ low  ░ low→high | green <10m, yellow 10–30m, red 30+m (by high), grey unknown")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
