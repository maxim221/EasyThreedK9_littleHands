## What Changed

-

## Why

-

## Safety Notes

- [ ] No printer motion or heating was run.
- [ ] Physical motion/heating was run and described below.
- [ ] This changes printer motion, SD workflow, Cura settings, firmware assumptions, G-code validation, or recovery behavior.

## Validation

```bash
python3 -m py_compile tools/k9_control_center.py tools/k9_marlin_sd.py tools/k9_cura_slice.py
python3 tools/regression_checks.py
```

Result:

-

## Physical Test Notes

-
