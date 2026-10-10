# Little Hands: quick guide

For the EasyThreed K9 / ET-4000+ with a manually saved start. This printer has no reliable endstop-based home in this workflow: do not use G28.

## Local agent / script control

While the GUI is running, `python3 tools/k9_agent_cli.py status` returns a
structured health and telemetry snapshot without moving the mouse or opening a
second printer connection. `watch --interval 5` emits JSONL for monitoring.
Commands that heat, move, stop, delete, or start require explicit CLI
confirmation and still pass the normal safety guards. Accepted commands are
asynchronous; check `status.operation`. The operator must watch every jog and
print start. See `docs/AGENT_CONTROL.md`.

## 1. Connect and save start

1. Connect USB and select the printer port, or click Find.
2. Set the physical start: head left, bed away from you, nozzle at the bed surface. Watch each axis and keep it away from hard stops.
3. Click Save start. This declares the current position as zero without moving the axes.

X moves the head left/right; Y moves the bed toward/away; Z moves the head up/down. Jog steps are 0.1–50 mm. A printer acknowledgement does not prove physical movement. If an axis did not move, inspect it and set start again.

## 2. Prepare and print

1. In Cura, select lilHands K9 warm mat and the cautious K9 profile. Save G-code in the project's gcode/ folder. Check orientation in Preview; do not slice raw moduleBot.STL without inspecting it.
2. Open Files & Firmware, choose G-code, and click Check G-code. Use Upload G-code or Upload & start.
3. For an uploaded file, select it in the SD list and click Print. The printer must physically be at the saved start.
4. Wait for preheat: the app first lifts the saved-start nozzle 10 mm, then heats the bed if requested, runs hotend stages at 60/100/150/200°C and the final heat gate, and returns to the saved start before printing. Lifting before bed heat prevents the nearby nozzle from warming enough to start the shared fan and slow the bed.
5. USB can be silent for the first 180 seconds after start. Watch the printer; USB silence alone does not mean it stopped. Do not refresh the SD list during this window.

After `M24`, missing `M105`/`M27` telemetry never authorizes an automatic stop. Little Hands keeps the SD print marked active, keeps service and return moves locked, and does not send `M524`. Stop only with the explicit operator Stop control. Confirm completion before clearing an uncertain active print.

If a restored print is definitely no longer running and you manually return the nozzle to the start, `Save start` is an explicit decision to close that old unknown result. The app records the decision and must not show the old file as active again after restart.

During preheat, **Stop becomes Cancel**. Cancellation turns heat off and undoes the known nozzle lift. Closing the window requests cancellation and waits for verified heater shutdown; manual axes stay locked until cleanup finishes.

Cancelled or damaged uploads remain blocked until deletion or a clean upload. Do not start an unknown partial SD copy. Port changes are locked during USB operations; use Cancel to stop an upload.

## 3. Heat and filament

- Public LH v5 firmware uses an external warm mat. The installed controlled bed uses experimental LH v8 Bed10K Max70 BedGuard3C60s: the initial bed heating watch is 180 seconds and the active hold guard is 3°C/60s. Thermal-runaway protection, the 2°C initial rise check, the 70°C firmware limit, and the 60°C application cap remain enabled.
- New local slices use `;LH_EXPERIMENTAL_HOTBED_TARGET:60` for host preheat and `;LH_EXPERIMENTAL_HOTBED_PRINT_TARGET:55` plus `M140 S55` for printing. Little Hands lifts the nozzle before enabling the bed, reaches 59°C before hotend preheat, then returns to saved start and verifies the reduced 55°C target immediately before `M24`. Keep Cura's ordinary bed temperature at 0°C; SD files must not contain M190.
- Manual bed presets are 35/40/50/55/60°C plus Hotbed off. Maximum target: 60°C. Before printing, the app waits up to 15 minutes and checks both actual temperature and the accepted setpoint. Failed preheat attempts to shut down both heaters and does not start the print.
- Manual bed heating is blocked during SD printing; Hotbed off is available between USB operations.
- Hotend 200C warms the nozzle for manual loading. Wait for a confirmed 180°C, choose an E step, then click Feed or Retract. These moves are blocked during printing. Hotend off stops nozzle heating.

The operator selected 60°C preheat / 55°C print support after a watched center-airflow test showed that the bed falls to about 55.7°C even at full output. This handoff reduces simultaneous bed, hotend, and motor load; it does not claim that the bed can physically hold 60°C under airflow. Cut power for smell, hot connectors, unstable readings, or heating that will not turn off.

## 4. Finish, Stop and return

1. Confirm printing has finished and remove the model.
2. Click Go to saved start in manual controls. Confirm recovery only when every condition in the dialog is met.
3. Check and save the physical start before the next print. Power-cycle for 5–10 seconds only when the app explicitly requires it after a real firmware reset/thermal halt, hard stop, unacknowledged Stop, or unconfirmed heater/USB cleanup.

Normal completion and an acknowledged Stop do not by themselves require a power cycle. If the exceptional gate is active and the power cycle was already completed when you click Save start, answer Yes in its separate confirmation. A successfully acknowledged Save start then records both conditions; answering No saves the pose but keeps that safety gate.

Pause waits for motion to finish and saves the paused file, SD cursor, coordinates, and temperatures. Resume rechecks them before sending the command. After a USB disconnect or app restart, confirm that printer power stayed on and the axes and part were not moved. A cooled nozzle, changed file/position, power reset, or unconfirmed pause blocks resuming.

Normal Stop first checks SD status. If the file already completed (`Not SD printing`), the app preserves the final pose and skips the nozzle lift and `M524`, because that command can move X/Y in the current firmware. If printing is still active, Stop attempts a safe lift, saves the interrupted pose, and turns off printing and heaters. If the printer does not acknowledge shutdown, the app shows “Stop is unconfirmed” and blocks automatic return. Hard stop is the emergency path; cut printer power for immediate danger. Motors off invalidates the saved start.

After USB loss or an app restart, axes never return automatically. If the restored printer answers `Not SD printing` and the G-code has a valid saved final pose, the app opens a result-confirmation window. Use **Confirm finish** only when the whole print completed, the model was removed, and the axes stayed at the final pose; guarded **Go to saved start** can then use that exact pose. Known-pose recovery returns X in acknowledged segments no longer than 50 mm at the validated F600; every segment uses the same local-neutral `G92 X50` one-move context as the working manual X jog, rather than saved-coordinate absolute X targets. After any X/Y return, visually confirm that the head is near-left, the bed is fully back, and the nozzle is at the saved height. `M114 = X0 Y0 Z0` is firmware state, not proof of physical motion; the app keeps start untrusted until this visual confirmation. An unfinished print must be returned manually. The app may select a replacement printer port when exactly one safe port is available.

If the computer or app restarts while SD printing continues, Little Hands does not “resume G-code from the cursor”: the printer is already continuing the SD job autonomously. The app restores the active marker, selects the sole safe printer port without refreshing the SD directory, and uses plain `M930` as its first state query to verify the saved LH1 token/session. A match attaches the GUI to the already-running job, restores live telemetry, and enables Pause, Stop, emergency heater-off, and verified Resume only for a previously confirmed pause. It does not resend `M24`, reselect the file, or move axes; jog, upload, another start, and return-to-start remain blocked during the active print.

If the log says that USB re-enumerated, Linux observed a real detach/attach rather than an ordinary late firmware reply. Check the USB cable, powered hub, connectors, and electrical interference. When possible, place the printer on a short direct or separately powered USB path instead of the same downstream hub as USB audio/video devices.

Open **Recovery** beside USB metrics to inspect or save the last replies. Each sample has its own time; old progress is not an exact stop point. The app retains a copy of the source G-code, but does not automatically replay a file tail from stale coordinates. An unfinished print cannot use the predicted final pose for return. If the controller is unresponsive, restore communication first; after a reset with unknown physical position, set start manually.

If preheat fails after lifting the nozzle, do not save the raised position as start. The app first tries to undo the known lift. If that fails, restore USB, use Go to saved start, and confirm printing never started and the axes were not moved. Heating failed requires a power cycle first. Inspect a sticking axis before retrying; do not force it with faster moves.

If the app remembers a failed lift, Save start requires confirmation that the nozzle was physically returned near the bed. Saving a raised pose does not lower the nozzle.

If USB disappears while heating and heater shutdown is unconfirmed, switch the printer power off. Restore communication and check both heater targets and outputs are zero before recovery.

## 5. Level the bed

Save start enables the five points: FL / C / FR / BL / BR. At Z0, use a 0.05 mm feeler with light, even drag. A 0.10 mm feeler is an upper check, not the target gap: Cura already raises the first layer to about Z0.20. Save start again after adjustment and inspect the first layer visually.

## 6. Help and files

Manual follows the selected language. Export Cura profile saves local settings in exports/. Edit Cura settings with Cura closed; restart Little Hands while the printer is idle. Do not enable Cura control of the printer's single fan.

USB metrics shows firmware replies; Save log saves diagnostics. Logs and state live in monitor_logs/ inside the project. Choose firmware for your board; experimental builds do not automatically replace the public LH v5 baseline.
