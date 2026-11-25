"""Play sound files from the repo's sounds/ folder.

Sounds play in the background (they never pause the robot), and any
problem -- no speaker, no player installed, missing file -- is logged and
otherwise ignored, so sound can never stop RobotOS from running.

Players used (standard Linux command-line tools):
  .wav  -> aplay    (package: alsa-utils)
  .mp3  -> mpg123   (package: mpg123)
"""

import io
import shutil
import subprocess
import sys
import threading
import wave
from pathlib import Path

SOUNDS_DIR = Path(__file__).resolve().parent.parent / "sounds"

# Which ALSA device to play on. None = the system default (set it in
# /etc/asound.conf). Or force one here, e.g. "plughw:1" for HDMI port 2.
DEVICE: str | None = None

# Silence added before each .wav sound. Many TVs mute the first fraction of
# a second of HDMI audio every time a sound starts. 0 to turn off.
LEAD_IN_SECONDS = 0.5

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


def with_lead_in(path: Path) -> bytes | None:
    """The .wav file's bytes with LEAD_IN_SECONDS of silence in front."""
    try:
        with wave.open(str(path), "rb") as src:
            params = src.getparams()
            audio = src.readframes(params.nframes)
        bytes_per_frame = params.nchannels * params.sampwidth
        # 8-bit WAV is unsigned, so its "silence" is 128 rather than 0.
        quiet = b"\x80" if params.sampwidth == 1 else b"\x00"
        silence = quiet * (int(params.framerate * LEAD_IN_SECONDS) * bytes_per_frame)
        out = io.BytesIO()
        with wave.open(out, "wb") as dst:
            dst.setparams(params)
            dst.writeframes(silence + audio)
        return out.getvalue()
    except Exception as exc:  # noqa: BLE001
        log(f"couldn't add lead-in to {path.name}, playing as-is: {exc}")
        return None


def timing(name: str) -> tuple[float, float]:
    """(seconds until sounds/<name> is actually heard, how long it lasts).

    Only known for .wav files; returns (0, 0) otherwise.
    """
    path = SOUNDS_DIR / name
    if path.suffix.lower() != ".wav":
        return 0.0, 0.0
    try:
        with wave.open(str(path), "rb") as f:
            return LEAD_IN_SECONDS, f.getnframes() / f.getframerate()
    except Exception:  # noqa: BLE001
        return 0.0, 0.0


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
            data = None
            if path.suffix.lower() == ".wav" and LEAD_IN_SECONDS > 0:
                data = with_lead_in(path)
            if data is not None:
                cmd[-1] = "-"   # aplay reads the padded sound from stdin
            result = subprocess.run(cmd, input=data,
                                    stdin=None if data is not None else subprocess.DEVNULL,
                                    stdout=subprocess.DEVNULL,
                                    stderr=subprocess.PIPE, timeout=120)
            if result.returncode != 0:
                err = result.stderr.decode(errors="replace").strip()
                log(f"{name} failed: {err[:200]}")
            else:
                log(f"played {name} ({' '.join(cmd[:-1])})")
        except Exception as exc:  # noqa: BLE001
            log(f"{name} failed: {exc}")

    threading.Thread(target=run, daemon=True).start()
    return True
