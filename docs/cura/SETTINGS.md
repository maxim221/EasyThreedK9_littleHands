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
G1 Z10.0 F1800
G92 E0
```

## End G-code

Use raw Marlin axes exactly as shown here. On the validated Little Hands K9 this presents the part by lifting the head and moving the bed toward the operator.

```gcode
M104 S0 ;Hotend off
M140 S0 ;Bed off in G-code even though bed is external
G91
G1 E-1 F1800
G1 Z10 F1200
G90
G1 X95 F3000
G1 Y95 F3000 ;Move bed toward the operator
```

Do not add `M84` at the end. Little Hands keeps steppers available for the post-print recovery workflow.

## Material And Temperature

- Material: PLA
- First layer hotend: `218C`
- Normal hotend: `214C`
- Bed temperature in G-code: `0C`
- Real external warm bed / warm mat: manually preheated to about `40-50C`
- Cooling fan: `100%`
- Minimum layer time: `10 s`

## Quality

- Layer height: `0.16 mm`
- First layer height: `0.20 mm`
- Wall line count: `4`
- Top layers: `6`
- Bottom layers: `6`
- Infill density: `20%`
- Infill pattern: `lines`
- Print infill before walls: `off`
- Top / bottom pattern: `lines`
- Initial bottom pattern: `concentric`

## Speed

- Print speed: `16 mm/s`
- Wall speed: `12 mm/s`
- Top / bottom speed: `12 mm/s`
- Infill speed: `18 mm/s`
- Travel speed: `40 mm/s`
- Initial layer speed: `7 mm/s`

## Adhesion

- Build plate adhesion: `brim`
- Brim width: `6 mm`

Do not use `10 mm` brim as the default. A `10 mm` brim file selected on SD but did not enter a reliable print start on the validated K9.

## Supports

For `mainFlasherTop.STL` and similar overhang-heavy parts:

- Generate support: `on`
- Support placement: `everywhere`
- Support overhang angle: `35 deg`
- Support structure: `normal`
- Support pattern: `zigzag`
- Support density: `12%`
- Support interface: `on`
- Support roof: `on`
- Support interface density: `85%`
- Support roof density: `85%`
- Support interface height: `0.8 mm`
- Support roof height: `0.8 mm`
- Support Z distance: `0.16 mm`
- Support top distance: `0.16 mm`
- Support XY distance: `0.2 mm`

If the slicer preview does not show supports under the problematic underside, do not print yet. Change support placement / threshold until the preview actually shows support where needed.

## Retraction And Bridges

- Retraction: `on`
- Retraction distance: `6.5 mm`
- Retraction speed: `25 mm/s`
- Prime speed: `25 mm/s`
- Bridge settings: `on`
- Bridge fan speed: `100%`
- Bridge skin speed: `10 mm/s`
- Bridge wall speed: `10 mm/s`
- Bridge skin flow: `90%`
- Bridge wall flow: `90%`
- Initial layer line width: about `135%`

## Before Saving To SD

The generated G-code must satisfy all of these:

- no real startup `G28`
- contains `G92 X0 Y0 Z0` near the start
- contains a hotend target command such as `M104` / `M109`
- bed target remains `0C`
- Cura / slicer bounds are sane and fit inside the `100 x 100 mm` bed
- not `Filament used: 0m`
- preview shows supports where the model needs them

If any of these fail, re-slice from settings. Do not manually edit the G-code unless you intentionally create a new file and clearly mark it as modified.
