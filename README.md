# Little Hands For EasyThreeD K9

Little Hands is a Linux desktop control center for a very specific 3D-printer setup:

- printer: `EasyThreeD K9`
- board family: `ET4000+ / ET4000PLUS`
- current firmware candidate: `LH-v5-YZSwap-AutoFan45-FAN1-z600-e1040-watch180-mksLite.bin`
- slicer baseline: `Cura 5.11`
- heated bed baseline: external warm mat / hotbed, not electrically wired into the printer mainboard

This project is still a little rough, but it already works for real printing.

- USB/SD control works
- firmware upload works
- manual-zero workflow works
- logging works
- Cura export works
- G-code upload validation catches unsafe or obviously broken files
- print progress and temperature monitoring work

What is still rough:

- this is not a generic `K9` package for every board variant
- there is no true endstop-based auto-home yet
- after a real failed print start with no heating / no motion, the safest recovery is still a printer power cycle
- Windows packaging is only planned, not shipped
- the app UI has RU / EN / ZH switching, but some rough edges are still being tested

## Screenshot

![Little Hands main window](docs/screenshots/little-hands-main-window.png)

![Files and Firmware window](docs/screenshots/little-hands-files-firmware-window.png)

![Manual window](docs/screenshots/little-hands-manual-window.png)

## Language Versions

- English:
  - [README.md](README.md)
  - [Linux setup](docs/INSTALL_LINUX.md)
  - [Printer and firmware guide](docs/PRINTER_AND_FIRMWARE.md)
- Russian:
  - [README.ru.md](README.ru.md)
  - [Установка на Linux / Raspberry Pi](docs/INSTALL_LINUX.ru.md)
  - [Принтер и прошивка](docs/PRINTER_AND_FIRMWARE.ru.md)
- Chinese:
  - [README.zh.md](README.zh.md)
  - [Linux / Raspberry Pi 安装](docs/INSTALL_LINUX.zh.md)
  - [打印机与固件说明](docs/PRINTER_AND_FIRMWARE.zh.md)

## Current Supported Setup

The current public baseline is a validated `EasyThreeD K9` setup with:

- tested printer family: `EasyThreeD K9`
- tested board family: `ET4000+ / ET4000PLUS`
- tested firmware baseline: `LH-v5-YZSwap-AutoFan45-FAN1-z600-e1040-watch180-mksLite.bin`
- tested app: `tools/k9_control_center.py`
- tested Cura machine: `lilHands K9 warm mat`
- tested Cura profile: `codex - K9 warm mat cautious`

Do **not** assume this will work unchanged on every random `K9`.
Different `K9` units already showed differences during development.

If you are bringing this up on a Raspberry Pi, use:

- [RASPBERRY_PI_CHECKLIST.md](RASPBERRY_PI_CHECKLIST.md)

## How Home Works

This setup does **not** use a normal endstop-based Marlin `G28` workflow.

Instead, Little Hands uses a manual-zero workflow:

1. Move the printer into a known print start pose.
2. Press `Save start`.
3. The app tells the printer `G92 X0 Y0 Z0`.
4. `Go to saved start` returns to that logical zero during the current clean session.

This means:

- this is a practical operator workflow, not a true sensor-based home
- after a failed print start, the safest next step is usually:
  - power cycle the printer
  - re-check the start pose
  - press `Save start` again
- after a stopped print, `Go to saved start` is allowed only through the explicit recovery prompts; if the app offers a live-session return because `M114` was not captured, clear the bed first and press `Save start` only after visually confirming the nozzle is back at the real start pose
- if hotend preheat fails after Little Hands lifted Z for clearance, `Go to saved start` can offer a guarded retry that lowers Z by the same known preheat lift; accept it only if the print did not start and the axes were not moved by hand
- if the hotend is heating, the printer is moving, or material is printing, do not power-cycle just because USB telemetry is quiet
- after a normal print finish, the SD panel `After print: return` button runs the same guarded recovery path as `Go to saved start` and requires a clear bed
- after a completed, stopped, or failed SD print/start, the app requires a confirmed printer power cycle and a fresh `Save start` before the next `M24`, so this K9 cannot skip the file-local `M109` and begin cold movements
- before `M24`, Little Hands confirms hotend heatup itself with a host-side `M109`; if heatup is not confirmed, SD print is not started

## External Warm Bed / Hotbed Note

The validated public baseline uses an external warm mat / hotbed.

- it is heated by its own external power path
- it is **not** controlled by the printer firmware
- the printer should still see `bed temp = 0`
- the validated working range was around `40-50C`

Important:

- do not put a random stock plastic sheet directly onto a raw external heater
- use a heat-safe build surface
- the validated setup used the perforated flexible print surface on the warmed bed

## Quick Start

1. Install Linux dependencies:
   - [docs/INSTALL_LINUX.md](docs/INSTALL_LINUX.md)
2. Read the printer/firmware guide:
   - [docs/PRINTER_AND_FIRMWARE.md](docs/PRINTER_AND_FIRMWARE.md)
3. Start the app:

```bash
python3 tools/k9_control_center.py
```

4. In Cura choose:
   - machine: `lilHands K9 warm mat`
   - profile: `codex - K9 warm mat cautious`
   - brim: `14 mm`
   - Cura preference: `Add machine prefix to job name` = `off`
   - PLA: `225C` first layer, then `224C`
   - walls: `5`, Z seam: `Random`
   - supports for `mainFlasherTop.STL`: everywhere, interface / roof enabled, support angle `35`

The tracked public Cura baseline is in [docs/cura/](docs/cura/).
Manual settings for other slicer versions are in [docs/cura/SETTINGS.md](docs/cura/SETTINGS.md).

## Recommended Firmware File

Use this file for the current public baseline:

- [`firmware/LH-v5-YZSwap-AutoFan45-FAN1-z600-e1040-watch180-mksLite.bin`](firmware/LH-v5-YZSwap-AutoFan45-FAN1-z600-e1040-watch180-mksLite.bin)

Archive and historical firmware files are kept in `firmware/`, but they are not the recommended default for new users.

## Repository Layout

- `tools/`
  - the Little Hands GUI, USB/SD helper code, and Cura slicing helper
- `firmware/`
  - current recommended firmware and historical builds
- `docs/`
  - install and printer guides
- `RASPBERRY_PI_CHECKLIST.md`
  - bring-up checklist for Raspberry Pi
- `PROJECT_LOG.md`
  - detailed working log and engineering history

## Status

This repo is not pretending to be fully polished yet.

It is best described as:

- actively used
- field-tested on a real K9
- still evolving
- good enough to print
