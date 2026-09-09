# Little Hands: quick guide

For the EasyThreed K9 / ET-4000+ with a manually saved start. This printer has no reliable endstop-based home in this workflow: do not use G28.

## 1. Connect and save start

1. Connect USB and select the printer port, or click Find.
2. Set the physical start: head left, bed away from you, nozzle at the bed surface. Watch each axis and keep it away from hard stops.
3. Click Save start. This declares the current position as zero without moving the axes.

X moves the head left/right; Y moves the bed toward/away; Z moves the head up/down. Jog steps are 0.1–50 mm. A printer acknowledgement does not prove physical movement. If an axis did not move, inspect it and set start again.

## 2. Prepare and print

1. In Cura, select lilHands K9 warm mat and the cautious K9 profile. Save G-code in the project's gcode/ folder. Check orientation in Preview; do not slice raw moduleBot.STL without inspecting it.
2. Open Files & Firmware, choose G-code, and click Check G-code. Use Upload G-code or Upload & start.
3. For an uploaded file, select it in the SD list and click Start print. The printer must physically be at the saved start.
4. Wait for preheat: bed first if requested by the file, then hotend stages at 60/100/150/200°C and a final heat gate. Before hotend warmup, the app lifts the nozzle 10 mm and returns it before starting.
5. USB can be silent for the first 180 seconds after start. Watch the printer; USB silence alone does not mean it stopped. Do not refresh the SD list during this window.

Cancelled or damaged uploads remain blocked until deletion or a verified replacement. Do not start an unknown partial copy from the card. Port changes and app closure are blocked during an operation; use Cancel to stop an upload.

## 3. Heat and filament

- Public LH v5 firmware uses an external warm mat. The installed controlled bed requires LH v6 Bed10K Max70.
- New local slices request 60°C through ;LH_EXPERIMENTAL_HOTBED_TARGET:60 and M140 S60. Keep Cura's ordinary bed temperature at 0°C; SD files must not contain M190. Re-slice and upload old files to change their target.
- Manual bed presets are 35/40/50/55/60°C plus Hotbed off. Maximum target: 60°C. Before printing, the app waits up to 15 minutes and checks both actual temperature and the accepted setpoint. Failed preheat attempts to shut down both heaters and does not start the print.
- Manual bed heating is blocked during SD printing; Hotbed off is available between USB operations.
- Hotend 200C warms the nozzle for manual loading. Wait for a confirmed 180°C, choose an E step, then click Feed or Retract. These moves are blocked during printing. Hotend off stops nozzle heating.

The operator selected 60°C; a setting change does not replace physical validation. Before a new test, check plausible cold B: and B@:0, watch warmup, and finish with Hotbed off. Cut power for smell, hot connectors, unstable readings, or heating that will not turn off. Faint clicks during otherwise normal early hotend warmup have been observed; those alone do not call for firmware changes.

## 4. Finish, Stop and return

1. Confirm printing has finished and remove the model.
2. Click Go to saved start in manual controls. Confirm recovery only when every condition in the dialog is met.
3. Before the next print, switch printer power off for 5–10 seconds, power it on, check the physical start, and click Save start again. Confirm this power cycle at the next start.

Pause and Resume control SD printing. Normal Stop saves a recovery pose, attempts a safe nozzle lift, and stops printing and heaters. Hard stop is the emergency path; cut printer power for immediate danger. Motors off invalidates the saved start.

After USB loss or an app restart, axes never return automatically. Recovery from a saved final pose requires a finished print, a removed model, and confirmation that the axes were not moved. The app may select a replacement printer port when exactly one safe port is available.

If preheat fails after lifting the nozzle, do not save the raised position as start. The app first tries to undo the known lift. If that fails, restore USB, use Go to saved start, and confirm printing never started and the axes were not moved. Heating failed requires a power cycle first. Inspect a sticking axis before retrying; do not force it with faster moves.

## 5. Level the bed

Save start enables the five points: FL / C / FR / BL / BR. At Z0, use a 0.05 mm feeler with light, even drag. A 0.10 mm feeler is an upper check, not the target gap: Cura already raises the first layer to about Z0.20. Save start again after adjustment and inspect the first layer visually.

## 6. Help and files

Manual follows the selected language. Export Cura profile saves local settings in exports/. Edit Cura settings with Cura closed; restart Little Hands while the printer is idle. Do not enable Cura control of the printer's single fan.

USB metrics shows firmware replies; Save log saves diagnostics. Logs and state live in monitor_logs/ inside the project. Choose firmware for your board; experimental builds do not automatically replace the public LH v5 baseline.
