"""Helpers for subprocess tests that use a temporary home directory."""

import os


def isolated_home_environment(home):
    environment = os.environ.copy()
    host_home = environment.get("HOME") or os.path.expanduser("~")
    user_bin = os.path.realpath(os.path.join(host_home, ".local", "bin"))
    fallback, preferred = [], []
    for entry in environment.get("PATH", "").split(os.pathsep):
        resolved = os.path.realpath(entry or os.curdir)
        target = fallback if resolved == user_bin else preferred
        target.append(entry)
    environment["PATH"] = os.pathsep.join(preferred + fallback)
    environment["HOME"] = str(home)
    return environment
