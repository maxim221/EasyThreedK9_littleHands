# Little Hands for EasyThreeD K9

Little Hands 是一个面向 Linux 的桌面控制中心，针对的是一个非常具体的 3D 打印机配置：

- 打印机：`EasyThreeD K9`
- 主板家族：`ET4000+ / ET4000PLUS`
- 当前候选固件：`LH-v5-YZSwap-AutoFan45-FAN1-z600-e1040-watch180-mksLite.bin`
- 切片器基线：`Cura 5.11`
- 热床基线：外部 warm mat / hotbed，不直接连接到打印机主板

这个项目还不算完全打磨完成，但已经能够实际打印。

- USB/SD 控制可用
- 固件刷写可用
- manual-zero 工作流可用
- 日志可用
- Cura 导出可用
- 上传前的 G-code 校验可以拦截危险或明显损坏的文件
- 温度与打印进度监控可用

还比较粗糙的地方：

- 这不是适用于所有 `K9` 变种的通用包
- 还没有真正基于限位开关的自动回零
- 如果确实启动失败，并且没有加热 / 没有运动，目前最稳妥的恢复方式仍然是打印机断电重启
- Windows 打包还只是计划
- 程序界面支持 RU / EN / ZH 切换；主要控制项和较新的系统日志事件已经本地化，而固件原始回复会保持打印机返回的内容

## 联系方式

- Telegram: [@NeuroMaxim](https://t.me/NeuroMaxim)
- Bug 和功能建议：[GitHub Issues](https://github.com/maxim221/EasyThreedK9_littleHands/issues)

## 截图

下面的截图使用英文界面。主窗口现在左侧是 manual control，USB metrics 位于其下方，journal 固定显示在右侧。

![Little Hands main window](docs/screenshots/little-hands-main-window.png)

![Files and Firmware window](docs/screenshots/little-hands-files-firmware-window.png)

![Manual window](docs/screenshots/little-hands-manual-window.png)

## 文档语言

- English:
  - [README.md](README.md)
  - [Linux setup](docs/INSTALL_LINUX.md)
  - [Printer and firmware guide](docs/PRINTER_AND_FIRMWARE.md)
- Русский:
  - [README.ru.md](README.ru.md)
  - [Установка на Linux / Raspberry Pi](docs/INSTALL_LINUX.ru.md)
  - [Принтер и прошивка](docs/PRINTER_AND_FIRMWARE.ru.md)
- 中文:
  - [README.zh.md](README.zh.md)
  - [Linux / Raspberry Pi 安装](docs/INSTALL_LINUX.zh.md)
  - [打印机与固件说明](docs/PRINTER_AND_FIRMWARE.zh.md)

## 当前支持的配置

当前公开基线是一套经过验证的 `EasyThreeD K9` 配置：

- 已验证打印机：`EasyThreeD K9`
- 已验证主板家族：`ET4000+ / ET4000PLUS`
- 测试基线固件：`LH-v5-YZSwap-AutoFan45-FAN1-z600-e1040-watch180-mksLite.bin`
- 已验证应用：`tools/k9_control_center.py`
- 已验证 Cura 机器：`lilHands K9 warm mat`
- 已验证 Cura 配置：`codex - K9 warm mat cautious`

不要假设任意一台 `K9` 都能直接照搬这个配置。
不同 `K9` 机器在开发过程中已经表现出差异。

## Home 的工作方式

这里不使用标准的 Marlin `G28` 限位回零。

Little Hands 使用的是 manual-zero 工作流：

1. 把打印机移动到已知的打印起始姿态。
2. 点击 `Save start`。
3. 程序向打印机发送 `G92 X0 Y0 Z0`。
4. `回到保存起点` 会在当前干净会话中返回这个逻辑零点。

也就是说：

- 这是一种实用的操作员工作流，不是真正的传感器自动回零
- 如果打印启动失败，最稳妥的下一步通常是：
  - 打印机断电重启
  - 重新检查起始姿态
  - 再次点击 `Save start`
- 如果 hotend 预热在自动抬 Z 后失败，`回到保存起点` 可以提供受保护重试：按同一个已知 preheat lift 把 Z 降回去；只有打印没有开始且各轴没有被手动移动时才确认
- 如果热端正在升温、打印机在运动或已经出料，不要仅仅因为 USB 遥测沉默就断电
- 正常打印完成后，SD 面板的 `打印后返回` 按钮会调用与 `回到保存起点` 相同的受保护 recovery 流程，并要求平台已清空
- 在 `M24` 前，Little Hands 会用分段 `M104` 目标和最后的阻塞 `M109` 自己确认 hotend 加热；如果加热没有确认，就不会启动 SD 打印

## 当前现场观察

当前工作基线故意比较保守。如果真实打印能够稳定开始和完成，不要只因为它看起来慢就急着“优化”。

- Hotend 预热初期可能很慢，并伴随轻微咔哒声，随后温度会快速上升。这是当前验证 K9 的已知观察。需要观察，但只要分段温度门槛能通过、目标不丢失、heater output 没有一直停在 `@0`，且没有电气异味/过热等危险信号，就不要仅为消除轻微声音而改固件或预热时序。
- 打印后喷头左右轴可能会机械性卡住。如果打印后返回没有完成水平移动，但几次短的 `head left` jog 能让它恢复并正常运动，应先按机械摩擦处理，不要提高 service speed 或加入更强的 recovery 移动。
- 如果任何 return-to-start 移动没有实际完成，在平台清空、轴重新顺畅、喷嘴目视回到正确起点前，不要点击 `Save start`。

## 外部热床说明

已验证的公开基线使用外部 warm mat / hotbed：

- 由独立外部供电加热
- 不由打印机固件直接控制
- 打印机仍然应该表现为“无加热床控制”
- 已验证的工作温度大约为 `40–50C`

## 快速开始

1. 安装 Linux 依赖：
   - [docs/INSTALL_LINUX.zh.md](docs/INSTALL_LINUX.zh.md)
2. 阅读打印机与固件说明：
   - [docs/PRINTER_AND_FIRMWARE.zh.md](docs/PRINTER_AND_FIRMWARE.zh.md)
3. 启动程序：

```bash
python3 tools/k9_control_center.py
```

4. 在 Cura 中选择：
   - machine: `lilHands K9 warm mat`
   - profile: `codex - K9 warm mat cautious`
   - brim: `14 mm`
   - Cura 偏好设置：`Add machine prefix to job name` = `off`
   - `mainFlasherTop.STL` 支撑：everywhere，启用 interface / roof，support angle `35`

公开固定的 Cura 基线副本位于 [docs/cura/](docs/cura/)。
其他切片器版本的手动设置说明：[docs/cura/SETTINGS.zh.md](docs/cura/SETTINGS.zh.md)。

## 推荐固件

- [`firmware/LH-v5-YZSwap-AutoFan45-FAN1-z600-e1040-watch180-mksLite.bin`](firmware/LH-v5-YZSwap-AutoFan45-FAN1-z600-e1040-watch180-mksLite.bin)
