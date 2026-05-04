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
TEMP_GRAPH_WINDOW_SEC = 15 * 60
TEMP_GRAPH_SCALE_RECENT_SEC = 3 * 60
TEMP_LOG_INTERVAL_SEC = 5.0


TEMP_RE = re.compile(r"T:([-\d.]+)\s*/([-\d.]+)")
HEATER_RE = re.compile(r"@:(\d+)")
SD_PROGRESS_RE = re.compile(r"SD printing byte\s+(\d+)\s*/\s*(\d+)", re.IGNORECASE)
PRINTABLE_SD_EXTS = {".gco", ".gcode", ".g"}
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
    - Motor routing on the validated second K9 behaves as Y/Z swapped relative
      to stock operator naming
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
    1. Slice in Cura normally. Do not use the old _k9xz remap file.
    2. Upload G-code to SD from this app or copy it by card.
    3. Move the printer into the fixed print-start pose.
    4. Press "Запомнить старт" to save this pose as print zero.
    5. Use "К старту" to return to this saved zero.
    6. Use "Печать с SD" to return to the saved zero and then send M24.

    Bed leveling
    - Use the four corners and the center.
    - Move between points with the app.
    - The app lifts Z before XY moves and lowers back to Z0 at each point.
    - If the center is slightly lower than the corners, leave it for now and test the first layer.

    Diagnostics
    - This printer does not have a reliable standard Marlin endstop-based home.
    - "Запомнить старт" stores the current physical pose as print zero for this session.
    - "К старту" returns to that stored print zero.
    - "Печать с SD" returns to that stored print zero and starts the selected SD file.
    - "Сброс USB" pauses polling and reopens a clean short serial session without restarting the whole app.
    - "Снять все метрики" dumps M115 / M503 / M114 / M105 / M27.

    Exports
    - "Экспорт Cura" saves the current printer profiles and Cura settings into the project.
    - Runtime log folder: /home/maxim/draftCode/littleHands/monitor_logs/
    - Ring log file: /home/maxim/draftCode/littleHands/monitor_logs/little_hands_runtime.log
    - "Сохранить лог" saves a timestamped copy of the current runtime log into gui_exports.
    """
).strip()

CURA_EXPORT_PATTERNS = [
    "machine_instances/lilHands.global.cfg",
    "definition_changes/lilHands_settings.inst.cfg",
    "definition_changes/custom_extruder_*settings.inst.cfg",
    "user/lilHands_user.inst.cfg",
    "user/codex*.cfg",
    "quality_changes/codex*.cfg",
    "extruders/*.extruder.cfg",
]
DISCONNECTED_PORT_LABEL = "— не подключаться —"


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

        self.port_var = tk.StringVar(value="/dev/ttyUSB0")
        self.port_display_var = tk.StringVar(value="/dev/ttyUSB0")
        self.local_gcode_var = tk.StringVar()
        self.dest_name_var = tk.StringVar(value="MODEL.GCO")
        self.firmware_var = tk.StringVar(value=str(DEFAULT_FIRMWARE))
        self.temp_var = tk.StringVar(value="Hotend: ? / ? C")
        self.sd_var = tk.StringVar(value="SD: unknown")
        self.fw_var = tk.StringVar(value="")
        self.progress_var = tk.StringVar(value="Печать: простой")
        self.print_start_var = tk.StringVar(value="Старт: -")
        self.busy_var = tk.StringVar(value="USB: idle")
        self.header_marquee_var = tk.StringVar(value="")
        self.selected_sd_var = tk.StringVar(value="Выбрано на SD: -")
        self.active_sd_var = tk.StringVar(value="Печатается: -")
        self.sd_notice_var = tk.StringVar(value="")
        self.files_status_var = tk.StringVar(value="Выбери G-code или прошивку.")
        self.step_var = tk.DoubleVar(value=5.0)
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
        self.suppress_next_completion_chime = False
        self.session_zero_defined = False
        self.log_file_lock = threading.Lock()
        self.temp_history: list[tuple[float, float, float]] = []
        self.last_telemetry_log_ts = 0.0
        self.current_print_file = "-"
        self.current_print_start_ts: float | None = None
        self.current_print_progress_pct: float | None = None
        self.print_state_restored_from_log = False
        self.print_start_watchdog_alerted = False
        self.printer_halted = False
        self.last_temp_sample_ts = 0.0
        self.last_temp_log_ts = 0.0
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
        self.pending_flash_finalize = self.ui_state.get("pending_flash_finalize")
        if not isinstance(self.pending_flash_finalize, dict):
            self.pending_flash_finalize = None
        self.flash_finalize_in_progress = False
        self.flash_finalize_last_attempt_ts = 0.0

        LOG_DIR.mkdir(parents=True, exist_ok=True)
        GUI_EXPORT_DIR.mkdir(parents=True, exist_ok=True)
        self._load_recent_temp_history_from_log()

        self._build_ui()
        if self.pending_flash_finalize:
            source_name = str(self.pending_flash_finalize.get("source_name", "mksLite.bin"))
            self.files_status_var.set(
                f"Ожидаю перезапуск принтера после прошивки {source_name}. Потом автоматически выполню M502/M500."
            )
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
        end_re = re.compile(r"(\d{2}):(\d{2}):(\d{2}) PRINT_END file=(.+?) temp=")
        last_active: str | None = None
        last_end: str | None = None
        last_start_ts: float | None = None
        last_progress_pct: float | None = None
        first_active_telem_ts: float | None = None
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
            ms = start_re.search(line)
            if ms:
                last_active = ms.group(4).strip()
                last_start_ts = stamp_for(int(ms.group(1)), int(ms.group(2)), int(ms.group(3)))
                first_active_telem_ts = None
                last_progress_pct = None
                continue
            mt = telemetry_re.search(line)
            if mt:
                file_name = mt.group(4).strip()
                last_active = file_name
                last_progress_pct = float(mt.group(5))
                ts = stamp_for(int(mt.group(1)), int(mt.group(2)), int(mt.group(3)))
                if file_name == last_active and first_active_telem_ts is None:
                    first_active_telem_ts = ts
                continue
            me = end_re.search(line)
            if me:
                last_end = me.group(4).strip()
        if last_active and last_active != "-" and last_active != last_end:
            self.current_print_file = last_active
            self.active_sd_var.set(f"Печатается: {last_active}")
            self.current_print_start_ts = last_start_ts or first_active_telem_ts
            self.current_print_progress_pct = last_progress_pct
            self.print_state_restored_from_log = True

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

    def _save_ui_state(self) -> None:
        state: dict[str, object] = {"geometry": self.root.winfo_geometry()}
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
        try:
            UI_STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    def _on_close(self) -> None:
        self._save_ui_state()
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
            c.create_text(width // 2, height // 2, text="Жду первый ответ M105", fill=colors["muted"], font=("DejaVu Sans", 10))
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
        conn.columnconfigure(4, weight=1)
        ttk.Label(conn, text="Port").grid(row=0, column=0, sticky="w")
        self.port_combo = ttk.Combobox(conn, textvariable=self.port_display_var, width=28, state="readonly")
        self.port_combo.grid(row=0, column=1, padx=(4, 6), sticky="ew")
        self.port_combo.bind("<<ComboboxSelected>>", lambda _event: self._on_port_selected())
        self.find_port_button = ttk.Button(conn, text="Найти", command=self.detect_printer_port_action)
        self.find_port_button.grid(row=0, column=2, padx=(0, 8), sticky="ew")
        self.disconnect_port_button = ttk.Button(conn, text="Откл.", command=self.disconnect_port)
        self.disconnect_port_button.grid(row=0, column=3, padx=(0, 8), sticky="ew")
        self.temp_status_label = tk.Label(conn, textvariable=self.header_marquee_var, anchor="w", padx=6)
        self.temp_status_label.grid(row=0, column=4, padx=(12, 0), sticky="ew")

        self.files_window: tk.Toplevel | None = None

        actions = ttk.Frame(top_left)
        actions.grid(row=1, column=0, sticky="ew", pady=(6, 0))
        for idx in range(5):
            actions.columnconfigure(idx, weight=1)
        btn = ttk.Button(actions, text="Файлы и прошивка", command=self.show_files_firmware_window)
        btn.grid(row=0, column=0, padx=3, sticky="ew")
        self.action_widgets.append(btn)
        btn = ttk.Button(actions, text="Manual", command=self.show_manual)
        btn.grid(row=0, column=1, padx=3, sticky="ew")
        self.action_widgets.append(btn)
        btn = ttk.Button(actions, text="Сброс USB", command=self.reset_usb_session)
        btn.grid(row=0, column=2, padx=3, sticky="ew")
        self.action_widgets.append(btn)
        btn = ttk.Button(actions, text="Экспорт Cura", command=self.export_cura_bundle)
        btn.grid(row=0, column=3, padx=3, sticky="ew")
        self.action_widgets.append(btn)
        btn = ttk.Button(actions, text="Звук ПК", command=self.play_computer_melody_button)
        btn.grid(row=0, column=4, padx=3, sticky="ew")
        self.action_widgets.append(btn)

        substatus = ttk.Frame(top_left)
        substatus.grid(row=2, column=0, sticky="ew", pady=(6, 0))
        substatus.columnconfigure(0, weight=1)
        toggles = ttk.Frame(substatus)
        toggles.grid(row=0, column=0, sticky="ew")
        ttk.Checkbutton(toggles, text="Звук окончания печати ПК", variable=self.computer_melody_on_complete_var).pack(side="left")
        self.progress_wrap = tk.Frame(substatus, bd=0, highlightthickness=0)
        self.progress_wrap.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        self.progress_wrap.columnconfigure(0, weight=1)
        self.progress_wrap.configure(height=30)
        self.progress_bar = ttk.Progressbar(self.progress_wrap, orient="horizontal", mode="determinate", maximum=100, style="LH.Horizontal.TProgressbar")
        self.progress_bar.grid(row=0, column=0, sticky="ew")
        self.progress_label = tk.Label(self.progress_wrap, textvariable=self.progress_var, anchor="center", bd=0, padx=6)
        self.progress_label.place(relx=0.5, rely=0.5, anchor="center")

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
        ttk.Label(graph, text="Температура hotend").grid(row=0, column=0, sticky="w", pady=(0, 6))
        self.temp_canvas = tk.Canvas(graph, width=760, height=280, bd=0, highlightthickness=1)
        self.temp_canvas.grid(row=1, column=0, sticky="nsew")
        self.temp_canvas.bind("<Configure>", lambda _event: self._draw_temp_graph())

        self.left_split = tk.PanedWindow(left, orient="vertical", sashwidth=6, bd=0, opaqueresize=True)
        self.left_split.grid(row=0, column=0, sticky="nsew")

        live_frame = ttk.LabelFrame(self.left_split, text="Параметры в реальном времени", padding=8)
        live_frame.columnconfigure(0, weight=1)
        live_frame.rowconfigure(0, weight=1)

        self.live_text = tk.Text(live_frame, height=10, wrap="word")
        self.live_text.grid(row=0, column=0, sticky="nsew")
        self.live_text.configure(state="disabled")

        sd_frame = ttk.LabelFrame(self.left_split, text="Файлы на SD принтера", padding=8)
        sd_frame.columnconfigure(0, weight=1)
        sd_frame.columnconfigure(1, weight=0)
        sd_frame.rowconfigure(6, weight=1)

        ttk.Label(sd_frame, textvariable=self.selected_sd_var).grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(sd_frame, textvariable=self.active_sd_var).grid(row=1, column=0, columnspan=2, sticky="w", pady=(2, 0))
        ttk.Label(sd_frame, textvariable=self.print_start_var).grid(row=2, column=0, columnspan=2, sticky="w", pady=(2, 0))
        self.sd_notice_label = tk.Label(sd_frame, textvariable=self.sd_notice_var, anchor="w", justify="left", wraplength=320)
        self.sd_notice_label.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(4, 0))

        ttk.Label(sd_frame, text="Файлы для печати").grid(row=4, column=0, sticky="w", pady=(6, 0))
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
        ttk.Button(buttons, text="Обновить список", command=self.refresh_sd_files).grid(row=0, column=0, padx=3, pady=2, sticky="ew")
        ttk.Button(buttons, text="Старт печати", command=self.start_selected_print_with_home).grid(row=0, column=1, padx=3, pady=2, sticky="ew")
        ttk.Button(buttons, text="Удалить", command=self.delete_selected_file).grid(row=0, column=2, padx=3, pady=2, sticky="ew")
        ttk.Button(buttons, text="Пауза", command=self.pause_print).grid(row=1, column=0, padx=3, pady=2, sticky="ew")
        ttk.Button(buttons, text="Продолжить", command=self.resume_print).grid(row=1, column=1, padx=3, pady=2, sticky="ew")
        ttk.Button(buttons, text="Стоп", command=self.stop_print).grid(row=1, column=2, padx=3, pady=2, sticky="ew")
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
        motion.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        for idx in range(4):
            motion.columnconfigure(idx, weight=1)

        ttk.Button(motion, text="Запомнить старт", command=self.set_current_home_zero).grid(row=0, column=0, padx=2, pady=2, sticky="ew")
        ttk.Button(motion, text="К старту", command=self.go_print_home).grid(row=0, column=1, padx=2, pady=2, sticky="ew")
        ttk.Button(motion, text="Моторы выкл", command=self.motor_off).grid(row=0, column=2, columnspan=2, padx=2, pady=2, sticky="ew")

        ttk.Label(motion, text="Шаг").grid(row=1, column=0, sticky="w", pady=(2, 1))
        step_box = ttk.Frame(motion)
        step_box.grid(row=1, column=1, columnspan=3, sticky="w", pady=(2, 1))
        for value in (0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 20.0):
            ttk.Radiobutton(step_box, text=str(value), value=value, variable=self.step_var).pack(side="left", padx=2)

        ttk.Button(motion, text="Голова влево", command=lambda: self.jog_axis("X", -self.step_var.get())).grid(row=2, column=0, padx=2, pady=2, sticky="ew")
        ttk.Button(motion, text="Голова вправо", command=lambda: self.jog_axis("X", self.step_var.get())).grid(row=2, column=1, padx=2, pady=2, sticky="ew")
        ttk.Button(motion, text="Стол от себя", command=lambda: self.jog_axis("Y", -self.step_var.get())).grid(row=2, column=2, padx=2, pady=2, sticky="ew")
        ttk.Button(motion, text="Стол к себе", command=lambda: self.jog_axis("Y", self.step_var.get())).grid(row=2, column=3, padx=2, pady=2, sticky="ew")
        ttk.Button(motion, text="Голова вниз", command=lambda: self.jog_axis("Z", -self.step_var.get())).grid(row=3, column=0, padx=2, pady=2, sticky="ew")
        ttk.Button(motion, text="Голова вверх", command=lambda: self.jog_axis("Z", self.step_var.get())).grid(row=3, column=1, padx=2, pady=2, sticky="ew")
        ttk.Button(motion, text="Жёсткий стоп", command=self.hard_stop).grid(row=3, column=2, columnspan=2, padx=2, pady=2, sticky="ew")

        level = ttk.LabelFrame(controls, text="Калибровка стола", padding=6)
        level.grid(row=0, column=1, sticky="nsew", padx=(5, 0))
        for idx in range(3):
            level.columnconfigure(idx, weight=1)

        ttk.Label(level, text="Точки X/Y").grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 2))
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
        ttk.Button(metrics_buttons, text="Снять все метрики", command=self.refresh_metrics).pack(side="left")
        ttk.Button(metrics_buttons, text="Сохранить лог", command=self.save_log_snapshot).pack(side="left", padx=(8, 0))
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
        if self.last_temp_current is None:
            temp_line = "Hotend: нет данных"
            age_line = "Возраст телеметрии: нет данных"
        else:
            stale = (now - self.last_temp_sample_ts) > 4.0
            state = "устарели" if stale else "свежие"
            temp_line = f"Hotend: {self.last_temp_current:.2f} / {self.last_temp_target or 0.0:.2f} C"
            age_line = f"Возраст телеметрии: {now - self.last_temp_sample_ts:.1f} c ({state})"

        sd_age = f"{now - self.last_sd_sample_ts:.1f} c" if self.last_sd_sample_ts else "нет данных"
        heater_line = f"Heater PWM @: {self.last_heater_power if self.last_heater_power is not None else '?'}"
        pos_line = self.last_position_line
        zero_line = "да" if self.session_zero_defined else "нет"
        fw_line = self.last_fw_identity or "-"
        if self.current_print_start_ts:
            start_line = f"Старт печати: {time.strftime('%H:%M:%S', time.localtime(self.current_print_start_ts))}"
            self.print_start_var.set(f"Старт: {time.strftime('%H:%M:%S', time.localtime(self.current_print_start_ts))}")
        else:
            start_line = "Старт печати: -"
            self.print_start_var.set("Старт: -")

        lines = [
            temp_line,
            heater_line,
            f"SD: {self.last_sd_summary}",
            f"Возраст SD-статуса: {sd_age}",
            self.progress_var.get(),
            f"Файл: {self.current_print_file}",
            f"Позиция: {pos_line}",
            f"Старт сохранён: {zero_line}",
            f"Прошивка: {fw_line}",
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
        for child in parent.winfo_children():
            child.destroy()
        parent.columnconfigure(1, weight=1)
        parent.columnconfigure(2, minsize=110)
        parent.columnconfigure(3, minsize=110)

        ttk.Label(parent, text="G-code").grid(row=0, column=0, sticky="w")
        ttk.Entry(parent, textvariable=self.local_gcode_var).grid(row=0, column=1, columnspan=2, sticky="ew", padx=4)
        btn = ttk.Button(parent, text="Выбрать", command=self.pick_gcode)
        btn.grid(row=0, column=3, padx=4, sticky="ew")
        self.action_widgets.append(btn)

        ttk.Label(parent, text="Имя на SD").grid(row=1, column=0, sticky="w")
        ttk.Entry(parent, textvariable=self.dest_name_var).grid(row=1, column=1, columnspan=2, sticky="ew", padx=4)
        btn = ttk.Button(parent, text="Залить G-code", command=self.upload_gcode)
        btn.grid(row=1, column=3, padx=4, sticky="ew")
        self.action_widgets.append(btn)

        btn = ttk.Button(parent, text="Залить и старт", command=self.upload_and_start_gcode)
        btn.grid(row=2, column=2, columnspan=2, padx=4, pady=(4, 0), sticky="ew")
        self.action_widgets.append(btn)

        ttk.Separator(parent, orient="horizontal").grid(row=3, column=0, columnspan=4, sticky="ew", pady=8)
        ttk.Label(parent, text="Прошивка").grid(row=4, column=0, sticky="w")
        ttk.Entry(parent, textvariable=self.firmware_var).grid(row=4, column=1, columnspan=2, sticky="ew", padx=4)
        btn = ttk.Button(parent, text="Выбрать", command=self.pick_firmware)
        btn.grid(row=4, column=3, padx=4, sticky="ew")
        self.action_widgets.append(btn)

        btn = ttk.Button(parent, text="Создать EEPROM.DAT", command=self.create_eeprom_via_printer)
        btn.grid(row=5, column=1, padx=4, pady=(4, 0), sticky="ew")
        self.action_widgets.append(btn)

        btn = ttk.Button(parent, text="Залить прошивку", command=self.flash_firmware)
        btn.grid(row=5, column=2, columnspan=2, padx=4, pady=(4, 0), sticky="ew")
        self.action_widgets.append(btn)

        status = tk.Label(parent, textvariable=self.files_status_var, anchor="w", justify="left", wraplength=700)
        status.grid(row=6, column=0, columnspan=4, sticky="ew", pady=(10, 0))
        status.configure(bg=self.colors["panel"], fg=self.colors["muted"], font=("DejaVu Sans", 9))

    def show_files_firmware_window(self) -> None:
        if self.files_window and self.files_window.winfo_exists():
            self.files_window.deiconify()
            self.files_window.lift()
            self.files_window.focus_force()
            return

        win = tk.Toplevel(self.root)
        self.files_window = win
        win.title("Little Hands — Файлы и прошивка")
        win.geometry("760x280")
        win.minsize(680, 240)
        win.configure(bg=self.colors["bg"])

        frame = ttk.LabelFrame(win, text="Файлы и прошивка", padding=10)
        frame.pack(fill="both", expand=True, padx=10, pady=10)
        self._populate_files_firmware_container(frame)

        def _on_close() -> None:
            self.files_window = None
            win.destroy()

        win.protocol("WM_DELETE_WINDOW", _on_close)

    def _set_busy_ui(self, busy: bool, label: str | None = None) -> None:
        self.busy_var.set(label or ("USB: busy" if busy else "USB: idle"))
        state = "disabled" if busy else "normal"
        for widget in self.action_widgets:
            try:
                widget.configure(state=state)
            except Exception:
                pass
        if busy and label and "g-code" in label.lower():
            self.progress_var.set("Upload: writing to SD...")
            self.progress_bar.configure(mode="indeterminate")
            self.progress_bar.start(12)
        elif not busy:
            self.progress_bar.stop()
            self.progress_bar.configure(mode="determinate")

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
                messagebox.showerror("K9 Control Center", str(payload))
                self.log(f"Ошибка: {payload}")
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
                if str(label).startswith("Upload"):
                    self.progress_bar.stop()
                    self.progress_bar.configure(mode="determinate")
                self.progress_var.set(str(label))
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
                self.active_sd_var.set(str(payload))
            elif kind == "ports":
                ports, detected = payload  # type: ignore[misc]
                self._set_port_choices(list(ports), str(detected) if detected else None)
            elif kind == "files-status":
                self.files_status_var.set(str(payload))
            elif kind == "find-port-ui":
                active = bool(payload)
                self._set_find_port_busy(active)
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

    def _apply_sd_files(self, files: list[str]) -> None:
        previous_path = self._selected_sd_path()
        self.sd_list = files
        self.sd_print_files = []
        self.sd_other_files = []
        self.sd_display_to_path = {}
        self.sd_print_listbox.delete(0, "end")
        if not files:
            self.sd_print_listbox.insert("end", "(empty)")
            self.selected_sd_var.set("Выбрано на SD: -")
            self.sd_notice_var.set("SD-карта читается, но список файлов пуст.")
            return

        selected_print_index = None
        lowered_paths: list[str] = []
        for idx, entry in enumerate(files):
            display = entry
            path = entry
            if " " in entry:
                display = entry
                path = entry.split()[0]
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
        elif self.sd_print_files:
            self.sd_print_listbox.selection_set(0)
        self._sync_selected_sd_label()
        self._update_sd_notice(lowered_paths)

    def _update_sd_notice(self, lowered_paths: list[str]) -> None:
        has_eeprom = any(Path(path).name.lower() == "eeprom.dat" for path in lowered_paths)
        self.sd_has_eeprom = has_eeprom or self.eeprom_confirmed
        has_bin = any(Path(path).name.lower() == "mkslite.bin" for path in lowered_paths)
        has_cur = any(Path(path).name.lower() == "mkslite.cur" for path in lowered_paths)
        notes: list[str] = []
        if has_bin:
            notes.append("На карте есть mksLite.bin: при следующем старте принтер может снова прошиться.")
        elif has_cur:
            notes.append("На карте есть mksLite.CUR: это след прошлой прошивки, обычно его можно удалить.")
        self.sd_notice_var.set(" ".join(notes))

    def _on_sd_listbox_select(self, source: str) -> None:
        if source != "print":
            self.sd_print_listbox.selection_clear(0, "end")
        self._sync_selected_sd_label()

    def _sync_selected_sd_label(self) -> None:
        path = self._selected_sd_path()
        self.selected_sd_var.set(f"Выбрано на SD: {path or '-'}")

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

    def _port_label(self, meta: dict[str, str]) -> str:
        device = meta.get("device", "")
        desc = meta.get("description", "") or meta.get("product", "") or "serial"
        kind = self._classify_port(meta)
        return f"{device} — {kind} — {desc}"

    def _set_port_choices(self, ports: list[dict[str, str]], preferred: str | None = None) -> None:
        self.port_choices = [DISCONNECTED_PORT_LABEL] + [self._port_label(meta) for meta in ports if meta.get("device")]
        self.port_combo["values"] = self.port_choices

        selected_device = preferred or self.port_var.get().strip()
        if not selected_device:
            self.port_display_var.set(DISCONNECTED_PORT_LABEL)
            self.port_var.set("")
            return
        if selected_device:
            for meta in ports:
                if meta.get("device") == selected_device:
                    self.port_display_var.set(self._port_label(meta))
                    self.port_var.set(selected_device)
                    return
        self.port_display_var.set(DISCONNECTED_PORT_LABEL)
        self.port_var.set("")

    def _on_port_selected(self) -> None:
        text = self.port_display_var.get().strip()
        if text == DISCONNECTED_PORT_LABEL:
            self.disconnect_port(log_change=True)
            return
        device = text.split(" — ", 1)[0].strip() if text else ""
        if device:
            self.port_var.set(device)
            self.log(f"Выбран порт: {device}")

    def disconnect_port(self, log_change: bool = False) -> None:
        self.port_var.set("")
        self.port_display_var.set(DISCONNECTED_PORT_LABEL)
        self.busy_var.set("USB: отключен")
        if log_change:
            self.log("Порт отключён. Автоопрос и команды принтера остановлены до выбора нового порта.")

    def _refresh_ports_on_startup(self) -> None:
        try:
            ports = sdtool.list_serial_ports()
            self._set_port_choices(ports)
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
                self.find_port_button.configure(state="normal", text="Найти")
            except Exception:
                pass

    def _tick_find_port_button(self) -> None:
        if not self.find_port_animating:
            return
        dots = "." * (self.find_port_anim_phase % 4)
        label = "Ищу" + dots
        try:
            self.find_port_button.configure(text=label)
        except Exception:
            return
        self.find_port_anim_phase += 1
        self.root.after(300, self._tick_find_port_button)

    def detect_printer_port_action(self) -> None:
        self._set_find_port_busy(True)

        def task() -> None:
            try:
                self._post("log", "Ищу вероятный порт принтера среди USB/ACM serial...")
                detected, ranked = sdtool.detect_printer_port(self._baud())
                self.events.put(("ports", (ranked, detected)))
                if detected:
                    self._post("log", f"Найден вероятный принтер: {detected}")
                    self._post("info", f"Найден вероятный принтер:\n{detected}")
                else:
                    self._post("log", "Автодетект не нашёл уверенный порт принтера. Оставляю ручной выбор.")
                    self._post("info", "Автопоиск не нашёл уверенный порт принтера.\nВыбери порт вручную из списка.")
            finally:
                self._post("find-port-ui", False)

        self._run_task("Поиск порта принтера", task, require_port=False)

    def _baud(self) -> int:
        return 115200

    def show_manual(self) -> None:
        win = tk.Toplevel(self.root)
        win.title("Little Hands Manual")
        win.geometry("880x760")
        win.configure(bg=self.colors["bg"])
        frame = ttk.Frame(win, padding=10)
        frame.pack(fill="both", expand=True)
        text = ScrolledText(frame, wrap="word")
        text.pack(fill="both", expand=True)
        text.insert("1.0", MANUAL_TEXT)
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
        manual_path.write_text(MANUAL_TEXT + "\n", encoding="utf-8")
        self.log(f"Экспорт Cura готов: {target_root} ({copied} файлов)")

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

    def _run_printer_completion_sequence(self) -> str:
        # Natural print completion: lift the head a little and present the part.
        commands = [
            "M17",
            "G91",
            "G1 Z20 F600",
            "G1 Y20 F900",
            "G90",
            "M400",
        ]
        return sdtool.run_commands(
            self._port(),
            self._baud(),
            commands,
            settle_after_each=0.15,
            final_wait=0.6,
            read_seconds=2.5,
        )

    def _run_task(self, label: str, func, *, require_port: bool = True) -> None:
        if require_port and not self._port():
            messagebox.showerror("Little Hands", "Сначала выбери порт принтера, нажми 'Найти' или оставь 'не подключаться'.")
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

    def _inspect_gcode_file(self, source: Path) -> dict[str, object]:
        info: dict[str, object] = {
            "has_g28": False,
            "target_machine_unknown": False,
            "start_gcode_comment": "",
        }
        try:
            lines = source.read_text(encoding="utf-8", errors="replace").splitlines()[:120]
        except Exception:
            return info
        for line in lines:
            stripped = line.strip()
            if stripped.startswith(";TARGET_MACHINE.NAME:Unknown"):
                info["target_machine_unknown"] = True
            if stripped.startswith("; Little Hands"):
                info["start_gcode_comment"] = stripped
            if not stripped or stripped.startswith(";"):
                continue
            code = stripped.split(";", 1)[0].strip().upper()
            if code.startswith("G28"):
                info["has_g28"] = True
        return info

    def _warn_if_gcode_looks_wrong(self, source: Path) -> None:
        info = self._inspect_gcode_file(source)
        if info.get("has_g28"):
            self.log(
                "Предупреждение: выбранный G-code содержит G28. Для K9 с Little Hands такой файл опасен: "
                "принтер после 'К старту' не должен делать обычный home."
            )
        elif info.get("target_machine_unknown"):
            self.log(
                "Предупреждение: G-code выглядит старым или слайсился не на машине 'lilHands K9 warm mat' "
                "(TARGET_MACHINE.NAME:Unknown)."
            )

    def _validate_gcode_for_current_k9(self, source: Path) -> tuple[bool, str]:
        info = self._inspect_gcode_file(source)
        if info.get("has_g28"):
            return (
                False,
                "Этот G-code содержит G28 в стартовых командах. Для текущего K9 это неверно: "
                "принтер уже ставится в старт через 'К старту', а обычный home потом ломает запуск. "
                "Переслайсь модель на машине 'lilHands K9 warm mat' и профиле 'codex - K9 warm mat cautious'.",
            )
        if info.get("target_machine_unknown"):
            return (
                False,
                "Этот G-code выглядит старым или был слайсен не на 'lilHands K9 warm mat' "
                "(TARGET_MACHINE.NAME:Unknown). Переслайсь модель заново и залей новый файл.",
            )
        return True, ""

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
            self.session_zero_defined = False
            self._post("log", "После включения выставь стартовую позу и нажми 'Запомнить старт'. Потом работают 'К старту' и 'Печать с SD'.")

        self._run_task("Проверка статуса", task)

    def refresh_metrics(self) -> None:
        self.views.select(self.metrics_frame)
        self.metrics_text.configure(state="normal")
        self.metrics_text.delete("1.0", "end")
        self.metrics_text.insert("1.0", "Собираю USB-метрики...\n")
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
                deadline = time.monotonic() + 3.0
                while time.monotonic() < deadline:
                    if self.serial_lock.acquire(blocking=False):
                        acquired = True
                        break
                    time.sleep(0.1)

                if not acquired:
                    self._post(
                        "log",
                        "Сброс USB: порт всё ещё занят текущей операцией. Если это не отпустит через пару секунд, перезапусти Little Hands.",
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
                self._post("log", raw.strip() or "Принтер не вернул список файлов SD.")

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
        dest = self.dest_name_var.get().strip() or source.name
        size_mib = source.stat().st_size / (1024 * 1024)

        def task() -> None:
            last_stage = {"name": None}

            def on_progress(stage: str, percent: float) -> None:
                self._post("progress", (f"{stage}: {percent:.1f}%", percent))
                self._post("files-status", f"Заливка G-code: {stage} {percent:.1f}%")
                if last_stage["name"] != stage:
                    last_stage["name"] = stage
                    self._post("log", f"Этап записи: {stage}")

            self._post("log", f"Локальный файл: {source}")
            self._post("log", f"Размер файла: {size_mib:.2f} MiB. Большие G-code могут писаться 1-5 минут.")
            self._post("progress", ("Upload (preflight): 0.0%", 0.0))
            self._post("files-status", f"Заливка G-code: preflight 0.0%")
            method = sdtool.upload_gcode_auto(self._port(), self._baud(), source, dest, progress_cb=on_progress)
            self._post("progress", ("Upload complete: 100.0%", 100.0))
            self._post("files-status", f"G-code залит: {source.name} -> {dest} ({method})")
            self._post("log", f"Залит G-code: {source.name} -> {dest} ({method})")
            files = sdtool.list_files(self._port(), self._baud())
            self._post("sd-files", files)

        self._run_task("Заливка G-code на SD", task)

    def upload_and_start_gcode(self) -> None:
        source = Path(self.local_gcode_var.get().strip()).expanduser().resolve()
        if not source.is_file():
            messagebox.showerror("Little Hands", "Выбери существующий G-code файл.")
            return
        ok, reason = self._validate_gcode_for_current_k9(source)
        if not ok:
            messagebox.showerror("Little Hands", reason)
            self.log(reason)
            return
        dest = (self.dest_name_var.get().strip() or sdtool.make_sd_name(source.name))
        self.dest_name_var.set(dest)
        size_mib = source.stat().st_size / (1024 * 1024)

        def task() -> None:
            last_stage = {"name": None}

            def on_progress(stage: str, percent: float) -> None:
                self._post("progress", (f"{stage}: {percent:.1f}%", percent))
                self._post("files-status", f"Заливка и старт: {stage} {percent:.1f}%")
                if last_stage["name"] != stage:
                    last_stage["name"] = stage
                    self._post("log", f"Этап записи: {stage}")

            self._post("log", f"Локальный файл: {source}")
            self._post("log", f"Размер файла: {size_mib:.2f} MiB. Большие G-code могут писаться 1-5 минут.")
            self._post("files-status", "Заливка и старт: preflight 0.0%")
            method = sdtool.upload_gcode_auto(self._port(), self._baud(), source, dest, progress_cb=on_progress)
            self._post("files-status", f"G-code залит: {source.name} -> {dest} ({method}). Запускаю печать...")
            self._post("log", f"Залит G-code: {source.name} -> {dest} ({method})")
            files = sdtool.list_files(self._port(), self._baud())
            self._post("sd-files", files)
            out = sdtool.start_sd_print_from_pseudo_home(self._port(), self._baud(), dest)
            self.current_print_file = dest
            self._post("active-sd", f"Печатается: {dest}")
            self._post("log", out.strip() or f"Печать запущена от K9 pseudo-home: {dest}")
            self._post("progress", ("Печать: старт", 0.0))
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

    def start_selected_print(self) -> None:
        path = self._selected_print_sd_path()
        if not path:
            messagebox.showerror("K9 Control Center", "Выбери файл в секции 'Файлы для печати'.")
            return

        def task() -> None:
            out = sdtool.start_sd_print(self._port(), self._baud(), path)
            self.current_print_file = path
            self.current_print_start_ts = time.time()
            self.current_print_progress_pct = 0.0
            self.print_state_restored_from_log = False
            self.print_start_watchdog_alerted = False
            self._append_ring_log(f"{time.strftime('%H:%M:%S')} PRINT_START file={path}")
            self._post("active-sd", f"Печатается: {path}")
            self._post("log", out.strip() or f"Печать запущена: {path}")
            self.print_was_active = False
            self.suppress_next_completion_chime = False

        self._run_task("Запуск SD-печати", task)

    def start_selected_print_with_home(self) -> None:
        path = self._selected_print_sd_path()
        if not path:
            messagebox.showerror("Little Hands", "Выбери файл в секции 'Файлы для печати'.")
            return
        if not self.session_zero_defined:
            messagebox.showerror("Little Hands", "Сначала выставь стартовую позу и нажми 'Запомнить старт'.")
            return

        def task() -> None:
            out = sdtool.start_sd_print_from_home(self._port(), self._baud(), path)
            self.current_print_file = path
            self.current_print_start_ts = time.time()
            self.current_print_progress_pct = 0.0
            self.print_state_restored_from_log = False
            self.print_start_watchdog_alerted = False
            self._append_ring_log(f"{time.strftime('%H:%M:%S')} PRINT_START file={path}")
            self._post("active-sd", f"Печатается: {path}")
            self._post("log", out.strip() or f"Печать с SD запущена от сохранённого старта: {path}")
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
        self.current_print_start_ts = None
        self.current_print_progress_pct = None
        self.print_state_restored_from_log = False
        self.print_was_active = False
        self.print_start_watchdog_alerted = False
        self._post("active-sd", "Печатается: -")
        self._post("progress", (progress_label, progress_value))
        self._post("sd", "SD: idle")

    def stop_print(self) -> None:
        def task() -> None:
            self.suppress_next_completion_chime = True
            out = ""
            error_text = None
            try:
                out = sdtool.stop_sd_print(self._port(), self._baud())
            except Exception as exc:
                error_text = str(exc)
            finally:
                self._clear_print_session_state("Печать: остановлена", 0.0)
            if out.strip():
                self._post("log", out.strip())
            elif error_text:
                self._post("log", f"Стоп отправлен локально, но принтер ответил неуверенно: {error_text}")
            else:
                self._post("log", "Стоп отправлен")

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
                    ["M524", "M104 S0", "M140 S0", "M107", "M400", "M18"],
                    settle_after_each=0.4,
                    final_wait=1.2,
                    read_seconds=2.5,
                )
            except Exception as exc:
                error_text = str(exc)
            finally:
                self._clear_print_session_state("Печать: жёсткий стоп", 0.0)
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
            out = sdtool.run_commands(self._port(), self._baud(), ["G90", "G28"], final_wait=1.2, read_seconds=2.0)
            self._post("log", out.strip() or "Home выполнен")

        self._run_task("Home всех осей", task)

    def set_current_home_zero(self) -> None:
        def task() -> None:
            out = sdtool.set_current_home_zero(self._port(), self._baud())
            self.session_zero_defined = True
            self._post("log", out.strip() or "Стартовая поза запомнена")
            self._post("log", "Теперь можно нажимать 'К старту' и 'Печать с SD'.")

        self._run_task("Запоминание стартовой позы", task)

    def go_print_home(self) -> None:
        if not self.session_zero_defined:
            messagebox.showerror("Little Hands", "Сначала выставь стартовую позу и нажми 'Запомнить старт'.")
            return

        def task() -> None:
            out = sdtool.goto_print_home(self._port(), self._baud())
            self._post("log", out.strip() or "Принтер возвращён к стартовой позе")

        self._run_task("Переход к сохранённому 0", task)

    def motor_off(self) -> None:
        def task() -> None:
            out = sdtool.query_command(self._port(), self._baud(), "M18", wait_before_read=0.4, read_seconds=1.0)
            self._post("log", out.strip() or "Моторы отключены")

        self._run_task("Отключение моторов", task)

    def jog_axis(self, axis: str, distance: float) -> None:
        feedrate = 1200 if axis == "Y" else 2400
        display_axis = self._operator_axis_name(axis)
        display_hint = self._operator_axis_hint(axis)

        def task() -> None:
            out = sdtool.run_commands(
                self._port(),
                self._baud(),
                ["M17", "G90", "M211 S0", "G91", f"G1 {axis}{distance:.3f} F{feedrate}", "G90"],
                final_wait=0.8,
                read_seconds=1.5,
            )
            self._post("log", out.strip() or f"{display_axis} ({display_hint}) {'+' if distance >= 0 else ''}{distance:g}")

        self._run_task(f"Сдвиг {display_axis}", task)

    def move_level_point(self, x: float, y: float) -> None:
        def task() -> None:
            out = sdtool.run_commands(
                self._port(),
                self._baud(),
                ["G90", "M211 S0", "G1 Z10 F600", f"G1 X{x:.2f} Y{y:.2f} F1800", "G1 Z0 F600"],
                final_wait=0.8,
                read_seconds=2.0,
            )
            self._post("log", out.strip() or f"Переход к точке X{x:.0f} Y{y:.0f}")

        self._run_task(f"Переход к точке X{x:.0f} Y{y:.0f}", task)

    def _poll_status(self) -> None:
        if not self._port():
            self.busy_var.set("USB: отключен")
            self.root.after(1000, self._poll_status)
            return
        if self.monitor_enabled and not self.user_task_pending and self.serial_lock.acquire(blocking=False):
            threading.Thread(target=self._poll_worker, daemon=True).start()
        self.root.after(1000, self._poll_status)

    def _poll_worker(self) -> None:
        try:
            now = time.time()
            temp = sdtool.query_command(self._port(), self._baud(), "M105", wait_before_read=0.12, read_seconds=0.45)
            match = TEMP_RE.search(temp)
            current_temp = None
            target_temp = None
            if match:
                current_temp = float(match.group(1))
                target_temp = float(match.group(2))
                heater_match = HEATER_RE.search(temp)
                heater = int(heater_match.group(1)) if heater_match else None
                self._post("temp", (current_temp, target_temp, heater))
                if now - self.last_temp_log_ts >= TEMP_LOG_INTERVAL_SEC:
                    self.last_temp_log_ts = now
                    heater_value = heater if heater is not None else "?"
                    self._append_ring_log(
                        f"{time.strftime('%H:%M:%S')} M105 T:{current_temp:.2f} /{target_temp:.2f} @:{heater_value}"
                    )
            self._post("metrics", ("m105", temp))
            sd = sdtool.query_command(self._port(), self._baud(), "M27", wait_before_read=0.15, read_seconds=0.45)
            summary = next((line.strip() for line in sd.splitlines() if line.strip()), "SD: idle")
            self._post("sd", summary)
            if (now - self.last_position_sample_ts) >= 3.0:
                m114 = sdtool.query_command(self._port(), self._baud(), "M114", wait_before_read=0.1, read_seconds=0.35)
                pos_line = next((line.strip() for line in m114.splitlines() if "X:" in line and "Y:" in line and "Z:" in line), "").strip()
                if pos_line:
                    self._post("pos", pos_line)
                self._post("metrics", ("m114", m114))
            if not self.last_fw_line and (now - self.last_fw_query_ts) >= 15.0:
                self.last_fw_query_ts = now
                m115 = sdtool.query_command(self._port(), self._baud(), "M115", wait_before_read=0.1, read_seconds=0.5)
                fw_line = next((line for line in m115.splitlines() if line.startswith("FIRMWARE_NAME:")), "")
                if fw_line:
                    self._post("fw", self._format_fw_line(fw_line))
                self._post("metrics", ("m115", m115))
            progress_match = SD_PROGRESS_RE.search(sd)
            if progress_match:
                done = int(progress_match.group(1))
                total = max(int(progress_match.group(2)), 1)
                pct = max(0.0, min(100.0, (done / total) * 100.0))
                self.print_was_active = True
                self.current_print_progress_pct = pct
                if self.current_print_file != "-":
                    self._post("active-sd", f"Печатается: {self.current_print_file}")
                else:
                    self._post("active-sd", "Печатается: идёт печать (имя не восстановлено)")
                self._post("progress", (f"Печать: {pct:.1f}% ({done}/{total})", pct))
                if now - self.last_telemetry_log_ts >= 5.0 and current_temp is not None and target_temp is not None:
                    self.last_telemetry_log_ts = now
                    self._append_ring_log(
                        f"{time.strftime('%H:%M:%S')} TELEMETRY file={self.current_print_file} progress={pct:.1f}% temp={current_temp:.2f}/{target_temp:.2f} sd=\"{summary}\""
                    )
            elif "Not SD printing" in sd:
                self._post("progress", ("Печать: простой", 0.0))
                if self.print_state_restored_from_log and not self.print_was_active:
                    self.current_print_file = "-"
                    self.current_print_start_ts = None
                    self.current_print_progress_pct = None
                    self.print_state_restored_from_log = False
                    self.print_start_watchdog_alerted = False
                    self._post("active-sd", "Печатается: -")
                    self._post("log", "Сбросил восстановленное из лога состояние печати: на текущем принтере активной SD-печати нет.")
                    return
                if self.print_was_active:
                    self.print_was_active = False
                    completion_move_result = ""
                    computer_melody_enabled = bool(self.computer_melody_on_complete_var.get())
                    if not self.suppress_next_completion_chime:
                        try:
                            completion_move_result = self._run_printer_completion_sequence().strip()
                        except Exception as exc:
                            self._post("log", f"Пост-обработка после печати не удалась: {exc}")
                    if self.suppress_next_completion_chime:
                        self.suppress_next_completion_chime = False
                    else:
                        if computer_melody_enabled:
                            self._post("melody", None)
                        if completion_move_result:
                            self._post("log", completion_move_result)
                        if computer_melody_enabled:
                            self._post("log", "Печать завершена: стол выдвинут, голова поднята, проиграна мелодия на компьютере")
                        else:
                            self._post("log", "Печать завершена: стол выдвинут, голова поднята")
                        self._post(
                            "info",
                            "Печать завершена.\n\n"
                            "1. Сними модель со стола.\n"
                            "2. Выключи принтер по питанию на 5–10 секунд и включи снова.\n"
                            "3. Выставь стартовую позу.\n"
                            "4. Нажми 'К старту'.\n"
                            "5. Если поза совпала со стартовой, нажми 'Запомнить старт'.\n\n"
                            "Так у тебя останется валидный старт для следующей печати."
                        )
                    self._append_ring_log(
                        f"{time.strftime('%H:%M:%S')} PRINT_END file={self.current_print_file} temp={current_temp if current_temp is not None else '?'}"
                    )
                    self.current_print_file = "-"
                    self.current_print_start_ts = None
                    self.current_print_progress_pct = None
                    self.print_state_restored_from_log = False
                    self.print_start_watchdog_alerted = False
                    self._post("active-sd", "Печатается: -")
                elif (
                    self.current_print_file != "-"
                    and self.current_print_start_ts
                    and not self.print_start_watchdog_alerted
                    and (now - self.current_print_start_ts) >= 20.0
                ):
                    self.print_start_watchdog_alerted = True
                    msg = (
                        "Печать была запущена, но принтер долго не начал двигаться. "
                        "Если телеметрия замерла или слышны только щелчки, самый надёжный следующий шаг — "
                        "выключить принтер по питанию на 5–10 секунд, включить снова, заново выставить стартовую "
                        "позу и только потом повторить запуск. Также проверь, что EEPROM сохранён корректно, и если "
                        "нужно создай его через окно 'Файлы и прошивка'."
                    )
                    self._post("log", msg)
                    self._post("info", msg)
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
