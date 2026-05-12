# 手动 Cura / 切片器设置

如果无法导入随附的 Cura 配置，或使用其他 Cura / 切片器版本，请使用本文档手动设置。

这些是当前验证过的 EasyThreeD K9 / Little Hands 基线设置。它们偏保守：慢速 PLA、外部 warm bed、manual-zero start、不使用固件控制热床。

## 机器

- 打印机名称：`lilHands K9 warm mat`
- 打印区域：`100 x 100 x 100 mm`
- Origin at center：`off`
- 固件热床控制：`off`
- G-code flavor：`RepRap (RepRap)`，或最接近的 Marlin / RepRap-style 模式
- 耗材直径：`1.75 mm`
- 喷嘴直径：使用实际安装的喷嘴；已验证配置没有覆盖 Cura 的 nozzle diameter

## Start G-code

使用这种 start G-code。不要添加 `G28`。

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

这里使用的是 raw Marlin 轴，不是 UI 中面向操作者的文字说明。在已验证的 K9 上，它会抬起喷头并把平台推向操作者。

```gcode
M104 S0 ;Hotend off
M140 S0 ;Bed off in G-code even though bed is external
G91
G1 E-1 F1800
G1 Z10 F1200
G90
M204 P250 T120 ;Gentle final presentation moves for the small Y-bed
G1 X95 F1800
G1 Y95 F600 ;Move bed toward the operator
```

不要在结尾添加 `M84`。Little Hands 需要让步进电机保持可用，以便完成打印后的恢复流程。

## 材料和温度

- 材料：PLA
- 第一层热端：`225C`
- 后续热端：`224C`
- G-code 中的热床温度：`0C`
- 实际外部 warm mat / hotbed：手动预热到约 `40-50C`
- Cura part cooling：`off`
- 重要：当前 K9 只有一个物理风扇，它作为 firmware-managed hotend fan 使用。Little Hands / helper 会移除 slicer 的 `M106/M107`，避免 Cura 把这个风扇当作模型冷却风扇控制。
- Minimum layer time：`10 s`

## 质量

- Layer height：`0.16 mm`
- Initial layer height：`0.20 mm`
- Wall line count：`5`
- Top layers：`6`
- Bottom layers：`6`
- Infill density：`20%`
- Infill pattern：`lines`
- Print infill before walls：`off`
- Flow：`103%`
- Wall flow：`103%`
- Outer wall flow：`102%`
- Top / bottom flow：`102%`
- Infill flow：`101%`
- Top / bottom pattern：`lines`
- Initial bottom pattern：`concentric`
- Ironing / 熨平：`on`
- Iron only highest layer：`on`
- Ironing pattern：`concentric`
- Ironing line spacing：`0.12 mm`
- Ironing flow：`7%`
- Z seam alignment：`Random`

## 速度

- Print speed：`15 mm/s`
- Wall speed：`12 mm/s`
- Top / bottom speed：`11 mm/s`
- Infill speed：`15 mm/s`
- Travel speed：`35 mm/s`
- Initial layer speed：`6 mm/s`
- Ironing speed：`8 mm/s`

## 运动平滑

这些限制对小型 K9 机械结构更温和，有助于减少 diagonal moves 上的 ringing / rattling。

- Acceleration control：`on`
- Print acceleration：`250 mm/s^2`
- Wall acceleration：`180 mm/s^2`
- Outer wall acceleration：`150 mm/s^2`
- Inner wall acceleration：`200 mm/s^2`
- Top / bottom acceleration：`180 mm/s^2`
- Infill acceleration：`250 mm/s^2`
- Support acceleration：`220 mm/s^2`
- Support interface / roof acceleration：`160 mm/s^2`
- Initial layer and skirt / brim acceleration：`150 mm/s^2`
- Travel acceleration：`200 mm/s^2`
- Ironing acceleration：`120 mm/s^2`
- Jerk control：`off`
- 注意：暂时不要为这个 RepRap-flavor 配置启用 Cura jerk control；我们的 Marlin 固件使用 `M205`，而 Cura 在此模式下会生成 `M566`。
- Y 平台限制：当前验证的 `LH-v4` 在 EEPROM/Marlin 中保存了 `M201 Y1000` 和 `M204 T1000`，这对小平台的手动和维护移动过于激进。打印时把 travel acceleration 保持在 `200 mm/s^2` 或更低；Little Hands 对维护移动会临时降到 `M204 T80`。

## 平台附着

- Build plate adhesion：`brim`
- Brim width：`12 mm`

如果四角仍然翘起，请先检查平台清洁、外部热床预热和首层压实；然后可以临时尝试 `14 mm` brim。`18 mm` 作为救急设置保留，因为它会明显增加占地和打印时间。

对于同一个物理角上反复出现的裂纹，请在打印机旁边放置实体挡风墙。默认不要启用 Cura Draft Shield：实体挡风墙更简单，也不会在 G-code 中增加额外打印塑料。

## 支撑

对于 `mainFlasherTop.STL` 和类似有较多悬垂的模型：

- Generate support：`on`
- Support placement：`everywhere`
- Support overhang angle：`35 deg`
- Support structure：`normal`
- Support pattern：`zigzag`
- Support density：`10%`
- Support interface：`on`
- Support roof：`on`
- Support interface density：`65%`
- Support roof density：`65%`
- Support interface height：`0.48 mm`
- Support roof height：`0.48 mm`
- Support Z distance：`0.16 mm`
- Support top distance：`0.16 mm`
- Support XY distance：`0.3 mm`

如果支撑太难拆，先使用这些 `easy-release` 数值。暂时保持 Z distance 为 `0.16 mm`，以保护底面质量。如果仍然难拆，下一次单独测试再把 Support Z distance / top distance 提高到 `0.24-0.32 mm`。

如果 preview 没有在问题底面下方显示支撑，不要打印。调整 support placement / threshold，直到 preview 中确实出现所需支撑。

## 回抽和桥接

- Retraction：`on`
- Retraction distance：`6.5 mm`
- Retraction speed：`25 mm/s`
- Prime speed：`25 mm/s`
- Bridge settings：`on`
- Bridge fan speed：`0%`
- Bridge skin speed：`10 mm/s`
- Bridge wall speed：`10 mm/s`
- Bridge skin flow：`90%`
- Bridge wall flow：`90%`
- Initial layer line width：约 `150%`

## 写入 SD 前检查

生成的 G-code 必须满足：

- 没有真正的启动 `G28`
- 开头附近包含 `G92 X0 Y0 Z0`
- 包含热端目标温度命令，例如 `M104` / `M109`
- 如果文件通过 Little Hands 上传或由 slicing helper 生成，早期 `M109` 会改写为 `M104`，热端会在 SD 启动前预热
- bed target 保持 `0C`
- slicer bounds 正常，并位于 `100 x 100 mm` 平台内
- 高度位于 `100 mm` 内
- 不出现 `Filament used: 0m`
- 没有 `M18/M84`、没有热床加热 `M140/M190 S>0`，body `M204` 不超过安全的 K9 baseline
- preview 中在模型需要的位置显示支撑

如果有任何一项不满足，请重新切片。不要手工修改 G-code，除非你有意创建一个新文件，并明确标记为 modified。
