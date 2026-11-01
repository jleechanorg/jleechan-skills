#!/usr/bin/env python3
"""Render private, inactive per-account launchd or systemd schedules."""
import argparse
import html
import json
import os
import plistlib
import re
import stat
import sys
from pathlib import Path

MAC_MINUTES = (0, 20, 40)
LINUX_MINUTES = (30, 50, 10)
MODES = ("main", "proceed")
DIRECTIVES = {
    "main": "Coordination mode: main. Use the periodic reminder for this mode. ",
    "proceed": ("Coordination mode: proceed. Use the proceed nudge outbound text from SKILL.md "
                "and read the last 20 rendered messages for destination and duplicate checks. "),
}
MODE_DECLARATION = re.compile(r"coordination\s+mode\s*:", re.IGNORECASE)
IDENTITY = re.compile(r"[0-9a-fA-F]{64}\Z")
ACCOUNT = re.compile(r"[A-Za-z0-9._@+-]{1,160}\Z")
HOST_LABEL = re.compile(r"[A-Za-z0-9._-]{1,64}\Z")
TEMPLATES = Path(__file__).resolve().parents[1] / "templates"


def fail(message):
    raise ValueError(message)


def private_json(path):
    path = Path(path).expanduser()
    if stat.S_IMODE(path.stat().st_mode) & 0o077:
        fail("configuration must have mode 0600 or stricter")
    return json.loads(path.read_text())


def systemd_value(value):
    if any(ord(c) < 32 or ord(c) == 127 for c in value):
        fail("configuration values cannot contain control characters")
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"').replace("$", "\\$").replace("`", "\\`") + '"'


def scheduled_runs(rows):
    """Expand each account into its declared main run plus its proceed runs, on disjoint minutes."""
    runs, taken = [], set()
    for row in rows:
        if MODE_DECLARATION.search(row["task"]):
            fail("account task must not declare its own coordination mode")
        extra = row.get("proceed_minutes", [])
        if (not isinstance(extra, list)
                or any(type(minute) is not int or not 0 <= minute <= 59 for minute in extra)
                or len(set(extra)) != len(extra)):
            fail("proceed_minutes must be a list of unique whole minutes from 0 to 59")
        for minute, mode in [(row["minute"], "main")] + [(minute, "proceed") for minute in extra]:
            if minute in taken:
                fail("scheduled runs must use distinct minutes within the hour")
            taken.add(minute)
            runs.append((row, minute, mode, DIRECTIVES[mode] + row["task"]))
    return runs


def configured_minutes(config, host):
    """Host cadence: an explicit `minutes` list wins over the platform default."""
    default = MAC_MINUTES if host == "macos" else LINUX_MINUTES
    minutes = config.get("minutes", list(default))
    if (not isinstance(minutes, list) or len(minutes) != 3
            or any(type(minute) is not int or not 0 <= minute <= 59 for minute in minutes)
            or len(set(minutes)) != 3):
        fail("minutes must be three distinct whole minutes from 0 to 59")
    return tuple(minutes)


def configured_hosts(config, host_label, host_priority):
    """Optional host map: label -> priority, so a run can rank peers it can only see by label."""
    hosts = config.get("hosts")
    if hosts is not None and not host_label:
        fail("a hosts map requires host_label so this host can be ranked")
    if hosts is None:
        if host_priority > 1:
            fail("a host with host_priority above 1 requires host_label and a complete hosts map")
        return host_priority, None
    if not isinstance(hosts, list) or len(hosts) < 2:
        fail("hosts must list at least two {label, priority} entries")
    labels, priorities = set(), set()
    for entry in hosts:
        if not isinstance(entry, dict):
            fail("hosts entries must be objects with label and priority")
        label, priority = entry.get("label"), entry.get("priority")
        if not isinstance(label, str) or not HOST_LABEL.fullmatch(label):
            fail("hosts labels must match [A-Za-z0-9._-]{1,64}")
        if type(priority) is not int or not 1 <= priority <= 9:
            fail("hosts priorities must be whole numbers from 1 to 9")
        if label.lower() in labels or priority in priorities:
            fail("hosts must have unique labels (case-insensitive) and unique priorities")
        labels.add(label.lower())
        priorities.add(priority)
    if (host_label or "").lower() not in labels:
        fail("host_label must appear in hosts")
    own = next(entry["priority"] for entry in hosts if entry["label"].lower() == (host_label or "").lower())
    ordered = sorted(hosts, key=lambda entry: entry["priority"])
    return own, ",".join(f"{entry['label']}={entry['priority']}" for entry in ordered)


def configured_cli(config):
    if "cli" in config and "pi_bin" in config:
        fail("configure either cli or pi_bin, not both")
    cli = config.get("cli", {"executable": config.get("pi_bin", ""), "args": []})
    if not isinstance(cli, dict) or not isinstance(cli.get("executable"), str):
        fail("cli must name an executable and optional arguments")
    args = cli.get("args", [])
    if not isinstance(args, list) or any(not isinstance(arg, str) or any(ord(c) < 32 or ord(c) == 127 for c in arg) for arg in args):
        fail("CLI arguments must be an array of strings without control characters")
    return Path(cli["executable"]).expanduser(), args


def node22_bins(home):
    nvm = Path(home) / ".nvm/versions/node"
    versions = [p for p in nvm.glob("v22.*") if (p / "bin/node").is_file()] if nvm.is_dir() else []
    versions.sort(key=lambda p: tuple(map(int, p.name[1:].split("."))), reverse=True)
    preferred = nvm / "v22.22.0"
    if preferred in versions:
        versions.remove(preferred)
        versions.insert(0, preferred)
    return [p / "bin" for p in versions]


def render(config_path, output, host):
    config = private_json(config_path)
    if config.get("version") != 1 or config.get("host_role") != host:
        fail("configuration version or host role does not match")
    minutes = configured_minutes(config, host)
    rows = config.get("accounts")
    if not isinstance(rows, list) or len(rows) != 3:
        fail("exactly three ordered account bindings are required")
    home = Path.home()
    dot_path = Path(config.get("dot_config_file", "~/.config/dot/config.json")).expanduser()
    dot = private_json(dot_path)
    dot_accounts = dot.get("accounts", {})
    keys = set()
    for index, row in enumerate(rows):
        if (not isinstance(row, dict) or not ACCOUNT.fullmatch(str(row.get("key", ""))) or
                row["key"] in keys or row.get("minute") != minutes[index] or
                not IDENTITY.fullmatch(str(row.get("identity_sha256", ""))) or
                not isinstance(row.get("task"), str) or not row["task"].strip() or
                "\n" in row["task"] or "\r" in row["task"]):
            fail("account bindings must match the ordered host cadence and include identity and task")
        keys.add(row["key"])
        details = dot_accounts.get(row["key"])
        if not isinstance(details, dict) or not details.get("user_data_dir"):
            fail("a scheduled account is missing from Dot configuration")
    runs = scheduled_runs(rows)
    takeover_hours = config.get("takeover_hours", 2)
    if type(takeover_hours) is not int or not 1 <= takeover_hours <= 48:
        fail("takeover_hours must be a whole number of hours from 1 to 48")
    host_priority = config.get("host_priority", 1)
    if type(host_priority) is not int or not 1 <= host_priority <= 9:
        fail("host_priority must be a whole number from 1 to 9")
    host_label = config.get("host_label")
    if host_label is not None and (not isinstance(host_label, str) or not HOST_LABEL.fullmatch(host_label)):
        fail("host_label must match [A-Za-z0-9._-]{1,64}")
    host_priority, host_map = configured_hosts(config, host_label, host_priority)
    pi, cli_args = configured_cli(config)
    mcp = Path(config.get("chrome_devtools_mcp_js", "")).expanduser()
    if not pi.is_absolute() or not pi.is_file() or not os.access(pi, os.X_OK):
        fail("configured PI_BIN must be an executable file")
    if not mcp.is_absolute() or not mcp.is_file():
        fail("configured Chrome DevTools MCP entrypoint is unavailable")
    package = json.loads((mcp.parents[3] / "package.json").read_text())
    if package.get("version") != "1.6.0":
        fail("Chrome DevTools MCP must be version 1.6.0")
    output = Path(output).expanduser().resolve()
    if not output.is_relative_to(Path("/tmp").resolve()):
        fail("staging output must be under /tmp")
    if os.path.lexists(output):
        fail("render destination already exists; choose a new staging directory")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.mkdir(mode=0o700)
    node_bins = node22_bins(home)
    if not node_bins:
        fail("Node 22 from nvm is unavailable")
    path = f"{os.pathsep.join(map(str, node_bins))}{os.pathsep}{home / '.local/bin'}:/usr/local/bin:/usr/bin:/bin"
    if host == "macos":
        path += ":/opt/homebrew/bin"
    for row, minute, mode, task in runs:
        key, suffix = row["key"], "" if mode == "main" else "-proceed"
        env = {
            "DOT_CONFIG_FILE": str(dot_path),
            "DOT_EXPECTED_IDENTITY_SHA256": row["identity_sha256"],
            "COORDINATOR_MODE": mode,
            **({"COORDINATOR_HOST_LABEL": host_label} if host_label else {}),
            "COORDINATOR_TAKEOVER_HOURS": str(takeover_hours),
            "COORDINATOR_HOST_PRIORITY": str(host_priority),
            **({"COORDINATOR_HOST_PRIORITIES": host_map} if host_map else {}),
            "COORDINATOR_TASK": task,
            "PI_BIN": str(pi),
            "COORDINATOR_CLI_ARGS": json.dumps(cli_args),
            "CHROME_DEVTOOLS_MCP_JS": str(mcp),
            "PATH": path,
        }
        if host == "macos":
            label = f"ai.dot-coordinator.{minute:02d}{suffix}"
            substitutions = {"@HOME@": str(home), "@MINUTE@": f"{minute:02d}", "@ACCOUNT@": key,
                             "@DOT_CONFIG_FILE@": str(dot_path), "@IDENTITY_SHA256@": row["identity_sha256"],
                             "@TASK@": task, "@MODE@": mode, "@HOST_LABEL@": host_label or "", "@TAKEOVER_HOURS@": str(takeover_hours), "@HOST_PRIORITY@": str(host_priority), "@PI_BIN@": str(pi), "@MCP_JS@": str(mcp), "@PATH@": path}
            source = (TEMPLATES / "launchd-agent.plist.in").read_text()
            for token, value in substitutions.items():
                source = source.replace(token, html.escape(value, quote=False))
            plist = plistlib.loads(source.encode())
            plist["Label"] = label
            plist["ProgramArguments"] = ["/bin/bash", str(home / ".claude/skills/dot-coordinator/scripts/dot-coordinator-wrapper.sh"), "--account", key]
            plist["EnvironmentVariables"] = env
            plist["StartCalendarInterval"] = {"Minute": minute}
            plist["StandardOutPath"] = str(home / f".local/state/ai.gemini.agy-dot-coordinator/{minute:02d}{suffix}.out.log")
            plist["StandardErrorPath"] = str(home / f".local/state/ai.gemini.agy-dot-coordinator/{minute:02d}{suffix}.err.log")
            write_private(output / f"{label}.plist", plistlib.dumps(plist))
        else:
            unit = f"ai.dot-coordinator-{minute:02d}{suffix}"
            for name in ("DISPLAY", "DBUS_SESSION_BUS_ADDRESS", "XDG_RUNTIME_DIR"):
                if os.environ.get(name):
                    env[name] = os.environ[name]
            write_private(output / f"{unit}.env", "\n".join(f"{k}={systemd_value(v)}" for k, v in env.items()) + "\n")
            service = (TEMPLATES / "systemd-coordinator.service.in").read_text().replace("@ACCOUNT@", key).replace("@UNIT@", unit).replace("@MODE@", mode)
            timer = (TEMPLATES / "systemd-coordinator.timer.in").read_text().replace("@ACCOUNT@", key).replace("@UNIT@", unit).replace("@MINUTE@", f"{minute:02d}")
            write_private(output / f"{unit}.service", service)
            write_private(output / f"{unit}.timer", timer)
    return output


def write_private(path, content):
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    fd = os.open(path, flags, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(content if isinstance(content, bytes) else content.encode())
        stream.flush()
        os.fsync(stream.fileno())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, help="private machine-local schedule JSON")
    parser.add_argument("--output", required=True, help="new private inactive staging directory")
    parser.add_argument("--host", choices=("macos", "linux"), required=True)
    args = parser.parse_args()
    try:
        result = render(args.config, args.output, args.host)
        print(f"Rendered inactive {args.host} schedule into {result}")
        return 0
    except (OSError, ValueError, KeyError, json.JSONDecodeError, IndexError) as error:
        print(f"Schedule render blocked: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
