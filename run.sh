#!/usr/bin/env bash
# Run RobotOS locally (on the dev machine or the Pi) in this terminal.
# Self-update is skipped unless this copy lives in /opt/robotos.
# Ctrl+C to exit.
cd "$(dirname "$0")"
exec python3 robotos/boot.py "$@"
