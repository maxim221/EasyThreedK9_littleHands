# 打印机与固件说明

## 1. 当前支持的硬件基线

当前仓库的公开说明面向：

- 打印机型号：`EasyThreeD K9`
- 主板家族：`ET4000+ / ET4000PLUS`
- 已验证的公开基线：`EasyThreeD K9` + `ET4000+ / ET4000PLUS`

重要说明：

- 这并不意味着所有 `K9` 都完全相同
- 在开发过程中，不同 `K9` 已经表现出不同的行为
- 当前最安全的公开基线使用 `LH v4`

## 2. 当前推荐固件

请使用：

- `firmware/LH-v4-YZSwap-AutoFan45-FAN1-z600-e1040-mksLite.bin`

选择它的原因：

- 固件会在 `M115` 中给出明确的 `LH` 身份
- 已验证与 `Little Hands` 兼容
- `FAN1` 在 `45C` 自动启停
- 使用接近 stock 的运动参数：
  - `X606`
  - `Y606`
  - `Z600`
  - `E1040`
- 已验证的操作者视角运动定义：
  - `X` = 喷头左右
  - `Y` = 喷头上下
  - `Z` = 平台前后

## 3. 固件识别

刷写成功后，应用应能识别出类似：

- `LH v4 YZSwap AutoFan45 FAN1 Z600 E1040`

## 4. 安全刷写流程

### 方式 A：通过 Little Hands

1. 打开 `Files & Firmware`
2. 选择：
   - `firmware/LH-v4-YZSwap-AutoFan45-FAN1-z600-e1040-mksLite.bin`
3. 上传固件到打印机 SD
4. 等待打印机完成刷写 / 重启
5. 之后从卡上删除 `mksLite.bin` 或 `mksLite.CUR`
6. 保留 `EEPROM.DAT`

![Files and Firmware window](screenshots/little-hands-files-firmware-window.png)

### 方式 B：通过读卡器

1. 把 SD 卡插入读卡器
2. 将固件复制为：
   - `mksLite.bin`
3. 把卡插回打印机
4. 通电 `30–60` 秒
5. 断电
6. 取出卡
7. 删除 `mksLite.bin` 或 `mksLite.CUR`
8. 保留 `EEPROM.DAT`
9. 再把卡放回打印机

## 5. EEPROM.DAT

`EEPROM.DAT` 很重要。

它保存打印机设置，例如：

- 运动参数
- 限制
- 偏移
- 已保存的固件设置

规则：

- 不要反复删除它
- 固件初始化后应保留在卡上
- 新刷写后应确认设置已初始化并且文件存在

### Y 平台“故障”的重要真实原因

之前那台打印机很可能不是 Y 电机或驱动通道烧坏。新的 K9 复现了同样现象：通电后平台几乎不动，但电机和通道本身仍然可用。

已确认：

- 已验证的 `LH v4` 在 `M503` 中显示正确步进比例：`M92 X606 Y606 Z600 E1040`
- 慢速 `G1 Y5 F300` 测试可以让平台双向移动
- 使用 EEPROM 中保存的激进 profile `M201 Y1000` / `M204 T1000` 做快速手动 jog 时会丢步：Marlin 认为 20 mm 已完成，但平台实际几乎没有移动

错误速度/动态的来源：

- 当前公开 `LH v4` 对应 `firmware_src/ECF-Marlin-upstream/Marlin/Configuration.h`
- 这个源码树里默认加速度是 `DEFAULT_MAX_ACCELERATION {1000,1000,100,1000}` 和 `DEFAULT_TRAVEL_ACCELERATION 1000`
- 这些值被保存进 EEPROM/设置，并会在断电重启后继续存在

当前规则：

- 计算打印速度和加速度时，把小型 X 喷头滑车和 Y 平台都当作 service-motion 限制轴
- Little Hands 对 recovery 移动保持柔和的 `M204 T80` service-idle 状态，长距离平台 service/recovery 移动约 `F240`，手动平台 jog 使用已验证的 `F600` / `M204 P80 T80`，喷头左右约 `F900`
- `5 mm` 短距离诊断移动中，平台到 `F600` 也可工作，现在 UI 会遵循已验证的手动移动上下文，而不是过度放慢移动
- Cura baseline 将 travel acceleration 保持在 `200 mm/s^2` 或更低
- 下一次重新构建固件时，应用已跟踪的补丁：`docs/firmware/LH-v4-safe-motion.patch`
- 如果平台或喷头嗡嗡响、丢步或几乎不动，先检查速度/加速度，再怀疑电机或驱动

## 6. Home 的工作方式

目前项目使用 `manual-zero`，不是真正的限位自动回零。

也就是说：

1. 操作者把打印机移动到已知的物理起始姿态
2. `Save start` 用下面的命令把它设为逻辑零点：

```gcode
G92 X0 Y0 Z0
```

3. `回到保存起点` 会在干净、可信的会话中回到这个逻辑零点

因此：

- 这是一种实用并且已经经过现场验证的工作流
- 但它还不是在任意外部移动后的绝对 home
- 如果启动失败或状态可疑，应重新建立起始姿态并重新设零
- Little Hands 现在把 home 状态分为 `trusted`、`uncertain` 和 `invalid`；除非 home 可信，或应用正在显示明确的打印后 recovery 确认流程，否则会阻止 SD 启动和 `回到保存起点`
- 更换 / 断开 USB 端口、关闭电机、硬停止、jog 失败或 recovery 失败都会清除 home 信任，因为这台机器没有物理限位开关来重新寻找绝对零点
- 普通 `Stop` 是受控停止，不是紧急路径：Little Hands 会暂停、读取 `M114`、尝试把 Z 抬到已知安全 recovery 高度，然后发送 `M524` 和关闭加热命令
- 正常 `Stop` 后，Little Hands 会尽量保存 stopped-print recovery 标记：X/Y 来自中断打印位置，Z 来自受控 post-stop 抬升（如果确认成功）；Stop 后的手动 jog 会更新该标记，而不是删除它
- 如果 `Stop` 发生在 K9 仍然 busy、没有取得 `M114` 的窗口内，Little Hands 可能提供受保护的 live-session `回到保存起点`；只有平台清空后才使用，并且只有目视确认实际起点正确后才点击 `Save start`
- 如果 USB 在真实 SD 打印期间断开，重新连接后主窗口仍显示过期的活动打印标记，`打印后返回` 可以按保存的 `LH_END_GCODE_V1` print-end 提供受保护恢复；只有确认打印已经结束、平台已清空且结束后没有手动移动各轴时才接受
- 如果 USB 断开后 CH340 打印机以新的 `/dev/ttyUSB*` 名称重新枚举，打印后 recovery 可以自动切换到唯一可见的安全 printer-like 端口；此 recovery 场景不需要手动点击 `Find`
- 如果旧的活动打印标记已经太旧，不能恢复为活动打印，Little Hands 仍会保留有效的 predicted print-end 作为受保护 recovery 选项
- 如果 SD 打印期间 USB 断开但打印正常完成，操作者可以在取下模型后点击 `Print finished`；Little Hands 会保留预测的最终位置，用于受保护的 `打印后返回`
- SD 面板有单独的 `打印后返回` 按钮；它不会执行另一套不安全的 home，而是调用与手动 `回到保存起点` 相同的受保护 recovery 流程，包括确认平台已清空
- 如果 Little Hands 重启或重新连接，并且随后检测到从日志恢复的打印已结束，它不得自动移动各轴；清空平台后需要手动恢复起点
- SD 启动必须在 `M24` 前回到已保存的 `X0 Y0 Z0`；如果 Little Hands 为热端预热抬起喷嘴而预热失败，应用会先用相同距离的相对 Z 向下移动撤销这次抬升，然后再显示错误
- 如果这个相对返回没有收到确认，Little Hands 会保留 failed-preheat-lift recovery 标记；只有操作者确认打印没有开始且各轴没有被手动移动后，`回到保存起点` 才能重试返回；成功返回后应用会立即用 `G92 X0 Y0 Z0` 重新声明已恢复的物理起点，因为断电重启后 Marlin 的逻辑 Z 可能已经过期；失败的手动 jog 不能清除这个标记，因为固件没有确认任何实际移动
- 对于 SD 上已经存在且仍包含早期阻塞 `M109` 的文件，Little Hands 不会在 `M24` 前再做一次 host-side 预热：应用会回到保存起点、选择文件并启动 SD，让 G-code 自己完成 hotend 加热等待
- 新的 Little Hands 文件不应再把早期 `M109` 改写为 `M104`；只有旧的已准备 `M104`-only 文件才需要 `M24` 前的 host-side 预热。如果使用这个 fallback，必须使用一次阻塞 `M109` 会话并被动读取温度行。不要把它改回 `M104` 加重复 `M105` 轮询；这个模式已经让这台 K9 停在接近热床温度并随后不响应。
- 如果 Marlin 显示 hotend 目标温度和正的加热输出，但第一分钟温度上升很小，应把它当作这台 K9 hotend / 传感器的 slow-start 特性：Little Hands 会记录警告并等待完整的预热超时；只有目标掉到 `/0C`、heater output 一直是 `@0` 或 `M109` 不再输出温度行时才快速中止

![Manual window](screenshots/little-hands-manual-window.png)

## 7. 外部 warm bed / hotbed

已验证的公开基线使用外部 heated bed / warm mat。

重要事实：

- 由外部加热
- 不作为“受控热床”接入打印机主板
- 固件应仍表现为“无热床控制”的打印机
- 在已验证的 Cura 基线中，热床温度保持为 `0`

已验证的实际组合：

- 外部热床约 `40–50C`
- 热床上覆盖打孔柔性打印面

## 8. Cura 基线

对于当前已验证的公开基线：

- machine: `lilHands K9 warm mat`
- profile: `codex - K9 warm mat cautious`
- brim width: `14 mm`
- PLA 温度：第一层 `225C`，之后 `224C`
- G-code 中的热床温度：`0C`，因为热床是外部供电
- `mainFlasherTop.STL` 的支撑：supports everywhere、normal supports、启用 interface / roof、support angle `35`

重要 G-code 规则：

- 不要使用启动 `G28`
- start G-code 必须使用 Little Hands 的 manual-zero `G92 X0 Y0 Z0` 流程
- 生成的文件必须包含热端目标温度命令，例如 `M104` / `M109`
- 通过当前 Little Hands 上传时，早期阻塞式 `M109` 会被保留；应用不会在 `M24` 前重复预热，加热在 SD 文件内部进行
- 只有旧的已准备 `M104`-only 文件会使用 fallback：应用在 SD 启动前用 host-side `M109` 预热热端
- 上传前可以使用 `Check G-code`；同一套校验也会在 `Upload G-code` 和 `Upload & start` 前自动运行
- 如果文件出现 `Filament used: 0m`、不可能的 bounds、超出 `100 x 100 x 100 mm`、热床加热 `M140/M190 S>0`、`M18/M84`、缺少热端目标温度，或 body `M204` 过激，请重新切片
- anti-warp 配置调整后，`14 mm` brim 现在是默认值；旧的启动失败与加热 / SD 启动顺序有关，不是 brim 宽度本身造成的

当前 end-gcode 规则：

- 使用 raw Marlin `G1 Y95 F240` 展示完成的模型；在验证过的机器上它会柔和地把平台推向操作者
- 不要在 Cura end-gcode 里加入 `M84`；`Little Hands` 会在恢复移动和 SD 打印开始前主动启用步进电机
- 如果旧文件以 `G1 Y0` 或 `M84` 结尾，请先重新切片，再判断打印完成动作是否正确

需要重新切片的情况：

- 固件基线改变
- 轴映射改变
- 文件是为另一台机器生成的

在应用中，使用 `Export Cura profile` 将当前验证过的 Cura 配置包复制到 `exports/`。
公开固定的参考副本位于 `docs/cura/`。
如果使用其他切片器版本，请按 `docs/cura/SETTINGS.zh.md` 手动配置。

## 9. 首次安全打印流程

1. 刷写 `LH v4`
2. 确认 tiny jog 映射正确
3. 确认外部热床已经预热
4. 在已验证的 Cura 机器/配置中切片
5. 上传 G-code
6. 设定物理起始姿态
7. 点击 `Save start`
8. 点击 `回到保存起点` 并确认它确实返回正确位置
9. 从 SD 启动打印。不需要手动预热热端。如果所选 SD 文件包含自己的早期 `M109`，Little Hands 会回到保存起点，发送 `M23`/`M24`，加热等待在 G-code 内部完成。
10. 如果文件是通过当前 Little Hands 上传或由内置 helper 导出的，早期 `M109` 会保留在 SD 文件中；这是正常路径。旧的 `M104`-only 准备文件最好重新生成，但应用仍可通过 host-side fallback 为它们预热。
11. 发送 `M24` 后，Little Hands 会让 USB 完全安静 `180` 秒。这是预期行为，有助于这台 K9 稳定进入 SD 打印。
12. 对旧 G-code 中残留的 `M109`，固件可能不会响应普通的 `M105` / `M27`；Little Hands 会先被动监听 `M109` 的温度行，避免向队列塞入额外命令。
13. 如果 `M24` 后约 `5` 分钟内没有温度行、没有 SD 进度，而且实际没有加热、风扇和运动，应用会把这次启动标记为未确认，并提示断电重启恢复。

## 10. 两次打印之间

一次 SD 打印成功结束后，下一次启动前请按这个顺序操作：

1. 从平台上取下模型。
2. 在已保存零点仍然有效时点击 `回到保存起点`。
3. 关闭打印机电源 `5–10` 秒，然后重新打开。
4. 确认打印机仍在起始位置。
5. 点击 `Save start`。
6. 开始下一次 SD 打印。

打印完成后，应用会阻止重复 SD 启动，直到这个恢复流程被确认。

## 11. 恢复规则

如果打印启动失败并看到：

- 咔哒声
- 没有运动
- 遥测冻结
- 状态过期
- `device reports readiness to read but returned no data`

目前最安全的流程是：

1. 停止打印
2. 重启打印机电源
3. 重新确认起始位置
4. 点击 `Save start`
5. 再次启动

重要细节：USB 遥测沉默本身不足以证明打印失败。如果热端正在升温、打印机在运动或已经出料，不要断电；请目视观察打印，并让 Little Hands 等待 USB 恢复。

对于卡住的启动，Little Hands 会先发送 `M108`，再发送 `M524`，让 Marlin 可以退出阻塞的 `M109` 加热等待，然后关闭加热和风扇。
