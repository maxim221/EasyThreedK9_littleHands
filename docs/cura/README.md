# Cura Baseline Bundle

This directory contains the current tracked Cura baseline for the validated EasyThreeD K9 / Little Hands setup.

- Cura version used during testing: `5.11`
- Machine: `lilHands K9 warm mat`
- Active Cura machine id: `lilHands_k9_warmmat`
- Profile: `codex - K9 warm mat cautious`
- Brim: `14 mm`
- PLA temperature: `225C` first layer, `224C` after that
- Cura material bed temperature: `0C`; the current controlled-hotbed slice path uses an explicit `;LH_EXPERIMENTAL_HOTBED_TARGET:60` marker plus non-blocking `M140 S60`
- Part cooling: `off`; the single K9 fan is the firmware-managed hotend fan, not an independent part-cooling fan
- Walls: `5`, with randomized Z seam to avoid concentrating the seam in one corner
- Draft protection: use a physical wind shield around the printer rather than Cura Draft Shield
- Ironing: highest top layer only, concentric, low flow
- Motion smoothing: conservative acceleration limits for reduced diagonal ringing
- Supports for `mainFlasherTop.STL`: everywhere, support interface / roof enabled, support angle `35`
- Cura file-name preference: `Add machine prefix to job name` must be `off`, so saved files are named like `moduleBot.gcode` instead of `CFFFP_moduleBot.gcode`

The app button `Export Cura profile` exports the live local Cura containers to `exports/`, which is intentionally ignored by git. This checked-in copy is the current local controlled-hotbed reference; keep public-release notes clear that standard Cura bed temperature remains `0C`.
The export also writes `CURA_PREFERENCES.txt` with the non-profile Cura preference that keeps the useless `CFFFP_` prefix disabled.

The local hotbed default was raised to `60C` at the operator's request on 2026-09-09. The app and helper cap targets at `60C` for Bed10K Max70 and wait up to `15 minutes` for bed preheat. Existing G-code keeps its original target: re-slice and upload it again to use the new temperature. Change live Cura containers only while Cura is closed, then reopen it; restart Little Hands when the printer is idle to load the new controls.

Save sliced G-code from Cura to the project's `gcode/` directory. The loose G-code files formerly in the repository root were moved there without changing their contents. Existing `exports/` helper output and `card_backups/` archives remain in place.

With Cura closed, set `[local_file] dialog_save_path` in `~/.config/cura/5.11/cura.cfg` to the absolute path of that directory (on this workstation: `/home/maxim/draftCode/littleHands/gcode`). Cura uses it as the suggested save directory and remembers a different directory if you choose one during a later save. This is an application preference, separate from the machine/profile containers.

After copying or editing Cura containers, confirm `~/.config/cura/5.11/cura.cfg` has `[cura] active_machine = lilHands_k9_warmmat`. If Cura silently falls back to the older `lilHands` machine, new Desktop G-code will use the old `G1 Z10.0 F1800` start and will not contain the controlled-hotbed marker.

Do not use startup `G28` with this printer. The start G-code uses the Little Hands manual-zero `G92 X0 Y0 Z0` workflow.

If the profile cannot be imported, use the manual settings sheet:

- [SETTINGS.md](SETTINGS.md)
- [SETTINGS.ru.md](SETTINGS.ru.md)
- [SETTINGS.zh.md](SETTINGS.zh.md)
