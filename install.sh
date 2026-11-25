#!/usr/bin/env bash
# Install RobotOS on the Raspberry Pi so it starts on boot.
#
# Usage (on the Pi, as root):
#   sudo bash install.sh https://github.com/<you>/<repo>.git [branch]
set -euo pipefail

REPO_URL="${1:?usage: install.sh <github-repo-url> [branch]}"
BRANCH="${2:-main}"
INSTALL_DIR=/opt/robotos

if [[ $EUID -ne 0 ]]; then
    echo "Please run as root (sudo)." >&2
    exit 1
fi

echo "==> Installing dependencies"
apt-get update -q
apt-get install -y -q git python3 alsa-utils mpg123

echo "==> Fetching RobotOS into $INSTALL_DIR"
if [[ -d "$INSTALL_DIR/.git" ]]; then
    git -C "$INSTALL_DIR" remote set-url origin "$REPO_URL"
    git -C "$INSTALL_DIR" fetch origin "$BRANCH"
    git -C "$INSTALL_DIR" checkout -B "$BRANCH" "origin/$BRANCH"
else
    git clone --branch "$BRANCH" "$REPO_URL" "$INSTALL_DIR"
fi

echo "==> Installing systemd service"
install -m 644 "$INSTALL_DIR/systemd/robotos.service" /etc/systemd/system/robotos.service
systemctl daemon-reload
systemctl enable robotos.service

echo
echo "Done. RobotOS will start on next boot."
echo "Start it now with:   sudo systemctl start robotos"
echo "View its logs with:  journalctl -u robotos -f"
