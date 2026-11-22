"""Local usage feeds: loading, attribution to PRs, rendering, and publishing a non-dashboard path."""

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import prw_metrics  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "prw"
CUTOFF = "2026-11-14T00:00:00Z"
REPO_A, REPO_B = "example-org/repo-a", "example-org/repo-b"
REAL_RUN = subprocess.run


def feed(machine="machine-1", generated_at="2026-11-13T20:00:00Z", sessions=()):
    return {"schema": "prw-local-usage.v1", "machine": machine, "generated_at": generated_at,
            "window": {"start": "2026-10-31T00:00:00Z", "end": generated_at},
            "idle_gap_sec": 300, "sessions": list(sessions)}


def session(branch="feature/x", repo=REPO_A, first="2026-11-10T00:00:00Z", last="2026-11-10T01:00:00Z",
            active=600, tool="claude", output=10, sid="s"):
    return {"tool": tool, "session_id": sid, "repo": repo, "branch": branch, "first_at": first,
            "last_at": last, "active_sec": active,
            "models": {"model-x": {"input": 1, "output": output, "cache_read": 2, "cache_write": 3}}}


def pr(repo, number, branch, created="2026-11-01T00:00:00Z"):
    return {"repo": repo, "number": number, "branch": branch, "created_at": created, "url": "u",
            "title": "t", "author": "a", "merged_at": None, "closed_at": None, "status": None,
            "timeline_complete": True, "events": [], "attempts": []}


def agg(records, feeds, problems=()):
    health = {REPO_A: {"ok": True}, REPO_B: {"ok": True}}
    return prw_metrics.aggregate(records, health, {"labels": {}, "status": "ABSENT"}, CUTOFF,
                                 usage=feeds, usage_problems=list(problems))["usage"]


def write(path, doc):
    Path(path).write_text(doc if isinstance(doc, str) else json.dumps(doc), encoding="utf-8")


# --- loading ---

def test_load_skips_bad_feeds_and_reports_problems(tmp_path):
    write(tmp_path / "good.json", feed("m-good", sessions=[session()]))
    write(tmp_path / "broken.json", "{not json")
    write(tmp_path / "other.json", dict(feed("m-other"), schema="something.v9"))
    incomplete = feed("m-incomplete")
    del incomplete["sessions"]
    write(tmp_path / "incomplete.json", incomplete)
    write(tmp_path / "list.json", [1, 2])
    feeds, problems = prw_metrics.load_usage_feeds([str(tmp_path)])
    assert [f["machine"] for f in feeds] == ["m-good"]
    assert len(problems) == 4
    for name in ("broken.json", "other.json", "incomplete.json", "list.json"):
        assert any(name in p for p in problems)


def test_load_accepts_file_path_and_reports_missing_path(tmp_path):
    write(tmp_path / "one.json", feed("m-one"))
    feeds, problems = prw_metrics.load_usage_feeds([str(tmp_path / "one.json"), str(tmp_path / "nope")])
    assert [f["machine"] for f in feeds] == ["m-one"] and len(problems) == 1


def test_load_drops_invalid_sessions_but_keeps_feed(tmp_path):
    bad = session()
    del bad["active_sec"]
    write(tmp_path / "f.json", feed("m", sessions=[session(), bad, "junk"]))
    feeds, problems = prw_metrics.load_usage_feeds([str(tmp_path)])
    assert len(feeds[0]["sessions"]) == 1 and len(problems) == 1


def test_load_keeps_newest_feed_per_machine(tmp_path):
    write(tmp_path / "a.json", feed("m", generated_at="2026-11-12T00:00:00Z"))
    write(tmp_path / "b.json", feed("m", generated_at="2026-11-13T00:00:00Z"))
    feeds, _ = prw_metrics.load_usage_feeds([str(tmp_path)])
    assert [f["generated_at"] for f in feeds] == ["2026-11-13T00:00:00Z"]


def _git(cwd, *args):
    return REAL_RUN(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout


@pytest.fixture
def usage_remote(tmp_path, monkeypatch):
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", "/dev/null")
    monkeypatch.setenv("GIT_CONFIG_SYSTEM", "/dev/null")
    seed = tmp_path / "seed"
    _git(tmp_path, "init", "-b", "main", str(seed))
    (seed / "dashboards/prw/usage").mkdir(parents=True)
    write(seed / "dashboards/prw/usage/remote-machine.json", feed("remote-machine"))
    _git(seed, "add", ".")
    _git(seed, "-c", "user.name=t", "-c", "user.email=t@example.invalid", "commit", "-m", "seed")
    return "file://%s" % seed


def test_load_reads_feeds_from_remote(tmp_path, usage_remote):
    write(tmp_path / "local.json", feed("local-machine"))
    feeds, problems = prw_metrics.load_usage_feeds([str(tmp_path / "local.json")], remote=usage_remote)
    assert sorted(f["machine"] for f in feeds) == ["local-machine", "remote-machine"] and problems == []


def test_load_remote_failure_is_a_problem_not_an_abort(tmp_path):
    feeds, problems = prw_metrics.load_usage_feeds([], remote="file://%s" % (tmp_path / "missing.git"))
    assert feeds == [] and len(problems) == 1


# --- aggregate ---

def test_aggregate_without_usage_has_no_usage_key():
    health = {REPO_A: {"ok": True}}
    metrics = prw_metrics.aggregate([], health, {"labels": {}, "status": "ABSENT"}, CUTOFF)
    assert "usage" not in metrics


def test_staleness_uses_twelve_hour_threshold():
    fresh = feed("fresh", generated_at="2026-11-13T12:00:00Z")  # exactly 12h before cutoff
    stale = feed("stale", generated_at="2026-11-13T11:59:59Z")
    machines = agg([], [fresh, stale])["machines"]
    assert machines == {"fresh": {"generated_at": "2026-11-13T12:00:00Z", "stale": False},
                        "stale": {"generated_at": "2026-11-13T11:59:59Z", "stale": True}}


def test_branch_match_attributes_to_pr_and_repo():
    u = agg([pr(REPO_A, 7, "feature/x")], [feed(sessions=[session(output=5, active=100)])])
    assert u["per_pr"] == {"%s#7" % REPO_A: {"active_sec": 100, "output": 5, "input": 1, "sessions": 1}}
    repo = u["per_repo"][REPO_A]
    assert repo["sessions"] == 1 and repo["tokens"] == {"input": 1, "output": 5, "cache_read": 2, "cache_write": 3}
    assert repo["by_tool"] == {"claude": {"sessions": 1, "active_sec": 100, "output": 5}}
    assert u["unattributed"] == {"sessions": 0, "active_sec": 0, "output": 0}


def test_repo_mismatch_is_not_attributed():
    u = agg([pr(REPO_B, 7, "feature/x")], [feed(sessions=[session(repo=REPO_A, active=50, output=4)])])
    assert u["per_pr"] == {}
    assert u["per_repo"][REPO_A]["sessions"] == 1
    assert u["unattributed"] == {"sessions": 1, "active_sec": 50, "output": 4}


def test_null_repo_matches_single_repo_pr():
    u = agg([pr(REPO_B, 3, "feature/x")], [feed(sessions=[session(repo=None)])])
    assert list(u["per_pr"]) == ["%s#3" % REPO_B]
    assert "unattributed" in u["per_repo"]  # session repo is null: the bucket, as the repo is unknown


def test_null_repo_ambiguous_across_repos_is_unattributed():
    records = [pr(REPO_A, 1, "feature/x"), pr(REPO_B, 2, "feature/x")]
    u = agg(records, [feed(sessions=[session(repo=None)])])
    assert u["per_pr"] == {} and u["unattributed"]["sessions"] == 1


@pytest.mark.parametrize("branch", ["main", "master", "trunk", "develop", None])
def test_trivial_or_missing_branch_never_matches(branch):
    u = agg([pr(REPO_A, 1, "main"), pr(REPO_A, 2, "develop")], [feed(sessions=[session(branch=branch)])])
    assert u["per_pr"] == {} and u["unattributed"]["sessions"] == 1


def test_reused_branch_goes_to_most_recent_pr():
    records = [pr(REPO_A, 1, "feature/x", "2026-10-01T00:00:00Z"),
               pr(REPO_A, 2, "feature/x", "2026-11-05T00:00:00Z"),
               pr(REPO_A, 3, "feature/x", "2026-10-20T00:00:00Z")]
    u = agg(records, [feed(sessions=[session()])])
    assert list(u["per_pr"]) == ["%s#2" % REPO_A]


def test_window_overlap_filter():
    inside = session(sid="in", first="2026-10-30T23:00:00Z", last="2026-10-31T00:00:00Z")  # touches start
    before = session(sid="before", first="2026-10-30T00:00:00Z", last="2026-10-30T23:59:59Z")
    at_cutoff = session(sid="at", first="2026-11-14T00:00:00Z", last="2026-11-14T01:00:00Z")
    spanning = session(sid="span", first="2026-10-01T00:00:00Z", last="2026-12-01T00:00:00Z")
    u = agg([], [feed(sessions=[inside, before, at_cutoff, spanning])])
    assert u["per_repo"][REPO_A]["sessions"] == 2


def test_aggregate_does_not_mutate_inputs():
    feeds = [feed(sessions=[session()])]
    snapshot = copy.deepcopy(feeds)
    agg([pr(REPO_A, 1, "feature/x")], feeds)
    assert feeds == snapshot


# --- render ---

def golden_with_usage():
    metrics = json.loads((FIXTURES / "metrics_golden.json").read_text(encoding="utf-8"))
    metrics["usage"] = {
        "machines": {"machine-1": {"generated_at": "2026-11-13T20:00:00Z", "stale": False},
                     "machine-2": {"generated_at": "2026-11-10T00:00:00Z", "stale": True}},
        "problems": ["broken.json: unreadable"],
        "per_repo": {"example-org/example-repo": {
            "sessions": 3, "active_sec": 7200,
            "tokens": {"input": 10, "output": 77, "cache_read": 20, "cache_write": 30},
            "by_tool": {"claude": {"sessions": 3, "active_sec": 7200, "output": 77}}}},
        "per_pr": {},
        "unattributed": {"sessions": 1, "active_sec": 60, "output": 5},
    }
    return metrics


def test_render_without_usage_says_no_feed():
    out = prw_metrics.render(json.loads((FIXTURES / "metrics_golden.json").read_text(encoding="utf-8")))
    assert "Local agent usage: no feed configured" in out
    assert "Local agent usage (observed" not in out


def test_render_with_usage_adds_subsection_inside_section_3():
    import re
    out = prw_metrics.render(golden_with_usage())
    assert re.findall(r"^## ([1-7])\. ", out, flags=re.M) == ["1", "2", "3", "4", "5", "6", "7"]
    section3 = out.split("## 3.")[1].split("## 4.")[0]
    assert "Local agent usage (observed on contributing machines)" in section3
    assert "Local agent usage: no feed configured" not in out
    assert "example-org/example-repo" in section3 and "2h" in section3 and "77" in section3
    assert "machine-2" in section3 and "STALE" in section3
    assert "broken.json: unreadable" in section3
    assert "machines without a feed are not counted" in section3


def test_render_with_usage_is_deterministic():
    assert prw_metrics.render(golden_with_usage()) == prw_metrics.render(golden_with_usage())


# --- publish a different path ---

def _publish_env(monkeypatch, tmp_path):
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", "/dev/null")
    monkeypatch.setenv("GIT_CONFIG_SYSTEM", "/dev/null")
    bare = tmp_path / "remote.git"
    _git(tmp_path, "init", "--bare", "-b", "main", str(bare))
    seed = tmp_path / "seed"
    _git(tmp_path, "init", "-b", "main", str(seed))
    (seed / "other.txt").write_text("seed\n")
    _git(seed, "add", ".")
    _git(seed, "-c", "user.name=t", "-c", "user.email=t@example.invalid", "commit", "-m", "seed")
    _git(seed, "push", str(bare), "main")
    return bare


def test_publish_custom_path_and_message(tmp_path, monkeypatch):
    bare = _publish_env(monkeypatch, tmp_path)
    path = "dashboards/prw/usage/machine-1.json"
    rc = prw_metrics.publish('{"a": 1}\n', "file://%s" % bare, "main", str(tmp_path / "fb"),
                             path=path, message="chore(prw-usage): update machine-1 feed")
    assert rc == 0
    assert _git(bare, "show", "main:%s" % path) == '{"a": 1}\n'
    assert _git(bare, "log", "-1", "--format=%s", "main").strip() == "chore(prw-usage): update machine-1 feed"
    assert REAL_RUN(["git", "cat-file", "-e", "main:dashboards/prw/README.md"], cwd=bare).returncode != 0


def test_publish_default_path_and_message_unchanged(tmp_path, monkeypatch):
    bare = _publish_env(monkeypatch, tmp_path)
    assert prw_metrics.publish("# d\n", "file://%s" % bare, "main", str(tmp_path / "fb")) == 0
    assert _git(bare, "log", "-1", "--format=%s", "main").strip() == "chore(prw-metrics): update PRW dashboard"
    assert _git(bare, "show", "main:dashboards/prw/README.md") == "# d\n"


# --- main wiring ---

def test_main_merges_usage_feed_into_dashboard(tmp_path):
    write(tmp_path / "feed.json", feed("machine-1", generated_at="2026-11-13T20:00:00Z",
                                       sessions=[session(repo="example-org/example-repo", branch="feature/pr-105-work")]))
    out = tmp_path / "out.md"
    rc = prw_metrics.main([
        "--repos", "example-org/example-repo", "--input-dir", str(FIXTURES), "--cutoff", CUTOFF,
        "--output", str(out), "--annotations", str(tmp_path / "missing.json"),
        "--usage-feed", str(tmp_path / "feed.json"),
    ])
    text = out.read_text(encoding="utf-8")
    assert rc == 0
    assert "Local agent usage (observed on contributing machines)" in text and "machine-1" in text


def test_main_reads_usage_feeds_from_env(tmp_path, monkeypatch):
    write(tmp_path / "a.json", feed("machine-a"))
    write(tmp_path / "b.json", feed("machine-b"))
    monkeypatch.setenv("PRW_METRICS_USAGE_FEEDS", "%s:%s" % (tmp_path / "a.json", tmp_path / "b.json"))
    out = tmp_path / "out.md"
    assert prw_metrics.main(["--repos", "example-org/example-repo", "--input-dir", str(FIXTURES),
                             "--cutoff", CUTOFF, "--output", str(out),
                             "--annotations", str(tmp_path / "missing.json")]) == 0
    text = out.read_text(encoding="utf-8")
    assert "machine-a" in text and "machine-b" in text


def test_main_without_usage_config_says_no_feed(tmp_path, monkeypatch):
    monkeypatch.delenv("PRW_METRICS_USAGE_FEEDS", raising=False)
    monkeypatch.delenv("PRW_METRICS_USAGE_REMOTE", raising=False)
    out = tmp_path / "out.md"
    assert prw_metrics.main(["--repos", "example-org/example-repo", "--input-dir", str(FIXTURES),
                             "--cutoff", CUTOFF, "--output", str(out),
                             "--annotations", str(tmp_path / "missing.json")]) == 0
    assert "Local agent usage: no feed configured" in out.read_text(encoding="utf-8")


def test_usage_remote_with_embedded_credentials_is_rejected(tmp_path):
    rc = prw_metrics.main(["--repos", "o/r", "--usage-remote", "https://user:secret@example.com/o/r.git",
                           "--annotations", str(tmp_path / "missing.json")])
    assert rc == 2


def test_usage_remote_defaults_to_roadmap_remote_when_publishing(tmp_path, monkeypatch):
    seen = {}
    monkeypatch.setattr(prw_metrics, "load_usage_feeds",
                        lambda paths, remote=None, branch="main": seen.update(remote=remote, branch=branch) or ([], []))
    monkeypatch.setattr(prw_metrics, "publish", lambda *a, **k: 0)
    rc = prw_metrics.main(["--repos", "example-org/example-repo", "--input-dir", str(FIXTURES),
                           "--cutoff", CUTOFF, "--annotations", str(tmp_path / "missing.json"),
                           "--publish", "--roadmap-remote", "file:///nonexistent", "--roadmap-branch", "trunk-x"])
    assert rc == 0 and seen == {"remote": "file:///nonexistent", "branch": "trunk-x"}
