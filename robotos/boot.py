#!/usr/bin/env python3
"""RobotOS boot entry point (run by systemd at startup).

1. Try to update this repository from GitHub (git fetch + reset to origin).
2. Whether or not the update worked, hand off to main.py in a *fresh*
   Python process so any newly pulled code is the code that runs.

Only the standard library is used, so nothing extra has to be installed.
"""

import os
import socket
import subprocess
import sys
import time
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parent.parent
MAIN = REPO_DIR / "robotos" / "main.py"

# Self-update discards local changes, so only do it in the Pi's install
# location -- never in a development checkout. Set ROBOTOS_SELF_UPDATE=1 to
# force it elsewhere.
INSTALL_DIR = Path("/opt/robotos")

NETWORK_WAIT_SECONDS = 20   # how long to wait for wifi at boot
GIT_TIMEOUT_SECONDS = 30    # max time for any single git command


def log(msg: str) -> None:
    # stderr goes to the journal under systemd (journalctl -u robotos).
    print(f"[robotos-boot] {msg}", file=sys.stderr, flush=True)


def git(*args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(REPO_DIR), *args],
        capture_output=True,
        text=True,
        timeout=GIT_TIMEOUT_SECONDS,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"git {' '.join(args)} failed")
    return result.stdout.strip()


def wait_for_network(timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            socket.create_connection(("github.com", 443), timeout=3).close()
            return True
        except OSError:
            time.sleep(1)
    return False


def try_update() -> str:
    """Returns a short human-readable status; never raises."""
    try:
        if REPO_DIR != INSTALL_DIR and os.environ.get("ROBOTOS_SELF_UPDATE") != "1":
            return f"skipped (dev copy, not {INSTALL_DIR})"
        if not (REPO_DIR / ".git").exists():
            return "skipped (not a git checkout)"
        if not wait_for_network(NETWORK_WAIT_SECONDS):
            return "skipped (no network)"

        branch = git("rev-parse", "--abbrev-ref", "HEAD")
        before = git("rev-parse", "--short", "HEAD")
        git("fetch", "--quiet", "origin", branch)
        # The Pi is a deployment target: GitHub is the source of truth, so
        # discard any local edits rather than risk a merge conflict at boot.
        git("reset", "--hard", "--quiet", f"origin/{branch}")
        after = git("rev-parse", "--short", "HEAD")

        if before == after:
            return f"up to date ({after})"
        return f"updated {before} -> {after}"
    except Exception as exc:  # noqa: BLE001 - any failure must not stop boot
        return f"failed ({exc.__class__.__name__}: {str(exc)[:80]})"


def main() -> None:
    log("checking for updates...")
    status = try_update()
    log(f"update {status}")

    # Pass the status along so the splash screen can show it.
    env = dict(os.environ, ROBOTOS_UPDATE_STATUS=status)
    os.execve(sys.executable, [sys.executable, str(MAIN)], env)


if __name__ == "__main__":
    main()
