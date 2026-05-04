# Linux / Raspberry Pi Setup

This guide is for:

- Linux desktop
- Raspberry Pi OS Desktop
- other Debian-like systems that can run `tkinter` and `pyserial`

## 1. What You Need

- Python `3`
- `tkinter`
- `pyserial`
- audio playback for the completion sound
- access to the USB serial port

## 2. System Packages

On Debian / Ubuntu / Raspberry Pi OS:

```bash
sudo apt update
sudo apt install -y \
  git \
  python3 \
  python3-tk \
  python3-serial \
  pulseaudio-utils
```

Optional but useful:

```bash
sudo apt install -y python3-pil wmctrl gnome-screenshot
```

Notes:

- `python3-pil` is not required by the current code, but is a common desktop package
- `wmctrl` and `gnome-screenshot` are only useful for desktop integration and screenshots

## 3. Clone The Repository

```bash
git clone <YOUR-REPO-URL>
cd littleHands
```

If you do not want to install system `python3-serial`, a minimal pip fallback is:

```bash
python3 -m pip install -r requirements.txt
```

## 4. Serial Port Permissions

Add your user to `dialout`:

```bash
sudo usermod -aG dialout "$USER"
```

Then log out and back in.

## 5. Start The App

From the repo root:

```bash
python3 tools/k9_control_center.py
```

If everything is fine, you should see the `Little Hands` window open.

## 6. Optional Desktop Launcher

The repo already contains:

- `Little Hands Control Center.desktop`

To install it locally:

```bash
mkdir -p ~/.local/share/applications
cp "Little Hands Control Center.desktop" ~/.local/share/applications/little-hands-control-center.desktop
update-desktop-database ~/.local/share/applications 2>/dev/null || true
```

## 7. Expected Runtime Files

Little Hands writes runtime state and logs to:

- `monitor_logs/little_hands_runtime.log`
- `monitor_logs/little_hands_ui_state.json`
- `monitor_logs/gui_exports/`

The runtime log is a ring log capped at `10 MiB`.

## 8. Cura Baseline For The Validated Second K9

Use:

- machine: `lilHands K9 warm mat`
- profile: `codex - K9 warm mat cautious`

Do not use the old reduced-area machine from the first experimental printer unless you are intentionally reproducing that older setup.

## 9. Raspberry Pi Notes

This app works fine on Raspberry Pi desktop setups, but:

- use a powered USB hub if the Pi is marginal on USB power
- prefer direct USB connection to the printer during firmware work
- for a full Raspberry Pi bring-up checklist, use:
  - [../RASPBERRY_PI_CHECKLIST.md](../RASPBERRY_PI_CHECKLIST.md)

## 10. If The App Does Not Start

Check these in order:

1. `python3 --version`
2. `python3 -c "import tkinter"`
3. `python3 -c "import serial"`
4. `python3 tools/k9_control_center.py`

If the import fails for `serial`, install `python3-serial` or use:

```bash
python3 -m pip install -r requirements.txt
```

## 11. If The Printer Is Not Found

This project is tuned for a `K9` that usually appears as a `CH340` USB serial device.

If the printer is not detected:

- power-cycle the printer
- reconnect USB directly
- reopen `Little Hands`
- use the `Найти` button

If a print start fails and the printer only clicks or telemetry freezes, the current safest workflow is:

1. `Жёсткий стоп`
2. printer power cycle
3. re-check the start pose
4. `Запомнить старт`
5. start again

