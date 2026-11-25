#!/usr/bin/env python3
"""RobotOS main program.

For now it draws the splash screen (an animated cat) and idles. This is
where the robot's real main loop will go later.

splash.txt format
-----------------
- The picture is split into frames by lines reading ``--- frame ---``.
  The first frame is the resting pose; the others are played in order and
  then back again, which makes the tail swish.
- Everything after a line reading ``=== text ===`` is shown, centered,
  under the picture. ``{version}`` and ``{update}`` are filled in.
- A file with no separators is shown as a plain, still splash screen.
"""

import os
import random
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

import sound

REPO_DIR = Path(__file__).resolve().parent.parent
SPLASH_FILE = REPO_DIR / "splash.txt"
STARTUP_SOUND = "startup.wav"    # any .wav or .mp3 in sounds/

FRAME_SEPARATOR = "--- frame ---"
TEXT_SEPARATOR = "=== text ==="

FRAME_SECONDS = 0.15             # time each frame of the swish is shown
SWISH_EVERY = (4.0, 12.0)        # random pause between swishes (seconds)

CLEAR_SCREEN = "\033[2J"
CURSOR_HOME = "\033[H"
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


def trim_blank(lines: list[str]) -> list[str]:
    while lines and not lines[0].strip():
        lines = lines[1:]
    while lines and not lines[-1].strip():
        lines = lines[:-1]
    return lines


def load_splash() -> tuple[list[list[str]], list[str]]:
    """Returns (frames, text_lines). Each frame is a list of lines."""
    try:
        raw = SPLASH_FILE.read_text(encoding="utf-8")
    except OSError:
        return [["RobotOS"]], ["(splash.txt missing)"]

    raw = raw.replace("{version}", version())
    raw = raw.replace("{update}", os.environ.get("ROBOTOS_UPDATE_STATUS", "n/a"))

    frames: list[list[str]] = [[]]
    text: list[str] = []
    in_text = False
    for line in raw.splitlines():
        line = line.rstrip()
        if line.strip() == TEXT_SEPARATOR:
            in_text = True
        elif in_text:
            text.append(line)
        elif line.strip() == FRAME_SEPARATOR:
            frames.append([])
        else:
            frames[-1].append(line)

    frames = [trim_blank(f) for f in frames]
    frames = [f for f in frames if f] or [[""]]

    # Make every frame the same height, padding at the top so the cat's
    # feet stay on the same line.
    height = max(len(f) for f in frames)
    frames = [[""] * (height - len(f)) + f for f in frames]
    return frames, trim_blank(text)


def swish_sequence(frame_count: int) -> list[int]:
    """Rest -> 1 -> 2 -> ... -> last -> ... -> 1 -> rest."""
    if frame_count < 2:
        return []
    forward = list(range(1, frame_count))
    return forward + forward[-2::-1] + [0]


class Screen:
    def __init__(self, frames: list[list[str]], text: list[str]):
        self.frames = frames
        self.text = text
        # Use the widest frame for all frames so the cat doesn't jump around.
        self.pic_width = max(len(line) for f in frames for line in f)

    def draw(self, frame_index: int, clear: bool = False) -> None:
        cols, rows = shutil.get_terminal_size(fallback=(80, 24))

        pic_left = max((cols - self.pic_width) // 2, 0)
        lines = [" " * pic_left + line.ljust(self.pic_width)
                 for line in self.frames[frame_index]]
        if self.text:
            lines.append("")
            lines += [line.strip().center(cols).rstrip() for line in self.text]

        top = max((rows - len(lines)) // 2, 0)
        # Pad each line to the screen width so it fully overwrites the
        # previous frame (no flicker from clearing the whole screen).
        lines = [""] * top + lines
        body = "\n".join(line[:cols].ljust(cols) for line in lines[:rows])

        sys.stdout.write((CLEAR_SCREEN if clear else "") + CURSOR_HOME + body)
        sys.stdout.flush()


def shutdown(*_: object) -> None:
    sys.stdout.write(SHOW_CURSOR + "\n")
    sys.stdout.flush()
    sys.exit(0)


def main() -> None:
    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    frames, text = load_splash()
    screen = Screen(frames, text)
    sequence = swish_sequence(len(frames))

    sys.stdout.write(HIDE_CURSOR)
    screen.draw(0, clear=True)
    sound.play(STARTUP_SOUND)

    # Placeholder main loop: swish the tail now and then. Replace/extend
    # with the robot's real control loop later.
    while True:
        time.sleep(random.uniform(*SWISH_EVERY))
        # Sometimes swish twice in a row.
        for _ in range(random.choice([1, 1, 2])):
            for index in sequence:
                screen.draw(index)
                time.sleep(FRAME_SECONDS)


if __name__ == "__main__":
    main()
