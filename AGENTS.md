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
- Bed/logical `Y` service motion is the limiting axis. Keep bed service moves around `F600` unless a new physical test proves otherwise.
- Head left/right service motion should stay around `F900`.
- Post-print `Go to start` must not re-declare coordinates from saved `M114` while the live Marlin session still has a trusted saved zero.
- End G-code should present the bed toward the operator with gentle motion: `M204 P250 T120`, `G1 X95 F900`, `G1 Y95 F600`.
- Do not add `M18` / `M84` at the end of print files; Little Hands needs steppers available for recovery.
- Do not let Cura control the single K9 fan as part cooling. Slicer `M106/M107` must be stripped or disabled.
- Do not directly slice raw `moduleBot.STL` without checking orientation. Use the validated oriented STL or explicitly inspect Cura Preview.

## Documentation

When a workflow or safety rule changes, update:

- `PROJECT_LOG.md`
- relevant files under `docs/`
- this file, if the rule affects future agent behavior
