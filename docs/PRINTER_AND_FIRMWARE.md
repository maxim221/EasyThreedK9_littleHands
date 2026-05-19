# Printer And Firmware Guide

## 1. Supported Hardware Baseline

This repository is currently documented for:

- printer model: `EasyThreeD K9`
- mainboard family: `ET4000+ / ET4000PLUS`
- validated public baseline: `EasyThreeD K9` + `ET4000+ / ET4000PLUS`

Important:

- this is **not** a blanket claim that every `K9` is identical
- different `K9` units already showed different behavior during development
- the current safe public candidate uses `LH v5`, based on the validated `LH v4` motion baseline
- the safe claim here is the `ET4000+ / ET4000PLUS` board family; an exact silkscreen subrevision was not separately frozen in this public doc pack

## 2. Current Recommended Firmware

Use:

- `firmware/LH-v5-YZSwap-AutoFan45-FAN1-z600-e1040-watch180-mksLite.bin`

This build is the current public default candidate because it matches the validated public K9 motion baseline and extends the hotend heating watchdog window:

- explicit `LH` firmware label in `M115`
- working `Little Hands` compatibility
- `FAN1` auto-fan at `45C`
- hotend `WATCH_TEMP_PERIOD 180s` to avoid false `Heating failed` on slow K9 cold starts while keeping thermal protection enabled
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

- `LH v5 YZSwap AutoFan45 FAN1 Z600 E1040 Watch180`

That identity comes from the firmware itself through `M115`.

## 4. Safe Flash Workflow

### Option A: through Little Hands

1. Open `Files & Firmware`.
2. Select:
   - `firmware/LH-v5-YZSwap-AutoFan45-FAN1-z600-e1040-watch180-mksLite.bin`
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

- `M503` on the validated `LH v4` / `LH v5` motion baseline reports correct step scaling: `M92 X606 Y606 Z600 E1040`
- a slow `G1 Y5 F300` test moves the bed both ways
- fast manual jog with the saved EEPROM profile `M201 Y1000` / `M204 T1000` can skip steps: Marlin believes the 20 mm move completed, but the bed physically barely moves

Where the bad speed/dynamics came from:

- the current public `LH v5` matches `firmware_src/ECF-Marlin-upstream/Marlin/Configuration.h`
- that tree had `DEFAULT_MAX_ACCELERATION {1000,1000,100,1000}` and `DEFAULT_TRAVEL_ACCELERATION 1000`
- those values were saved in EEPROM/settings and survive power cycles

Current rule:

- treat the small X head carriage and Y bed as limiting service-motion axes when choosing print speeds and acceleration
- Little Hands now leaves recovery motion in the soft `M204 T80` service-idle state, moves long bed service/recovery paths around `F240`, uses the validated `F600` / `M204 P80 T80` context for manual bed jogs, and moves the head left/right around `F900`
- short diagnostic bed moves up to `F600` worked over `5 mm`, and the UI now follows the validated manual context instead of over-softening the move
- the Cura baseline keeps travel acceleration at or below `200 mm/s^2`
- Little Hands SD start uses staged hotend preheat: `M104` stages around `60/100/150/200C`, then the final blocking `M109` before `M24`
- the first hotend stage can look slow and may produce faint clicks before the temperature suddenly climbs; this is acceptable only while the staged temperature gates are reached, the target is stable, and heater output is not stuck at `@0`
- keep `WATCH_TEMP_PERIOD 180s` in future firmware rebuilds unless a physical cold-start heat test proves a safer replacement
- for the next firmware rebuild, preserve the tracked safe-motion patch assumptions from `docs/firmware/LH-v4-safe-motion.patch`
- also apply `docs/firmware/LH-v5-watch180.patch` so firmware identity and hotend thermal-watch behavior stay reproducible
- if the bed or head buzzes, skips, or barely moves, check speed/acceleration first, before blaming the motor or driver
- if the head left/right axis sticks only after a print and later frees up after a few short jogs, treat it as a mechanical carriage issue first; do not compensate by increasing recovery speed or adding forceful return moves

## 6. How Home Works Here

This project currently uses a `manual-zero` workflow, not a true endstop-based auto-home.

That means:

1. The operator moves the printer into a known physical start pose.
2. `Save start` sets that pose as logical zero with:

```gcode
G92 X0 Y0 Z0
```

3. `Go to saved start` returns to that logical zero during a clean trusted session.

So:

- this is practical and field-tested
- but it is not yet a guaranteed absolute home after arbitrary external movement
- after a failed start or suspicious state, re-establish the start pose and zero again
- Little Hands now tracks home as `trusted`, `uncertain`, or `invalid`; SD start and `Go to saved start` are blocked unless home is trusted or the app is showing an explicit post-print recovery prompt
- changing / disconnecting the USB port, disabling motors, hard-stopping, a failed jog, or a failed recovery invalidates that trust because the printer has no physical endstops to re-discover zero
- normal `Stop` is a controlled stop, not the emergency path: Little Hands pauses, reads `M114`, tries to lift Z to a known safe recovery height, then sends `M524` / heater-off commands
- after a normal `Stop`, Little Hands saves a stopped-print recovery marker when possible: X/Y come from the interrupted print position, while Z comes from the controlled post-stop lift when available; manual jogs after Stop update this recovery marker instead of deleting it
- if `Stop` happens while the K9 is still busy and no `M114` is captured, Little Hands may offer a guarded live-session `Go to saved start`; use it only with a clear bed, then press `Save start` only after visually confirming the physical start pose
- if USB drops during a real SD print and the main window still shows a stale active-print marker after reconnect, `After print: return` may offer guarded recovery from the saved `LH_END_GCODE_V1` print-end; accept only if the print is definitely finished, the bed is clear, and the axes were not moved after finish
- if the CH340 printer re-enumerates under a new `/dev/ttyUSB*` name after USB loss, post-print recovery may automatically switch to the single visible safe printer-like port; manual `Find` is not required for that recovery case
- if an old active-print marker is too stale to restore as active printing, Little Hands still keeps a valid predicted print-end as a guarded recovery option
- if USB is lost during SD printing but the print finishes normally, the operator can use `Print finished` after removing the part; Little Hands then keeps the saved predicted final pose for guarded `After print: return`
- the SD panel has a dedicated `After print: return` button; it does not perform a separate unsafe home, but runs the same guarded recovery path as the manual `Go to saved start` button, including the clear-bed confirmation
- if Little Hands is restarted or reconnects and later detects that a restored print has finished, it must not move axes automatically; restore the start pose manually after clearing the bed
- SD start is now blocked unless the app knows the printer is physically at the saved `X0 Y0 Z0`
- before `M24`, Little Hands always proves hotend heatup with staged `M104` targets followed by one final host-side `M109` session while passively reading temperature lines; if heatup is not confirmed, `M24` is not sent and cold movements should not happen
- if Little Hands lifted the nozzle for safe heatup, the app explicitly returns the nozzle to the saved start before `M24`; if the preheat fails, it first undoes the known lift with a relative Z-down move before showing the error
- if that relative return is not acknowledged, Little Hands preserves a failed-preheat-lift recovery marker; `Go to saved start` can retry only after the operator confirms that the print did not start and the axes were not moved by hand; after a successful retry Little Hands immediately re-declares the recovered physical start with `G92 X0 Y0 Z0`, because Marlin's logical Z may be stale after a power cycle; a failed manual jog must not clear this marker because no motion was acknowledged
- for existing SD files that still contain an early blocking `M109`, Little Hands still preheats the hotend before `M24`; the file-local `M109` stays in G-code as an extra safety wait, but the app no longer relies on it as the only heat gate
- after a completed, stopped, hard-stopped, or failed SD print/start, the next SD start requires explicit confirmation that the printer was power-cycled for `5–10` seconds and the start pose was saved again; pressing `Save start` alone does not clear this gate
- new Little Hands files must not rewrite early `M109` to `M104`; host preheat before `M24` must use staged `M104` targets followed by one final `M109` session with passive temperature parsing. Do not change this back to a single cold high `M109` or the old active `M104` plus repeated `M105` polling loop; both modes have failed on this K9.
- if Marlin shows a hotend target and positive heater output but the first minute of temperature rise is small, treat it as this K9's slow-start hotend/sensor behavior: log a warning and keep waiting up to the full preheat timeout; still abort quickly if the target drops to `/0C`, heater output stays `@0`, or `M109` stops producing temperature lines

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
- brim width: `14 mm`
- PLA temperature: `225C` first layer, `224C` after that
- bed temperature in G-code: `0C` because the warm bed is external
- support mode for `mainFlasherTop.STL`: supports everywhere, normal supports, interface / roof enabled, support angle `35`

Important G-code rules:

- do not use startup `G28`
- the start G-code must use the Little Hands manual-zero `G92 X0 Y0 Z0` workflow
- the generated file must contain a hotend target command such as `M104` / `M109`
- when a file is uploaded through current Little Hands, early blocking `M109` is preserved; the app still preheats the hotend before `M24`, and the file-local `M109` remains as a safety wait
- old already-prepared `M104`-only files are also supported because the app preheats the hotend with the same staged host-side heat gate before SD start
- use `Check G-code` before upload; the same validation also runs automatically before `Upload G-code` and `Upload & start`
- reject or re-slice files with `Filament used: 0m`, impossible bounds, motion outside `100 x 100 x 100 mm`, bed heat `M140/M190 S>0`, `M18/M84`, missing hotend target, or aggressive body `M204`
- `14 mm` brim is now the current default after the anti-warp profile tuning; the old start failure was tied to heat / SD-start sequencing, not to brim width itself

Current end-G-code rule:

- present the finished part with raw Marlin `G1 Y95 F240`, which moves the bed toward the operator gently on the validated setup
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

1. Flash `LH v5`.
2. Confirm tiny jog mapping.
3. Confirm the external warm bed is preheated.
4. Slice in the validated Cura machine/profile.
5. Upload the G-code.
6. Set the physical start pose.
7. Press `Save start`.
8. Press `Go to saved start` and confirm it returns correctly.
9. Start printing from SD. Manual hotend preheat is not needed: Little Hands first heats the hotend with staged `M104` targets and a final host-side `M109`, returns the nozzle to the saved start, and only then sends `M23`/`M24`.
10. If the file was uploaded through current Little Hands or exported by the bundled helper, the early `M109` stays in the SD file as an extra safety wait; this is the normal path.
11. After `M24`, Little Hands keeps USB fully quiet for `180` seconds. This is expected and helps this K9 enter SD printing reliably.
12. During any remaining `M109` in older G-code, firmware may not answer ordinary `M105` / `M27`; Little Hands first listens passively for `M109` temperature lines and avoids stuffing the queue with extra commands.
13. If there are no temperature lines, no SD progress, and physically no heating, fan, or motion for about `5` minutes after `M24`, the app treats the start as unconfirmed and offers power-cycle recovery.

## 10. Between Prints

After a successful SD print, use this order before starting the next one:

1. Remove the printed part from the bed.
2. Press `Go to saved start` while the saved zero is still valid.
3. Power-cycle the printer for `5–10` seconds.
4. Confirm the printer is still in the start pose.
5. Press `Save start`.
6. Start the next SD print.

The app blocks repeated SD starts after completion until this recovery cycle and the power cycle are acknowledged.

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
