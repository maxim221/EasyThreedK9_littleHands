# Second K9 Intake Checklist

Purpose:

- Bring the incoming second Easythreed K9 online safely.
- Avoid damaging a known-good printer with experimental steps.
- Capture a complete stock baseline before any changes.

## Rule Zero

This printer is the protected reference machine.

Until the baseline is captured:

- do not flash experimental firmware
- do not swap motor plugs
- do not swap fan plugs
- do not move stepper drivers
- do not delete service files from the TF card
- do not run aggressive homing experiments

## 1. Before Power-On

1. Photograph the printer from all sides.
2. Photograph the main board clearly.
3. Photograph all motor / fan / endstop / button connectors.
4. Photograph the TF card contents in a computer.
5. Copy the whole TF card to a backup folder on the PC.

Suggested backup folder name:

- `card_backups/second_k9_stock_YYYYMMDD_HHMMSS/`

## 2. Stock TF Card Capture

Record:

- all visible files on the TF card
- whether `EEPROM.DAT` exists
- whether any `mksLite.bin` / `.CUR` file exists
- example stock models / G-code
- any config text files

Do not delete anything yet.

## 3. First Safe Bring-Up

1. Insert the stock TF card back into the printer.
2. Power on the printer.
3. Connect USB directly to the computer, not through a questionable hub.
4. In `Little Hands`, do read-only checks first:
   - port detection
   - `M115`
   - `M105`
   - SD file list

If USB does not come up:

- stop and document it
- do not start changing firmware immediately

## 4. Motion Mapping

Use only tiny jogs.

Record what each axis actually does:

- `X+`
- `X-`
- `Y+`
- `Y-`
- `Z+`
- `Z-`

Write down:

- which motion is left/right
- which motion is bed in/out
- which motion is head up/down

## 5. Fan Behavior

Check and record:

- where the physical fan is plugged in
- whether the fan is always-on or temperature-controlled
- whether `M106` changes anything
- whether heating the hotend changes anything

Do not repin fans yet.

## 6. Home Behavior

Only after motion mapping is documented:

1. Decide whether a homing test is safe.
2. If tested, keep it supervised and be ready to cut power.
3. Record exactly:
   - direction of motion
   - whether it hits hard stops
   - whether it stops cleanly

If homing looks dangerous:

- stop immediately
- do not repeat it

## 7. Decide The Role Of The Printer

Only after steps 1–6 are complete:

- keep it stock as the protected reference
or
- migrate it carefully toward the Little Hands baseline

## 8. If Migration Is Chosen

Do it in this order:

1. preserve the stock card backup
2. preserve all photos and notes
3. change one thing at a time
4. test after every single change

## 9. Hard Stop Conditions

Stop immediately if any of these happen:

- a motor grinds into an end repeatedly
- a fan stops while the hotend is hot
- USB disappears during a risky operation
- the printer enters a halted state
- the printer starts moving in an unexpected axis

## 10. Success Condition

The intake is complete only when we have:

- full TF card backup
- full photo set
- stock file list
- known USB behavior
- known axis mapping
- known fan behavior
- known home behavior or an explicit note that home is unsafe
