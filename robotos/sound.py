"""Play sound files from the repo's sounds/ folder.

RobotOS keeps ONE audio stream open to the speaker for as long as it runs,
and plays sounds into it. TVs take about a second to switch their speakers
on whenever HDMI audio starts, so a stream that starts fresh for every sound
loses short sounds entirely. With the stream always open, the TV wakes up
once at startup and every sound after that plays in full, almost instantly.

Sounds never pause the robot, and any problem -- no speaker, no player
installed, missing file, stream dropped -- is logged and otherwise ignored
(the stream reopens itself), so sound can never stop RobotOS from running.

Supported files: .wav (any rate / channels / bit depth) and .mp3 (needs the
mpg123 package). Everything is converted to 48 kHz 16-bit stereo.
"""

import array
import fcntl
import random
import shutil
import subprocess
import sys
import threading
import time
import wave
from collections import deque
from pathlib import Path

SOUNDS_DIR = Path(__file__).resolve().parent.parent / "sounds"

# ALSA device to play on. "plughw:0" = the Pi's first HDMI port (where the TV
# is). When the speaker amp is fitted it gets its own card number -- check
# `aplay -l` and change this.
DEVICE = "plughw:0"

# Faint hiss sent between sounds so the TV never decides the stream has gone
# quiet and switches its speakers off. ~-60 dB: inaudible. 0 = pure silence.
KEEPALIVE_LEVEL = 30

RATE = 48000                  # stream format: 48 kHz, 16-bit, stereo
CHUNK_FRAMES = RATE // 50     # write 20 ms at a time
BUFFER_SECONDS = 0.2          # aplay's buffer; also roughly the playback delay
RETRY_SECONDS = 5.0           # wait before reopening a stream that dropped

F_SETPIPE_SZ = 1031           # Linux fcntl: shrink the pipe so sounds start sooner


def log(msg: str) -> None:
    # Under systemd stderr goes to the journal. In a terminal, stay quiet so
    # messages don't scribble over the splash screen.
    if not sys.stderr.isatty():
        print(f"[robotos-sound] {msg}", file=sys.stderr, flush=True)


# ---------------------------------------------------------------- decoding

def _to_16bit(raw: bytes, width: int) -> array.array:
    if width == 2:
        return array.array("h", raw)
    if width == 1:   # 8-bit WAV is unsigned
        return array.array("h", ((b - 128) << 8 for b in raw))
    # 24/32-bit: keep the top two bytes of each little-endian sample
    out = bytearray()
    for i in range(0, len(raw), width):
        out += raw[i + width - 2:i + width]
    return array.array("h", bytes(out))


def _to_stereo(samples: array.array, channels: int) -> array.array:
    if channels == 2:
        return samples
    frames = len(samples) // channels
    left = samples[0::channels]
    right = samples[1::channels] if channels > 1 else left
    out = array.array("h", bytes(4 * frames))
    out[0::2] = left[:frames]
    out[1::2] = right[:frames]
    return out


def _resample(stereo: array.array, rate: int) -> array.array:
    if rate == RATE:
        return stereo
    frames_in = len(stereo) // 2
    frames_out = int(frames_in * RATE / rate)
    out = array.array("h", bytes(4 * frames_out))
    for i in range(frames_out):
        pos = i * rate / RATE
        j = min(int(pos), frames_in - 2)
        frac = pos - j
        for c in (0, 1):
            a, b = stereo[2 * j + c], stereo[2 * j + 2 + c]
            out[2 * i + c] = int(a + (b - a) * frac)
    return out


def _decode(path: Path) -> bytes:
    """The file as raw 48 kHz 16-bit stereo bytes."""
    suffix = path.suffix.lower()
    if suffix == ".wav":
        with wave.open(str(path), "rb") as f:
            p = f.getparams()
            samples = _to_16bit(f.readframes(p.nframes), p.sampwidth)
        return _resample(_to_stereo(samples, p.nchannels), p.framerate).tobytes()
    if suffix == ".mp3":
        if shutil.which("mpg123") is None:
            raise RuntimeError("mpg123 not installed")
        result = subprocess.run(
            ["mpg123", "-q", "-s", "-r", str(RATE), "--stereo", "-e", "s16", str(path)],
            capture_output=True, timeout=30)
        if result.returncode != 0:
            raise RuntimeError(result.stderr.decode(errors="replace").strip()[:200])
        return result.stdout
    raise RuntimeError(f"don't know how to play {suffix} files")


_cache: dict[str, bytes] = {}


def _load(name: str) -> bytes | None:
    if name not in _cache:
        path = SOUNDS_DIR / name
        if not path.is_file():
            log(f"missing sound file {path}")
            return None
        try:
            _cache[name] = _decode(path)
        except Exception as exc:  # noqa: BLE001
            log(f"can't load {name}: {exc}")
            return None
    return _cache[name]


# ------------------------------------------------------------------ stream

class _Stream:
    def __init__(self) -> None:
        self.queue: deque[bytes] = deque()
        self.lock = threading.Lock()
        self.thread: threading.Thread | None = None
        chunk = CHUNK_FRAMES * 2
        self.keepalive = array.array("h", (
            random.randint(-KEEPALIVE_LEVEL, KEEPALIVE_LEVEL) if KEEPALIVE_LEVEL else 0
            for _ in range(chunk))).tobytes()

    def start(self) -> bool:
        if shutil.which("aplay") is None:
            log("aplay not installed (package alsa-utils), sound disabled")
            return False
        if self.thread is None or not self.thread.is_alive():
            self.thread = threading.Thread(target=self._run, daemon=True)
            self.thread.start()
        return True

    def add(self, data: bytes) -> None:
        with self.lock:
            self.queue.append(data)

    def _next_chunk(self) -> bytes:
        size = len(self.keepalive)
        with self.lock:
            if not self.queue:
                return self.keepalive
            current = self.queue[0]
            chunk, rest = current[:size], current[size:]
            if rest:
                self.queue[0] = rest
            else:
                self.queue.popleft()
        return chunk + self.keepalive[len(chunk):]   # pad the last bit

    def _run(self) -> None:
        cmd = ["aplay", "-q", "-D", DEVICE, "-t", "raw", "-f", "S16_LE",
               "-r", str(RATE), "-c", "2", f"--buffer-time={int(BUFFER_SECONDS * 1e6)}"]
        while True:
            proc = None
            try:
                proc = subprocess.Popen(cmd, stdin=subprocess.PIPE,
                                        stdout=subprocess.DEVNULL,
                                        stderr=subprocess.PIPE)
                try:
                    fcntl.fcntl(proc.stdin.fileno(), F_SETPIPE_SZ, 4096)
                except OSError:
                    pass
                log(f"audio stream open on {DEVICE}")
                while True:
                    proc.stdin.write(self._next_chunk())   # blocks = real-time pacing
                    proc.stdin.flush()
            except Exception as exc:  # noqa: BLE001
                err = ""
                if proc is not None:
                    proc.kill()
                    err = proc.stderr.read().decode(errors="replace").strip()
                log(f"audio stream stopped ({err[:200] or exc}); retrying in {RETRY_SECONDS:.0f}s")
                with self.lock:
                    self.queue.clear()   # don't play stale sounds late
                time.sleep(RETRY_SECONDS)


_stream = _Stream()


# --------------------------------------------------------------------- API

def start() -> bool:
    """Open the audio stream now (call at startup so the TV wakes up early)."""
    return _stream.start()


def timing(name: str) -> tuple[float, float]:
    """(seconds until sounds/<name> is heard after play(), how long it lasts)."""
    data = _load(name)
    if data is None:
        return 0.0, 0.0
    return BUFFER_SECONDS, len(data) / (RATE * 4)


def play(name: str) -> bool:
    """Queue sounds/<name> to play. Returns False if it can't be played."""
    data = _load(name)
    if data is None or not _stream.start():
        return False
    _stream.add(data)
    log(f"playing {name}")
    return True
