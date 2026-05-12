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

- 计算打印速度和加速度时，把 Y 平台当作限制轴
- Little Hands 对手动 / service moves 临时降到 `M204 T80`，平台速度约 `F600`
- Cura baseline 将 travel acceleration 保持在 `200 mm/s^2` 或更低
- 下一次重新构建固件时，应用已跟踪的补丁：`docs/firmware/LH-v4-safe-motion.patch`
- 如果平台嗡嗡响或几乎不动，先检查速度/加速度，再怀疑电机或驱动

## 6. Home 的工作方式

目前项目使用 `manual-zero`，不是真正的限位自动回零。

也就是说：

1. 操作者把打印机移动到已知的物理起始姿态
2. `Save start` 用下面的命令把它设为逻辑零点：

```gcode
G92 X0 Y0 Z0
```

3. `Go to start` 会在干净、可信的会话中回到这个逻辑零点

因此：

- 这是一种实用并且已经经过现场验证的工作流
- 但它还不是在任意外部移动后的绝对 home
- 如果启动失败或状态可疑，应重新建立起始姿态并重新设零

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
- brim width: `12 mm`
- PLA 温度：第一层 `225C`，之后 `224C`
- G-code 中的热床温度：`0C`，因为热床是外部供电
- `mainFlasherTop.STL` 的支撑：supports everywhere、normal supports、启用 interface / roof、support angle `35`

重要 G-code 规则：

- 不要使用启动 `G28`
- start G-code 必须使用 Little Hands 的 manual-zero `G92 X0 Y0 Z0` 流程
- 生成的文件必须包含热端目标温度命令，例如 `M104` / `M109`
- 通过 Little Hands 上传时，早期阻塞式 `M109` 会自动改写为 `M104`；应用会在 SD 启动前预热热端
- 如果文件出现 `Filament used: 0m`、不可能的 Cura bounds，或缺少热端目标温度，请重新切片
- 自动热端预热流程确认后，`12 mm` brim 现在是默认值；旧的启动失败与加热 / SD 启动顺序有关，不是 brim 宽度本身造成的

当前 end-gcode 规则：

- 使用 raw Marlin `G1 Y95` 展示完成的模型；在验证过的机器上它会把平台推向操作者
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
8. 点击 `Go to start` 并确认它确实返回正确位置
9. 从 SD 启动打印。不需要手动预热热端：发送 `M24` 前，Little Hands 会把热端预热到 G-code 中的目标温度，然后发送 `M23`，等待 `File selected` 确认，再发送 `M24`。
10. 如果文件是通过 Little Hands 上传或由内置 helper 导出的，早期 `M109` 已改写为 `M104`，避免 SD 启动卡在阻塞式加热等待中。
11. 发送 `M24` 后，Little Hands 会让 USB 完全安静 `180` 秒。这是预期行为，有助于这台 K9 稳定进入 SD 打印。
12. 对旧 G-code 中残留的 `M109`，固件可能不会响应普通的 `M105` / `M27`；Little Hands 会先被动监听 `M109` 的温度行，避免向队列塞入额外命令。
13. 如果 `M24` 后约 `5` 分钟内没有温度行、没有 SD 进度，而且实际没有加热、风扇和运动，应用会把这次启动标记为未确认，并提示断电重启恢复。

## 10. 两次打印之间

一次 SD 打印成功结束后，下一次启动前请按这个顺序操作：

1. 从平台上取下模型。
2. 在已保存零点仍然有效时点击 `Go to start`。
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
