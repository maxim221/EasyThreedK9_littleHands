# 手动 Cura / 切片器设置

如果无法导入随附的 Cura 配置，或使用其他 Cura / 切片器版本，请使用本文档手动设置。

这些是当前验证过的 EasyThreeD K9 / Little Hands 基线设置。它们偏保守：慢速 PLA、manual-zero start，受控 hotbed 只通过明确的 Little Hands 标记启用。

## 机器

- 打印机名称：`lilHands K9 warm mat`
- Cura active machine id：`lilHands_k9_warmmat`
- 打印区域：`100 x 100 x 100 mm`
- Origin at center：`off`
- 标准 Cura 热床温度：`0C`；受控 hotbed 只由下面的 start G-code 标记请求
- G-code flavor：`RepRap (RepRap)`，或最接近的 Marlin / RepRap-style 模式
- 耗材直径：`1.75 mm`
- 喷嘴直径：使用实际安装的喷嘴；已验证配置没有覆盖 Cura 的 nozzle diameter
- Cura 偏好设置：关闭 `Preferences -> General -> Add machine prefix to job name`。在 `cura.cfg` 中对应 `[cura] jobname_prefix = False`。这样 Cura 不会在导出的 G-code 文件名前添加无用的 `CFFFP_`。
- Cura active-machine 设置：`~/.config/cura/5.11/cura.cfg` 中的 `[cura] active_machine` 必须是 `lilHands_k9_warmmat`。如果还是旧的 `lilHands`，Cura 可能保存一个看起来正常、但没有 `;LH_EXPERIMENTAL_HOTBED_TARGET:35` 标记的文件，受控热床就不会加热。

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
;LH_EXPERIMENTAL_HOTBED_TARGET:35
M140 S35 ;Experimental controlled hotbed target; Little Hands preheats before M24
```

## End G-code

这里使用的是 raw Marlin 轴，不是 UI 中面向操作者的文字说明。在已验证的 K9 上，它会抬起喷头并把平台推向操作者。

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

不要在结尾添加 `M84`。Little Hands 需要让步进电机保持可用，以便完成打印后的恢复流程。

## 材料和温度

- 材料：PLA
- 第一层热端：`225C`
- 后续热端：`224C`
- Cura material bed temperature：`0C`
- 受控 hotbed start 目标：`35C`，只通过 `;LH_EXPERIMENTAL_HOTBED_TARGET:35` 和非阻塞 `M140 S35` 输出
- 外部 warm mat 备用方案：手动预热到约 `40-50C`
- Cura part cooling：`off`
- 重要：当前 K9 只有一个物理风扇，它作为 firmware-managed hotend fan 使用。Little Hands / helper 会移除 slicer 的 `M106/M107`，避免 Cura 把这个风扇当作模型冷却风扇控制。
- Minimum layer time：`10 s`

## 质量

- Layer height：`0.16 mm`
- Initial layer height：`0.20 mm`
- Wall line count：`5`
- Top layers：`7`
- Bottom layers：`7`
- Infill density：`20%`
- Infill pattern：`lines`
- Print infill before walls：`off`
- Flow：`103%`
- Wall flow：`103%`
- Outer wall flow：`102%`
- Top / bottom flow：`104%`
- Infill flow：`101%`
- Initial layer flow：`103%`
- Skin overlap：`10%`
- Top / bottom pattern：`lines`
- Initial bottom pattern：`concentric`
- Ironing / 熨平：`on`
- Iron only highest layer：`on`
- Ironing pattern：`concentric`
- Ironing line spacing：`0.12 mm`
- Ironing flow：`7%`
- Z seam alignment：`Random`

## 速度

- Print speed：`11 mm/s`
- Wall speed：`8 mm/s`
- Top / bottom speed：`8 mm/s`
- Infill speed：`11 mm/s`
- Travel speed：`25 mm/s`
- Initial layer speed：`6 mm/s`
- Skirt / brim speed：`21 mm/s`
- Support speed：`11 mm/s`
- Support interface / roof speed：`8 mm/s`
- Ironing speed：`6 mm/s`

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
- K9 维护移动限制：当前验证的 `LH-v5` baseline 仍可能在 EEPROM/Marlin 中带有类似 `M201 X1000 Y1000` 和 `M204 T1000` 的 service dynamics，这对小型机械结构的手动和 recovery 移动过于激进。打印时把 travel acceleration 保持在 `200 mm/s^2` 或更低；Little Hands 对长距离 service / recovery 平台移动保持柔和的 `M204 T80` service-idle 状态并使用约 `F240`，手动平台 jog 使用已验证的 `F600` / `M204 P80 T80`，喷头左右 service/recovery 约 `F900`，手动喷头左右 jog 使用更柔和的 one-move `F600` / `M204 P80 T80` 诊断上下文。手动 X jog 会先声明本地中性 `G92 X50`，避免跳步后过期的负 X 坐标继续累积。
- 手动 X jog 的确认不再被视为 X 物理移动的证明；如果喷头卡住，请目视检查滑车，并在打印前重新保存起点。
- 不要通过提高 Cura travel speed 或 recovery speed 来补偿打印后喷头左右滑车的机械卡滞。先释放 / 检查该轴；如果几次短 jog 后恢复正常运动，应按现场机械问题处理，而不是修改切片速度目标。

## 平台附着

- Build plate adhesion：`brim`
- Brim width：`14 mm`

如果四角仍然翘起，请先检查平台清洁、外部热床预热和首层压实；然后可以临时尝试 `16 mm` brim。`18 mm` 作为救急设置保留，因为它会明显增加占地和打印时间。

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

## 模型方向检查

对于 `moduleBot.STL`，在 Cura Preview 确认方向之前，不要直接打印新的切片。在 2026-05 测试中，直接切片原始 `moduleBot.STL` 曾生成一个倒置且支撑很多的文件。

这个模型的实用检查方法：已验证方向通常约为 `9-11 m` 耗材。如果小型 `moduleBot` 切片突然显示约 `20 m+` 耗材，或出现大量支撑，请不要写入 SD；先在 Preview 中重新检查方向并重新切片。

## 回抽和桥接

- Retraction：`on`
- Retraction distance：`6.5 mm`
- Retraction speed：`25 mm/s`
- Prime speed：`25 mm/s`
- Bridge settings：`on`
- Bridge fan speed：`0%`
- Bridge skin speed：`7 mm/s`
- Bridge wall speed：`7 mm/s`
- Bridge skin flow：`100%`
- Bridge wall flow：`100%`
- Initial layer line width：约 `155%`

## 写入 SD 前检查

生成的 G-code 必须满足：

- 没有真正的启动 `G28`
- 开头附近包含 `G92 X0 Y0 Z0`
- 包含热端目标温度命令，例如 `M104` / `M109`
- 早期阻塞 `M109` 应保留在 SD 文件中；Little Hands 仍会在 `M24` 前用分段 host-side 预热和最终 `M109` 确认 hotend 已加热，文件中的 `M109` 作为额外安全等待保留
- 旧的已准备 `M104`-only 文件也由同一个 `M24` 前分段 host preheat 支持
- Cura material bed target 保持 `0C`；受控 hotbed 文件必须明确带有 `;LH_EXPERIMENTAL_HOTBED_TARGET:35` 标记，并且只使用非阻塞 `M140 S35`
- slicer bounds 正常，并位于 `100 x 100 mm` 平台内
- 高度位于 `100 mm` 内
- 不出现 `Filament used: 0m`
- 没有 `M18/M84`、没有阻塞式 `M190`、没有未标记的热床加热 `M140/M190 S>0`，body `M204` 不超过安全的 K9 baseline
- preview 中在模型需要的位置显示支撑
- 导出的文件名不应以 `CFFFP_` 开头；如果出现该前缀，请关闭 Cura 的 `Add machine prefix to job name` 后重新保存
- 新的 Cura export 开头应包含 `; Little Hands manual-zero workflow for EasyThreed K9 / K9 Plus`，使用 `G1 Z10.0 F600`，并包含 `;LH_EXPERIMENTAL_HOTBED_TARGET:35`；如果开头还是旧的短版 `; Little Hands manual-zero workflow` 和 `G1 Z10.0 F1800`，请把 Cura 切回 `lilHands K9 warm mat` 后重新保存

如果有任何一项不满足，请重新切片。不要手工修改 G-code，除非你有意创建一个新文件，并明确标记为 modified。
