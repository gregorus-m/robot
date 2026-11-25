#!/usr/bin/env bash
# Quick checks before you push. Never touches git or the network.
set -uo pipefail
cd "$(dirname "$0")"
fail=0
check() { if "$@"; then echo "  ok"; else echo "  FAILED"; fail=1; fi; }

echo "Python files compile:"
check python3 -m py_compile robotos/*.py

echo "Shell scripts parse:"
check bash -n install.sh run.sh

echo "splash.txt frames:"
check python3 - <<'EOF'
import sys
sys.path.insert(0, "robotos")
import main
frames, text = main.load_splash()
for i, frame in enumerate(frames):
    print(f"  --- frame {i}")
    print("\n".join("  " + line for line in frame))
if text:
    print("  --- text")
    print("\n".join("  " + line for line in text))
print(f"  swish order: {main.swish_sequence(len(frames))}")
EOF

echo "Animation runs for 2s without crashing:"
check bash -c '
  timeout 2 python3 -c "
import sys; sys.path.insert(0, \"robotos\")
import main
main.SWISH_EVERY = (0.1, 0.2); main.FRAME_SECONDS = 0.05
main.main()
" >/dev/null
  [ $? -eq 124 ]   # 124 = still running when timeout stopped it (good)
'

echo "Sound module handles missing players/files without crashing:"
check python3 -c "
import sys; sys.path.insert(0, 'robotos')
import sound
from pathlib import Path
assert (sound.SOUNDS_DIR / 'meow.wav').is_file(), 'sounds/meow.wav missing'
sound.play('meow.wav'); sound.play('does-not-exist.wav')
import array, io, wave
data = sound._load('meow.wav'); assert data and len(data) % 4 == 0
print(f'  meow.wav -> {len(data)/(sound.RATE*4):.2f}s at 48k stereo; aplay found: {bool(__import__(\"shutil\").which(\"aplay\"))}')
# conversions: 8-bit mono 22050 Hz and 16-bit stereo 44100 Hz
for ch, w, r in [(1, 1, 22050), (2, 2, 44100)]:
    buf = io.BytesIO(); f = wave.open(buf, 'wb'); f.setnchannels(ch); f.setsampwidth(w); f.setframerate(r)
    f.writeframes(bytes(ch * w * r // 10)); f.close()
    open('/tmp/robotos-test.wav', 'wb').write(buf.getvalue())
    out = sound._decode(__import__('pathlib').Path('/tmp/robotos-test.wav'))
    assert abs(len(out) / (sound.RATE * 4) - 0.1) < 0.01, (ch, w, r, len(out))
print('  format conversions ok')
"

echo "Controller reads button presses (simulated device):"
check python3 -c "
import sys, struct, time, tempfile; sys.path.insert(0, 'robotos')
import controller
ev = struct.Struct('IhBB')
f = tempfile.NamedTemporaryFile(delete=False)
f.write(ev.pack(0, 0, 0x81, 0))          # initial state: A up (not a press)
f.write(ev.pack(0, -32767, 0x82, 2))     # initial state: left trigger at rest
f.write(ev.pack(1, 1, 0x01, 0)); f.write(ev.pack(2, 0, 0x01, 0))   # press+release A
f.write(ev.pack(3, 1, 0x01, 1))          # press B
f.write(ev.pack(4, 16000, 0x02, 0))      # left stick half right
f.close()
controller.glob.glob = lambda pattern: [f.name]
controller.RESCAN_SECONDS = 60
pad = controller.Controller(); time.sleep(0.3)
got = pad.events()
assert got == [controller.A, controller.B], got
print('  presses:', [controller.BUTTON_NAMES[b] for b in got])
"

echo "Self-update is skipped in this dev copy:"
check bash -c 'python3 -c "
import sys; sys.path.insert(0, \"robotos\")
import boot
s = boot.try_update(); print(\"  \" + s)
sys.exit(0 if s.startswith(\"skipped\") else 1)
"'

echo
if [ $fail -eq 0 ]; then echo "All checks passed."; else echo "Some checks FAILED."; fi
exit $fail
