"""Helpers for subprocess tests that use a temporary home directory."""

import os
from pathlib import Path
from typing import Mapping


def isolated_home_environment(
    home: str | os.PathLike[str],
    *,
    cwd: str | os.PathLike[str] | None = None,
    base_environment: Mapping[str, str] | None = None,
) -> dict[str, str]:
    environment = dict(os.environ if base_environment is None else base_environment)
    if "PATH" in environment:
        host_home = os.environ.get("HOME") or os.path.expanduser("~")
        user_bin = os.path.realpath(os.path.join(host_home, ".local", "bin"))
        child_cwd = Path(cwd) if cwd is not None else Path.cwd()
        if not child_cwd.is_absolute():
            child_cwd = Path.cwd() / child_cwd
        fallback, preferred = [], []
        for entry in environment["PATH"].split(os.pathsep):
            candidate = entry or os.curdir
            if not os.path.isabs(candidate):
                candidate = os.path.join(child_cwd, candidate)
            resolved = os.path.realpath(candidate)
            target = fallback if resolved == user_bin else preferred
            target.append(entry)
        environment["PATH"] = os.pathsep.join(preferred + fallback)
    environment["HOME"] = os.fspath(home)
    return environment
