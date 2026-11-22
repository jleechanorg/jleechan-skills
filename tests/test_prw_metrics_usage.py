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


def test_load_picks_newest_feed_by_parsed_time_not_string_order(tmp_path):
    older, newer = feed("m", generated_at="2026-11-13T10:00:00Z"), feed("m", generated_at="2026-11-13T10:00:00.5+00:00")
    write(tmp_path / "a.json", older)
    write(tmp_path / "b.json", newer)
    feeds, problems = prw_metrics.load_usage_feeds([str(tmp_path)])
    assert [f["generated_at"] for f in feeds] == ["2026-11-13T10:00:00.5+00:00"] and problems == []


@pytest.mark.parametrize("bad", ["not-a-time", 123, "2026-11-13T10:00:00"])
def test_load_unparseable_generated_at_is_a_problem(tmp_path, bad):
    write(tmp_path / "a.json", feed("m", generated_at=bad))
    feeds, problems = prw_metrics.load_usage_feeds([str(tmp_path)])
    assert feeds == [] and len(problems) == 1


def _no_git(monkeypatch):
    def boom(*a, **k):
        raise FileNotFoundError("git")
    monkeypatch.setattr(prw_metrics.subprocess, "run", boom)


def test_load_remote_without_git_is_a_problem_not_a_crash(tmp_path, monkeypatch):
    _no_git(monkeypatch)
    feeds, problems = prw_metrics.load_usage_feeds([], remote="file://%s" % (tmp_path / "r.git"))
    assert feeds == [] and len(problems) == 1


def test_publish_without_git_returns_3_with_fallback_file(tmp_path, monkeypatch):
    _no_git(monkeypatch)
    fallback = tmp_path / "fb.json"
    assert prw_metrics.publish("{}\n", "file://%s" % (tmp_path / "r.git"), "main", str(fallback)) == 3
    assert fallback.read_text() == "{}\n"


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


# --- heartbeat ---

def _feed_text(generated_at, sessions=()):
    return json.dumps(feed("machine-1", generated_at=generated_at, sessions=list(sessions)), sort_keys=True) + "\n"


def _commits(bare):
    return int(_git(bare, "rev-list", "--count", "main").strip())


@pytest.mark.parametrize("later,expected_new_commits", [
    ("2026-11-13T05:59:59Z", 0),   # unchanged content, 5h59m59s newer: nothing to push
    ("2026-11-13T06:00:00Z", 1),   # unchanged content, exactly HEARTBEAT_SEC newer: heartbeat commit
])
def test_publish_heartbeat_for_unchanged_feed(tmp_path, monkeypatch, later, expected_new_commits):
    bare = _publish_env(monkeypatch, tmp_path)
    remote, path = "file://%s" % bare, "dashboards/prw/usage/machine-1.json"
    assert prw_metrics.publish(_feed_text("2026-11-13T00:00:00Z"), remote, "main", str(tmp_path / "fb"), path=path) == 0
    before = _commits(bare)
    assert prw_metrics.publish(_feed_text(later), remote, "main", str(tmp_path / "fb"), path=path) == 0
    assert _commits(bare) == before + expected_new_commits
    assert json.loads(_git(bare, "show", "main:%s" % path))["generated_at"] == (
        later if expected_new_commits else "2026-11-13T00:00:00Z")


def test_publish_changed_sessions_commit_regardless_of_age(tmp_path, monkeypatch):
    bare = _publish_env(monkeypatch, tmp_path)
    remote, path = "file://%s" % bare, "dashboards/prw/usage/machine-1.json"
    assert prw_metrics.publish(_feed_text("2026-11-13T00:00:00Z"), remote, "main", str(tmp_path / "fb"), path=path) == 0
    before = _commits(bare)
    assert prw_metrics.publish(_feed_text("2026-11-13T00:01:00Z", [session()]), remote, "main",
                               str(tmp_path / "fb"), path=path) == 0
    assert _commits(bare) == before + 1


def test_heartbeat_is_shorter_than_staleness_threshold():
    assert prw_metrics.HEARTBEAT_SEC == 6 * 3600 < prw_metrics._STALE_AFTER


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


def test_publish_without_usage_options_reads_no_feeds(tmp_path, monkeypatch):
    clones, published = [], []
    monkeypatch.setattr(prw_metrics, "load_usage_feeds", lambda *a, **k: clones.append(a) or ([], []))
    monkeypatch.setattr(prw_metrics, "publish", lambda md, *a, **k: published.append(md) or 0)
    rc = prw_metrics.main(["--repos", "example-org/example-repo", "--input-dir", str(FIXTURES),
                           "--cutoff", CUTOFF, "--annotations", str(tmp_path / "missing.json"),
                           "--publish", "--roadmap-remote", "file:///nonexistent"])
    assert rc == 0 and clones == []
    assert "Local agent usage: no feed configured" in published[0]
    assert "Local agent usage" not in published[0].replace("Local agent usage: no feed configured", "")


def test_explicit_usage_remote_is_read_with_the_roadmap_branch(tmp_path, monkeypatch):
    seen = {}
    monkeypatch.setattr(prw_metrics, "load_usage_feeds",
                        lambda paths, remote=None, branch="main", **k: seen.update(remote=remote, branch=branch) or ([], []))
    monkeypatch.setattr(prw_metrics, "publish", lambda *a, **k: 0)
    rc = prw_metrics.main(["--repos", "example-org/example-repo", "--input-dir", str(FIXTURES),
                           "--cutoff", CUTOFF, "--annotations", str(tmp_path / "missing.json"),
                           "--publish", "--roadmap-remote", "file:///nonexistent", "--roadmap-branch", "trunk-x",
                           "--usage-remote", "file:///usage"])
    assert rc == 0 and seen == {"remote": "file:///usage", "branch": "trunk-x"}


def test_future_generated_at_is_ignored_and_reported(tmp_path):
    write(tmp_path / "ok.json", feed("m", generated_at="2026-11-13T20:00:00Z"))
    write(tmp_path / "future.json", feed("m", generated_at="2027-01-01T00:00:00Z", sessions=[session()]))
    write(tmp_path / "soon.json", feed("m2", generated_at="2026-11-14T00:04:00Z"))  # within 5 min tolerance
    feeds, problems = prw_metrics.load_usage_feeds([str(tmp_path)], cutoff=CUTOFF)
    assert {f["machine"]: f["generated_at"] for f in feeds} == {
        "m": "2026-11-13T20:00:00Z", "m2": "2026-11-14T00:04:00Z"}
    assert len(problems) == 1 and "future.json" in problems[0]


def test_only_future_feed_leaves_machine_absent(tmp_path):
    write(tmp_path / "future.json", feed("m", generated_at="2026-11-20T00:00:00Z"))
    feeds, problems = prw_metrics.load_usage_feeds([str(tmp_path)], cutoff=CUTOFF)
    assert feeds == [] and len(problems) == 1


def test_main_passes_cutoff_so_future_feeds_are_dropped(tmp_path):
    write(tmp_path / "future.json", feed("m", generated_at="2026-11-20T00:00:00Z"))
    out = tmp_path / "out.md"
    assert prw_metrics.main(["--repos", "example-org/example-repo", "--input-dir", str(FIXTURES),
                             "--cutoff", CUTOFF, "--output", str(out), "--usage-feed", str(tmp_path),
                             "--annotations", str(tmp_path / "missing.json")]) == 0
    assert "future.json" in out.read_text(encoding="utf-8")


def test_session_that_started_on_main_is_attributed_to_feature_branch_pr():
    from prw_local_usage import _final_branch, _note_branch
    rec = {"branch": None, "any_branch": None}
    for at, b in enumerate(["main", "feat/x", "main"]):
        _note_branch(rec, at, b)
    usage = agg([pr(REPO_A, 5, "feat/x")], [feed(sessions=[session(branch=_final_branch(rec))])])
    assert list(usage["per_pr"]) == ["%s#5" % REPO_A] and usage["unattributed"]["sessions"] == 0


# --- hardening: git timeouts, credential check, validation, repo case, no-change detection ---

class _Done:
    returncode, stdout, stderr = 0, "", ""


@pytest.fixture(autouse=True)
def _fresh_ssh_config_cache(monkeypatch):
    monkeypatch.setattr(prw_metrics, "_SSH_CONFIGURED", None)
    monkeypatch.delenv("GIT_SSH", raising=False)


def _capture_git(monkeypatch):
    seen = {}

    def fake(cmd, **kw):
        seen.update(cmd=cmd, **kw)
        return _Done()
    monkeypatch.setattr(prw_metrics.subprocess, "run", fake)
    return seen


def test_git_has_default_timeout_and_noninteractive_env(monkeypatch):
    monkeypatch.delenv("PRW_METRICS_GIT_TIMEOUT_SEC", raising=False)
    monkeypatch.delenv("GIT_SSH_COMMAND", raising=False)
    seen = _capture_git(monkeypatch)
    prw_metrics._git(".", "status")
    assert seen["timeout"] == 120
    assert seen["env"]["GIT_TERMINAL_PROMPT"] == "0"
    assert seen["env"]["GIT_SSH_COMMAND"] == "ssh -o BatchMode=yes -o ConnectTimeout=20"


def test_git_timeout_env_override_and_existing_ssh_command_kept(monkeypatch):
    monkeypatch.setenv("PRW_METRICS_GIT_TIMEOUT_SEC", "7")
    monkeypatch.setenv("GIT_SSH_COMMAND", "ssh -i key")
    seen = _capture_git(monkeypatch)
    prw_metrics._git(".", "status")
    assert seen["timeout"] == 7 and seen["env"]["GIT_SSH_COMMAND"] == "ssh -i key"


def _fake_git_with_config(monkeypatch, configured):
    calls = []

    def fake(cmd, **kw):
        calls.append((cmd, kw))
        done = _Done()
        if "config" in cmd:
            done.stdout = configured
        return done
    monkeypatch.setattr(prw_metrics.subprocess, "run", fake)
    return calls


def test_git_keeps_users_core_ssh_command(monkeypatch):
    monkeypatch.delenv("GIT_SSH_COMMAND", raising=False)
    calls = _fake_git_with_config(monkeypatch, "ssh -i mykey\n")
    prw_metrics._git(".", "status")
    assert "GIT_SSH_COMMAND" not in calls[-1][1]["env"]
    assert any(c[0][-3:] == ["config", "--get", "core.sshCommand"] and c[1]["timeout"] == 5 for c in calls)


def test_git_keeps_users_git_ssh(monkeypatch):
    monkeypatch.delenv("GIT_SSH_COMMAND", raising=False)
    monkeypatch.setenv("GIT_SSH", "/opt/my-ssh")
    calls = _fake_git_with_config(monkeypatch, "")
    prw_metrics._git(".", "status")
    assert "GIT_SSH_COMMAND" not in calls[-1][1]["env"] and calls[-1][1]["env"]["GIT_SSH"] == "/opt/my-ssh"


def test_git_ssh_config_lookup_is_cached_per_process(monkeypatch):
    monkeypatch.delenv("GIT_SSH_COMMAND", raising=False)
    calls = _fake_git_with_config(monkeypatch, "")
    prw_metrics._git(".", "status")
    prw_metrics._git(".", "fetch")
    assert sum("config" in c[0] for c in calls) == 1
    assert calls[-1][1]["env"]["GIT_SSH_COMMAND"].startswith("ssh -o BatchMode=yes")


def _hang(monkeypatch):
    def fake(cmd, **kw):
        raise subprocess.TimeoutExpired(cmd, kw.get("timeout"))
    monkeypatch.setattr(prw_metrics.subprocess, "run", fake)


def test_git_timeout_raises_runtime_error(monkeypatch):
    _hang(monkeypatch)
    with pytest.raises(RuntimeError, match="git clone timed out"):
        prw_metrics._git(".", "clone", "x")


def test_publish_returns_3_with_fallback_on_git_timeout(tmp_path, monkeypatch):
    _hang(monkeypatch)
    fb = tmp_path / "fb.md"
    assert prw_metrics.publish("# d\n", "file:///nowhere", "main", str(fb)) == 3
    assert fb.read_text() == "# d\n"


def test_load_usage_feeds_git_timeout_is_a_problem(monkeypatch):
    _hang(monkeypatch)
    feeds, problems = prw_metrics.load_usage_feeds([], remote="file:///nowhere")
    assert feeds == [] and len(problems) == 1


@pytest.mark.parametrize("url", [
    "HTTPS://tok@github.com/o/n", "git+https://tok@github.com/o/n", "ssh://git:pw@github.com/o/n",
    "https://user:tok@h/o/n", "git:tok@github.com:o/n.git"])
def test_embeds_credentials_rejects(url):
    assert prw_metrics.embeds_credentials(url)


@pytest.mark.parametrize("url", [
    "https://github.com/o/n", "ssh://git@github.com/o/n", "git@github.com:o/n.git", "file:///tmp/x", ""])
def test_embeds_credentials_allows(url):
    assert not prw_metrics.embeds_credentials(url)


def test_both_cli_flags_reject_credentials(tmp_path):
    ann = str(tmp_path / "missing.json")
    assert prw_metrics.main(["--repos", "o/r", "--publish", "--roadmap-remote", "git+https://tok@h.io/o/n",
                             "--annotations", ann]) == 2
    assert prw_metrics.main(["--repos", "o/r", "--usage-remote", "git:tok@h.io:o/n.git",
                             "--annotations", ann]) == 2


def _load_with(tmp_path, bad):
    write(tmp_path / "f.json", feed("m", sessions=[session(sid="good"), dict(session(sid="bad"), **bad)]))
    feeds, problems = prw_metrics.load_usage_feeds([str(tmp_path / "f.json")])
    assert [s["session_id"] for s in feeds[0]["sessions"]] == ["good"]
    assert any("dropped 1" in p for p in problems)
    return feeds, problems


@pytest.mark.parametrize("bad", [
    {"branch": ["x"]}, {"repo": 5}, {"active_sec": -1}, {"active_sec": True}, {"tool": 3}, {"session_id": None},
    {"models": {"m": {"input": True, "output": 1, "cache_read": 1, "cache_write": 1}}},
    {"models": {"m": {"input": -1, "output": 1, "cache_read": 1, "cache_write": 1}}},
    {"models": {"m": 5}}, {"models": []},
    {"first_at": "2026-11-10T02:00:00Z", "last_at": "2026-11-10T01:00:00Z"},
    {"first_at": "nonsense"}])
def test_invalid_session_dropped_and_dashboard_renders(tmp_path, bad):
    feeds, problems = _load_with(tmp_path, bad)
    metrics = prw_metrics.aggregate([], {REPO_A: {"ok": True}}, {"labels": {}, "status": "ABSENT"}, CUTOFF,
                                    usage=feeds, usage_problems=problems)
    assert "Local agent usage" in prw_metrics.render(metrics)


def test_repo_comparison_is_case_insensitive():
    records = [pr("org/repo", 7, "feature/x")]
    usage = agg(records, [feed(sessions=[session(repo="Org/Repo", branch="feature/x")])])
    assert list(usage["per_pr"]) == ["org/repo#7"]
    assert list(usage["per_repo"]) == ["org/repo"]


def _publish_feed_text(sessions, generated_at):
    doc = dict(feed(sessions=sessions), generated_at=generated_at)  # window is fixed; only generated_at varies
    return json.dumps(doc, sort_keys=True) + "\n"


def test_publish_json_ignores_generated_at_only_changes(tmp_path, monkeypatch):
    bare = _publish_env(monkeypatch, tmp_path)
    remote, path = "file://%s" % bare, "dashboards/prw/usage/m.json"
    fb = str(tmp_path / "fb")

    def go(text):
        return prw_metrics.publish(text, remote, "main", fb, path=path, message="m")

    def commits():
        return int(_git(bare, "rev-list", "--count", "main"))
    assert go(_publish_feed_text([session()], "2026-11-13T00:00:00Z")) == 0
    n = commits()
    assert go(_publish_feed_text([session()], "2026-11-13T05:00:00Z")) == 0
    assert commits() == n
    assert go(_publish_feed_text([session(active=999)], "2026-11-13T06:00:00Z")) == 0
    assert commits() == n + 1


def test_stable_ignores_rolling_window_of_a_feed():
    base = {"schema": "prw-local-usage.v1", "machine": "m", "generated_at": "2026-01-01T00:00:00Z",
            "window": {"start": "2025-12-18T00:00:00Z", "end": "2026-01-01T00:00:00Z"}, "sessions": []}
    later = dict(base, generated_at="2026-01-01T01:00:00Z",
                 window={"start": "2025-12-18T01:00:00Z", "end": "2026-01-01T01:00:00Z"})
    changed = dict(later, sessions=[{"tool": "claude"}])
    stable = prw_metrics._stable
    assert stable(json.dumps(base)) == stable(json.dumps(later))
    assert stable(json.dumps(base)) != stable(json.dumps(changed))
