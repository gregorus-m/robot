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
print('  players found:', {k: __import__('shutil').which(v[0]) for k, v in sound.PLAYERS.items()})
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
