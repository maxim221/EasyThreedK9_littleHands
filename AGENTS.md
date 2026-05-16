# Little Hands Project Rules

These rules are mandatory for future Codex / agent work in this repository.

## Regression Checks

Before committing any change that touches printer motion, SD print workflow, Cura settings, firmware assumptions, G-code validation, or post-print recovery, run:

```bash
python3 -m py_compile tools/k9_control_center.py tools/k9_marlin_sd.py tools/k9_cura_slice.py
python3 tools/regression_checks.py
```

If a physical printer test is needed, ask the operator before moving axes or starting a print.

## Do Not Regress Fixed K9 Behavior

- Do not use `G28` for this K9 workflow. The printer has no reliable endstop-based home in the current baseline.
- Do not leave service/manual/recovery moves at `M204 T1000`. The safe Little Hands service state is `M204 T80`; print G-code may set its own conservative print accelerations.
- Bed/logical `Y` service motion is the limiting axis. Keep long bed service/recovery moves at `F240`; keep manual bed jog at the validated working UI/manual context `F600` with `M204 P80 T80`, honoring the selected UI step as one move.
- Manual bed jog must match the validated direct-control sequence and must not open a separate pre-move `M114` query/session before the jog. This K9 has no endstops, so raw negative coordinates are not a physical-edge guard in this workflow.
- During operator-requested bed jog diagnostics, the operator watches the physical bed and keeps it away from hard stops. Do not assume "bed is at the edge" or diagnose a buzz/no-move symptom as a physical hard-stop unless the operator reports that it is actually at the edge; still keep app-level safety and recovery guards.
- Head left/right service motion should stay around `F900`.
- All manual jog, bed-level, SD start-from-home, `Go to start`, recovery, and presentation service moves must use the ok-waiting serial helper plus `M400`/soft `M204 T80` where appropriate. Do not go back to fire-and-read command batches for axes.
- Post-print `Go to start` must not re-declare coordinates from saved `M114` while the live Marlin session still has a trusted saved zero.
- Never run automatic post-print axis movement for a print state restored from logs / app restart. Startup, reconnect, telemetry recovery, and restored completion detection may update UI/logs only; physical completion moves are allowed only for a trusted current live session.
- Stopped-print recovery must preserve interrupted X/Y from the pre-`M524` print position, but account for the K9 head lift after stop by using the raised post-stop Z when available. Do not treat the reset-like post-stop `X0 Y0 Z5` as real X/Y home.
- Normal `Stop` is not the emergency stop path. It should pause, capture `M114`, try a controlled safe Z lift, then stop SD/heaters and keep that stopped-print recovery pose. Manual jogs after Stop must update this recovery pose instead of deleting it.
- If the nozzle is known to be at saved start (`Z0`) before SD start, lift to safe Z clearance before long hotend preheat, then return to saved start immediately before `M24`.
- Every UI SD-start path must send `start_sd_print_from_home` after any preheat/lift phase, never plain `start_sd_print`, so Cura's initial `G92 X0 Y0 Z0` is executed at the real saved start and not at the temporary preheat clearance height.
- If hotend preheat fails after Little Hands lifted Z for clearance, first undo that known lift with a relative move of the same distance (`G91` / `G1 Z-<clearance>`), then surface the error. Do not recover with `G1 Z0` because a USB/controller reset can make the raised pose become the new logical zero. If the relative return fails or USB disappeared, mark home uncertain and require the operator to visually confirm the physical start and press `Save start` again.
- If Marlin reports a hotend target and nonzero heater output but the temperature stays near the external warm-bed temperature, abort quickly, send heater-off, and do not keep waiting for the full preheat timeout. Recovery attempts after this must use short acknowledgements because the K9 may stop answering USB commands.
- If Stop succeeds during the post-`M24` quiet window but `M114` is not captured, `Go to start` may only offer the guarded live-session return path while warning the operator to clear the bed and visually confirm/save start afterwards. Clear that marker on new print starts, hard stop, motor off, port changes/disconnects, or after the attempt.
- If USB drops during a real SD print and the app later still has a stale active-print marker, `Go to start` must not blindly block when a matching valid `LH_END_GCODE_V1` predicted print-end exists and there is no recent SD progress. It may offer the guarded predicted-end recovery prompt after the operator confirms the print is finished, the bed is clear, and axes were not moved.
- If USB re-enumerates the CH340 printer to a new `/dev/ttyUSB*` name after a disconnect, guarded `Go to start` recovery may automatically switch to the single currently visible safe printer-like port. Do not require manual `Find` when exactly one CH340/ACM printer port is present.
- Do not discard a valid predicted print-end recovery pose just because an old active-print state is older than the active-restore window. It is safer to drop the stale active marker but keep the explicit guarded recovery option.
- Home is trusted only after `Save start` or a confirmed Little Hands recovery/return. Port changes, disconnects, motor-off, hard stop, failed jog/recovery/start, and stopped prints must mark home uncertain or invalid and block SD start until the operator re-saves or confirms recovery.
- End G-code should present the bed toward the operator with gentle motion: `M204 P250 T120`, `G1 X95 F900`, `G1 Y95 F240`.
- Do not add `M18` / `M84` at the end of print files; Little Hands needs steppers available for recovery.
- Do not let Cura control the single K9 fan as part cooling. Slicer `M106/M107` must be stripped or disabled.
- Do not directly slice raw `moduleBot.STL` without checking orientation. Use the validated oriented STL or explicitly inspect Cura Preview.
- Keep the current cautious Cura baseline for this small K9 mechanics unless a new physical test proves a faster profile is safe: print/infill `11 mm/s`, wall/top-bottom `8 mm/s`, travel `25 mm/s`, first layer `6 mm/s`, skirt/brim `21 mm/s`, bridge `7 mm/s`. Do not drop first-layer/brim to `4 mm/s` without an explicit physical test; it made the print crawl rather than simply reducing speed by 30%.
- Keep Cura `Preferences -> General -> Add machine prefix to job name` disabled (`[cura] jobname_prefix = False`). The K9 workflow should save `model.gcode`, not `CFFFP_model.gcode`.

## Documentation

When a workflow or safety rule changes, update:

- `PROJECT_LOG.md`
- relevant files under `docs/`
- this file, if the rule affects future agent behavior
