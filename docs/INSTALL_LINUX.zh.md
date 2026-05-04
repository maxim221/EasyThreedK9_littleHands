# Linux / Raspberry Pi 安装

本说明适用于：

- Linux 桌面系统
- Raspberry Pi OS Desktop
- 其他支持 `tkinter` 和 `pyserial` 的 Debian 系系统

## 1. 所需组件

- Python `3`
- `tkinter`
- `pyserial`
- 用于完成提示音的音频播放
- 对 USB 串口的访问权限

## 2. 系统包

在 Debian / Ubuntu / Raspberry Pi OS 上：

```bash
sudo apt update
sudo apt install -y \
  git \
  python3 \
  python3-tk \
  python3-serial \
  pulseaudio-utils
```

可选但有帮助：

```bash
sudo apt install -y python3-pil wmctrl gnome-screenshot
```

## 3. 克隆仓库

```bash
git clone <YOUR-REPO-URL>
cd littleHands
```

如果你不想通过系统包安装 `python3-serial`，也可以：

```bash
python3 -m pip install -r requirements.txt
```

## 4. 串口权限

把当前用户加入 `dialout`：

```bash
sudo usermod -aG dialout "$USER"
```

然后重新登录桌面会话。

## 5. 启动应用

在仓库根目录执行：

```bash
python3 tools/k9_control_center.py
```

如果一切正常，你会看到 `Little Hands` 窗口。

## 6. 可选桌面启动器

仓库中已经带有：

- `Little Hands Control Center.desktop`

安装到当前用户桌面环境：

```bash
mkdir -p ~/.local/share/applications
cp "Little Hands Control Center.desktop" ~/.local/share/applications/little-hands-control-center.desktop
update-desktop-database ~/.local/share/applications 2>/dev/null || true
```

## 7. 运行时文件

Little Hands 会写入：

- `monitor_logs/little_hands_runtime.log`
- `monitor_logs/little_hands_ui_state.json`
- `monitor_logs/gui_exports/`

其中 runtime log 是 `10 MiB` 上限的环形日志。

## 8. Cura 基线

使用：

- machine: `lilHands K9 warm mat`
- profile: `codex - K9 warm mat cautious`

## 9. 打印机找不到时

这个项目主要针对通常显示为 `CH340` 的 `K9`。

如果找不到打印机：

- 给打印机断电重启
- 直接重新连接 USB
- 重新打开 `Little Hands`
- 点击 `Find`

如果打印启动失败并且只听到点击声或遥测冻结，目前最稳妥的流程是：

1. `Hard stop`
2. 打印机断电重启
3. 重新检查起始姿态
4. 点击 `Save start`
5. 再次启动
