#!/usr/bin/env python3
"""parse_fields.py — JSON parser for runner-health.sh master script.

Usage:
  python3 parse_fields.py api "$API_JSON"   # extract api fields
  python3 parse_fields.py docker "$JSON"    # extract docker line
  python3 parse_fields.py lima "$JSON"      # extract lima line
  python3 parse_fields.py session_conflict "$JSON"  # extract session-conflict line
  python3 parse_fields.py verdict "$API" "$DOCKER" "$JEFF" ["$SESSION_CONFLICT"]  # compute verdict

Reads JSON from argv[2], outputs formatted text to stdout.
"""
import json
import sys


def _safe_json_loads(raw: str) -> dict:
    """Degrade any parse failure (empty string, invalid JSON, non-dict
    top-level value) to an empty dict instead of raising. An upstream
    check_*.sh script writing its error to stderr instead of stdout leaves
    runner-health.sh reading an empty (not missing) capture file for that
    check — every caller here must treat "" and "{}" identically, and a
    top-level JSON array must not propagate into `.get()` calls that
    assume a dict (see rev-1jtb5: PR #8193 round 3 only hardened this for
    the api/docker/jeff verdict path, not the display-line functions below
    or general non-dict JSON shapes).

    An empty string is the expected, silent "check reported nothing" case
    and degrades quietly. A NON-empty but malformed payload (garbage JSON,
    or valid JSON of the wrong shape) is warned to stderr rather than
    silently degrading: without this, a genuine upstream format regression
    would render as an ordinary "?" placeholder — visually identical to
    "field legitimately absent" — and pass unnoticed in the one tool meant
    to surface fleet problems (per /advice review on PR #8229)."""
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        print(f"WARNING: malformed JSON in runner-health capture: {raw[:200]!r}", file=sys.stderr)
        return {}
    if not isinstance(parsed, dict):
        print(f"WARNING: expected JSON object, got {type(parsed).__name__}: {raw[:200]!r}", file=sys.stderr)
        return {}
    return parsed


def api_fields(api_json: str) -> str:
    api = _safe_json_loads(api_json)
    on = api.get("runners", {}).get("online", "?")
    bu = api.get("runners", {}).get("busy", "?")
    lb = api.get("runners", {}).get("by_arch", {}).get("linux_x64", {}).get("busy", "?")
    mb = api.get("runners", {}).get("by_arch", {}).get("mac_arm64", {}).get("busy", "?")
    lo = api.get("runners", {}).get("by_arch", {}).get("linux_x64", {}).get("online", "?")
    mo = api.get("runners", {}).get("by_arch", {}).get("mac_arm64", {}).get("online", "?")
    return f"{on} {bu} {lb} {mb} {lo} {mo}"


def docker_line(docker_json: str) -> str:
    d = _safe_json_loads(docker_json)
    if d.get("error"):
        return f"error: {d['error']}"
    c = d.get("containers", {})
    up = c.get("up", "?")
    re_ = c.get("restarting", "?")
    return f"{up} up, {re_} restarting"


def lima_line(lima_json: str) -> str:
    d = _safe_json_loads(lima_json)
    if d.get("error"):
        return f"error: {d['error']}"
    i = d.get("instances", [])
    if not i:
        return "(no instances)"
    parts = ", ".join(f"{x.get('name')}={x.get('status')}" for x in i)
    return f"{len(i)} instance(s) — {parts}"


def jeff_line(jeff_json: str) -> str:
    d = _safe_json_loads(jeff_json)
    r = d.get("reachable", "?")
    if r is True:
        return "reachable"
    if r is False:
        return "UNREACHABLE (different wifi)"
    return "?"


def session_conflict_line(session_conflict_json: str) -> str:
    """Format check_session_conflict.sh output for the console table.

    Ported from closed PR #8033's check_github_session_state(): a runner
    container can show "Up" locally while GitHub reports status=offline
    (stale session/registration divergence). Neither ezgha serve's own
    churn-replacement nor the ezgha-watchdog fleet-size check catches this
    class — both only compare a local managed-container count against the
    configured target, and a session-conflicted container is still alive
    and still counted as "managed" locally.
    """
    d = _safe_json_loads(session_conflict_json)
    if d.get("error"):
        return f"error: {d['error']}"
    conflicts = d.get("session_conflicts", [])
    if conflicts:
        return f"{len(conflicts)} SESSION CONFLICT(S): {', '.join(conflicts)} (manual heal required)"
    invalid_names = d.get("invalid_names") or []
    if invalid_names:
        return f"{len(invalid_names)} invalid runner name(s) rejected: {', '.join(invalid_names)}"
    unverified = (d.get("docker_unavailable") or []) + (d.get("ssh_unreachable") or [])
    if unverified:
        return f"{len(unverified)} offline runner(s) unverified: {', '.join(unverified)}"
    offline_count = d.get("offline_count", 0)
    if offline_count:
        return f"{offline_count} offline (no session conflicts — ezgha will respawn)"
    return "none (all runners online)"


def _json_object_or_empty(raw_json: str) -> dict:
    try:
        parsed = json.loads(raw_json) if raw_json else {}
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _session_conflict_verdict(session_conflict: dict) -> str | None:
    # Session conflicts (ported from closed PR #8033 — see
    # check_session_conflict.sh) take priority over every other verdict
    # branch below: a container Up but GitHub offline is invisible to both
    # ezgha serve's own churn-replacement and the ezgha-watchdog fleet-size
    # check, so it needs its own distinct, actionable RED rather than being
    # folded into (or hidden by) the per-arch online-count logic.
    conflicts = session_conflict.get("session_conflicts") or []
    if conflicts:
        return (
            f"RED|SESSION CONFLICT: {', '.join(conflicts)} — container Up but GitHub "
            "offline; ezgha will NOT fix this (still counts it as locally managed), "
            "manual heal required (delete GH registration + restart container)"
        )
    return None


def compute_verdict(api_json: str, docker_json: str, jeff_json: str, session_conflict_json: str = "{}") -> str:
    """Verdict for an ezgha-managed fleet: 16 Linux + 6 Mac = 22 total expected.

    Healthy floor (allowing ~2 churn slots in transient deregister window):
      Linux >= 14, Mac >= 5, total online >= 19
    Critical floor (ezgha serve stuck, restart needed):
      Linux < 10 OR Mac < 4

    Verdict logic is split per-arch so the reason names the failing host —
    fixes become obvious: restart launchctl org.jleechanorg.ezgha on Mac,
    or `systemctl --user restart ezgha` on jeff-ubuntu.
    """
    # Defense-in-depth: an upstream capture failure (e.g. runner-health.sh
    # reading an empty stdout file from a crashed/errored check script) can
    # hand us "" instead of a valid JSON document. _safe_json_loads degrades
    # a parse failure (or a non-dict top-level value) to the same
    # "unavailable" shape the "runner data missing" guard below already
    # expects, instead of crashing the whole verdict call.
    api = _safe_json_loads(api_json)
    docker = _safe_json_loads(docker_json)
    jeff = _safe_json_loads(jeff_json)
    session_conflict = _safe_json_loads(session_conflict_json)

    session_conflict_verdict = _session_conflict_verdict(session_conflict)
    if session_conflict_verdict:
        return session_conflict_verdict

    runners_raw = api.get("runners")
    by_arch = runners_raw.get("by_arch", {}) if isinstance(runners_raw, dict) else {}

    # Distinguish "field genuinely reported as low/zero" from "field absent
    # because the upstream check_api.sh call failed" (auth error, rate limit,
    # empty gh api response -> runner-health.sh falls back to API_JSON='{}').
    # Without this guard, `linux.get("online", 0)` silently defaults an
    # unavailable reading to the same value (0) as a confirmed-empty fleet,
    # which would satisfy the host-dark RED check below via a totally
    # different trigger (upstream data-collection failure) than the one it
    # was designed to catch (a confirmed-dark host).
    if not isinstance(runners_raw, dict) or "linux_x64" not in by_arch:
        return (
            "AMBER|API data unavailable — check_api.sh returned no runner data "
            "(auth failure, rate limit, or empty gh api response); fleet state "
            "cannot be confirmed, do NOT assume host dark"
        )

    runners = runners_raw
    linux = by_arch.get("linux_x64", {})
    mac = runners.get("by_arch", {}).get("mac_arm64", {})
    linux_online = linux.get("online", 0)
    mac_online = mac.get("online", 0)
    linux_busy = linux.get("busy", 0)
    mac_busy = mac.get("busy", 0)
    total_online = runners.get("online", 0)
    total_busy = runners.get("busy", 0)
    de = docker.get("error") or ""
    jr = jeff.get("reachable", "?")
    restarting = docker.get("containers", {}).get("restarting", 0)

    expected_linux = 16
    expected_mac = 6
    healthy_floor_linux = 14  # 2 churn slots allowed
    healthy_floor_mac = 5     # 1 churn slot allowed
    critical_floor_linux = 10
    critical_floor_mac = 4

    # CRITICAL: jeff-ubuntu host dark — Linux fleet offline + SSH unreachable.
    # Three-signal confirmation: 0 busy alone is not enough — a fully
    # healthy-but-idle fleet (overnight/weekend, no active CI jobs) combined
    # with an operator on a different wifi (SSH commonly unreachable, on its
    # own benign) would otherwise false-positive here. Require linux_online
    # to ALSO be critically low before calling the host dark; a high online
    # count with 0 busy + unreachable SSH is a healthy-idle fleet and should
    # fall through to the GREEN/AMBER logic below instead.
    if (
        jr is False
        and linux_busy == 0
        and (not isinstance(linux_online, int) or linux_online < critical_floor_linux)
    ):
        result = "RED|jeff-ubuntu host dark — 0 Linux runners busy + SSH unreachable (do NOT restart containers, wait for host)"

    # CRITICAL: severe shortage (supervisor stuck on one or both hosts).
    elif isinstance(linux_online, int) and linux_online < critical_floor_linux:
        result = f"RED|Linux fleet critically low: {linux_online}/{expected_linux} online — `systemctl --user restart ezgha` on jeff-ubuntu"
    elif isinstance(mac_online, int) and mac_online < critical_floor_mac:
        result = f"RED|Mac fleet critically low: {mac_online}/{expected_mac} online — `launchctl kickstart -k gui/$(id -u)/org.jleechanorg.ezgha`"

    # AMBER: minor shortage — likely ezgha serve stuck, needs restart.
    elif isinstance(linux_online, int) and linux_online < healthy_floor_linux:
        result = f"AMBER|Linux fleet short: {linux_online}/{expected_linux} online (ezgha serve likely stuck — restart ezgha.service on jeff-ubuntu)"
    elif isinstance(mac_online, int) and mac_online < healthy_floor_mac:
        result = f"AMBER|Mac fleet short: {mac_online}/{expected_mac} online (ezgha serve likely stuck — `launchctl kickstart -k gui/$(id -u)/org.jleechanorg.ezgha`)"

    # AMBER: docker restart loops indicate container-level crashes.
    elif restarting and restarting > 0:
        result = f"AMBER|{restarting} container(s) in restart loop"

    # AMBER: no work flowing (everything idle).
    elif isinstance(total_busy, int) and total_busy == 0:
        result = "AMBER|0 runners busy (no active jobs — fleet healthy but unused)"

    # AMBER: docker error.
    elif de:
        result = f"AMBER|Docker error: {de}"

    # GREEN: full or near-full fleet, all online are busy.
    else:
        result = f"GREEN|{total_online}/22 online ({linux_online}/{expected_linux} Linux + {mac_online}/{expected_mac} Mac), {total_busy}/{total_online} busy ({linux_busy} Linux + {mac_busy} Mac busy)"

    session_conflict_error = session_conflict.get("error")
    if session_conflict_error and not result.startswith("RED|"):
        return (
            "AMBER|Session-conflict check unavailable: "
            f"{session_conflict_error}; fleet state cannot be confirmed"
        )

    invalid_names = session_conflict.get("invalid_names") or []
    if invalid_names and not result.startswith("RED|"):
        return (
            "AMBER|Session-conflict check rejected invalid runner name metadata: "
            f"{', '.join(invalid_names)}; fleet state cannot be confirmed"
        )

    unverified = (session_conflict.get("docker_unavailable") or []) + (
        session_conflict.get("ssh_unreachable") or []
    )
    if unverified and not result.startswith("RED|"):
        return (
            "AMBER|Session-conflict check could not inspect offline runner(s): "
            f"{', '.join(unverified)}; fleet state cannot be confirmed"
        )

    return result


def main():
    if len(sys.argv) < 2:
        print(
            "usage: parse_fields.py {api|docker|lima|jeff|session_conflict|verdict} <json> [more json]",
            file=sys.stderr,
        )
        sys.exit(1)
    cmd = sys.argv[1]
    if cmd == "api":
        print(api_fields(sys.argv[2]))
    elif cmd == "docker":
        print(docker_line(sys.argv[2]))
    elif cmd == "lima":
        print(lima_line(sys.argv[2]))
    elif cmd == "jeff":
        print(jeff_line(sys.argv[2]))
    elif cmd == "session_conflict":
        print(session_conflict_line(sys.argv[2]))
    elif cmd == "verdict":
        session_conflict_json = sys.argv[5] if len(sys.argv) > 5 else "{}"
        result = compute_verdict(sys.argv[2], sys.argv[3], sys.argv[4], session_conflict_json)
        print(result)
    else:
        print(f"unknown command: {cmd}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
