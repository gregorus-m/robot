# RobotOS

Python "operating system" for a Raspberry Pi 5 robot brain (running DietPi).

On boot, systemd runs `robotos/boot.py`, which:

1. Waits up to 20 s for network, then pulls the latest code from GitHub.
2. If anything fails (no wifi, GitHub down, etc.) it logs it and carries on
   with the code already on the Pi.
3. Starts `robotos/main.py`, which shows `splash.txt` on the HDMI screen.

## Layout

| Path | What it is |
|---|---|
| `splash.txt` | The splash screen: an animated cat. Frames are separated by `--- frame ---` (the first is the resting pose); text under the picture goes after `=== text ===`. `{version}` and `{update}` are filled in at runtime. |
| `robotos/boot.py` | Startup script: self-update, then launch main. |
| `robotos/main.py` | RobotOS itself (splash + main loop placeholder). |
| `systemd/robotos.service` | systemd unit that starts RobotOS at boot on tty1. |
| `install.sh` | One-time installer to run on the Pi. |

## Workflow

1. Push this repo to a **public** GitHub repository.
2. On the Pi (once):
   ```bash
   sudo apt-get install -y git
   git clone https://github.com/<you>/<repo>.git /tmp/robotos
   sudo bash /tmp/robotos/install.sh https://github.com/<you>/<repo>.git main
   sudo reboot
   ```
3. From then on: edit here, commit, push. The Pi picks up changes on its next boot
   (or `sudo systemctl restart robotos`).

Note: the Pi's copy in `/opt/robotos` is reset to match GitHub on every boot, so
don't edit files there directly — any local changes on the Pi get overwritten.

## Useful commands on the Pi

```bash
sudo systemctl status robotos     # is it running?
journalctl -u robotos -b          # boot/update log
sudo systemctl stop robotos       # get your tty1 login back
sudo systemctl disable robotos    # stop it starting at boot
```

## Test locally

```bash
python3 robotos/boot.py    # Ctrl+C to exit (self-update is skipped outside /opt/robotos)
```
