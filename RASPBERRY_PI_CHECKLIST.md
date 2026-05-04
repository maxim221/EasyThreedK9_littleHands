# Little Hands On Raspberry Pi

Purpose:

- help another person bring `Little Hands` up on a Raspberry Pi without guesswork
- make the setup repeatable
- avoid damaging the printer during the first launch

This checklist assumes:

- Raspberry Pi OS with desktop
- a USB-connected EasyThreeD `K9`
- the project folder is copied to the Pi

Suggested project location:

- `/home/pi/littleHands`

If the username is not `pi`, replace paths accordingly.

## 0. Safety First

Before connecting the printer:

- do not flash random firmware files
- do not move motor plugs
- do not swap fan plugs
- do not run `G28`
- do not assume this printer matches another `K9` exactly

## 1. Copy The Project

Copy the whole project folder to the Pi.

Recommended target:

- `/home/pi/littleHands`

Quick check:

```bash
cd /home/pi/littleHands
ls
```

You should see at least:

- `tools/`
- `firmware/`
- `assets/`
- `PROJECT_LOG.md`

## 2. Install System Packages

Update the package index:

```bash
sudo apt update
```

Install the required runtime packages:

```bash
sudo apt install -y \
  python3 \
  python3-tk \
  python3-serial \
  python3-pil \
  pulseaudio-utils
```

Notes:

- `python3-tk` is required for the GUI
- `python3-serial` is required for USB / serial communication
- `pulseaudio-utils` provides `paplay` for the optional completion sound on the computer
- `python3-pil` is not strictly required by the current code, but it is a useful standard package on desktop Pis

## 3. Give The User Access To USB Serial

Add the user to `dialout`:

```bash
sudo usermod -aG dialout "$USER"
```

Then log out and log back in, or reboot:

```bash
sudo reboot
```

After reboot, verify:

```bash
groups
```

The output should include:

- `dialout`

## 4. Optional: Desktop Launcher

If the project stays in `/home/pi/littleHands`, create a desktop launcher like this:

```bash
mkdir -p /home/pi/.local/share/applications
cp /home/pi/littleHands/Little\ Hands\ Control\ Center.desktop /home/pi/.local/share/applications/
```

Edit the launcher if needed:

```bash
nano /home/pi/.local/share/applications/Little\ Hands\ Control\ Center.desktop
```

Adjust these lines to the real path:

- `Exec=...`
- `Path=...`

If you want a matching icon, you can point the desktop file to:

- `/home/pi/littleHands/assets/little-hands-3d-printer.svg`

## 5. First Dry Run Without Printer

From the project root:

```bash
cd /home/pi/littleHands
python3 -m py_compile tools/k9_control_center.py tools/k9_marlin_sd.py
python3 tools/k9_control_center.py
```

Expected result:

- the `Little Hands` window opens
- no printer is required for this test

If it crashes:

- read the traceback in the terminal
- do not continue to printer tests until it starts cleanly

## 6. Connect The Printer Safely

Use:

- direct USB connection if possible
- a good data cable
- external power on the printer

Avoid:

- flaky hubs
- unknown USB extenders

Then check that Linux sees the USB serial device:

```bash
python3 - <<'PY'
from serial.tools import list_ports
for p in list_ports.comports():
    print(p.device, p.description, p.hwid)
PY
```

For a `K9`, a good sign is something like:

- `CH340`
- `/dev/ttyUSB0`

If you only see unrelated `FTDI` ports:

- do not assume the printer is connected correctly

## 7. First Safe Printer Checks

Open `Little Hands`.

Do only these checks first:

1. `Find`
2. `Capture all metrics`
3. `Refresh list`

Only after that, do tiny jogs:

- `Head left`
- `Head right`
- `Bed away`
- `Bed toward`
- `Head down`
- `Head up`

If any axis moves unexpectedly:

- stop
- document it
- do not print yet

## 8. Printer-Specific Files To Keep Track Of

Important files in this project:

- control app:
  - `tools/k9_control_center.py`
- printer USB/SD backend:
  - `tools/k9_marlin_sd.py`
- active printer notes:
  - `PROJECT_LOG.md`
- active firmware folder:
  - `firmware/`

## 9. SD Card Rules

After any firmware flash:

- remove `mksLite.bin`
- remove `mksLite.CUR` if it appeared
- keep `EEPROM.DAT`
- keep only the G-code files you actually need

Do not keep old mystery firmware files on the card.

## 10. Current Safe Baseline

Current known-good firmware:

- `firmware/LH-v4-YZSwap-AutoFan45-FAN1-z600-e1040-mksLite.bin`

Current known-good Cura setup:

- machine: `lilHands K9 warm mat`
- profile: `codex - K9 warm mat cautious`

Important behavior assumptions:

- external heated bed, not wired into the printer
- bed is manually preheated outside the printer electronics
- `Little Hands` uses manual-zero workflow, not `G28`

## 11. What Not To Do

Do not:

- run `G28`
- upload a G-code file that contains startup `G28`
- trust a random old G-code file just because the name looks familiar
- use aggressive homing experiments on an unverified printer
- leave `mksLite.bin` on the SD card after a successful flash

## 12. Fast Recovery Checklist

If the printer behaves strangely:

1. Press `Hard stop`
2. If needed, power off the printer for `10` seconds
3. Restart `Little Hands`
4. Re-check the port with `Find`
5. Re-check tiny jogs only
6. Re-define the start pose with:
   - `Save start`
   - `Go to start`

## 13. When Setup Is Considered Successful

The Pi setup is complete when:

- `Little Hands` launches from terminal without crashing
- the user is in `dialout`
- the printer is found reliably over USB
- `Capture all metrics` works
- `Refresh list` works
- tiny jogs are correct
- no dangerous `G28`-based workflow is used

## 14. Handy Commands

Check syntax:

```bash
cd /home/pi/littleHands
python3 -m py_compile tools/k9_control_center.py tools/k9_marlin_sd.py
```

Run app from terminal:

```bash
cd /home/pi/littleHands
python3 tools/k9_control_center.py
```

List serial ports:

```bash
python3 - <<'PY'
from serial.tools import list_ports
for p in list_ports.comports():
    print(p.device, p.description, p.hwid)
PY
```

## 15. Final Rule

If anything about motion, USB, or startup behavior looks different from expectation:

- stop
- write down exactly what moved
- and compare against `PROJECT_LOG.md` before trying to improvise a fix
