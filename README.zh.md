# Little Hands for EasyThreeD K9

Little Hands 是一个面向 Linux 的桌面控制中心，针对的是一个非常具体的 3D 打印机配置：

- 打印机：`EasyThreeD K9`
- 主板家族：`ET4000+ / ET4000PLUS`
- 当前验证通过的固件：`LH-v4-YZSwap-AutoFan45-FAN1-z600-e1040-mksLite.bin`
- 切片器基线：`Cura 5.11`
- 热床基线：外部 warm mat / hotbed，不直接连接到打印机主板

这个项目还不算完全打磨完成，但已经能够实际打印。

- USB/SD 控制可用
- 固件刷写可用
- manual-zero 工作流可用
- 日志可用
- Cura 导出可用
- 温度与打印进度监控可用

还比较粗糙的地方：

- 这不是适用于所有 `K9` 变种的通用包
- 还没有真正基于限位开关的自动回零
- 如果打印启动失败，目前最稳妥的恢复方式仍然是打印机断电重启
- Windows 打包还只是计划
- 程序界面现在主要仍然偏俄语，但文档已经提供三种语言

## 截图

![Little Hands main window](docs/screenshots/little-hands-main-window.png)

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

当前公开基线是“受保护的第二台 `K9`”。

- 已验证打印机：`EasyThreeD K9`
- 已验证主板家族：`ET4000+ / ET4000PLUS`
- 已验证固件：`LH-v4-YZSwap-AutoFan45-FAN1-z600-e1040-mksLite.bin`
- 已验证应用：`tools/k9_control_center.py`
- 已验证 Cura 机器：`lilHands K9 warm mat`
- 已验证 Cura 配置：`codex - K9 warm mat cautious`

不要假设任意一台 `K9` 都能直接照搬这个配置。

## Home 的工作方式

这里不使用标准的 Marlin `G28` 限位回零。

Little Hands 使用的是 manual-zero 工作流：

1. 把打印机移动到已知的打印起始姿态。
2. 点击 `Запомнить старт`。
3. 程序向打印机发送 `G92 X0 Y0 Z0`。
4. `К старту` 会在当前干净会话中返回这个逻辑零点。

也就是说：

- 这是一种实用的操作员工作流，不是真正的传感器自动回零
- 如果打印启动失败，最稳妥的下一步通常是：
  - 打印机断电重启
  - 重新检查起始姿态
  - 再次点击 `Запомнить старт`

## 外部热床说明

已验证的第二台打印机使用外部 warm mat / hotbed：

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

## 推荐固件

- [`firmware/LH-v4-YZSwap-AutoFan45-FAN1-z600-e1040-mksLite.bin`](firmware/LH-v4-YZSwap-AutoFan45-FAN1-z600-e1040-mksLite.bin)

