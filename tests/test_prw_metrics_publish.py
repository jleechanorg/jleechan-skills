"""Publisher and CLI tests: every test uses a temporary bare remote and never publishes for real."""

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "prw_metrics.py"
spec = importlib.util.spec_from_file_location("prw_metrics", SCRIPT)
prw = importlib.util.module_from_spec(spec)
sys.modules["prw_metrics"] = prw
spec.loader.exec_module(prw)

REAL_RUN = subprocess.run
README = "dashboards/prw/README.md"


def git(cwd, *args):
    return REAL_RUN(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout


@pytest.fixture(autouse=True)
def clean_env(monkeypatch, tmp_path):
    for name in ("PRW_METRICS_ROADMAP_REMOTE", "PRW_METRICS_PUBLISH", "PRW_METRICS_REPOS"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("PRW_METRICS_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", "/dev/null")
    monkeypatch.setenv("GIT_CONFIG_SYSTEM", "/dev/null")
    for who in ("AUTHOR", "COMMITTER"):
        monkeypatch.setenv("GIT_%s_NAME" % who, "Test")
        monkeypatch.setenv("GIT_%s_EMAIL" % who, "test@example.invalid")


@pytest.fixture
def remote(tmp_path):
    bare = tmp_path / "remote.git"
    git(tmp_path, "init", "--bare", "-b", "main", str(bare))
    seed = tmp_path / "seed"
    git(tmp_path, "init", "-b", "main", str(seed))
    (seed / "other.txt").write_text("seed\n")
    git(seed, "add", ".")
    git(seed, "commit", "-m", "seed")
    git(seed, "push", str(bare), "main")
    return "file://%s" % bare


def read_remote(remote_url, tmp_path, name="check"):
    dest = tmp_path / name
    git(tmp_path, "clone", "-b", "main", remote_url, str(dest))
    return dest


def commit_count(remote_url):
    return int(git(remote_url[len("file://"):], "rev-list", "--count", "main").strip())


def test_unchanged_content_exits_0_without_commit(remote, tmp_path):
    fallback = tmp_path / "fb.md"
    assert prw.publish("# dash\n", remote, "main", str(fallback)) == 0
    before = commit_count(remote)
    assert prw.publish("# dash\n", remote, "main", str(fallback)) == 0
    assert commit_count(remote) == before


def test_publish_pushes_commit_to_remote(remote, tmp_path):
    before = commit_count(remote)
    assert prw.publish("# dash\n", remote, "main", str(tmp_path / "fb.md")) == 0
    assert commit_count(remote) == before + 1
    checkout = read_remote(remote, tmp_path)
    assert (checkout / README).read_text() == "# dash\n"
    assert (checkout / "other.txt").exists()


def test_publish_rebases_after_concurrent_remote_commit(remote, tmp_path, monkeypatch):
    raced = []

    def racing_run(cmd, *args, **kwargs):
        if "push" in cmd and not raced:
            raced.append(True)
            other = read_remote(remote, tmp_path, "racer")
            (other / "concurrent.txt").write_text("x\n")
            git(other, "add", ".")
            git(other, "commit", "-m", "concurrent")
            git(other, "push", "origin", "HEAD:main")
        return REAL_RUN(cmd, *args, **kwargs)

    monkeypatch.setattr(prw.subprocess, "run", racing_run)
    assert prw.publish("# dash\n", remote, "main", str(tmp_path / "fb.md")) == 0
    checkout = read_remote(remote, tmp_path)
    assert (checkout / README).read_text() == "# dash\n"
    assert (checkout / "concurrent.txt").exists()


def test_publish_without_remote_exits_2(tmp_path, monkeypatch, capsys):
    fallback = tmp_path / "fb.md"
    assert prw.publish("# dash\n", "", "main", str(fallback)) == 2
    assert not fallback.exists()
    for name in ("collect", "aggregate", "render"):
        monkeypatch.setattr(prw, name, lambda *a, **k: pytest.fail("ran pipeline"))
    out = tmp_path / "out.md"
    assert prw.main(["--repos", "o/r", "--publish", "--output", str(out)]) == 2
    assert not out.exists()
    assert capsys.readouterr().err.strip()


def test_push_failure_exits_3_and_writes_fallback(remote, tmp_path):
    hook = Path(remote[len("file://"):]) / "hooks" / "pre-receive"
    hook.write_text("#!/bin/sh\necho denied >&2\nexit 1\n")
    hook.chmod(0o755)
    fallback = tmp_path / "state" / "last-dashboard.md"
    assert prw.publish("# dash\n", remote, "main", str(fallback)) == 3
    assert fallback.read_text() == "# dash\n"


def test_output_flag_writes_file(tmp_path, monkeypatch):
    seen = {}
    monkeypatch.setattr(prw, "gh_runner", object(), raising=False)
    monkeypatch.setattr(
        prw, "collect",
        lambda repos, cutoff, runner: seen.update(repos=repos, cutoff=cutoff) or ([], {"o/r": {"ok": True}}),
    )
    monkeypatch.setattr(prw, "aggregate", lambda records, health, ann, cutoff: {"cutoff": cutoff})
    monkeypatch.setattr(prw, "render", lambda metrics: "# rendered %s\n" % metrics["cutoff"])
    out = tmp_path / "out.md"
    assert prw.main(["--repos", "o/r,o/s", "--cutoff", "2026-11-14T00:00:00Z", "--output", str(out)]) == 0
    assert out.read_text() == "# rendered 2026-11-14T00:00:00Z\n"
    assert seen["repos"] == ["o/r", "o/s"]
