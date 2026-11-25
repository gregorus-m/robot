"""Read a game controller (Logitech F310 / F710, or any Xbox-style pad).

Uses the Linux joystick device (/dev/input/js0) directly, so no extra
libraries are needed. Set the Logitech controller's X/D switch to X: in
X mode the wired F310 and wireless F710 report identical button numbers.

The controller can be plugged in or unplugged at any time; a background
thread keeps looking for it. The main loop calls events() to collect what
happened since it last asked.
"""

import glob
import struct
import sys
import threading
import time
from collections import deque

# Button numbers in X mode.
A, B, X, Y = 0, 1, 2, 3
LB, RB = 4, 5
BACK, START, LOGITECH = 6, 7, 8
LEFT_STICK_PRESS, RIGHT_STICK_PRESS = 9, 10

# Axis numbers in X mode. Sticks/d-pad go -32767..32767 (up/left negative);
# triggers rest at -32767 and go to 32767 when fully pressed.
LEFT_X, LEFT_Y, LEFT_TRIGGER = 0, 1, 2
RIGHT_X, RIGHT_Y, RIGHT_TRIGGER = 3, 4, 5
DPAD_X, DPAD_Y = 6, 7

BUTTON_NAMES = {A: "A", B: "B", X: "X", Y: "Y", LB: "LB", RB: "RB",
                BACK: "Back", START: "Start", LOGITECH: "Logitech",
                LEFT_STICK_PRESS: "L3", RIGHT_STICK_PRESS: "R3"}

_EVENT = struct.Struct("IhBB")   # time (ms), value, type, number
_BUTTON, _AXIS, _INIT = 0x01, 0x02, 0x80
RESCAN_SECONDS = 2.0


def log(msg: str) -> None:
    if not sys.stderr.isatty():
        print(f"[robotos-controller] {msg}", file=sys.stderr, flush=True)


class Controller:
    def __init__(self) -> None:
        self.connected = False
        self.name = ""
        self.axes: dict[int, int] = {}       # latest value of every axis
        self.held: set[int] = set()          # buttons currently held down
        self._presses: deque[int] = deque()  # button presses not yet collected
        self._lock = threading.Lock()
        threading.Thread(target=self._run, daemon=True).start()

    def events(self) -> list[int]:
        """Buttons pressed since the last call, in order."""
        with self._lock:
            presses = list(self._presses)
            self._presses.clear()
        return presses

    def buttons_held(self) -> set[int]:
        """Buttons currently held down."""
        with self._lock:
            return set(self.held)

    def axis(self, number: int) -> float:
        """Axis position from -1.0 to 1.0 (0 if not connected)."""
        return self.axes.get(number, 0) / 32767

    def _run(self) -> None:
        while True:
            try:
                devices = sorted(glob.glob("/dev/input/js*"))
                if devices:
                    self._read(devices[0])
            except Exception as exc:  # noqa: BLE001 - never let this thread die
                log(f"error: {exc}")
            time.sleep(RESCAN_SECONDS)

    def _read(self, path: str) -> None:
        try:
            with open(path, "rb") as js:
                self.name = _device_name(path)
                self.connected = True
                log(f"connected: {self.name} ({path})")
                while True:
                    data = js.read(_EVENT.size)
                    if len(data) < _EVENT.size:
                        break
                    _, value, kind, number = _EVENT.unpack(data)
                    initial = kind & _INIT
                    kind &= ~_INIT
                    if kind == _AXIS:
                        self.axes[number] = value
                    elif kind == _BUTTON:
                        with self._lock:
                            if value:
                                self.held.add(number)
                                if not initial:
                                    self._presses.append(number)
                            else:
                                self.held.discard(number)
        except OSError as exc:
            if self.connected:
                log(f"disconnected ({exc.strerror or exc})")
        finally:
            self.connected = False
            self.axes.clear()
            with self._lock:
                self.held.clear()


def _device_name(path: str) -> str:
    try:
        number = path.rsplit("js", 1)[1]
        with open(f"/sys/class/input/js{number}/device/name") as f:
            return f.read().strip()
    except (OSError, IndexError):
        return "controller"
