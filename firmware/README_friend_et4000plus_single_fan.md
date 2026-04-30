# EasyThreeD K9 ET-4000+ Single-Fan Firmware

This folder contains the tested Marlin firmware variant prepared for:

- `EasyThreeD K9`
- mainboard `ET-4000+`
- single physical fan used for hotend/head cooling

## Included Firmware

- `K9_ET4000PLUS_single_fan_guard_mksLite.bin`

## What This Firmware Changes

- keeps USB / Marlin host control working
- keeps the EasyThreeD button UI working
- adds a safety guard for the only fan on `FAN1/FAN0`
- starts that fan automatically when the hotend is heating
- keeps that fan from stopping while the hotend still has a target or is still warm

This is intentionally a safety-first firmware for printers that only have one fan.

## Important Limitation

If the printer has only one physical fan, this firmware prioritizes hotend safety over true independent part cooling.

## Flash Method

1. Copy the file to a FAT32 microSD card as `mksLite.bin`
2. Power the printer off
3. Insert the card
4. Power the printer on and wait about `30-60` seconds
5. Power it off again
6. Put the card back into a computer and confirm the file was renamed to `mksLite.CUR`

## Verified Binary

- source file used in this workspace:
  - `/home/maxim/draftCode/littleHands/firmware/custom-hotend-fan-guard-mksLite.bin`
- expected SHA256:
  - `4a73c0ccb6b995dbfc38ffd4847655a7cbd8613ecb67aea73e4951b49c0547eb`
