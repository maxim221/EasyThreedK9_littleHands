# Second K9 Careful Rollout

Purpose:

- migrate the incoming protected `K9` toward `Little Hands`
- do it without repeating the destructive path of the first printer
- keep the second `K9` usable as a reference machine

## Current Hardware Assumptions

- same `K9` family as the first machine
- external heated bed, not wired into the printer mainboard
- real build plate is the original flexible perforated mat
- external bed target during printing: `40–50C`

Important:

- because the hotbed is external, the printer firmware does **not** need bed-heater control for the first rollout
- Cura should **not** send `M140/M190` as part of normal operation
- bed temperature remains a manual preheat step outside the printer electronics

## Target Firmware For App Compatibility

Use this file as the migration target:

- `firmware/LH-v4-YZSwap-AutoFan45-FAN1-z600-e1040-mksLite.bin`

Why this build:

- explicit `LH` firmware identity in `M115`
- known `Little Hands` compatibility
- `FAN1` auto-fan logic already integrated
- stock-like motion values for the protected second printer:
  - `X606`
  - `Y606`
  - `Z600`
  - `E1040`
- keeps the working physical `Y/Z` routing observed on both K9 units
- removes the later mistaken unit-specific `Y/E0` step-dir swap from `LH v2`

## Mandatory Safe Sequence

1. Complete `SECOND_K9_INTAKE.md` first.
2. Keep a full stock TF backup.
3. Photograph board and wiring.
4. Read-only USB checks first:
   - `M115`
   - `M105`
   - SD list
5. Tiny jog mapping before any print.

## Flash Procedure

1. Insert the printer TF card into the PC and preserve its contents.
2. Put the card back into the printer.
3. In `Little Hands`, open `Файлы и прошивка`.
4. Select:
   - `LH-v4-YZSwap-AutoFan45-FAN1-z600-e1040-mksLite.bin`
5. Run firmware upload.
6. Follow the app post-flash message.
7. If needed, power-cycle the printer with the card still inserted.
8. Re-check:
   - `M115`
   - `M105`
   - SD list
   - `M503`

## First Post-Flash Checks

Only after the printer reconnects:

1. Confirm the app sees the firmware as `LH v4 YZSwap AutoFan45 FAN1 Z600 E1040`.
2. Confirm the fan behavior is sane while heating.
3. Jog `X`, `Y`, `Z` with tiny moves only.
4. Record actual physical motion for each axis.

Expected operator mapping in `Little Hands` after `LH v4`:

- `X` = head left / right
- `Y` = head up / down
- `Z` = bed away / toward the operator

If motion mapping differs from that:

- stop
- document it
- do not print

## Cura Machine For This Printer

Use the dedicated machine/profile prepared for this printer:

- machine: `lilHands K9 warm mat`
- profile: `codex - K9 warm mat cautious`

This machine is separate from the damaged first-printer setup and keeps:

- `100 x 100 x 100` build volume
- manual-zero start workflow
- no bed-heater control commands

## Cura Intent For External Warm Bed

The new profile is conservative on purpose:

- smaller brim than the first-printer emergency profile
- moderate first-layer speed
- moderate nozzle temperature
- external bed assumed already warm at `40–50C`

Before each print:

1. Preheat the external bed manually.
2. Wait until the plate is stable in the `40–50C` range.
3. Then start the print workflow in `Little Hands`.

## Success Condition

Rollout is complete only when all of these are true:

- firmware upload completed safely
- `Little Hands` sees and identifies the printer
- tiny jogs work and are documented
- first-layer test stays inside the real build area
- first baseline print adheres on the perforated warm mat without destructive over-squish
