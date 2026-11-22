"""Installer tests: temporary HOME, stub launchctl first on PATH, throwaway source repo."""

import os
import re
import stat
import subprocess
from pathlib import Path

import pytest

INSTALLER = Path(__file__).resolve().parent.parent / "scripts" / "install-prw-metrics-launchd.sh"
LABEL = "com.jleechan.prw-metrics-slim"
OLD_LABEL = re.compile(r"com\.jleechan\.prw-metrics(?!-slim)")
REMOTE = "file:///tmp/example-roadmap.git"


@pytest.fixture
def env(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    calls = tmp_path / "launchctl.calls"
    marker = tmp_path / "loaded.marker"
    stub = bin_dir / "launchctl"
    stub.write_text(
        '#!/bin/sh\necho "$@" >> "%s"\n'
        'if [ "$1" = print ]; then [ -e "%s" ]; exit $?; fi\nexit 0\n' % (calls, marker)
    )
    stub.chmod(stub.stat().st_mode | stat.S_IEXEC)
    git_env = {
        "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_SYSTEM": "/dev/null",
        "GIT_AUTHOR_NAME": "T", "GIT_AUTHOR_EMAIL": "t@example.invalid",
        "GIT_COMMITTER_NAME": "T", "GIT_COMMITTER_EMAIL": "t@example.invalid",
    }
    source = tmp_path / "source"
    (source / "scripts").mkdir(parents=True)
    (source / "scripts" / "prw_metrics.py").write_text(
        "import sys\nif '--help' in sys.argv:\n    print('stub help')\n"
    )
    (source / "scripts" / "run_prw_metrics.sh").write_text("#!/bin/sh\n")
    full_env = dict(os.environ, HOME=str(home), PATH="%s:%s" % (bin_dir, os.environ["PATH"]), **git_env)
    for cmd in (["init", "-b", "main"], ["add", "."], ["commit", "-m", "stub"]):
        subprocess.run(["git", *cmd], cwd=source, env=full_env, check=True, capture_output=True)
    sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=source, env=full_env, check=True, capture_output=True, text=True
    ).stdout.strip()

    class Ctx:
        pass

    ctx = Ctx()
    ctx.home, ctx.marker, ctx.sha, ctx.env = home, marker, sha, full_env
    ctx.calls = lambda: calls.read_text().splitlines() if calls.exists() else []
    ctx.release = home / ".local/share/prw-metrics-slim/releases" / sha
    ctx.plist = home / "Library/LaunchAgents" / (LABEL + ".plist")
    ctx.staged = ctx.release / (LABEL + ".plist")

    def run(*extra):
        cmd = [
            "bash", str(INSTALLER), "--source-repo", str(source), "--source-rev", sha,
            "--repos", "o/a,o/b", "--roadmap-remote", REMOTE, "--roadmap-branch", "main", *extra,
        ]
        return subprocess.run(cmd, env=full_env, capture_output=True, text=True)

    ctx.run = run
    return ctx


def test_dry_run_prints_plist_and_calls_no_launchctl(env):
    done = env.run("--dry-run")
    assert done.returncode == 0, done.stderr
    assert LABEL in done.stdout and "--publish" in done.stdout and REMOTE in done.stdout
    assert "o/a,o/b" in done.stdout and env.sha in done.stdout
    assert env.calls() == []
    assert not env.plist.exists()


def test_install_creates_pinned_release_via_git_archive_and_runs_help(env):
    done = env.run()
    assert done.returncode == 0, done.stderr
    assert (env.release / "scripts" / "prw_metrics.py").exists()
    assert not (env.release / ".git").exists()
    assert env.staged.exists() and env.sha in env.staged.read_text()
    assert not env.plist.exists()  # launchd loads LaunchAgents at login; only --activate may put it there
    assert "stub help" in done.stdout


def test_refuses_when_slim_label_already_loaded(env):
    env.marker.write_text("")
    done = env.run()
    assert done.returncode != 0
    assert "--replace-slim" in done.stderr
    assert not env.plist.exists() and not env.release.exists()


def test_replace_slim_flag_allows_reinstall(env):
    env.marker.write_text("")
    done = env.run("--replace-slim")
    assert done.returncode == 0, done.stderr
    assert env.staged.exists()
    assert not any(c.startswith(("bootstrap", "kickstart", "enable")) for c in env.calls())


def test_never_touches_old_label(env):
    assert env.run().returncode == 0
    assert env.run("--replace-slim", "--activate").returncode == 0
    assert not any(OLD_LABEL.search(c) for c in env.calls())
    assert not (env.home / "Library/LaunchAgents/com.jleechan.prw-metrics.plist").exists()


def test_install_without_activate_does_not_load_or_start(env):
    assert env.run().returncode == 0
    assert not any(c.split()[0] in ("bootstrap", "enable", "kickstart", "load", "start") for c in env.calls())


def test_activate_enables_and_bootstraps_slim_label(env):
    assert env.run("--activate").returncode == 0
    calls = env.calls()
    assert any(c.startswith("enable ") and c.endswith("/" + LABEL) for c in calls)
    assert any(c.startswith("bootstrap ") and LABEL + ".plist" in c for c in calls)
    assert env.plist.exists()


def test_usage_remote_in_plist_only_when_given(env):
    assert "--usage-remote" not in env.run("--dry-run").stdout
    given = env.run("--dry-run", "--usage-remote", REMOTE)
    assert given.returncode == 0, given.stderr
    lines = [ln.strip() for ln in given.stdout.splitlines()]
    assert lines[lines.index("<string>--usage-remote</string>") + 1] == "<string>%s</string>" % REMOTE
    assert env.calls() == []


def test_usage_remote_with_credentials_exits_2(env):
    done = env.run("--dry-run", "--usage-remote", "https://u:p@example.invalid/r.git")
    assert done.returncode == 2
    assert env.calls() == []


@pytest.mark.parametrize("flag", ["--usage-remote", "--roadmap-remote"])
def test_credential_remotes_rejected_without_echoing_url(env, flag):
    bad = "https://u:p@example.invalid/r.git"
    done = env.run("--dry-run", flag, bad)
    assert done.returncode == 2
    assert bad not in done.stdout and bad not in done.stderr
    assert env.calls() == []
