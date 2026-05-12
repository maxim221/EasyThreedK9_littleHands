# Printer And Firmware Guide

## 1. Supported Hardware Baseline

This repository is currently documented for:

- printer model: `EasyThreeD K9`
- mainboard family: `ET4000+ / ET4000PLUS`
- validated public baseline: `EasyThreeD K9` + `ET4000+ / ET4000PLUS`

Important:

- this is **not** a blanket claim that every `K9` is identical
- different `K9` units already showed different behavior during development
- the current safe public baseline uses `LH v4`
- the safe claim here is the `ET4000+ / ET4000PLUS` board family; an exact silkscreen subrevision was not separately frozen in this public doc pack

## 2. Current Recommended Firmware

Use:

- `firmware/LH-v4-YZSwap-AutoFan45-FAN1-z600-e1040-mksLite.bin`

This build is the current public default because it matches the validated public K9 baseline:

- explicit `LH` firmware label in `M115`
- working `Little Hands` compatibility
- `FAN1` auto-fan at `45C`
- stock-like motion values:
  - `X606`
  - `Y606`
  - `Z600`
  - `E1040`
- validated operator motion mapping:
  - `X` = printhead left / right
  - `Y` = printhead up / down
  - `Z` = bed in the print plane

## 3. Firmware Identity

After a successful flash, the app should recognize something like:

- `LH v4 YZSwap AutoFan45 FAN1 Z600 E1040`

That identity comes from the firmware itself through `M115`.

## 4. Safe Flash Workflow

### Option A: through Little Hands

1. Open `Files & Firmware`.
2. Select:
   - `firmware/LH-v4-YZSwap-AutoFan45-FAN1-z600-e1040-mksLite.bin`
3. Upload the firmware to the printer SD.
4. Let the printer reboot / complete the flash.
5. Remove `mksLite.bin` or `mksLite.CUR` from the card afterward.
6. Keep `EEPROM.DAT`.

![Files and Firmware window](screenshots/little-hands-files-firmware-window.png)

### Option B: through a card reader

1. Put the SD card into a reader.
2. Copy the firmware to the card as:
   - `mksLite.bin`
3. Insert the card into the printer.
4. Power the printer on for `30–60` seconds.
5. Power it off again.
6. Remove the card.
7. Delete `mksLite.bin` or `mksLite.CUR`.
8. Keep `EEPROM.DAT`.
9. Put the card back into the printer.

## 5. EEPROM.DAT

`EEPROM.DAT` is important.

It stores printer settings such as:

- motion values
- limits
- offsets
- saved firmware settings

Rules:

- do **not** keep deleting it
- keep it on the card after the firmware is initialized
- after a fresh flash, initialize settings and verify the file exists

### Important Cause Of The False Y-Bed "Failure"

The previous printer was most likely not killed by a bad Y motor or a dead driver channel. The same symptom was reproduced on the new K9: after power-on the bed barely moved, while the motor and channel were still alive.

What was confirmed:

- `M503` on the validated `LH v4` reports correct step scaling: `M92 X606 Y606 Z600 E1040`
- a slow `G1 Y5 F300` test moves the bed both ways
- fast manual jog with the saved EEPROM profile `M201 Y1000` / `M204 T1000` can skip steps: Marlin believes the 20 mm move completed, but the bed physically barely moves

Where the bad speed/dynamics came from:

- the current public `LH v4` matches `firmware_src/ECF-Marlin-upstream/Marlin/Configuration.h`
- that tree had `DEFAULT_MAX_ACCELERATION {1000,1000,100,1000}` and `DEFAULT_TRAVEL_ACCELERATION 1000`
- those values were saved in EEPROM/settings and survive power cycles

Current rule:

- treat the Y bed as the limiting motion axis when choosing print speeds and acceleration
- Little Hands now lowers service/manual moves to `M204 T80` and moves the bed around `F600`
- the Cura baseline keeps travel acceleration at or below `200 mm/s^2`
- for the next firmware rebuild, apply the tracked patch: `docs/firmware/LH-v4-safe-motion.patch`
- if the bed buzzes or barely moves, check speed/acceleration first, before blaming the motor or driver

## 6. How Home Works Here

This project currently uses a `manual-zero` workflow, not a true endstop-based auto-home.

That means:

1. The operator moves the printer into a known physical start pose.
2. `Save start` sets that pose as logical zero with:

```gcode
G92 X0 Y0 Z0
```

3. `Go to start` returns to that logical zero during a clean trusted session.

So:

- this is practical and field-tested
- but it is not yet a guaranteed absolute home after arbitrary external movement
- after a failed start or suspicious state, re-establish the start pose and zero again

![Manual window](screenshots/little-hands-manual-window.png)

## 7. External Warm Bed / Hotbed

The validated public baseline uses an external heated bed / warm mat.

Important facts:

- it is heated externally
- it is not connected to the printer board as a controlled heated bed
- the firmware should still behave like a printer without bed-heater control
- in Cura the validated baseline kept bed temperature at `0`

Validated practical setup:

- external warm bed around `40–50C`
- perforated flexible build surface on the warmed bed

Safety note:

- use a heat-safe surface
- do not blindly reuse a random stock plate on a raw external heater

## 8. Cura Baseline

For the current validated public baseline:

- machine: `lilHands K9 warm mat`
- profile: `codex - K9 warm mat cautious`
- brim width: `12 mm`
- PLA temperature: `225C` first layer, `224C` after that
- bed temperature in G-code: `0C` because the warm bed is external
- support mode for `mainFlasherTop.STL`: supports everywhere, normal supports, interface / roof enabled, support angle `35`

Important G-code rules:

- do not use startup `G28`
- the start G-code must use the Little Hands manual-zero `G92 X0 Y0 Z0` workflow
- the generated file must contain a hotend target command such as `M104` / `M109`
- when a file is uploaded through Little Hands, early blocking `M109` is rewritten to `M104`; the app preheats the hotend before the SD start
- reject or re-slice files with `Filament used: 0m`, impossible Cura bounds, or missing hotend target
- `12 mm` brim is now the current default after the automatic hotend-preheat workflow was confirmed; the old start failure was tied to heat / SD-start sequencing, not to brim width itself

Current end-G-code rule:

- present the finished part with raw Marlin `G1 Y95`, which moves the bed toward the operator on the validated setup
- do not add `M84` to Cura end-G-code; `Little Hands` explicitly enables steppers before recovery moves and before SD print start
- if an older file ends with `G1 Y0` or `M84`, re-slice it before judging completion behavior

Re-slice when:

- firmware baseline changes
- printer mapping changes
- the file was generated for another machine

In the app, use `Export Cura profile` to copy the currently validated Cura profile bundle into `exports/`.
The tracked public reference copy is in `docs/cura/`.
If a different slicer version is used, configure it from `docs/cura/SETTINGS.md`.

## 9. First Safe Print Workflow

1. Flash `LH v4`.
2. Confirm tiny jog mapping.
3. Confirm the external warm bed is preheated.
4. Slice in the validated Cura machine/profile.
5. Upload the G-code.
6. Set the physical start pose.
7. Press `Save start`.
8. Press `Go to start` and confirm it returns correctly.
9. Start printing from SD. Manual hotend preheat is not needed: before `M24`, Little Hands preheats the hotend to the target found in the G-code, then sends `M23`, waits for `File selected`, and sends `M24`.
10. If the file was uploaded through Little Hands or exported by the bundled helper, the early `M109` has been rewritten to `M104` so SD start does not get stuck in a blocking heat wait.
11. After `M24`, Little Hands keeps USB fully quiet for `180` seconds. This is expected and helps this K9 enter SD printing reliably.
12. During any remaining `M109` in older G-code, firmware may not answer ordinary `M105` / `M27`; Little Hands first listens passively for `M109` temperature lines and avoids stuffing the queue with extra commands.
13. If there are no temperature lines, no SD progress, and physically no heating, fan, or motion for about `5` minutes after `M24`, the app treats the start as unconfirmed and offers power-cycle recovery.

## 10. Between Prints

After a successful SD print, use this order before starting the next one:

1. Remove the printed part from the bed.
2. Press `Go to start` while the saved zero is still valid.
3. Power-cycle the printer for `5–10` seconds.
4. Confirm the printer is still in the start pose.
5. Press `Save start`.
6. Start the next SD print.

The app blocks repeated SD starts after completion until this recovery cycle is acknowledged.

## 11. Recovery Rule

If a print start fails and you see:

- clicking
- no motion
- frozen telemetry
- stale status
- `device reports readiness to read but returned no data`

the current safest workflow is:

1. stop the print
2. power-cycle the printer
3. re-check the start pose
4. press `Save start`
5. start again

Important nuance: silent USB telemetry alone is not enough to decide that the print failed. If the hotend is heating, the printer is moving, or material is printing, do not power-cycle it; visually monitor the print and let Little Hands wait for USB to recover.

For a stuck start, Little Hands sends `M108` before `M524` so Marlin can break out of a blocking `M109` heat wait, then turns off heat and fan.
