# Manual Cura / Slicer Settings

Use this file when the bundled Cura profile cannot be imported, or when another slicer version is used.

These settings describe the currently validated EasyThreeD K9 / Little Hands baseline. They are intentionally conservative: slow PLA printing, external warm bed, manual-zero start, no firmware-controlled bed.

## Machine

- Printer model name: `lilHands K9 warm mat`
- Printable area: `100 x 100 x 100 mm`
- Origin at center: `off`
- Heated bed in firmware: `off`
- G-code flavor: `RepRap (RepRap)` or the closest Marlin / RepRap-style mode available
- Filament diameter: `1.75 mm`
- Nozzle diameter: use the real installed nozzle; the validated profile does not override Cura's nozzle diameter

## Start G-code

Use exactly this style of start G-code. Do not add `G28`.

```gcode
; Little Hands manual-zero workflow for EasyThreed K9 / K9 Plus
; Expected fixed start pose on this printer:
; X = fully left, Y = bed fully back (away from operator), Z = nozzle touching bed
; This pose is treated as logical 0,0,0. Do not G28 before print.
G92 X0 Y0 Z0
G1 Z10.0 F600
G92 E0
```

## End G-code

Use raw Marlin axes exactly as shown here. On the validated Little Hands K9 this presents the part by lifting the head and moving the bed toward the operator.

```gcode
M204 P250 T120 ;Gentle final presentation moves for the small Y-bed
M104 S0 ;Hotend off
M140 S0 ;Bed off in G-code even though bed is external
G91
G1 E-1 F1800
G1 Z10 F1200
G90
G1 X95 F900
G1 Y95 F240 ;Move bed toward the operator
```

Do not add `M84` at the end. Little Hands keeps steppers available for the post-print recovery workflow.

## Material And Temperature

- Material: PLA
- First layer hotend: `225C`
- Normal hotend: `224C`
- Bed temperature in G-code: `0C`
- Real external warm bed / warm mat: manually preheated to about `40-50C`
- Part cooling in Cura: `off`
- Important: the current K9 has one physical fan, used as the firmware-managed hotend fan. Little Hands / the helper strip slicer `M106/M107` commands so Cura cannot treat that fan as part cooling.
- Minimum layer time: `10 s`

## Quality

- Layer height: `0.16 mm`
- First layer height: `0.20 mm`
- Wall line count: `5`
- Top layers: `7`
- Bottom layers: `7`
- Infill density: `20%`
- Infill pattern: `lines`
- Print infill before walls: `off`
- Flow: `103%`
- Wall flow: `103%`
- Outer wall flow: `102%`
- Top / bottom flow: `104%`
- Infill flow: `101%`
- Initial layer flow: `103%`
- Skin overlap: `10%`
- Top / bottom pattern: `lines`
- Initial bottom pattern: `concentric`
- Ironing: `on`
- Iron only highest layer: `on`
- Ironing pattern: `concentric`
- Ironing line spacing: `0.12 mm`
- Ironing flow: `7%`
- Z seam alignment: `Random`

## Speed

- Print speed: `15 mm/s`
- Wall speed: `12 mm/s`
- Top / bottom speed: `11 mm/s`
- Infill speed: `15 mm/s`
- Travel speed: `35 mm/s`
- Initial layer speed: `6 mm/s`
- Ironing speed: `8 mm/s`

## Motion Smoothing

These limits are intentionally gentle for the small K9 mechanics and help reduce ringing / rattling on diagonal moves.

- Acceleration control: `on`
- Print acceleration: `250 mm/s^2`
- Wall acceleration: `180 mm/s^2`
- Outer wall acceleration: `150 mm/s^2`
- Inner wall acceleration: `200 mm/s^2`
- Top / bottom acceleration: `180 mm/s^2`
- Infill acceleration: `250 mm/s^2`
- Support acceleration: `220 mm/s^2`
- Support interface / roof acceleration: `160 mm/s^2`
- Initial layer and skirt / brim acceleration: `150 mm/s^2`
- Travel acceleration: `200 mm/s^2`
- Ironing acceleration: `120 mm/s^2`
- Jerk control: `off`
- Note: do not enable Cura jerk control for this RepRap-flavor profile yet; our Marlin firmware uses `M205`, while Cura emits `M566` for jerk in this mode.
- K9 service-motion limit: the verified `LH-v4` currently stores `M201 X1000 Y1000` and `M204 T1000` in EEPROM/Marlin, which is too aggressive for manual and recovery moves on the tiny mechanics. Keep print travel acceleration at or below `200 mm/s^2`; Little Hands leaves manual/recovery motion in the soft `M204 T80` service-idle state, moves long bed service moves around `F240`, uses `F300` for manual bed jogs, and moves the head left/right around `F900`.

## Adhesion

- Build plate adhesion: `brim`
- Brim width: `14 mm`

If corners still lift, first check bed cleanliness, external bed warm-up, and first-layer squish; then temporarily try `16 mm` brim. Keep `18 mm` as a rescue setting because it adds significant footprint and time.

For the repeatable crack in one physical corner, use a physical draft wall / wind shield near the printer. Do not enable Cura Draft Shield by default: a real wall is simpler and does not add extra printed plastic to the G-code.

## Supports

For `mainFlasherTop.STL` and similar overhang-heavy parts:

- Generate support: `on`
- Support placement: `everywhere`
- Support overhang angle: `35 deg`
- Support structure: `normal`
- Support pattern: `zigzag`
- Support density: `10%`
- Support interface: `on`
- Support roof: `on`
- Support interface density: `65%`
- Support roof density: `65%`
- Support interface height: `0.48 mm`
- Support roof height: `0.48 mm`
- Support Z distance: `0.16 mm`
- Support top distance: `0.16 mm`
- Support XY distance: `0.3 mm`

If supports grip too hard, try these `easy-release` values first. Keep Z distance at `0.16 mm` for now to protect underside quality. If removal is still difficult, make the next separate test Support Z distance / top distance `0.24-0.32 mm`.

If the slicer preview does not show supports under the problematic underside, do not print yet. Change support placement / threshold until the preview actually shows support where needed.

## Model Orientation Sanity Check

For `moduleBot.STL`, do not print a fresh slice until Cura Preview confirms the intended orientation. During 2026-05 testing, directly slicing the raw `moduleBot.STL` produced an upside-down, support-heavy file.

A practical sanity check for this model: the validated orientation is usually around `9-11 m` of filament. If a small `moduleBot` slice suddenly shows about `20 m+` of filament or a forest of supports, do not save it to SD; re-check orientation in Preview and re-slice.

## Retraction And Bridges

- Retraction: `on`
- Retraction distance: `6.5 mm`
- Retraction speed: `25 mm/s`
- Prime speed: `25 mm/s`
- Bridge settings: `on`
- Bridge fan speed: `0%`
- Bridge skin speed: `10 mm/s`
- Bridge wall speed: `10 mm/s`
- Bridge skin flow: `100%`
- Bridge wall flow: `100%`
- Initial layer line width: about `155%`

## Before Saving To SD

The generated G-code must satisfy all of these:

- no real startup `G28`
- contains `G92 X0 Y0 Z0` near the start
- contains a hotend target command such as `M104` / `M109`
- if the file is uploaded through Little Hands or generated by the slicing helper, early `M109` is rewritten to `M104` and the hotend is preheated before SD start
- bed target remains `0C`
- Cura / slicer bounds are sane and fit inside the `100 x 100 mm` bed
- height fits inside `100 mm`
- not `Filament used: 0m`
- no `M18/M84`, no bed heat `M140/M190 S>0`, and no body `M204` above the safe K9 baseline
- preview shows supports where the model needs them

If any of these fail, re-slice from settings. Do not manually edit the G-code unless you intentionally create a new file and clearly mark it as modified.
