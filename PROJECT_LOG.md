# littleHands Project Log

## Purpose

This file tracks the current 3D-printing setup, decisions, and observations for the Easythreed K9 workflow so progress is not lost between sessions.

## Current Goal

Print simple boxes reliably on an Easythreed K9 using Cura and TF-card workflow.

## Test Strategy

We are using iterative profile comparison instead of changing many things at once without records.

Current comparison plan:

1. Establish a working baseline that prints and sticks reliably.
2. Record geometry quality, adhesion, surface look, and weak points.
3. Create a second profile aimed specifically at strength.
4. Reprint the same model and compare only the changed behavior.

This should help separate:

- bed adhesion problems
- first-layer height / squish problems
- geometry / small-hole reproduction problems
- interlayer strength problems
- material problems versus slicer-setting problems

## Current State

- Main slicer path is the official AppImage:
  - `/home/maxim/Applications/UltiMaker-Cura-5.11.0-linux-X64.AppImage`
- Local launcher files point to the AppImage:
  - `/home/maxim/.local/share/applications/UltiMaker-Cura.desktop`
  - `/home/maxim/.local/share/applications/cura-slicer_cura.desktop`
- Cura default save path is set to:
  - `/media/maxim/LHprint`
- TF card label currently seen by the system:
  - `LHprint`

## 2026-05-10 PLA Profile V2: Anti-Warp And Layer Bond

Observation after the successful `moduleBot` print:

- Application workflow is much more stable.
- Model quality improved compared with the previous baseline.
- Remaining issues:
  - front-right edge has a serious crack starting around `10 mm` above the bed
  - corners still lift by about `1 mm`

Profile response, intentionally conservative:

- `brim_width`: `10 mm -> 12 mm`
- normal PLA temperature: `220C -> 222C`
- first layer temperature: keep `225C`
- part-cooling removed from the quality-tuning plan
- slicer `M106/M107` commands are stripped because the current K9 has one physical firmware-managed hotend fan, not an independent part-cooling fan
- initial layer line width: `145% -> 150%`
- Z seam: user-specified `backleft`, to avoid the visible front-right edge

Reasoning:

- Corner lift points to residual bed adhesion / shrink stress, not a total first-layer failure.
- The one-edge crack may be real delamination from shrink stress, or a visible seam/retraction scar on the front-right corner.
- Do not use Cura fan tuning as a quality lever on this hardware revision; the single fan belongs to hotend safety.
- Avoid raft and extreme `18 mm` brim for now because the last print is close to usable and large changes would hide the actual cause.

## 2026-05-10 PLA Profile V3: Crack Moved Up To 15 Mm

Field observation during the next `moduleBot` print:

- The print is more stable overall.
- The previous crack moved upward from roughly `10 mm` to roughly `15 mm`.
- Runtime telemetry shows the hotend holding `222C` cleanly, so this is not a heater stability fault.
- The active G-code already has:
  - `brim_width = 12`
  - `z_seam_position = backleft`
  - part cooling disabled / slicer `M106/M107` removed

Profile response for the next slice:

- normal PLA temperature: `222C -> 224C`
- first layer temperature: keep `225C`
- add mild flow compensation:
  - total flow `103%`
  - wall flow `103%`
  - outer wall flow `102%`
  - top / bottom flow `102%`
  - infill flow `101%`

Reasoning:

- Moving the crack upward is progress: first-layer adhesion and lower-wall bonding improved, but residual shrink stress is still finding a weak layer higher in the model.
- The next safest lever is slightly hotter extrusion plus mild flow compensation, not fan tuning.
- Do not change brim, supports, or geometry yet; keep the experiment narrow.

## 2026-05-11 PLA Profile V4: Random Seam And Stronger Walls

Field observation:

- After the hotter / mild-flow `v3` profile, the crack remained in the same physical corner and at the same height.
- That makes a pure temperature / extrusion fix unlikely.
- G-code around `Z ~= 15 mm` repeatedly transitions through the same corner area, so the current failure looks like concentrated Z-seam / corner stress rather than missing support.

Profile response for the next slice:

- `wall_line_count`: `4 -> 5`
- `z_seam_type`: `back -> random`
- keep:
  - normal PLA temperature `224C`
  - first layer `225C`
  - `brim_width = 12`
  - part cooling off / slicer fan commands stripped
  - mild flow compensation from `v3`
- do not enable Cura Draft Shield by default

Operator note:

- Use a physical draft wall / wind shield around the printer instead of Cura Draft Shield.
- If the crack turns into small scattered seam marks, the seam was the main culprit.
- If the crack remains in exactly the same physical corner and height, the next fix should be in the model geometry: fillet / chamfer / local reinforcement at that stress riser.

## 2026-05-11 Orientation Test: Upside Down With Supports

Field observation during print:

- The part appears to be printing upside down with supports.
- No crack is visible during the active print so far.
- Final inspection after print:
  - part quality is good
  - walls have no cracks
  - supports are difficult to remove cleanly

Why this matters:

- This test changes more than one variable at once:
  - model orientation
  - support contact / load path
  - effective stress direction during cooling
  - likely visible seam location relative to the previous physical corner
- Therefore, do not treat it as proof that only one Cura setting fixed the crack.

What to inspect after completion:

- Whether the old crack location is gone entirely or only moved.
- Whether random seam creates small scattered surface marks instead of one vertical crack.
- Whether supports damaged the visible face or left acceptable cleanup marks.
- Whether bottom warp / lifted corners improved or got worse in the new orientation.

## 2026-05-11 PLA Profile V5: Easy-Release Supports

Field result from the upside-down support print:

- Crack problem is solved in this orientation / support workflow.
- Main remaining issue is support cleanup difficulty.
- Keep the successful orientation, `5` walls, random seam, `224C`, and mild flow compensation.

Profile response for the next slice:

- support infill: `12% -> 10%`
- support interface density: `85% -> 65%`
- support roof density: `85% -> 65%`
- support interface height: `0.8 mm -> 0.48 mm`
- support roof height: `0.8 mm -> 0.48 mm`
- support XY distance: `0.2 mm -> 0.3 mm`
- keep support Z distance / top distance at `0.16 mm` for now

Reasoning:

- Reducing dense interface / roof contact should make support removal easier while preserving underside quality better than immediately doubling the Z gap.
- If supports are still too hard to remove, the next separate test should increase support Z distance / top distance to `0.24-0.32 mm`, accepting a rougher supported underside.

## 2026-05-11 First-Layer Failure After Bed Calibration

Field observation:

- A later print detached from the bed at all four corners from the beginning.
- The operator had calibrated the bed before this attempt.
- The active profile still keeps the first-layer adhesion settings unchanged:
  - `brim_width = 12`
  - first-layer hotend `225C`
  - first-layer speed `6 mm/s`
  - initial layer line width `150%`

Interpretation:

- Because all four corners lifted immediately, this is more likely a first-layer / bed-state issue than a support-removal profile issue.
- Most likely causes:
  - nozzle too high after bed calibration / saved start
  - external warm bed not soaked long enough
  - surface contamination after handling / support cleanup
  - first layer visually round rather than flattened/squished

Next action:

- Do not change Cura support settings yet.
- Re-check start pose and first-layer squish on the warm bed.
- Clean the perforated mat before retrying.
- During the next start, inspect brim lines: they should be continuous and slightly flattened, not round strings sitting on top of the surface.

## Printer Notes

- Printer model: Easythreed K9
- Intended workflow: `Cura -> slice -> save G-code to TF card -> print from printer`
- USB is not currently treated as the primary print path.
- Earlier USB detection was confused by another device (`OrangePi` serial console).

## Safety Rules For The Incoming Second K9

The incoming protected second Easythreed K9 must not be sacrificed to experiments.

Treat it as a protected reference printer:

- Do not flash experimental firmware first.
- Do not swap motor plugs, fan plugs, or stepper drivers first.
- Do not run destructive homing or repeated hard-stop tests first.
- Do not delete service files from its card blindly.
- Do not assume its board is wired exactly like the first K9 until checked.

Mandatory first steps on the second K9:

1. Make a full TF-card backup before changing anything.
2. Record stock behavior before changing anything:
   - photos of the board and wiring
   - visible file layout on the card
   - firmware identity / version if readable
   - motion mapping of X / Y / Z
   - fan behavior
3. Start with the least invasive checks only:
   - read-only USB queries
   - small manual jogs
   - visual inspection
4. Only after the baseline is documented may we decide whether to:
   - keep it stock as a known-good control printer
   - or migrate it carefully toward the Little Hands baseline

Project rule:

- The first K9 may remain the experimental / repair unit.
- The second K9 must be handled as the “do not break this one” machine until a complete stock baseline is captured.
- Second-K9 rollout guide:
  - [SECOND_K9_INTAKE.md](/home/maxim/draftCode/littleHands/SECOND_K9_INTAKE.md)
  - [SECOND_K9_ROLLOUT.md](/home/maxim/draftCode/littleHands/SECOND_K9_ROLLOUT.md)

## Second K9 External Warm Bed Note

- The incoming second `K9` uses an external heated bed, not one electrically driven by the printer mainboard.
- Operational assumption for rollout:
  - preheat the bed externally to `40–50C`
  - keep Cura `material_bed_temperature = 0`
  - do not rely on `M140/M190` for normal printing
- A separate Cura machine/profile was prepared so the damaged first-printer setup is not overwritten:
  - machine: `lilHands K9 warm mat`
  - profile: `codex - K9 warm mat cautious`

## Active Cura Setup

- Machine name in Cura: `lilHands`
- Visible print profile family:
  - `codex - base`
  - `codex - strength`
- Material: `Generic PLA`

## codex1 Baseline Settings

- Layer height: `0.20 mm`
- Initial layer height: `0.20 mm`
- Walls: `3`
- Top layers: `5`
- Bottom layers: `5`
- Infill: `12%`
- Adhesion: `Brim`
- Brim width: `6 mm`
- Support: `Off`
- Ironing: `Off`
- Nozzle temperature: `208 C`
- Initial nozzle temperature: `210 C`
- Bed temperature: `0 C`
- Print speed: `28 mm/s`
- Wall speed: `24 mm/s`
- Top/bottom speed: `24 mm/s`
- Infill speed: `30 mm/s`
- Initial layer speed: `15 mm/s`
- Travel speed: `40 mm/s`
- Retraction: `6.5 mm`
- Retraction speed: `25 mm/s`
- Fan: `100%`

## Profile Meanings

### `codex - base`

Use this when:

- you want the already-proven adhesion baseline
- you are checking geometry
- you want to compare a future change against the first successful print

Behavior summary:

- stronger cooling
- lower print temperature
- lighter walls/infill
- better as a reference profile than as a hard-use profile

### `codex - strength`

Use this when:

- the part must survive handling or repeated use
- interlayer strength matters more than cosmetic sharpness
- the `base` profile printed correctly but felt brittle

Behavior summary:

- hotter printing
- slower movement
- lower fan
- thicker shell
- more infill
- intended to improve layer bonding and mechanical durability

## codex - strength Settings

- Layer height: `0.20 mm`
- Initial layer height: `0.20 mm`
- Walls: `4`
- Top layers: `6`
- Bottom layers: `6`
- Infill: `35%`
- Infill pattern: `Grid`
- Adhesion: `Brim`
- Brim width: `10 mm`
- Support: `Off`
- Ironing: `Off`
- Nozzle temperature: `218 C`
- Initial nozzle temperature: `220 C`
- Bed temperature: `0 C`
- Print speed: `20 mm/s`
- Wall speed: `18 mm/s`
- Top/bottom speed: `18 mm/s`
- Infill speed: `22 mm/s`
- Initial layer speed: `10 mm/s`
- Travel speed: `35 mm/s`
- Retraction: `6.5 mm`
- Retraction speed: `22 mm/s`
- Fan: `55%`
- Initial layer line width factor: `125%`

## Files Touched

- `/home/maxim/.config/cura/4.13/cura.cfg`
- `/home/maxim/.config/cura/5.11/cura.cfg`
- `/home/maxim/.local/share/cura/4.13/...`
- `/home/maxim/.local/share/cura/5.11/...`
- `/home/maxim/.local/share/applications/UltiMaker-Cura.desktop`
- `/home/maxim/.local/share/applications/cura-slicer_cura.desktop`
- `/home/maxim/.local/share/icons/hicolor/128x128/apps/cura-icon.png`
- `/home/maxim/.local/share/icons/hicolor/256x256/apps/cura-icon.png`

## Open Questions

- Confirm in the Cura UI that `codex1` is visible and selected after restart.
- Verify that saving directly to `/media/maxim/LHprint` feels reliable in day-to-day use.
- Validate the first real print and adjust the profile based on first-layer behavior.
- Compare `codex - strength` directly against the successful `codex - base` print on the same model.

## Next Print Checklist

1. Restart Cura fully.
2. Confirm machine `lilHands`.
3. Confirm profile `codex1`.
4. Load a simple test box or cube.
5. Slice and save G-code to `LHprint`.
6. Run the print.
7. Record first-layer result and any defects here.

## Session Notes

- Official Cura 5.11.0 AppImage was downloaded and prepared.
- Launcher/icon mismatch was fixed so the app icon matches the window more reliably.
- A visible profile named `codex1` was created for the `lilHands` machine.
- First live print attempt started with model `connector.stl`.
- Bed surface note: a PTFE-like overlay on the bed showed poor adhesion for PLA.
- Observed failure: the part started detaching almost immediately.
- User plans to try a double-sided tape surface as the next adhesion experiment.
- Double-sided tape thickness used for the next attempt: `0.1 mm`.
- A normal paper-drag test is awkward on sticky tape, so comparison should be based mainly on print behavior and whether the nozzle is scraping or printing too high.
- `codex1` was updated for the next adhesion-focused attempt:
  - `brim_width = 10`
  - `speed_layer_0 = 10`
  - `material_print_temperature_layer_0 = 215`
- Second attempt status on `connector.stl` with `0.1 mm` double-sided tape:
  - Adhesion is good across the whole bed.
  - First layers look dense and stable.
  - No critical early-layer defects observed.
  - In corners, the nozzle slightly disturbs the tape surface and creates a small messy mix of filament and tape.
  - Working hypothesis: nozzle is slightly too close to the taped surface, especially in corners.
  - Hole channels may be partially closed in print, but post-processing with a drill is acceptable for this part.
- `connector.stl` finished successfully.
- Part quality summary:
  - geometry is generally good
  - channels are through, though walls are rough
  - surface is glossy
  - the part is mechanically too brittle
  - interlayer bonding is weak and breaks easily
  - weakness is especially noticeable near the base
- Interpretation:
  - adhesion problem is solved
  - current profile favors shape retention more than strength
  - likely causes are too much cooling, too low effective bonding temperature, too little shell/infill for a hard-working part

## Current Working Conclusions

- Plain PTFE-like bed surface is not reliable enough for PLA on this printer.
- Thin double-sided tape greatly improves adhesion.
- Current first-layer settings are close to usable.
- Next tuning target after this print should be reducing corner over-squish without losing adhesion.
- A second strength-focused profile `codex2` was created and made active.
- `codex2` changes relative to `codex1`:
  - lower fan: `55%`
  - higher print temperatures: `220C` first layer, `218C` after
  - slower print: `20 mm/s`
  - thicker shell: `4 walls`
  - more top/bottom: `6 / 6`
  - stronger infill: `35%`
  - gentler first-layer squash: `initial_layer_line_width_factor = 125`
- Cura profile naming was clarified for easier switching:
  - `codex - base` = geometry / adhesion baseline
  - `codex - strength` = stronger mechanical version
  - current active profile = `codex - strength`
- Next planned comparison print:
  - restart Cura
  - select `codex - strength`
  - print the model again
  - compare strength, base quality, hole quality, and surface finish against the previous result

## Last Completed Print

- Model: `connector.stl`
- Profile used: `codex - base`
- Bed surface: `0.1 mm` double-sided tape over the bed
- Adhesion result: good across the full bed
- First-layer result: dense and stable
- Corner behavior: slight tape disturbance / over-squish in corners
- Geometry result: acceptable
- Channels: through, with rough internal walls
- Surface finish: glossy
- Mechanical result: too brittle for intensive use
- Main failure mode: weak interlayer bonding, especially near the base

## Current Action

- User is restarting Cura now.
- User will select `codex - strength`.
- User will send the same model to print for a strength comparison run.
- `codex - strength` print has started.
- Immediate observations from the live start:
  - print is visibly slower, as expected
  - lower speed is acceptable for this use case
  - real fan behavior does not seem much lower by sound alone
  - user has a manual hardware fan regulator available if needed later
  - during roughly the first one to one-and-a-half loops of the first layer, little or no plastic came out
  - after that, extrusion started normally
  - current adhesion is good

## Live Hypotheses For The Current Print

- The fan setting in Cura may not map cleanly to the actual hardware fan behavior on this printer.
- The delayed extrusion at the start suggests weak priming / purge behavior rather than a pure adhesion problem.
- A future improvement may be to add a more explicit start purge line or stronger prime routine before the first layer starts.

## codex - strength Interim Result

- Compared with the previous attempt, the new part is much stronger.
- The part now tolerates elastic deformation better before failure.
- This is a meaningful mechanical improvement and suggests the hotter / slower / lower-fan profile helped layer bonding.
- End-of-print custom behavior did not fully happen as expected in this run:
  - bed did not move fully forward
  - no melody happened
  - print head only moved slightly upward
- Likely explanation:
  - the current print may have used an older already-sliced G-code
  - or the machine ignored part of the custom end sequence
- Next work is moving from calibration pieces to a useful real part: a housing component for the future device.

## Storage Incident

- On the current session, the microSD card reader appeared in the OS as:
  - USB reader: `Super Top microSD card reader (SY-T18)`
  - block device: `/dev/sdb`
  - partition: `/dev/sdb1`
- The partition table is present and the partition type is DOS `0x0c` (FAT32 LBA style).
- However, the filesystem on `/dev/sdb1` is not currently recognized by the OS:
  - `IdType` is empty
  - `IdLabel` is empty
  - `IdUsage` is empty
  - auto-mount fails because it is "not a mountable filesystem"
- Interpretation:
  - the card reader works
  - the partition exists
  - the filesystem on the card is likely damaged or unreadable
- This means the current blocking issue is below Cura level.
- Practical expectation:
  - if Linux cannot identify a filesystem on `/dev/sdb1`, the Easythreed K9 is very unlikely to read the card successfully
  - the printer firmware is simpler and usually expects a clean FAT-formatted card
- Re-check later in the same session showed recovery / re-detection:
  - `/dev/sdb1` is now recognized as `vfat FAT32`
  - label: `LHPRINT`
  - UUID: `6CA7-7F49`
  - mounted at `/media/maxim/LHPRINT`
- Interpretation:
  - the earlier failure was likely a transient card/reader/contact/init issue rather than a permanently broken card
  - note the mount path is currently uppercase `LHPRINT`, not the earlier lowercase-style `LHprint`

## What To Compare After The Next Print

- Does the part feel less brittle?
- Do layers resist snapping better by hand?
- Is the base stronger than before?
- Did roughness or over-extrusion get worse?
- Did the hotter / slower / lower-fan profile deform the channels or improve them?
- Did the glossy look change toward a tougher-looking bead fusion?

## Firmware / Monitoring Research

- Official manual path for the K9 is still TF-card based printing.
- The manual describes the USB port as being for firmware update use, not as the primary normal print workflow.
- Community firmware options do exist for some K9 units, especially those using the `ET4000+` / `ET4000PLUS` family of boards.
- Important limitation:
  - K7/K9 printers were sold with multiple different boards
  - community firmware is board-specific
  - flashing the wrong build is a real brick risk
- A promising path exists if the printer has the `ET4000+` style board:
  - custom Marlin-based firmware with serial/USB control
  - possible OctoPrint / SimplyPrint style monitoring afterward
- This is not yet a "safe default" upgrade.
- Before flashing anything, the board revision should be confirmed physically.

## USB Probe During Live Print

- User connected the printer board to the computer with a USB cable during an active print.
- Immediate host-side probe showed:
  - no new `/dev/ttyUSB*`
  - no new `/dev/ttyACM*`
  - no obvious new USB device entry corresponding to the printer
- Interpretation:
  - the current USB connection is not exposing an ordinary host-serial printer interface to Linux
  - this may be caused by one of:
    - power-only / bad USB cable
    - stock firmware not exposing usable host serial
    - board/USB path only intended for firmware/update scenarios
    - USB enumeration behavior that differs from a normal Marlin serial printer
- Current conclusion:
  - board revision cannot be identified remotely from the present USB session alone
  - physical board inspection is still the most reliable identification path if USB remains silent

## Mainboard Identification Result

- Physical inspection found the printer mainboard to be `ET-4000+`.
- This is important because community firmware support for K9 exists specifically for the `ET4000+` family.
- This moves the printer from "unknown board / unsafe to plan flashing" to "board family appears supported by community firmware paths".
- Community firmware binary prepared locally:
  - source family: `ECF-Marlin`
  - target: `K9 ET-4000+`
  - local file: `/home/maxim/draftCode/littleHands/firmware/ecf-k9-et4000plus-mksLite.bin`
  - size: `138676 bytes`
  - sha256: `76b20caf87ad2d1f79ec855d59bb3ec6680260e243aafeecae19ddd9969fb8eb`
- Flashing was not completed yet because the printer microSD card is currently not inserted in the computer.
- Later, the printer microSD card was reinserted and prepared for flashing:
  - card mountpoint before unmount: `/media/maxim/LHPRINT`
  - full card backup stored at:
    `/home/maxim/draftCode/littleHands/card_backups/LHPRINT_preflash_2026-04-29`
  - firmware copied to card as:
    `/media/maxim/LHPRINT/mksLite.bin`
  - file hash on card matched the local firmware hash
  - card was cleanly unmounted afterward with `udisksctl unmount -b /dev/sdb1`
- Card contents at flash-prep time included:
  - `CFFFP_connector.gcode`
  - `mksLite.bin`
- No original `mksLite.CUR` file was present on the card at preparation time, so rollback from card-stored stock firmware is not currently available from this specific card snapshot.
- Card was then cleaned to be more "flash-only":
  - user G-code file removed from the card
  - `mksLite.bin` left on the card
  - Windows-style `System Volume Information` folder remained, which is normally harmless on FAT cards
- Final intended flash card state:
  - firmware file present: `mksLite.bin`
  - card unmounted and ready to insert into printer
- After the flash attempt, the card was reinserted in the computer and showed:
  - `mksLite.bin` had been renamed to `mksLite.CUR`
  - file present on card: `mksLite.CUR` with size `138676`
- Interpretation:
  - the ET-4000+ bootloader did process the firmware file
  - flashing appears to have at least been accepted by the board
  - next validation step is live functional testing of the printer and USB behavior
- Post-flash live printer test:
  - printer powers on
  - print head moved on startup
  - LED stays solid
  - pressing the bed-level button caused the printer to run into the edge, buzz for a while, then stop
- This suggests:
  - firmware is running
  - but at least one stock interaction path may now behave differently or less safely than before
  - motion / homing should be treated cautiously until behavior is better understood
- Post-flash USB result:
  - printer now enumerates as a CH340 serial adapter on `/dev/ttyUSB0`
  - a direct `M115` query succeeded
  - firmware response:
    - `FIRMWARE_NAME: Marlin 2.1.2.1`
    - build date: `Sep 19 2024`
    - `EEPROM:1`
    - `SDCARD:1`
    - `SD_WRITE:1`
    - `HOST_ACTION_COMMANDS:1`
    - `AUTOREPORT_TEMP:1`
- Major outcome:
  - the custom firmware flash succeeded
  - USB serial host communication is now working
  - remote monitoring / OctoPrint-style integration is now realistically possible

## Safe Serial Diagnostics After Flash

- A safe serial session was run without motion commands.
- Commands sent:
  - `M115`
  - `M105`
  - `M503`
  - `M106 S0`
  - `M106 S255`
  - `M106 S0`
- Observed results:
  - `M115` returned a valid Marlin 2.1.2.1 identity string
  - `M105` returned live temperature data:
    - nozzle around `23C`
    - bed reported `-15C` with target `0C`
  - `M503` returned stored configuration successfully
  - all fan commands returned `ok`
- Important interpretation:
  - host serial communication is healthy
  - firmware-level fan control commands are accepted
  - accepted `M106` commands do not yet prove that the physical fan is really under firmware control
  - physical confirmation still depends on whether fan sound / airflow changed during the command sequence
- Physical observation after the test:
  - fan sound did not noticeably change during `M106 S0 -> M106 S255 -> M106 S0`
- Working interpretation:
  - the stock physical fan in use is likely not connected to the firmware-controlled fan output
  - or the audible fan is a different always-on fan than the one mapped to `M106`

## Temperature Telemetry Result

- Temperature-by-request works:
  - `M105` returns live hotend temperature data
- Periodic temperature auto-report also works:
  - `M155 S2` enabled temperature reports every ~2 seconds
  - reports were received successfully
  - `M155 S0` disabled the auto-report again
- Practical outcome:
  - temperature telemetry is available over USB
  - we can monitor hotend temperature in real time from the host
- Current caveat:
  - bed temperature reports are nonsensical (`B:-15C`) for this printer and should not be treated as meaningful

## Auto-Fan Safety Test

- A no-motion hotend heating test was run to check whether the single fan on `FAN1` auto-starts from temperature alone.
- Sequence used:
  - `M155 S2`
  - `M106 S0`
  - `M104 S80`
  - wait for hotend to rise close to `80C`
  - `M104 S0`
  - `M155 S0`
- Serial-side result:
  - hotend rose from about `30C` to about `79C`
  - heater control was active during the climb
  - no explicit fan-on command was sent during the test
- Practical interpretation:
  - if the fan did not audibly start by itself during this temperature climb, then `FAN1` is not acting as an automatic hotend-temperature safety fan in the current firmware behavior

## Fan Rewire Direction

- Current likely situation:
  - Marlin accepts `M106`
  - board/firmware appears to have a controllable fan channel
  - the physically audible fan is likely not wired to that controllable output
- Best hardware goal:
  - keep the hotend heatsink fan on a permanent always-on supply if needed
  - move only the part-cooling fan to the firmware-controlled fan output
- Before rewiring:
  - identify which fan is the always-on hotend/heatsink fan
  - identify which fan is the part-cooling fan / blower
  - identify the board-side fan output that responds to `M106`
- Hardware observation on the ET-4000+ board:
  - two fan headers are visible: `FAN1` and `FAN2`
  - current fan is plugged into `FAN2`
  - `FAN1` is currently empty
- Hardware confirmation by live test:
  - the fan was temporarily moved to `FAN1`
  - the printer was powered on with USB connected
  - `M106 S255`, `M106 S128`, `M106 S0` were sent
  - the fan audibly changed speed in multiple steps
  - the fan stopped again at `S0`
- Conclusion:
  - `FAN1` is the firmware-controlled fan output
  - `M106` control is physically working
  - `FAN2` is therefore the likely always-on fan output
- Important user clarification:
  - the printer appears to have only one fan in total
  - that fan is the fan cooling the print head / hotend area
  - it is currently connected to `FAN1` and is firmware-controlled
- Implication:
  - if this single fan is the hotend heatsink cooling fan, leaving it under normal `M106` control may be unsafe
  - a hotend heatsink fan usually should be always on while the printer is powered, or at least automatically tied to hotend temperature
  - if no separate part-cooling fan exists, then "controlled fan" and "hotend safety fan" are currently the same physical fan
- Current user decision:
  - keep the existing head/hotend-area fan on `FAN1`
  - monitor behavior carefully
  - explore adding a second fan later rather than reverting immediately
- Design consequence:
  - future fan planning should distinguish between:
    - a safety / hotend heatsink cooling fan
    - a print / part-cooling fan
- End-of-print behavior was improved in Cura:
  - hotend off
  - bed off
  - small retract
  - `Z` lift by `10 mm`
  - move head to `X95`
  - move bed fully forward to `Y0`
  - motors off
- A servo-based melody was not added because this printer does not expose confirmed servo hardware in the slicing workflow, and adding an unverified motion-based tune would be more risk than value.

## 2026-04-29 Firmware Fan Safety Investigation

- User confirmed by live test that the flashed community firmware does **not** auto-start the single physical fan on `FAN1` during hotend warmup.
- Source repository used for investigation:
  - `/home/maxim/draftCode/littleHands/firmware_src/EasyThreeD-K9_ET4000PLUS`
- Root cause found in source:
  - `config/EasyThreeD/ET4000PLUS/Configuration_adv.h`
  - `E0_AUTO_FAN_PIN` is set to `-1`, so classic Marlin extruder auto-fan is disabled
  - the board pin file exposes only one Marlin-controlled fan pin:
    - `Marlin/src/pins/stm32f1/pins_MKS_ROBIN_LITE.h`
    - `FAN0_PIN = PA8`
- Architectural constraint found in Marlin:
  - `SanityCheck.h` rejects `E0_AUTO_FAN_PIN == FAN0_PIN`
  - so the usual config-only approach cannot make the same physical fan both `M106` fan and `E0_AUTO_FAN`
- Chosen fix:
  - add an EasyThreeD-specific `FAN0` safety guard instead of trying to reuse Marlin auto-fan
  - this guard forces `FAN0` on whenever:
    - hotend target is non-zero, or
    - measured hotend temperature is at or above guard threshold
- Files changed for this fix:
  - `/home/maxim/draftCode/littleHands/firmware_src/EasyThreeD-K9_ET4000PLUS/Marlin/Configuration_adv.h`
  - `/home/maxim/draftCode/littleHands/firmware_src/EasyThreeD-K9_ET4000PLUS/config/EasyThreeD/ET4000PLUS/Configuration_adv.h`
  - `/home/maxim/draftCode/littleHands/firmware_src/EasyThreeD-K9_ET4000PLUS/Marlin/src/module/temperature.h`
- New config knobs added:
  - `EASYTHREED_FAN0_GUARD`
  - `EASYTHREED_FAN0_GUARD_TEMPERATURE = 45`
  - `EASYTHREED_FAN0_GUARD_SPEED = 255`
- Build preparation:
  - copied the ET4000+ example configs into `Marlin/Configuration.h` and `Marlin/Configuration_adv.h` so PlatformIO would build the correct target configuration instead of the generic Marlin defaults
- Build result:
  - environment: `mks_robin_lite_maple`
  - build status: `SUCCESS`
  - output binary: `/home/maxim/draftCode/littleHands/firmware/custom-hotend-fan-guard-mksLite.bin`
  - sha256: `4a73c0ccb6b995dbfc38ffd4847655a7cbd8613ecb67aea73e4951b49c0547eb`
- Expected runtime behavior of this custom build:
  - the single fan on `FAN1` should start automatically as soon as the hotend has a target temperature
  - the fan should stay on while the hotend remains warm above about `45C`
  - slicer `M106` commands can no longer reduce this fan below the safety minimum while the hotend is hot
  - this intentionally prioritizes hotend safety over part-cooling behavior on the single fan
- Not yet done at this point:
  - flash the custom `custom-hotend-fan-guard-mksLite.bin`
  - verify on hardware that the fan now starts automatically during warmup

## 2026-04-29 Fan Guard Flash Preparation

- The microSD card was inserted again and mounted at:
  - `/media/maxim/LHPRINT`
- The card contained only:
  - `mksLite.CUR`
- That previous firmware image was backed up to:
  - `/home/maxim/draftCode/littleHands/card_backups/LHPRINT_preflash_fanguard_2026-04-29/mksLite.CUR`
- The card was then prepared for the new fan-guard firmware:
  - removed old `mksLite.CUR`
  - copied `/home/maxim/draftCode/littleHands/firmware/custom-hotend-fan-guard-mksLite.bin`
  - renamed on card as `mksLite.bin`
- Verification:
  - `/media/maxim/LHPRINT/mksLite.bin`
  - sha256 on card matches local build:
  - `4a73c0ccb6b995dbfc38ffd4847655a7cbd8613ecb67aea73e4951b49c0547eb`
- Expected next verification steps after flashing:
  - bootloader renames `mksLite.bin` to `mksLite.CUR`
  - hotend fan should auto-start during warmup without any `M106`

## 2026-04-29 Fan Guard Flash Result

- After flashing, the card returned with:
  - `mksLite.CUR`
  - `EEPROM.DAT`
- Verification:
  - `mksLite.CUR` sha256 = `4a73c0ccb6b995dbfc38ffd4847655a7cbd8613ecb67aea73e4951b49c0547eb`
  - this matches the custom fan-guard build exactly
- Conclusion:
  - the printer bootloader accepted the new custom firmware image
- Immediate next step still pending:
  - reconnect the powered printer by USB
  - verify that the fan auto-starts during warmup without `M106`

## 2026-04-29 Fan Guard Runtime Verification

- The printer was reconnected by USB after flashing the fan-guard firmware.
- Serial verification:
  - port: `/dev/ttyUSB0`
  - USB bridge: `CH340`
  - reported firmware:
    - `Marlin 2.1.2.5 (Apr 29 2026 16:17:50)`
- Test sequence:
  - `M155 S2`
  - `M106 S0`
  - `M104 S80`
  - observe fan behavior
  - `M104 S0`
  - `M155 S0`
- User observation:
  - the fan auto-started on its own
  - airflow changed during the test
  - the fan later shut off again after cooldown
- Conclusion:
  - the custom fan-guard firmware is working on the real printer
  - the printer now has automatic fan behavior for the single head fan during hotend heating / warm state

## 2026-04-29 Saved Firmware And Monitoring Kit

- Saved a clearer firmware pack for reuse with another printer of the same type:
  - binary: `/home/maxim/draftCode/littleHands/firmware/friend_pack/K9_ET4000PLUS_single_fan_guard_mksLite.bin`
  - checksum: `4a73c0ccb6b995dbfc38ffd4847655a7cbd8613ecb67aea73e4951b49c0547eb`
  - notes: `/home/maxim/draftCode/littleHands/firmware/README_friend_et4000plus_single_fan.md`
  - detailed Russian guide: `/home/maxim/draftCode/littleHands/firmware/friend_pack/FRIEND_UPGRADE_GUIDE_RU.md`
- Added a local USB monitor tool:
  - `/home/maxim/draftCode/littleHands/tools/k9_usb_monitor.py`
  - purpose:
    - show live `M155` temperature telemetry
    - periodically query SD print status with `M27`
    - keep an eye on a card-based print over USB
- Added a local SD uploader tool for USB:
  - `/home/maxim/draftCode/littleHands/tools/k9_sd_upload.py`
  - verified behavior:
    - `M28` / `M29` file upload mode works
    - raw plain-text G-code lines are rejected in upload mode
    - Marlin line numbers + checksums are accepted
  - implication:
    - sliced G-code can be uploaded to the printer SD over USB
    - this is not ordinary file copying; it requires Marlin SD upload protocol

## 2026-04-29 Cura Profile For This Firmware

- Created and selected a new active Cura profile:
  - `codex - monitored strength`
- Cura container changes:
  - machine stack now points to `codex3_user` / `codex3_quality`
  - extruder stack now points to `codex3_extruder_user` / `codex3_extruder_quality`
- Profile intent:
  - preserve the stronger mechanical settings already validated on the printer
  - pair that print behavior with live USB monitoring
- Important limitation:
  - because this printer currently has only one physical fan, the firmware still prioritizes hotend safety over true independent part-cooling behavior
  - Cura can still carry fan targets, but actual fan behavior is constrained by the firmware guard while the hotend is active

## 2026-04-29 Direct USB Print Attempt

- Goal:
  - print `CFFFP_zeroBottom.gcode` directly over USB, without using the card as the active print source
- Created helper:
  - `/home/maxim/draftCode/littleHands/tools/k9_usb_print.py`
- First direct-print attempt failed at:
  - `G28`
- Observed printer response:
  - `echo:Homing Failed`
  - `Error:Printer halted. kill() called!`
- Root cause:
  - `VALIDATE_HOMING_ENDSTOPS` was still enabled in the ET4000+ firmware config
  - this matches the warning in the upstream ET4000+ notes that K7/K9-style motion without normal X/Y feedback should not use that validation

## 2026-04-29 Firmware Revision For USB Printing

- Changed in firmware config:
  - disabled `VALIDATE_HOMING_ENDSTOPS`
- Files updated:
  - `/home/maxim/draftCode/littleHands/firmware_src/EasyThreeD-K9_ET4000PLUS/Marlin/Configuration.h`
  - `/home/maxim/draftCode/littleHands/firmware_src/EasyThreeD-K9_ET4000PLUS/config/EasyThreeD/ET4000PLUS/Configuration.h`
- Rebuilt firmware successfully.
- New binary:
  - `/home/maxim/draftCode/littleHands/firmware/custom-hotend-fan-guard-no-validate-mksLite.bin`
- SHA256:
  - `c6d2933678e50fb6d875ffc46c3c4f79653764fd77a95dd91a1071bf45e667c2`
- Next required step:
  - flash this revised build through the usual `mksLite.bin` SD-card method
  - then retry direct USB printing

## 2026-04-29 No-Validate Flash Preparation

- Card prepared for the revised build at:
  - `/media/maxim/LHPRINT/mksLite.bin`
- Previous flashed image backed up to:
  - `/home/maxim/draftCode/littleHands/card_backups/LHPRINT_preflash_no_validate_2026-04-29/mksLite.CUR`
- Prepared binary on card:
  - `/home/maxim/draftCode/littleHands/firmware/custom-hotend-fan-guard-no-validate-mksLite.bin`
- Card copy SHA256 verified:
  - `c6d2933678e50fb6d875ffc46c3c4f79653764fd77a95dd91a1071bf45e667c2`

## 2026-04-29 Soft Fan-Guard Firmware Revision

- Problem found during direct USB print:
  - the previous single-fan guard forced `FAN0` to `255` whenever the hotend had a target
  - this kept the hotend fan at full blast during `M109`, so the printer could sit hot and never proceed to motion
- Goal of the revision:
  - keep single-fan hotend safety
  - stop overcooling during warmup
  - let the printer reach and hold the requested print temperature more naturally
- Firmware logic changed from:
  - one hard minimum speed while target > 0
- Firmware logic changed to:
  - `heating` minimum speed: `96`
  - `hold / near-target` minimum speed: `160`
  - `cooldown after target cleared` minimum speed: `128`
  - near-target window: `8C`
  - overshoot threshold: `3C`
- Files updated:
  - `/home/maxim/draftCode/littleHands/firmware_src/EasyThreeD-K9_ET4000PLUS/Marlin/Configuration_adv.h`
  - `/home/maxim/draftCode/littleHands/firmware_src/EasyThreeD-K9_ET4000PLUS/config/EasyThreeD/ET4000PLUS/Configuration_adv.h`
  - `/home/maxim/draftCode/littleHands/firmware_src/EasyThreeD-K9_ET4000PLUS/Marlin/src/module/temperature.h`
- Build status:
  - `platformio run -e mks_robin_lite_maple` completed successfully
- New binary:
  - `/home/maxim/draftCode/littleHands/firmware/custom-hotend-fan-guard-soft-mksLite.bin`
- SHA256:
  - `758cd67a175ac98aae45a8fb645d3e9f958d313c7b5898655ec437d622d054db`
- Card-write status at the end of the build:
  - first reconnect attempt did not expose the card to the OS
  - after reinsert, the card appeared again as `sdb`
  - `udisks2` format was used to recreate the filesystem as `FAT32`
  - label set to `LHPRINT`
  - mounted at `/media/maxim/LHPRINT`
  - current card contents snapshot saved to:
    - `/home/maxim/draftCode/littleHands/card_backups/LHPRINT_preflash_soft_guard_2026-04-29`
  - the card was then cleaned and prepared with only:
    - `/media/maxim/LHPRINT/mksLite.bin`
  - card copy SHA256 verified:
    - `758cd67a175ac98aae45a8fb645d3e9f958d313c7b5898655ec437d622d054db`
- Flash result:
  - after booting the printer from this card, `mksLite.bin` was renamed by the bootloader to `mksLite.CUR`
  - resulting file on card:
    - `/media/maxim/LHPRINT/mksLite.CUR`
  - flashed-image SHA256 verified:
    - `758cd67a175ac98aae45a8fb645d3e9f958d313c7b5898655ec437d622d054db`
  - the new soft fan-guard firmware is therefore confirmed written to the printer

## 2026-04-29 Soft Fan-Guard Validation

- USB check after flashing:
  - printer answered on `/dev/ttyUSB0`
  - `M115` reported:
    - `Marlin 2.1.2.5 (Apr 29 2026 17:54:33)`
- Important thermal behavior before the fix:
  - the previous guard could hold the fan too aggressively during warmup
  - direct USB prints could stall around `M109`
- Validation result with the new soft guard:
  - `M104 S180` successfully heated the hotend from about `117C` to `178C`
  - `M109 S180` also completed successfully
  - observed stable residency countdown:
    - `W:9 -> ... -> W:0`
  - final result:
    - `ok`
- Practical conclusion:
  - the new firmware no longer blocks normal temperature ramp-up
  - the printer can now reach and hold a commanded print temperature while still keeping the single-fan safety behavior

## 2026-04-29 Fast PWM Fan Revision

- New symptom after the soft-guard build:
  - the user still heard a persistent high-pitched whine while the fan was active at partial duty
- Live check:
  - the hotend was around `48C` with target `0`
  - this matches the soft-guard cooldown band, where the fan is intentionally still on
- Likely root cause:
  - audible PWM on the single fan at intermediate duty, not a thermal fault and not a stepper movement issue
- Firmware change:
  - enabled `FAST_PWM_FAN`
  - forced `FAST_PWM_FAN_FREQUENCY 31400`
- Files updated:
  - `/home/maxim/draftCode/littleHands/firmware_src/EasyThreeD-K9_ET4000PLUS/Marlin/Configuration_adv.h`
  - `/home/maxim/draftCode/littleHands/firmware_src/EasyThreeD-K9_ET4000PLUS/config/EasyThreeD/ET4000PLUS/Configuration_adv.h`
- Resulting binary:
  - `/home/maxim/draftCode/littleHands/firmware/custom-hotend-fan-guard-soft-fastpwm-mksLite.bin`
- SHA256:
  - `ba4ab131da77ecf1c043c9a783efbdd38c8a74e42c868485b6981b4e136ce91d`
- Expected effect:
  - keep the same soft single-fan guard behavior
  - significantly reduce or remove the audible PWM squeal from the fan
- Flash preparation:
  - card contents before this step saved to:
    - `/home/maxim/draftCode/littleHands/card_backups/LHPRINT_preflash_soft_fastpwm_2026-04-29`
  - card prepared with only:
    - `/media/maxim/LHPRINT/mksLite.bin`
  - card copy SHA256 verified:
    - `ba4ab131da77ecf1c043c9a783efbdd38c8a74e42c868485b6981b4e136ce91d`
  - card was unmounted and is ready to move into the printer

## 2026-04-29 Fan Start Threshold Revision

- Field check after the fast-PWM build:
  - the user physically verified that the new premium fan was not spinning during heating
  - this means the fan became quiet, but the minimum heating-duty was too low to guarantee startup
- Firmware adjustments:
  - enabled `FAN_KICKSTART_TIME 250`
  - enabled `FAN_KICKSTART_POWER 255`
  - raised `EASYTHREED_FAN0_GUARD_HEATING_SPEED` from `96` to `128`
- Files updated:
  - `/home/maxim/draftCode/littleHands/firmware_src/EasyThreeD-K9_ET4000PLUS/Marlin/Configuration_adv.h`
  - `/home/maxim/draftCode/littleHands/firmware_src/EasyThreeD-K9_ET4000PLUS/config/EasyThreeD/ET4000PLUS/Configuration_adv.h`
- New binary:
  - `/home/maxim/draftCode/littleHands/firmware/custom-hotend-fan-guard-soft-fastpwm-kickstart-mksLite.bin`
- SHA256:
  - `7f13d1875356afd087d46453224e402abf4812f64828ef873bd9276ac00bed63`
- Expected effect:
  - preserve quiet high-frequency PWM
  - still allow safe soft fan control
  - guarantee that the hotend fan actually starts when the guard first engages
- Flash preparation:
  - card contents before this step saved to:
    - `/home/maxim/draftCode/littleHands/card_backups/LHPRINT_preflash_soft_fastpwm_kickstart_2026-04-29`
  - card prepared with only:
    - `/media/maxim/LHPRINT/mksLite.bin`
  - card copy SHA256 verified:
    - `7f13d1875356afd087d46453224e402abf4812f64828ef873bd9276ac00bed63`
  - card was unmounted and is ready to move into the printer

## 2026-04-29 Fast-PWM Rollback Decision

- Manual PWM test result on the fast-PWM branch:
  - the fan did not spin at all, even when commanded manually through `M106`
  - this means the regression is not just "wrong duty threshold"
  - the fast-PWM experiment broke usable fan control on this hardware path
- Decision:
  - roll back to the last known-good `soft-guard` firmware
  - re-establish a working fan output first
  - only then continue temperature-behavior tuning from that stable point
- Rollback image selected:
  - `/home/maxim/draftCode/littleHands/firmware/custom-hotend-fan-guard-soft-mksLite.bin`
- SHA256:
  - `758cd67a175ac98aae45a8fb645d3e9f958d313c7b5898655ec437d622d054db`
- Rollback card prep:
  - backup of current card contents saved to:
    - `/home/maxim/draftCode/littleHands/card_backups/LHPRINT_rollback_from_fastpwm_2026-04-29`
  - rollback image copied to card as:
    - `/media/maxim/LHPRINT/mksLite.bin`
  - card copy SHA256 verified:
    - `758cd67a175ac98aae45a8fb645d3e9f958d313c7b5898655ec437d622d054db`
  - card unmounted and ready for flashing

## 2026-04-29 Manual PWM Sanity Check After Rollback

- User observation after rollback:
  - the fan again spins on manual PWM commands
  - it remains controllable across multiple duty levels
  - at low PWM it can reach an audible squeal region
- Conclusion:
  - the fan hardware itself is healthy
  - the controllable fan channel is healthy on the rollback firmware
  - the regression came from the later fast-PWM branch, not from the fan or the wiring
- Practical decision:
  - keep `custom-hotend-fan-guard-soft-mksLite.bin` as the stable base
  - if further tuning is needed, only tune guard duty values from this working branch
  - do not continue on the broken fast-PWM branch

## 2026-04-29 Moderate Fast-PWM Experiment

- User observation on the stable rollback branch:
  - fan control works again
  - the fan remains controllable across multiple PWM levels
  - the audible squeal begins roughly around `S208` and lower
- Design choice:
  - do not use periodic on/off fan control
  - instead try a moderate PWM frequency increase from the stable branch
  - avoid the previous `31.4kHz` branch that broke fan control entirely
- Changes for this experiment:
  - enabled `FAST_PWM_FAN`
  - set `FAST_PWM_FAN_FREQUENCY 7800`
  - reverted back to the softer stable guard baseline:
    - `FAN_KICKSTART` disabled
    - `EASYTHREED_FAN0_GUARD_HEATING_SPEED 96`
    - `EASYTHREED_FAN0_GUARD_HOLD_SPEED 160`
    - `EASYTHREED_FAN0_GUARD_COOLDOWN_SPEED 128`
- Files updated:
  - `/home/maxim/draftCode/littleHands/firmware_src/EasyThreeD-K9_ET4000PLUS/Marlin/Configuration_adv.h`
  - `/home/maxim/draftCode/littleHands/firmware_src/EasyThreeD-K9_ET4000PLUS/config/EasyThreeD/ET4000PLUS/Configuration_adv.h`
- New binary:
  - `/home/maxim/draftCode/littleHands/firmware/custom-hotend-fan-guard-soft-fastpwm-7k8-mksLite.bin`
- SHA256:
  - `6f9fd14efc2e357f58039d8c999f6f23674cfc949ea414cfe053e17f882b037c`
- Flash preparation:
  - card contents before this step saved to:
    - `/home/maxim/draftCode/littleHands/card_backups/LHPRINT_preflash_soft_fastpwm_7k8_2026-04-29`
  - card prepared with only:
    - `/media/maxim/LHPRINT/mksLite.bin`
  - card copy SHA256 verified:
    - `6f9fd14efc2e357f58039d8c999f6f23674cfc949ea414cfe053e17f882b037c`
  - card unmounted and ready for flashing

## 2026-04-29 Extreme Fast-PWM Experiment

- User requested a test with a strongly increased PWM frequency.
- Purpose:
  - determine whether this fan prefers true ultrasonic drive better than the moderate `7.8kHz` setting
  - answer the question experimentally instead of inferring from previous mixed-change branches
- Changes for this experiment:
  - `FAST_PWM_FAN` kept enabled
  - `FAST_PWM_FAN_FREQUENCY 31400`
  - all other guard values kept on the same soft baseline used in the experiment branch
- New binary:
  - `/home/maxim/draftCode/littleHands/firmware/custom-hotend-fan-guard-soft-fastpwm-31k4-mksLite.bin`
- SHA256:
  - `41d49b5e7e9edb166a70f0e34ddf865cada2ad17f9fa6fd245c44b00b93dd802`
- Flash preparation:
  - card contents before this step saved to:
    - `/home/maxim/draftCode/littleHands/card_backups/LHPRINT_preflash_soft_fastpwm_31k4_2026-04-29`
  - card prepared with only:
    - `/media/maxim/LHPRINT/mksLite.bin`
  - card copy SHA256 verified:
    - `41d49b5e7e9edb166a70f0e34ddf865cada2ad17f9fa6fd245c44b00b93dd802`
  - card unmounted and ready for flashing

## 2026-04-29 High-Frequency Fan Threshold Findings

- After flashing the `31.4kHz` build, the fan was tested step-by-step with manual `M106`.
- Observed behavior:
  - `S255`:
    - spins normally
    - noisy, but not squealing
  - `S254`:
    - spins normally
    - noisy, but not squealing
  - `S253`:
    - spins normally
    - noisy, but not squealing
  - `S252`:
    - spins
    - quieter than above
    - not squealing
  - `S251`:
    - does not spin
    - does not squeal
- Start behavior:
  - direct start from `S0 -> S252` works
- Practical conclusion:
  - with this fan on the `31.4kHz` branch, the usable non-squealing region is extremely narrow
  - the lowest confirmed self-starting quiet value is `S252`
  - anything below `S252` is not safe to assume for hotend protection

## 2026-04-29 Practical 31.4k Working Build

- Based on the measured threshold, a practical firmware was prepared with:
  - `FAST_PWM_FAN_FREQUENCY 31400`
  - `FAN_KICKSTART_TIME 250`
  - `FAN_KICKSTART_POWER 255`
  - `EASYTHREED_FAN0_GUARD_HEATING_SPEED 255`
  - `EASYTHREED_FAN0_GUARD_HOLD_SPEED 252`
  - `EASYTHREED_FAN0_GUARD_COOLDOWN_SPEED 252`
- New binary:
  - `/home/maxim/draftCode/littleHands/firmware/custom-hotend-fan-guard-31k4-kick255-hold252-mksLite.bin`
- SHA256:
  - `23b409118e134d3811b6395fe238595738374060d3278752b566b04fe120adb7`
- Flash preparation:
  - card contents before this step saved to:
    - `/home/maxim/draftCode/littleHands/card_backups/LHPRINT_preflash_31k4_kick255_hold252_2026-04-29`
  - card prepared with only:
    - `/media/maxim/LHPRINT/mksLite.bin`
  - card copy SHA256 verified:
    - `23b409118e134d3811b6395fe238595738374060d3278752b566b04fe120adb7`
  - card unmounted and ready for flashing

## How To Use This Log

After each test print, append:

- Model name
- Date
- Profile used
- Material
- First-layer result
- Surface quality
- Stringing / warping / adhesion notes
- What changed next

## 2026-04-29 SD Print Abort Due To Suspected Y-Axis Motion Fault

- Started SD print of `CFFFP_~1.GCO` from printer SD over the flashed `31.4kHz + kick255 + hold252` firmware.
- USB status confirmed the file was selected and started:
  - `M23 CFFFP_~1.GCO` -> `File selected`
  - `M24` accepted
- During the first layer, the user observed that the toolhead only moved left-right along one edge of the bed instead of tracing the expected perimeter around the model.
- Live serial status during this phase:
  - temperature reached and held target:
    - `ok T:220.00 /220.00`
  - SD progress advanced:
    - `SD printing byte 2992/1260365`
    - later `SD printing byte 16174/1260365`
- The sliced file itself contains normal 2D skirt motion with clear Y variation, so the observed behavior is not explained by the G-code:
  - example path includes both X and Y movement around the model perimeter in `/home/maxim/draftCode/littleHands/CFFFP_zeroBottom.gcode`
- Print was aborted over USB:
  - `M108`
  - `M524`
  - heaters and fan stop commands sent
- Post-abort status:
  - `M27` -> `Not SD printing`
  - `M105` -> `ok T:156.90 /0.00 ...`
- Working hypothesis:
  - a firmware / homing / axis-direction / endstop problem remains on axis `Y`
  - next step is a direct manual Y-axis movement test over USB before the next print attempt

## 2026-04-29 Manual Axis Test After SD Abort

- Manual USB movement test was run with relative moves.
- Observed behavior:
  - `X` motion is visible and correct in both directions.
  - `Y` commands are accepted by firmware and `M114` position changes accordingly.
  - physically, `Y` motion is not visible; only motor noise is heard.
- User observation:
  - on the `Y` move portion, there is mechanical noise but no visible axis motion
  - behavior resembles a stalled or miswired motor more than a planner / slicer problem
- Firmware pin mapping check:
  - `Y_STEP_PIN / Y_DIR_PIN / Y_ENABLE_PIN` are defined separately from `E0_*`
  - references:
    - `/home/maxim/draftCode/littleHands/firmware_src/EasyThreeD-K9_ET4000PLUS/Marlin/src/pins/stm32f1/pins_MKS_ROBIN_LITE.h`
- Conclusion at this stage:
  - the current firmware does not appear to map `Y` commands onto the extruder pins
  - the more likely fault is hardware-level on the Y axis path:
    - stalled Y motor
    - loose / bad motor connector
    - one coil open or intermittent
    - Y driver / board output issue
    - mechanical jam in the Y axis

## 2026-04-29 Minimal SD Axis Test Result

- A minimal SD test file `AXISTEST.GCO` was uploaded and started on the printer SD.
- File content:
  - no heating
  - no extrusion
  - `Z +10`
  - `X +30`, `X -30`
  - `Y +30`, `Y -30`
- Physical result reported by the user:
  - `Z` visibly moved upward
  - `X` visibly moved right then left
  - on the `Y` portion, the extruder motor buzzed twice
  - no visible Y-axis / bed motion
- Practical interpretation:
  - this is much stronger evidence that the current `Y` mapping ends up driving the extruder motor path in the real hardware setup
  - likely causes now narrow to:
    - Y and E motor connectors/wiring are swapped relative to the firmware expectation
    - the specific ET4000+ revision in this printer uses a different Y/E driver mapping than the current `pins_MKS_ROBIN_LITE.h` assumptions
- Next best diagnostic:
  - with power off, swap the physical Y-motor and E-motor plugs on the board
  - rerun the same minimal axis test
  - if Y then moves correctly, firmware pin mapping needs adjustment

## 2026-04-29 Firmware Build With Y/E Stepper Mapping Swapped

- Based on the minimal SD axis test, firmware was changed to swap the `Y` and `E0` stepper pin assignments.
- File changed:
  - `/home/maxim/draftCode/littleHands/firmware_src/EasyThreeD-K9_ET4000PLUS/Marlin/src/pins/stm32f1/pins_MKS_ROBIN_LITE.h`
- New logic:
  - `Y_*` now uses the pins that previously belonged to `E0_*`
  - `E0_*` now uses the pins that previously belonged to `Y_*`
- Existing working fan safeguards were preserved:
  - `FAST_PWM_FAN_FREQUENCY 31400`
  - `FAN_KICKSTART_POWER 255`
  - `EASYTHREED_FAN0_GUARD_HEATING_SPEED 255`
  - `EASYTHREED_FAN0_GUARD_HOLD_SPEED 252`
  - `EASYTHREED_FAN0_GUARD_COOLDOWN_SPEED 252`
- Build result:
  - `platformio run -e mks_robin_lite_maple` -> `SUCCESS`
- New binary:
  - `/home/maxim/draftCode/littleHands/firmware/custom-hotend-fan-guard-31k4-kick255-hold252-y-e-swapped-mksLite.bin`
- SHA256:
  - `f3245583d8e80fce029eca494d762bb9ee6b213f7f02b481dafc9383024688c0`

## 2026-04-29 SD Cleanup State

- After the axis test, `M27` confirmed `Not SD printing`.
- `M30 /CFFFP_~1.GCO` returned `ok`.
- A following `M20 L` returned `echo:No media`, indicating the printer no longer saw the SD at that moment.
- So the old print file was accepted for deletion, but the card state should be rechecked after the next power cycle / reinsert.

## 2026-04-29 Motion Defaults Lost And Restored

- After returning to the known-good `31k4 + kick255 + hold252` build, the printer responded over USB but showed no visible motion.
- `M503` revealed the root cause:
  - motion-related defaults were zeroed in RAM / settings
  - examples:
    - `M92 X0.00 Y0.00 Z0.00 E0.00`
    - `M203 X0.00 Y0.00 Z0.00 E0.00`
    - `M201 X0.00 Y0.00 Z0.00 E0.00`
- `M502` restored hardcoded defaults successfully.
- `M500` returned `echo:No EEPROM.`
- A follow-up `M503` then showed normal values again, including:
  - `M92 X606.00 Y606.00 Z606.00 E1040.00`
  - normal max feedrates / accelerations / PID values
- This explains why the machine could accept movement commands while appearing dead after some reflashes / restarts.

## 2026-04-29 Rollback Axis Test After Restoring Defaults

- With defaults restored via `M502`, the USB axis test was repeated.
- User observation:
  - `Z` visibly moved upward
  - `X` visibly moved right then left
  - on `Y` moves, only the extruder motor sound was heard and the bed did not move
- Conclusion:
  - the current rollback firmware is alive again
  - the `Y -> extruder` mis-mapping persists on this board / firmware combination
  - the motion-zero problem and the Y/E mapping problem are two separate issues

## 2026-04-29 Full Y/E Swap Branch Diagnostics

- The `full Y/E swap` build was reflashed and tested again, this time with a more disciplined sequence:
  - flash firmware
  - remove SD card
  - boot without card
  - USB connect
  - immediately issue `M502`
  - then motion tests
- Diagnostic serial capture saved to:
  - `/home/maxim/draftCode/littleHands/diagnostics_full_swap.log`
- Result from that diagnostic capture:
  - the printer returned effectively no usable serial responses on this branch during the scripted test
  - every command in the scripted session was logged as `<no response>`
- Separate user-observed motion result on the same branch:
  - nothing moved at all
- Practical conclusion:
  - the `full Y/E swap` branch is not merely “Y mapped wrong”
  - it destabilizes the machine more broadly and should not be used as the working base

## 2026-04-29 ECF Baseline Axis Mapping

- Flashed `ecf-k9-et4000plus-mksLite.bin` as a cleaner Marlin baseline for ET-4000+.
- USB on this baseline came up healthy immediately:
  - `M115` responded normally
  - `M503` showed sane defaults without needing `M502`
- User-observed one-axis test on ECF baseline established the actual mapping:
  - `X` command moved the printhead on real `X`
  - `Y` command moved the printhead on real `Z`
  - `Z` command moved the bed on real `Y`
- Conclusion:
  - this printer's real motor wiring / board-channel mapping is `X -> X`, `Y -> Z`, `Z -> Y`
  - ECF baseline is a much healthier base than the previous custom branch
  - the next firmware step is a pure `Y/Z swap` on top of ECF

## 2026-04-29 ECF Y/Z Swap Build

- Patched ECF source in:
  - `/home/maxim/draftCode/littleHands/firmware_src/ECF-Marlin-upstream/Marlin/src/pins/stm32f1/pins_MKS_ROBIN_LITE.h`
  - swapped logical `Y` and `Z` motor channels while leaving `X` and `E0` untouched
- Build initially failed because `BACKLASH_COMPENSATION` in this ECF branch did not compile cleanly.
- Disabled `BACKLASH_COMPENSATION` in:
  - `/home/maxim/draftCode/littleHands/firmware_src/ECF-Marlin-upstream/Marlin/Configuration_adv.h`
- Rebuilt successfully for `mks_robin_lite_maple`.
- Produced binary:
  - `/home/maxim/draftCode/littleHands/firmware/ecf-k9-et4000plus-y-z-swapped-mksLite.bin`
- `sha256`:
  - `5a258c03c0c3be4278b54a92edc1fd26c9f4c15f45116d2238e0a8c7cdd740a6`
- Copied to SD card as `mksLite.bin` and unmounted the card for flashing.

## 2026-04-29 ECF Y/Z Swap Runtime Result

- After flashing `ecf-k9-et4000plus-y-z-swapped-mksLite.bin`, the printer again came up with zeroed motion settings.
- `M502` was required immediately after boot to restore sane defaults.
- User-observed motion after `M502`:
  - `X` still moved the head right / left
  - `Y` moved the head vertically
  - `Z` also moved the head vertically
- Practical conclusion:
  - this `Y/Z swap` build is wrong for the real kinematics of this K9
  - the earlier plain `ECF baseline` was likely already correct for this machine's unconventional axis layout:
    - `X` = head left/right
    - `Y` = head up/down
    - `Z` = bed in/out
- next step should be rollback to plain `ECF baseline` and then port fan logic onto that healthy base instead of forcing a Y/Z swap

## 2026-04-29 Final ECF USB Workflow Firmware

- Built final firmware:
  - `/home/maxim/draftCode/littleHands/firmware/ecf-k9-et4000plus-single-fan-guard-binary-upload-eeprom-init-mksLite.bin`
- `sha256`:
  - `ed556106c06315ee835cb1447d3a77f52bec58511f711a06d4e92769d2d13fad`
- This build combines:
  - healthy plain ECF motion / axis baseline
  - single-fan guard for the only hotend fan
  - `FAST_PWM_FAN_FREQUENCY 31400`
  - `FAN_KICKSTART_TIME 250`
  - `FAN_KICKSTART_POWER 255`
  - `BINARY_FILE_TRANSFER`
  - `CUSTOM_FIRMWARE_UPLOAD`
  - `EEPROM_INIT_NOW`
- USB-only firmware update path was successfully exercised:
  - binary upload of `mksLite.bin` to printer SD over USB
  - `M997` reboot issued over USB
  - printer came back on the new build
- Post-flash verification over USB:
  - `M115` reported build timestamp `Apr 29 2026 23:27:45`
  - `Cap:BINARY_FILE_TRANSFER:1`
  - `Cap:CUSTOM_FIRMWARE_UPLOAD:1`
  - `Cap:SD_WRITE:1`
  - `M503` now shows non-zero defaults automatically after flash
    - `M92 X606.00 Y606.00 Z1167.00 E1140.00`
    - `M203 X40.00 Y40.00 Z10.00 E70.00`
    - `M201 X1000.00 Y1000.00 Z100.00 E1000.00`
- Practical conclusion:
  - the printer is now on a good working firmware base
  - future firmware updates no longer require moving the SD card to the computer
  - future print jobs can be uploaded to printer SD over USB with the local helper tool

## 2026-04-29 Little Hands Control Center

- Added Linux GUI utility:
  - `/home/maxim/draftCode/littleHands/tools/k9_control_center.py`
- Purpose:
  - upload `gcode` to printer SD over USB
  - upload firmware over USB to printer SD and send `M997`
  - browse / start / pause / resume / stop / delete SD files
  - home printer, disable motors, jog `X/Y/Z`
  - move to bed-leveling points on the printer's `X/Z` bed plane
  - show live USB metrics (`M115`, `M503`, `M114`, `M105`, `M27`)
  - show SD print progress parsed from `M27`
  - export debug logs to `/home/maxim/draftCode/littleHands/monitor_logs/gui_exports/`
- Added launchers:
  - `/home/maxim/draftCode/littleHands/Little Hands Control Center.desktop`
  - `/home/maxim/.local/share/applications/little-hands-control-center.desktop`
- Launcher pinned into GNOME favorites for quick access.
- Smoke test:
  - `python3 -m py_compile` passed for `k9_control_center.py` and `k9_marlin_sd.py`
  - headless `tkinter` smoke test succeeded (`gui smoke ok`)

## 2026-04-30 Baseline Printing Mode

- The printer was reset to the plain community firmware baseline:
  - `/home/maxim/draftCode/littleHands/firmware/ecf-k9-et4000plus-mksLite.bin`
  - `sha256: 76b20caf87ad2d1f79ec855d59bb3ec6680260e243aafeecae19ddd9969fb8eb`
- Final hardware layout that produced the first normal first layer:
  - the only fan was moved back to `FAN2`
  - this fan now runs continuously as an always-on hotend / head cooling fan
  - the motor connectors for `Y` and `Z` were physically swapped on the control board
- Resulting effective motion on this baseline:
  - `X` = printhead left / right
  - `Y` = bed in the print plane
  - `Z` = printhead up / down
- Safe operational conclusion:
  - no more fan-control experiments are required for baseline printing
  - no more firmware-side `Y/Z` remap is required for baseline printing
  - the printer should now use ordinary sliced G-code, not the `_k9xz` remapped variant
- First successful baseline print start:
  - SD file: `CFFFP_~1.GCO`
  - source model: `/home/maxim/draftCode/littleHands/CFFFP_zeroBottom.gcode`
  - `home` was visually confirmed sane
  - the first layer started successfully
- Baseline mode to preserve:
  - firmware: plain `ECF`
  - fan: always-on in `FAN2`
  - hardware: `Y/Z` motor connectors swapped physically
  - slicing: normal Cura output, no plane-remap post-processing
- Cura start workflow was changed to remove `G28` from print start:
  - file: `/home/maxim/.local/share/cura/5.11/definition_changes/lilHands_settings.inst.cfg`
  - new mode: `manual zero + G92`
  - fixed expected home pose:
    - `X` fully left
    - `Y` bed fully back / away from the operator
    - `Z` nozzle touching the bed
  - Cura now treats this physical pose as `X0 Y0 Z0`
  - this avoids the dangerous end-of-home grinding behavior on this K9

## 2026-04-30 GUI Baseline Workflow Update

- Updated `/home/maxim/draftCode/littleHands/tools/k9_control_center.py` to match the baseline print setup:
  - plain `ECF`
  - fan always-on in `FAN2`
  - physical `Y/Z` motor plug swap
- Added GUI actions:
  - `Manual` window with the current Little Hands operating procedure
  - `Экспорт профиля Cura` to copy the printer profiles and Cura settings into the project
  - `Подготовить` for ordinary Cura G-code (no `_k9xz` remap in baseline mode)
  - `Залить и старт` for upload + start from the fixed print home
  - `Запомнить Home` (`G92 X0 Y0 Z0`)
  - `К Home` (return to fixed print home before start)
  - `Пуск с home` for SD prints
- Updated jog and leveling labels to the real current machine motion:
  - `X` = printhead left/right
  - `Y` = bed in print plane
  - `Z` = printhead up/down
- Leveling point moves now:
  - lift `Z`
  - move in `X/Y`
  - lower back to `Z0`
- Export self-test:
  - `/home/maxim/draftCode/littleHands/exports/cura_bundle_selftest`
  - copied 31 Cura-related files successfully

## 2026-04-30 Adhesion Tuning For FAN2 Always-On

- During a normal baseline print, the far-left rear corner began lifting from the tape.
- Immediate operational decision:
  - do not use `G28` on stop / restart
  - stop workflow for this machine should be:
    - pause / cancel if possible
    - hotend off
    - lift `Z`
    - no homing
  - after any interrupted calibration in the center of the bed, return explicitly to the fixed print-home pose before restarting
- Cura profile `codex - monitored strength` was strengthened for adhesion:
  - `brim_width = 14`
  - `speed_layer_0 = 8`
  - `material_print_temperature = 220`
  - `material_print_temperature_layer_0 = 225`
  - `initial_layer_line_width_factor = 135`
- Files updated:
  - `/home/maxim/.local/share/cura/5.11/user/codex3_user.inst.cfg`
  - `/home/maxim/.local/share/cura/5.11/user/codex3_extruder_user.inst.cfg`
  - `/home/maxim/.local/share/cura/5.11/quality_changes/codex3_quality.inst.cfg`
  - `/home/maxim/.local/share/cura/5.11/quality_changes/codex3_extruder_quality.inst.cfg`

## 2026-04-30 Print Failure Notes And Anti-Warp Revision

- Current test part reached stable printing for a while, but showed the following defects:
  - far-left rear corner no longer lifted
  - near-left front corner lifted along the seam between brim and model corner
  - approximate lifted zone:
    - from `X0` to about `X40`
    - from `Z0` to about `Z15`
    - lift height from about `1.5 mm` down to `0 mm`
  - later, around `4 mm` print height, the near-left front corner cracked
  - crack direction:
    - from `X0` toward roughly the middle along the `Z` axis
    - from `X0` toward roughly the middle along the `X` axis
  - near-right front and far-right rear corners showed shallow non-through grooves on the corner surface
- Likely interpretation:
  - adhesion improved, but internal stress / corner cooling asymmetry still remain
  - `grid` infill may contribute to stress and nozzle contact, so the infill pattern was softened
- Profile was revised again for the next attempt:
  - `brim_width = 18`
  - `infill_pattern = lines`
  - `speed_layer_0 = 6`
  - `speed_print = 18`
  - `speed_wall = 16`
  - `speed_topbottom = 16`
  - `speed_infill = 20`
  - `material_print_temperature = 222`
  - `material_print_temperature_layer_0 = 228`
  - `initial_layer_line_width_factor = 145`
- 2026-04-30: Updated Cura baseline profile `codex - monitored strength` to test concentric first bottom layer while keeping later bottom/top skin on lines. Added `top_bottom_pattern = lines` and `top_bottom_pattern_0 = concentric` in the active user and quality profile files to improve brim-to-part transition and reduce front-left corner lift.
- 2026-04-30: Tuned `codex - monitored strength` further against corner cracking / internal stress: reduced infill from 35% to 20%, set `infill_before_walls = False`, lowered print/wall/topbottom/infill speeds to 16/14/14/18 mm/s, reduced top/bottom layers from 6 to 5, and raised nozzle temperatures to 224C print / 230C first layer.
- 2026-04-30: Restored FAN1 control on the EasyThreeD single-fan branch and built a new hotend-safe fan profile with USB firmware-update support: `custom-hotend-fan-guard-hotonly-pulsedcooldown-mksLite.bin` (`sha256: 64577dc459222ce92b4f272eae56df81885b3a62379c9015cb776011b28ade01`). New logic: fan off when cold, full 255 while heating / holding a hot target, full 255 while passively cooling above 60C, then pulsed 255/off cooldown between 60C and 45C, then fully off below 45C.
- 2026-04-30: Finalized the new working hotend-fan baseline on `FAN1` with `custom-hotend-autofan-45c-usb-mksLite.bin` (`sha256: 6ea0bd0340329cf96cf4b9b3d2164c03299f4e84edd02989238414cde5f1127c`). Verified behavior on hardware: fan stays off below 45C, turns on above 45C during heating, and turns off again after cooldown below 45C. This resolves the overnight noise problem while keeping hotend cooling automatic.
- 2026-04-30: Little Hands runtime print logging was standardized.
  - Ring log path: `/home/maxim/draftCode/littleHands/monitor_logs/little_hands_runtime.log`
  - Ring log size cap: `10 MiB`
  - Saved log snapshots path: `/home/maxim/draftCode/littleHands/monitor_logs/gui_exports/`
  - The GUI now records print session start/end and periodic telemetry into the ring log.

## Backlog For Next Session

- `home / start workflow`
  - make `Запомнить старт -> К старту -> Печать с SD` completely deterministic
  - verify that `Печать с SD` never re-enters pseudo-home or drives into hard stops
  - if needed, separate diagnostic homing from production print-start logic in the GUI
- `USB robustness`
  - review serial recovery after interrupted jobs or printer-side busy states
  - make sure `Сброс USB` and background polling recover cleanly without requiring GUI restarts
  - reduce chances of the app appearing frozen when the printer stops answering temporarily
- `print profile / adhesion / cracking`
  - review the result of the current print tomorrow before changing Cura again
  - only then decide whether to keep `brim 18 + tabs + concentric first layer`
  - if cracks remain, prefer targeted anti-warp and stress reduction changes over broad random tuning

## 2026-05-01 Current Baseline Snapshot

- Printer-side baseline now treated as:
  - firmware: `custom-hotend-autofan-45c-usb-mksLite.bin`
  - fan wiring: single fan on `FAN1`
  - fan behavior: auto hotend fan, `off` below `45C`, `on` above `45C`
  - motor wiring: physical `Y/Z` swap on the board remains required
- `Little Hands` current operator baseline:
  - persistent window geometry and pane proportions
  - runtime ring log and temperature history restore
  - SD panel shows selected file, active print file, and survives `M27` / list-unavailable situations better
  - top status is now a single scrolling line instead of four unstable clipped fields
  - progress bar is wider and carries its status text inside the bar
- Known next technical focus:
  - deterministic print start / home workflow
  - USB recovery polish
  - next Cura tuning only after reviewing the active print result

## 2026-05-01 Z Height Root Cause

- A later print result showed a very specific failure pattern:
  - X/Y footprint matched the sliced model
  - Z height was approximately 2x too large
  - the part was weak / porous because adjacent layers were spaced too far apart
- This matches a bad vertical steps-per-mm setting, not a slicer scaling issue.
- The stable plain-ECF motion baseline for the K9 with physical `Y/Z` motor swap relied on:
  - `M92 X606.00 Y606.00 Z1167.00 E1140.00`
- The later `custom-hotend-autofan-45c-usb-mksLite.bin` branch came from the EasyThreeD single-fan tree where the default motion constants were:
  - `M92 X606.00 Y606.00 Z606.00 E1040.00`
- For this machine that reintroduced an under-scaled vertical axis, so every commanded layer lift became almost 2x too large in the real world.
- Permanent source fix prepared on 2026-05-01:
  - changed `DEFAULT_AXIS_STEPS_PER_UNIT` from `{ 606, 606, 606, 1040 }` to `{ 606, 606, 1167, 1040 }`
  - files:
    - `/home/maxim/draftCode/littleHands/firmware_src/EasyThreeD-K9_ET4000PLUS/Marlin/Configuration.h`
    - `/home/maxim/draftCode/littleHands/firmware_src/EasyThreeD-K9_ET4000PLUS/config/EasyThreeD/ET4000PLUS/Configuration.h`
  - rebuilt binary:
    - `/home/maxim/draftCode/littleHands/firmware/custom-hotend-autofan-45c-usb-z1167-mksLite.bin`
    - `sha256: 8861ba0dc2f162d821f7474b60acd717a7c705db6dae8fcab5afcb8841f8aa77`
- Important operational note:
  - flashing the corrected binary alone may not be enough if `EEPROM.DAT` still contains the old saved `Z606`
  - after applying the fix, motion settings must be explicitly overwritten with either:
    - `M92 Z1167` then `M500`
  - or a full defaults reload:
    - `M502` then `M500`
- 2026-05-01: Added explicit Little Hands firmware identity to the printer firmware path. The EasyThreeD single-fan branch now defines `LH_FIRMWARE_LABEL`, and `M115` reports that label directly instead of forcing the UI to infer the build only from `Marlin` base version + `M503`. Current canonical labels:
  - `LH v1 AutoFan45 FAN1 Z606`
  - `LH v2 AutoFan45 FAN1 Z1167`
- 2026-05-01: Extended the same `LH_FIRMWARE_LABEL` mechanism into the ECF source tree as a compatibility hook, so future builds from either firmware tree can expose an explicit Little Hands firmware version through `M115`.
- 2026-05-01: Built and archived the new explicit-version binary as:
  - `/home/maxim/draftCode/littleHands/firmware/LH-v2-AutoFan45-FAN1-z1167-mksLite.bin`
  - sha256: `7504c6d2c808b435b1a62c635c588a01e9e0450d1bc7c2472de10bc0288fe21d`

## 2026-05-03 Second K9 Firmware Root Cause

- Investigated the second fully working `K9` after flashing `LH v2 AutoFan45 FAN1 Z1167`.
- Confirmed by tiny jog tests that its motion mapping did not match the first experimental K9:
  - `X` behaved normally
  - `Y` and `Z` behavior was inconsistent with the first printer baseline
- Root cause found in the source trees:
  - `firmware_src/EasyThreeD-K9_ET4000PLUS/Marlin/src/pins/stm32f1/pins_MKS_ROBIN_LITE.h`
    remaps `Y_STEP/Y_DIR` onto the pins Marlin normally uses for `E0_STEP/E0_DIR`
  - `firmware_src/ECF-Marlin-upstream/Marlin/src/pins/stm32f1/pins_MKS_ROBIN_LITE.h`
    keeps the standard K9 / ET4000+ mapping:
    - `Y_STEP_PIN PB11`
    - `Y_DIR_PIN PB2`
    - `E0_STEP_PIN PC4`
    - `E0_DIR_PIN PA5`
- The EasyThreeD hard fork even documents this as a unit-specific observation:
  - `EasyThreeD K9 ET4000+ in this unit appears to route Y motion on the step/dir lines Marlin would normally use for E0.`
- External references also align with the community baseline rather than our unit-specific swap:
  - `schmttc/EasyThreeD-K7-STM32` explicitly treats `ET4000PLUS-K9` as its own supported branch
  - `schmttc/ECF-Marlin` Beginner's Guide lists `K9 + ET4000+` as a supported combination
  - a public `lite_cfg.txt` dump for factory K9 firmware reports stock motion values closer to:
    - `X606`
    - `Y606`
    - `Z600`
    - `E1040`
- Conclusion:
  - the bad behavior on the second K9 is best explained by our firmware assumptions, not by spontaneous simultaneous motor/driver failure
  - specifically:
    - a unit-specific `Y/E0` step-dir swap was baked into `LH v2`
    - and `Z1167` may be correct only for the first experimental printer, not for a stock-like second K9
- Built a new cautious rollback firmware for the second K9:
  - source tree: `firmware_src/ECF-Marlin-upstream`
  - key properties:
    - standard stock-like K9/ET4000+ step/dir mapping
    - `FAN1` / `PA8` auto-fan at `45C`
    - explicit `M115` label
    - stock-like motion constants `{ 606, 606, 600, 1040 }`
  - binary:
    - `/home/maxim/draftCode/littleHands/firmware/LH-v3-StockPins-AutoFan45-FAN1-z600-e1040-mksLite.bin`
  - sha256:
    - `817288cba35bb78bcca0ca57c4c085eb57d6cabd3af069dd0a670f9aaf85179f`
- Safety rule for the second K9:
  - do not continue experiments on `LH v2` there
  - use `LH v3 StockPins AutoFan45 FAN1 Z600 E1040` as the next validation build
  - re-run only tiny jog tests first, then calibrate zero, and only after that attempt the first print
- 2026-05-03: `LH v3 StockPins ...` validated one more point: the second K9 did not show random or dead motion. Instead, tiny jog tests were stable and revealed a clean axis swap:
  - `X` correct
  - logical `Y` moved the physical vertical axis
  - logical `Z` moved the physical bed axis
- That means the second K9 still wants the physical `Y/Z` swap we learned on the first printer, but it does **not** want the later unit-specific `Y/E0` swap from `LH v2`.
- Built the corrected follow-up firmware:
  - `/home/maxim/draftCode/littleHands/firmware/LH-v4-YZSwap-AutoFan45-FAN1-z600-e1040-mksLite.bin`
  - sha256:
    - `64d679c51f3b1571027dac24ae572d3eeb9d9bfb48a0f1ed1d91ec3022bff86c`
- `LH v4` keeps:
  - standard K9 / ET4000+ `Y/E0` mapping
  - `FAN1` auto-fan at `45C`
  - stock-like motion values `X606 Y606 Z600 E1040`
- `LH v4` changes only one axis-level assumption versus `LH v3`:
  - logical `Y` uses the former `Z` pins
  - logical `Z` uses the former `Y` pins
- Operational conclusion:
  - the earlier theory that the first K9 necessarily had a burned `Y` driver is now weaker
  - the safer explanation is that `LH v2` combined two different assumptions:
    - real `Y/Z` motor routing quirk
    - mistaken extra `Y/E0` step-dir swap
- 2026-05-03: `LH v4` validated successfully on the protected second K9.
  - operator-facing tiny jog mapping is now correct:
    - `X` = head left/right
    - `Y` = head up/down
    - `Z` = bed away/toward operator
  - `Little Hands` was updated so logs, live status, and `M114` presentation follow the operator convention above, while still preserving raw `M114` in USB metrics for debugging.
  - second K9 is now considered ready for first cautious print tests with:
    - firmware `LH v4 YZSwap AutoFan45 FAN1 Z600 E1040`
    - Cura machine `lilHands K9 warm mat`
    - Cura profile `codex - K9 warm mat cautious`
- 2026-05-03: final UI cleanup for the current operator workflow:
  - removed the experimental stepper-melody feature from `Little Hands`
  - left only the computer completion sound as an optional end-of-print notification
  - restored `Печать: ...` inside the progress bar
  - moved `Старт` and `ETA` into the `Файлы на SD принтера` block so active print metadata stays next to file selection / SD controls
  - removed redundant duplicate start / ETA lines from `Параметры в реальном времени`
- 2026-05-03: added two practical safety rules to `Little Hands` for the second K9 workflow:
  - local G-code upload is now blocked if the file looks wrong for the current manual-zero K9 baseline
    - explicit `G28` in the startup section is treated as unsafe
    - `TARGET_MACHINE.NAME:Unknown` is treated as suspicious and the user is told to re-slice on `lilHands K9 warm mat`
  - after a naturally observed print completion, `Little Hands` now reminds the operator to:
    - remove the printed part
    - press `К старту`
    - then press `Запомнить старт` if the pose still matches the expected start pose

## Windows Distribution Plan

- Goal:
  - prepare a future Windows build of `Little Hands` without starting packaging work yet

- Expected packaging route:
  - `PyInstaller` single-folder or one-file executable build

- Likely already portable:
  - `tkinter` GUI structure
  - `pyserial`-based printer communication
  - log saving, file dialogs, operator workflow

- Platform-specific work to review before any build:
  - serial port naming:
    - Linux `/dev/ttyUSB*`
    - Windows `COM*`
  - sound notification implementation
  - file/path handling and default save locations
  - any Linux-only helper tooling or shell assumptions
  - screenshot / window-inspection helpers must remain optional and non-critical

- Future validation checklist for Windows:
  - app starts on a clean Windows machine
  - detects `CH340` / printer-like serial ports correctly
  - does not confuse unrelated `FTDI` devices for the printer
  - can save logs, open firmware/G-code files, and keep UI state
  - can monitor temperatures and SD-print state over serial

- Important rule:
  - do not start Windows packaging until the current Linux K9 workflow is considered stable enough that porting effort will not duplicate churn

## 2026-05-04 Public Repository Documentation Pack

- Added a public-facing documentation layer for publishing the project:
  - `README.md`
  - `README.ru.md`
  - `docs/INSTALL_LINUX.md`
  - `docs/INSTALL_LINUX.ru.md`
  - `docs/PRINTER_AND_FIRMWARE.md`
  - `docs/PRINTER_AND_FIRMWARE.ru.md`
  - `docs/screenshots/little-hands-main-window.png`
- Added `requirements.txt` with the minimal Python dependency currently needed beyond stdlib / system packages:
  - `pyserial`
- Updated `Little Hands` defaults to match the protected second-K9 public baseline:
  - default firmware file:
    - `LH-v4-YZSwap-AutoFan45-FAN1-z600-e1040-mksLite.bin`
  - firmware catalog entries for `LH v3` and `LH v4`
  - built-in manual text now reflects:
    - external warm bed / hotbed
    - operator-facing `Y/Z` convention
    - current `LH v4` baseline
- Publishing note:
  - local docs and repo content are now prepared for a public GitHub repository
  - local `origin` now points to:
    - `https://github.com/maxim221/EasyThreedK9_littleHands.git`
  - current `gh auth status` for account `maxim221` reports an invalid token, so actual remote push may still need re-authentication before publication

## 2026-05-04 UI Language Toggle And Chinese Docs

- Added a visible language selector in `Little Hands`:
  - `RU`
  - `EN`
  - `中文`
- The selector now updates the main visible interface elements:
  - top action buttons
  - major section titles
  - manual window text
  - files/firmware window labels
  - key SD labels such as selected file / active print / start time
- Added Chinese public docs:
  - `README.zh.md`
  - `docs/INSTALL_LINUX.zh.md`
  - `docs/PRINTER_AND_FIRMWARE.zh.md`
- `README.md` and `README.ru.md` now link to all three language variants.
- Verified that `Little Hands` still launches after the localization changes.

## 2026-05-06 Completion Recovery And mainFlasherTop Notes

- Hardened SD print start and recovery commands:
  - `Little Hands` now sends `M17` before direct SD print start, before `Save start`, before `Go to start`, and before `Start from saved start`
  - `Go to start` and `Start from saved start` now include `M400` so queued recovery moves finish before the next step
- Updated the active local Cura `5.11` machine end-gcode:
  - finished prints should present the part with raw Marlin `G1 Y95`
  - active end-gcode no longer adds `M84`
  - existing old G-code files must be re-sliced to inherit this
- `mainFlasherTop.STL` geometry check:
  - model bounds are about `70.0 x 52.64 x 15.0 mm`
  - current STL orientation touches the bed with a narrow strip of about `260 mm2`
  - the broad opposite face is about `2850 mm2`, so this model should be laid flat on that broad face in Cura before slicing
- Active local Cura `codex - K9 warm mat cautious` settings were tuned for this flat-cover print:
  - `top_layers = 6`
  - `bottom_layers = 6`
  - `infill_sparse_density = 20`
  - `brim_width = 8`
  - `speed_layer_0 = 7`
  - `initial_layer_line_width_factor = 135`
  - support remains off

## 2026-05-07 Post-Print Recovery Guard

- Fixed the post-print recovery instruction order:
  - remove the part first
  - press `Go to start` while the saved zero is still valid
  - then power-cycle the printer
  - after power-on, press `Save start`
- Replaced the blocking completion messagebox with a non-modal instruction window so the main UI can continue repainting and resizing.
- Added a post-print recovery guard:
  - after natural completion or a failed repeated start, `Little Hands` blocks the next SD print start
  - the block is cleared when the operator confirms the recovery window or saves the start pose again
- Added duplicate-command protection so repeated clicks cannot queue multiple USB movement tasks while one command is still running.
- Fixed UI state persistence:
  - geometry, selected tab, main sash, and left split position are now actually written to `monitor_logs/little_hands_ui_state.json`
- Improved port detection diagnostics:
  - if a CH340-like port is visible but Marlin does not answer `M115/M105`, the app selects the candidate but reports that the printer likely needs a power cycle instead of pretending no USB device exists

## 2026-05-07 SD Start USB Read Retry

- Observed a repeated-start failure where the app selected the SD file and entered `Start print from home`, but pyserial raised:
  - `device reports readiness to read but returned no data`
- Added a transient USB-start retry path:
  - classify common CH340/pyserial readiness / I/O errors as transient start errors
  - after such an error, query `M27` to see whether SD printing actually started
  - if `M27` confirms active SD printing, treat the start as successful and keep monitoring
  - otherwise retry the SD start once
  - if retry still cannot confirm active SD printing, show an explicit power-cycle / Find / Save start recovery message
- Error events are now written to the journal before showing a modal error dialog, so diagnostics are not hidden while a dialog is open.

## 2026-05-07 Printer Port Safety Guard

- Observed a dangerous diagnostic clue in the runtime log:
  - `Login incorrect`
  - this means a printer command reached a non-printer serial console instead of Marlin
- Hardened serial-port handling:
  - the GUI no longer defaults blindly to `/dev/ttyUSB0`
  - the last selected port is only used after the current Linux port list confirms that it still looks like the K9 printer
  - common non-printer ports such as `FTDI` adapters and `/dev/ttyS*` are hidden from the normal printer-port dropdown
  - manual printer commands are blocked if the selected port disappeared or no longer looks like a CH340/ACM printer port
  - background telemetry disconnects the stale port in the UI after USB disappearance instead of continuing to poll the old `/dev/ttyUSB*` name
- Updated Linux installation docs to explain that `Find` should be used for printer discovery and that unrelated serial devices are intentionally filtered out.

## 2026-05-07 Auto SD Refresh After Port Reconnect

- Added automatic SD file-list refresh after a printer port is selected or rediscovered.
- The refresh is delayed and retried while USB discovery is still busy, so it should not collide with the `Find` command.
- This keeps the printable-file list populated after CH340 reconnect / power cycle and reduces the chance of starting from an empty or stale SD UI state.

## 2026-05-07 Confirm SD Print Start With M27

- Observed a false-positive start after power cycle:
  - Marlin replied `File selected`
  - the GUI logged `Start print: done`
  - telemetry then stopped and no `SD printing byte ...` confirmation appeared
- Hardened SD print start:
  - `M23` file selection is no longer treated as proof that printing started
  - after `M24`, Little Hands now polls `M27` on the same open serial session
  - if active SD printing is not confirmed, it sends `M24` once more and checks again
  - only `M27` active-print confirmation is treated as a successful start
  - if the start is still not confirmed after retry, the app raises an explicit recovery error instead of showing a misleading success

## 2026-05-07 More Robust SD File Listing

- Observed a post-restart failure where the printer answered temperature polling but returned no usable SD file list for `M20`.
- Hardened SD listing:
  - use one open serial session per listing attempt instead of reopening for each `M20` variant
  - run `M21`, wait briefly, then check `M27` before asking for files
  - try `M20`, `M20 L`, and `M20 F`
  - read each listing response for longer
  - log a short raw response excerpt, or explicitly log that all `M20` variants were empty

## 2026-05-07 Human-Friendly SD File Names

- Restored `M20 L` as the preferred SD listing command so long filenames are used when Marlin provides them.
- The UI now separates display name from command path:
  - display can show the long filename, plus the short SD alias in parentheses
  - print/delete/start commands still use the short first token returned by Marlin
- Selected-file and active-print labels now show the human-facing display string instead of only the short 8.3 filename.
- Closing the GUI now explicitly stops telemetry and clears the selected port before destroying the window, so the serial port is released promptly on exit.

## 2026-05-07 Wait For Motion Idle Before SD File Select

- Observed a failed start where the head moved up/down, then Marlin answered only:
  - `echo:busy: processing`
  - no `File selected`
- Root cause:
  - `M23` was sent while the printer still considered the previous movement / `M400` busy
  - Little Hands correctly refused to treat that as a selected file, but the recovery was not automatic
- Hardened SD start:
  - this strict approach was later found too aggressive for the K9 startup/heating behavior
  - see `Restore Working SD Start Semantics` below for the corrected follow-up

## 2026-05-07 Skip Redundant Go-To-Start After Save Start

- Observed that immediately after `Save start`, the operator is already physically at the saved start pose.
- The extra `Go to start` movement inside `Start print` could produce a long Marlin busy state and block SD file selection.
- Added session state:
  - `Save start` marks the printer as already at saved start
  - `Go to start` marks the printer as back at saved start
  - jog / leveling / home / stop / print start clear that flag
- When the flag is true, `Start print` skips the redundant pre-print move and starts the selected SD file directly.

## 2026-05-07 Restore Working SD Start Semantics

- Compared the current start path with the known working `5f4ffaf` behavior from the successful print.
- Regression found:
  - the stricter immediate `M27` confirmation was wrong for this printer
  - during SD start / heating, Marlin may answer `busy` for a while even though the old `M23` + `M24` workflow can proceed
- Restored the working SD-start semantics:
  - `M23` / `M24` plus `File opened`, `echo:Now fresh file`, or `ok` is treated as a sent start
  - immediate `M27 SD printing byte ...` is no longer required for success
  - transient USB read errors still use the existing `M27` retry confirmation path
- Kept the later useful improvements:
  - safer port filtering
  - SD auto-refresh after reconnect
  - human-friendly SD file names
  - skip redundant pre-start move immediately after `Save start`

## 2026-05-07 Reduce SD / USB Pressure Around Start

- Observed another failed start pattern after automatic SD refresh:
  - `M23/M24` returned `File opened` / `File selected`
  - printer then stayed in `busy` / silent state and no fresh telemetry appeared
- Reduced how much Little Hands touches SD and USB around print start:
  - normal SD list refresh is back to the shorter `M20 L` / `M20` path
  - `M20 F` is no longer used during normal printable-file refresh
  - automatic SD refresh after reconnect waits longer before reading the card
  - automatic SD refresh is skipped while the app still has an unresolved print-start state restored from the log
  - log-based print-state restore now treats a newer `PRINT_START` for the same file as active even if an older run of that file has a `PRINT_END`
  - telemetry polling no longer sends `M110` sync before every `M105/M27/M114/M115`
  - print-start grace is now five minutes instead of a premature 20-second failed-start watchdog
- Practical rule for the operator:
  - after pressing `Start print`, do not refresh the SD list until the printer has either started heating / moving or clearly failed

## 2026-05-07 Safer Post-Print Start Recovery

- Observed that after a completed print the app could refuse `Go to start` with "save start first".
- Root cause:
  - the saved-start flag is intentionally in application memory
  - the `Status` action was too destructive and cleared that flag even though it only reads `M115/M27`
  - the post-print dialog also had a misleading confirmation button that did not actually send `G92`
- Fixed:
  - `Status` no longer clears a trusted saved start
  - the post-print dialog now tells the operator to return to the start pose manually if `Go to start` is already unavailable
  - the dialog action is now `Save start` and runs the same save-start command as the main control
  - missing-start errors now explain why Little Hands refuses to move automatically without a trusted zero

## 2026-05-07 Use Known Post-Print Pose For Return-To-Start

- Refined the post-print recovery flow:
  - the app must not return to start automatically while the printed part is still on the bed
  - after natural print completion Little Hands already moves to a known presentation pose: head lifted and bed presented
  - while the printer has not been power-cycled, Marlin still has the logical zero from the print start `G92`
- Added a known-post-print-pose state:
  - if Little Hands observed natural completion and its completion move succeeded, `Go to start` may use that known state even if the app's saved-start flag was lost
  - the post-print dialog now has an explicit `Go to start` button with a confirmation that the model has been removed
  - manual jogs, new print starts, stop/failed-start clearing, port changes, and port disconnects clear the known-post-print-pose state
- Intended operator flow:
  - remove the printed part
  - press `Go to start`
  - only then power-cycle the printer
  - after power-on, press `Save start` before the next SD print

## 2026-05-07 mainFlasherTop Surface Quality Tuning

- Investigated `mainFlasherTop.STL` after a print with a rough/stringy unsupported face.
- Geometry finding:
  - current STL dimensions are about `70.0 x 52.64 x 15.0 mm`
  - original orientation has only about `260 mm2` of bottom contact
  - the broad face contact after flipping is about `2850 mm2`
  - later correction from the operator: the printed model had already been manually placed broad-side-down in Cura
  - the real failed surface is therefore a remaining unsupported overhang / underside, not the bed-contact orientation
- Created local working STL:
  - `mainFlasherTop_broadFaceDown.STL`
  - this is still useful as a no-manual-rotation helper, but it is not by itself the fix for the rough unsupported face
- Updated local Cura 5.11 active profile `codex - K9 warm mat cautious` for the next PLA test:
  - `layer_height = 0.16`
  - `layer_height_0 = 0.2`
  - `material_print_temperature = 214`
  - `material_print_temperature_layer_0 = 218`
  - `cool_fan_speed = 100`
  - `cool_min_layer_time = 10`
  - `speed_print = 16`
  - `speed_wall = 12`
  - `speed_topbottom = 12`
  - `speed_infill = 18`
  - `speed_travel = 40`
  - `brim_width = 6`
  - `support_enable = True`
  - `support_type = everywhere`
  - `support_angle = 35`
  - `support_structure = normal`
  - corrected after Cura preview still showed no supports by forcing the same support placement in both Cura user and quality containers
  - `support_infill_rate = 12`
  - `support_interface_enable = True`
  - `support_roof_enable = True`
  - `support_interface_density = 85`
  - `support_roof_density = 85`
  - `support_z_distance = 0.16`
  - bridge tuning enabled: fan `100`, bridge skin/wall speed `10`, bridge flow `90`
- Next test instruction:
  - slice broad-side-down; using `mainFlasherTop_broadFaceDown.STL` avoids having to rotate manually
  - inspect Cura preview: the bad underside should show generated support/interface below it
  - if supports are still missing under that face, change support placement from `Touching Buildplate` to `Everywhere` for this model

## 2026-05-07 Reproducible Cura 5.11 Slicing Helper

- Added `tools/k9_cura_slice.py` to make the working K9 warm-mat slicing flow reproducible from the project.
- The helper:
  - runs the UltiMaker Cura 5.11 AppImage CuraEngine directly
  - applies the validated Little Hands manual-zero start/end G-code
  - uses the cautious PLA profile with supports everywhere, support interface/roof enabled, and `6 mm` brim
  - centers binary STL models by their STL bounds before slicing
  - validates resulting extrusion bounds against the `100 x 100 mm` K9 bed before optional SD copy
  - refuses real `G28` commands in output G-code
- `10 mm` brim is no longer the default because one generated SD file selected successfully but did not enter a reliable print start on the validated K9.

## 2026-05-08 SD Start Reliability And G-Code Guardrails

- Investigated a repeated failed SD start after power cycle and a valid manual-zero save:
  - Little Hands selected `CFFFP_~2.GCO` and sent `M24`
  - firmware replied `File opened`, `File selected`, and `echo:busy: processing`
  - hotend target stayed at `0`
  - USB stopped answering `M105`
- Compared with the last known successful run:
  - the successful path had a full `180 s` USB silence after `M24`
  - the newer M105-only compromise was still too chatty for this K9 start window
- Restored full post-`M24` USB silence:
  - Little Hands now avoids all USB polling for `180 s` after SD start
  - after the silence window it resumes telemetry and SD progress checks
- Added safer handling for silent USB:
  - automatic SD refresh waits for a fresh `M105` before touching `M20`
  - if the printer does not answer `M105`, the app skips SD/position queries and logs a power-cycle recovery hint
  - `Find` no longer shows a blocking success dialog for an already confident printer match
- Added G-code upload/start validation guardrails:
  - reject real `G28`
  - reject G-code with impossible Cura bounds
  - reject `Filament used: 0m`
  - reject files with no hotend target command near the start
  - allow older verified Little Hands start-G-code even when Cura reports `TARGET_MACHINE.NAME:Unknown`
- Local finding:
  - `exports/CFFFP_mainFlasherTop_brim10.gcode` was a bad export with impossible bounds and `Filament used: 0m`
  - moved it out of normal `.gcode` selection as `exports/rejected/CFFFP_mainFlasherTop_brim10.bad.txt`
  - the next safe recovery candidate is the known-good backup:
    `card_backups/sd_before_brim10_20260507_223700/CFFFP_mainFlasherTop.gcode`

## 2026-05-08 Remove SD Start Quiet Pause

- Removed the explicit `180 s` post-`M24` USB quiet window from Little Hands.
- Reason:
  - the timer was opaque in the UI
  - earlier successful starts did not require the operator to understand or wait through a hidden countdown
  - the more likely root cause of the latest repeated failed start is bad or incompatible G-code, not normal telemetry polling
- Current behavior:
  - after SD start, Little Hands immediately resumes normal polling
  - if the printer stops answering `M105`, the app still avoids piling on SD/position queries and logs a power-cycle recovery hint
  - G-code validation remains in place to block obviously broken Cura exports before upload/start

## 2026-05-08 Restore Visible SD Start USB Quiet Window

- Field result after removing the quiet window:
  - the known-good `CFFFP_~2.GCO` file of size `1703396` opened and selected correctly
  - Little Hands immediately resumed USB polling
  - the printer then stopped answering `M105`
  - the operator observed only the fan noise and no real print start
- Conclusion:
  - the file itself was not the only factor
  - immediate post-`M24` polling can still wedge this K9 while it is entering SD print
- Fixed:
  - restored a full `180 s` post-`M24` USB quiet window
  - made the wait explicit in the UI and log instead of hiding it
  - during this window Little Hands does not send `M105`, `M27`, `M114`, or SD-list commands
  - after the window, it resumes cautious telemetry / SD progress polling
- Also refined user-facing warnings:
  - USB silence during an actual heating / moving / printing start is not by itself a reason to power-cycle
  - the failed-start recovery window now says to use power-cycle only when the printer is physically not heating, not moving, and not printing
- Cura baseline:
  - active local Cura profile and the reproducible slicing helper now use `brim_width = 6`
  - `Export Cura profile` includes the current `lilHands K9 warm mat` and `codex - K9 warm mat cautious` containers, including extruder temperature / bridge settings

## 2026-05-08 Manual Cura Settings For Other Slicers

- Added human-readable Cura / slicer settings sheets:
  - `docs/cura/SETTINGS.md`
  - `docs/cura/SETTINGS.ru.md`
  - `docs/cura/SETTINGS.zh.md`
- Purpose:
  - allow users on another Cura version or a different slicer to recreate the validated K9 warm-mat profile without manually editing generated G-code
  - document machine size, start/end G-code, temperatures, speeds, supports, brim, retraction, bridge settings, and pre-SD validation rules
- Key rule preserved:
  - use slicer settings and preview to produce correct G-code
  - do not hand-edit G-code except as a deliberate, clearly marked modified file

## 2026-05-08 Saved Print-End Recovery Model

- Added an explicit print-end model for SD-print recovery:
  - on print start Little Hands records `LH_END_GCODE_V1`
  - expected end position is calculated from the validated Cura G-code as `X95 Y95 Z(min(100, MAXZ + 10))`
  - the model is stored in `monitor_logs/little_hands_print_state.json`
  - SD mirroring as `LHSTATE.TXT` was later disabled in the print-start path; local state / ring log are the trusted source
- The state survives closing and reopening Little Hands:
  - reopening the app should not invalidate the print-end model
  - the ring log marker `PRINT_END_EXPECTED ... end_z=...` is also used as a fallback source
- Power-cycle semantics are intentionally conservative:
  - a power cycle still invalidates firmware RAM coordinates
  - if the printer physically stayed in the expected final pose, Little Hands can offer an explicit recovery return using the saved print-end model
  - the operator must confirm that the print finished, the part was removed, and the axes were not moved by hand
  - if the saved model is incomplete or unsafe, the app offers to delete the marker and asks the operator to set the start pose manually
- Recovery implementation:
  - declares the current physical position as the saved print-end coordinates with `G92`
  - returns to `X0 Y0 Z0`
  - declares the returned position as `G92 X0 Y0 Z0`
  - clears the active print marker and asks for the normal post-print/start confirmation workflow
- Active-print USB silence messages were softened:
  - once SD progress has confirmed a real print, intermittent missing `M105` is shown in status/progress fields instead of the journal
  - Little Hands still avoids extra `M27/M114` queries while `M105` is temporarily silent

## 2026-05-09 Suppress Confirmed-Print USB Chatter

- Field correction:
  - telemetry cadence was not the problem
  - the noisy line was the visible journal message:
    `Печать уже была подтверждена SD-прогрессом; сейчас M105 временно молчит...`
- Final behavior:
  - raw `M105` and `TELEMETRY` logging cadences stay at the previous detailed rates
  - if an active SD print was already confirmed and a single `M105` poll is silent, the UI updates status/progress only
  - the journal no longer records that expected active-print partial-USB condition
- Warnings remain visible for:
  - unconfirmed starts
  - idle USB silence
  - real command errors
  - failed-start recovery

## 2026-05-09 ModuleBot Cura Quality Pass

- Updated the validated K9 warm-mat Cura profile for `moduleBot.STL` and similar PLA parts:
  - enabled conservative ironing on the highest top layer only
  - kept hotend temperature, brim width, support policy, and manual-zero workflow unchanged
  - reduced print / infill / top-bottom / travel speeds slightly
  - added explicit acceleration limits for walls, infill, top/bottom, supports, skirt/brim, travel, and ironing
  - left Cura jerk control disabled because this RepRap-flavor profile emits `M566`, while the validated Marlin firmware exposes jerk through `M205`
  - softened final presentation moves after Cura resets motion limits at end of print
- Rationale:
  - side-wall edge stripes are more likely ringing / mechanical resonance than poor layer bonding
  - ironing is useful for visible top surfaces, but it is intentionally low-flow and top-only to avoid over-smearing small K9 parts
- Slicing verification:
  - `moduleBot.STL` sliced successfully with the updated helper
  - generated bounds are X `10.729..89.282`, Y `13.150..86.850`, Z `25.00`, inside the validated `100 x 100 x 100 mm` K9 volume
  - generated start still uses `G92 X0 Y0 Z0` and no startup `G28`
  - helper-generated G-code now patches CuraEngine's misleading `Filament used: 0m` header from the actual positive `E` moves

## 2026-05-09 Revert Host Preheat And Avoid Pre-Start SD Writes

- Field correction:
  - host-side preheat before `M24` was the wrong algorithm for the validated K9 SD workflow
  - superseded later the same day by the proven no-`M109` preheat workflow below, after runtime logs showed the successful print used that exact workaround
  - the SD file must own its own `M104` / `M109` sequence after `M24`
  - Little Hands should not keep a long preheat polling session open before handing control to the SD file
- Restored SD-start semantics:
  - return to the saved start pose only when needed
  - send `M23` / `M24`
  - keep USB fully quiet for `180 s`
  - let the Cura-generated SD G-code perform hotend heating and first motion
  - if `M24` has already been sent and the immediate USB read fails, treat the start as possibly active and enter the quiet window instead of probing `M27` or retrying immediately
- Reliability hardening:
  - Little Hands no longer mirrors the print-end marker to printer SD as `LHSTATE.TXT` immediately before print start
  - local print-end recovery state still lives in `monitor_logs/little_hands_print_state.json` and the ring log
  - this avoids extra `M28` / `M29` / `M30` SD writes in the sensitive window before `M23` / `M24`
- Rationale from logs:
  - the failed starts showed `LHSTATE.TXT` being written immediately before `PRINT_START`
  - the successful long SD print used the pure SD-owned start path with progress/temperature recovery after the quiet window

## 2026-05-09 Unconfirmed Silent Start Watchdog

- Field observation:
  - `M23` / `M24` could be accepted with `File opened` / `File selected` / `busy: processing`
  - then the printer could remain physically idle: no hotend fan, no motion, and no `M105` replies after the quiet window
  - the UI previously stayed in a misleading "printing / no telemetry" state forever because the silent-`M105` branch returned before the failed-start watchdog could clear the session
- App behavior now:
  - if `5` minutes pass after `M24` with no `M105`, no SD progress, and no previously observed active print, Little Hands marks the start as unconfirmed
  - the active print state is cleared locally, the failed-start recovery window is shown, and the log explicitly says to power-cycle only when the printer is physically not heating / not moving / not printing
  - stale persisted `printing` / `prepared` state without positive progress is no longer restored after the grace window; restart should not resurrect a dead start as an active print
  - if the printer is physically printing despite USB silence, the operator should not power-cycle and should monitor visually
- Stop hardening:
  - normal stop and hard stop now send `M108` before `M524`
  - this gives Marlin a chance to break out of a blocking `M109` heat wait before SD stop / heat-off commands are sent

## 2026-05-09 Strict SD File Selection Before M24

- Field correction:
  - the start helper previously sent `M23 <file>` and then `M24` after a fixed short delay
  - logs showed the current larger `CFFFP_~3.GCO` reporting `File opened` / `File selected` / `busy: processing`, but then never heating or moving
  - this is consistent with a race where `M24` is sent while the firmware is still finishing SD file selection
- App behavior now:
  - Little Hands sends `M23 <file>`
  - waits up to `8 s` for Marlin's `File selected` confirmation
  - only then sends `M24`
  - the same strict sequence is used for plain SD start, start from saved home, and pseudo-home upload-and-start
- Rationale:
  - successful starts used the same high-level workflow, but smaller / luckier SD selection timing
  - waiting for `File selected` is the Marlin-correct ordering and should reduce silent "selected but not actually running" starts without changing Cura G-code ownership of heating

## 2026-05-09 Treat M109 Heatup As Passive Telemetry

- Field correction:
  - after `M24`, Cura G-code reaches `M109`
  - while `M109` is waiting, Marlin does not process ordinary host commands like `M105` / `M27` / `M114`
  - instead it emits heater-state lines about once per second from inside the heatup loop
- App behavior now:
  - during the unconfirmed-start window Little Hands first listens passively for unsolicited temperature lines instead of immediately relying on `M105`
  - the read window is long enough to catch Marlin's roughly 1 Hz `M109` heater reports
  - if hotend target/current temperature is seen and the hotend is still below target, Little Hands shows `M109 heatup` and avoids sending `M27` / `M114` / `M115` into the blocked command queue
  - once the hotend reaches target or ordinary `M105` replies again, normal SD progress polling resumes
- Rationale:
  - a silent `M105` during `M109` is expected Marlin behavior, not proof of a failed start
  - this avoids both false failed-start decisions and command pileups while the printer is legitimately heating from SD G-code

## 2026-05-09 Restore The Proven No-M109 Preheat Workflow

- Field correction:
  - the previous successful overnight start was not a plain unmodified Cura file
  - the working model file had the early blocking `M109` replaced by non-blocking `M104`
  - a small `PREHEAT.GCO` / preheat step brought the hotend to temperature before the model file was started
- App behavior now:
  - before SD print start, Little Hands reads the target hotend temperature from the known G-code profile and preheats with `M104` / `M105`
  - for old or unknown files that may still contain blocking `M109`, it preheats about `7C` above the target so `M109 S...` can pass immediately; this mirrors the proven `225C` preheat before a `218C` model
  - if the target cannot be read from a local file or cached profile, it uses the current validated PLA first-layer target `218C` plus the same safety margin
  - uploads through Little Hands create a prepared copy where early startup `M109` is rewritten to `M104`
  - the bundled Cura slicing helper applies the same early `M109` -> `M104` rewrite
- Why this matters:
  - this matches the real proven workflow instead of relying on Marlin to sit inside a long blocking `M109` after `M24`
  - the SD file still owns the actual print moves and temperature target, but Little Hands makes sure heating has already happened before SD execution reaches the first layer

## 2026-05-09 Confirm Automatic Hotend Preheat Start

- Field confirmation:
  - after power-cycle recovery and saved start, Little Hands preheated the hotend to `225C`
  - the user then pressed `Start print` once; Little Hands detected the hotend was already at target, selected `CFFFP_~3.GCO`, and sent `M24`
  - the print finally started successfully with the automatic preheat workflow
- Final user-facing workflow:
  - user manually preheats only the external bed / warm mat
  - user does not manually preheat the hotend
  - Little Hands handles hotend preheat, strict `M23` / `File selected` / `M24`, and the post-`M24` USB quiet window
- UI text cleanup:
  - startup messages now say that the hotend was preheated by Little Hands
  - the post-`M24` quiet message no longer says that Cura is still responsible for heating
  - preheat progress is shown in the progress area as temperature rises

## 2026-05-09 Avoid False Failed-Start Window During Real Print

- Field observation:
  - the print physically started, but Little Hands still opened the "start not confirmed" recovery window at the `5 min` watchdog boundary
  - logs showed several fresh `M105 T:217-218 /218` samples before the warning
  - real `SD printing byte ...` progress arrived seconds after the warning, proving this was a false negative
- Fix:
  - the failed-start watchdog no longer fires if a recent post-`M24` `M105` sample with a non-zero hotend target was seen
  - in that state the UI says the hotend is at target and Little Hands is waiting for SD progress
  - the operator should not power-cycle if the printer is visibly printing

## 2026-05-09 Anti-Warp PLA Profile Update

- Field result:
  - `moduleBot` printed to completion, but all four bottom corners lifted from the external warm mat
  - the model bottom warped, and at least one wall showed layer separation
- Cura baseline changes:
  - brim widened from `6 mm` to `10 mm`
  - PLA first layer raised from `218C` to `225C`
  - PLA normal print temperature raised from `214C` to `220C`
  - historical note: this first attempt lowered Cura fan targets, but that was later corrected because the K9 has no independent part-cooling fan
  - current rule: slicer `M106/M107` commands are stripped; the single fan is reserved for firmware-managed hotend cooling
  - initial layer speed lowered from `7 mm/s` to `6 mm/s`
  - initial layer line width raised from `135%` to `145%`
- Rationale:
  - lifting on all corners points to global bed adhesion / shrink stress, not a single bad corner
  - wall delamination points to too-cold layer bonding for the current filament / airflow / room conditions
  - `10 mm` brim is acceptable now that the print-start failure was fixed in the automatic preheat / SD-start workflow; the old `10 mm` warning was about start reliability, not the brim geometry itself
- Operator note:
  - keep the external bed at the upper end of the tested range and let it soak before starting
  - clean the perforated mat before retrying
  - if corners still lift, test `12-14 mm` brim before jumping to `18 mm`

## 2026-05-09 Avoid 232C Preheat On New 225C G-code

- Field correction:
  - the user-sliced Cura file already had `M104 S225` / `M109 S225`
  - Little Hands treated any blocking `M109` file as needing a `+7C` safety margin and tried to preheat to `232C`
  - that margin was only intended for old `218C` files, where the proven workaround was `225C` preheat before a `218C` model
- Fix:
  - the `+7C` margin is now applied only when the detected target is below `220C`
  - new `225C` first-layer G-code preheats to `225C`, not `232C`

## 2026-05-12 Manual Jog / Long-Idle Coordinate Safety

- Field observation:
  - after a long idle / fresh power-on, manual bed jog felt much smaller and slower than the selected `20 mm` step
  - live printer settings were checked over USB: `M92 X606 Y606 Z600 E1040`, so EEPROM / firmware scale was not 10x wrong
  - controlled `Y +2 mm` / `Y -2 mm` test changed the Marlin step counter by exactly `1212` steps each way, confirming `Y606` math
- App fixes:
  - Little Hands now persists the selected manual jog step in `little_hands_ui_state.json`
  - manual jog log messages now include the physical hint, commanded distance, raw G-code axis, and feedrate
  - stale active-print state from logs / persisted print state expires after 30 minutes, so the app should not rebuild a trusted post-print coordinate model after a long idle
  - manual jog feedrates are explicit: `X F2400`, bed/logical `Y F600`, head vertical/logical `Z F600`
  - bed/logical `Y` and head vertical/logical `Z` jogs temporarily lower travel acceleration with `M204 T80`, wait for `M400`, then restore `M204 T1000`
- Rationale:
  - the dangerous case was not a bad `M92`, but trusting old print/position state after the printer may have been power-cycled or left idle
  - the confirmed slow `Y +/-5 mm F300` test moved the bed both ways, so the channel and motor were not treated as failed hardware
  - the live printer profile had `M201 Y1000` / `M204 T1000`; manual bed jog at high acceleration can skip steps while Marlin still believes the move completed
  - root cause was traced to the `LH v4` source baseline in `firmware_src/ECF-Marlin-upstream/Marlin/Configuration.h`: it carried `DEFAULT_MAX_ACCELERATION {1000,1000,100,1000}` and `DEFAULT_TRAVEL_ACCELERATION 1000`, and those values were persisted in EEPROM
  - `firmware_src/` is intentionally ignored by git, so the safe future-firmware change is captured as `docs/firmware/LH-v4-safe-motion.patch`
  - next firmware rebuild should apply that patch: `DEFAULT_MAX_ACCELERATION {300,200,100,1000}`, `DEFAULT_ACCELERATION 250`, and `DEFAULT_TRAVEL_ACCELERATION 200`
  - treat the bed/logical `Y` axis as the limiting axis when calculating print speeds, travel acceleration, service moves, and post-print presentation
  - after idle, the safe workflow is to establish the physical start pose again and press `Save start`

## 2026-05-12 K9 G-code Validation

- Added a first-class G-code validation path in the Little Hands Files & Firmware window:
  - new `Check G-code` button
  - the same validator runs before `Upload G-code` and `Upload & start`
- The validator blocks files that are unsafe or structurally wrong for the current K9 workflow:
  - old `_k9xz.gcode` plane-remap files
  - real `G28`
  - missing `G92 X0 Y0 Z0`
  - missing positive hotend target
  - bed heat `M140/M190 S>0` because the warm bed is external
  - `M18/M84`, because post-print recovery must keep steppers usable
  - missing extrusion moves or bounds outside `100 x 100 x 100 mm`
  - aggressive body `M204` values that can make the small Y-bed skip steps
- The validator warns, but does not block, cases that Little Hands can handle:
  - `TARGET_MACHINE.NAME:Unknown` when Little Hands start-gcode is present
  - early blocking `M109`, which is rewritten to `M104` during upload
  - slicer `M106/M107`, which is stripped because the single fan is firmware-managed hotend cooling
  - high Cura acceleration reset in the final tail when the validated end-gcode softens presentation moves afterward

## 2026-05-12 Stop / Go-To-Start Safety

- Field correction:
  - no power cycle was involved in the failed restart scenario
  - the start pose had been saved correctly
  - after `Stop`, pressing `Go to start` returned to the saved `Z0`
  - in this workflow `Z0` means the nozzle touches the bed, so the motion was expected mechanically but unsafe without a clear-bed confirmation
  - K9 has no real mechanical endstops; do not solve stopped-print recovery by driving axes blindly into hard limits
- App fix:
  - while an SD start / print is active, `Go to start` is blocked; the operator must stop the print first
  - after any SD print start, `Stop`, or `Hard stop`, Little Hands requires the operator to confirm that the bed is clear before any recovery path can lower the nozzle back to `Z0`
  - `Stop` now invalidates the trusted saved start pose because this K9 can report `X0/Y0` after `M524` even when the nozzle is physically not back at the start X/Y pose
  - before `M524`, `Stop` now tries to pause SD printing and capture `M114`; if that interrupted pose is available, `Go to start` restores that coordinate model with `G92`, lifts Z, moves to `X0/Y0`, lowers to `Z0`, and saves start again
  - if the interrupted pose was not captured, `Go to start` refuses automatic recovery and asks the operator to re-establish start manually
  - `Hard stop` also invalidates the trusted saved start pose because it sends `M18` and releases the steppers
  - `Upload & start` no longer uses pseudo-home; it requires a trusted saved start pose and starts from that pose
- Operator rule:
  - `Go to start` is a real return to print zero, not just a high safe travel point
  - after a stopped / aborted print, remove the failed first layer before pressing `Go to start`
  - if Little Hands says the stop pose was not captured, manually re-establish the fixed start pose and press `Save start`

## 2026-05-12 Hotend Preheat Failure Guard

- Field observation:
  - `Upload & start` uploaded `moduleBot_k9_warmmat_v5_easysupport.gcode` successfully and started the Little Hands hotend preheat stage
  - `M105` showed the target as `225C`, but the measured hotend temperature only drifted from about `39C` to `46C` over four minutes
  - the application correctly refused to send `M24`, so the model did not start cold
- App fix:
  - the preheat stage now keeps one serial session open instead of reopening the port for every `M105`
  - Little Hands selects `T0`, sends `M104 S...`, logs the hotend heater power value `@`, and shows it in the preheat progress text
  - if Marlin reports a non-zero target but the heater power stays `@0`, the app aborts early with a clear message
  - if the hotend target is not accepted, no temperature data arrives, or temperature does not rise, the app sends `M104 S0` before reporting failure
- Operator rule:
  - after this specific failure mode, power-cycle the printer before retrying, because the K9 USB/Marlin state may remain half-alive while still exposing the serial port

## 2026-05-13 ModuleBot Supported Orientation Result

- Field result:
  - the latest `moduleBot` print completed successfully
  - the model is intact
  - support removal is now better than the earlier supported-orientation attempt
- Working conclusion:
  - the current supported orientation is a reliable baseline
  - a normal-orientation test is now reasonable, but it should be treated as an A/B experiment against this successful baseline rather than a replacement profile yet
- Next test file:
  - generated a flipped broad-face-down STL copy at `exports/mbnorm01_moduleBot_normal_orientation.stl`
  - sliced it with the same K9 warm-mat cautious profile as `exports/mbnorm01_moduleBot_normal_orientation.gcode`
  - the filename intentionally starts with `mbnorm01`, so Little Hands / Marlin 8.3 naming should show it as `MBNORM01.GCO` instead of colliding with the previous `MODULEBO.GCO`
  - validation result: no blocking K9 workflow errors; bounds `X 9.56..90.45`, `Y 11.98..88.02`, `Z 0.20..25.00`; hotend target `225C`

## 2026-05-13 Upload UI And End-G-Code Cleanup

- UI workflow:
  - after a valid `Upload G-code` or `Upload & start`, the Files & Firmware window closes automatically
  - the main progress area now exposes a cancel button only while a file upload progress label is active
  - pressing cancel requests upload cancellation; the transfer stops at the next progress callback and no SD print start is attempted
  - after a cancelled upload, Little Hands automatically attempts to delete the partial target file from printer SD and refresh the SD list
- Print timing:
  - natural SD print completion now writes a human-readable finish line with local start, finish, and actual elapsed duration
  - the actual elapsed duration is stored in the known SD G-code profile and shown as `Known time` under the `Start` line when that file is selected or active
- Cura / validation cleanup:
  - the K9 end-gcode now applies the gentle `M204 P250 T120` immediately at the start of the end sequence
  - this overrides Cura's final `M204 P4000` / `M204 T4000` reset before any final lift or bed presentation move
  - the G-code validator no longer warns about the high Cura tail reset if a later gentle `M204` is present before `G1 Y95`
  - regenerated local `exports/mbnorm01_moduleBot_normal_orientation.gcode`; validation now passes without warnings

## 2026-05-13 Post-Print Home Recovery Fix

- Observed issue: after a completed print, pressing `Go to start` could still use the plain saved-zero path (`G1 X0/Y0/Z0`) instead of the safer post-print recovery path.
- Root cause:
  - the completion path marked `post_print_pose_known`, but did not store or use the real final `M114` pose
  - `Go to start` only considered the known post-print path when `session_zero_defined` was already false, so a completed print could bypass recovery
- Fix:
  - the completion sequence now asks `M114` after presenting the part
  - Little Hands stores the real post-print pose and persists it in the local print-state file
  - `Go to start` now prefers the saved real post-print pose whenever post-print recovery is required, even if the old session-zero flag is still true
  - if no reliable post-print / stopped-print pose exists, automatic `Go to start` is blocked and the user must jog manually and press `Save start`

## 2026-05-13 ModuleBot Next Anti-Warp / Floor Test

- Latest observed result:
  - walls are straight and have no cracks
  - corner lift still exists but is smaller, about `1-2 mm`
  - bottom / floor still has large gaps
- Next controlled profile change:
  - brim width `12 mm -> 14 mm`
  - initial layer line width `150% -> 155%`
  - initial nozzle temperature `225C -> 226C`
  - top / bottom layers `6 -> 7`
  - top / bottom flow `102% -> 104%`
  - initial layer flow `103%`
  - skin overlap `10%`
  - bridge skin / wall flow `90% -> 100%`
- Rationale:
  - this keeps the successful no-crack wall settings and support settings
  - it strengthens bed grip and floor closure without jumping to raft or emergency `18 mm` brim

## 2026-05-13 X Head Service-Motion Softening

- Observed follow-up: the same speed / skipped-step risk applies to `Head left`, especially during post-print recovery back to the start pose.
- Fix:
  - manual X jog now uses `F900` instead of `F2400`
  - manual X jog now temporarily lowers travel acceleration with `M204 T80`, like the bed / vertical axes
  - SD recovery / pseudo-home X service moves now use `SAFE_X_FEEDRATE = 900` instead of `1800`
  - Cura end-gcode presentation move `G1 X95` now uses `F900`
- Rule: if the head buzzes, skips, or moves weakly, treat it first as a service-motion speed / acceleration problem, not as a dead X motor or driver.

## 2026-05-13 ModuleBot Upside-Down Slice Guard

- Field failure:
  - `exports/moduleBot_k9_warmmat_v6_antiwarp_floor.gcode` was generated from raw `moduleBot.STL` and printed upside down
  - the bad slice was visibly support-heavy and reported about `22.3 m` filament instead of the expected `9-11 m` range for the intended broad-face-down orientation
- Fix:
  - the slicing helper now blocks direct raw `moduleBot.STL` slicing unless `--allow-unvalidated-modulebot-orientation` is passed explicitly
  - Little Hands G-code validation blocks local `moduleBot` files whose filament estimate is above `15 m`, because that is a strong sign of the accidental upside-down/support-heavy slice
  - the bad local export was removed from the top-level `exports/` workflow
- Operator rule:
  - for `moduleBot`, confirm orientation in Cura Preview before saving to SD
  - if the slicer estimate jumps to about `20 m+` filament or shows a forest of supports, stop and re-check orientation before printing
