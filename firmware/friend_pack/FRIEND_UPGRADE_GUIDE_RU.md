# EasyThreeD K9 ET-4000+ - Guide To Upgrade To The New System

This guide describes the exact conversion path that was tested in this workspace for:

- printer: `EasyThreeD K9`
- mainboard: `ET-4000+`
- one physical fan on the print head
- target result:
  - Marlin firmware with USB access
  - automatic safety behavior for the single head fan
  - live USB monitoring from a PC

## 1. What This Upgrade Gives You

After the upgrade the printer should have:

- Marlin over USB
- working `M115`, `M105`, `M155`
- card printing still available
- automatic start of the single head fan during hotend heating
- automatic stop of that fan after cooldown
- ability to monitor temperatures and SD print status from a computer

## 2. Important Limitation

This upgrade is designed for a K9 that has only one physical fan.

That means:

- the single fan is treated as a safety / hotend cooling fan first
- true fully independent part-cooling is **not** the main goal of this firmware
- if you later add a second fan, you should consider a second firmware/layout pass

## 3. Before You Start

You need:

- a `FAT32` microSD card
- a USB cable
- a screwdriver to open the base if needed
- a way to confirm that the board is really `ET-4000+`

Recommended:

- back up the original `mksLite.CUR` from the printer card
- take a photo of the original fan wiring before moving anything

## 4. Confirm The Board

Do **not** use this guide blindly on a random K9.

Check inside the printer and confirm that the board is marked:

- `ET-4000+`

If the board is not `ET-4000+`, stop and do not use this firmware.

## 5. Fan Wiring For This Single-Fan System

On the tested ET-4000+ setup:

- `FAN1` is the firmware-controlled fan header
- `FAN2` behaves like the non-controlled / always-powered header

For this specific firmware, the single head fan must be connected to:

- `FAN1`

Why:

- this firmware adds a safety guard to the Marlin-controlled fan channel
- the fan will then start automatically while the hotend is heating or still warm

If your single fan is still connected to `FAN2`:

1. power the printer off
2. move the fan plug from `FAN2` to `FAN1`
3. double-check polarity before power-up

## 6. Files To Use

Firmware file for the tested single-fan setup:

- `K9_ET4000PLUS_single_fan_guard_mksLite.bin`

Expected SHA256:

- `4a73c0ccb6b995dbfc38ffd4847655a7cbd8613ecb67aea73e4951b49c0547eb`

## 7. Flash Procedure

1. Format a microSD card as `FAT32` if needed.
2. Copy the firmware file to the card as:
   - `mksLite.bin`
3. Power the printer off.
4. Insert the card into the printer.
5. Power the printer on.
6. Wait about `30-60` seconds.
7. Power the printer off again.
8. Put the card back into a computer.
9. Confirm the file was renamed to:
   - `mksLite.CUR`

If the file did **not** rename, the flash likely did not happen.

## 8. First Boot Checks

After flashing:

1. power the printer on normally
2. check that the LED comes on
3. check that the printer still wakes up and moves on boot
4. do **not** immediately start a long print

If something behaves badly, stop and diagnose before printing.

## 9. USB Check

Connect the printer to a computer by USB.

The upgraded printer should enumerate as a serial device, typically:

- `/dev/ttyUSB0`

And `M115` should report a Marlin firmware string.

## 10. Mandatory Fan Safety Test

Do this before trusting the printer for a real job.

Test sequence:

1. connect over USB at `115200`
2. make sure no manual fan command is forcing the fan on
3. send:
   - `M106 S0`
4. then send:
   - `M104 S80`
5. listen to the fan

Expected result:

- the fan should start on its own during warmup
- the fan may change behavior while the hotend warms
- after cooling and target reset, the fan should eventually stop again

If the fan does **not** auto-start, do not proceed with printing.

## 11. Basic Cura Starting Point

For strong useful parts on this small printer, a good baseline is:

- layer height: `0.20`
- walls: `4`
- top layers: `6`
- bottom layers: `6`
- infill: `35%`
- print temp: `218C`
- first layer temp: `220C`
- first layer speed: `10 mm/s`
- print speed: `20 mm/s`
- brim: `10 mm`
- retraction: `6.5 mm`

## 12. Live Monitoring From A PC

If you want to watch a card print over USB, use the included monitor tool from this project:

- `/home/maxim/draftCode/littleHands/tools/k9_usb_monitor.py`

Example:

```bash
python3 /home/maxim/draftCode/littleHands/tools/k9_usb_monitor.py
```

It shows:

- live temperature telemetry via `M155`
- periodic SD print status via `M27`

## 13. Recommended Next Upgrade Later

The best future hardware upgrade is to add a second fan.

Ideal end state:

- dedicated hotend/heatsink safety fan
- separate controllable part-cooling fan

But this guide is intentionally for the simpler tested single-fan conversion.
