"""Play sound files from the repo's sounds/ folder.

Sounds play in the background (they never pause the robot), and any
problem -- no speaker, no player installed, missing file -- is logged and
otherwise ignored, so sound can never stop RobotOS from running.

Players used (standard Linux command-line tools):
  .wav  -> aplay    (package: alsa-utils)
  .mp3  -> mpg123   (package: mpg123)
"""

import shutil
import subprocess
import sys
import threading
from pathlib import Path

SOUNDS_DIR = Path(__file__).resolve().parent.parent / "sounds"

# Which ALSA device to play on. None = the system default (set it in
# /etc/asound.conf). Or force one here, e.g. "plughw:1" for HDMI port 2.
DEVICE: str | None = None

PLAYERS = {
    ".wav": ("aplay", "-q", "-D"),
    ".mp3": ("mpg123", "-q", "-a"),
}


def log(msg: str) -> None:
    # Under systemd stderr goes to the journal. In a terminal, stay quiet so
    # messages don't scribble over the splash screen.
    if not sys.stderr.isatty():
        print(f"[robotos-sound] {msg}", file=sys.stderr, flush=True)


def command_for(path: Path) -> list[str] | None:
    player = PLAYERS.get(path.suffix.lower())
    if player is None:
        log(f"don't know how to play {path.name}")
        return None
    program, quiet_flag, device_flag = player
    if shutil.which(program) is None:
        log(f"{program} not installed, can't play {path.name}")
        return None
    cmd = [program, quiet_flag]
    if DEVICE:
        cmd += [device_flag, DEVICE]
    return cmd + [str(path)]


def play(name: str) -> bool:
    """Start playing sounds/<name> in the background.

    Returns True if playback was started, False if it couldn't be.
    """
    path = SOUNDS_DIR / name
    if not path.is_file():
        log(f"missing sound file {path}")
        return False
    cmd = command_for(path)
    if cmd is None:
        return False

    def run() -> None:
        try:
            result = subprocess.run(cmd, stdin=subprocess.DEVNULL,
                                    stdout=subprocess.DEVNULL,
                                    stderr=subprocess.PIPE, text=True,
                                    timeout=120)
            if result.returncode != 0:
                log(f"{name} failed: {result.stderr.strip()[:200]}")
        except Exception as exc:  # noqa: BLE001
            log(f"{name} failed: {exc}")

    threading.Thread(target=run, daemon=True).start()
    return True
