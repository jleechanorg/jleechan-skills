import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import prw_local_usage as plu  # noqa: E402

START = "2026-01-10T00:00:00Z"
END = "2026-01-11T00:00:00Z"
SECRET_TEXT = "SECRET-PROMPT-TEXT-xyz"


def write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write((r if isinstance(r, str) else json.dumps(r)) + "\n")


def claude_row(ts, mid=None, out=0, inp=0, cr=0, cw=0, cwd="/nonexistent/example", branch="feat/x", model="claude-example"):
    row = {"timestamp": ts, "sessionId": "s1", "cwd": cwd, "gitBranch": branch,
           "message": {"content": SECRET_TEXT}}
    if mid:
        row["message"] = {"id": mid, "model": model, "content": SECRET_TEXT,
                          "usage": {"input_tokens": inp, "output_tokens": out,
                                    "cache_read_input_tokens": cr, "cache_creation_input_tokens": cw}}
    return row


def run(tmp_path, claude=(), codex=(), idle=300, start=START, end=END, resolver=None):
    return plu.collect(start, end, [tmp_path / "c"], [tmp_path / "x"], idle, "m1",
                       now="2026-01-12T00:00:00Z", resolver=resolver or (lambda cwd: None))


def claude_file(tmp_path, rows):
    write_jsonl(tmp_path / "c" / "proj" / "s1.jsonl", rows)


def codex_file(tmp_path, rows, name="rollout-1.jsonl"):
    write_jsonl(tmp_path / "x" / "2026" / name, rows)


def tok(ts, inp, cached=0, cw=0, out=0):
    return {"timestamp": ts, "type": "event_msg", "payload": {"type": "token_count", "info": {
        "total_token_usage": {"input_tokens": inp, "cached_input_tokens": cached,
                              "cache_write_input_tokens": cw, "output_tokens": out}}}}


def codex_meta(cwd="/nonexistent/example"):
    return {"timestamp": "2026-01-09T00:00:00Z", "type": "session_meta",
            "payload": {"id": "cx1", "cwd": cwd, "git": {"branch": "main"}}}


def test_claude_usage_grouped_by_message_id_keeping_largest(tmp_path):
    claude_file(tmp_path, [
        claude_row("2026-01-10T01:00:00Z", "m1", out=5, inp=10),
        claude_row("2026-01-10T01:00:01Z", "m1", out=50, inp=10, cr=7, cw=3),
        claude_row("2026-01-10T01:00:02Z", "m2", out=4, inp=1),
    ])
    feed = run(tmp_path)
    (s,) = feed["sessions"]
    assert s["tool"] == "claude" and s["session_id"] == "s1" and s["branch"] == "feat/x"
    assert s["models"] == {"claude-example": {"input": 11, "output": 54, "cache_read": 7, "cache_write": 3}}


def test_claude_events_outside_window_excluded(tmp_path):
    claude_file(tmp_path, [
        claude_row("2026-01-09T23:59:59Z", "a", out=100),
        claude_row("2026-01-10T00:00:00Z", "b", out=1),
        claude_row("2026-01-11T00:00:00Z", "c", out=1000),
    ])
    (s,) = run(tmp_path)["sessions"]
    assert s["models"]["claude-example"]["output"] == 1
    assert s["first_at"] == s["last_at"] == "2026-01-10T00:00:00Z"
    claude_file(tmp_path, [claude_row("2026-02-01T00:00:00Z", "z", out=1)])
    assert run(tmp_path)["sessions"] == []


def test_codex_usage_is_delta_of_cumulative_totals(tmp_path):
    codex_file(tmp_path, [
        codex_meta(),
        {"timestamp": "2026-01-09T00:00:01Z", "type": "turn_context", "payload": {"model": "gpt-example"}},
        tok("2026-01-09T23:00:00Z", 100, out=10),
        tok("2026-01-10T05:00:00Z", 300, out=40),
        tok("2026-01-10T06:00:00Z", 500, out=90),
        tok("2026-01-11T01:00:00Z", 9000, out=900),
    ])
    (s,) = run(tmp_path)["sessions"]
    assert s["tool"] == "codex" and s["session_id"] == "cx1" and s["branch"] == "main"
    assert s["models"] == {"gpt-example": {"input": 400, "output": 80, "cache_read": 0, "cache_write": 0}}


def test_codex_cached_input_split_from_input(tmp_path):
    codex_file(tmp_path, [codex_meta(), tok("2026-01-10T05:00:00Z", 1000, cached=600, cw=5, out=20)])
    (s,) = run(tmp_path)["sessions"]
    assert s["models"]["unknown"] == {"input": 400, "output": 20, "cache_read": 600, "cache_write": 5}


def test_active_sec_counts_gaps_up_to_idle_limit_only(tmp_path):
    claude_file(tmp_path, [
        claude_row("2026-01-10T01:00:00Z"),
        claude_row("2026-01-10T01:04:00Z"),   # 240 counted
        claude_row("2026-01-10T01:09:00Z"),   # 300 counted (== limit)
        claude_row("2026-01-10T01:20:00Z", "m", out=1),  # 660 dropped
    ])
    (s,) = run(tmp_path)["sessions"]
    assert s["active_sec"] == 540
    (s,) = run(tmp_path, idle=100)["sessions"]
    assert s["active_sec"] == 0


def test_feed_contains_no_text_or_paths(tmp_path):
    claude_file(tmp_path, [claude_row("2026-01-10T01:00:00Z", "m1", out=5, cwd="/home/someone/secret-dir")])
    codex_file(tmp_path, [codex_meta("/home/someone/other-dir"), tok("2026-01-10T05:00:00Z", 10)])
    blob = json.dumps(run(tmp_path, resolver=lambda cwd: "example-org/example-repo"))
    for bad in (SECRET_TEXT, "/home/", "secret-dir", "other-dir", str(tmp_path), "https://", "git@"):
        assert bad not in blob


def test_repo_resolved_from_git_remote_and_none_when_missing(tmp_path):
    repo = tmp_path / "r"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "remote", "add", "origin",
                    "git@github.com:example-org/example-repo.git"], check=True)
    assert plu.resolve_repo(str(repo)) == "example-org/example-repo"
    assert plu.normalize_remote("https://github.com/example-org/example-repo.git") == "example-org/example-repo"
    assert plu.normalize_remote("ssh://git@host.example/example-org/example-repo") == "example-org/example-repo"
    assert plu.resolve_repo(str(tmp_path / "gone")) is None
    plain = tmp_path / "plain"
    plain.mkdir()
    assert plu.resolve_repo(str(plain)) is None


def test_missing_roots_yield_empty_feed(tmp_path):
    feed = run(tmp_path)
    assert feed["schema"] == "prw-local-usage.v1" and feed["sessions"] == []
    assert feed["window"] == {"start": START, "end": END} and feed["idle_gap_sec"] == 300


def test_malformed_lines_skipped(tmp_path):
    claude_file(tmp_path, ["{not json", "", "[1,2]", claude_row("2026-01-10T01:00:00Z", "m1", out=3),
                           {"timestamp": "garbage", "message": {}}])
    (s,) = run(tmp_path)["sessions"]
    assert s["models"]["claude-example"]["output"] == 3


def test_output_is_deterministic(tmp_path):
    claude_file(tmp_path, [claude_row("2026-01-10T01:00:00Z", "m1", out=3)])
    codex_file(tmp_path, [codex_meta(), tok("2026-01-10T05:00:00Z", 10)])
    a = json.dumps(run(tmp_path), sort_keys=True)
    b = json.dumps(run(tmp_path), sort_keys=True)
    assert a == b
    assert [s["tool"] for s in run(tmp_path)["sessions"]] == ["claude", "codex"]
    out = tmp_path / "o.json"
    args = ["--claude-root", str(tmp_path / "c"), "--codex-root", str(tmp_path / "x"), "--machine", "m1",
            "--since", START, "--until", END, "--output", str(out)]
    assert plu.main(args) == 0
    first = out.read_text()
    assert plu.main(args) == 0
    assert json.loads(first)["sessions"] and "generated_at" in first


def test_publish_rejects_credential_remote(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(plu, "publish", lambda *a, **k: calls.append((a, k)) or 0)
    for url in ("https://user:token@example.com/o/r.git", "https://token@example.com/o/r.git"):
        rc = plu.main(["--claude-root", str(tmp_path / "c"), "--codex-root", str(tmp_path / "x"),
                       "--publish-remote", url])
        assert rc == 2
    assert calls == []


def test_publish_called_with_machine_slug_path(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(plu, "publish", lambda *a, **k: calls.append((a, k)) or 0)
    rc = plu.main(["--claude-root", str(tmp_path / "c"), "--codex-root", str(tmp_path / "x"),
                   "--machine", "My Laptop_01", "--publish-remote", "git@example.com:o/r.git",
                   "--publish-branch", "dash"])
    assert rc == 0
    ((args, kw),) = calls
    assert kw["path"] == "dashboards/prw/usage/my-laptop-01.json"
    assert args[1] == "git@example.com:o/r.git" and args[2] == "dash"
    assert json.loads(args[0])["machine"] == "My Laptop_01"
