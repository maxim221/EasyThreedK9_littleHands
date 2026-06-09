# Contributing To Little Hands

Thanks for helping with Little Hands. This project is small, field-driven, and safety-sensitive: a tiny printer can still crash into itself, overheat, or lose its physical position if the workflow is changed casually.

## What Feedback Helps Most

- exact printer model and visible controller-board markings
- photos of the board, wiring, SD card contents, and connector labels
- Linux distribution, Python version, and USB device name
- raw `M115`, `M503`, `M114`, `M105`, and `M27` replies when possible
- whether SD file listing, upload, start, stop, and post-print recovery behave as documented
- logs from `monitor_logs/` after a failed start or odd USB/SD state

Use the issue template when you can: it asks for the details that have mattered most during field debugging.

## Safety Rules

- Do not add startup `G28` to the K9 workflow.
- Do not make axis movement faster just because it looks slow; the current limits exist because the machine can skip steps while Marlin still reports success.
- Do not treat `ok` / `M400` as proof that the physical carriage moved.
- Do not enable Cura bed heat (`M140/M190 S>0`) in the public baseline.
- Do not add `M18` / `M84` at the end of print files; Little Hands needs steppers available for recovery.
- Do not let Cura control the single K9 fan as part cooling.

The full maintainer rules live in [AGENTS.md](AGENTS.md).

## Local Checks

Before sending changes that touch printer motion, SD print workflow, Cura settings, firmware assumptions, G-code validation, or post-print recovery, run:

```bash
python3 -m py_compile tools/k9_control_center.py tools/k9_marlin_sd.py tools/k9_cura_slice.py
python3 tools/regression_checks.py
```

If a physical printer test is needed, say exactly what will move or heat before running it.

## Pull Requests

Good pull requests are small and explicit:

- explain the field problem or safety reason
- say whether physical printer motion or heating was tested
- include logs or screenshots for UI/USB/SD behavior when relevant
- keep unrelated generated files, SD-card backups, and local logs out of the diff

If you are unsure whether a behavior is a firmware issue, slicer issue, or mechanical K9 issue, open an issue first. This project has already had several "looks like software, was actually field mechanics" moments.
