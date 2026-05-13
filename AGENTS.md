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
- Head left/right service motion should stay around `F900`.
- All manual jog, bed-level, SD start-from-home, `Go to start`, recovery, and presentation service moves must use the ok-waiting serial helper plus `M400`/soft `M204 T80` where appropriate. Do not go back to fire-and-read command batches for axes.
- Post-print `Go to start` must not re-declare coordinates from saved `M114` while the live Marlin session still has a trusted saved zero.
- Never run automatic post-print axis movement for a print state restored from logs / app restart. Startup, reconnect, telemetry recovery, and restored completion detection may update UI/logs only; physical completion moves are allowed only for a trusted current live session.
- Stopped-print recovery must preserve interrupted X/Y from the pre-`M524` print position, but account for the K9 head lift after stop by using the raised post-stop Z when available. Do not treat the reset-like post-stop `X0 Y0 Z5` as real X/Y home.
- Home is trusted only after `Save start` or a confirmed Little Hands recovery/return. Port changes, disconnects, motor-off, hard stop, failed jog/recovery/start, and stopped prints must mark home uncertain or invalid and block SD start until the operator re-saves or confirms recovery.
- End G-code should present the bed toward the operator with gentle motion: `M204 P250 T120`, `G1 X95 F900`, `G1 Y95 F240`.
- Do not add `M18` / `M84` at the end of print files; Little Hands needs steppers available for recovery.
- Do not let Cura control the single K9 fan as part cooling. Slicer `M106/M107` must be stripped or disabled.
- Do not directly slice raw `moduleBot.STL` without checking orientation. Use the validated oriented STL or explicitly inspect Cura Preview.
- Keep the current slow Cura baseline for this small K9 mechanics unless a new physical test proves a faster profile is safe: print/infill `11 mm/s`, wall/top-bottom `8 mm/s`, travel `25 mm/s`, first-layer and skirt/brim `4 mm/s`, bridge `7 mm/s`.

## Documentation

When a workflow or safety rule changes, update:

- `PROJECT_LOG.md`
- relevant files under `docs/`
- this file, if the rule affects future agent behavior
