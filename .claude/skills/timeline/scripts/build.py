#!/usr/bin/env python3
"""Build a timeline HTML from a JSON spec and print the matching text Gantt.

Usage: build.py spec.json [out.html] [--branch B] [--pr N] [--no-publish]
Spec: {title, snapshot, subtitle, branch, pr, bead, bead_db, done:[str], span,
  phases:[{title, rows:[{id, name, owner, bead, detail, start, lo, hi, label}]}],
  flow:[[group...] | "‖" | str]}
Minutes throughout. hi=null means unknown (grey). Color is chosen from hi.
Without out.html the path is /tmp/timeline/<branch>-pr<N>.html, stable across
rebuilds. --publish secret-scans the HTML, creates or edits one secret gist
(id kept in <html>.gist), shortens the gistpreview.github.io link via tinyurl, cleanuri, then spoo.me
(cached in <html>.short), and creates or updates one bead (id kept in <html>.bead).
"""
import argparse
import html
import json
import math
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

TEMPLATE = Path(__file__).resolve().parent.parent / "assets" / "template.html"
COLS = 60
UA = "timeline-skill/1.0"
SECRET_RE = re.compile(
    r"gh[pousr]_[A-Za-z0-9]{30,}|github_pat_\w{20,}|sk-[A-Za-z0-9_-]{20,}|(?:AKIA|ASIA)[0-9A-Z]{16}"
    r"|AIza[0-9A-Za-z_-]{35}|xox[abposr]-[A-Za-z0-9-]{10,}|hooks\.slack\.com/services/"
    r"|-----BEGIN [A-Z ]*PRIVATE KEY-----|eyJ[\w-]{10,}\.eyJ[\w-]{10,}\.[\w-]{10,}"
    r"|AQ\.[A-Za-z0-9_-]{30,}")


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


def out_file(spec, out_path):
    if out_path:
        return Path(out_path)
    if not spec.get("branch"):
        sys.exit("build.py: give out.html, or branch (and pr) in the spec or flags")
    stem = spec["branch"].replace("/", "-") + (f"-pr{spec['pr']}" if spec.get("pr") else "")
    return Path("/tmp/timeline") / f"{stem}.html"


def run(cmd, cwd=None):
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120, cwd=cwd)
    if r.returncode:
        raise RuntimeError(f"{' '.join(cmd[:3])}: {r.stderr.strip()[-300:]}")
    return r.stdout.strip()


def publish_gist(spec, path):
    hit = SECRET_RE.search(path.read_text())
    if hit:
        sys.exit(f"build.py: refusing to publish, secret-like token at offset {hit.start()}")
    side = Path(f"{path}.gist")
    gid = side.read_text().strip() if side.exists() else ""
    if gid:
        try:
            run(["gh", "gist", "edit", gid, "-f", path.name, str(path)])
        except RuntimeError as err:
            if "404" not in str(err) and "not found" not in str(err).lower():
                print(f"build.py: gist edit failed ({err}); keeping gist {gid}, content may be stale",
                      file=sys.stderr)
            else:
                print(f"build.py: gist {gid} is gone ({err}); creating a new gist", file=sys.stderr)
                gid = ""
    if not gid:
        url = run(["gh", "gist", "create", str(path), "-d", f"timeline: {spec['title']}"])
        gid = url.rstrip("/").rsplit("/", 1)[-1]
        side.write_text(gid + "\n")
    owner = run(["gh", "api", f"gists/{gid}", "--jq", ".owner.login"])
    return f"https://gist.github.com/{owner}/{gid}", f"https://gistpreview.github.io/?{gid}/{path.name}"


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def _redirects_to(short, target):
    """True when a HEAD on the short URL answers 3xx with Location exactly the target."""
    req = urllib.request.Request(short, method="HEAD", headers={"User-Agent": UA})
    try:
        urllib.request.build_opener(_NoRedirect).open(req, timeout=10)
    except urllib.error.HTTPError as err:
        return 300 <= err.code < 400 and err.headers.get("Location") == target
    except OSError:
        return False
    return False


def _shorten(api, target):
    q = urllib.parse.quote(target, safe="")
    if api == "tinyurl":
        req = urllib.request.Request(f"https://tinyurl.com/api-create.php?url={q}")
    elif api == "cleanuri":
        req = urllib.request.Request("https://cleanuri.com/api/v1/shorten",
                                     data=f"url={q}".encode())
    else:
        req = urllib.request.Request("https://spoo.me/", data=f"url={q}".encode(),
                                     headers={"Accept": "application/json"})
    req.add_header("User-Agent", UA)
    with urllib.request.urlopen(req, timeout=10) as resp:
        out = resp.read().decode().strip()
    if api != "tinyurl":
        out = json.loads(out).get("result_url" if api == "cleanuri" else "short_url", "")
    return re.sub(r"^http://", "https://", out)


def short_link(target, path):
    """Short URL for target, cached in <html>.short (line 1 target, line 2 short).

    Only a short URL that answers 3xx straight to target is accepted, so interstitial
    shorteners are rejected.
    """
    side = Path(f"{path}.short")
    if side.exists():
        cached = side.read_text().split()
        if len(cached) == 2 and cached[0] == target:
            return cached[1]
    for api in ("tinyurl", "cleanuri", "spoo"):
        try:
            out = _shorten(api, target)
        except (OSError, ValueError):
            continue
        if re.fullmatch(r"https://\S+", out) and _redirects_to(out, target):
            side.write_text(f"{target}\n{out}\n")
            return out
    return None


def publish_bead(spec, path, gist_url, preview):
    db = spec.get("bead_db")
    if not db:
        db = json.loads(run(["br", "info", "--json"]))["database_path"]
        top = run(["git", "rev-parse", "--show-toplevel"])
        if Path(top).resolve() not in Path(db).resolve().parents:
            raise RuntimeError(f"bead db {db} is outside this worktree; set spec bead_db")
    side = Path(f"{path}.bead")
    bid = side.read_text().strip() if side.exists() else spec.get("bead", "")
    if not bid:
        bid = json.loads(run(["br", "--db", db, "create", f"Timeline: {spec['title']}",
                              "--type", "task", "--priority", "3", "--json", "--description",
                              f"Provenance: /timeline for {path.name}; tracks the live timeline."]))
        bid = bid[0]["id"] if isinstance(bid, list) else bid["id"]
    side.write_text(bid + "\n")
    notes = (f"Timeline gist: {gist_url}\nPreview: {preview}\nHTML: {path}\n"
             f"Updated: {spec.get('snapshot', '')}")
    run(["br", "--db", db, "update", bid, "--notes", notes])
    return bid


def main(spec_path, out_path=None, branch=None, pr=None, publish=False):
    spec = json.loads(Path(spec_path).read_text())
    if branch:
        spec["branch"] = branch
    if pr:
        spec["pr"] = pr
    dest = out_file(spec, out_path)
    dest.parent.mkdir(parents=True, exist_ok=True)
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
    for _, r in rows:
        if r["unknown"]:
            r["lo"] = max(1, min(r["lo"], span - r["start"]))
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
        if not r.get("owner"):
            print(f"build.py: row {r.get('id', r['name'])} has no owner", file=sys.stderr)
        meta = " · ".join(str(r[k]) for k in ("owner", "bead", "detail") if r.get(k))
        det = f"<small>{e(meta)}</small>" if meta else ""
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
    dest.write_text("\n".join(out))

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
        who = " ".join(str(r[k]) for k in ("owner", "bead") if r.get(k))
        print(f"{(str(r.get('id', '')) + ' ' + r['name']).ljust(w)} |{bar.ljust(COLS)}| "
              f"{fmt_est(r)} {word}" + (f" [{who}]" if who else ""))
    axis = [" "] * (COLS + 8)
    for t in range(0, span + 1, 10):
        s = str(t)
        for i, ch in enumerate(s):
            axis[min(cell(t) + i, len(axis) - 1)] = ch
    print(" " * w + " |" + "".join(axis).rstrip() + " min")
    print("█ low  ░ low→high | green <10m, yellow 10–30m, red 30+m (by high), grey unknown")
    print()
    if not publish:
        print(f"HTML (local): {dest}")
    else:
        t0 = time.time()
        gist_url, preview = publish_gist(spec, dest)
        short = short_link(preview, dest)
        print(f"Timeline: {short or preview}")
        if short:
            print(f"Preview (full): {preview}")
        print(f"Gist: {gist_url}\nHTML (local): {dest}")
        t1 = time.time()
        try:
            bid = publish_bead(spec, dest, gist_url, preview)
            print(f"Bead: {bid}  (gist {t1 - t0:.1f}s, bead {time.time() - t1:.1f}s)")
        except (RuntimeError, KeyError, ValueError, subprocess.TimeoutExpired) as err:
            print(f"build.py: bead step failed, timeline still drawn: {err}", file=sys.stderr)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("spec")
    ap.add_argument("out", nargs="?")
    ap.add_argument("--branch")
    ap.add_argument("--pr")
    ap.add_argument("--publish", action="store_true", help="default; kept for compatibility")
    ap.add_argument("--no-publish", action="store_true", help="local HTML only, no gist or bead")
    a = ap.parse_args()
    main(a.spec, a.out, a.branch, a.pr, not a.no_publish)
