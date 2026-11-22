"""Collector installer tests: temporary HOME, stub launchctl/crontab/systemctl first on PATH, throwaway source repo."""

import os
import re
import stat
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
INSTALLER = ROOT / "scripts" / "install-prw-local-usage.sh"
LABEL = "com.jleechan.prw-local-usage"
OLD_LABEL = re.compile(r"com\.jleechan\.prw-metrics")
REMOTE = "file:///tmp/example-roadmap.git"


@pytest.fixture
def env(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    calls = tmp_path / "calls"
    marker = tmp_path / "loaded.marker"
    for name in ("launchctl", "crontab", "systemctl"):
        stub = bin_dir / name
        stub.write_text(
            '#!/bin/sh\necho "%s $@" >> "%s"\n'
            'if [ "$1" = print ]; then [ -e "%s" ]; exit $?; fi\nexit 0\n' % (name, calls, marker)
        )
        stub.chmod(stub.stat().st_mode | stat.S_IEXEC)
    git_env = {
        "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_SYSTEM": "/dev/null",
        "GIT_AUTHOR_NAME": "T", "GIT_AUTHOR_EMAIL": "t@example.invalid",
        "GIT_COMMITTER_NAME": "T", "GIT_COMMITTER_EMAIL": "t@example.invalid",
    }
    source = tmp_path / "source"
    (source / "scripts").mkdir(parents=True)
    (source / "scripts" / "prw_local_usage.py").write_text("print('stub collector')\n")
    (source / "scripts" / "run_prw_local_usage.sh").write_text("#!/bin/sh\n")
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
    ctx.release = home / ".local/share/prw-local-usage/releases" / sha
    ctx.plist = home / "Library/LaunchAgents" / (LABEL + ".plist")
    ctx.staged = ctx.release / (LABEL + ".plist")

    def run(*extra, remote=REMOTE):
        cmd = ["bash", str(INSTALLER), "--source-repo", str(source), "--source-rev", sha]
        if remote:
            cmd += ["--roadmap-remote", remote]
        return subprocess.run(cmd + list(extra), env=full_env, capture_output=True, text=True)

    ctx.run = run
    return ctx


def test_dry_run_prints_plist_and_calls_nothing(env):
    done = env.run("--dry-run", "--machine", "laptop-a")
    assert done.returncode == 0, done.stderr
    out = done.stdout
    assert LABEL in out and REMOTE in out and "laptop-a" in out and env.sha in out
    assert "--publish-remote" in out and "run_prw_local_usage.sh" in out
    assert "<integer>37</integer>" in out and "StartCalendarInterval" in out
    for path in ("/opt/homebrew/bin", "/usr/local/bin", str(env.home / ".local/bin"), "/usr/bin"):
        assert path in out
    assert env.calls() == [] and not env.release.exists() and not env.plist.exists()


def test_install_stages_but_does_not_load_or_place_plist(env):
    done = env.run()
    assert done.returncode == 0, done.stderr
    assert (env.release / "scripts" / "prw_local_usage.py").exists()
    assert not (env.release / ".git").exists()
    assert env.staged.exists() and env.sha in env.staged.read_text()
    assert "--machine" not in env.staged.read_text()
    assert not env.plist.exists()
    assert not any(c.split()[1] in ("bootstrap", "enable", "kickstart", "load") for c in env.calls())


def test_activate_enables_then_bootstraps_new_label_only(env):
    assert env.run("--activate").returncode == 0
    calls = env.calls()
    assert env.plist.exists()
    verbs = [c.split()[1] for c in calls if c.split()[1] in ("enable", "bootstrap")]
    assert verbs == ["enable", "bootstrap"]
    assert all(LABEL in c for c in calls if c.split()[1] in ("enable", "bootstrap"))
    assert not any(OLD_LABEL.search(c) for c in calls)


def test_refuses_when_loaded_without_replace(env):
    env.marker.write_text("")
    done = env.run("--activate")
    assert done.returncode != 0 and "--replace" in done.stderr
    assert not env.plist.exists() and not env.release.exists()


def test_replace_allows_reinstall(env):
    env.marker.write_text("")
    assert env.run("--replace").returncode == 0
    assert env.staged.exists()


@pytest.mark.parametrize("bad", ["https://tok@example.invalid/r.git", "https://u:p@example.invalid/r.git"])
def test_credential_remote_exits_2(env, bad):
    for extra in ((), ("--dry-run",), ("--print-crontab",)):
        done = env.run(*extra, remote=bad)
        assert done.returncode == 2, extra
        assert bad not in done.stdout
    assert env.calls() == [] and not env.release.exists()


def test_requires_remote(env):
    assert env.run(remote="").returncode != 0


def test_print_crontab_prints_release_and_remote_and_executes_nothing(env):
    done = env.run("--print-crontab", "--machine", "box")
    assert done.returncode == 0, done.stderr
    assert str(env.release) in done.stdout and REMOTE in done.stdout
    assert "37 * * * *" in done.stdout and "OnCalendar" in done.stdout and "[Timer]" in done.stdout
    assert env.calls() == [] and not env.release.exists() and not env.plist.exists()


def test_old_labels_never_touched(env):
    assert env.run("--activate").returncode == 0
    assert env.run("--replace", "--activate").returncode == 0
    assert not any(OLD_LABEL.search(c) for c in env.calls())
    assert not list((env.home / "Library/LaunchAgents").glob("com.jleechan.prw-metrics*"))


def test_wrapper_runs_collector_with_args_and_returns_its_status(tmp_path):
    rel = tmp_path / "rel"
    (rel / "scripts").mkdir(parents=True)
    wrapper = rel / "scripts" / "run_prw_local_usage.sh"
    wrapper.write_text((ROOT / "scripts" / "run_prw_local_usage.sh").read_text())
    (rel / "scripts" / "prw_local_usage.py").write_text(
        "import sys; print('ARGS', *sys.argv[1:]); sys.exit(3)\n"
    )
    done = subprocess.run(
        ["bash", str(wrapper), "--publish-remote", REMOTE, "--machine", "m"],
        env=dict(os.environ, HOME=str(tmp_path)), capture_output=True, text=True,
    )
    assert done.returncode == 3
    assert "ARGS --publish-remote %s --machine m" % REMOTE in done.stdout
    assert "start" in done.stdout and "exit 3" in done.stdout
