#!/usr/bin/env python3
"""RobotOS main program.

For now it just draws the splash screen and then idles. This is where the
robot's real main loop will go later.
"""

import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parent.parent
SPLASH_FILE = REPO_DIR / "splash.txt"

CLEAR_SCREEN = "\033[2J\033[H"
HIDE_CURSOR = "\033[?25l"
SHOW_CURSOR = "\033[?25h"


def version() -> str:
    try:
        return subprocess.run(
            ["git", "-C", str(REPO_DIR), "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=5,
        ).stdout.strip() or "unknown"
    except Exception:  # noqa: BLE001
        return "unknown"


def load_splash() -> str:
    try:
        return SPLASH_FILE.read_text(encoding="utf-8").rstrip("\n")
    except OSError:
        return "RobotOS\n(splash.txt missing)"


def render(text: str) -> str:
    """Center the splash text on the screen, horizontally and vertically."""
    cols, rows = shutil.get_terminal_size(fallback=(80, 24))
    lines = text.splitlines()
    width = max((len(line) for line in lines), default=0)
    left = max((cols - width) // 2, 0)
    top = max((rows - len(lines)) // 2, 0)
    body = "\n".join(" " * left + line for line in lines)
    return "\n" * top + body


def show_splash() -> None:
    splash = load_splash()
    splash = splash.replace("{version}", version())
    splash = splash.replace("{update}", os.environ.get("ROBOTOS_UPDATE_STATUS", "n/a"))
    sys.stdout.write(CLEAR_SCREEN + HIDE_CURSOR + render(splash) + "\n")
    sys.stdout.flush()


def shutdown(*_: object) -> None:
    sys.stdout.write(SHOW_CURSOR)
    sys.stdout.flush()
    sys.exit(0)


def main() -> None:
    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    show_splash()

    # Placeholder main loop: keep the process alive so systemd sees RobotOS
    # as running. Replace with the robot's real control loop later.
    while True:
        time.sleep(1)


if __name__ == "__main__":
    main()
