#!/usr/bin/env python3
"""
Local GUI control center for the EasyThreeD K9 / ET-4000+.

Features:
- upload G-code to the printer SD over USB
- upload firmware to the printer SD over USB and trigger M997
- browse, start, pause, resume, stop, and delete SD files
- live temperature / SD status polling
- home, disable motors, and jog X/Y/Z
- bed-leveling helper points for the unusual X/Z bed plane layout
"""

from __future__ import annotations

import queue
import re
import shutil
import threading
import time
import subprocess
import json
import math
from pathlib import Path
import textwrap
import tkinter as tk
import tkinter.font as tkfont
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText

import k9_marlin_sd as sdtool


PROJECT_ROOT = Path("/home/maxim/draftCode/littleHands")
CURA_ROOT = Path.home() / ".local/share/cura/5.11"
DEFAULT_FIRMWARE = PROJECT_ROOT / "firmware/LH-v4-YZSwap-AutoFan45-FAN1-z600-e1040-mksLite.bin"
LOG_DIR = PROJECT_ROOT / "monitor_logs"
GUI_EXPORT_DIR = LOG_DIR / "gui_exports"
RUNTIME_LOG_PATH = LOG_DIR / "little_hands_runtime.log"
RUNTIME_LOG_MAX_BYTES = 10 * 1024 * 1024
UI_STATE_PATH = LOG_DIR / "little_hands_ui_state.json"
PRINT_STATE_PATH = LOG_DIR / "little_hands_print_state.json"
TEMP_GRAPH_WINDOW_SEC = 15 * 60
TEMP_GRAPH_SCALE_RECENT_SEC = 3 * 60
TEMP_LOG_INTERVAL_SEC = 5.0
AUTO_SD_REFRESH_DELAY_MS = 3500
AUTO_SD_REFRESH_REQUIRE_FRESH_TEMP_SEC = 12.0
PRINT_START_GRACE_SEC = 5 * 60
PRINT_START_RECENT_TEMP_CONFIRM_SEC = 90.0
POST_M24_USB_QUIET_SEC = 180
PRINT_ACTIVE_CONFIRM_SAMPLES = 2
PRINT_ACTIVE_CONFIRM_MIN_SEC = 45
USB_SILENCE_LOG_INTERVAL_SEC = 30.0
PRINT_STATE_SAVE_INTERVAL_SEC = 5.0
PRINT_STATE_MAX_AGE_SEC = 48 * 60 * 60
PRINT_STATE_ACTIVE_RESTORE_MAX_AGE_SEC = 30 * 60
PRINT_END_CONTRACT = "LH_END_GCODE_V1"
PRINT_END_MAX_Z = 100.0
DEFAULT_PRINT_HOTEND_TARGET_C = 218.0
PRINT_PREHEAT_BLOCKING_M109_EXTRA_C = 7.0
PRINT_PREHEAT_MARGIN_C = 2.0
PRINT_PREHEAT_TIMEOUT_SEC = 240.0
PRINT_PREHEAT_POLL_SEC = 3.0
PRINT_PREHEAT_TARGET_GRACE_SEC = 25.0
PRINT_PREHEAT_HEATER_ZERO_GRACE_SEC = 45.0
PRINT_PREHEAT_NO_RISE_GRACE_SEC = 120.0
PRINT_PREHEAT_MIN_RISE_C = 4.0
K9_PRINT_BED_SIZE_MM = 100.0
K9_MAX_PRINT_Z_MM = 100.0
K9_GCODE_BOUNDS_TOLERANCE_MM = 0.2
K9_HOTEND_MIN_TARGET_C = 150.0
K9_HOTEND_WARN_LOW_C = 185.0
K9_HOTEND_WARN_HIGH_C = 240.0
K9_HOTEND_MAX_TARGET_C = 260.0
K9_WARN_TRAVEL_ACCEL = 250.0
K9_MAX_BODY_TRAVEL_ACCEL = 600.0
K9_WARN_PRINT_ACCEL = 350.0
K9_MAX_BODY_PRINT_ACCEL = 600.0


TEMP_RE = re.compile(r"T:([-\d.]+)\s*/([-\d.]+)")
HEATER_RE = re.compile(r"@:(\d+)")
SD_PROGRESS_RE = re.compile(r"SD printing byte\s+(\d+)\s*/\s*(\d+)", re.IGNORECASE)
HOTEND_TARGET_RE = re.compile(r"\bS([-+]?\d+(?:\.\d+)?)\b", re.IGNORECASE)
PRINTABLE_SD_EXTS = {".gco", ".gcode", ".g"}
HOME_TRUST_TRUSTED = "trusted"
HOME_TRUST_UNCERTAIN = "uncertain"
HOME_TRUST_INVALID = "invalid"
JOG_STEPS_MM = (0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 20.0)
JOG_DEFAULT_STEP_MM = 5.0
SERVICE_X_FEEDRATE = 900
SERVICE_BED_FEEDRATE = 240
JOG_BED_FEEDRATE = 120
BED_JOG_SEGMENT_MM = 2.0
MAX_MANUAL_BED_JOG_MM = 2.0
BED_RAW_MIN_MM = 0.0
BED_RAW_MAX_MM = 95.0
JOG_FEEDRATES = {
    "X": SERVICE_X_FEEDRATE,
    "Y": JOG_BED_FEEDRATE,
    "Z": 600,
}
JOG_TRAVEL_ACCEL = {
    "X": 80,
    "Y": 40,
    "Z": 80,
}
JOG_RESTORE_TRAVEL_ACCEL = 80
MARLIN_VER_RE = re.compile(r"FIRMWARE_NAME:Marlin\s+([0-9.]+)")
LH_M115_RE = re.compile(r"FIRMWARE_NAME:(LH[^\r\n]*?)(?:\s+\(|\s+SOURCE_CODE_URL:|$)")
M92_RE = re.compile(r"M92\s+X([-\d.]+)\s+Y([-\d.]+)\s+Z([-\d.]+)\s+E([-\d.]+)")

LH_FIRMWARE_CATALOG = {
    "custom-hotend-autofan-45c-usb-mksLite.bin": {
        "lh_version": "LH v1",
        "label": "LH v1 AutoFan45 FAN1 Z606",
        "marlin": "2.1.2.5",
        "m92": (606.0, 606.0, 606.0, 1040.0),
    },
    "custom-hotend-autofan-45c-usb-z1167-mksLite.bin": {
        "lh_version": "LH v2",
        "label": "LH v2 AutoFan45 FAN1 Z1167",
        "marlin": "2.1.2.5",
        "m92": (606.0, 606.0, 1167.0, 1040.0),
    },
    "LH-v1-AutoFan45-FAN1-z606-mksLite.bin": {
        "lh_version": "LH v1",
        "label": "LH v1 AutoFan45 FAN1 Z606",
        "marlin": "2.1.2.5",
        "m92": (606.0, 606.0, 606.0, 1040.0),
    },
    "LH-v2-AutoFan45-FAN1-z1167-mksLite.bin": {
        "lh_version": "LH v2",
        "label": "LH v2 AutoFan45 FAN1 Z1167",
        "marlin": "2.1.2.5",
        "m92": (606.0, 606.0, 1167.0, 1040.0),
    },
    "LH-v3-StockPins-AutoFan45-FAN1-z600-e1040-mksLite.bin": {
        "lh_version": "LH v3",
        "label": "LH v3 StockPins AutoFan45 FAN1 Z600 E1040",
        "marlin": "2.1.2.5",
        "m92": (606.0, 606.0, 600.0, 1040.0),
    },
    "LH-v4-YZSwap-AutoFan45-FAN1-z600-e1040-mksLite.bin": {
        "lh_version": "LH v4",
        "label": "LH v4 YZSwap AutoFan45 FAN1 Z600 E1040",
        "marlin": "2.1.2.5",
        "m92": (606.0, 606.0, 600.0, 1040.0),
    },
    "ecf-k9-et4000plus-mksLite.bin": {
        "lh_version": "LH ECF",
        "label": "LH ECF Baseline",
        "marlin": "2.1.2.1",
        "m92": None,
    },
}

MANUAL_TEXT = textwrap.dedent(
    """
    Little Hands baseline printing mode

    Current working hardware setup
    - Firmware: LH-v4-YZSwap-AutoFan45-FAN1-z600-e1040-mksLite.bin
    - Fan: the only fan is connected to FAN1 and works as hotend auto-fan
      below 45C = off, above 45C = on
    - External hotbed / warm mat is not controlled by the printer firmware
    - Motor routing in the validated public K9 baseline behaves as Y/Z swapped
      relative to stock operator naming
    - Effective motion:
      X = printhead left / right
      Y = printhead up / down
      Z = bed in the print plane

    Fixed print home
    - X fully left
    - Z bed fully back / away from the operator
    - Y nozzle touching the bed
    - This pose is the print zero for the current power-on session
    - Cura start G-code uses G92 and treats this pose as X0 Y0 Z0 in the
      operator-facing Little Hands convention
    - Do not use plain G28 in normal print workflow

    Normal workflow
    1. Slice in Cura on the validated machine/profile.
    2. Upload G-code to SD from this app or copy it by card.
    3. Move the printer into the fixed print-start pose.
    4. Press "Save start" to save this pose as print zero.
    5. Use "Go to start" to return to this saved zero.
    6. Use "Start print"; the app preheats the hotend first, then returns to the saved zero and sends M24.
    7. Files uploaded by Little Hands have early blocking M109 rewritten to M104.
    8. After M24 the app keeps USB fully quiet for 180 seconds so this K9 can enter SD printing reliably.

    Bed leveling
    - Use the four corners and the center.
    - Move between points with the app.
    - The app lifts Z before XY moves and lowers back to Z0 at each point.
    - If the center is slightly lower than the corners, leave it for now and test the first layer.

    Diagnostics
    - This printer does not have a reliable standard Marlin endstop-based home.
    - "Save start" stores the current physical pose as print zero for this session.
    - "Go to start" returns to that stored print zero.
    - "Start print" returns to that stored print zero and starts the selected SD file.
    - "Reset USB" pauses polling and reopens a clean short serial session without restarting the whole app.
    - "Capture all metrics" dumps M115 / M503 / M114 / M105 / M27.
    - If USB telemetry is silent during a real SD start but the printer is heating,
      moving, or printing, do not power-cycle it; visually monitor the print and let
      Little Hands wait for USB to recover.

    Exports
    - "Export Cura profile" saves the current validated printer profile and Cura settings into the project.
    - Runtime log folder: /home/maxim/draftCode/littleHands/monitor_logs/
    - Ring log file: /home/maxim/draftCode/littleHands/monitor_logs/little_hands_runtime.log
    - "Save log" saves a timestamped copy of the current runtime log into gui_exports.
    """
).strip()

CURA_EXPORT_PATTERNS = [
    "machine_instances/lilHands.global.cfg",
    "machine_instances/lilHands_k9_warmmat.global.cfg",
    "definition_changes/lilHands_settings.inst.cfg",
    "definition_changes/lilHands_k9_warmmat_settings.inst.cfg",
    "definition_changes/custom_extruder_*settings.inst.cfg",
    "user/lilHands_user.inst.cfg",
    "user/codex_k9_warmmat*.cfg",
    "user/codex*.cfg",
    "quality_changes/codex_k9_warmmat*.cfg",
    "quality_changes/codex*.cfg",
    "extruders/*.extruder.cfg",
]
DISCONNECTED_PORT_LABEL = "— не подключаться —"
LANG_CHOICES = [("RU", "ru"), ("EN", "en"), ("中文", "zh")]

MANUAL_TEXTS = {
    "ru": MANUAL_TEXT,
    "en": textwrap.dedent(
        """
        Little Hands baseline printing mode

        Current working hardware setup
        - Firmware: LH-v4-YZSwap-AutoFan45-FAN1-z600-e1040-mksLite.bin
        - Fan: the only fan is connected to FAN1 and works as the hotend auto-fan
          below 45C = off, above 45C = on
        - External hotbed / warm mat is not controlled by the printer firmware
        - Effective operator motion:
          X = printhead left / right
          Y = printhead up / down
          Z = bed in the print plane

        Fixed print home
        - X fully left
        - Z bed fully back / away from the operator
        - Y nozzle touching the bed
        - This pose is the print zero for the current power-on session
        - Cura start G-code uses G92 and treats this pose as X0 Y0 Z0 in the
          operator-facing Little Hands convention
        - Do not use plain G28 in the normal print workflow

        Normal workflow
        1. Slice in Cura on the validated machine/profile.
        2. Upload G-code to SD from this app or copy it by card.
        3. Move the printer into the fixed print-start pose.
        4. Press "Save start" to save this pose as print zero.
        5. Use "Go to start" to return to this saved zero.
        6. Use "Start print"; the app preheats the hotend first, then returns to the saved zero and sends M24.
        7. Files uploaded by Little Hands have early blocking M109 rewritten to M104.
        8. After M24 the app keeps USB fully quiet for 180 seconds so this K9 can enter SD printing reliably.

        Diagnostics
        - This printer does not have a reliable standard Marlin endstop-based home.
        - "Save start" stores the current physical pose as print zero for this session.
        - "Go to start" returns to that stored print zero.
        - If USB telemetry is silent during a real SD start but the printer is heating,
          moving, or printing, do not power-cycle it; visually monitor the print and let
          Little Hands wait for USB to recover.
        """
    ).strip(),
    "zh": textwrap.dedent(
        """
        Little Hands 当前基线打印模式

        当前可工作的硬件配置
        - 固件：LH-v4-YZSwap-AutoFan45-FAN1-z600-e1040-mksLite.bin
        - 风扇：唯一风扇接在 FAN1，上端热端 45C 以上自动开启，以下关闭
        - 外部热床 / 保温垫不由打印机固件控制
        - 面向操作者的运动定义：
          X = 喷头左右
          Y = 喷头上下
          Z = 平台前后

        固定打印起点
        - X 最左
        - Z 平台最靠后 / 远离操作者
        - Y 喷嘴刚好接触床面
        - 这个姿态作为当前上电会话中的打印零点
        - Cura 起始 G-code 使用 G92，并按 Little Hands 的操作者坐标把它当作 X0 Y0 Z0
        - 正常打印流程不要使用普通 G28

        正常流程
        1. 在已验证的 Cura 机器/配置上切片。
        2. 通过本程序上传 G-code 到 SD，或手动拷卡。
        3. 将打印机移动到固定起始姿态。
        4. 点击“Save start”保存当前零点。
        5. 点击“Go to start”返回该零点。
        6. 点击“Start print”；程序会先预热热端，然后回到零点并发送 M24。
        7. 通过 Little Hands 上传的文件会把早期阻塞式 M109 改写为 M104。
        8. 发送 M24 后，程序会让 USB 完全安静 180 秒，以便这台 K9 稳定进入 SD 打印。

        诊断说明
        - 这台打印机没有可靠的标准 Marlin 限位回零。
        - “Save start”会把当前物理姿态设为本次会话的打印零点。
        - “Go to start”会回到这个零点。
        - 如果 SD 启动时 USB 遥测暂时沉默，但打印机正在加热、运动或打印，
          不要断电；目视观察打印，让 Little Hands 等待 USB 恢复。
        """
    ).strip(),
}


class K9ControlCenter:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Little Hands")
        self.ui_state = self._load_ui_state()
        self.root.geometry(self._normalized_geometry(str(self.ui_state.get("geometry", "1280x780"))))
        self.root.minsize(1080, 680)

        self.events: queue.Queue[tuple[str, object]] = queue.Queue()
        self.serial_lock = threading.Lock()
        self.monitor_enabled = True
        self.user_task_pending = False
        self.upload_cancel_requested = False

        self.preferred_port = str(self.ui_state.get("last_port", "")).strip()
        self.port_var = tk.StringVar(value="")
        self.port_display_var = tk.StringVar(value="")
        self.lang_var = tk.StringVar(value=str(self.ui_state.get("language", "ru")))
        self.lang_display_var = tk.StringVar()
        self.local_gcode_var = tk.StringVar()
        self.dest_name_var = tk.StringVar(value="MODEL.GCO")
        self.firmware_var = tk.StringVar(value=str(DEFAULT_FIRMWARE))
        self.temp_var = tk.StringVar(value="Hotend: ? / ? C")
        self.sd_var = tk.StringVar(value="SD: unknown")
        self.fw_var = tk.StringVar(value="")
        self.progress_var = tk.StringVar(value="Печать: простой")
        self.print_start_var = tk.StringVar(value="Старт: -")
        self.print_known_time_var = tk.StringVar(value="Известное время: -")
        self.busy_var = tk.StringVar(value="USB: idle")
        self.header_marquee_var = tk.StringVar(value="")
        self.selected_sd_var = tk.StringVar(value="Выбрано на SD: -")
        self.active_sd_var = tk.StringVar(value="Печатается: -")
        self.sd_notice_var = tk.StringVar(value="")
        self.files_status_var = tk.StringVar(value="Выбери G-code или прошивку.")
        self.step_var = tk.DoubleVar(value=self._initial_jog_step())
        self.computer_melody_on_complete_var = tk.BooleanVar(value=True)

        self.sd_list: list[str] = []
        self.sd_print_files: list[str] = []
        self.sd_other_files: list[str] = []
        self.sd_display_to_path: dict[str, str] = {}
        self.sd_has_eeprom = False
        self.eeprom_confirmed = False
        self.metrics_sections: dict[str, str] = {}
        self.action_widgets: list[ttk.Widget] = []
        self.print_was_active = False
        self.print_completion_armed = False
        self.sd_progress_sample_count = 0
        self.first_sd_progress_ts: float | None = None
        self.last_sd_progress_ts: float | None = None
        self.suppress_next_completion_chime = False
        self.home_trust = HOME_TRUST_INVALID
        self.home_trust_reason = "start pose not saved in this app session"
        self.session_zero_defined = False
        self.at_saved_start_pose = False
        self.post_print_pose_known = False
        self.post_print_pose: tuple[float, float, float] | None = None
        self.log_file_lock = threading.Lock()
        self.temp_history: list[tuple[float, float, float]] = []
        self.last_telemetry_log_ts = 0.0
        self.current_print_file = "-"
        self.current_print_display = "-"
        self.current_print_start_ts: float | None = None
        self.post_m24_usb_quiet_until = 0.0
        self.last_post_m24_quiet_log_ts = 0.0
        self.current_print_progress_pct: float | None = None
        self.print_state_restored_from_log = False
        self.print_start_watchdog_alerted = False
        self.post_print_recovery_required = False
        self.bed_clear_before_go_start_required = False
        self.stopped_print_pose: tuple[float, float, float] | None = None
        self.stopped_print_display = "-"
        self.predicted_print_end_valid = False
        self.predicted_print_end_file = "-"
        self.predicted_print_end_display = "-"
        self.predicted_print_end_contract = ""
        self.predicted_print_end_start_ts: float | None = None
        self.predicted_print_end_x = 95.0
        self.predicted_print_end_y = 95.0
        self.predicted_print_end_z: float | None = None
        self.last_print_state_save_ts = 0.0
        raw_profiles = self.ui_state.get("sd_gcode_profiles", {})
        self.sd_gcode_profiles = raw_profiles if isinstance(raw_profiles, dict) else {}
        self.printer_halted = False
        self.last_temp_sample_ts = 0.0
        self.last_temp_log_ts = 0.0
        self.usb_silence_since = 0.0
        self.last_usb_silence_log_ts = 0.0
        self.last_temp_current: float | None = None
        self.last_temp_target: float | None = None
        self.last_heater_power: int | None = None
        self.last_sd_sample_ts = 0.0
        self.last_sd_summary = "SD: unknown"
        self.last_fw_line = ""
        self.last_fw_identity = ""
        self.last_m115_raw = ""
        self.last_m503_raw = ""
        self.last_position_line = "X:? Y:? Z:?"
        self.last_position_sample_ts = 0.0
        self.last_fw_query_ts = 0.0
        self.last_poll_error_ts = 0.0
        self.header_marquee_source = ""
        self.header_marquee_offset = 0
        self.port_choices: list[str] = []
        self.find_port_animating = False
        self.find_port_anim_phase = 0
        self.auto_sd_refresh_after_port: str | None = None
        self.pending_flash_finalize = self.ui_state.get("pending_flash_finalize")
        if not isinstance(self.pending_flash_finalize, dict):
            self.pending_flash_finalize = None
        self.flash_finalize_in_progress = False
        self.flash_finalize_last_attempt_ts = 0.0
        self.files_window_content: ttk.LabelFrame | None = None
        self.files_window_status_label: tk.Label | None = None
        self.cancel_upload_button: ttk.Button | None = None
        self.manual_window: tk.Toplevel | None = None
        self.manual_text_widget: ScrolledText | None = None
        self.post_print_window: tk.Toplevel | None = None
        self.post_print_text_widget: tk.Text | None = None

        LOG_DIR.mkdir(parents=True, exist_ok=True)
        GUI_EXPORT_DIR.mkdir(parents=True, exist_ok=True)
        self._load_recent_temp_history_from_log()
        self._restore_persistent_print_state()

        self._build_ui()
        self._sync_home_controls()
        self.step_var.trace_add("write", self._on_jog_step_changed)
        if self.pending_flash_finalize:
            source_name = str(self.pending_flash_finalize.get("source_name", "mksLite.bin"))
            self.files_status_var.set(self._t("files_status_flash_pending").format(source=source_name))
        else:
            self.files_status_var.set(self._t("choose_gcode_or_firmware"))
        self._apply_language()
        self._apply_theme()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.after(150, self._drain_events)
        self.root.after(300, self._refresh_header_from_cache)
        self.root.after(400, self._refresh_ports_on_startup)
        self.root.after(350, self._tick_header_marquee)
        self.root.after(350, self._init_pane_layout)
        self.root.after(200, self._poll_status)

    def _draw_corner_hands(self) -> None:
        c = self.hands_canvas
        colors = self.colors
        c.configure(bg=colors["bg"], highlightbackground=colors["bg"])
        c.delete("all")

        palm_fill = "#9fe3b2"
        palm_outline = colors["accent"]
        cuff_fill = "#173127"

        def hand(offset_x: int, flip: int) -> None:
            c.create_oval(offset_x + 10, 18, offset_x + 34, 38, fill=palm_fill, outline=palm_outline, width=2)
            for idx, x in enumerate((11, 16, 21, 26)):
                c.create_oval(offset_x + x, 4, offset_x + x + 6, 22, fill=palm_fill, outline=palm_outline, width=2)
            thumb = [
                offset_x + (8 if flip < 0 else 29), 24,
                offset_x + (0 if flip < 0 else 39), 20,
                offset_x + (0 if flip < 0 else 39), 30,
                offset_x + (10 if flip < 0 else 29), 33,
            ]
            c.create_polygon(thumb, fill=palm_fill, outline=palm_outline, width=2, smooth=True)
            c.create_rectangle(offset_x + 14, 38, offset_x + 30, 48, fill=cuff_fill, outline=palm_outline, width=2)

        hand(6, -1)
        hand(52, 1)
        c.create_text(58, 57, text="Little Hands", fill=colors["muted"], font=("DejaVu Sans", 9, "bold"))

    def _load_recent_temp_history_from_log(self) -> None:
        if not RUNTIME_LOG_PATH.is_file():
            return
        now = time.time()
        today = time.localtime(now)
        cutoff = now - TEMP_GRAPH_WINDOW_SEC
        loaded: list[tuple[float, float, float]] = []
        telem_re = re.compile(r"(\d{2}):(\d{2}):(\d{2}).*temp=([-\d.]+)/([-\d.]+)")
        m105_re = re.compile(r"(\d{2}):(\d{2}):(\d{2}).*T:([-\d.]+)\s*/([-\d.]+)")
        try:
            lines = RUNTIME_LOG_PATH.read_text(encoding="utf-8", errors="replace").splitlines()
        except Exception:
            return
        for line in lines[-4000:]:
            m = telem_re.search(line) or m105_re.search(line)
            if not m:
                continue
            hh, mm, ss = int(m.group(1)), int(m.group(2)), int(m.group(3))
            cur = float(m.group(4))
            tgt = float(m.group(5))
            stamp = time.mktime((
                today.tm_year, today.tm_mon, today.tm_mday,
                hh, mm, ss,
                today.tm_wday, today.tm_yday, today.tm_isdst
            ))
            if stamp > now + 60:
                stamp -= 24 * 3600
            if stamp >= cutoff:
                loaded.append((stamp, cur, tgt))
        if loaded:
            self.temp_history = loaded[-1200:]
            self.last_temp_sample_ts = loaded[-1][0]
            self.last_temp_current = loaded[-1][1]
            self.last_temp_target = loaded[-1][2]
        self._restore_last_print_state_from_log(lines)

    def _restore_last_print_state_from_log(self, lines: list[str]) -> None:
        telemetry_re = re.compile(r"(\d{2}):(\d{2}):(\d{2}) TELEMETRY file=(.+?) progress=([-\d.]+)%")
        start_re = re.compile(r"(\d{2}):(\d{2}):(\d{2}) PRINT_START file=(.+)")
        expected_re = re.compile(
            r"(\d{2}):(\d{2}):(\d{2}) PRINT_END_EXPECTED file=(.+?) contract=(\S+) end_x=([-\d.]+) end_y=([-\d.]+) end_z=([-\d.?]+)"
        )
        end_re = re.compile(r"(\d{2}):(\d{2}):(\d{2}) PRINT_END file=(.+?) temp=")
        last_active: str | None = None
        last_end: str | None = None
        last_start_ts: float | None = None
        last_progress_pct: float | None = None
        first_active_telem_ts: float | None = None
        last_active_evidence_ts: float | None = None
        expected_by_file: dict[str, dict[str, object]] = {}
        today = time.localtime(time.time())

        def stamp_for(hh: int, mm: int, ss: int) -> float:
            stamp = time.mktime((
                today.tm_year, today.tm_mon, today.tm_mday,
                hh, mm, ss,
                today.tm_wday, today.tm_yday, today.tm_isdst
            ))
            if stamp > time.time() + 60:
                stamp -= 24 * 3600
            return stamp

        for line in lines[-4000:]:
            mx = expected_re.search(line)
            if mx:
                file_name = mx.group(4).strip()
                end_z_text = mx.group(8).strip()
                try:
                    end_z = float(end_z_text)
                except ValueError:
                    end_z = None
                expected_by_file[file_name] = {
                    "ts": stamp_for(int(mx.group(1)), int(mx.group(2)), int(mx.group(3))),
                    "contract": mx.group(5).strip(),
                    "end_x": float(mx.group(6)),
                    "end_y": float(mx.group(7)),
                    "end_z": end_z,
                }
                continue
            ms = start_re.search(line)
            if ms:
                last_active = ms.group(4).strip()
                last_end = None
                last_start_ts = stamp_for(int(ms.group(1)), int(ms.group(2)), int(ms.group(3)))
                last_active_evidence_ts = last_start_ts
                first_active_telem_ts = None
                last_progress_pct = None
                continue
            mt = telemetry_re.search(line)
            if mt:
                file_name = mt.group(4).strip()
                last_active = file_name
                last_progress_pct = float(mt.group(5))
                ts = stamp_for(int(mt.group(1)), int(mt.group(2)), int(mt.group(3)))
                last_active_evidence_ts = ts
                if file_name == last_active and first_active_telem_ts is None:
                    first_active_telem_ts = ts
                continue
            me = end_re.search(line)
            if me:
                last_end = me.group(4).strip()
        if last_active and last_active != "-" and last_active != last_end:
            now = time.time()
            if last_active_evidence_ts and (now - last_active_evidence_ts) > PRINT_STATE_ACTIVE_RESTORE_MAX_AGE_SEC:
                return
            unconfirmed_start_age = (now - last_start_ts) if last_start_ts and last_progress_pct is None else None
            if unconfirmed_start_age is not None and unconfirmed_start_age > PRINT_START_GRACE_SEC:
                return
            self.current_print_file = last_active
            self.current_print_display = last_active
            self.active_sd_var.set(self._format_label_value("active_sd", last_active))
            self.current_print_start_ts = last_start_ts or first_active_telem_ts
            if last_progress_pct is None and last_start_ts:
                self.post_m24_usb_quiet_until = max(0.0, last_start_ts + POST_M24_USB_QUIET_SEC)
            self.current_print_progress_pct = last_progress_pct
            self.print_state_restored_from_log = True
            if last_progress_pct is not None:
                self.print_completion_armed = True
                self.print_was_active = True
            expected = expected_by_file.get(last_active)
            if expected:
                self.predicted_print_end_valid = True
                self.predicted_print_end_file = last_active
                self.predicted_print_end_display = last_active
                self.predicted_print_end_contract = str(expected.get("contract") or PRINT_END_CONTRACT)
                self.predicted_print_end_start_ts = last_start_ts or float(expected.get("ts") or 0.0) or None
                self.predicted_print_end_x = float(expected.get("end_x") or 95.0)
                self.predicted_print_end_y = float(expected.get("end_y") or 95.0)
                end_z = expected.get("end_z")
                self.predicted_print_end_z = float(end_z) if isinstance(end_z, (int, float)) else None

    def _normalize_sd_key(self, path: str) -> str:
        return path.strip().lstrip("/").upper()

    def _restore_persistent_print_state(self) -> None:
        if not PRINT_STATE_PATH.is_file():
            return
        try:
            data = json.loads(PRINT_STATE_PATH.read_text(encoding="utf-8"))
        except Exception:
            return
        if not isinstance(data, dict):
            return
        try:
            updated_ts = float(data.get("updated_ts") or 0.0)
        except (TypeError, ValueError):
            return
        if updated_ts and (time.time() - updated_ts) > PRINT_STATE_MAX_AGE_SEC:
            return
        profiles = data.get("sd_gcode_profiles")
        if isinstance(profiles, dict):
            self.sd_gcode_profiles.update(profiles)
        phase = str(data.get("phase") or "")
        if phase == "completed" and data.get("post_print_recovery_required"):
            pose = data.get("post_print_pose")
            if isinstance(pose, list) and len(pose) == 3:
                try:
                    self.post_print_pose = (float(pose[0]), float(pose[1]), float(pose[2]))
                    self.post_print_pose_known = True
                    self.post_print_recovery_required = True
                    self.bed_clear_before_go_start_required = True
                except (TypeError, ValueError):
                    self.post_print_pose = None
                    self.post_print_pose_known = False
        if (
            phase in {"prepared", "printing", "print_end_expected"}
            and updated_ts
            and (time.time() - updated_ts) > PRINT_STATE_ACTIVE_RESTORE_MAX_AGE_SEC
        ):
            self._clear_predicted_print_end(save=False)
            self._save_print_state("idle", force=True)
            return
        predicted = data.get("predicted_end")
        if not isinstance(predicted, dict) or not predicted.get("valid"):
            return
        file_name = str(predicted.get("file") or "-").strip()
        if not file_name or file_name == "-":
            return
        self.predicted_print_end_valid = True
        self.predicted_print_end_file = file_name
        self.predicted_print_end_display = str(predicted.get("display") or file_name).strip()
        self.predicted_print_end_contract = str(predicted.get("contract") or PRINT_END_CONTRACT)
        try:
            self.predicted_print_end_start_ts = float(predicted.get("start_ts") or 0.0) or None
            self.predicted_print_end_x = float(predicted.get("end_x") or 95.0)
            self.predicted_print_end_y = float(predicted.get("end_y") or 95.0)
        except (TypeError, ValueError):
            self.predicted_print_end_start_ts = None
            self.predicted_print_end_x = 95.0
            self.predicted_print_end_y = 95.0
        end_z = predicted.get("end_z")
        try:
            self.predicted_print_end_z = float(end_z) if end_z is not None else None
        except (TypeError, ValueError):
            self.predicted_print_end_z = None
        if self.current_print_file == "-" and phase in {"prepared", "printing", "print_end_expected"}:
            restore_start_ts = self.predicted_print_end_start_ts or updated_ts or None
            progress = data.get("progress_pct")
            try:
                progress_value = float(progress) if progress is not None else None
            except (TypeError, ValueError):
                progress_value = None
            if (
                (progress_value is None or progress_value <= 0.0)
                and restore_start_ts
                and (time.time() - restore_start_ts) > PRINT_START_GRACE_SEC
            ):
                self._clear_predicted_print_end(save=False)
                self._save_print_state("idle", force=True)
                return
            self.current_print_file = file_name
            self.current_print_display = self.predicted_print_end_display
            self.current_print_start_ts = restore_start_ts
            self.current_print_progress_pct = progress_value
            self.print_state_restored_from_log = True
            self.print_completion_armed = bool(self.current_print_progress_pct is not None)
            self.print_was_active = bool(self.current_print_progress_pct is not None)
            self.active_sd_var.set(self._format_label_value("active_sd", self.current_print_display))

    def _print_state_payload(self, phase: str) -> dict[str, object]:
        return {
            "schema": 1,
            "phase": phase,
            "updated_ts": time.time(),
            "current_print_file": self.current_print_file,
            "current_print_display": self.current_print_display,
            "current_print_start_ts": self.current_print_start_ts,
            "progress_pct": self.current_print_progress_pct,
            "predicted_end": {
                "valid": self.predicted_print_end_valid,
                "file": self.predicted_print_end_file,
                "display": self.predicted_print_end_display,
                "contract": self.predicted_print_end_contract,
                "start_ts": self.predicted_print_end_start_ts,
                "end_x": self.predicted_print_end_x,
                "end_y": self.predicted_print_end_y,
                "end_z": self.predicted_print_end_z,
            },
            "post_print_recovery_required": self.post_print_recovery_required,
            "post_print_pose_known": self.post_print_pose_known,
            "post_print_pose": list(self.post_print_pose) if self.post_print_pose is not None else None,
            "sd_gcode_profiles": self.sd_gcode_profiles,
        }

    def _save_print_state(self, phase: str = "printing", *, force: bool = False) -> None:
        now = time.time()
        if not force and (now - self.last_print_state_save_ts) < PRINT_STATE_SAVE_INTERVAL_SEC:
            return
        self.last_print_state_save_ts = now
        try:
            PRINT_STATE_PATH.write_text(
                json.dumps(self._print_state_payload(phase), ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        except Exception as exc:
            self._post("log", f"Не удалось сохранить локальное состояние печати: {exc}")

    def _clear_predicted_print_end(self, *, save: bool = True) -> None:
        self.predicted_print_end_valid = False
        self.predicted_print_end_file = "-"
        self.predicted_print_end_display = "-"
        self.predicted_print_end_contract = ""
        self.predicted_print_end_start_ts = None
        self.predicted_print_end_x = 95.0
        self.predicted_print_end_y = 95.0
        self.predicted_print_end_z = None
        if save:
            self._save_print_state("idle", force=True)

    def _profile_key(self, sd_path: str) -> str:
        return self._normalize_sd_key(sd_path)

    def _remember_gcode_profile(self, sd_path: str, display: str, source: Path) -> dict[str, object]:
        info = self._inspect_gcode_file(source)
        bounds = info.get("bounds") if isinstance(info.get("bounds"), dict) else {}
        max_z = bounds.get("MAXZ") if isinstance(bounds, dict) else None
        key = self._profile_key(sd_path)
        previous = self.sd_gcode_profiles.get(key)
        previous_profile = previous if isinstance(previous, dict) else {}
        profile: dict[str, object] = {
            "sd_path": sd_path,
            "display": display,
            "source": str(source),
            "updated_ts": time.time(),
            "max_z": float(max_z) if isinstance(max_z, (int, float)) else None,
            "bounds": bounds,
            "hotend_target": info.get("hotend_target"),
            "has_blocking_m109": bool(info.get("has_blocking_m109")),
        }
        for field in ("last_duration_s", "last_started_at", "last_finished_at", "last_print_display"):
            if field in previous_profile:
                profile[field] = previous_profile[field]
        self.sd_gcode_profiles[key] = profile
        if len(self.sd_gcode_profiles) > 40:
            items = sorted(
                self.sd_gcode_profiles.items(),
                key=lambda item: float(item[1].get("updated_ts") or 0.0) if isinstance(item[1], dict) else 0.0,
                reverse=True,
            )
            self.sd_gcode_profiles = dict(items[:40])
        self._save_print_state("idle", force=True)
        return profile

    def _profile_for_print(self, sd_path: str, display: str, source: Path | None = None) -> dict[str, object] | None:
        if source and source.is_file():
            return self._remember_gcode_profile(sd_path, display, source)
        cached = self.sd_gcode_profiles.get(self._profile_key(sd_path))
        return cached if isinstance(cached, dict) else None

    def _remember_print_duration(self, sd_path: str, display: str, start_ts: float | None, finish_ts: float) -> None:
        if not sd_path or sd_path == "-" or not start_ts:
            return
        duration_s = max(0, int(round(finish_ts - start_ts)))
        key = self._profile_key(sd_path)
        profile = self.sd_gcode_profiles.get(key)
        if not isinstance(profile, dict):
            profile = {
                "sd_path": sd_path,
                "display": display or sd_path,
            }
        profile.update(
            {
                "sd_path": sd_path,
                "display": display or profile.get("display") or sd_path,
                "updated_ts": finish_ts,
                "last_duration_s": duration_s,
                "last_started_at": start_ts,
                "last_finished_at": finish_ts,
                "last_print_display": display or sd_path,
            }
        )
        self.sd_gcode_profiles[key] = profile

    def _known_print_time_text(self, sd_path: str | None, display: str | None = None) -> str:
        if not sd_path:
            return "-"
        profile = self._profile_for_print(sd_path, display or sd_path)
        if not profile:
            return "-"
        duration = profile.get("last_duration_s")
        try:
            duration_s = float(duration) if duration is not None else None
        except (TypeError, ValueError):
            duration_s = None
        if duration_s is None:
            return "-"
        finished = profile.get("last_finished_at")
        try:
            finished_text = time.strftime("%Y-%m-%d %H:%M", time.localtime(float(finished))) if finished else ""
        except (TypeError, ValueError, OSError):
            finished_text = ""
        base = self._format_duration_short(duration_s)
        if not finished_text:
            return base
        suffix = {
            "ru": "последняя",
            "en": "last",
            "zh": "上次",
        }.get(self.lang_var.get().strip() or "ru", "последняя")
        return f"{base} ({suffix}: {finished_text})"

    def _update_known_print_time_label(self, sd_path: str | None = None, display: str | None = None) -> None:
        if sd_path is None:
            if self.current_print_file != "-":
                sd_path = self.current_print_file
                display = self.current_print_display if self.current_print_display != "-" else self.current_print_file
            else:
                if not hasattr(self, "sd_print_listbox"):
                    self.print_known_time_var.set(self._format_label_value("known_print_time", "-"))
                    return
                sd_path = self._selected_print_sd_path()
                display = self._selected_sd_display() or sd_path
        self.print_known_time_var.set(self._format_label_value("known_print_time", self._known_print_time_text(sd_path, display)))

    def _hotend_target_for_print(self, sd_path: str, display: str, source: Path | None = None) -> float:
        profile = self._profile_for_print(sd_path, display, source)
        target = profile.get("hotend_target") if isinstance(profile, dict) else None
        if isinstance(target, (int, float)) and target > 0:
            base_target = float(target)
        else:
            base_target = DEFAULT_PRINT_HOTEND_TARGET_C
        has_blocking_m109 = True if profile is None else bool(profile.get("has_blocking_m109"))
        if has_blocking_m109 and base_target < 220.0:
            return base_target + PRINT_PREHEAT_BLOCKING_M109_EXTRA_C
        return base_target

    def _preheat_hotend_for_sd_start(self, target: float) -> None:
        target = float(target)
        if target <= 0:
            return
        self._post("log", f"Предпрогрев hotend до {target:.0f}C перед SD-стартом.")
        self._post("files-status", f"Предпрогрев hotend: цель {target:.0f}C")
        self._post("progress", (f"Предпрогрев hotend: цель {target:.0f}C", 0.0))
        deadline = time.monotonic() + PRINT_PREHEAT_TIMEOUT_SEC
        last_logged = 0.0
        last_temp: float | None = None
        first_temp: float | None = None
        first_temp_ts = 0.0
        target_zero_since = 0.0
        heater_zero_since = 0.0
        heater_positive_seen = False
        hotend_off_sent = False

        def send_hotend_off(ser: object | None = None) -> None:
            nonlocal hotend_off_sent
            if hotend_off_sent:
                return
            hotend_off_sent = True
            try:
                if ser is not None:
                    sdtool.send_line(ser, "M104 S0")
                    time.sleep(0.2)
                    sdtool.read_for(ser, 0.5)
                else:
                    sdtool.query_command(
                        self._port(),
                        self._baud(),
                        "M104 S0",
                        wait_before_read=0.2,
                        read_seconds=0.5,
                        sync=False,
                        reset_input=False,
                    )
            except Exception:
                pass

        try:
            with sdtool.open_serial(self._port(), self._baud(), timeout=0.5, reset_input=True) as ser:
                sdtool.sync_ascii(ser)
                sdtool.send_line(ser, "T0")
                time.sleep(0.2)
                sdtool.send_line(ser, f"M104 S{target:.0f}")
                time.sleep(0.4)
                sdtool.read_for(ser, 0.8)

                while time.monotonic() < deadline:
                    sdtool.send_line(ser, "M105")
                    time.sleep(0.25)
                    temp_reply = sdtool.read_for(ser, 1.0)
                    match = TEMP_RE.search(temp_reply)
                    if match:
                        now = time.monotonic()
                        current = float(match.group(1))
                        seen_target = float(match.group(2))
                        last_temp = current
                        if first_temp is None:
                            first_temp = current
                            first_temp_ts = now
                        heater_match = HEATER_RE.search(temp_reply)
                        heater = int(heater_match.group(1)) if heater_match else None
                        if heater is not None and heater > 0:
                            heater_positive_seen = True
                            heater_zero_since = 0.0
                        self._post("temp", (current, seen_target, heater))
                        pct = max(0.0, min(100.0, (current / max(target, 1.0)) * 100.0))
                        heater_text = f" @:{heater}" if heater is not None else " @:?"
                        self._post("progress", (f"Предпрогрев hotend: {current:.1f}/{seen_target:.0f}C{heater_text}", pct))
                        if now - last_logged >= 8.0:
                            last_logged = now
                            self._post("log", f"Предпрогрев: {current:.1f}/{seen_target:.0f}C{heater_text}")
                        if current >= target - PRINT_PREHEAT_MARGIN_C:
                            self._post("progress", ("Предпрогрев завершён: запускаю SD", 100.0))
                            self._post("log", f"Предпрогрев завершён: {current:.1f}/{seen_target:.0f}C{heater_text}. Запускаю SD-файл.")
                            return
                        if seen_target <= 0.0:
                            target_zero_since = target_zero_since or now
                            if now - target_zero_since >= PRINT_PREHEAT_TARGET_GRACE_SEC:
                                send_hotend_off(ser)
                                raise RuntimeError(
                                    "Hotend не принял цель нагрева перед SD-стартом: M105 показывает /0C. "
                                    "Нагрев выключен командой M104 S0; нужен power cycle принтера перед новой попыткой."
                                )
                        else:
                            target_zero_since = 0.0
                        if (
                            heater is not None
                            and heater <= 0
                            and seen_target > 0.0
                            and current < target - PRINT_PREHEAT_MARGIN_C
                            and not heater_positive_seen
                        ):
                            heater_zero_since = heater_zero_since or now
                            if now - heater_zero_since >= PRINT_PREHEAT_HEATER_ZERO_GRACE_SEC:
                                send_hotend_off(ser)
                                raise RuntimeError(
                                    f"Hotend получил цель {seen_target:.0f}C, но нагреватель остаётся @0 "
                                    f"при температуре {current:.1f}C. Нагрев выключен командой M104 S0; "
                                    "сделай power cycle принтера и проверь, что вентилятор/hotend оживают при старте."
                                )
                        else:
                            heater_zero_since = 0.0
                        if (
                            first_temp is not None
                            and first_temp_ts
                            and now - first_temp_ts >= PRINT_PREHEAT_NO_RISE_GRACE_SEC
                            and current < first_temp + PRINT_PREHEAT_MIN_RISE_C
                            and current < target - PRINT_PREHEAT_MARGIN_C
                        ):
                            send_hotend_off(ser)
                            raise RuntimeError(
                                f"Hotend почти не греется: {first_temp:.1f}C -> {current:.1f}C "
                                f"за {PRINT_PREHEAT_NO_RISE_GRACE_SEC:.0f} секунд. "
                                "Нагрев выключен командой M104 S0; печать не запускаю."
                            )
                    time.sleep(PRINT_PREHEAT_POLL_SEC)
                send_hotend_off(ser)
        except Exception:
            send_hotend_off(None)
            raise
        if last_temp is None:
            raise RuntimeError(
                "Не удалось получить температуру hotend перед SD-стартом. "
                "Нагрев выключен командой M104 S0; нужен power cycle принтера перед новой попыткой."
            )
        raise RuntimeError(
            f"Hotend не вышел на температуру перед SD-стартом: {last_temp:.1f}/{target:.0f}C. "
            "Нагрев выключен командой M104 S0; не запускаю печать вслепую."
        )

    def _prime_print_end_contract(self, sd_path: str, display: str, source: Path | None = None) -> None:
        profile = self._profile_for_print(sd_path, display, source)
        max_z = profile.get("max_z") if isinstance(profile, dict) else None
        end_z = min(PRINT_END_MAX_Z, float(max_z) + 10.0) if isinstance(max_z, (int, float)) else None
        self.predicted_print_end_valid = True
        self.predicted_print_end_file = sd_path
        self.predicted_print_end_display = display or sd_path
        self.predicted_print_end_contract = PRINT_END_CONTRACT
        self.predicted_print_end_start_ts = time.time()
        self.predicted_print_end_x = 95.0
        self.predicted_print_end_y = 95.0
        self.predicted_print_end_z = end_z
        z_text = f"{end_z:.2f}" if end_z is not None else "?"
        self._append_ring_log(
            f"{time.strftime('%H:%M:%S')} PRINT_END_EXPECTED file={sd_path} contract={PRINT_END_CONTRACT} end_x=95.00 end_y=95.00 end_z={z_text}"
        )
        self._save_print_state("prepared", force=True)

    def _source_for_print(self, sd_path: str, display: str) -> Path | None:
        raw = self.local_gcode_var.get().strip()
        if not raw:
            return None
        source = Path(raw).expanduser()
        if not source.is_file():
            return None
        source_sd_name = sdtool.make_sd_name(source.name)
        if (
            self._normalize_sd_key(source_sd_name) == self._normalize_sd_key(sd_path)
            or source.name in display
            or self._normalize_sd_key(source.name) == self._normalize_sd_key(display)
        ):
            return source
        return None

    def _load_ui_state(self) -> dict[str, object]:
        if not UI_STATE_PATH.is_file():
            return {}
        try:
            data = json.loads(UI_STATE_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except Exception:
            pass
        return {}

    def _initial_jog_step(self) -> float:
        try:
            value = float(self.ui_state.get("jog_step", JOG_DEFAULT_STEP_MM))
        except (TypeError, ValueError):
            value = JOG_DEFAULT_STEP_MM
        if any(abs(value - allowed) < 0.0001 for allowed in JOG_STEPS_MM):
            return value
        return JOG_DEFAULT_STEP_MM

    def _on_jog_step_changed(self, *_args) -> None:
        self._save_ui_state()

    def _home_trust_label(self) -> str:
        lang = self.lang_var.get().strip() or "ru"
        labels = {
            HOME_TRUST_TRUSTED: {"ru": "доверенный", "en": "trusted", "zh": "可信"},
            HOME_TRUST_UNCERTAIN: {"ru": "сомнительный", "en": "uncertain", "zh": "不确定"},
            HOME_TRUST_INVALID: {"ru": "не задан", "en": "invalid", "zh": "无效"},
        }
        return labels.get(self.home_trust, labels[HOME_TRUST_INVALID]).get(lang, labels[HOME_TRUST_INVALID]["ru"])

    def _home_is_trusted(self) -> bool:
        return bool(self.home_trust == HOME_TRUST_TRUSTED and self.session_zero_defined)

    def _sync_home_controls(self) -> None:
        trusted = self._home_is_trusted()
        go_state = "normal" if trusted and not self.user_task_pending else "disabled"
        start_state = "normal" if trusted and not self.user_task_pending else "disabled"
        guarded_buttons = (
            ("go_start_button", go_state),
            ("start_print_button", start_state),
            ("upload_and_start_button", start_state),
        )
        for name, state in guarded_buttons:
            widget = getattr(self, name, None)
            if widget is not None:
                try:
                    widget.configure(state=state)
                except Exception:
                    pass

    def _apply_home_trust(self, state: str, reason: str = "", *, log_change: bool = False) -> None:
        if state not in {HOME_TRUST_TRUSTED, HOME_TRUST_UNCERTAIN, HOME_TRUST_INVALID}:
            state = HOME_TRUST_INVALID
        previous = getattr(self, "home_trust", HOME_TRUST_INVALID)
        self.home_trust = state
        self.home_trust_reason = reason
        self.session_zero_defined = state == HOME_TRUST_TRUSTED
        if state != HOME_TRUST_TRUSTED:
            self.at_saved_start_pose = False
        self._sync_home_controls()
        if log_change and (previous != state or reason):
            label = self._home_trust_label()
            detail = f": {reason}" if reason else ""
            self.log(f"Home trust: {label}{detail}")

    def _set_home_trust(self, state: str, reason: str = "", *, log_change: bool = False) -> None:
        if threading.current_thread() is threading.main_thread():
            self._apply_home_trust(state, reason, log_change=log_change)
            return
        if state not in {HOME_TRUST_TRUSTED, HOME_TRUST_UNCERTAIN, HOME_TRUST_INVALID}:
            state = HOME_TRUST_INVALID
        self.home_trust = state
        self.home_trust_reason = reason
        self.session_zero_defined = state == HOME_TRUST_TRUSTED
        if state != HOME_TRUST_TRUSTED:
            self.at_saved_start_pose = False
        self._post("home-trust", (state, reason, log_change))

    def _save_ui_state(self) -> None:
        state: dict[str, object] = {"geometry": self.root.winfo_geometry()}
        state["language"] = self.lang_var.get().strip() or "ru"
        try:
            state["jog_step"] = float(self.step_var.get())
        except (tk.TclError, TypeError, ValueError):
            state["jog_step"] = JOG_DEFAULT_STEP_MM
        state["sd_gcode_profiles"] = self.sd_gcode_profiles
        if self.pending_flash_finalize:
            state["pending_flash_finalize"] = self.pending_flash_finalize
        try:
            current = self.views.select()
            state["selected_view"] = "log" if str(current) == str(self.log_frame) else "metrics"
        except Exception:
            pass
        try:
            state["main_sash"] = int(self.main_pane.sashpos(0))
        except Exception:
            pass
        try:
            _x, y = self.left_split.sash_coord(0)
            state["left_split_y"] = int(y)
        except Exception:
            pass
        if self._port():
            state["last_port"] = self._port()
        try:
            UI_STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    def _t(self, key: str) -> str:
        lang = self.lang_var.get().strip() or "ru"
        table = {
            "language": {"ru": "Язык", "en": "Language", "zh": "语言"},
            "find": {"ru": "Найти", "en": "Find", "zh": "查找"},
            "disconnect": {"ru": "Откл.", "en": "Off", "zh": "断开"},
            "files_and_firmware": {"ru": "Файлы и прошивка", "en": "Files & Firmware", "zh": "文件和固件"},
            "manual": {"ru": "Manual", "en": "Manual", "zh": "说明"},
            "reset_usb": {"ru": "Сброс USB", "en": "Reset USB", "zh": "重置 USB"},
            "export_cura": {"ru": "Экспорт профиля Cura", "en": "Export Cura profile", "zh": "导出 Cura 配置"},
            "sound_pc_short": {"ru": "Звук ПК", "en": "PC sound", "zh": "电脑提示音"},
            "sound_pc_complete": {"ru": "Звук окончания печати ПК", "en": "PC completion sound", "zh": "打印完成电脑提示音"},
            "temp_graph": {"ru": "Температура hotend", "en": "Hotend temperature", "zh": "热端温度"},
            "live_params": {"ru": "Параметры в реальном времени", "en": "Realtime parameters", "zh": "实时参数"},
            "sd_files": {"ru": "Файлы на SD принтера", "en": "Printer SD files", "zh": "打印机 SD 文件"},
            "printable_files": {"ru": "Файлы для печати", "en": "Printable files", "zh": "可打印文件"},
            "refresh_list": {"ru": "Обновить список", "en": "Refresh list", "zh": "刷新列表"},
            "start_print": {"ru": "Старт печати", "en": "Start print", "zh": "开始打印"},
            "delete": {"ru": "Удалить", "en": "Delete", "zh": "删除"},
            "pause": {"ru": "Пауза", "en": "Pause", "zh": "暂停"},
            "resume": {"ru": "Продолжить", "en": "Resume", "zh": "继续"},
            "stop": {"ru": "Стоп", "en": "Stop", "zh": "停止"},
            "manual_controls": {"ru": "Ручное управление", "en": "Manual control", "zh": "手动控制"},
            "save_start": {"ru": "Запомнить старт", "en": "Save start", "zh": "保存起点"},
            "go_start": {"ru": "К старту", "en": "Go to start", "zh": "回到起点"},
            "motors_off": {"ru": "Моторы выкл", "en": "Motors off", "zh": "关闭电机"},
            "step": {"ru": "Шаг", "en": "Step", "zh": "步长"},
            "head_left": {"ru": "Голова влево", "en": "Head left", "zh": "喷头左移"},
            "head_right": {"ru": "Голова вправо", "en": "Head right", "zh": "喷头右移"},
            "bed_away": {"ru": "Стол от себя", "en": "Bed away", "zh": "平台后移"},
            "bed_toward": {"ru": "Стол к себе", "en": "Bed toward", "zh": "平台前移"},
            "head_down": {"ru": "Голова вниз", "en": "Head down", "zh": "喷头下移"},
            "head_up": {"ru": "Голова вверх", "en": "Head up", "zh": "喷头上移"},
            "hard_stop": {"ru": "Жёсткий стоп", "en": "Hard stop", "zh": "强制停止"},
            "bed_level": {"ru": "Калибровка стола", "en": "Bed leveling", "zh": "平台调平"},
            "level_points": {"ru": "Точки X/Y", "en": "X/Y points", "zh": "X/Y 点位"},
            "journal": {"ru": "Журнал", "en": "Journal", "zh": "日志"},
            "usb_metrics": {"ru": "USB-метрики", "en": "USB metrics", "zh": "USB 指标"},
            "capture_metrics": {"ru": "Снять все метрики", "en": "Capture all metrics", "zh": "抓取全部指标"},
            "save_log": {"ru": "Сохранить лог", "en": "Save log", "zh": "保存日志"},
            "pick_gcode": {"ru": "Выбрать", "en": "Choose", "zh": "选择"},
            "gcode": {"ru": "G-code", "en": "G-code", "zh": "G-code"},
            "sd_name": {"ru": "Имя на SD", "en": "Name on SD", "zh": "SD 文件名"},
            "check_gcode": {"ru": "Проверить G-code", "en": "Check G-code", "zh": "检查 G-code"},
            "upload_gcode": {"ru": "Залить G-code", "en": "Upload G-code", "zh": "上传 G-code"},
            "upload_and_start": {"ru": "Залить и старт", "en": "Upload & start", "zh": "上传并开始"},
            "cancel_upload": {"ru": "Отменить", "en": "Cancel", "zh": "取消"},
            "cancel_uploading": {"ru": "Отменяю...", "en": "Cancelling...", "zh": "正在取消..."},
            "firmware": {"ru": "Прошивка", "en": "Firmware", "zh": "固件"},
            "create_eeprom": {"ru": "Создать EEPROM.DAT", "en": "Create EEPROM.DAT", "zh": "创建 EEPROM.DAT"},
            "flash_firmware": {"ru": "Залить прошивку", "en": "Flash firmware", "zh": "写入固件"},
            "files_window_title": {"ru": "Little Hands — Файлы и прошивка", "en": "Little Hands — Files and Firmware", "zh": "Little Hands — 文件和固件"},
            "manual_title": {"ru": "Little Hands Manual", "en": "Little Hands Manual", "zh": "Little Hands 使用说明"},
            "wait_m105": {"ru": "Жду первый ответ M105", "en": "Waiting for first M105 reply", "zh": "等待第一个 M105 响应"},
            "selected_sd": {"ru": "Выбрано на SD", "en": "Selected on SD", "zh": "SD 已选择"},
            "active_sd": {"ru": "Печатается", "en": "Printing", "zh": "正在打印"},
            "start_time": {"ru": "Старт", "en": "Start", "zh": "开始时间"},
            "known_print_time": {"ru": "Известное время", "en": "Known time", "zh": "已知耗时"},
            "choose_gcode_or_firmware": {"ru": "Выбери G-code или прошивку.", "en": "Choose a G-code file or firmware.", "zh": "请选择 G-code 或固件文件。"},
            "sd_empty": {"ru": "SD-карта читается, но список файлов пуст.", "en": "The SD card is readable, but the file list is empty.", "zh": "SD 卡可读取，但文件列表为空。"},
            "progress_idle": {"ru": "Печать: простой", "en": "Print: idle", "zh": "打印：空闲"},
            "files_status_flash_pending": {
                "ru": "Ожидаю перезапуск принтера после прошивки {source}. Потом автоматически выполню M502/M500.",
                "en": "Waiting for printer reboot after flashing {source}. Then M502/M500 will run automatically.",
                "zh": "正在等待打印机在刷写 {source} 后重启，随后会自动执行 M502/M500。",
            },
            "not_connected": {"ru": "— не подключаться —", "en": "— do not connect —", "zh": "— 不连接 —"},
        }
        return table.get(key, {}).get(lang, table.get(key, {}).get("ru", key))

    def _format_label_value(self, key: str, value: str) -> str:
        return f"{self._t(key)}: {value}"

    def _refresh_translated_strings(self) -> None:
        self.progress_var.set(self._t("progress_idle") if self.progress_var.get().startswith(("Печать: простой", "Print: idle", "打印：空闲")) else self.progress_var.get())
        self.selected_sd_var.set(self._format_label_value("selected_sd", self._selected_sd_display() or "-"))
        active_raw = self.current_print_display if self.current_print_display != "-" else self.current_print_file
        if self.active_sd_var.get().endswith("(имя не восстановлено)"):
            suffix = {
                "ru": "идёт печать (имя не восстановлено)",
                "en": "printing (name not recovered)",
                "zh": "正在打印（文件名未恢复）",
            }[self.lang_var.get() or "ru"]
            self.active_sd_var.set(self._format_label_value("active_sd", suffix))
        else:
            self.active_sd_var.set(self._format_label_value("active_sd", active_raw))
        if self.current_print_start_ts:
            self.print_start_var.set(self._format_label_value("start_time", time.strftime("%H:%M:%S", time.localtime(self.current_print_start_ts))))
        else:
            self.print_start_var.set(self._format_label_value("start_time", "-"))
        self._update_known_print_time_label()
        if not self.files_status_var.get() or self.files_status_var.get() == "Выбери G-code или прошивку.":
            self.files_status_var.set(self._t("choose_gcode_or_firmware"))
        if self.pending_flash_finalize:
            source_name = str(self.pending_flash_finalize.get("source_name", "mksLite.bin"))
            self.files_status_var.set(self._t("files_status_flash_pending").format(source=source_name))
        if not self._port():
            self.port_display_var.set(self._t("not_connected"))

    def _on_language_selected(self, _event=None) -> None:
        display = self.lang_display_var.get().strip()
        for label, code in LANG_CHOICES:
            if label == display:
                self.lang_var.set(code)
                break
        self._apply_language()
        self._save_ui_state()

    def _on_close(self) -> None:
        self.monitor_enabled = False
        self.auto_sd_refresh_after_port = None
        self._save_ui_state()
        self.port_var.set("")
        try:
            if self.serial_lock.acquire(timeout=0.4):
                self.serial_lock.release()
        except Exception:
            pass
        self.root.destroy()

    def _on_views_tab_changed(self, _event=None) -> None:
        self._save_ui_state()

    def _format_fw_line(self, raw_line: str) -> str:
        line = raw_line.strip()
        if line.startswith("FIRMWARE_NAME:"):
            line = line.replace("FIRMWARE_NAME:", "Firmware: ", 1)
        if "(" in line and line.count("(") > line.count(")"):
            line = line + (")" * (line.count("(") - line.count(")")))
        close_idx = line.rfind(")")
        if close_idx != -1:
            line = line[: close_idx + 1]
        return line

    def _selected_firmware_profile_label(self) -> str:
        name = Path(self.firmware_var.get().strip()).name
        entry = LH_FIRMWARE_CATALOG.get(name)
        return entry["label"] if entry else name

    def _infer_lh_firmware_identity(self) -> str:
        direct = LH_M115_RE.search(self.last_m115_raw)
        if direct:
            return direct.group(1).strip()

        marlin_ver = None
        m = MARLIN_VER_RE.search(self.last_m115_raw)
        if m:
            marlin_ver = m.group(1)

        m92 = None
        mm = M92_RE.search(self.last_m503_raw)
        if mm:
            m92 = tuple(float(mm.group(i)) for i in range(1, 5))

        if marlin_ver:
            for entry in LH_FIRMWARE_CATALOG.values():
                if entry.get("marlin") != marlin_ver:
                    continue
                expected = entry.get("m92")
                if expected is None:
                    return entry["label"]
                if m92 and all(abs(a - b) < 0.01 for a, b in zip(m92, expected)):
                    return entry["label"]

        if m92:
            if abs(m92[2] - 1167.0) < 0.01 and abs(m92[3] - 1040.0) < 0.01:
                return "LH v2 AutoFan45 FAN1 Z1167"
            if abs(m92[2] - 606.0) < 0.01 and abs(m92[3] - 1040.0) < 0.01:
                return "LH v1 AutoFan45 FAN1 Z606"

        return self.last_fw_identity or "LH ?"

    def _refresh_fw_identity(self) -> None:
        self.last_fw_identity = self._infer_lh_firmware_identity()

    def _normalized_geometry(self, geometry: str) -> str:
        match = re.match(r"^(\d+)x(\d+)([+-]\d+)([+-]\d+)$", geometry.strip())
        screen_w = max(1280, int(self.root.winfo_screenwidth() or 0))
        screen_h = max(720, int(self.root.winfo_screenheight() or 0))
        min_w, min_h = 1080, 680
        default_w, default_h = 1280, 780
        if not match:
            w = min(default_w, screen_w)
            h = min(default_h, screen_h)
            x = max(0, (screen_w - w) // 2)
            y = max(0, (screen_h - h) // 3)
            return f"{w}x{h}+{x}+{y}"

        w = max(min_w, min(int(match.group(1)), screen_w))
        h = max(min_h, min(int(match.group(2)), screen_h))
        x = int(match.group(3))
        y = int(match.group(4))
        x = min(max(0, x), max(0, screen_w - w))
        y = min(max(0, y), max(0, screen_h - h))
        return f"{w}x{h}+{x}+{y}"

    def _draw_temp_graph(self) -> None:
        c = self.temp_canvas
        colors = self.colors
        c.configure(bg=colors["panel"], highlightbackground=colors["border"])
        c.delete("all")

        width = max(int(c.winfo_width() or 0), int(c.cget("width")))
        height = max(int(c.winfo_height() or 0), int(c.cget("height")))
        left, right = 32, width - 8
        top, bottom = 8, height - 18
        plot_w = max(20, right - left)
        plot_h = max(20, bottom - top)

        c.create_rectangle(left, top, right, bottom, outline=colors["border"], width=1)

        if not self.temp_history:
            for frac, label in ((0.0, "0"), (0.5, "125"), (1.0, "250")):
                y = bottom - int(plot_h * frac)
                c.create_line(left, y, right, y, fill="#22372d")
                c.create_text(18, y, text=label, fill=colors["muted"], font=("DejaVu Sans", 8))
            c.create_text(width // 2, height // 2, text=self._t("wait_m105"), fill=colors["muted"], font=("DejaVu Sans", 10))
            return

        now = time.time()
        t1 = now
        t0 = max(0.0, t1 - TEMP_GRAPH_WINDOW_SEC)
        data = [row for row in self.temp_history if row[0] >= t0]
        if not data:
            data = self.temp_history[-1:]
            t0 = data[0][0]
            t1 = max(now, t0 + 1e-6)

        scale_cutoff = t1 - TEMP_GRAPH_SCALE_RECENT_SEC
        scale_data = [row for row in data if row[0] >= scale_cutoff]
        if not scale_data:
            scale_data = data

        series = [temp for _ts, current, target in scale_data for temp in (current, target) if temp > 0.0]
        if not series:
            series = [temp for _ts, current, _target in scale_data for temp in (current,)]
        vmin = min(series)
        vmax = max(series)
        span = max(8.0, vmax - vmin)
        pad = max(2.0, span * 0.18)
        graph_min = max(0.0, vmin - pad)
        graph_max = min(260.0, vmax + pad)
        if (graph_max - graph_min) < 8.0:
            center = (graph_max + graph_min) / 2.0
            graph_min = max(0.0, center - 4.0)
            graph_max = min(260.0, center + 4.0)

        for frac, label_value in ((0.0, graph_min), (0.5, (graph_min + graph_max) / 2.0), (1.0, graph_max)):
            y = bottom - int(plot_h * frac)
            c.create_line(left, y, right, y, fill="#22372d")
            c.create_text(18, y, text=f"{label_value:.0f}", fill=colors["muted"], font=("DejaVu Sans", 8))

        def map_x(ts: float) -> float:
            return left + ((ts - t0) / max(1e-6, (t1 - t0))) * plot_w

        def map_y(temp: float) -> float:
            temp = max(graph_min, min(graph_max, temp))
            return bottom - ((temp - graph_min) / max(1e-6, (graph_max - graph_min))) * plot_h

        target_points: list[float] = []
        temp_points: list[float] = []
        for ts, current, target in data:
            x = map_x(ts)
            temp_points.extend((x, map_y(current)))
            target_points.extend((x, map_y(target)))

        if len(target_points) >= 4:
            c.create_line(*target_points, fill="#d33682", width=1, dash=(4, 2))
        if len(temp_points) >= 4:
            c.create_line(*temp_points, fill="#b58900", width=2)

        current = data[-1][1]
        target = data[-1][2]
        c.create_text(left + 4, height - 7, anchor="w", text=f"{current:.1f}C / {target:.1f}C", fill=colors["text"], font=("DejaVu Sans", 9, "bold"))
        c.create_text(right - 4, height - 7, anchor="e", text="15 min", fill=colors["muted"], font=("DejaVu Sans", 8))

    def _apply_theme(self) -> None:
        colors = {
            "bg": "#0b1410",
            "panel": "#122019",
            "panel_alt": "#183025",
            "field": "#0f1713",
            "field_alt": "#0d1511",
            "text": "#d7f6df",
            "muted": "#87b896",
            "accent": "#43c86a",
            "accent_active": "#66e48d",
            "border": "#284337",
        }
        self.colors = colors

        default_font = tkfont.nametofont("TkDefaultFont")
        default_font.configure(family="DejaVu Sans", size=10)
        text_font = tkfont.nametofont("TkTextFont")
        text_font.configure(family="DejaVu Sans Mono", size=10)

        self.root.configure(bg=colors["bg"])
        style = ttk.Style()
        style.theme_use("clam")

        style.configure(".", background=colors["bg"], foreground=colors["text"])
        style.configure("TFrame", background=colors["bg"])
        style.configure("TPanedwindow", background=colors["bg"])
        style.configure("TLabelframe", background=colors["panel"], bordercolor=colors["border"], relief="solid")
        style.configure("TLabelframe.Label", background=colors["panel"], foreground=colors["accent"], font=("DejaVu Sans", 10, "bold"))
        style.configure("TLabel", background=colors["bg"], foreground=colors["text"])
        style.configure("TSeparator", background=colors["border"])
        style.configure(
            "TEntry",
            fieldbackground=colors["field"],
            foreground=colors["text"],
            insertcolor=colors["accent"],
            bordercolor=colors["border"],
            lightcolor=colors["border"],
            darkcolor=colors["border"],
        )
        style.configure(
            "TCombobox",
            fieldbackground=colors["field"],
            background=colors["field"],
            foreground=colors["text"],
            arrowcolor=colors["accent"],
            bordercolor=colors["border"],
            lightcolor=colors["border"],
            darkcolor=colors["border"],
            insertcolor=colors["accent"],
        )
        style.map(
            "TCombobox",
            fieldbackground=[("readonly", colors["field"])],
            background=[("readonly", colors["field"])],
            foreground=[("readonly", colors["text"])],
            arrowcolor=[("readonly", colors["accent"]), ("active", colors["accent_active"])],
        )
        style.configure(
            "TButton",
            background=colors["panel_alt"],
            foreground=colors["text"],
            bordercolor=colors["border"],
            lightcolor=colors["border"],
            darkcolor=colors["border"],
            padding=6,
            focusthickness=1,
            focuscolor=colors["accent"],
        )
        style.map(
            "TButton",
            background=[("active", colors["accent"]), ("pressed", colors["accent_active"])],
            foreground=[("active", colors["field"]), ("pressed", colors["field"])],
        )
        style.configure(
            "TRadiobutton",
            background=colors["panel"],
            foreground=colors["text"],
            indicatorcolor=colors["field"],
        )
        style.map(
            "TRadiobutton",
            background=[("active", colors["panel_alt"])],
            foreground=[("active", colors["accent"])],
        )
        style.configure(
            "TProgressbar",
            background=colors["accent"],
            troughcolor=colors["field"],
            bordercolor=colors["border"],
            lightcolor=colors["accent"],
            darkcolor=colors["accent"],
        )
        style.configure(
            "LH.Horizontal.TProgressbar",
            background=colors["accent"],
            troughcolor=colors["field"],
            bordercolor=colors["border"],
            lightcolor=colors["accent"],
            darkcolor=colors["accent"],
            thickness=24,
        )
        style.configure(
            "Vertical.TScrollbar",
            background=colors["panel_alt"],
            troughcolor=colors["field"],
            bordercolor=colors["border"],
            arrowcolor=colors["accent"],
        )
        style.configure(
            "LH.TNotebook",
            background=colors["panel"],
            borderwidth=0,
            relief="flat",
            bordercolor=colors["border"],
            lightcolor=colors["border"],
            darkcolor=colors["border"],
            tabmargins=(2, 2, 2, 0),
        )
        style.configure(
            "LH.TNotebook.Tab",
            background="#16261f",
            foreground="#bdd7c5",
            bordercolor=colors["border"],
            lightcolor=colors["border"],
            darkcolor=colors["border"],
            padding=(12, 4),
            font=("DejaVu Sans", 9, "bold"),
        )
        style.map(
            "LH.TNotebook.Tab",
            background=[
                ("selected", "#20352b"),
                ("active", "#1b2d24"),
            ],
            foreground=[
                ("selected", "#dbeadf"),
                ("active", "#d1e3d7"),
            ],
            padding=[
                ("selected", (14, 7)),
                ("active", (12, 5)),
            ],
            font=[
                ("selected", ("DejaVu Sans", 11, "bold")),
                ("active", ("DejaVu Sans", 10, "bold")),
            ],
        )
        style.configure("NotebookPage.TFrame", background=colors["panel"])

        for sd_listbox in (self.sd_print_listbox,):
            sd_listbox.configure(
                bg=colors["field"],
                fg=colors["text"],
                selectbackground=colors["accent"],
                selectforeground=colors["field"],
                highlightbackground=colors["border"],
                highlightcolor=colors["accent"],
                relief="solid",
                borderwidth=1,
            )
        self.sd_notice_label.configure(
            bg=colors["panel"],
            fg=colors["muted"],
            font=("DejaVu Sans", 9),
        )
        self.log_text.configure(
            bg=colors["field"],
            fg=colors["text"],
            insertbackground=colors["accent"],
            selectbackground=colors["accent"],
            selectforeground=colors["field"],
            highlightbackground=colors["field"],
            highlightcolor=colors["field"],
            highlightthickness=0,
            relief="flat",
            borderwidth=0,
        )
        self.metrics_text.configure(
            bg=colors["field_alt"],
            fg=colors["text"],
            insertbackground=colors["accent"],
            selectbackground=colors["accent"],
            selectforeground=colors["field"],
            highlightbackground=colors["field_alt"],
            highlightcolor=colors["field_alt"],
            highlightthickness=0,
            relief="flat",
            borderwidth=0,
        )
        self.live_text.configure(
            bg=colors["field_alt"],
            fg=colors["text"],
            insertbackground=colors["accent"],
            selectbackground=colors["accent"],
            selectforeground=colors["field"],
            highlightbackground=colors["border"],
            highlightcolor=colors["accent"],
            relief="solid",
            borderwidth=1,
        )
        self.temp_status_label.configure(
            bg=colors["field_alt"],
            fg=colors["text"],
            highlightbackground=colors["border"],
            highlightcolor=colors["accent"],
            relief="solid",
            borderwidth=1,
        )
        self.left_split.configure(bg=colors["border"])
        self.temp_canvas.configure(bg=colors["panel"], highlightbackground=colors["border"], highlightcolor=colors["accent"], relief="solid", borderwidth=1)
        self.progress_wrap.configure(bg=colors["field_alt"], highlightbackground=colors["border"], highlightcolor=colors["accent"], highlightthickness=1)
        self.progress_label.configure(bg=colors["field_alt"], fg=colors["text"], font=("DejaVu Sans", 9, "bold"))
        try:
            self.root.option_add("*TCombobox*Listbox*Background", colors["field"])
            self.root.option_add("*TCombobox*Listbox*Foreground", colors["text"])
            self.root.option_add("*TCombobox*Listbox*selectBackground", colors["accent"])
            self.root.option_add("*TCombobox*Listbox*selectForeground", colors["field"])
        except Exception:
            pass
        for widget in (self.log_text, self.metrics_text):
            try:
                widget.frame.configure(bg=colors["panel"], bd=0, highlightthickness=0, relief="flat")
            except Exception:
                pass
            try:
                widget.vbar.configure(
                    background=colors["panel_alt"],
                    troughcolor=colors["field"],
                    activebackground=colors["accent"],
                    highlightbackground=colors["border"],
                    highlightcolor=colors["accent"],
                    bd=0,
                    relief="flat",
                )
            except Exception:
                pass
        self._draw_corner_hands()
        self._draw_temp_graph()
        self._render_live_status()

    def _build_ui(self) -> None:
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)

        top = ttk.Frame(self.root, padding=10)
        top.grid(row=0, column=0, sticky="ew")
        top.columnconfigure(0, weight=1)
        top.columnconfigure(1, weight=0)

        top_left = ttk.Frame(top)
        top_left.grid(row=0, column=0, sticky="ew")
        top_left.columnconfigure(0, weight=1)

        conn = ttk.Frame(top_left)
        conn.grid(row=0, column=0, sticky="ew")
        conn.columnconfigure(6, weight=1)
        self.port_label = ttk.Label(conn, text="Port")
        self.port_label.grid(row=0, column=0, sticky="w")
        self.port_combo = ttk.Combobox(conn, textvariable=self.port_display_var, width=28, state="readonly")
        self.port_combo.grid(row=0, column=1, padx=(4, 6), sticky="ew")
        self.port_combo.bind("<<ComboboxSelected>>", lambda _event: self._on_port_selected())
        self.find_port_button = ttk.Button(conn, text="Найти", command=self.detect_printer_port_action)
        self.find_port_button.grid(row=0, column=2, padx=(0, 8), sticky="ew")
        self.disconnect_port_button = ttk.Button(conn, text="Откл.", command=self.disconnect_port)
        self.disconnect_port_button.grid(row=0, column=3, padx=(0, 8), sticky="ew")
        self.lang_label = ttk.Label(conn, text="Язык")
        self.lang_label.grid(row=0, column=4, sticky="w", padx=(0, 4))
        self.lang_combo = ttk.Combobox(conn, textvariable=self.lang_display_var, width=6, state="readonly")
        self.lang_combo["values"] = [label for label, _code in LANG_CHOICES]
        self.lang_combo.grid(row=0, column=5, padx=(0, 8), sticky="ew")
        self.lang_combo.bind("<<ComboboxSelected>>", self._on_language_selected)
        self.temp_status_label = tk.Label(conn, textvariable=self.header_marquee_var, anchor="w", padx=6)
        self.temp_status_label.grid(row=0, column=6, padx=(12, 0), sticky="ew")

        self.files_window: tk.Toplevel | None = None

        actions = ttk.Frame(top_left)
        actions.grid(row=1, column=0, sticky="ew", pady=(6, 0))
        for idx in range(5):
            actions.columnconfigure(idx, weight=1)
        self.files_fw_button = ttk.Button(actions, text="Файлы и прошивка", command=self.show_files_firmware_window)
        self.files_fw_button.grid(row=0, column=0, padx=3, sticky="ew")
        self.action_widgets.append(self.files_fw_button)
        self.manual_button = ttk.Button(actions, text="Manual", command=self.show_manual)
        self.manual_button.grid(row=0, column=1, padx=3, sticky="ew")
        self.action_widgets.append(self.manual_button)
        self.reset_usb_button = ttk.Button(actions, text="Сброс USB", command=self.reset_usb_session)
        self.reset_usb_button.grid(row=0, column=2, padx=3, sticky="ew")
        self.action_widgets.append(self.reset_usb_button)
        self.export_cura_button = ttk.Button(actions, text="Экспорт профиля Cura", command=self.export_cura_bundle)
        self.export_cura_button.grid(row=0, column=3, padx=3, sticky="ew")
        self.action_widgets.append(self.export_cura_button)
        self.pc_sound_button = ttk.Button(actions, text="Звук ПК", command=self.play_computer_melody_button)
        self.pc_sound_button.grid(row=0, column=4, padx=3, sticky="ew")
        self.action_widgets.append(self.pc_sound_button)

        substatus = ttk.Frame(top_left)
        substatus.grid(row=2, column=0, sticky="ew", pady=(6, 0))
        substatus.columnconfigure(0, weight=1)
        substatus.columnconfigure(1, weight=0)
        toggles = ttk.Frame(substatus)
        toggles.grid(row=0, column=0, columnspan=2, sticky="ew")
        self.pc_sound_check = ttk.Checkbutton(toggles, text="Звук окончания печати ПК", variable=self.computer_melody_on_complete_var)
        self.pc_sound_check.pack(side="left")
        self.progress_wrap = tk.Frame(substatus, bd=0, highlightthickness=0)
        self.progress_wrap.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        self.progress_wrap.columnconfigure(0, weight=1)
        self.progress_wrap.configure(height=30)
        self.progress_bar = ttk.Progressbar(self.progress_wrap, orient="horizontal", mode="determinate", maximum=100, style="LH.Horizontal.TProgressbar")
        self.progress_bar.grid(row=0, column=0, sticky="ew")
        self.progress_label = tk.Label(self.progress_wrap, textvariable=self.progress_var, anchor="center", bd=0, padx=6)
        self.progress_label.place(relx=0.5, rely=0.5, anchor="center")
        self.cancel_upload_button = ttk.Button(substatus, text="Отменить", command=self.cancel_upload)
        self.cancel_upload_button.grid(row=1, column=1, sticky="e", padx=(8, 0), pady=(8, 0))
        self.cancel_upload_button.grid_remove()

        self.hands_canvas = tk.Canvas(top, width=108, height=64, bd=0, highlightthickness=0)
        self.hands_canvas.grid(row=0, column=1, sticky="ne", padx=(8, 0))

        self.main_pane = ttk.Panedwindow(self.root, orient="horizontal")
        self.main_pane.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))

        left = ttk.Frame(self.main_pane, padding=6)
        left.columnconfigure(0, weight=1)
        left.rowconfigure(0, weight=1)
        self.main_pane.add(left, weight=1)

        right = ttk.Frame(self.main_pane, padding=6)
        right.columnconfigure(0, weight=1)
        self.main_pane.add(right, weight=4)

        graph = ttk.Frame(right, padding=8, height=340)
        graph.columnconfigure(0, weight=1)
        graph.rowconfigure(1, weight=1)
        graph.grid_propagate(False)
        self.temp_graph_label = ttk.Label(graph, text="Температура hotend")
        self.temp_graph_label.grid(row=0, column=0, sticky="w", pady=(0, 6))
        self.temp_canvas = tk.Canvas(graph, width=760, height=280, bd=0, highlightthickness=1)
        self.temp_canvas.grid(row=1, column=0, sticky="nsew")
        self.temp_canvas.bind("<Configure>", lambda _event: self._draw_temp_graph())

        self.left_split = tk.PanedWindow(left, orient="vertical", sashwidth=6, bd=0, opaqueresize=True)
        self.left_split.grid(row=0, column=0, sticky="nsew")

        live_frame = ttk.LabelFrame(self.left_split, text="Параметры в реальном времени", padding=8)
        self.live_frame = live_frame
        live_frame.columnconfigure(0, weight=1)
        live_frame.rowconfigure(0, weight=1)

        self.live_text = tk.Text(live_frame, height=10, wrap="word")
        self.live_text.grid(row=0, column=0, sticky="nsew")
        self.live_text.configure(state="disabled")

        sd_frame = ttk.LabelFrame(self.left_split, text="Файлы на SD принтера", padding=8)
        self.sd_frame = sd_frame
        sd_frame.columnconfigure(0, weight=1)
        sd_frame.columnconfigure(1, weight=0)
        sd_frame.rowconfigure(6, weight=1)

        ttk.Label(sd_frame, textvariable=self.selected_sd_var).grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(sd_frame, textvariable=self.active_sd_var).grid(row=1, column=0, columnspan=2, sticky="w", pady=(2, 0))
        ttk.Label(sd_frame, textvariable=self.print_start_var).grid(row=2, column=0, columnspan=2, sticky="w", pady=(2, 0))
        ttk.Label(sd_frame, textvariable=self.print_known_time_var).grid(row=3, column=0, columnspan=2, sticky="w", pady=(2, 0))
        self.sd_notice_label = tk.Label(sd_frame, textvariable=self.sd_notice_var, anchor="w", justify="left", wraplength=320)
        self.sd_notice_label.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(4, 0))

        self.sd_printable_label = ttk.Label(sd_frame, text="Файлы для печати")
        self.sd_printable_label.grid(row=5, column=0, sticky="w", pady=(6, 0))
        self.sd_print_listbox = tk.Listbox(sd_frame, height=4, exportselection=False)
        self.sd_print_listbox.grid(row=6, column=0, sticky="nsew", pady=(4, 0))
        self.sd_print_listbox.bind("<Double-1>", lambda _event: self.start_selected_print_with_home())
        self.sd_print_listbox.bind("<<ListboxSelect>>", lambda _event: self._on_sd_listbox_select("print"))
        sd_print_scroll = ttk.Scrollbar(sd_frame, orient="vertical", command=self.sd_print_listbox.yview)
        sd_print_scroll.grid(row=6, column=1, sticky="ns", pady=(4, 0))
        self.sd_print_listbox.configure(yscrollcommand=sd_print_scroll.set)

        buttons = ttk.Frame(sd_frame)
        buttons.grid(row=7, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        for idx in range(3):
            buttons.columnconfigure(idx, weight=1)
        self.refresh_sd_button = ttk.Button(buttons, text="Обновить список", command=self.refresh_sd_files)
        self.refresh_sd_button.grid(row=0, column=0, padx=3, pady=2, sticky="ew")
        self.action_widgets.append(self.refresh_sd_button)
        self.start_print_button = ttk.Button(buttons, text="Старт печати", command=self.start_selected_print_with_home)
        self.start_print_button.grid(row=0, column=1, padx=3, pady=2, sticky="ew")
        self.action_widgets.append(self.start_print_button)
        self.delete_button = ttk.Button(buttons, text="Удалить", command=self.delete_selected_file)
        self.delete_button.grid(row=0, column=2, padx=3, pady=2, sticky="ew")
        self.action_widgets.append(self.delete_button)
        self.pause_button = ttk.Button(buttons, text="Пауза", command=self.pause_print)
        self.pause_button.grid(row=1, column=0, padx=3, pady=2, sticky="ew")
        self.action_widgets.append(self.pause_button)
        self.resume_button = ttk.Button(buttons, text="Продолжить", command=self.resume_print)
        self.resume_button.grid(row=1, column=1, padx=3, pady=2, sticky="ew")
        self.action_widgets.append(self.resume_button)
        self.stop_button = ttk.Button(buttons, text="Стоп", command=self.stop_print)
        self.stop_button.grid(row=1, column=2, padx=3, pady=2, sticky="ew")
        self.action_widgets.append(self.stop_button)
        self.left_split.add(live_frame, stretch="always", minsize=180)
        self.left_split.add(sd_frame, stretch="always", minsize=120)

        graph.grid(row=0, column=0, sticky="ew")
        right.rowconfigure(1, weight=1)

        controls_and_views = ttk.Frame(right)
        controls_and_views.columnconfigure(0, weight=1)
        controls_and_views.rowconfigure(1, weight=1)
        controls_and_views.grid(row=1, column=0, sticky="nsew", pady=(10, 0))

        controls = ttk.Frame(controls_and_views)
        controls.grid(row=0, column=0, sticky="ew")
        controls.columnconfigure(0, weight=1)
        controls.columnconfigure(1, weight=1)

        motion = ttk.LabelFrame(controls, text="Ручное управление", padding=6)
        self.motion_frame = motion
        motion.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        for idx in range(4):
            motion.columnconfigure(idx, weight=1)

        self.save_start_button = ttk.Button(motion, text="Запомнить старт", command=self.set_current_home_zero)
        self.save_start_button.grid(row=0, column=0, padx=2, pady=2, sticky="ew")
        self.action_widgets.append(self.save_start_button)
        self.go_start_button = ttk.Button(motion, text="К старту", command=self.go_print_home)
        self.go_start_button.grid(row=0, column=1, padx=2, pady=2, sticky="ew")
        self.action_widgets.append(self.go_start_button)
        self.motors_off_button = ttk.Button(motion, text="Моторы выкл", command=self.motor_off)
        self.motors_off_button.grid(row=0, column=2, columnspan=2, padx=2, pady=2, sticky="ew")
        self.action_widgets.append(self.motors_off_button)

        self.step_label = ttk.Label(motion, text="Шаг")
        self.step_label.grid(row=1, column=0, sticky="w", pady=(2, 1))
        step_box = ttk.Frame(motion)
        step_box.grid(row=1, column=1, columnspan=3, sticky="w", pady=(2, 1))
        for value in JOG_STEPS_MM:
            ttk.Radiobutton(step_box, text=str(value), value=value, variable=self.step_var).pack(side="left", padx=2)

        self.head_left_button = ttk.Button(motion, text="Голова влево", command=lambda: self.jog_axis("X", -self.step_var.get()))
        self.head_left_button.grid(row=2, column=0, padx=2, pady=2, sticky="ew")
        self.action_widgets.append(self.head_left_button)
        self.head_right_button = ttk.Button(motion, text="Голова вправо", command=lambda: self.jog_axis("X", self.step_var.get()))
        self.head_right_button.grid(row=2, column=1, padx=2, pady=2, sticky="ew")
        self.action_widgets.append(self.head_right_button)
        self.bed_away_button = ttk.Button(motion, text="Стол от себя", command=lambda: self.jog_axis("Y", -self.step_var.get()))
        self.bed_away_button.grid(row=2, column=2, padx=2, pady=2, sticky="ew")
        self.action_widgets.append(self.bed_away_button)
        self.bed_toward_button = ttk.Button(motion, text="Стол к себе", command=lambda: self.jog_axis("Y", self.step_var.get()))
        self.bed_toward_button.grid(row=2, column=3, padx=2, pady=2, sticky="ew")
        self.action_widgets.append(self.bed_toward_button)
        self.head_down_button = ttk.Button(motion, text="Голова вниз", command=lambda: self.jog_axis("Z", -self.step_var.get()))
        self.head_down_button.grid(row=3, column=0, padx=2, pady=2, sticky="ew")
        self.action_widgets.append(self.head_down_button)
        self.head_up_button = ttk.Button(motion, text="Голова вверх", command=lambda: self.jog_axis("Z", self.step_var.get()))
        self.head_up_button.grid(row=3, column=1, padx=2, pady=2, sticky="ew")
        self.action_widgets.append(self.head_up_button)
        self.hard_stop_button = ttk.Button(motion, text="Жёсткий стоп", command=self.hard_stop)
        self.hard_stop_button.grid(row=3, column=2, columnspan=2, padx=2, pady=2, sticky="ew")
        self.action_widgets.append(self.hard_stop_button)

        level = ttk.LabelFrame(controls, text="Калибровка стола", padding=6)
        self.level_frame = level
        level.grid(row=0, column=1, sticky="nsew", padx=(5, 0))
        for idx in range(3):
            level.columnconfigure(idx, weight=1)

        self.level_points_label = ttk.Label(level, text="Точки X/Y")
        self.level_points_label.grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 2))
        ttk.Button(level, text="ПЛ", command=lambda: self.move_level_point(5, 5)).grid(row=1, column=0, padx=2, pady=2, sticky="ew")
        ttk.Button(level, text="Ц", command=lambda: self.move_level_point(45, 45)).grid(row=1, column=1, padx=2, pady=2, sticky="ew")
        ttk.Button(level, text="ПП", command=lambda: self.move_level_point(95, 5)).grid(row=1, column=2, padx=2, pady=2, sticky="ew")
        ttk.Button(level, text="ЗЛ", command=lambda: self.move_level_point(5, 95)).grid(row=2, column=0, padx=2, pady=2, sticky="ew")
        ttk.Button(level, text="ЗП", command=lambda: self.move_level_point(95, 95)).grid(row=2, column=2, padx=2, pady=2, sticky="ew")

        self.views = ttk.Notebook(controls_and_views, style="LH.TNotebook")
        self.views.grid(row=1, column=0, sticky="nsew", pady=(10, 0))

        self.metrics_frame = ttk.Frame(self.views, padding=8, style="NotebookPage.TFrame")
        self.metrics_frame.columnconfigure(0, weight=1)
        self.metrics_frame.rowconfigure(1, weight=1)
        metrics_buttons = ttk.Frame(self.metrics_frame)
        metrics_buttons.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        self.capture_metrics_button = ttk.Button(metrics_buttons, text="Снять все метрики", command=self.refresh_metrics)
        self.capture_metrics_button.pack(side="left")
        self.save_log_button = ttk.Button(metrics_buttons, text="Сохранить лог", command=self.save_log_snapshot)
        self.save_log_button.pack(side="left", padx=(8, 0))
        self.metrics_text = ScrolledText(self.metrics_frame, wrap="word", height=18)
        self.metrics_text.grid(row=1, column=0, sticky="nsew")
        self.metrics_text.configure(state="disabled")

        self.log_frame = ttk.Frame(self.views, padding=8, style="NotebookPage.TFrame")
        self.log_frame.columnconfigure(0, weight=1)
        self.log_frame.rowconfigure(0, weight=1)
        self.log_text = ScrolledText(self.log_frame, wrap="word", height=18)
        self.log_text.grid(row=0, column=0, sticky="nsew")
        self.log_text.configure(state="disabled")
        self.views.add(self.log_frame, text="Журнал")
        self.views.add(self.metrics_frame, text="USB-метрики")
        self.views.select(self.log_frame)

    def _apply_language(self) -> None:
        current_lang = self.lang_var.get().strip() or "ru"
        display = next((label for label, code in LANG_CHOICES if code == current_lang), "RU")
        self.lang_display_var.set(display)

        self.lang_label.configure(text=self._t("language"))
        self.find_port_button.configure(text=self._t("find"))
        self.disconnect_port_button.configure(text=self._t("disconnect"))
        self.files_fw_button.configure(text=self._t("files_and_firmware"))
        self.manual_button.configure(text=self._t("manual"))
        self.reset_usb_button.configure(text=self._t("reset_usb"))
        self.export_cura_button.configure(text=self._t("export_cura"))
        self.pc_sound_button.configure(text=self._t("sound_pc_short"))
        self.pc_sound_check.configure(text=self._t("sound_pc_complete"))
        if self.cancel_upload_button is not None:
            self.cancel_upload_button.configure(text=self._t("cancel_upload"))
        self.temp_graph_label.configure(text=self._t("temp_graph"))
        self.live_frame.configure(text=self._t("live_params"))
        self.sd_frame.configure(text=self._t("sd_files"))
        self.sd_printable_label.configure(text=self._t("printable_files"))
        self.refresh_sd_button.configure(text=self._t("refresh_list"))
        self.start_print_button.configure(text=self._t("start_print"))
        self.delete_button.configure(text=self._t("delete"))
        self.pause_button.configure(text=self._t("pause"))
        self.resume_button.configure(text=self._t("resume"))
        self.stop_button.configure(text=self._t("stop"))
        self.motion_frame.configure(text=self._t("manual_controls"))
        self.save_start_button.configure(text=self._t("save_start"))
        self.go_start_button.configure(text=self._t("go_start"))
        self.motors_off_button.configure(text=self._t("motors_off"))
        self.step_label.configure(text=self._t("step"))
        self.head_left_button.configure(text=self._t("head_left"))
        self.head_right_button.configure(text=self._t("head_right"))
        self.bed_away_button.configure(text=self._t("bed_away"))
        self.bed_toward_button.configure(text=self._t("bed_toward"))
        self.head_down_button.configure(text=self._t("head_down"))
        self.head_up_button.configure(text=self._t("head_up"))
        self.hard_stop_button.configure(text=self._t("hard_stop"))
        self.level_frame.configure(text=self._t("bed_level"))
        self.level_points_label.configure(text=self._t("level_points"))
        self.capture_metrics_button.configure(text=self._t("capture_metrics"))
        self.save_log_button.configure(text=self._t("save_log"))
        self.views.tab(self.log_frame, text=self._t("journal"))
        self.views.tab(self.metrics_frame, text=self._t("usb_metrics"))
        if self.files_window and self.files_window.winfo_exists():
            self.files_window.title(self._t("files_window_title"))
        if self.files_window_content and self.files_window_content.winfo_exists():
            self.files_window_content.configure(text=self._t("files_and_firmware"))
            self._populate_files_firmware_container(self.files_window_content)
        if self.manual_window and self.manual_window.winfo_exists():
            self.manual_window.title(self._t("manual_title"))
        if self.manual_text_widget and self.manual_text_widget.winfo_exists():
            self.manual_text_widget.configure(state="normal")
            self.manual_text_widget.delete("1.0", "end")
            self.manual_text_widget.insert("1.0", MANUAL_TEXTS.get(current_lang, MANUAL_TEXT))
            self.manual_text_widget.configure(state="disabled")
        self._refresh_translated_strings()
        if hasattr(self, "colors"):
            self._draw_temp_graph()

    def log(self, message: str) -> None:
        cleaned_lines: list[str] = []
        for raw_line in str(message).splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if line.lower() == "ok":
                continue
            cleaned_lines.append(line)
        if not cleaned_lines:
            return
        message = "\n".join(cleaned_lines)
        timestamp = time.strftime("%H:%M:%S")
        line = f"{timestamp} {message}"
        self.log_text.configure(state="normal")
        self.log_text.insert("end", line + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")
        self._append_ring_log(line)
        lowered = message.lower()
        if (
            not self.printer_halted
            and (
                "printer halted" in lowered
                or "kill() called" in lowered
                or "homing failed" in lowered
                or "bad x endstop" in lowered
            )
        ):
            self.printer_halted = True
            self.busy_var.set("USB: printer halted")
            messagebox.showwarning(
                "Little Hands",
                "Прошивка остановила принтер (Printer halted / Homing Failed).\n"
                "Нужен power cycle: выключи принтер по питанию на 5–10 секунд и включи снова.",
            )

    def _append_ring_log(self, line: str) -> None:
        payload = (line.rstrip() + "\n").encode("utf-8", "replace")
        with self.log_file_lock:
            with RUNTIME_LOG_PATH.open("ab") as fh:
                fh.write(payload)
            size = RUNTIME_LOG_PATH.stat().st_size
            if size <= RUNTIME_LOG_MAX_BYTES:
                return
            keep = min(RUNTIME_LOG_MAX_BYTES, size)
            with RUNTIME_LOG_PATH.open("rb") as fh:
                fh.seek(-keep, 2)
                data = fh.read()
            nl = data.find(b"\n")
            if 0 <= nl < len(data) - 1:
                data = data[nl + 1 :]
            with RUNTIME_LOG_PATH.open("wb") as fh:
                fh.write(data)

    def _format_local_datetime(self, stamp: float) -> str:
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(stamp))

    def _format_duration_ru(self, seconds: float) -> str:
        total = max(0, int(round(seconds)))
        hours, remainder = divmod(total, 3600)
        minutes, secs = divmod(remainder, 60)
        if hours:
            return f"{hours} ч {minutes:02d} мин {secs:02d} с"
        if minutes:
            return f"{minutes} мин {secs:02d} с"
        return f"{secs} с"

    def _format_duration_short(self, seconds: float) -> str:
        total = max(0, int(round(seconds)))
        hours, remainder = divmod(total, 3600)
        minutes, secs = divmod(remainder, 60)
        if hours:
            return f"{hours}:{minutes:02d}:{secs:02d}"
        return f"{minutes}:{secs:02d}"

    def _record_temp_point(self, current: float, target: float) -> None:
        now = time.time()
        self.temp_history.append((now, current, target))
        cutoff = now - (TEMP_GRAPH_WINDOW_SEC + 60)
        self.temp_history = [row for row in self.temp_history if row[0] >= cutoff]
        self._draw_temp_graph()

    def _refresh_header_from_cache(self) -> None:
        now = time.time()
        if self.last_temp_current is not None and (now - self.last_temp_sample_ts) <= 4.0:
            self.temp_var.set(f"Hotend: {self.last_temp_current:.2f} / {self.last_temp_target or 0.0:.2f} C")
        elif self.last_temp_current is None:
            self.temp_var.set("Hotend: ? / ? C")

        if self.last_sd_summary and (now - self.last_sd_sample_ts) <= 8.0:
            self.sd_var.set(self.last_sd_summary)
        elif not self.sd_var.get():
            self.sd_var.set("SD: unknown")

        self.fw_var.set(f"FW: {self.last_fw_identity}" if self.last_fw_identity else "")
        self.header_marquee_source = "   •   ".join(
            part for part in (
                self.temp_var.get().strip(),
                self.sd_var.get().strip(),
                self.fw_var.get().strip(),
                self.busy_var.get().strip(),
            ) if part
        )
        self._render_live_status()
        self.root.after(500, self._refresh_header_from_cache)

    def _set_pending_flash_finalize(self, source_name: str) -> None:
        self.pending_flash_finalize = {
            "source_name": source_name,
            "requested_at": time.time(),
        }
        self.eeprom_confirmed = False
        self._save_ui_state()

    def _clear_pending_flash_finalize(self) -> None:
        self.pending_flash_finalize = None
        self._save_ui_state()

    def _tick_header_marquee(self) -> None:
        source = (self.header_marquee_source or "").strip()
        if not source:
            self.header_marquee_var.set("")
            self.root.after(220, self._tick_header_marquee)
            return

        padded = source + "     "
        if len(padded) <= 8:
            self.header_marquee_var.set(source)
            self.root.after(220, self._tick_header_marquee)
            return

        self.header_marquee_offset = (self.header_marquee_offset + 1) % len(padded)
        rolled = padded[self.header_marquee_offset:] + padded[:self.header_marquee_offset]
        self.header_marquee_var.set(rolled)
        self.root.after(220, self._tick_header_marquee)

    def _render_live_status(self) -> None:
        now = time.time()
        lang = self.lang_var.get().strip() or "ru"
        if self.last_temp_current is None:
            temp_line = {"ru": "Hotend: нет данных", "en": "Hotend: no data", "zh": "Hotend：无数据"}[lang]
            age_line = {"ru": "Возраст телеметрии: нет данных", "en": "Telemetry age: no data", "zh": "遥测年龄：无数据"}[lang]
        else:
            stale = (now - self.last_temp_sample_ts) > 4.0
            state = {"ru": ("устарели" if stale else "свежие"), "en": ("stale" if stale else "fresh"), "zh": ("过期" if stale else "正常")}[lang]
            temp_line = f"Hotend: {self.last_temp_current:.2f} / {self.last_temp_target or 0.0:.2f} C"
            age_prefix = {"ru": "Возраст телеметрии", "en": "Telemetry age", "zh": "遥测年龄"}[lang]
            age_line = f"{age_prefix}: {now - self.last_temp_sample_ts:.1f} c ({state})"

        sd_age = f"{now - self.last_sd_sample_ts:.1f} c" if self.last_sd_sample_ts else {"ru": "нет данных", "en": "no data", "zh": "无数据"}[lang]
        heater_line = f"Heater PWM @: {self.last_heater_power if self.last_heater_power is not None else '?'}"
        pos_line = self.last_position_line
        zero_line = {"ru": ("да" if self.session_zero_defined else "нет"), "en": ("yes" if self.session_zero_defined else "no"), "zh": ("是" if self.session_zero_defined else "否")}[lang]
        home_reason = f" ({self.home_trust_reason})" if self.home_trust_reason else ""
        home_line = f"{ {'ru': 'Home', 'en': 'Home', 'zh': 'Home'}[lang] }: {self._home_trust_label()}{home_reason}"
        fw_line = self.last_fw_identity or "-"
        if self.current_print_start_ts:
            self.print_start_var.set(self._format_label_value("start_time", time.strftime('%H:%M:%S', time.localtime(self.current_print_start_ts))))
        else:
            self.print_start_var.set(self._format_label_value("start_time", "-"))
        self._update_known_print_time_label()

        lines = [
            temp_line,
            heater_line,
            f"SD: {self.last_sd_summary}",
            f"{ {'ru': 'Возраст SD-статуса', 'en': 'SD status age', 'zh': 'SD 状态年龄'}[lang] }: {sd_age}",
            self.progress_var.get(),
            f"{ {'ru': 'Файл', 'en': 'File', 'zh': '文件'}[lang] }: {self.current_print_display if self.current_print_display != '-' else self.current_print_file}",
            f"{ {'ru': 'Позиция', 'en': 'Position', 'zh': '位置'}[lang] }: {pos_line}",
            home_line,
            f"{ {'ru': 'Старт сохранён', 'en': 'Start saved', 'zh': '起点已保存'}[lang] }: {zero_line}",
            f"{ {'ru': 'Прошивка', 'en': 'Firmware', 'zh': '固件'}[lang] }: {fw_line}",
            age_line,
        ]
        rendered = "\n".join(lines)
        self.live_text.configure(state="normal")
        self.live_text.delete("1.0", "end")
        self.live_text.insert("1.0", rendered)
        self.live_text.configure(state="disabled")

    def _init_pane_layout(self) -> None:
        try:
            self.root.update_idletasks()
            width = max(self.root.winfo_width(), 1120)
            default_main = max(360, min(int(width * 0.34), 430))
            main_sash = int(self.ui_state.get("main_sash", default_main))
            self.main_pane.sashpos(0, main_sash)
            left_y = int(self.ui_state.get("left_split_y", 415))
            self.left_split.sash_place(0, 0, left_y)
        except Exception:
            pass

    def _populate_files_firmware_container(self, parent) -> None:
        lang = self.lang_var.get().strip() or "ru"
        for child in parent.winfo_children():
            child.destroy()
        self.files_window_content = parent
        parent.columnconfigure(1, weight=1)
        parent.columnconfigure(2, minsize=110)
        parent.columnconfigure(3, minsize=110)

        self.files_gcode_label = ttk.Label(parent, text="G-code")
        self.files_gcode_label.grid(row=0, column=0, sticky="w")
        ttk.Entry(parent, textvariable=self.local_gcode_var).grid(row=0, column=1, columnspan=2, sticky="ew", padx=4)
        self.pick_gcode_button = ttk.Button(parent, text=self._t("pick_gcode"), command=self.pick_gcode)
        self.pick_gcode_button.grid(row=0, column=3, padx=4, sticky="ew")
        self.action_widgets.append(self.pick_gcode_button)

        self.sd_name_label = ttk.Label(parent, text=self._t("sd_name"))
        self.sd_name_label.grid(row=1, column=0, sticky="w")
        ttk.Entry(parent, textvariable=self.dest_name_var).grid(row=1, column=1, columnspan=2, sticky="ew", padx=4)
        self.upload_gcode_button = ttk.Button(parent, text=self._t("upload_gcode"), command=self.upload_gcode)
        self.upload_gcode_button.grid(row=1, column=3, padx=4, sticky="ew")
        self.action_widgets.append(self.upload_gcode_button)

        self.upload_and_start_button = ttk.Button(parent, text=self._t("upload_and_start"), command=self.upload_and_start_gcode)
        self.upload_and_start_button.grid(row=2, column=2, columnspan=2, padx=4, pady=(4, 0), sticky="ew")
        self.action_widgets.append(self.upload_and_start_button)

        self.check_gcode_button = ttk.Button(parent, text=self._t("check_gcode"), command=self.check_gcode_validity)
        self.check_gcode_button.grid(row=2, column=1, padx=4, pady=(4, 0), sticky="ew")
        self.action_widgets.append(self.check_gcode_button)

        ttk.Separator(parent, orient="horizontal").grid(row=3, column=0, columnspan=4, sticky="ew", pady=8)
        self.firmware_label = ttk.Label(parent, text=self._t("firmware"))
        self.firmware_label.grid(row=4, column=0, sticky="w")
        ttk.Entry(parent, textvariable=self.firmware_var).grid(row=4, column=1, columnspan=2, sticky="ew", padx=4)
        self.pick_firmware_button = ttk.Button(parent, text=self._t("pick_gcode"), command=self.pick_firmware)
        self.pick_firmware_button.grid(row=4, column=3, padx=4, sticky="ew")
        self.action_widgets.append(self.pick_firmware_button)

        self.create_eeprom_button = ttk.Button(parent, text=self._t("create_eeprom"), command=self.create_eeprom_via_printer)
        self.create_eeprom_button.grid(row=5, column=1, padx=4, pady=(4, 0), sticky="ew")
        self.action_widgets.append(self.create_eeprom_button)

        self.flash_firmware_button = ttk.Button(parent, text=self._t("flash_firmware"), command=self.flash_firmware)
        self.flash_firmware_button.grid(row=5, column=2, columnspan=2, padx=4, pady=(4, 0), sticky="ew")
        self.action_widgets.append(self.flash_firmware_button)

        self.files_window_status_label = tk.Label(parent, textvariable=self.files_status_var, anchor="w", justify="left", wraplength=700)
        self.files_window_status_label.grid(row=6, column=0, columnspan=4, sticky="ew", pady=(10, 0))
        self.files_window_status_label.configure(bg=self.colors["panel"], fg=self.colors["muted"], font=("DejaVu Sans", 9))

    def show_files_firmware_window(self) -> None:
        if self.files_window and self.files_window.winfo_exists():
            self.files_window.deiconify()
            self.files_window.lift()
            self.files_window.focus_force()
            return

        win = tk.Toplevel(self.root)
        self.files_window = win
        win.title(self._t("files_window_title"))
        win.geometry("760x280")
        win.minsize(680, 240)
        win.configure(bg=self.colors["bg"])

        frame = ttk.LabelFrame(win, text=self._t("files_and_firmware"), padding=10)
        frame.pack(fill="both", expand=True, padx=10, pady=10)
        self._populate_files_firmware_container(frame)
        self._sync_home_controls()

        def _on_close() -> None:
            self.files_window = None
            win.destroy()

        win.protocol("WM_DELETE_WINDOW", _on_close)

    def _close_files_firmware_window(self) -> None:
        if self.files_window and self.files_window.winfo_exists():
            self.files_window.destroy()
        self.files_window = None

    def _set_upload_cancel_visible(self, visible: bool, *, cancelling: bool = False) -> None:
        if self.cancel_upload_button is None:
            return
        if visible:
            self.cancel_upload_button.configure(
                text=self._t("cancel_uploading") if cancelling else self._t("cancel_upload"),
                state="disabled" if cancelling else "normal",
            )
            self.cancel_upload_button.grid()
        else:
            self.cancel_upload_button.configure(text=self._t("cancel_upload"), state="normal")
            self.cancel_upload_button.grid_remove()

    def cancel_upload(self) -> None:
        self.upload_cancel_requested = True
        self._set_upload_cancel_visible(True, cancelling=True)
        self.progress_var.set("Upload: отмена...")
        self.log("Загрузка: запрошена отмена. Остановлю передачу на ближайшем безопасном шаге.")

    def _cleanup_cancelled_upload(self, dest: str) -> tuple[bool, str]:
        self._post("progress", ("Upload cancel cleanup", 0.0))
        self._post("files-status", f"Загрузка отменена: удаляю частичный файл {dest} с SD...")
        try:
            out = sdtool.delete_file(self._port(), self._baud(), dest)
        except Exception as exc:
            msg = (
                f"Загрузка отменена, но частичный файл {dest} удалить автоматически не удалось: {exc}. "
                "Не запускай этот файл; удали его вручную после обновления списка SD."
            )
            self._post("log", msg)
            self._post("files-status", msg)
            return False, msg

        self._post("log", out.strip() or f"Частичный файл {dest} удалён после отмены загрузки.")
        try:
            files = sdtool.list_files(self._port(), self._baud())
            self._post("sd-files", files)
        except Exception as exc:
            self._post("log", f"Частичный файл удалён, но список SD обновить не удалось: {exc}")
        msg = f"Загрузка отменена; частичный файл {dest} удалён с SD."
        self._post("files-status", msg)
        return True, msg

    def _set_busy_ui(self, busy: bool, label: str | None = None) -> None:
        self.busy_var.set(label or ("USB: busy" if busy else "USB: idle"))
        state = "disabled" if busy else "normal"
        for widget in self.action_widgets:
            try:
                widget.configure(state=state)
            except Exception:
                pass
        if not busy:
            self._sync_home_controls()
        if busy and label and "g-code" in label.lower():
            self.progress_var.set("Upload: writing to SD...")
            self.progress_bar.configure(mode="indeterminate")
            self.progress_bar.start(12)
        elif not busy:
            self.progress_bar.stop()
            self.progress_bar.configure(mode="determinate")
            self._set_upload_cancel_visible(False)

    def _post(self, kind: str, payload: object) -> None:
        self.events.put((kind, payload))

    def _drain_events(self) -> None:
        while True:
            try:
                kind, payload = self.events.get_nowait()
            except queue.Empty:
                break

            if kind == "log":
                self.log(str(payload))
            elif kind == "error":
                text = str(payload)
                self.log(f"Ошибка: {text}")
                if self._is_port_gone_error(text):
                    lost_port = self._port()
                    self.disconnect_port(log_change=False)
                    if lost_port:
                        self.log(
                            f"Порт {lost_port} отключён в приложении: система больше не подтверждает этот USB-порт."
                        )
                if sdtool.is_transient_serial_error(text):
                    self.post_print_recovery_required = True
                    self._show_post_print_recovery_window("failed-start")
                messagebox.showerror("K9 Control Center", text)
            elif kind == "info":
                messagebox.showinfo("Little Hands", str(payload))
                self.log(str(payload))
            elif kind == "temp":
                current, target, heater = payload  # type: ignore[misc]
                self.last_temp_current = float(current)
                self.last_temp_target = float(target)
                self.last_heater_power = None if heater is None else int(heater)
                self.last_temp_sample_ts = time.time()
                self.temp_var.set(f"Hotend: {current:.2f} / {target:.2f} C")
                self._record_temp_point(float(current), float(target))
            elif kind == "sd":
                self.last_sd_summary = str(payload)
                self.last_sd_sample_ts = time.time()
                self.sd_var.set(self.last_sd_summary)
            elif kind == "fw":
                self.last_fw_line = str(payload).strip()
                self._refresh_fw_identity()
                self.fw_var.set(f"FW: {self.last_fw_identity}" if self.last_fw_identity else self.last_fw_line)
            elif kind == "pos":
                self.last_position_line = self._format_operator_position_line(str(payload))
                self.last_position_sample_ts = time.time()
            elif kind == "progress":
                label, value = payload  # type: ignore[misc]
                label_text = str(label)
                label_lower = label_text.lower()
                if label_text.startswith("Upload"):
                    self.progress_bar.stop()
                    self.progress_bar.configure(mode="determinate")
                    self._set_upload_cancel_visible(
                        "complete" not in label_lower and "cancel" not in label_lower,
                        cancelling=self.upload_cancel_requested,
                    )
                else:
                    self._set_upload_cancel_visible(False)
                self.progress_var.set(label_text)
                self.progress_bar["value"] = float(value)
            elif kind == "melody":
                self._play_completion_melody()
            elif kind == "busy":
                busy, label = payload  # type: ignore[misc]
                self._set_busy_ui(bool(busy), str(label))
            elif kind == "metrics":
                key, value = payload  # type: ignore[misc]
                key_str = str(key)
                value_str = str(value).strip()
                if key_str == "m114":
                    value_str = self._format_m114_for_metrics(value_str)
                self.metrics_sections[key_str] = value_str
                if key_str == "m115":
                    self.last_m115_raw = value_str
                    self._refresh_fw_identity()
                    self.fw_var.set(f"FW: {self.last_fw_identity}" if self.last_fw_identity else "")
                elif key_str == "m503":
                    self.last_m503_raw = value_str
                    self._refresh_fw_identity()
                    self.fw_var.set(f"FW: {self.last_fw_identity}" if self.last_fw_identity else "")
                self._render_metrics()
            elif kind == "sd-files":
                self._apply_sd_files(payload)  # type: ignore[arg-type]
            elif kind == "active-sd":
                text = str(payload).strip()
                if ":" in text:
                    text = text.split(":", 1)[1].strip()
                self.active_sd_var.set(self._format_label_value("active_sd", text or "-"))
                self._update_known_print_time_label()
            elif kind == "ports":
                ports, detected = payload  # type: ignore[misc]
                self._set_port_choices(list(ports), str(detected) if detected else None)
            elif kind == "port-lost":
                lost_port = str(payload or self._port()).strip()
                self.disconnect_port(log_change=False)
                if lost_port:
                    self.log(
                        f"Порт {lost_port} отключён в приложении: система больше не подтверждает этот USB-порт. "
                        "Нажми 'Найти' после power cycle или переподключения принтера."
                    )
            elif kind == "files-status":
                self.files_status_var.set(str(payload))
            elif kind == "close-files-window":
                self._close_files_firmware_window()
            elif kind == "upload-cancel-visible":
                visible, cancelling = payload  # type: ignore[misc]
                self._set_upload_cancel_visible(bool(visible), cancelling=bool(cancelling))
            elif kind == "find-port-ui":
                active = bool(payload)
                self._set_find_port_busy(active)
            elif kind == "home-trust":
                state, reason, log_change = payload  # type: ignore[misc]
                self._apply_home_trust(str(state), str(reason), log_change=bool(log_change))
            elif kind == "post-print-recovery":
                reason = str(payload or "completion")
                self.post_print_recovery_required = True
                self.log(self._post_print_recovery_text(reason))
                self._show_post_print_recovery_window(reason)
            elif kind == "post-print-recovery-clear":
                self.post_print_recovery_required = False
                self._close_post_print_window()
        self.root.after(150, self._drain_events)

    def _render_metrics(self) -> None:
        order = [
            ("m115", "M115 / Firmware"),
            ("m503", "M503 / Settings"),
            ("m114", "M114 / Position"),
            ("m105", "M105 / Temperature"),
            ("m27", "M27 / SD status"),
        ]
        blocks: list[str] = []
        for key, title in order:
            value = self.metrics_sections.get(key)
            if value:
                blocks.append(f"[{title}]\n{value}")
        rendered = "\n\n".join(blocks) if blocks else "Метрики ещё не запрошены."
        self.metrics_text.configure(state="normal")
        self.metrics_text.delete("1.0", "end")
        self.metrics_text.insert("1.0", rendered)
        self.metrics_text.configure(state="disabled")

    def _operator_axis_name(self, axis: str) -> str:
        axis = axis.upper()
        if axis == "Y":
            return "Z"
        if axis == "Z":
            return "Y"
        return axis

    def _operator_axis_hint(self, axis: str) -> str:
        axis = axis.upper()
        if axis == "Y":
            return "стол"
        if axis == "Z":
            return "голова вверх/вниз"
        if axis == "X":
            return "голова влево/вправо"
        return axis

    def _format_operator_position_line(self, raw_line: str) -> str:
        text = (raw_line or "").strip()
        m = re.search(r"X:([+-]?\d+(?:\.\d+)?)\s+Y:([+-]?\d+(?:\.\d+)?)\s+Z:([+-]?\d+(?:\.\d+)?)", text)
        if not m:
            return text
        x, y_raw, z_raw = m.groups()
        return f"X:{x} Y:{z_raw} Z:{y_raw}"

    def _format_m114_for_metrics(self, raw_text: str) -> str:
        text = (raw_text or "").strip()
        if not text:
            return text
        raw_line = next((line.strip() for line in text.splitlines() if "X:" in line and "Y:" in line and "Z:" in line), "")
        if not raw_line:
            return text
        operator_line = self._format_operator_position_line(raw_line)
        return f"Operator view: {operator_line}\nRaw M114: {raw_line}"

    def _is_printable_sd_path(self, path: str) -> bool:
        return Path(path.strip().lower()).suffix in PRINTABLE_SD_EXTS

    def _parse_sd_entry_for_ui(self, entry: str) -> tuple[str, str]:
        line = entry.strip()
        if not line:
            return "", ""
        tokens = line.split()
        path = tokens[0] if tokens else line
        display = path
        long_name = ""
        if len(tokens) >= 2:
            for idx, token in enumerate(tokens[1:], start=1):
                if token.isdigit():
                    continue
                candidate = " ".join(tokens[idx:])
                if self._is_printable_sd_path(candidate) or Path(candidate.strip().lower()).name in {
                    "eeprom.dat",
                    "mkslite.cur",
                    "mkslite.bin",
                }:
                    long_name = candidate
                    break
        if long_name and long_name != path:
            display = f"{long_name} (SD: {path})"
        elif len(tokens) >= 2 and tokens[1].isdigit():
            display = f"{path} ({int(tokens[1]):,} B)"
        return display, path

    def _apply_sd_files(self, files: list[str]) -> None:
        previous_path = self._selected_sd_path()
        self.sd_list = files
        self.sd_print_files = []
        self.sd_other_files = []
        self.sd_display_to_path = {}
        self.sd_print_listbox.delete(0, "end")
        if not files:
            self.sd_print_listbox.insert("end", "(empty)")
            self.selected_sd_var.set(self._format_label_value("selected_sd", "-"))
            if self.current_print_file == "-":
                self._update_known_print_time_label(None, None)
            self.sd_notice_var.set(self._t("sd_empty"))
            return

        selected_print_index = None
        lowered_paths: list[str] = []
        for idx, entry in enumerate(files):
            display, path = self._parse_sd_entry_for_ui(entry)
            if not path:
                continue
            self.sd_display_to_path[display] = path
            lowered_paths.append(path.strip().lower())
            if self._is_printable_sd_path(path):
                self.sd_print_files.append(display)
                self.sd_print_listbox.insert("end", display)
                if previous_path and path == previous_path:
                    selected_print_index = len(self.sd_print_files) - 1
            else:
                self.sd_other_files.append(display)

        if not self.sd_print_files:
            self.sd_print_listbox.insert("end", "(empty)")

        if selected_print_index is not None:
            self.sd_print_listbox.selection_set(selected_print_index)
            self.sd_print_listbox.see(selected_print_index)
        self._sync_selected_sd_label()
        self._update_sd_notice(lowered_paths)

    def _update_sd_notice(self, lowered_paths: list[str]) -> None:
        has_eeprom = any(Path(path).name.lower() == "eeprom.dat" for path in lowered_paths)
        self.sd_has_eeprom = has_eeprom or self.eeprom_confirmed
        has_bin = any(Path(path).name.lower() == "mkslite.bin" for path in lowered_paths)
        has_cur = any(Path(path).name.lower() == "mkslite.cur" for path in lowered_paths)
        notes: list[str] = []
        if has_bin:
            notes.append({
                "ru": "На карте есть mksLite.bin: при следующем старте принтер может снова прошиться.",
                "en": "The card still contains mksLite.bin: the printer may flash again on the next boot.",
                "zh": "卡上仍有 mksLite.bin：打印机下次启动时可能会再次刷机。",
            }[self.lang_var.get().strip() or "ru"])
        elif has_cur:
            notes.append({
                "ru": "На карте есть mksLite.CUR: это след прошлой прошивки, обычно его можно удалить.",
                "en": "The card contains mksLite.CUR: this is usually leftover from the last flash and can normally be removed.",
                "zh": "卡上有 mksLite.CUR：这通常是上次刷机留下的文件，一般可以删除。",
            }[self.lang_var.get().strip() or "ru"])
        self.sd_notice_var.set(" ".join(notes))

    def _on_sd_listbox_select(self, source: str) -> None:
        if source != "print":
            self.sd_print_listbox.selection_clear(0, "end")
        self._sync_selected_sd_label()

    def _sync_selected_sd_label(self) -> None:
        display = self._selected_sd_display()
        self.selected_sd_var.set(self._format_label_value("selected_sd", display or "-"))
        if self.current_print_file == "-":
            self._update_known_print_time_label(self._selected_print_sd_path(), display)

    def _selected_sd_display(self) -> str | None:
        print_sel = self.sd_print_listbox.curselection()
        if print_sel:
            display = self.sd_print_listbox.get(print_sel[0])
            return None if display == "(empty)" else display
        return None

    def _port(self) -> str:
        return self.port_var.get().strip()

    def _classify_port(self, meta: dict[str, str]) -> str:
        hay = " ".join(str(v) for v in meta.values()).lower()
        vid = (meta.get("vid") or "").upper()
        pid = (meta.get("pid") or "").upper()
        detected = (meta.get("detected") or "").lower()
        if detected == "marlin":
            return "Marlin / принтер"
        if detected == "marlin-like":
            return "похож на принтер"
        if detected == "usb-visible-no-marlin":
            return "CH340 виден / Marlin молчит"
        if detected == "probe-error":
            return "USB виден / ошибка ответа"
        if vid == "1A86" and pid == "7523":
            return "CH340 / вероятный K9"
        if "ch340" in hay or "wch" in hay:
            return "CH340 / вероятный K9"
        if vid == "0403" and pid == "6001":
            return "FTDI / не принтер"
        if "ftdi" in hay or "ft232" in hay:
            return "FTDI / не принтер"
        if meta.get("device", "").startswith("/dev/ttyACM"):
            return "ACM / проверить"
        return "serial / проверить"

    def _is_safe_printer_port_meta(self, meta: dict[str, str]) -> bool:
        return sdtool.is_likely_printer_port(meta)

    def _selected_port_meta(self) -> dict[str, str] | None:
        device = self._port()
        if not device:
            return None
        try:
            ports = sdtool.list_serial_ports()
        except Exception:
            return None
        return next((meta for meta in ports if meta.get("device") == device), None)

    def _selected_port_safety_error(self) -> str | None:
        device = self._port()
        if not device:
            return None
        meta = self._selected_port_meta()
        if meta is None:
            return (
                f"Выбранный порт {device} сейчас не найден системой. "
                "Нажми 'Найти' и выбери заново подтверждённый CH340/ACM порт принтера."
            )
        if not self._is_safe_printer_port_meta(meta):
            return (
                f"Выбранный порт {device} не похож на EasyThreed K9/CH340 printer port "
                f"({self._classify_port(meta)}). Команда заблокирована, чтобы не отправлять G-code "
                "в чужой serial-интерфейс."
            )
        return None

    def _is_port_gone_error(self, exc: BaseException | str) -> bool:
        text = str(exc).lower()
        return (
            "no such file or directory" in text
            or "could not open port" in text
            or "device disconnected" in text
            or "device reports readiness" in text
        )

    def _port_label(self, meta: dict[str, str]) -> str:
        device = meta.get("device", "")
        desc = meta.get("description", "") or meta.get("product", "") or "serial"
        kind = self._classify_port(meta)
        return f"{device} — {kind} — {desc}"

    def _set_port_choices(self, ports: list[dict[str, str]], preferred: str | None = None) -> None:
        disconnected_label = self._t("not_connected")
        safe_ports = [meta for meta in ports if meta.get("device") and self._is_safe_printer_port_meta(meta)]
        self.port_choices = [disconnected_label] + [self._port_label(meta) for meta in safe_ports]
        self.port_combo["values"] = self.port_choices

        previous_device = self.port_var.get().strip()
        selected_device = preferred or self.port_var.get().strip()
        if not selected_device:
            if previous_device:
                self._set_home_trust(HOME_TRUST_INVALID, "printer port disconnected", log_change=True)
                self.post_print_pose_known = False
                self.post_print_pose = None
            self.port_display_var.set(disconnected_label)
            self.port_var.set("")
            return
        if selected_device:
            for meta in safe_ports:
                if meta.get("device") == selected_device:
                    if previous_device and selected_device != previous_device:
                        self._set_home_trust(HOME_TRUST_INVALID, "printer port changed", log_change=True)
                        self.post_print_pose_known = False
                        self.post_print_pose = None
                    self.port_display_var.set(self._port_label(meta))
                    self.port_var.set(selected_device)
                    self.preferred_port = selected_device
                    self._schedule_sd_refresh_after_port(selected_device, force=selected_device != previous_device)
                    return
        if selected_device and any(meta.get("device") == selected_device for meta in ports):
            self.log(
                f"Порт {selected_device} скрыт из списка принтера: он не похож на K9/CH340. "
                "Команды на него отправляться не будут."
            )
        if previous_device:
            self._set_home_trust(HOME_TRUST_INVALID, "printer port is not available", log_change=True)
            self.post_print_pose_known = False
            self.post_print_pose = None
        self.port_display_var.set(disconnected_label)
        self.port_var.set("")

    def _on_port_selected(self) -> None:
        text = self.port_display_var.get().strip()
        if text == self._t("not_connected"):
            self.disconnect_port(log_change=True)
            return
        device = text.split(" — ", 1)[0].strip() if text else ""
        if device:
            if self.port_var.get().strip() and self.port_var.get().strip() != device:
                self._set_home_trust(HOME_TRUST_INVALID, "printer port changed", log_change=True)
                self.post_print_pose_known = False
                self.post_print_pose = None
            self.port_var.set(device)
            self.preferred_port = device
            self.log(f"Выбран порт: {device}")
            self._schedule_sd_refresh_after_port(device, force=True)

    def disconnect_port(self, log_change: bool = False) -> None:
        had_port = bool(self.port_var.get().strip())
        self.port_var.set("")
        self.port_display_var.set(self._t("not_connected"))
        self.auto_sd_refresh_after_port = None
        self.busy_var.set("USB: отключен")
        if had_port:
            self._set_home_trust(HOME_TRUST_INVALID, "printer port disconnected", log_change=True)
            self.post_print_pose_known = False
            self.post_print_pose = None
        if log_change:
            self.log("Порт отключён. Автоопрос и команды принтера остановлены до выбора нового порта.")

    def _schedule_sd_refresh_after_port(self, port: str, *, force: bool = False) -> None:
        if not port:
            return
        if not force and self.auto_sd_refresh_after_port == port:
            return
        self.auto_sd_refresh_after_port = port
        self.root.after(AUTO_SD_REFRESH_DELAY_MS, lambda: self._try_auto_sd_refresh_after_port(port, 0))

    def _try_auto_sd_refresh_after_port(self, port: str, attempt: int) -> None:
        if self._port() != port or self.auto_sd_refresh_after_port != port:
            return
        if self.current_print_file != "-":
            self.auto_sd_refresh_after_port = None
            self.log(
                "Автообновление SD пропущено: в логе есть незавершённый старт печати. "
                "Сначала проверяю статус M27, чтобы не трогать карту во время возможной SD-печати."
            )
            return
        if self.user_task_pending:
            if attempt < 6:
                self.root.after(700, lambda: self._try_auto_sd_refresh_after_port(port, attempt + 1))
            else:
                self.log("Автообновление SD после выбора порта отложено: USB всё ещё занят.")
            return
        temp_age = time.time() - self.last_temp_sample_ts if self.last_temp_sample_ts else None
        if temp_age is None or temp_age > AUTO_SD_REFRESH_REQUIRE_FRESH_TEMP_SEC:
            if attempt < 10:
                if attempt == 0:
                    self.log("Автообновление SD ждёт свежий ответ M105, чтобы не трогать карту при молчащем принтере.")
                self.root.after(1000, lambda: self._try_auto_sd_refresh_after_port(port, attempt + 1))
            else:
                self.auto_sd_refresh_after_port = None
                self.log(
                    "Автообновление SD пропущено: принтер не дал свежую телеметрию M105. "
                    "Если это после завершения или неудачного старта печати, выключи принтер по питанию на 5-10 секунд."
                )
            return
        self.auto_sd_refresh_after_port = None
        self.log(f"Порт принтера {port} подключён: автоматически обновляю список SD.")
        self.refresh_sd_files()

    def _mark_sd_start_sent(self, path: str, display: str) -> None:
        self.current_print_file = path
        self.current_print_display = display
        start_ts = time.time()
        self.current_print_start_ts = start_ts
        if not self.predicted_print_end_valid or self.predicted_print_end_file != path:
            self.predicted_print_end_valid = True
            self.predicted_print_end_file = path
            self.predicted_print_end_display = display or path
            self.predicted_print_end_contract = PRINT_END_CONTRACT
            self.predicted_print_end_x = 95.0
            self.predicted_print_end_y = 95.0
            self.predicted_print_end_z = None
        self.predicted_print_end_start_ts = start_ts
        self.post_m24_usb_quiet_until = start_ts + POST_M24_USB_QUIET_SEC
        self.last_post_m24_quiet_log_ts = 0.0
        self.current_print_progress_pct = 0.0
        self.print_state_restored_from_log = False
        self.print_start_watchdog_alerted = False
        self.print_was_active = False
        self.print_completion_armed = False
        self.sd_progress_sample_count = 0
        self.first_sd_progress_ts = None
        self.last_sd_progress_ts = None
        self.bed_clear_before_go_start_required = True
        self.stopped_print_pose = None
        self.stopped_print_display = "-"
        self._append_ring_log(f"{time.strftime('%H:%M:%S')} PRINT_START file={path}")
        self._save_print_state("printing", force=True)
        self._post("active-sd", f"Печатается: {display}")
        self._post("progress", ("Печать: старт отправлен, жду вход в SD-печать", 0.0))
        self._post(
            "log",
            "Старт SD отправлен. Hotend уже был прогрет Little Hands; теперь K9 может несколько минут отвечать busy "
            "или молчать, пока входит в SD-печать. Не обновляй список SD в этот момент.",
        )
        self._post(
            "log",
            f"Первые {POST_M24_USB_QUIET_SEC} с после M24 Little Hands не трогает USB вообще. "
            "Это нужно этой K9-прошивке, чтобы спокойно войти в SD-печать. "
            "Если вентилятор/моторы ожили или пластик пошёл - не выключай питание, просто наблюдай.",
        )

    def _refresh_ports_on_startup(self) -> None:
        try:
            ports = sdtool.list_serial_ports()
            self._set_port_choices(ports, self.preferred_port or None)
        except Exception:
            pass

    def _set_find_port_busy(self, active: bool) -> None:
        self.find_port_animating = active
        if active:
            try:
                self.find_port_button.configure(state="disabled")
            except Exception:
                pass
            self.find_port_anim_phase = 0
            self._tick_find_port_button()
        else:
            try:
                self.find_port_button.configure(state="normal", text=self._t("find"))
            except Exception:
                pass

    def _tick_find_port_button(self) -> None:
        if not self.find_port_animating:
            return
        dots = "." * (self.find_port_anim_phase % 4)
        base = {"ru": "Ищу", "en": "Finding", "zh": "查找中"}[self.lang_var.get().strip() or "ru"]
        label = base + dots
        try:
            self.find_port_button.configure(text=label)
        except Exception:
            return
        self.find_port_anim_phase += 1
        self.root.after(300, self._tick_find_port_button)

    def detect_printer_port_action(self) -> None:
        if self.user_task_pending:
            self.log("Поиск порта не запущен: предыдущая USB-команда ещё выполняется.")
            return
        self._set_find_port_busy(True)

        def task() -> None:
            try:
                self._post("log", "Ищу вероятный порт принтера среди USB/ACM serial...")
                detected, ranked = sdtool.detect_printer_port(self._baud())
                self.events.put(("ports", (ranked, detected)))
                if detected:
                    detected_meta = next((meta for meta in ranked if meta.get("device") == detected), {})
                    detected_kind = str(detected_meta.get("detected") or "")
                    if detected_kind in {"marlin", "marlin-like"}:
                        self._post("log", f"Найден вероятный принтер: {detected}")
                    else:
                        msg = (
                            f"USB-порт похож на принтер и выбран: {detected}\n\n"
                            "Но Marlin сейчас не ответил на M115/M105. После завершения предыдущей печати "
                            "это обычно означает полуживое состояние USB/SD: сделай power cycle принтера "
                            "на 5–10 секунд, затем нажми 'Найти' ещё раз."
                        )
                        self._post("log", msg)
                        self._post("info", msg)
                else:
                    self._post("log", "Автодетект не нашёл уверенный порт принтера. Оставляю ручной выбор.")
                    self._post("info", "Автопоиск не нашёл уверенный порт принтера.\nВыбери порт вручную из списка.")
            finally:
                self._post("find-port-ui", False)

        self._run_task("Поиск порта принтера", task, require_port=False)

    def _baud(self) -> int:
        return 115200

    def show_manual(self) -> None:
        if self.manual_window and self.manual_window.winfo_exists():
            self.manual_window.deiconify()
            self.manual_window.lift()
            self.manual_window.focus_force()
            return

        win = tk.Toplevel(self.root)
        self.manual_window = win
        win.title(self._t("manual_title"))
        win.geometry("880x760")
        win.configure(bg=self.colors["bg"])
        frame = ttk.Frame(win, padding=10)
        frame.pack(fill="both", expand=True)
        text = ScrolledText(frame, wrap="word")
        self.manual_text_widget = text
        text.pack(fill="both", expand=True)
        text.insert("1.0", MANUAL_TEXTS.get(self.lang_var.get().strip() or "ru", MANUAL_TEXT))
        text.configure(state="disabled")
        text.configure(
            bg=self.colors["field"],
            fg=self.colors["text"],
            insertbackground=self.colors["accent"],
            selectbackground=self.colors["accent"],
            selectforeground=self.colors["field"],
            highlightbackground=self.colors["border"],
            highlightcolor=self.colors["accent"],
            relief="solid",
            borderwidth=1,
        )

        def _on_close() -> None:
            self.manual_window = None
            self.manual_text_widget = None
            win.destroy()

        win.protocol("WM_DELETE_WINDOW", _on_close)

    def export_cura_bundle(self) -> None:
        stamp = time.strftime("%Y%m%d_%H%M%S")
        target_root = PROJECT_ROOT / "exports" / f"cura_bundle_{stamp}"
        copied = 0
        for pattern in CURA_EXPORT_PATTERNS:
            for src in CURA_ROOT.glob(pattern):
                if src.is_file():
                    dst = target_root / src.relative_to(CURA_ROOT)
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dst)
                    copied += 1
        if copied == 0:
            messagebox.showerror("Little Hands", "Не удалось найти файлы Cura для экспорта.")
            return
        manual_path = target_root / "BASELINE_MANUAL.txt"
        manual_text = MANUAL_TEXTS.get(self.lang_var.get().strip() or "ru", MANUAL_TEXT)
        manual_path.write_text(manual_text + "\n", encoding="utf-8")
        self.log(f"Экспорт профиля Cura готов: {target_root} ({copied} файлов)")

    def play_computer_melody_button(self) -> None:
        self._play_completion_melody()
        self.log("Тестовая мелодия на компьютере проиграна")

    def _play_completion_melody(self) -> None:
        if shutil.which("paplay"):
            sound = "/usr/share/sounds/freedesktop/stereo/complete.oga"
            if Path(sound).is_file():
                def worker() -> None:
                    for _ in range(2):
                        subprocess.run(["paplay", sound], check=False)
                        time.sleep(0.18)
                threading.Thread(target=worker, daemon=True).start()
                return
        for delay_ms in (0, 180, 420):
            self.root.after(delay_ms, self.root.bell)

    def _post_print_recovery_text(self, reason: str = "completion") -> str:
        lang = self.lang_var.get().strip() or "ru"
        failed = reason in {"failed-start", "blocked-start"}
        if lang == "en":
            if failed:
                return (
                    "The print start was not confirmed reliably.\n\n"
                    "Use this recovery only if the printer is physically NOT printing, NOT heating, and NOT moving. "
                    "If the printer is actually working, close this window, do not power-cycle it, and monitor the print visually.\n\n"
                    "1. If the printer is stuck with clicks or a silent hotend, press 'Hard stop'.\n"
                    "2. Power the printer off for 5-10 seconds and power it on again.\n"
                    "3. Press 'Find' if the port is not responsive.\n"
                    "4. Check the start pose manually.\n"
                    "5. Press 'Save start'.\n"
                    "6. Before retrying, verify that the G-code was sliced with the validated Cura profile and was not edited by hand.\n\n"
                    "Why: this K9 can leave USB/SD half-alive after a bad start, but a silent USB reply alone is not proof that a real print has failed."
                )
            intro = (
                "Print finished. Before the next print, bring the printer back to a clean start state."
            )
            return (
                f"{intro}\n\n"
                "1. Remove the printed part from the bed.\n"
                "2. Only after the part is removed, return the printer to the start pose. If Little Hands observed the print finish, 'Go to start' can use that known post-print pose.\n"
                "3. While the printer is physically in that start pose, power it off for 5-10 seconds and power it on again.\n"
                "4. If the port is not responsive, press 'Find'. If the app sees CH340 but Marlin does not answer, repeat the power cycle.\n"
                "5. Make sure the printer is still in the start pose and press 'Save start' in this window or in the main controls.\n"
                "6. Start the next SD print only after the app confirms that the start was saved.\n\n"
                "Why: after an SD print this K9/Marlin build can leave USB/SD in a half-alive state. Starting again before a power cycle can produce clicks, frozen telemetry, or no motion."
            )
        if lang == "zh":
            if failed:
                return (
                    "打印启动没有被可靠确认。\n\n"
                    "只有在打印机实际没有打印、没有加热、也没有运动时，才按这个恢复流程操作。"
                    "如果打印机确实已经在工作，请关闭此窗口，不要断电，并目视观察打印。\n\n"
                    "1. 如果打印机卡住、发出咔哒声或热端不加热，点击 'Hard stop'。\n"
                    "2. 关闭打印机电源 5-10 秒，然后重新打开。\n"
                    "3. 如果端口没有响应，点击 'Find'。\n"
                    "4. 手动检查起始姿态。\n"
                    "5. 点击 'Save start'。\n"
                    "6. 再次启动前，确认 G-code 来自已验证的 Cura 配置，并且没有手工改坏。\n\n"
                    "原因：这台 K9 在异常启动后可能让 USB/SD 处于半工作状态，但 USB 暂时沉默本身并不能证明真实打印失败。"
                )
            intro = "打印已完成。下一次打印前，请先回到干净的起始状态。"
            return (
                f"{intro}\n\n"
                "1. 从平台上取下模型。\n"
                "2. 只有在取下模型之后，才让打印机回到起始姿态。如果 Little Hands 观察到了打印结束，'Go to start' 可以使用已知的打印后位置。\n"
                "3. 打印机实际停在起始姿态时，关闭电源 5-10 秒，然后重新打开。\n"
                "4. 如果端口没有响应，点击 'Find'。如果只看到 CH340 但 Marlin 不回应，请再次断电重启。\n"
                "5. 确认打印机仍在起始姿态，然后在此窗口或主控制区点击 'Save start'。\n"
                "6. 等程序确认起点已保存后，再开始下一次 SD 打印。\n\n"
                "原因：这台 K9/Marlin 在 SD 打印结束后可能让 USB/SD 留在半工作状态，直接重复启动会导致咔哒声、遥测冻结或无动作。"
            )
        if failed:
            return (
                "Старт печати не подтвердился надёжно.\n\n"
                "Используй это восстановление только если принтер физически НЕ печатает, НЕ греется и НЕ двигается. "
                "Если принтер реально работает, закрой это окно, не выключай питание и наблюдай за печатью визуально.\n\n"
                "1. Если принтер застрял со щелчками или молчащим хотендом, нажми 'Жёсткий стоп'.\n"
                "2. Выключи питание принтера на 5–10 секунд и включи снова.\n"
                "3. Если порт не отвечает, нажми 'Найти'.\n"
                "4. Вручную проверь стартовую позу.\n"
                "5. Нажми 'Запомнить старт'.\n"
                "6. Перед повтором проверь, что G-code сделан проверенным профилем Cura или залит через Little Hands; "
                "ручной предпрогрев hotend в нормальном сценарии не нужен.\n\n"
                "Почему так: этот K9 после плохого старта может оставлять USB/SD в полуживом состоянии, "
                "но одно только молчание USB ещё не доказывает, что реальная печать сорвалась."
            )
        intro = "Печать завершена. Перед следующей печатью верни принтер в чистое стартовое состояние."
        return (
            f"{intro}\n\n"
            "1. Сними модель со стола.\n"
            "2. Только после снятия модели верни принтер в стартовую позу. Если Little Hands видел завершение печати, 'К старту' использует известную послепечатную позу.\n"
            "3. Когда принтер физически стоит в стартовой позе, выключи питание на 5–10 секунд и включи снова.\n"
            "4. Если порт не отвечает, нажми 'Найти'. Если приложение видит CH340, но Marlin молчит, повтори power cycle.\n"
            "5. Убедись, что принтер всё ещё в стартовой позе, и нажми 'Запомнить старт' в этом окне или в ручном управлении.\n"
            "6. Запускай следующую печать с SD только после подтверждения, что старт сохранён.\n\n"
            "Почему так: после SD-печати эта связка K9/Marlin иногда оставляет USB/SD в полуживом состоянии. "
            "Повторный старт без power cycle может дать щелчки, замершую телеметрию или отсутствие движения."
        )

    def _save_start_from_post_print_window(self) -> None:
        self.set_current_home_zero()

    def _go_start_from_post_print_window(self) -> None:
        lang = self.lang_var.get().strip() or "ru"
        prompt = {
            "en": (
                "Has the printed part already been removed from the bed?\n\n"
                "Return to start only after removing the part, so the head and bed cannot hit the model."
            ),
            "zh": (
                "模型已经从平台上取下了吗？\n\n"
                "只有取下模型后才能回到起点，避免喷头或平台碰到模型。"
            ),
            "ru": (
                "Модель уже снята со стола?\n\n"
                "Возврат к старту можно делать только после удаления детали, чтобы голова и стол не задели модель."
            ),
        }.get(lang) or (
            "Модель уже снята со стола?\n\n"
            "Возврат к старту можно делать только после удаления детали, чтобы голова и стол не задели модель."
        )
        if not messagebox.askyesno(
            "Little Hands",
            prompt,
        ):
            return
        self.go_print_home(confirm_model_removed=True)

    def _close_post_print_window(self) -> None:
        if self.post_print_window and self.post_print_window.winfo_exists():
            self.post_print_window.destroy()
        self.post_print_window = None
        self.post_print_text_widget = None

    def _show_post_print_recovery_window(self, reason: str = "completion") -> None:
        text = self._post_print_recovery_text(reason)
        if reason in {"failed-start", "blocked-start"}:
            title = {
                "ru": "Проверка старта печати",
                "en": "Print Start Check",
                "zh": "打印启动检查",
            }.get(self.lang_var.get().strip() or "ru", "Проверка старта печати")
        else:
            title = {
                "ru": "Перед следующей печатью",
                "en": "Before Next Print",
                "zh": "下一次打印前",
            }.get(self.lang_var.get().strip() or "ru", "Перед следующей печатью")
        if self.post_print_window and self.post_print_window.winfo_exists():
            win = self.post_print_window
            win.deiconify()
            win.lift()
            if self.post_print_text_widget and self.post_print_text_widget.winfo_exists():
                self.post_print_text_widget.configure(state="normal")
                self.post_print_text_widget.delete("1.0", "end")
                self.post_print_text_widget.insert("1.0", text)
                self.post_print_text_widget.configure(state="disabled")
            return

        win = tk.Toplevel(self.root)
        self.post_print_window = win
        win.title(title)
        win.geometry("680x430")
        win.minsize(560, 340)
        win.configure(bg=self.colors["bg"])
        win.transient(self.root)

        frame = ttk.Frame(win, padding=14)
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)

        text_widget = tk.Text(frame, wrap="word", height=12)
        self.post_print_text_widget = text_widget
        text_widget.grid(row=0, column=0, sticky="nsew")
        text_widget.insert("1.0", text)
        text_widget.configure(
            state="disabled",
            bg=self.colors["field_alt"],
            fg=self.colors["text"],
            insertbackground=self.colors["accent"],
            relief="solid",
            borderwidth=1,
            highlightbackground=self.colors["border"],
            highlightcolor=self.colors["accent"],
        )

        buttons = ttk.Frame(frame)
        buttons.grid(row=1, column=0, sticky="ew", pady=(12, 0))
        buttons.columnconfigure(0, weight=1)
        buttons.columnconfigure(1, weight=1)
        buttons.columnconfigure(2, weight=1)
        close_label = {"ru": "Понятно", "en": "OK", "zh": "知道了"}.get(self.lang_var.get().strip() or "ru", "Понятно")
        go_start_label = {
            "ru": "К старту",
            "en": "Go to start",
            "zh": "回到起点",
        }.get(self.lang_var.get().strip() or "ru", "К старту")
        confirm_label = {
            "ru": "Запомнить старт",
            "en": "Save start",
            "zh": "保存起点",
        }.get(self.lang_var.get().strip() or "ru", "Запомнить старт")
        ttk.Button(buttons, text=close_label, command=self._close_post_print_window).grid(row=0, column=0, sticky="ew", padx=(0, 5))
        ttk.Button(buttons, text=go_start_label, command=self._go_start_from_post_print_window).grid(row=0, column=1, sticky="ew", padx=5)
        ttk.Button(buttons, text=confirm_label, command=self._save_start_from_post_print_window).grid(row=0, column=2, sticky="ew", padx=(5, 0))

        def _on_close() -> None:
            self._close_post_print_window()

        win.protocol("WM_DELETE_WINDOW", _on_close)

    def _run_printer_completion_sequence(self) -> str:
        # Natural print completion: lift the head a little and present the part.
        commands = [
            "M17",
            "G90",
            "M211 S0",
            "M204 T80",
            "G91",
            "G1 Z20 F600",
            "G90",
            f"G1 Y95 F{SERVICE_BED_FEEDRATE}",
            "M400",
            f"M204 T{JOG_RESTORE_TRAVEL_ACCEL}",
            "M114",
        ]
        return sdtool.run_commands_wait_ok(
            self._port(),
            self._baud(),
            commands,
            per_command_timeout=45.0,
        )

    def _run_task(self, label: str, func, *, require_port: bool = True) -> None:
        if self.user_task_pending:
            self.log(f"Команда '{label}' не запущена: предыдущая USB-команда ещё выполняется.")
            return
        if require_port and not self._port():
            messagebox.showerror("Little Hands", "Сначала выбери порт принтера, нажми 'Найти' или оставь 'не подключаться'.")
            return
        if require_port:
            safety_error = self._selected_port_safety_error()
            if safety_error:
                self.disconnect_port(log_change=False)
                self.log(f"Команда '{label}' не запущена: {safety_error}")
                messagebox.showerror("Little Hands", safety_error)
                return
        self.user_task_pending = True

        def worker() -> None:
            while not self.serial_lock.acquire(timeout=0.25):
                pass
            try:
                self._post("busy", (True, f"USB: {label.lower()}"))
                self._post("log", f"{label}...")
                func()
                self._post("log", f"{label}: готово")
            except sdtool.UploadCancelled as exc:
                self._post("log", str(exc))
                self._post("files-status", str(exc))
                self._post("progress", ("Upload cancelled", 0.0))
            except Exception as exc:
                self._post("error", exc)
            finally:
                self.serial_lock.release()
                self.user_task_pending = False
                self._post("busy", (False, "USB: idle"))

        threading.Thread(target=worker, daemon=True).start()

    def pick_gcode(self) -> None:
        path = filedialog.askopenfilename(
            title="Выбрать G-code",
            parent=self.files_window if self.files_window and self.files_window.winfo_exists() else self.root,
            filetypes=[("G-code", "*.gcode *.gco *.g"), ("All files", "*.*")],
        )
        if path:
            self.local_gcode_var.set(path)
            self.dest_name_var.set(sdtool.make_sd_name(Path(path).name))
            self.files_status_var.set(f"G-code выбран: {Path(path).name}")
            if self.files_window and self.files_window.winfo_exists():
                self.files_window.deiconify()
                self.files_window.lift()
                self.files_window.focus_force()
            self._warn_if_gcode_looks_wrong(Path(path))

    def prepare_gcode(self) -> None:
        source = Path(self.local_gcode_var.get().strip()).expanduser()
        if not source.is_file():
            messagebox.showerror("Little Hands", "Выбери существующий G-code файл.")
            return
        dest = sdtool.make_sd_name(source.name)
        self.dest_name_var.set(dest)
        self.log(f"G-code подготовлен: {source.name} -> {dest}")
        if source.name.endswith("_k9xz.gcode"):
            self.log("Предупреждение: для текущего baseline нужен обычный Cura G-code, не старый _k9xz remap.")
        else:
            self.log("Baseline использует обычный Cura G-code: auto-fan FAN1 + физический swap Y/Z + запуск от сохранённого 0.")

    @staticmethod
    def _gcode_param(command: str, letter: str) -> float | None:
        match = re.search(rf"\b{re.escape(letter.upper())}\s*([-+]?\d+(?:\.\d+)?)", command.upper())
        if not match:
            return None
        try:
            return float(match.group(1))
        except ValueError:
            return None

    @staticmethod
    def _gcode_command_word(command: str) -> str:
        match = re.match(r"^(?:N\d+\s*)?([GMT]\d+(?:\.\d+)?)\b", command.strip(), re.IGNORECASE)
        return match.group(1).upper() if match else ""

    @staticmethod
    def _format_gcode_line(line_number: object) -> str:
        return f", строка {line_number}" if isinstance(line_number, int) and line_number > 0 else ""

    def _inspect_gcode_file(self, source: Path) -> dict[str, object]:
        info: dict[str, object] = {
            "read_error": "",
            "line_count": 0,
            "file_size": 0,
            "has_g28": False,
            "first_g28_line": None,
            "has_hotend_target": False,
            "hotend_target": None,
            "hotend_target_line": None,
            "has_blocking_m109": False,
            "has_little_hands_start": False,
            "has_manual_zero": False,
            "manual_zero_line": None,
            "target_machine_unknown": False,
            "target_machine_name": "",
            "start_gcode_comment": "",
            "has_slicer_fan_commands": False,
            "fan_command_count": 0,
            "has_bed_heat": False,
            "bed_heat_line": None,
            "bed_target": None,
            "has_motor_disable": False,
            "motor_disable_line": None,
            "end_has_y95": False,
            "end_has_y0": False,
            "end_soft_travel_before_y95": False,
            "extrusion_move_count": 0,
            "body_max_travel_accel": None,
            "body_max_travel_accel_line": None,
            "body_max_print_accel": None,
            "body_max_print_accel_line": None,
            "end_max_travel_accel": None,
            "end_max_travel_accel_line": None,
            "suspicious": [],
        }
        try:
            text = source.read_text(encoding="utf-8", errors="replace")
            try:
                info["file_size"] = source.stat().st_size
            except OSError:
                info["file_size"] = len(text.encode("utf-8", "replace"))
            lines = text.splitlines()
        except Exception as exc:
            info["read_error"] = str(exc)
            return info

        info["line_count"] = len(lines)
        bounds: dict[str, float] = {}
        computed_bounds: dict[str, float] = {}
        filament_m: float | None = None
        required_bounds = {"MINX", "MINY", "MINZ", "MAXX", "MAXY", "MAXZ"}
        position: dict[str, float | None] = {"X": None, "Y": None, "Z": None, "E": None}
        relative_xyz = False
        relative_e = False
        end_phase = False
        end_travel_is_soft = False

        def update_computed_bounds(axis: str, value: float) -> None:
            low = f"MIN{axis}"
            high = f"MAX{axis}"
            computed_bounds[low] = min(value, computed_bounds.get(low, value))
            computed_bounds[high] = max(value, computed_bounds.get(high, value))

        for line_number, line in enumerate(lines, start=1):
            stripped = line.strip()
            if stripped.startswith(";TIME_ELAPSED:") or stripped.startswith(";End of Gcode"):
                end_phase = True
            if stripped.startswith(";Filament used:"):
                match = re.search(r"([-+]?\d+(?:\.\d+)?)\s*m\b", stripped, re.IGNORECASE)
                if match:
                    filament_m = float(match.group(1))
            bound_match = re.match(
                r";(MINX|MINY|MINZ|MAXX|MAXY|MAXZ):\s*([-+]?\d+(?:\.\d+)?(?:e[-+]?\d+)?)",
                stripped,
                re.IGNORECASE,
            )
            if bound_match:
                try:
                    bounds[bound_match.group(1).upper()] = float(bound_match.group(2))
                except ValueError:
                    pass
            if stripped.startswith(";TARGET_MACHINE.NAME:"):
                machine = stripped.split(":", 1)[1].strip()
                info["target_machine_name"] = machine
                info["target_machine_unknown"] = machine.lower() == "unknown"
            if stripped.startswith("; Little Hands"):
                info["start_gcode_comment"] = stripped
                info["has_little_hands_start"] = True

            command = stripped.split(";", 1)[0].strip()
            if not command:
                continue
            command_upper = command.upper()
            word = self._gcode_command_word(command_upper)
            if not word:
                continue

            if word == "G90":
                relative_xyz = False
            elif word == "G91":
                relative_xyz = True
            elif word == "M82":
                relative_e = False
            elif word == "M83":
                relative_e = True

            if word == "G28":
                info["has_g28"] = True
                info["first_g28_line"] = info["first_g28_line"] or line_number

            if word == "G92":
                x = self._gcode_param(command_upper, "X")
                y = self._gcode_param(command_upper, "Y")
                z = self._gcode_param(command_upper, "Z")
                if (
                    x is not None
                    and y is not None
                    and z is not None
                    and abs(x) <= 0.001
                    and abs(y) <= 0.001
                    and abs(z) <= 0.001
                ):
                    info["has_manual_zero"] = True
                    info["manual_zero_line"] = info["manual_zero_line"] or line_number
                for axis in ("X", "Y", "Z", "E"):
                    value = self._gcode_param(command_upper, axis)
                    if value is not None:
                        position[axis] = value

            if word in {"G0", "G1", "G00", "G01"}:
                new_position = dict(position)
                for axis in ("X", "Y", "Z"):
                    value = self._gcode_param(command_upper, axis)
                    if value is None:
                        continue
                    if relative_xyz:
                        new_position[axis] = None if position[axis] is None else position[axis] + value
                    else:
                        new_position[axis] = value

                e_value = self._gcode_param(command_upper, "E")
                extruding = False
                if e_value is not None:
                    if relative_e:
                        extruding = e_value > 0.000001
                        new_position["E"] = (position["E"] or 0.0) + e_value
                    else:
                        if position["E"] is None:
                            extruding = e_value > 0.000001
                        else:
                            extruding = e_value > position["E"] + 0.000001
                        new_position["E"] = e_value
                position = new_position

                if extruding and all(position.get(axis) is not None for axis in ("X", "Y", "Z")):
                    info["extrusion_move_count"] = int(info["extrusion_move_count"]) + 1
                    update_computed_bounds("X", float(position["X"] or 0.0))
                    update_computed_bounds("Y", float(position["Y"] or 0.0))
                    update_computed_bounds("Z", float(position["Z"] or 0.0))

                if end_phase:
                    y_value = self._gcode_param(command_upper, "Y")
                    if y_value is not None and not relative_xyz:
                        if y_value >= 90.0:
                            info["end_has_y95"] = True
                            if end_travel_is_soft:
                                info["end_soft_travel_before_y95"] = True
                        if y_value <= 1.0:
                            info["end_has_y0"] = True

            if word in {"M104", "M109"}:
                target = self._gcode_param(command_upper, "S")
                if target is not None and target > 0:
                    if not info["has_hotend_target"]:
                        info["hotend_target"] = target
                        info["hotend_target_line"] = line_number
                    info["has_hotend_target"] = True
                    if word == "M109":
                        info["has_blocking_m109"] = True

            if word in {"M140", "M190"}:
                target = self._gcode_param(command_upper, "S")
                if target is not None and target > 0:
                    info["has_bed_heat"] = True
                    info["bed_heat_line"] = info["bed_heat_line"] or line_number
                    info["bed_target"] = target

            if word in {"M106", "M107"}:
                info["has_slicer_fan_commands"] = True
                info["fan_command_count"] = int(info["fan_command_count"]) + 1

            if word in {"M18", "M84"}:
                info["has_motor_disable"] = True
                info["motor_disable_line"] = info["motor_disable_line"] or line_number

            if word == "M204":
                p_value = self._gcode_param(command_upper, "P")
                t_value = self._gcode_param(command_upper, "T")
                s_value = self._gcode_param(command_upper, "S")
                print_value = max([value for value in (p_value, s_value) if value is not None], default=None)
                travel_value = max([value for value in (t_value, s_value) if value is not None], default=None)
                if end_phase:
                    if travel_value is not None and (
                        info["end_max_travel_accel"] is None or travel_value > float(info["end_max_travel_accel"])
                    ):
                        info["end_max_travel_accel"] = travel_value
                        info["end_max_travel_accel_line"] = line_number
                    if travel_value is not None:
                        end_travel_is_soft = travel_value <= K9_WARN_TRAVEL_ACCEL
                else:
                    if travel_value is not None and (
                        info["body_max_travel_accel"] is None or travel_value > float(info["body_max_travel_accel"])
                    ):
                        info["body_max_travel_accel"] = travel_value
                        info["body_max_travel_accel_line"] = line_number
                    if print_value is not None and (
                        info["body_max_print_accel"] is None or print_value > float(info["body_max_print_accel"])
                    ):
                        info["body_max_print_accel"] = print_value
                        info["body_max_print_accel_line"] = line_number

        suspicious: list[str] = []
        if filament_m is not None and filament_m <= 0.0:
            suspicious.append("Cura записала 'Filament used: 0m'")
        if required_bounds.issubset(bounds):
            if any(abs(value) > 1000 for value in bounds.values()):
                suspicious.append("Cura записала невозможные границы модели")
            for low, high in (("MINX", "MAXX"), ("MINY", "MAXY"), ("MINZ", "MAXZ")):
                if bounds[high] < bounds[low]:
                    suspicious.append(f"Cura записала {high} меньше {low}")
                    break
        info["filament_m"] = filament_m
        info["bounds"] = bounds
        info["computed_bounds"] = computed_bounds
        info["suspicious"] = suspicious
        return info

    def _gcode_validation_report(self, source: Path) -> tuple[list[str], list[str], dict[str, object]]:
        info = self._inspect_gcode_file(source)
        errors: list[str] = []
        warnings: list[str] = []
        if info.get("read_error"):
            return [f"Не удалось прочитать файл: {info['read_error']}"], warnings, info

        if source.name.lower().endswith("_k9xz.gcode"):
            errors.append("Файл похож на старый `_k9xz.gcode` с ремапом плоскости. Для текущей LH-v4 нужен обычный Cura G-code.")
        filament_m = info.get("filament_m")
        if "modulebot" in source.name.lower() and isinstance(filament_m, (int, float)) and filament_m > 15.0:
            errors.append(
                f"`moduleBot` выглядит подозрительно: Cura оценила пластик как {filament_m:.1f} m. "
                "Для проверенной ориентации этой модели ожидается примерно 9-11 m; "
                "такой файл похож на случайный upside-down/support-heavy slice."
            )
        if info.get("has_g28"):
            errors.append(
                "Найден `G28`"
                + self._format_gcode_line(info.get("first_g28_line"))
                + ". Для K9 без концевиков это опасно: старт задаётся вручную через `Запомнить старт` и `G92 X0 Y0 Z0`."
            )
        if not info.get("has_manual_zero"):
            errors.append("Не найден `G92 X0 Y0 Z0`. Этот K9 должен печатать от сохранённой стартовой позы, а не от обычного home.")
        if not info.get("has_hotend_target"):
            errors.append("Не найдена положительная цель hotend `M104 S...` или `M109 S...`; такой файл может выбраться на SD, но не начать печать.")
        else:
            target = float(info.get("hotend_target") or 0.0)
            if target < K9_HOTEND_MIN_TARGET_C or target > K9_HOTEND_MAX_TARGET_C:
                errors.append(
                    f"Цель hotend {target:g}C"
                    + self._format_gcode_line(info.get("hotend_target_line"))
                    + f" вне безопасного диапазона {K9_HOTEND_MIN_TARGET_C:g}-{K9_HOTEND_MAX_TARGET_C:g}C."
                )
            elif target < K9_HOTEND_WARN_LOW_C or target > K9_HOTEND_WARN_HIGH_C:
                warnings.append(f"Цель hotend {target:g}C необычна для текущего PLA-профиля; проверь материал и профиль Cura.")
        if info.get("has_bed_heat"):
            errors.append(
                "Найден нагрев стола `M140/M190`"
                + self._format_gcode_line(info.get("bed_heat_line"))
                + ". У нашего K9 стол внешний, в G-code температура стола должна быть 0C."
            )
        if info.get("has_motor_disable"):
            errors.append(
                "Найдено отключение моторов `M18/M84`"
                + self._format_gcode_line(info.get("motor_disable_line"))
                + ". После печати Little Hands должен сохранить возможность recovery-движений."
            )
        if info.get("target_machine_unknown") and not info.get("has_little_hands_start"):
            errors.append("`TARGET_MACHINE.NAME:Unknown` без Little Hands start-комментария: файл похож на старый или слайсился не на `lilHands K9 warm mat`.")
        elif info.get("target_machine_unknown"):
            warnings.append("Cura пишет `TARGET_MACHINE.NAME:Unknown`, но Little Hands start найден; это допустимо для текущего custom-профиля.")
        if not info.get("has_little_hands_start"):
            warnings.append("Не найден комментарий `Little Hands manual-zero workflow`; если файл сделан другим слайсером, особенно внимательно проверь start/end G-code.")

        for reason in info.get("suspicious", []):
            errors.append(str(reason) + "; переслайсь заново и проверь Preview перед записью на SD.")

        header_bounds = dict(info.get("bounds") or {})
        computed_bounds = dict(info.get("computed_bounds") or {})
        required_bounds = {"MINX", "MINY", "MINZ", "MAXX", "MAXY", "MAXZ"}
        bounds = header_bounds if required_bounds.issubset(header_bounds) else computed_bounds
        bounds_source = "Cura header" if bounds is header_bounds else "расчёт по extrusion moves"
        if not required_bounds.issubset(bounds):
            errors.append("Не удалось определить печатные XY/Z bounds. Это похоже не на полноценный sliced G-code для печати.")
        else:
            min_x = float(bounds["MINX"])
            max_x = float(bounds["MAXX"])
            min_y = float(bounds["MINY"])
            max_y = float(bounds["MAXY"])
            min_z = float(bounds["MINZ"])
            max_z = float(bounds["MAXZ"])
            if max_x <= min_x or max_y <= min_y or max_z < min_z:
                errors.append(f"Некорректные bounds ({bounds_source}): min/max перепутаны или размер модели нулевой.")
            if min_x < -K9_GCODE_BOUNDS_TOLERANCE_MM or max_x > K9_PRINT_BED_SIZE_MM + K9_GCODE_BOUNDS_TOLERANCE_MM:
                errors.append(f"X bounds {min_x:.2f}..{max_x:.2f} выходят за стол {K9_PRINT_BED_SIZE_MM:g} mm.")
            if min_y < -K9_GCODE_BOUNDS_TOLERANCE_MM or max_y > K9_PRINT_BED_SIZE_MM + K9_GCODE_BOUNDS_TOLERANCE_MM:
                errors.append(f"Y bounds {min_y:.2f}..{max_y:.2f} выходят за стол {K9_PRINT_BED_SIZE_MM:g} mm.")
            if min_z < -K9_GCODE_BOUNDS_TOLERANCE_MM or max_z > K9_MAX_PRINT_Z_MM + K9_GCODE_BOUNDS_TOLERANCE_MM:
                errors.append(f"Z bounds {min_z:.2f}..{max_z:.2f} выходят за высоту {K9_MAX_PRINT_Z_MM:g} mm.")
            info["validated_bounds_source"] = bounds_source
            info["validated_bounds"] = bounds

        if int(info.get("extrusion_move_count") or 0) <= 0:
            errors.append("Не найдено печатных extrusion-движений `G1 ... E...` с XY/Z координатами. Это не похоже на модель для печати.")

        body_travel = info.get("body_max_travel_accel")
        if isinstance(body_travel, (int, float)):
            if body_travel > K9_MAX_BODY_TRAVEL_ACCEL:
                errors.append(
                    f"`M204 T{body_travel:g}`"
                    + self._format_gcode_line(info.get("body_max_travel_accel_line"))
                    + " слишком резкий для стола K9; это может снова выглядеть как 'сломанный' Y-канал."
                )
            elif body_travel > K9_WARN_TRAVEL_ACCEL:
                warnings.append(f"Travel acceleration `M204 T{body_travel:g}` выше осторожного baseline; если стол трещит или пропускает шаги, переслайсь мягче.")
        body_print = info.get("body_max_print_accel")
        if isinstance(body_print, (int, float)):
            if body_print > K9_MAX_BODY_PRINT_ACCEL:
                errors.append(
                    f"`M204 P{body_print:g}`"
                    + self._format_gcode_line(info.get("body_max_print_accel_line"))
                    + " слишком резкий для текущего K9 baseline."
                )
            elif body_print > K9_WARN_PRINT_ACCEL:
                warnings.append(f"Print acceleration `M204 P{body_print:g}` выше осторожного baseline; это может усилить резонанс.")

        if info.get("has_blocking_m109"):
            warnings.append("Есть блокирующий `M109`; при заливке через Little Hands ранний `M109` будет заменён на `M104`, а приложение прогреет hotend перед SD-стартом.")
        if info.get("has_slicer_fan_commands"):
            warnings.append(
                f"Есть slicer-команды вентилятора `M106/M107` ({info.get('fan_command_count')}); при заливке через Little Hands они будут удалены, потому что вентилятор у K9 firmware-managed."
            )
        if info.get("end_has_y0"):
            warnings.append("В конце найден `G1 Y0`: старые файлы могут уводить стол не к пользователю. Лучше переслайсить на текущем профиле.")
        if not info.get("end_has_y95"):
            warnings.append("В конце не найдено предъявление стола `G1 Y95`. Печать может завершиться без удобного выезда стола к пользователю.")
        end_travel = info.get("end_max_travel_accel")
        if (
            isinstance(end_travel, (int, float))
            and end_travel > K9_MAX_BODY_TRAVEL_ACCEL
            and not info.get("end_soft_travel_before_y95")
        ):
            warnings.append("В финальном хвосте Cura есть высокий `M204 T...`; это допустимо только если end-gcode затем задаёт мягкое `M204` перед движением стола.")

        return errors, warnings, info

    def _format_gcode_validation_report(
        self,
        source: Path,
        errors: list[str],
        warnings: list[str],
        info: dict[str, object],
    ) -> str:
        size = int(info.get("file_size") or 0)
        size_label = f"{size / 1024 / 1024:.2f} MiB" if size else "unknown"
        lines = [
            f"Файл: {source.name}",
            f"Строк: {info.get('line_count') or 0}; размер: {size_label}",
        ]
        target = info.get("hotend_target")
        if isinstance(target, (int, float)):
            lines.append(f"Hotend target: {target:g}C")
        bounds = info.get("validated_bounds")
        if isinstance(bounds, dict):
            lines.append(
                "Bounds: "
                f"X {float(bounds['MINX']):.2f}..{float(bounds['MAXX']):.2f}, "
                f"Y {float(bounds['MINY']):.2f}..{float(bounds['MAXY']):.2f}, "
                f"Z {float(bounds['MINZ']):.2f}..{float(bounds['MAXZ']):.2f}"
            )
        if info.get("manual_zero_line"):
            lines.append(f"Manual zero: G92 X0 Y0 Z0 на строке {info['manual_zero_line']}")
        if errors:
            lines.append("")
            lines.append("Блокирующие ошибки:")
            lines.extend(f"- {item}" for item in errors)
        if warnings:
            lines.append("")
            lines.append("Предупреждения:")
            lines.extend(f"- {item}" for item in warnings)
        if not errors and not warnings:
            lines.append("")
            lines.append("Проверка пройдена: G-code выглядит подходящим для текущего K9 / Little Hands workflow.")
        return "\n".join(lines)

    def check_gcode_validity(self) -> None:
        source = Path(self.local_gcode_var.get().strip()).expanduser()
        if not source.is_file():
            messagebox.showerror("Little Hands", "Выбери существующий G-code файл.")
            return
        errors, warnings, info = self._gcode_validation_report(source)
        report = self._format_gcode_validation_report(source, errors, warnings, info)
        if errors:
            self.files_status_var.set(f"G-code не прошёл проверку: {errors[0]}")
            self.log("G-code не прошёл проверку:\n" + report)
            messagebox.showerror("Little Hands — проверка G-code", report)
        elif warnings:
            self.files_status_var.set(f"G-code прошёл проверку с предупреждениями: {warnings[0]}")
            self.log("G-code прошёл проверку с предупреждениями:\n" + report)
            messagebox.showwarning("Little Hands — проверка G-code", report)
        else:
            self.files_status_var.set(f"G-code проверен: {source.name}")
            self.log("G-code проверен:\n" + report)
            messagebox.showinfo("Little Hands — проверка G-code", report)

    def _warn_if_gcode_looks_wrong(self, source: Path) -> None:
        errors, warnings, info = self._gcode_validation_report(source)
        if errors:
            self.files_status_var.set(f"G-code не прошёл проверку: {errors[0]}")
            for reason in errors[:6]:
                self.log(f"G-code: блокирующая проблема: {reason}")
        elif warnings:
            self.files_status_var.set(f"G-code выбран с предупреждениями: {warnings[0]}")
            for reason in warnings[:6]:
                self.log(f"G-code: предупреждение: {reason}")
        else:
            target = info.get("hotend_target")
            target_text = f", hotend {float(target):g}C" if isinstance(target, (int, float)) else ""
            self.files_status_var.set(f"G-code проверен: {source.name}{target_text}")

    def _validate_gcode_for_current_k9(self, source: Path) -> tuple[bool, str]:
        errors, warnings, info = self._gcode_validation_report(source)
        if errors:
            return False, self._format_gcode_validation_report(source, errors, warnings, info)
        if warnings:
            return True, self._format_gcode_validation_report(source, errors, warnings, info)
        return True, f"G-code проверен: {source.name}"

    def _prepare_k9_gcode_for_sd(self, source: Path, target: Path) -> tuple[bool, float | None, int]:
        lines = source.read_text(encoding="utf-8", errors="replace").splitlines()
        patched = False
        hotend_target: float | None = None
        removed_fan_commands = 0
        for index, line in enumerate(lines[:120]):
            stripped = line.strip()
            if stripped.startswith(";LAYER:") or stripped.startswith(";LAYER_COUNT:"):
                break
            if not stripped or stripped.startswith(";"):
                continue
            command = stripped.split(";", 1)[0].strip()
            if not command.upper().startswith("M109"):
                continue
            match = HOTEND_TARGET_RE.search(command)
            if not match:
                continue
            hotend_target = float(match.group(1))
            prefix = line[: len(line) - len(line.lstrip())]
            lines[index] = (
                f"{prefix}M104 S{hotend_target:g} ; LH: non-blocking heat target; "
                "Little Hands preheats before SD start"
            )
            patched = True
            break
        for index, line in enumerate(lines):
            stripped = line.strip()
            if not stripped or stripped.startswith(";"):
                continue
            command = stripped.split(";", 1)[0].strip()
            command_upper = command.upper()
            if not command_upper.startswith(("M106", "M107")):
                continue
            prefix = line[: len(line) - len(line.lstrip())]
            comment = ""
            if ";" in line:
                comment = " ;" + line.split(";", 1)[1]
            lines[index] = (
                f"{prefix}; LH: removed slicer fan command '{command_upper}' "
                f"because K9 has one firmware-managed hotend fan{comment}"
            )
            removed_fan_commands += 1
            patched = True
        if patched:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return patched, hotend_target, removed_fan_commands

    def _prepared_gcode_for_sd_upload(self, source: Path) -> tuple[Path, bool]:
        info = self._inspect_gcode_file(source)
        if not info.get("has_blocking_m109") and not info.get("has_slicer_fan_commands"):
            return source, False
        prepared_dir = GUI_EXPORT_DIR / "prepared"
        prepared = prepared_dir / f"{source.stem}_lh_k9safe{source.suffix or '.gcode'}"
        patched, target, removed_fan_commands = self._prepare_k9_gcode_for_sd(source, prepared)
        if not patched:
            return source, False
        target_text = f"{target:.0f}C" if isinstance(target, (int, float)) else "рабочей температуры"
        changes: list[str] = []
        if info.get("has_blocking_m109"):
            changes.append(f"ранний блокирующий M109 заменён на M104; hotend будет прогрет до {target_text} перед SD-стартом")
        if removed_fan_commands:
            changes.append(f"удалены команды вентилятора M106/M107 ({removed_fan_commands}), потому что у K9 один firmware-managed hotend fan")
        self._post("log", "G-code подготовлен для K9: " + "; ".join(changes) + ".")
        return prepared, True

    def pick_firmware(self) -> None:
        path = filedialog.askopenfilename(
            title="Выбрать прошивку",
            parent=self.files_window if self.files_window and self.files_window.winfo_exists() else self.root,
            filetypes=[("Firmware", "*.bin"), ("All files", "*.*")],
        )
        if path:
            self.firmware_var.set(path)
            self.files_status_var.set(f"Прошивка выбрана: {Path(path).name}")
            if self.files_window and self.files_window.winfo_exists():
                self.files_window.deiconify()
                self.files_window.lift()
                self.files_window.focus_force()

    def refresh_status(self) -> None:
        def task() -> None:
            caps, sd = sdtool.preflight(self._port(), self._baud())
            self.printer_halted = False
            fw_line = next((line for line in caps.splitlines() if line.startswith("FIRMWARE_NAME:")), "")
            if fw_line:
                self._post("fw", self._format_fw_line(fw_line))
            self._post("sd", sd.strip() or "SD: unknown")
            self._post("metrics", ("m115", caps))
            self._post("log", caps.strip())
            if self._home_is_trusted():
                self._post("log", "Статус снят: сохранённая стартовая поза в приложении оставлена активной.")
            else:
                self._post("log", "Статус снят. Если был power cycle или перезапуск приложения, выставь стартовую позу и нажми 'Запомнить старт'.")

        self._run_task("Проверка статуса", task)

    def refresh_metrics(self) -> None:
        self.views.select(self.metrics_frame)
        self.metrics_text.configure(state="normal")
        self.metrics_text.delete("1.0", "end")
        self.metrics_text.insert("1.0", {
            "ru": "Собираю USB-метрики...\n",
            "en": "Collecting USB metrics...\n",
            "zh": "正在收集 USB 指标...\n",
        }[self.lang_var.get().strip() or "ru"])
        self.metrics_text.configure(state="disabled")

        def task() -> None:
            caps, sd = sdtool.preflight(self._port(), self._baud())
            m503 = sdtool.query_command(self._port(), self._baud(), "M503", wait_before_read=0.6, read_seconds=2.0)
            m114 = sdtool.query_command(self._port(), self._baud(), "M114", wait_before_read=0.3, read_seconds=1.0)
            m105 = sdtool.query_command(self._port(), self._baud(), "M105", wait_before_read=0.3, read_seconds=1.0)
            m27 = sdtool.query_command(self._port(), self._baud(), "M27", wait_before_read=0.3, read_seconds=1.0)
            fw_line = next((line for line in caps.splitlines() if line.startswith("FIRMWARE_NAME:")), "")
            if fw_line:
                self._post("fw", self._format_fw_line(fw_line))
            self._post("sd", sd.strip() or "SD: unknown")
            pos_line = next((line.strip() for line in m114.splitlines() if "X:" in line and "Y:" in line and "Z:" in line), "").strip()
            if pos_line:
                self._post("pos", pos_line)
            self._post("metrics", ("m115", caps))
            self._post("metrics", ("m503", m503))
            self._post("metrics", ("m114", m114))
            self._post("metrics", ("m105", m105))
            self._post("metrics", ("m27", m27))

        self._run_task("Снятие всех USB-метрик", task)

    def save_log_snapshot(self) -> None:
        stamp = time.strftime("%Y%m%d_%H%M%S")
        desktop_dir = Path.home() / "Desktop"
        desktop_dir.mkdir(parents=True, exist_ok=True)
        target_path = filedialog.asksaveasfilename(
            title="Сохранить лог Little Hands",
            initialdir=str(desktop_dir),
            initialfile=f"little_hands_runtime_{stamp}.log",
            defaultextension=".log",
            filetypes=[("Log files", "*.log"), ("Text files", "*.txt"), ("All files", "*.*")],
        )
        if not target_path:
            self.log("Сохранение лога отменено")
            return
        target = Path(target_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        if RUNTIME_LOG_PATH.is_file():
            shutil.copy2(RUNTIME_LOG_PATH, target)
        else:
            target.write_text("", encoding="utf-8")
        self.log(f"Лог сохранён: {target}")
        self.views.select(self.log_frame)
        messagebox.showinfo("Little Hands", f"Лог сохранён:\n{target}")

    def reset_usb_session(self) -> None:
        self.monitor_enabled = False
        self.user_task_pending = True

        def worker() -> None:
            acquired = False
            try:
                self._post("busy", (True, "USB: reset"))
                self._post("log", "Сброс USB: ставлю автоопрос на паузу и жду освобождения порта...")
                deadline = time.monotonic() + 8.0
                while time.monotonic() < deadline:
                    if self.serial_lock.acquire(blocking=False):
                        acquired = True
                        break
                    time.sleep(0.1)

                if not acquired:
                    self._post(
                        "log",
                        "Сброс USB: порт всё ещё занят текущей операцией. Если это не отпустит через пару секунд, "
                        "закрой Little Hands, сделай power cycle принтера и открой приложение снова.",
                    )
                    return

                out = sdtool.query_command(
                    self._port(),
                    self._baud(),
                    "M110 N0",
                    wait_before_read=0.3,
                    read_seconds=0.8,
                    sync=False,
                )
                temp = sdtool.query_command(self._port(), self._baud(), "M105", wait_before_read=0.2, read_seconds=0.8)
                match = TEMP_RE.search(temp)
                if match:
                    heater_match = HEATER_RE.search(temp)
                    heater = int(heater_match.group(1)) if heater_match else None
                    self._post("temp", (float(match.group(1)), float(match.group(2)), heater))
                self._post("metrics", ("m105", temp))
                self._post("log", (out + temp).strip() or "Сброс USB выполнен")
            except Exception as exc:
                self._post("error", exc)
            finally:
                if acquired:
                    self.serial_lock.release()
                self.user_task_pending = False
                self.monitor_enabled = True
                self._post("busy", (False, "USB: idle"))

        threading.Thread(target=worker, daemon=True).start()

    def refresh_sd_files(self) -> None:
        def task() -> None:
            files, status, raw = sdtool.read_sd_listing(self._port(), self._baud())
            if status == "ok":
                self._post("sd-files", files)
                self._post("log", f"SD: найдено файлов {len(files)}")
            elif status == "busy":
                self._post("sd", "SD: занято печатью, список недоступен")
                self._post("log", "Во время активной SD-печати список файлов сейчас недоступен.")
            else:
                self._post("sd", "SD: список недоступен")
                excerpt = " ".join(raw.strip().split())
                if excerpt:
                    self._post("log", f"Принтер не вернул список файлов SD. Последний ответ: {excerpt[:260]}")
                else:
                    self._post(
                        "log",
                        "Принтер не вернул список файлов SD: пустой ответ на M20 L / M20 после M21.",
                    )

        self._run_task("Чтение списка SD", task)

    def upload_gcode(self) -> None:
        source = Path(self.local_gcode_var.get().strip()).expanduser().resolve()
        if not source.is_file():
            messagebox.showerror("K9 Control Center", "Выбери существующий G-code файл.")
            return
        ok, reason = self._validate_gcode_for_current_k9(source)
        if not ok:
            messagebox.showerror("Little Hands", reason)
            self.log(reason)
            return
        if reason:
            self.log(reason)
        dest = self.dest_name_var.get().strip() or source.name
        self.upload_cancel_requested = False

        def task() -> None:
            self._post("close-files-window", None)
            self._post("upload-cancel-visible", (True, False))
            last_stage = {"name": None}

            def on_progress(stage: str, percent: float) -> None:
                if self.upload_cancel_requested:
                    raise sdtool.UploadCancelled("Загрузка G-code отменена пользователем.")
                self._post("progress", (f"{stage}: {percent:.1f}%", percent))
                self._post("files-status", f"Заливка G-code: {stage} {percent:.1f}%")
                if last_stage["name"] != stage:
                    last_stage["name"] = stage
                    self._post("log", f"Этап записи: {stage}")

            upload_source, patched = self._prepared_gcode_for_sd_upload(source)
            size_mib = upload_source.stat().st_size / (1024 * 1024)
            self._post("log", f"Локальный файл: {source}")
            if patched:
                self._post("log", f"На SD будет записана подготовленная копия: {upload_source}")
            self._post("log", f"Размер файла: {size_mib:.2f} MiB. Большие G-code могут писаться 1-5 минут.")
            self._post("progress", ("Upload (preflight): 0.0%", 0.0))
            self._post("files-status", f"Заливка G-code: preflight 0.0%")
            try:
                method = sdtool.upload_gcode_auto(self._port(), self._baud(), upload_source, dest, progress_cb=on_progress)
            except sdtool.UploadCancelled as exc:
                _ok, msg = self._cleanup_cancelled_upload(dest)
                raise sdtool.UploadCancelled(msg) from exc
            self._remember_gcode_profile(dest, source.name, upload_source)
            self._post("progress", ("Upload complete: 100.0%", 100.0))
            self._post("files-status", f"G-code залит: {source.name} -> {dest} ({method})")
            self._post("log", f"Залит G-code: {source.name} -> {dest} ({method})")
            files = sdtool.list_files(self._port(), self._baud())
            self._post("sd-files", files)
            self._post("upload-cancel-visible", (False, False))

        self._run_task("Заливка G-code на SD", task)

    def upload_and_start_gcode(self) -> None:
        if not self._guard_post_print_recovery():
            return
        if not self._home_is_trusted():
            self._show_missing_start_zero()
            return
        source = Path(self.local_gcode_var.get().strip()).expanduser().resolve()
        if not source.is_file():
            messagebox.showerror("Little Hands", "Выбери существующий G-code файл.")
            return
        ok, reason = self._validate_gcode_for_current_k9(source)
        if not ok:
            messagebox.showerror("Little Hands", reason)
            self.log(reason)
            return
        if reason:
            self.log(reason)
        dest = (self.dest_name_var.get().strip() or sdtool.make_sd_name(source.name))
        self.dest_name_var.set(dest)
        self.upload_cancel_requested = False

        def task() -> None:
            self._post("close-files-window", None)
            self._post("upload-cancel-visible", (True, False))
            last_stage = {"name": None}

            def on_progress(stage: str, percent: float) -> None:
                if self.upload_cancel_requested:
                    raise sdtool.UploadCancelled("Загрузка G-code отменена пользователем; печать не запускалась.")
                self._post("progress", (f"{stage}: {percent:.1f}%", percent))
                self._post("files-status", f"Заливка и старт: {stage} {percent:.1f}%")
                if last_stage["name"] != stage:
                    last_stage["name"] = stage
                    self._post("log", f"Этап записи: {stage}")

            upload_source, patched = self._prepared_gcode_for_sd_upload(source)
            size_mib = upload_source.stat().st_size / (1024 * 1024)
            self._post("log", f"Локальный файл: {source}")
            if patched:
                self._post("log", f"На SD будет записана подготовленная копия: {upload_source}")
            self._post("log", f"Размер файла: {size_mib:.2f} MiB. Большие G-code могут писаться 1-5 минут.")
            self._post("files-status", "Заливка и старт: preflight 0.0%")
            try:
                method = sdtool.upload_gcode_auto(self._port(), self._baud(), upload_source, dest, progress_cb=on_progress)
            except sdtool.UploadCancelled as exc:
                _ok, msg = self._cleanup_cancelled_upload(dest)
                raise sdtool.UploadCancelled(f"{msg} Печать не запускалась.") from exc
            self._post("files-status", f"G-code залит: {source.name} -> {dest} ({method}). Запускаю печать...")
            self._post("log", f"Залит G-code: {source.name} -> {dest} ({method})")
            files = sdtool.list_files(self._port(), self._baud())
            self._post("sd-files", files)
            self._post("upload-cancel-visible", (False, False))
            target = self._hotend_target_for_print(dest, source.name, upload_source)
            self._preheat_hotend_for_sd_start(target)
            self._prime_print_end_contract(dest, source.name, upload_source)
            try:
                if self.at_saved_start_pose:
                    out = sdtool.start_sd_print(self._port(), self._baud(), dest)
                else:
                    out = sdtool.start_sd_print_from_home(self._port(), self._baud(), dest)
                    self.at_saved_start_pose = True
            except Exception:
                self._clear_predicted_print_end()
                self._set_home_trust(HOME_TRUST_UNCERTAIN, "upload-and-start failed after motion/start attempt", log_change=True)
                raise
            self._mark_sd_start_sent(dest, source.name)
            self._post("log", out.strip() or f"Печать запущена от сохранённого старта: {source.name}")
            self.at_saved_start_pose = False
            self.post_print_pose_known = False
            self.post_print_pose = None
            self.print_was_active = False
            self.suppress_next_completion_chime = False

        self._run_task("Заливка и запуск G-code", task)

    def flash_firmware(self) -> None:
        source = Path(self.firmware_var.get().strip()).expanduser()
        if not source.is_file():
            messagebox.showerror("K9 Control Center", "Выбери существующий .bin файл прошивки.")
            return
        if not messagebox.askyesno(
            "K9 Control Center",
            "Залить прошивку на SD принтера и выполнить M997?\nПосле этого принтер перезагрузится.",
        ):
            return
        self.files_status_var.set(f"Шью: {source.name} ...")

        def task() -> None:
            sdtool.flash_firmware(self._port(), self._baud(), source, purge_bin=True)
            self._set_pending_flash_finalize(source.name)
            result = (
                f"Прошивка отправлена: {source.name} -> mksLite.bin, M997 отправлен. "
                "Передача по USB завершилась успешно. После перезапуска принтера Little Hands автоматически выполнит "
                "M502/M500 и проверит EEPROM. После прошивки на карте вручную оставь EEPROM.DAT и нужные G-code, "
                "а mksLite.bin / mksLite.CUR удали."
            )
            self._post("files-status", result)
            self._post("log", result)
            self._post("info", result)

        self._run_task("Заливка прошивки", task)

    def create_eeprom_via_printer(self) -> None:
        if not messagebox.askyesno(
            "Little Hands",
            "Попробовать создать EEPROM через принтер командами M502/M500?\n"
            "После этого проверь наличие EEPROM.DAT на карте вручную.",
        ):
            return

        self.files_status_var.set("Создаю EEPROM через M502/M500 ...")

        def task() -> None:
            out = sdtool.run_commands(
                self._port(),
                self._baud(),
                ["M502", "M500", "M21"],
                settle_after_each=0.5,
                final_wait=1.5,
                read_seconds=3.0,
            )
            self._post("metrics", ("m503", sdtool.query_command(self._port(), self._baud(), "M503", wait_before_read=0.5, read_seconds=2.0)))
            msg = (
                "Команды M502/M500 отправлены. Проверь наличие EEPROM.DAT на карте вручную. "
                "Если эта прошивка не показывает файл в списке SD, ориентируйся на успешный ответ Settings Stored."
            )
            if "Settings Stored" in out:
                self.eeprom_confirmed = True
            self._post("files-status", msg)
            self._post("log", (out.strip() + "\n" + msg).strip())
            self._post("info", msg)

        self._run_task("Создание EEPROM", task)

    def _selected_sd_path(self) -> str | None:
        display = self._selected_sd_display()
        if not display:
            return None
        return self.sd_display_to_path.get(display, display)

    def _selected_print_sd_path(self) -> str | None:
        selection = self.sd_print_listbox.curselection()
        if not selection:
            return None
        display = self.sd_print_listbox.get(selection[0])
        if display == "(empty)":
            return None
        return self.sd_display_to_path.get(display, display)

    def _guard_post_print_recovery(self) -> bool:
        if not self.post_print_recovery_required:
            return True
        self.log("Старт печати заблокирован: сначала выполни послепечатный цикл из инструкции.")
        self._show_post_print_recovery_window("blocked-start")
        return False

    def start_selected_print(self) -> None:
        if not self._guard_post_print_recovery():
            return
        path = self._selected_print_sd_path()
        display = self._selected_sd_display() or path or "-"
        if not path:
            messagebox.showerror("K9 Control Center", "Выбери файл в секции 'Файлы для печати'.")
            return
        if not self._home_is_trusted():
            self._show_missing_start_zero()
            return

        def task() -> None:
            source_for_profile = self._source_for_print(path, display)
            target = self._hotend_target_for_print(path, display, source_for_profile)
            self._preheat_hotend_for_sd_start(target)
            self._prime_print_end_contract(path, display, source_for_profile)
            try:
                out = sdtool.start_sd_print(self._port(), self._baud(), path)
            except Exception:
                self._clear_predicted_print_end()
                raise
            self._mark_sd_start_sent(path, display)
            self._post("log", out.strip() or f"Печать запущена: {display}")
            self.at_saved_start_pose = False
            self.post_print_pose_known = False
            self.post_print_pose = None
            self.print_was_active = False
            self.suppress_next_completion_chime = False

        self._run_task("Запуск SD-печати", task)

    def start_selected_print_with_home(self) -> None:
        if not self._guard_post_print_recovery():
            return
        path = self._selected_print_sd_path()
        display = self._selected_sd_display() or path or "-"
        if not path:
            messagebox.showerror("Little Hands", "Выбери файл в секции 'Файлы для печати'.")
            return
        if not self._home_is_trusted():
            self._show_missing_start_zero()
            return

        def task() -> None:
            source_for_profile = self._source_for_print(path, display)
            target = self._hotend_target_for_print(path, display, source_for_profile)
            self._preheat_hotend_for_sd_start(target)
            self._prime_print_end_contract(path, display, source_for_profile)
            try:
                if self.at_saved_start_pose:
                    out = sdtool.start_sd_print(self._port(), self._baud(), path)
                    start_note = "Печать с SD запущена из уже сохранённой стартовой позы"
                else:
                    out = sdtool.start_sd_print_from_home(self._port(), self._baud(), path)
                    self.at_saved_start_pose = True
                    start_note = "Печать с SD запущена от сохранённого старта"
            except Exception:
                self._clear_predicted_print_end()
                self._set_home_trust(HOME_TRUST_UNCERTAIN, "SD print start failed after motion/start attempt", log_change=True)
                raise
            self._mark_sd_start_sent(path, display)
            self._post("log", out.strip() or f"{start_note}: {display}")
            self.at_saved_start_pose = False
            self.post_print_pose_known = False
            self.post_print_pose = None
            self.print_was_active = False
            self.suppress_next_completion_chime = False

        self._run_task("Запуск печати с SD", task)

    def _ensure_eeprom_present(self) -> bool:
        if self.sd_has_eeprom:
            return True

        self._post("files-status", "EEPROM.DAT отсутствует -> пытаюсь инициализировать через M502/M500 ...")
        self._post("log", "EEPROM.DAT отсутствует -> пытаюсь инициализировать через M502/M500 ...")
        try:
            out = sdtool.run_commands(
                self._port(),
                self._baud(),
                ["M502", "M500", "M21"],
                settle_after_each=0.5,
                final_wait=1.5,
                read_seconds=3.0,
            )
            self._post("metrics", ("m503", sdtool.query_command(self._port(), self._baud(), "M503", wait_before_read=0.5, read_seconds=2.0)))
            for attempt in range(4):
                if attempt:
                    time.sleep(0.8)
                files, status, _raw = sdtool.read_sd_listing(self._port(), self._baud())
                if status == "ok":
                    self._post("sd-files", files)
                    lowered = [Path((entry.split()[0] if " " in entry else entry)).name.lower() for entry in files]
                    if "eeprom.dat" in lowered:
                        self.eeprom_confirmed = True
                        self._post("files-status", "EEPROM.DAT создан. Теперь печать разрешена.")
                        self._post("log", out.strip() or "EEPROM.DAT создан. Теперь печать разрешена.")
                        return True
            if "Settings Stored" in out:
                self.eeprom_confirmed = True
                files = self.sd_list[:] if self.sd_list else []
                if files:
                    lowered = [Path((entry.split()[0] if " " in entry else entry)).name.lower() for entry in files]
                    self._update_sd_notice(lowered)
                msg = "EEPROM сохранён командой M500. Файл может не отображаться в списке SD этой прошивки. Печать разрешена."
                self._post("files-status", msg)
                self._post("log", msg)
                return True
            msg = (
                "EEPROM.DAT не создан. Печать заблокирована. Оставь SD в принтере, "
                "выключи принтер по питанию на 5–10 секунд, включи снова и нажми 'Обновить список'."
            )
            self._post("files-status", msg)
            self._post("log", msg)
            self._post("info", msg)
            return False
        except Exception as exc:
            msg = f"Не удалось инициализировать EEPROM.DAT: {exc}"
            self._post("files-status", msg)
            self._post("log", msg)
            self._post("info", msg)
            return False

    def pause_print(self) -> None:
        def task() -> None:
            out = sdtool.pause_sd_print(self._port(), self._baud())
            self._post("log", out.strip() or "Пауза отправлена")

        self._run_task("Пауза печати", task)

    def resume_print(self) -> None:
        def task() -> None:
            out = sdtool.resume_sd_print(self._port(), self._baud())
            self._post("log", out.strip() or "Продолжение отправлено")

        self._run_task("Продолжение печати", task)

    def _clear_print_session_state(self, progress_label: str, progress_value: float = 0.0) -> None:
        self.current_print_file = "-"
        self.current_print_display = "-"
        self.current_print_start_ts = None
        self.post_m24_usb_quiet_until = 0.0
        self.last_post_m24_quiet_log_ts = 0.0
        self.current_print_progress_pct = None
        self.print_state_restored_from_log = False
        self.print_was_active = False
        self.print_completion_armed = False
        self.sd_progress_sample_count = 0
        self.first_sd_progress_ts = None
        self.last_sd_progress_ts = None
        self.print_start_watchdog_alerted = False
        self.at_saved_start_pose = False
        self.post_print_pose_known = False
        self.post_print_pose = None
        self._clear_predicted_print_end(save=False)
        self._save_print_state("idle", force=True)
        self._post("active-sd", "Печатается: -")
        self._post("progress", (progress_label, progress_value))
        self._post("sd", "SD: idle")

    def stop_print(self) -> None:
        def task() -> None:
            self.suppress_next_completion_chime = True
            out = ""
            error_text = None
            stop_pose: tuple[float, float, float] | None = None
            stopped_display = self.current_print_display if self.current_print_display != "-" else self.current_print_file
            try:
                out, stop_pose = sdtool.stop_sd_print_with_position(self._port(), self._baud())
            except Exception as exc:
                error_text = str(exc)
            finally:
                self._clear_print_session_state("Печать: остановлена", 0.0)
                self.bed_clear_before_go_start_required = True
                self._set_home_trust(
                    HOME_TRUST_UNCERTAIN if stop_pose is not None else HOME_TRUST_INVALID,
                    "print stopped; physical position must be recovered or start must be re-saved",
                    log_change=True,
                )
                self.stopped_print_pose = stop_pose
                self.stopped_print_display = stopped_display or "-"
            if out.strip():
                self._post("log", out.strip())
            elif error_text:
                self._post("log", f"Стоп отправлен локально, но принтер ответил неуверенно: {error_text}")
            else:
                self._post("log", "Стоп отправлен")
            self._post(
                "log",
                "После остановки печати сохранённый старт сброшен: эта K9 может сообщать X0/Y0 после Stop, "
                "даже если физически сопло осталось не в стартовой X/Y-позе. После удаления пластика со стола "
                "можно нажать 'К старту': Little Hands попробует вернуться по позиции, снятой перед M524.",
            )
            if stop_pose is not None:
                self._post(
                    "log",
                    f"Позиция остановки сохранена до M524: X{stop_pose[0]:.2f} Y{stop_pose[1]:.2f} Z{stop_pose[2]:.2f}.",
                )
            else:
                self._post(
                    "log",
                    "Позицию остановки до M524 получить не удалось. Автоматический возврат к старту после этого стопа недоступен.",
                )

        self._run_task("Остановка печати", task)

    def hard_stop(self) -> None:
        if not messagebox.askyesno(
            "Little Hands",
            "Выполнить жёсткий стоп?\n"
            "Будет отправлена остановка печати, снят нагрев, отключены моторы и сброшено состояние задания в приложении.",
        ):
            return

        def task() -> None:
            self.suppress_next_completion_chime = True
            out = ""
            error_text = None
            try:
                out = sdtool.run_commands(
                    self._port(),
                    self._baud(),
                    ["M108", "M524", "M104 S0", "M140 S0", "M107", "M400", "M18"],
                    settle_after_each=0.4,
                    final_wait=1.2,
                    read_seconds=2.5,
                )
            except Exception as exc:
                error_text = str(exc)
            finally:
                self._clear_print_session_state("Печать: жёсткий стоп", 0.0)
                self.bed_clear_before_go_start_required = True
                self._set_home_trust(HOME_TRUST_INVALID, "hard stop disabled steppers", log_change=True)
                self.stopped_print_pose = None
                self.stopped_print_display = "-"
            if out.strip():
                self._post("log", out.strip())
            elif error_text:
                self._post("log", f"Жёсткий стоп выполнен локально, но принтер ответил неуверенно: {error_text}")
            else:
                self._post("log", "Жёсткий стоп отправлен")

        self._run_task("Жёсткий стоп", task)

    def delete_selected_file(self) -> None:
        path = self._selected_sd_path()
        if not path:
            messagebox.showerror("K9 Control Center", "Выбери файл на SD.")
            return
        if not messagebox.askyesno("K9 Control Center", f"Удалить {path} с SD принтера?"):
            return

        def task() -> None:
            out = sdtool.delete_file(self._port(), self._baud(), path)
            self._post("log", out.strip() or f"Удалён {path}")
            files = sdtool.list_files(self._port(), self._baud())
            self._post("sd-files", files)

        self._run_task("Удаление файла", task)

    def home_all(self) -> None:
        def task() -> None:
            self._set_home_trust(HOME_TRUST_INVALID, "G28 is disabled for this K9 workflow", log_change=True)
            self.post_print_pose_known = False
            self.post_print_pose = None
            self._clear_predicted_print_end()
            self._post(
                "log",
                "Обычный G28 отключён: у текущего K9 нет надёжного home по концевикам. "
                "Выставь стартовую позу вручную и нажми 'Запомнить старт'.",
            )

        self._run_task("Home всех осей", task)

    def set_current_home_zero(self) -> None:
        def task() -> None:
            out = sdtool.set_current_home_zero(self._port(), self._baud())
            self._set_home_trust(HOME_TRUST_TRUSTED, "operator saved current physical start", log_change=True)
            self.at_saved_start_pose = True
            self.bed_clear_before_go_start_required = False
            self.stopped_print_pose = None
            self.stopped_print_display = "-"
            self.post_print_pose_known = False
            self.post_print_pose = None
            had_active_print = self.current_print_file != "-"
            self._clear_predicted_print_end(save=False)
            if had_active_print:
                self.current_print_file = "-"
                self.current_print_display = "-"
                self.current_print_start_ts = None
                self.current_print_progress_pct = None
                self.print_state_restored_from_log = False
                self.print_start_watchdog_alerted = False
                self.print_was_active = False
                self.print_completion_armed = False
                self.sd_progress_sample_count = 0
                self.first_sd_progress_ts = None
                self.last_sd_progress_ts = None
                self._post("active-sd", "Печатается: -")
                self._post("progress", ("Печать: состояние закрыто после сохранения старта", 0.0))
            self._save_print_state("idle", force=True)
            if self.post_print_recovery_required:
                self._post("post-print-recovery-clear", None)
                self._post("log", "Стартовая поза записана после послепечатного цикла: следующая печать разрешена.")
            self._post("log", out.strip() or "Стартовая поза запомнена")
            self._post("log", "Теперь можно нажимать 'К старту' и 'Печать с SD'.")

        self._run_task("Запоминание стартовой позы", task)

    def _missing_start_zero_text(self) -> str:
        lang = self.lang_var.get().strip() or "ru"
        if lang == "en":
            return (
                "The app does not currently have a trusted saved start pose. "
                "For safety it will not send 'Go to start'. If the printer is already physically at the start pose, press 'Save start'. "
                "Otherwise use manual jog first, then press 'Save start'. "
                "If a print completed while Little Hands was closed or disconnected, automatic return is only safe if the app offers the explicit saved print-end recovery prompt."
            )
        if lang == "zh":
            return (
                "程序当前没有可信的已保存起点。为安全起见，不会发送 'Go to start'。"
                "如果打印机已经实际位于起点，请点击 'Save start'；否则请先手动点动到起点，再保存。"
                "如果打印完成时 Little Hands 已关闭或 USB 断开，只有程序显示明确的已保存 print-end / SD 标记恢复确认时，自动返回才是安全的。"
            )
        return (
            "Сейчас у приложения нет доверенной сохранённой стартовой позы, поэтому оно безопасно не отправляет 'К старту'. "
            "Если принтер уже физически стоит в стартовой позе, нажми 'Запомнить старт'. "
            "Если нет — сначала выставь позу ручными кнопками, потом нажми 'Запомнить старт'. "
            "Если печать завершилась, пока Little Hands был закрыт или потерял USB, автоматический возврат безопасен только через отдельное подтверждение recovery по сохранённому print-end."
        )

    def _can_return_from_known_post_print_pose(self) -> bool:
        return bool(
            self.post_print_pose_known
            and self.post_print_pose is not None
            and self.post_print_recovery_required
            and self._port()
        )

    def _can_return_from_predicted_print_end_pose(self) -> bool:
        return bool(
            self._port()
            and not self._home_is_trusted()
            and self.predicted_print_end_valid
            and self.predicted_print_end_file != "-"
            and self.predicted_print_end_contract == PRINT_END_CONTRACT
            and self.predicted_print_end_z is not None
        )

    def _has_unusable_predicted_print_end(self) -> bool:
        return bool(
            self._port()
            and not self._home_is_trusted()
            and self.predicted_print_end_valid
            and self.predicted_print_end_file != "-"
            and self.predicted_print_end_z is None
        )

    def _confirm_predicted_print_return(self) -> str | None:
        lang = self.lang_var.get().strip() or "ru"
        end_z = self.predicted_print_end_z
        z_text = f"{end_z:.1f} mm" if end_z is not None else "unknown"
        file_text = self.predicted_print_end_display if self.predicted_print_end_display != "-" else self.predicted_print_end_file
        prompt = {
            "en": (
                f"Little Hands has a saved print-end model for:\n{file_text}\n\n"
                f"Expected final pose: X95 Y95 Z{z_text}.\n\n"
                "Try automatic return to start only if ALL are true:\n"
                "- the print is fully finished\n"
                "- the printed part has been removed\n"
                "- after the finish, the axes were not moved by hand\n"
                "- if power was cycled, the printer physically remained in that final pose\n\n"
                "Yes = try recovery from the saved print-end model.\n"
                "No = delete the saved marker and set start manually.\n"
                "Cancel = do nothing."
            ),
            "zh": (
                f"Little Hands 保存了以下文件的打印结束模型：\n{file_text}\n\n"
                f"预计结束位置：X95 Y95 Z{z_text}。\n\n"
                "只有全部满足时才尝试自动回到起点：\n"
                "- 打印已经完全结束\n"
                "- 模型已经取下\n"
                "- 结束后没有手动移动各轴\n"
                "- 如果断电重启过，打印机实际仍停在这个结束位置\n\n"
                "Yes = 按保存的打印结束模型恢复。\n"
                "No = 删除保存的标记，手动设置起点。\n"
                "Cancel = 不操作。"
            ),
            "ru": (
                f"У Little Hands есть сохранённая модель print-end для файла:\n{file_text}\n\n"
                f"Ожидаемая конечная поза: X95 Y95 Z{z_text}.\n\n"
                "Пробовать автоматический возврат к старту можно только если ВСЁ верно:\n"
                "- печать полностью завершилась\n"
                "- деталь снята со стола\n"
                "- после завершения оси не двигали руками\n"
                "- если был power cycle, физически принтер остался в этой конечной позе\n\n"
                "Да = попробовать recovery по сохранённому print-end.\n"
                "Нет = удалить сохранённый маркер и выставлять старт вручную.\n"
                "Отмена = ничего не делать."
            ),
        }.get(lang) or (
            "У Little Hands есть сохранённая модель print-end.\n\n"
            "Да = recovery, Нет = удалить маркер и вручную, Отмена = ничего не делать."
        )
        answer = messagebox.askyesnocancel("Little Hands", prompt)
        if answer is None:
            return None
        return "recover" if answer else "manual"

    def _confirm_clear_unusable_predicted_print_end(self) -> bool:
        lang = self.lang_var.get().strip() or "ru"
        prompt = {
            "en": (
                "Little Hands has a saved print-end marker, but it does not contain enough G-code height data for automatic recovery.\n\n"
                "Delete the marker and set the start pose manually?"
            ),
            "zh": (
                "Little Hands 有保存的打印结束标记，但没有足够的高度数据，不能自动恢复。\n\n"
                "删除标记并手动设置起点吗？"
            ),
            "ru": (
                "У Little Hands есть сохранённый print-end маркер, но в нём нет достаточной высоты из G-code для автоматического recovery.\n\n"
                "Удалить маркер и выставить старт вручную?"
            ),
        }.get(lang) or (
            "Сохранённый print-end неполный. Удалить маркер и выставить старт вручную?"
        )
        return bool(messagebox.askyesno("Little Hands", prompt))

    def _show_missing_start_zero(self) -> None:
        msg = self._missing_start_zero_text()
        self.log(msg)
        if self.post_print_recovery_required:
            self._show_post_print_recovery_window("blocked-start")
        messagebox.showerror("Little Hands", msg)

    def _confirm_model_removed_before_go_start(self) -> bool:
        lang = self.lang_var.get().strip() or "ru"
        prompt = {
            "en": (
                "Is the bed clear now?\n\n"
                "'Go to start' returns to Z0, which means the nozzle touches the bed. "
                "Use it only after the printed part or failed first layer has been removed."
            ),
            "zh": (
                "平台现在已经清空了吗？\n\n"
                "'Go to start' 会回到 Z0，也就是喷嘴接触平台。"
                "只有取下模型或失败的第一层后才使用。"
            ),
            "ru": (
                "Стол сейчас свободен?\n\n"
                "'К старту' возвращает в Z0, то есть сопло опустится до касания стола. "
                "Нажимай это только после удаления детали или неудавшегося первого слоя."
            ),
        }.get(lang) or (
            "Стол сейчас свободен?\n\n"
            "'К старту' возвращает в Z0, то есть сопло опустится до касания стола. "
            "Нажимай это только после удаления детали или неудавшегося первого слоя."
        )
        return bool(messagebox.askyesno("Little Hands", prompt))

    def _confirm_aborted_print_recovery(self, pose: tuple[float, float, float]) -> bool:
        lang = self.lang_var.get().strip() or "ru"
        pose_text = f"X{pose[0]:.2f} Y{pose[1]:.2f} Z{pose[2]:.2f}"
        file_text = self.stopped_print_display if self.stopped_print_display != "-" else "stopped print"
        prompt = {
            "en": (
                "Return to start after a stopped / failed print?\n\n"
                f"Little Hands saved the interrupted position before M524:\n{file_text}\n{pose_text}\n\n"
                "It will not use any endstop-based homing. It will:\n"
                "1. lift the nozzle\n"
                "2. temporarily restore that interrupted coordinate model with G92\n"
                "3. move back to X0 Y0 Z0\n"
                "4. save the start pose again\n\n"
                "Continue only if the bed is clear: remove the model, brim, strings, and failed first layer."
            ),
            "zh": (
                "停止/失败打印后回到起点吗？\n\n"
                f"Little Hands 在 M524 前保存了中断位置：\n{file_text}\n{pose_text}\n\n"
                "它不会使用任何基于限位开关的 homing。它会：\n"
                "1. 抬起喷嘴\n"
                "2. 用 G92 临时恢复中断时的坐标模型\n"
                "3. 回到 X0 Y0 Z0\n"
                "4. 再次保存起点\n\n"
                "只有平台清空后才继续：请移除模型、brim、拉丝和失败的第一层。"
            ),
            "ru": (
                "Вернуть к старту после остановленной / сорванной печати?\n\n"
                f"Little Hands сохранил позицию прерывания до M524:\n{file_text}\n{pose_text}\n\n"
                "Он не будет использовать home по концевикам. Recovery будет таким:\n"
                "1. поднимет сопло\n"
                "2. временно восстановит координаты прерывания через G92\n"
                "3. вернётся в X0 Y0 Z0\n"
                "4. заново сохранит стартовую позу\n\n"
                "Продолжай только если стол свободен: убери модель, brim, нитки и неудавшийся первый слой."
            ),
        }.get(lang) or (
            "Вернуть к старту после остановленной печати?\n\n"
            "Продолжай только если стол свободен: убери модель, brim, нитки и неудавшийся первый слой."
        )
        return bool(messagebox.askyesno("Little Hands", prompt))

    def go_print_home(self, *, confirm_model_removed: bool = False) -> None:
        if self.current_print_file != "-" and not confirm_model_removed:
            msg = (
                "Сейчас у приложения есть активный SD-старт/печать. 'К старту' не выполняется во время активной печати: "
                "сначала нажми 'Стоп', дождись остановки, убери пластик со стола и заново выставь стартовую позу."
            )
            self.log(msg)
            messagebox.showwarning("Little Hands", msg)
            return
        use_stopped_print_pose = False
        stopped_pose = self.stopped_print_pose
        if not self._home_is_trusted() and self.bed_clear_before_go_start_required and stopped_pose is not None:
            if not self._confirm_aborted_print_recovery(stopped_pose):
                return
            use_stopped_print_pose = True
        if (
            not use_stopped_print_pose
            and (self.post_print_recovery_required or self.bed_clear_before_go_start_required)
            and not confirm_model_removed
        ):
            if not self._confirm_model_removed_before_go_start():
                return
        use_post_print_pose = False
        post_print_pose = self.post_print_pose
        use_predicted_print_end_pose = False
        if use_stopped_print_pose:
            self.log(
                "Выполняю recovery к старту после остановленной печати: использую позицию, "
                "снятую до M524, затем возвращаюсь в X0 Y0 Z0."
            )
        elif self._can_return_from_known_post_print_pose() and not self._home_is_trusted():
            post_print_pose = self.post_print_pose
            use_post_print_pose = True
            self.log(
                "Использую реальную послепечатную позу M114: Little Hands видел завершение печати. "
                "Возврат к старту допустим только после снятия модели со стола."
            )
        elif not self._home_is_trusted() and self._can_return_from_predicted_print_end_pose():
            choice = self._confirm_predicted_print_return()
            if choice is None:
                return
            if choice == "manual":
                self._clear_print_session_state("Печать: сохранённый print-end удалён", 0.0)
                self.log("Сохранённый print-end удалён. Выставь стартовую позу вручную и нажми 'Запомнить старт'.")
                return
            use_predicted_print_end_pose = True
            self.log(
                "Пробую recovery-возврат по сохранённой модели print-end. "
                "Оператор подтвердил: печать закончилась, модель снята, физическая конечная поза не сбита."
            )
        elif not self._home_is_trusted() and self._has_unusable_predicted_print_end():
            if self._confirm_clear_unusable_predicted_print_end():
                self._clear_print_session_state("Печать: неполный print-end удалён", 0.0)
                self.log("Неполный print-end удалён. Выставь стартовую позу вручную и нажми 'Запомнить старт'.")
            return
        elif (self.post_print_recovery_required or self.bed_clear_before_go_start_required) and not self._home_is_trusted():
            msg = (
                "После завершения или остановки печати нет надёжной сохранённой позы для автоматического 'К старту'. "
                "Чтобы не увести сопло в модель или за край, выставь стартовую позу ручными кнопками и нажми 'Запомнить старт'."
            )
            self.log(msg)
            messagebox.showerror("Little Hands", msg)
            return
        elif self.post_print_recovery_required or self.bed_clear_before_go_start_required:
            self.log(
                "Текущая Marlin-сессия ещё хранит сохранённый ноль: возвращаюсь обычным G1 X0 Y0 Z0 "
                "без переобъявления координат через послепечатный M114."
            )
        elif not self._home_is_trusted():
            self._show_missing_start_zero()
            return

        def task() -> None:
            try:
                if use_stopped_print_pose:
                    assert stopped_pose is not None
                    out = sdtool.goto_print_home_from_predicted_end(
                        self._port(),
                        self._baud(),
                        end_x=stopped_pose[0],
                        end_y=stopped_pose[1],
                        end_z=stopped_pose[2],
                    )
                elif use_predicted_print_end_pose:
                    assert self.predicted_print_end_z is not None
                    out = sdtool.goto_print_home_from_predicted_end(
                        self._port(),
                        self._baud(),
                        end_x=self.predicted_print_end_x,
                        end_y=self.predicted_print_end_y,
                        end_z=self.predicted_print_end_z,
                    )
                elif use_post_print_pose:
                    assert post_print_pose is not None
                    out = sdtool.goto_print_home_from_predicted_end(
                        self._port(),
                        self._baud(),
                        end_x=post_print_pose[0],
                        end_y=post_print_pose[1],
                        end_z=post_print_pose[2],
                    )
                else:
                    out = sdtool.goto_print_home(self._port(), self._baud())
            except Exception:
                self._set_home_trust(HOME_TRUST_UNCERTAIN, "go-to-start failed; physical position is not trusted", log_change=True)
                raise
            if use_stopped_print_pose or use_post_print_pose or use_predicted_print_end_pose:
                self._set_home_trust(HOME_TRUST_TRUSTED, "recovered to saved start", log_change=True)
            elif self._home_is_trusted():
                self._set_home_trust(HOME_TRUST_TRUSTED, "returned to saved start", log_change=False)
            self.at_saved_start_pose = True
            self.bed_clear_before_go_start_required = False
            self.stopped_print_pose = None
            self.stopped_print_display = "-"
            self.post_print_pose_known = False
            self.post_print_pose = None
            if use_stopped_print_pose:
                self._clear_predicted_print_end(save=False)
                self._save_print_state("recovered-to-start", force=True)
                self._post("progress", ("Recovery после стопа: старт восстановлен", 0.0))
                self._post("log", out.strip() or "Recovery после остановленной печати выполнен: стартовая поза заново сохранена")
                self._post("log", "Теперь можно запускать следующую печать из сохранённого старта.")
            elif use_post_print_pose:
                self._clear_predicted_print_end(save=False)
                self._save_print_state("recovered-to-start", force=True)
                self._post("progress", ("Recovery print-end: возвращён к старту", 0.0))
                self._post("log", out.strip() or "Recovery по реальной M114 print-end позе выполнен: принтер возвращён к стартовой позе")
                self._post(
                    "log",
                    "Когда принтер физически стоит в старте, нажми 'Запомнить старт' перед следующей печатью.",
                )
                self._post("post-print-recovery", "completion")
            elif use_predicted_print_end_pose:
                self.current_print_file = "-"
                self.current_print_display = "-"
                self.current_print_start_ts = None
                self.current_print_progress_pct = None
                self.print_state_restored_from_log = False
                self.print_start_watchdog_alerted = False
                self.print_was_active = False
                self.print_completion_armed = False
                self.sd_progress_sample_count = 0
                self.first_sd_progress_ts = None
                self.last_sd_progress_ts = None
                self._clear_predicted_print_end(save=False)
                self._save_print_state("recovered-to-start", force=True)
                self._post("active-sd", "Печатается: -")
                self._post("progress", ("Recovery print-end: возвращён к старту", 0.0))
                self._post("log", out.strip() or "Recovery по print-end выполнен: принтер возвращён к стартовой позе")
                self._post(
                    "log",
                    "Если power cycle ещё не был сделан после завершения печати, сделай его перед следующей печатью. "
                    "Когда принтер физически стоит в старте, нажми 'Запомнить старт'.",
                )
                self._post("post-print-recovery", "completion")
            else:
                self._save_print_state("returned-to-start", force=True)
                self._post("log", out.strip() or "Принтер возвращён к стартовой позе")
                if self.post_print_recovery_required:
                    self._post(
                        "log",
                        "Если принтер физически стоит в старте, сделай power cycle перед следующей печатью и нажми 'Запомнить старт'. "
                        "Если физически это не старт, выставь стартовую позу вручную.",
                    )

        self._run_task("Переход к сохранённому 0", task)

    def motor_off(self) -> None:
        def task() -> None:
            self._set_home_trust(HOME_TRUST_INVALID, "motors were disabled", log_change=True)
            self.post_print_pose_known = False
            self.post_print_pose = None
            self._clear_predicted_print_end()
            out = sdtool.query_command(self._port(), self._baud(), "M18", wait_before_read=0.4, read_seconds=1.0)
            self._post("log", out.strip() or "Моторы отключены")

        self._run_task("Отключение моторов", task)

    def jog_axis(self, axis: str, distance: float) -> None:
        axis = axis.upper()
        feedrate = JOG_FEEDRATES.get(axis, 1200)
        travel_accel = JOG_TRAVEL_ACCEL.get(axis)
        display_hint = self._operator_axis_hint(axis)
        requested_distance = distance
        distance_was_limited = False
        if axis == "Y" and abs(distance) > MAX_MANUAL_BED_JOG_MM:
            distance = (1.0 if distance > 0 else -1.0) * MAX_MANUAL_BED_JOG_MM
            distance_was_limited = True
        signed_distance = f"{distance:+g}"
        segments: list[float] = [distance]
        if axis == "Y" and abs(distance) > BED_JOG_SEGMENT_MM:
            sign = 1.0 if distance > 0 else -1.0
            remaining = abs(distance)
            segments = []
            while remaining > 1e-6:
                step = min(BED_JOG_SEGMENT_MM, remaining)
                segments.append(sign * step)
                remaining -= step

        def task() -> None:
            self.at_saved_start_pose = False
            self.post_print_pose_known = False
            self.post_print_pose = None
            self.stopped_print_pose = None
            self.stopped_print_display = "-"
            self._clear_predicted_print_end()
            self._post(
                "log",
                f"Jog: {display_hint} {signed_distance} мм; G-code {axis}{distance:.3f} F{feedrate}"
                + (f", limited from requested {requested_distance:+g}mm" if distance_was_limited else "")
                + (f", segments {len(segments)}x<= {BED_JOG_SEGMENT_MM:g}mm" if len(segments) > 1 else "")
                + (f", M204 P{travel_accel} T{travel_accel}" if travel_accel is not None else ""),
            )
            commands = ["M17", "G90", "M211 S0"]
            if travel_accel is not None:
                commands.append(f"M204 P{travel_accel} T{travel_accel}")
            if axis == "Y":
                raw_pos = sdtool.query_command(self._port(), self._baud(), "M114", wait_before_read=0.3, read_seconds=1.0)
                parsed = sdtool.parse_position(raw_pos)
                if parsed is not None:
                    _x_raw, y_raw, _z_raw = parsed
                    if distance < 0 and y_raw <= BED_RAW_MIN_MM:
                        msg = (
                            f"Стол уже у отрицательного края raw Y={y_raw:.2f}. "
                            "Не жму дальше в упор; используй 'Стол к себе' или сдвинь стол вручную от края."
                        )
                        self._post("log", msg)
                        self._post("info", msg)
                        return
                    if distance > 0 and y_raw >= BED_RAW_MAX_MM:
                        msg = (
                            f"Стол уже у положительного края raw Y={y_raw:.2f}. "
                            "Не жму дальше в упор; используй 'Стол от себя' или сдвинь стол вручную от края."
                        )
                        self._post("log", msg)
                        self._post("info", msg)
                        return
                    self._post("log", f"Bed jog precheck: raw Y={y_raw:.2f}, command Y{distance:+.3f}")
            commands.append("G91")
            for segment in segments:
                commands.extend([f"G1 {axis}{segment:.3f} F{feedrate}", "M400"])
            if travel_accel is not None:
                commands.append(f"M204 P{JOG_RESTORE_TRAVEL_ACCEL} T{JOG_RESTORE_TRAVEL_ACCEL}")
            commands.append("G90")
            try:
                out = sdtool.run_commands_wait_ok(
                    self._port(),
                    self._baud(),
                    commands,
                    per_command_timeout=45.0,
                )
            except Exception:
                self._set_home_trust(HOME_TRUST_UNCERTAIN, "manual jog failed; app position model is not trusted", log_change=True)
                raise
            useful_lines = [
                line.strip()
                for line in out.splitlines()
                if line.strip() and line.strip().lower() != "ok"
            ]
            if useful_lines:
                self._post("log", "\n".join(useful_lines))

        self._run_task(f"Сдвиг {display_hint} {signed_distance} мм", task)

    def move_level_point(self, x: float, y: float) -> None:
        def task() -> None:
            self.at_saved_start_pose = False
            self.post_print_pose_known = False
            self.post_print_pose = None
            self._clear_predicted_print_end()
            try:
                out = sdtool.run_commands_wait_ok(
                    self._port(),
                    self._baud(),
                    [
                        "G90",
                        "M211 S0",
                        "M204 T80",
                        "G1 Z10 F600",
                        f"G1 X{x:.2f} F{SERVICE_X_FEEDRATE}",
                        f"G1 Y{y:.2f} F{SERVICE_BED_FEEDRATE}",
                        "G1 Z0 F600",
                        "M400",
                        f"M204 T{JOG_RESTORE_TRAVEL_ACCEL}",
                    ],
                    per_command_timeout=45.0,
                )
            except Exception:
                self._set_home_trust(HOME_TRUST_UNCERTAIN, "bed-level move failed; app position model is not trusted", log_change=True)
                raise
            self._post("log", out.strip() or f"Переход к точке X{x:.0f} Y{y:.0f}")

        self._run_task(f"Переход к точке X{x:.0f} Y{y:.0f}", task)

    def _poll_status(self) -> None:
        if not self._port():
            self.busy_var.set("USB: отключен")
            self.root.after(1000, self._poll_status)
            return
        safety_error = self._selected_port_safety_error()
        if safety_error:
            self.log(f"Автоопрос остановлен: {safety_error}")
            self.disconnect_port(log_change=False)
            self.root.after(1000, self._poll_status)
            return
        if self.monitor_enabled and not self.user_task_pending and self.serial_lock.acquire(blocking=False):
            threading.Thread(target=self._poll_worker, daemon=True).start()
        self.root.after(1000, self._poll_status)

    def _poll_worker(self) -> None:
        try:
            now = time.time()
            quiet_remaining = self.post_m24_usb_quiet_until - now
            if self.current_print_file != "-" and quiet_remaining > 0:
                remaining = max(1, int(math.ceil(quiet_remaining)))
                self._post("busy", (False, "USB: стартовая пауза"))
                self._post("sd", f"SD: старт, USB пауза {remaining} c")
                self._post("progress", (f"Старт SD: не трогаю USB {remaining} c", 0.0))
                if (
                    not self.last_post_m24_quiet_log_ts
                    or (now - self.last_post_m24_quiet_log_ts) >= USB_SILENCE_LOG_INTERVAL_SEC
                    or remaining <= 5
                ):
                    self.last_post_m24_quiet_log_ts = now
                    self._post(
                        "log",
                        f"Стартовая USB-пауза после M24: осталось примерно {remaining} c. "
                        "Это нормальное ожидание: hotend уже прогрет, сейчас даём K9 войти в SD-печать. SD не обновляй.",
                    )
                return
            if self.post_m24_usb_quiet_until and self.current_print_file != "-":
                self.post_m24_usb_quiet_until = 0.0
                self.last_post_m24_quiet_log_ts = 0.0
                self._post("busy", (False, "USB: idle"))
                self._post("log", "Стартовая USB-пауза после M24 завершена: начинаю аккуратный опрос M105/M27.")
            pending_start_heatup = (
                self.current_print_file != "-"
                and self.current_print_start_ts
                and not self.print_was_active
            )
            if pending_start_heatup:
                # During M109 Marlin doesn't answer ordinary M105 commands.
                # It does emit temperature lines about once a second, so listen first.
                temp = sdtool.listen_serial(
                    self._port(),
                    self._baud(),
                    read_seconds=1.35,
                    reset_input=False,
                )
                if not TEMP_RE.search(temp):
                    temp = sdtool.query_command(
                        self._port(),
                        self._baud(),
                        "M105",
                        wait_before_read=0.12,
                        read_seconds=1.10,
                        sync=False,
                        reset_input=False,
                    )
            else:
                temp = sdtool.query_command(
                    self._port(),
                    self._baud(),
                    "M105",
                    wait_before_read=0.12,
                    read_seconds=0.45,
                    sync=False,
                    reset_input=False,
                )
            match = TEMP_RE.search(temp)
            current_temp = None
            target_temp = None
            if match:
                current_temp = float(match.group(1))
                target_temp = float(match.group(2))
                heater_match = HEATER_RE.search(temp)
                heater = int(heater_match.group(1)) if heater_match else None
                self.usb_silence_since = 0.0
                self.last_usb_silence_log_ts = 0.0
                self._post("temp", (current_temp, target_temp, heater))
                if now - self.last_temp_log_ts >= TEMP_LOG_INTERVAL_SEC:
                    self.last_temp_log_ts = now
                    heater_value = heater if heater is not None else "?"
                    self._append_ring_log(
                        f"{time.strftime('%H:%M:%S')} M105 T:{current_temp:.2f} /{target_temp:.2f} @:{heater_value}"
                    )
            self._post("metrics", ("m105", temp))
            if not match:
                if not self.usb_silence_since:
                    self.usb_silence_since = now
                in_start_grace = (
                    self.current_print_file != "-"
                    and self.current_print_start_ts
                    and not self.print_was_active
                    and (now - self.current_print_start_ts) < PRINT_START_GRACE_SEC
                )
                active_print_observed = (
                    self.current_print_file != "-"
                    and (
                        self.print_was_active
                        or self.print_completion_armed
                        or self.sd_progress_sample_count > 0
                        or (self.current_print_progress_pct is not None and self.current_print_progress_pct > 0.0)
                    )
                )
                recent_post_start_temp = (
                    self.current_print_file != "-"
                    and self.current_print_start_ts
                    and self.last_temp_sample_ts >= self.current_print_start_ts
                    and (now - self.last_temp_sample_ts) <= PRINT_START_RECENT_TEMP_CONFIRM_SEC
                    and self.last_temp_target > 0.0
                )
                if in_start_grace:
                    self._post("sd", "SD: старт/прогрев, USB занят")
                    self._post("progress", ("Печать: старт отправлен, жду прогрев/движение", 0.0))
                    silence_message = (
                        "Во время старта SD-печати принтер временно не отвечает на M105. "
                        "Это не повод выключать питание: если хотенд греется, вентилятор ожил или моторы начали работу, просто жди. "
                        "Little Hands пока не отправляет SD/позиционные запросы и ждёт подтверждения старта."
                    )
                elif active_print_observed:
                    pct = self.current_print_progress_pct
                    progress_value = float(pct) if pct is not None else 0.0
                    progress_text = (
                        f"Печать: {pct:.1f}% (телеметрия частичная)"
                        if pct is not None
                        else "Печать: активна, телеметрия частичная"
                    )
                    self._post("sd", "SD: печать активна, USB частичный")
                    self._post("progress", (progress_text, progress_value))
                    return
                elif recent_post_start_temp:
                    self._post("sd", "SD: hotend держит цель, жду SD-прогресс")
                    self._post("progress", ("Печать: hotend на цели, жду SD-прогресс", 0.0))
                    silence_message = (
                        "USB иногда молчит во время входа K9 в SD-печать, но после M24 уже были свежие M105 "
                        "с рабочей целью hotend. Это не считается провалом старта; Little Hands ждёт SD-прогресс."
                    )
                elif self.current_print_file != "-":
                    self._post("sd", "SD: печать/USB занят")
                    self._post("progress", ("Печать: нет телеметрии, проверь визуально", 0.0))
                    silence_message = (
                        "Little Hands не может подтвердить состояние печати по USB: M105 временно молчит. "
                        "Если принтер греется, двигается или уже печатает, не выключай питание; приложение ждёт восстановления связи "
                        "и не отправляет SD/позиционные запросы. Если принтер физически не греется и не двигается несколько минут, "
                        "тогда это похоже на неподтверждённый старт."
                    )
                else:
                    self._post("sd", "SD: USB не отвечает")
                    silence_message = (
                        "USB не отвечает на M105; Little Hands откладывает SD/позиционные запросы, чтобы не забивать порт. "
                        "Power cycle нужен только если принтер не печатает, не греется и не двигается."
                    )
                if (now - self.last_usb_silence_log_ts) >= USB_SILENCE_LOG_INTERVAL_SEC:
                    self.last_usb_silence_log_ts = now
                    self._post("log", silence_message)
                if (
                    self.current_print_file != "-"
                    and self.current_print_start_ts
                    and not self.print_was_active
                    and not self.print_start_watchdog_alerted
                    and not recent_post_start_temp
                    and (now - self.current_print_start_ts) >= PRINT_START_GRACE_SEC
                ):
                    file_name = self.current_print_file
                    self.print_start_watchdog_alerted = True
                    self._append_ring_log(
                        f"{time.strftime('%H:%M:%S')} PRINT_START_UNCONFIRMED file={file_name} reason=m105_silent"
                    )
                    self._clear_print_session_state("Печать: старт не подтверждён", 0.0)
                    self._post("post-print-recovery", "failed-start")
                    self._post(
                        "log",
                        "Старт печати не подтвердился: 5 минут после M24 нет M105/SD-прогресса. "
                        "Если принтер физически не греется, вентилятор не включился и движения нет, "
                        "это зависший старт; сделай power cycle перед новой попыткой. "
                        "Если принтер всё-таки реально печатает, не выключай питание и наблюдай визуально.",
                    )
                return
            if (
                pending_start_heatup
                and self.current_print_file != "-"
                and not self.print_was_active
                and current_temp is not None
                and target_temp is not None
                and target_temp > 0.0
                and current_temp < (target_temp - 1.5)
            ):
                display = self.current_print_display if self.current_print_display != "-" else self.current_print_file
                self._post("active-sd", f"Печатается: {display}")
                self._post("sd", "SD: прогрев hotend (M109)")
                self._post("progress", (f"Прогрев hotend: {current_temp:.1f}/{target_temp:.0f} C", 0.0))
                self.current_print_progress_pct = 0.0
                self._save_print_state("printing")
                if now - self.last_telemetry_log_ts >= 5.0:
                    self.last_telemetry_log_ts = now
                    self._append_ring_log(
                        f"{time.strftime('%H:%M:%S')} TELEMETRY file={self.current_print_file} progress=0.0% temp={current_temp:.2f}/{target_temp:.2f} sd=\"M109 heatup\""
                    )
                return
            sd = sdtool.query_command(
                self._port(),
                self._baud(),
                "M27",
                wait_before_read=0.15,
                read_seconds=0.45,
                sync=False,
                reset_input=False,
            )
            summary = next((line.strip() for line in sd.splitlines() if line.strip()), "SD: idle")
            self._post("sd", summary)
            if (now - self.last_position_sample_ts) >= 3.0:
                m114 = sdtool.query_command(
                    self._port(),
                    self._baud(),
                    "M114",
                    wait_before_read=0.1,
                    read_seconds=0.35,
                    sync=False,
                    reset_input=False,
                )
                pos_line = next((line.strip() for line in m114.splitlines() if "X:" in line and "Y:" in line and "Z:" in line), "").strip()
                if pos_line:
                    self._post("pos", pos_line)
                self._post("metrics", ("m114", m114))
            if not self.last_fw_line and (now - self.last_fw_query_ts) >= 15.0:
                self.last_fw_query_ts = now
                m115 = sdtool.query_command(
                    self._port(),
                    self._baud(),
                    "M115",
                    wait_before_read=0.1,
                    read_seconds=0.5,
                    sync=False,
                    reset_input=False,
                )
                fw_line = next((line for line in m115.splitlines() if line.startswith("FIRMWARE_NAME:")), "")
                if fw_line:
                    self._post("fw", self._format_fw_line(fw_line))
                self._post("metrics", ("m115", m115))
            progress_match = SD_PROGRESS_RE.search(sd)
            if progress_match:
                done = int(progress_match.group(1))
                total = max(int(progress_match.group(2)), 1)
                pct = max(0.0, min(100.0, (done / total) * 100.0))
                self.sd_progress_sample_count += 1
                if self.first_sd_progress_ts is None:
                    self.first_sd_progress_ts = now
                self.last_sd_progress_ts = now
                start_elapsed = (now - self.current_print_start_ts) if self.current_print_start_ts else None
                if (
                    self.sd_progress_sample_count >= PRINT_ACTIVE_CONFIRM_SAMPLES
                    and (start_elapsed is None or start_elapsed >= PRINT_ACTIVE_CONFIRM_MIN_SEC)
                    and done < total
                    and pct < 99.5
                ):
                    self.print_was_active = True
                    self.print_completion_armed = True
                self.current_print_progress_pct = pct
                if self.current_print_file != "-":
                    display = self.current_print_display if self.current_print_display != "-" else self.current_print_file
                    self._post("active-sd", f"Печатается: {display}")
                else:
                    self._post("active-sd", "Печатается: идёт печать (имя не восстановлено)")
                self._post("progress", (f"Печать: {pct:.1f}% ({done}/{total})", pct))
                if now - self.last_telemetry_log_ts >= 5.0:
                    self.last_telemetry_log_ts = now
                    temp_text = (
                        f"{current_temp:.2f}/{target_temp:.2f}"
                        if current_temp is not None and target_temp is not None
                        else "?/?"
                    )
                    self._append_ring_log(
                        f"{time.strftime('%H:%M:%S')} TELEMETRY file={self.current_print_file} progress={pct:.1f}% temp={temp_text} sd=\"{summary}\""
                    )
                self._save_print_state("printing")
            elif (
                self.current_print_file != "-"
                and self.current_print_start_ts
                and not self.print_was_active
                and not self.print_start_watchdog_alerted
                and (now - self.current_print_start_ts) >= PRINT_START_GRACE_SEC
                and (target_temp is None or target_temp <= 0.0)
            ):
                self.print_start_watchdog_alerted = True
                try:
                    recovery_out = sdtool.stop_sd_print(self._port(), self._baud())
                    if recovery_out.strip():
                        self._post("log", recovery_out.strip())
                except Exception as exc:
                    self._post("log", f"Автостоп после неподтверждённого старта не получил уверенный ответ: {exc}")
                self._clear_print_session_state("Печать: старт не подтверждён", 0.0)
                self._post("post-print-recovery", "failed-start")
                self._post(
                    "log",
                    "Старт печати не подтвердился: за 5 минут не было ни SD-прогресса, ни цели нагрева хотенда.",
                )
            elif "Not SD printing" in sd:
                in_start_grace = (
                    self.current_print_file != "-"
                    and self.current_print_start_ts
                    and not self.print_was_active
                    and (now - self.current_print_start_ts) < PRINT_START_GRACE_SEC
                )
                if in_start_grace:
                    self._post("progress", ("Печать: старт отправлен, жду SD/прогрев", 0.0))
                else:
                    self._post("progress", ("Печать: простой", 0.0))
                if self.print_state_restored_from_log and not self.print_was_active:
                    self.current_print_file = "-"
                    self.current_print_display = "-"
                    self.current_print_start_ts = None
                    self.current_print_progress_pct = None
                    self.print_state_restored_from_log = False
                    self.print_start_watchdog_alerted = False
                    self.print_was_active = False
                    self.print_completion_armed = False
                    self.sd_progress_sample_count = 0
                    self.first_sd_progress_ts = None
                    self.last_sd_progress_ts = None
                    self._clear_predicted_print_end(save=False)
                    self._save_print_state("idle", force=True)
                    self._post("active-sd", "Печатается: -")
                    self._post("log", "Сбросил восстановленное из лога состояние печати: на текущем принтере активной SD-печати нет.")
                    self._schedule_sd_refresh_after_port(self._port(), force=True)
                    return
                if self.print_was_active and self.print_completion_armed:
                    finish_ts = now
                    finished_file = self.current_print_display if self.current_print_display != "-" else self.current_print_file
                    start_ts = self.current_print_start_ts
                    started_at_log = self._format_local_datetime(start_ts) if start_ts else "?"
                    finished_at_log = self._format_local_datetime(finish_ts)
                    if start_ts:
                        duration_s = max(0, int(round(finish_ts - start_ts)))
                        duration_text = self._format_duration_ru(duration_s)
                        finish_message = (
                            f"Финиш печати: {finished_file}; финиш {finished_at_log}; "
                            f"старт {started_at_log}; фактическая длительность {duration_text}."
                        )
                    else:
                        duration_s = None
                        duration_text = "?"
                        finish_message = (
                            f"Финиш печати: {finished_file}; финиш {finished_at_log}; "
                            "старт неизвестен, фактическую длительность посчитать не удалось."
                        )
                    self.print_was_active = False
                    self.print_completion_armed = False
                    completion_move_result = ""
                    completion_pose_known = False
                    completion_pose: tuple[float, float, float] | None = None
                    computer_melody_enabled = bool(self.computer_melody_on_complete_var.get())
                    if not self.suppress_next_completion_chime:
                        try:
                            completion_move_result = self._run_printer_completion_sequence().strip()
                            completion_pose = sdtool.parse_position(completion_move_result)
                            completion_pose_known = completion_pose is not None
                        except Exception as exc:
                            self._post("log", f"Пост-обработка после печати не удалась: {exc}")
                    if self.suppress_next_completion_chime:
                        self.suppress_next_completion_chime = False
                    else:
                        if computer_melody_enabled:
                            self._post("melody", None)
                        if completion_move_result:
                            self._post("log", completion_move_result)
                        self.post_print_pose_known = completion_pose_known
                        self.post_print_pose = completion_pose
                        if completion_pose_known:
                            self._post(
                                "log",
                                "Послепечатная поза M114 известна: после снятия модели кнопка 'К старту' может вернуть принтер к сохранённому 0.",
                            )
                        else:
                            self._post(
                                "log",
                                "Послепечатная поза M114 не получена. Автоматический 'К старту' после power cycle может быть небезопасен; если сомневаешься, выставь старт вручную.",
                            )
                        if computer_melody_enabled:
                            self._post("log", "Печать завершена: стол выдвинут, голова поднята, проиграна мелодия на компьютере")
                        else:
                            self._post("log", "Печать завершена: стол выдвинут, голова поднята")
                        self._post("log", finish_message)
                        self.post_print_recovery_required = True
                        self._post("post-print-recovery", "completion")
                    duration_log = duration_s if duration_s is not None else "?"
                    self._remember_print_duration(self.current_print_file, finished_file, start_ts, finish_ts)
                    self._append_ring_log(
                        f"{time.strftime('%H:%M:%S', time.localtime(finish_ts))} PRINT_END file={self.current_print_file} "
                        f"temp={current_temp if current_temp is not None else '?'} "
                        f"started_at={started_at_log.replace(' ', 'T')} finished_at={finished_at_log.replace(' ', 'T')} "
                        f"duration_s={duration_log} duration=\"{duration_text}\""
                    )
                    self.current_print_file = "-"
                    self.current_print_display = "-"
                    self.current_print_start_ts = None
                    self.current_print_progress_pct = None
                    self.print_state_restored_from_log = False
                    self.print_start_watchdog_alerted = False
                    self.sd_progress_sample_count = 0
                    self.first_sd_progress_ts = None
                    self.last_sd_progress_ts = None
                    self._clear_predicted_print_end(save=False)
                    self._save_print_state("completed", force=True)
                    self._post("active-sd", "Печатается: -")
                elif self.print_was_active and not self.print_completion_armed:
                    self._post("progress", ("Печать: SD ответил Not SD printing, жду подтверждения старта", 0.0))
                elif (
                    self.current_print_file != "-"
                    and self.current_print_start_ts
                    and not self.print_start_watchdog_alerted
                    and (now - self.current_print_start_ts) >= PRINT_START_GRACE_SEC
                ):
                    self.print_start_watchdog_alerted = True
                    try:
                        recovery_out = sdtool.stop_sd_print(self._port(), self._baud())
                        if recovery_out.strip():
                            self._post("log", recovery_out.strip())
                    except Exception as exc:
                        self._post("log", f"Автостоп после неподтверждённого старта не получил уверенный ответ: {exc}")
                    self._clear_print_session_state("Печать: старт не подтверждён", 0.0)
                    self._post("post-print-recovery", "failed-start")
            self._post("metrics", ("m27", sd))
            if (
                self.pending_flash_finalize
                and not self.flash_finalize_in_progress
                and (now - self.flash_finalize_last_attempt_ts) >= 8.0
                and "Not SD printing" in sd
            ):
                self.flash_finalize_in_progress = True
                self.flash_finalize_last_attempt_ts = now
                source_name = str(self.pending_flash_finalize.get("source_name", "mksLite.bin"))
                self._post("files-status", f"Автозавершение прошивки: {source_name} -> выполняю M502/M500 ...")
                self._post("log", f"Автозавершение прошивки: {source_name} -> выполняю M502/M500 ...")
                try:
                    out = sdtool.run_commands(
                        self._port(),
                        self._baud(),
                        ["M502", "M500", "M21"],
                        settle_after_each=0.5,
                        final_wait=1.5,
                        read_seconds=3.0,
                    )
                    self._post("metrics", ("m503", sdtool.query_command(self._port(), self._baud(), "M503", wait_before_read=0.5, read_seconds=2.0)))
                    files: list[str] = []
                    has_eeprom = False
                    for attempt in range(4):
                        if attempt:
                            time.sleep(0.8)
                        try:
                            files, status, _raw = sdtool.read_sd_listing(self._port(), self._baud())
                        except Exception:
                            continue
                        if status == "ok":
                            self._post("sd-files", files)
                        lowered = [Path((entry.split()[0] if " " in entry else entry)).name.lower() for entry in files]
                        has_eeprom = "eeprom.dat" in lowered
                        if has_eeprom:
                            break
                    if has_eeprom:
                        self.eeprom_confirmed = True
                        result = (
                            f"Автозавершение прошивки выполнено: M502/M500 прошли, EEPROM.DAT создан "
                            f"для {source_name}."
                        )
                    elif "Settings Stored" in out:
                        self.eeprom_confirmed = True
                        result = (
                            f"Автозавершение прошивки выполнено: M502/M500 прошли для {source_name}. "
                            "EEPROM сохранён, но файл не виден в списке SD этой прошивки."
                        )
                    else:
                        result = (
                            f"Автозавершение прошивки почти завершено: M502/M500 отправлены для {source_name}, "
                            "но EEPROM.DAT ещё не виден. Надёжный следующий шаг: оставь SD в принтере, "
                            "выключи принтер по питанию на 5–10 секунд, включи снова и нажми 'Обновить список'."
                        )
                    self._clear_pending_flash_finalize()
                    self._post("files-status", result)
                    self._post("log", (out.strip() + "\n" + result).strip())
                    self._post("info", result)
                except Exception as exc:
                    self._post("files-status", f"Автозавершение прошивки не удалось: {exc}")
                    self._post("log", f"Автозавершение прошивки не удалось: {exc}")
                finally:
                    self.flash_finalize_in_progress = False
        except Exception as exc:
            now = time.time()
            if (now - self.last_poll_error_ts) >= 5.0:
                self.last_poll_error_ts = now
                self._post("log", f"Опрос USB сорвался: {exc}")
            if self._is_port_gone_error(exc):
                self._post("port-lost", self._port())
        finally:
            self.serial_lock.release()


def main() -> int:
    root = tk.Tk(className="little-hands-control-center")
    app = K9ControlCenter(root)
    app.log("Little Hands готов. Baseline: LH v4, auto-fan FAN1 45C, operator-facing manual-zero workflow, печать с SD от сохранённого старта.")
    app.log("Порт должен быть свободен от Cura и других мониторов.")
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
