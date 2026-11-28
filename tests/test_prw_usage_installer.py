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
    systemd_state = tmp_path / "systemd.state"
    uname_file = tmp_path / "uname.override"
    uname_stub = bin_dir / "uname"
    uname_stub.write_text(
        '#!/bin/sh\nif [ -e "%s" ]; then cat "%s"; else echo "Darwin"; fi\n' % (uname_file, uname_file)
    )
    uname_stub.chmod(uname_stub.stat().st_mode | stat.S_IEXEC)
    for name in ("launchctl", "crontab"):
        stub = bin_dir / name
        stub.write_text(
            '#!/bin/sh\necho "%s $@" >> "%s"\n'
            'if [ "$1" = print ]; then [ -e "%s" ]; exit $?; fi\nexit 0\n' % (name, calls, marker)
        )
        stub.chmod(stub.stat().st_mode | stat.S_IEXEC)
    systemctl_stub = bin_dir / "systemctl"
    systemctl_stub.write_text(
        """#!/bin/sh
printf 'systemctl' >> '%s'
printf ' <%s>' "$@" >> '%s'
printf '\\n' >> '%s'
state=$(cat '%s' 2>/dev/null || echo inactive)
case "$2" in
  show)
    [ "$state" = query-failure ] && exit 42
    case "$state" in
      active) printf 'LoadState=loaded\\nActiveState=active\\nUnitFileState=disabled\\n' ;;
      enabled) printf 'LoadState=loaded\\nActiveState=inactive\\nUnitFileState=enabled\\n' ;;
      *) printf 'LoadState=not-found\\nActiveState=inactive\\nUnitFileState=\\n' ;;
    esac
    exit 0 ;;
  is-active)
    [ "$state" = active ] && exit 0
    [ "$state" = query-failure ] && exit 42
    exit 3 ;;
  is-enabled)
    [ "$state" = query-failure ] && exit 42
    [ "$state" = enabled ] && { printf 'enabled\\n'; exit 0; }
    printf 'disabled\\n'; exit 1 ;;
esac
exit 0
""" % (calls, "%s", calls, calls, systemd_state)
    )
    systemctl_stub.chmod(systemctl_stub.stat().st_mode | stat.S_IEXEC)
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
    ctx.systemd_state = systemd_state
    ctx.set_os = lambda os_name: uname_file.write_text(os_name + "\n")
    ctx.calls = lambda: calls.read_text().splitlines() if calls.exists() else []
    ctx.release = home / ".local/share/prw-local-usage/releases" / sha
    ctx.plist = home / "Library/LaunchAgents" / (LABEL + ".plist")
    ctx.staged = ctx.release / (LABEL + ".plist")
    ctx.systemd_user = home / ".config" / "systemd" / "user"
    ctx.service_dest = ctx.systemd_user / "prw-local-usage.service"
    ctx.timer_dest = ctx.systemd_user / "prw-local-usage.timer"
    ctx.staged_service = ctx.release / "prw-local-usage.service"
    ctx.staged_timer = ctx.release / "prw-local-usage.timer"

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
        assert bad not in done.stdout and bad not in done.stderr
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


def test_replace_while_loaded_boots_out_then_enables_then_bootstraps_collector_only(env):
    env.marker.write_text("")
    assert env.run("--replace", "--activate").returncode == 0
    target = "gui/%d/%s" % (os.getuid(), LABEL)
    calls = [c for c in env.calls() if c.split()[1] in ("bootout", "enable", "bootstrap")]
    assert [c.split()[1] for c in calls] == ["bootout", "enable", "bootstrap"]
    assert calls[0].endswith(target) and calls[1].endswith(target) and LABEL + ".plist" in calls[2]
    assert not any("dashboard" in c or OLD_LABEL.search(c) for c in env.calls())


def test_wrapper_exits_0_without_running_collector_when_lock_held(tmp_path):
    import fcntl

    rel = tmp_path / "rel"
    (rel / "scripts").mkdir(parents=True)
    wrapper = rel / "scripts" / "run_prw_local_usage.sh"
    wrapper.write_text((ROOT / "scripts" / "run_prw_local_usage.sh").read_text())
    ran = tmp_path / "ran"
    (rel / "scripts" / "prw_local_usage.py").write_text("open(%r, 'w').close()\n" % str(ran))
    state = tmp_path / "state"
    lock_dir = state / "prw-local-usage"
    lock_dir.mkdir(parents=True)
    env = dict(os.environ, HOME=str(tmp_path), XDG_STATE_HOME=str(state))
    with open(lock_dir / "run.lock", "a") as held:
        fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
        done = subprocess.run(["bash", str(wrapper)], env=env, capture_output=True, text=True)
    assert done.returncode == 0 and "lock" in done.stdout and not ran.exists()
    again = subprocess.run(["bash", str(wrapper)], env=env, capture_output=True, text=True)
    assert again.returncode == 0 and ran.exists()


def test_print_crontab_and_systemd_text_round_trip_awkward_words(env, tmp_path):
    import shlex

    home = tmp_path / "home dir"
    home.mkdir()
    remote = "file:///tmp/road%20map.git"
    machine = 'Mac "mini" $x'
    done = subprocess.run(
        ["bash", str(INSTALLER), "--source-repo", str(tmp_path / "source"), "--source-rev", env.sha,
         "--roadmap-remote", remote, "--machine", machine, "--print-crontab"],
        env=dict(env.env, HOME=str(home)), capture_output=True, text=True,
    )
    assert done.returncode == 0, done.stderr
    release = "%s/.local/share/prw-local-usage/releases/%s" % (home, env.sha)
    argv = ["/bin/bash", release + "/scripts/run_prw_local_usage.sh",
            "--publish-remote", remote, "--publish-branch", "main", "--machine", machine]

    cron = next(ln for ln in done.stdout.splitlines() if ln.startswith("37 "))
    assert re.search(r"(?<!\\)%", cron) is None  # every % is escaped for cron
    words = shlex.split(cron.replace("\\%", "%"))
    assert words[:5] == ["37", "*", "*", "*", "*"] and words[5].startswith("PATH=")
    assert words[6:] == argv

    unit = next(ln for ln in done.stdout.splitlines() if ln.startswith("ExecStart="))
    quoted = re.findall(r'"((?:[^"\\]|\\.)*)"', unit)
    assert unit == "ExecStart=" + " ".join('"%s"' % q for q in quoted)  # nothing outside double quotes
    unescaped = [re.sub(r"\\(.)", r"\1", q).replace("%%", "%").replace("$$", "$") for q in quoted]
    assert unescaped == argv
    assert "%%20" in unit


def test_linux_stage_only_creates_service_and_timer_under_release_without_systemctl(env):
    env.set_os("Linux")
    done = env.run()
    assert done.returncode == 0, done.stderr
    assert env.staged_service.exists()
    assert env.staged_timer.exists()
    assert not env.service_dest.exists()
    assert not env.timer_dest.exists()
    assert not env.systemd_user.exists()
    assert not any("systemctl" in c for c in env.calls())
    assert not env.plist.exists()
    service_txt = env.staged_service.read_text()
    assert "ExecStart=" in service_txt and "run_prw_local_usage.sh" in service_txt and env.sha in service_txt
    timer_txt = env.staged_timer.read_text()
    assert "OnCalendar=*:37:00" in timer_txt and "Persistent=true" in timer_txt and "WantedBy=timers.target" in timer_txt


def test_linux_activate_copies_staged_units_and_enables_timer(env):
    env.set_os("Linux")
    done = env.run("--activate")
    assert done.returncode == 0, done.stderr
    assert env.service_dest.exists()
    assert env.timer_dest.exists()
    calls = [c for c in env.calls() if c.startswith("systemctl")]
    daemon_reloads = [i for i, c in enumerate(calls) if "daemon-reload" in c]
    enables = [i for i, c in enumerate(calls) if "enable" in c and "--now" in c and "prw-local-usage.timer" in c]
    assert daemon_reloads and enables
    assert daemon_reloads[-1] < enables[-1]


def test_linux_activate_uses_absolute_xdg_config_home(env, tmp_path):
    env.set_os("Linux")
    config_home = tmp_path / "xdg-config"
    env.env["XDG_CONFIG_HOME"] = str(config_home)
    done = env.run("--activate")
    assert done.returncode == 0, done.stderr
    assert (config_home / "systemd/user/prw-local-usage.service").exists()
    assert (config_home / "systemd/user/prw-local-usage.timer").exists()
    assert not env.service_dest.exists()
    assert not env.timer_dest.exists()


def test_linux_refuses_when_timer_active_without_replace(env):
    env.set_os("Linux")
    env.systemd_state.write_text("active\n")
    done = env.run("--activate")
    assert done.returncode != 0
    assert "--replace" in done.stderr
    assert not env.timer_dest.exists()
    assert not env.release.exists()
    calls = [c for c in env.calls() if c.startswith("systemctl")]
    assert not any("launchctl" in c for c in env.calls())


def test_linux_refuses_when_timer_enabled_without_replace(env):
    env.set_os("Linux")
    env.systemd_state.write_text("enabled\n")
    done = env.run("--activate")
    assert done.returncode != 0
    assert "--replace" in done.stderr
    assert not env.timer_dest.exists()
    assert not env.release.exists()
    calls = [c for c in env.calls() if c.startswith("systemctl")]
    assert not any("<daemon-reload>" in c or "<enable>" in c for c in calls)


def test_linux_query_failure_preserves_existing_units_without_staging(env):
    env.set_os("Linux")
    env.systemd_state.write_text("query-failure\n")
    env.systemd_user.mkdir(parents=True)
    env.service_dest.write_text("existing service\n")
    env.timer_dest.write_text("existing timer\n")
    done = env.run("--activate")
    assert done.returncode != 0
    assert "systemctl" in done.stderr.lower()
    assert env.service_dest.read_text() == "existing service\n"
    assert env.timer_dest.read_text() == "existing timer\n"
    assert not env.release.exists()
    calls = [c for c in env.calls() if c.startswith("systemctl")]
    assert not any("<daemon-reload>" in c or "<enable>" in c or "<disable>" in c for c in calls)


def test_linux_replace_stops_and_disables_timer_before_reenabling(env):
    env.set_os("Linux")
    env.systemd_state.write_text("active\n")
    done = env.run("--replace", "--activate")
    assert done.returncode == 0, done.stderr
    assert env.service_dest.exists() and env.timer_dest.exists()
    calls = [c for c in env.calls() if c.startswith("systemctl")]
    disables = [i for i, c in enumerate(calls) if "<disable>" in c and "<--now>" in c]
    reloads = [i for i, c in enumerate(calls) if "daemon-reload" in c]
    enables = [i for i, c in enumerate(calls) if "enable" in c and "--now" in c and "prw-local-usage.timer" in c]
    assert disables and reloads and enables
    assert disables[0] < reloads[0] < enables[0]
    assert not any("prw-local-usage.service" in c and "disable" in c for c in calls)


def test_linux_staged_unit_escapes_line_breaks_in_argv(env):
    env.set_os("Linux")
    done = env.run("--machine", "first\nsecond\rthird")
    assert done.returncode == 0, done.stderr
    lines = env.staged_service.read_text().splitlines()
    exec_start = next(line for line in lines if line.startswith("ExecStart="))
    assert exec_start.endswith(r'"first\nsecond\rthird"')
