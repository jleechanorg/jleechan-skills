import copy
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import prw_metrics  # noqa: E402

GOLDEN = Path(__file__).resolve().parent / "fixtures" / "prw" / "metrics_golden.json"


def golden():
    return json.loads(GOLDEN.read_text(encoding="utf-8"))


def blank_dist(dist):
    for key in ("p50", "p75", "p90", "p99"):
        dist[key] = None
    dist["n"] = 0


def test_render_has_seven_sections():
    out = prw_metrics.render(golden())
    headings = re.findall(r"^## ([1-7])\. ", out, flags=re.M)
    assert headings == ["1", "2", "3", "4", "5", "6", "7"]
    assert out == prw_metrics.render(golden())


def test_none_renders_unknown():
    m = golden()
    repo = m["repos"][0]
    for window in m["merge_stats"][repo].values():
        for dist in window.values():
            blank_dist(dist)
    blank_dist(m["elapsed"][repo])
    m["stage_dwell"][repo] = {}
    for key in ("requested", "readiness"):
        blank_dist(m["handoff"][repo][key])
    out = prw_metrics.render(m)
    assert "UNKNOWN" in out
    assert not re.search(r"(?<![\w.])0s\b", out)
    # every stage column is still present even with no samples
    stage_header = [ln for ln in out.splitlines() if ln.startswith("| Repository") and "Stage" in ln]
    assert stage_header and stage_header[0].count("|") >= 8


def test_header_states_cutoff_and_repos():
    m = golden()
    out = prw_metrics.render(m)
    head = out.split("## 1.")[0]
    assert m["cutoff"] in head
    for repo in m["repos"]:
        assert repo in head


def test_incomplete_repo_rendered_incomplete():
    m = golden()
    repo = m["repos"][0]
    m["health"][repo]["ok"] = False
    m["health"][repo]["error"] = "boom"
    out = prw_metrics.render(m)
    section1 = out.split("## 1.")[1].split("## 2.")[0]
    rows = [ln for ln in section1.splitlines() if repo in ln]
    assert rows and all("INCOMPLETE" in ln for ln in rows)
    assert prw_metrics.format_duration(m["merge_stats"][repo]["w2"]["all"]["p50"]) not in section1
    assert "INCOMPLETE" in out.split("## 7.")[1]
