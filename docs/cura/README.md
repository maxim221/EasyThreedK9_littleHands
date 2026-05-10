# Cura Baseline Bundle

This directory contains the current tracked Cura baseline for the validated EasyThreeD K9 / Little Hands setup.

- Cura version used during testing: `5.11`
- Machine: `lilHands K9 warm mat`
- Profile: `codex - K9 warm mat cautious`
- Brim: `12 mm`
- PLA temperature: `225C` first layer, `222C` after that
- Bed temperature in G-code: `0C`, because the warm bed is external
- Ironing: highest top layer only, concentric, low flow
- Motion smoothing: conservative acceleration limits for reduced diagonal ringing
- Supports for `mainFlasherTop.STL`: everywhere, support interface / roof enabled, support angle `35`

The app button `Export Cura profile` exports the live local Cura containers to `exports/`, which is intentionally ignored by git. This checked-in copy is the public reference baseline.

Do not use startup `G28` with this printer. The start G-code uses the Little Hands manual-zero `G92 X0 Y0 Z0` workflow.

If the profile cannot be imported, use the manual settings sheet:

- [SETTINGS.md](SETTINGS.md)
- [SETTINGS.ru.md](SETTINGS.ru.md)
- [SETTINGS.zh.md](SETTINGS.zh.md)
