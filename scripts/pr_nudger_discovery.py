"""Read cmux session bindings for exact worktree roots."""

from collections import defaultdict
import json
from pathlib import Path
import subprocess


def _cmux_json(*args, strict=False, cmux="cmux"):
    try:
        output = subprocess.check_output(
            (cmux, *args, "--json"), text=True, stderr=subprocess.PIPE, timeout=3
        )
        result = json.loads(output)
        if not isinstance(result, dict):
            raise ValueError("Expected cmux JSON object")
        return result
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        if strict:
            raise ValueError("cmux owner inventory unavailable") from exc
        return {}


def terminal_surfaces(cmux="cmux", strict=False):
    tree = _cmux_json("--id-format", "both", "tree", "--all", strict=strict, cmux=cmux)
    def children(node, key):
        entries = node.get(key, None if strict else [])
        if not isinstance(entries, list):
            raise ValueError(f"cmux {key} inventory unavailable")
        return entries

    return [
        (workspace["ref"], surface["ref"], workspace.get("id"), surface.get("id"),
         (surface.get("tty") or "").removeprefix("/dev/"))
        for window in children(tree, "windows")
        for workspace in children(window, "workspaces")
        for pane in children(workspace, "panes")
        for surface in children(pane, "surfaces")
        if surface.get("type") == "terminal"
    ]


def surface_claims(roots, ws, sf, strict=False, cmux="cmux"):
    info = _cmux_json("surface", "resume", "show", "--workspace", ws,
                      "--surface", sf, strict=strict, cmux=cmux)
    if (info.get("workspace_ref"), info.get("surface_ref")) == (ws, sf) and (
        {"resume_binding", "restore_record"} & info.keys()
    ):
        return _surface_owners(roots, ws, sf, info)
    if strict:
        raise ValueError("cmux session binding unavailable")
    return ()


def discover_owners(paths, strict=False, surfaces=None, cmux="cmux"):
    """Return current cmux claims grouped by canonical cwd."""
    roots = {Path(path).expanduser().resolve() for path in paths}
    owners = defaultdict(list)
    if roots:
        if surfaces is None:
            surfaces = terminal_surfaces(cmux, strict)
        for ws, sf, *_ in surfaces:
            for owner in surface_claims(roots, ws, sf, strict, cmux):
                owners[owner["cwd"]].append(owner)
    return dict(owners)


def _surface_owners(roots, ws, sf, info):
    claims = {}
    for record_key, cwd_key in (("restore_record", "working_directory"), ("resume_binding", "cwd")):
        record = info.get(record_key) or {}
        cli, session, cwd = (record.get(key) for key in ("kind", "checkpoint_id", cwd_key))
        if not all(isinstance(value, str) and value for value in (cli, session, cwd)):
            continue
        path = Path(cwd)
        if not path.is_absolute() or (path := path.resolve()) not in roots:
            continue
        key = (str(path), cli, session)
        owner = claims.setdefault(key, dict(cwd=str(path), cli=cli, session=session,
                                            workspace=ws, surface=sf, cmux_discovered=True))
        env_key = {"codex": "CODEX_HOME", "claude": "CLAUDE_CONFIG_DIR"}.get(cli)
        launch = record.get("launch_command") or {}
        profile = ((launch.get("environment") or {}).get(env_key)
                   or (record.get("environment") or {}).get(env_key))
        if isinstance(profile, str) and Path(profile).is_absolute():
            if owner.get("profile_dir", profile) == profile:
                owner["profile_dir"] = profile
            else:
                claims[(*key, profile)] = dict(owner, profile_dir=profile)
    return claims.values()
