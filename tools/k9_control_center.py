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
import threading
import time
from pathlib import Path
import tkinter as tk
import tkinter.font as tkfont
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText

import k9_marlin_sd as sdtool


PROJECT_ROOT = Path("/home/maxim/draftCode/littleHands")
DEFAULT_FIRMWARE = PROJECT_ROOT / "firmware/ecf-k9-et4000plus-single-fan-guard-binary-upload-eeprom-init-mksLite.bin"


TEMP_RE = re.compile(r"T:([-\d.]+)\s*/([-\d.]+)")
SD_PROGRESS_RE = re.compile(r"SD printing byte\s+(\d+)\s*/\s*(\d+)", re.IGNORECASE)


class K9ControlCenter:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Little Hands Control Center")
        self.root.geometry("1220x820")

        self.events: queue.Queue[tuple[str, object]] = queue.Queue()
        self.serial_lock = threading.Lock()
        self.monitor_enabled = True
        self.user_task_pending = False

        self.port_var = tk.StringVar(value="/dev/ttyUSB0")
        self.baud_var = tk.StringVar(value="115200")
        self.local_gcode_var = tk.StringVar()
        self.dest_name_var = tk.StringVar(value="MODEL.GCO")
        self.firmware_var = tk.StringVar(value=str(DEFAULT_FIRMWARE))
        self.temp_var = tk.StringVar(value="Hotend: ? / ? C")
        self.sd_var = tk.StringVar(value="SD: unknown")
        self.fw_var = tk.StringVar(value="Firmware: unknown")
        self.progress_var = tk.StringVar(value="Print: idle")
        self.busy_var = tk.StringVar(value="USB: idle")
        self.step_var = tk.DoubleVar(value=5.0)

        self.sd_list: list[str] = []
        self.sd_display_to_path: dict[str, str] = {}
        self.metrics_sections: dict[str, str] = {}
        self.action_widgets: list[ttk.Widget] = []

        self._build_ui()
        self._apply_theme()
        self.root.after(150, self._drain_events)
        self.root.after(1200, self._poll_status)

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
            "Vertical.TScrollbar",
            background=colors["panel_alt"],
            troughcolor=colors["field"],
            bordercolor=colors["border"],
            arrowcolor=colors["accent"],
        )

        self.sd_listbox.configure(
            bg=colors["field"],
            fg=colors["text"],
            selectbackground=colors["accent"],
            selectforeground=colors["field"],
            highlightbackground=colors["border"],
            highlightcolor=colors["accent"],
            relief="solid",
            borderwidth=1,
        )
        self.log_text.configure(
            bg=colors["field"],
            fg=colors["text"],
            insertbackground=colors["accent"],
            selectbackground=colors["accent"],
            selectforeground=colors["field"],
            highlightbackground=colors["border"],
            highlightcolor=colors["accent"],
            relief="solid",
            borderwidth=1,
        )
        self.metrics_text.configure(
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
        self._draw_corner_hands()

    def _build_ui(self) -> None:
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)

        top = ttk.Frame(self.root, padding=10)
        top.grid(row=0, column=0, sticky="ew")
        top.columnconfigure(10, weight=1)

        ttk.Label(top, text="Port").grid(row=0, column=0, sticky="w")
        ttk.Entry(top, textvariable=self.port_var, width=16).grid(row=0, column=1, padx=(4, 8))
        ttk.Label(top, text="Baud").grid(row=0, column=2, sticky="w")
        ttk.Entry(top, textvariable=self.baud_var, width=10).grid(row=0, column=3, padx=(4, 8))
        btn = ttk.Button(top, text="Проверить", command=self.refresh_status)
        btn.grid(row=0, column=4, padx=4)
        self.action_widgets.append(btn)
        btn = ttk.Button(top, text="Обновить SD", command=self.refresh_sd_files)
        btn.grid(row=0, column=5, padx=4)
        self.action_widgets.append(btn)
        ttk.Label(top, textvariable=self.temp_var).grid(row=0, column=6, padx=(12, 8), sticky="w")
        ttk.Label(top, textvariable=self.sd_var).grid(row=0, column=7, padx=(12, 8), sticky="w")
        ttk.Label(top, textvariable=self.fw_var).grid(row=0, column=8, padx=(12, 8), sticky="w")
        ttk.Label(top, textvariable=self.busy_var).grid(row=1, column=0, columnspan=4, sticky="w")
        ttk.Label(top, textvariable=self.progress_var).grid(row=1, column=6, padx=(12, 8), sticky="w")
        self.progress_bar = ttk.Progressbar(top, orient="horizontal", mode="determinate", maximum=100, length=260)
        self.progress_bar.grid(row=1, column=7, columnspan=2, padx=(12, 8), sticky="ew")
        self.hands_canvas = tk.Canvas(top, width=120, height=64, bd=0, highlightthickness=0)
        self.hands_canvas.grid(row=0, column=10, rowspan=2, sticky="ne", padx=(12, 0))

        main = ttk.Panedwindow(self.root, orient="horizontal")
        main.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))

        left = ttk.Frame(main, padding=6)
        left.columnconfigure(0, weight=1)
        left.rowconfigure(1, weight=1)
        main.add(left, weight=1)

        right = ttk.Frame(main, padding=6)
        right.columnconfigure(0, weight=1)
        main.add(right, weight=4)

        upload = ttk.LabelFrame(left, text="Файлы и прошивка", padding=8)
        upload.grid(row=0, column=0, sticky="ew")
        upload.columnconfigure(1, weight=1)

        ttk.Label(upload, text="G-code").grid(row=0, column=0, sticky="w")
        ttk.Entry(upload, textvariable=self.local_gcode_var).grid(row=0, column=1, sticky="ew", padx=4)
        ttk.Button(upload, text="Выбрать", command=self.pick_gcode).grid(row=0, column=2, padx=4)
        ttk.Label(upload, text="Имя на SD").grid(row=1, column=0, sticky="w")
        ttk.Entry(upload, textvariable=self.dest_name_var).grid(row=1, column=1, sticky="ew", padx=4)
        ttk.Button(upload, text="Залить G-code", command=self.upload_gcode).grid(row=1, column=2, padx=4)

        ttk.Separator(upload, orient="horizontal").grid(row=2, column=0, columnspan=3, sticky="ew", pady=8)
        ttk.Label(upload, text="Прошивка").grid(row=3, column=0, sticky="w")
        ttk.Entry(upload, textvariable=self.firmware_var).grid(row=3, column=1, sticky="ew", padx=4)
        ttk.Button(upload, text="Выбрать", command=self.pick_firmware).grid(row=3, column=2, padx=4)
        ttk.Button(upload, text="Залить прошивку", command=self.flash_firmware).grid(row=4, column=2, padx=4, pady=(6, 0))

        sd_frame = ttk.LabelFrame(left, text="Файлы на SD принтера", padding=8)
        sd_frame.grid(row=1, column=0, sticky="nsew", pady=(10, 0))
        sd_frame.columnconfigure(0, weight=1)
        sd_frame.rowconfigure(0, weight=1)

        self.sd_listbox = tk.Listbox(sd_frame, height=10, exportselection=False)
        self.sd_listbox.grid(row=0, column=0, sticky="nsew")
        self.sd_listbox.bind("<Double-1>", lambda _event: self.start_selected_print())
        sd_scroll = ttk.Scrollbar(sd_frame, orient="vertical", command=self.sd_listbox.yview)
        sd_scroll.grid(row=0, column=1, sticky="ns")
        self.sd_listbox.configure(yscrollcommand=sd_scroll.set)

        buttons = ttk.Frame(sd_frame)
        buttons.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        for idx in range(6):
            buttons.columnconfigure(idx, weight=1)
        ttk.Button(buttons, text="Обновить", command=self.refresh_sd_files).grid(row=0, column=0, padx=3, sticky="ew")
        ttk.Button(buttons, text="Пуск", command=self.start_selected_print).grid(row=0, column=1, padx=3, sticky="ew")
        ttk.Button(buttons, text="Пауза", command=self.pause_print).grid(row=0, column=2, padx=3, sticky="ew")
        ttk.Button(buttons, text="Продолжить", command=self.resume_print).grid(row=0, column=3, padx=3, sticky="ew")
        ttk.Button(buttons, text="Стоп", command=self.stop_print).grid(row=0, column=4, padx=3, sticky="ew")
        ttk.Button(buttons, text="Удалить", command=self.delete_selected_file).grid(row=0, column=5, padx=3, sticky="ew")

        motion = ttk.LabelFrame(right, text="Ручное управление", padding=8)
        motion.grid(row=0, column=0, sticky="ew")
        for idx in range(5):
            motion.columnconfigure(idx, weight=1)

        ttk.Button(motion, text="Home", command=self.home_all).grid(row=0, column=0, padx=2, pady=2, sticky="ew")
        ttk.Button(motion, text="Motor Off", command=self.motor_off).grid(row=0, column=1, padx=2, pady=2, sticky="ew")
        ttk.Button(motion, text="Status", command=self.refresh_status).grid(row=0, column=2, padx=2, pady=2, sticky="ew")

        ttk.Label(motion, text="Шаг").grid(row=1, column=0, sticky="w", pady=(4, 2))
        step_box = ttk.Frame(motion)
        step_box.grid(row=1, column=1, columnspan=4, sticky="w", pady=(4, 2))
        for value in (0.1, 1.0, 5.0, 10.0, 20.0):
            ttk.Radiobutton(step_box, text=str(value), value=value, variable=self.step_var).pack(side="left", padx=3)

        ttk.Label(motion, text="X: голова  Y: вверх/вниз  Z: стол").grid(row=2, column=0, columnspan=5, sticky="w", pady=(4, 2))
        ttk.Button(motion, text="X -", command=lambda: self.jog_axis("X", -self.step_var.get())).grid(row=3, column=0, padx=2, pady=2, sticky="ew")
        ttk.Button(motion, text="X +", command=lambda: self.jog_axis("X", self.step_var.get())).grid(row=3, column=1, padx=2, pady=2, sticky="ew")
        ttk.Button(motion, text="Y -", command=lambda: self.jog_axis("Y", -self.step_var.get())).grid(row=3, column=2, padx=2, pady=2, sticky="ew")
        ttk.Button(motion, text="Y +", command=lambda: self.jog_axis("Y", self.step_var.get())).grid(row=3, column=3, padx=2, pady=2, sticky="ew")
        ttk.Button(motion, text="Z -", command=lambda: self.jog_axis("Z", -self.step_var.get())).grid(row=3, column=4, padx=2, pady=2, sticky="ew")
        ttk.Button(motion, text="Z +", command=lambda: self.jog_axis("Z", self.step_var.get())).grid(row=4, column=0, padx=2, pady=2, sticky="ew")

        level = ttk.LabelFrame(right, text="Калибровка стола", padding=8)
        level.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        for idx in range(3):
            level.columnconfigure(idx, weight=1)

        ttk.Label(level, text="Home -> опускай Y малыми шагами -> точки X/Z").grid(
            row=0, column=0, columnspan=3, sticky="w", pady=(0, 4)
        )
        ttk.Button(level, text="ПЛ", command=lambda: self.move_level_point(5, 5)).grid(row=1, column=0, padx=2, pady=2, sticky="ew")
        ttk.Button(level, text="Центр", command=lambda: self.move_level_point(50, 50)).grid(row=1, column=1, padx=2, pady=2, sticky="ew")
        ttk.Button(level, text="ПП", command=lambda: self.move_level_point(95, 5)).grid(row=1, column=2, padx=2, pady=2, sticky="ew")
        ttk.Button(level, text="ЗЛ", command=lambda: self.move_level_point(5, 95)).grid(row=2, column=0, padx=2, pady=2, sticky="ew")
        ttk.Button(level, text="ЗП", command=lambda: self.move_level_point(95, 95)).grid(row=2, column=2, padx=2, pady=2, sticky="ew")

        log_frame = ttk.LabelFrame(right, text="Журнал", padding=8)
        metrics_frame = ttk.LabelFrame(right, text="USB-метрики", padding=8)
        metrics_frame.grid(row=2, column=0, sticky="nsew", pady=(10, 0))
        metrics_frame.columnconfigure(0, weight=1)
        metrics_frame.rowconfigure(1, weight=1)
        metrics_buttons = ttk.Frame(metrics_frame)
        metrics_buttons.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        ttk.Button(metrics_buttons, text="Снять все метрики", command=self.refresh_metrics).pack(side="left")
        ttk.Button(metrics_buttons, text="Выгрузить лог в проект", command=self.export_debug_log).pack(side="left", padx=(8, 0))
        self.metrics_text = ScrolledText(metrics_frame, wrap="word", height=20)
        self.metrics_text.grid(row=1, column=0, sticky="nsew")
        self.metrics_text.configure(state="disabled")

        log_frame.grid(row=3, column=0, sticky="nsew", pady=(10, 0))
        right.rowconfigure(2, weight=1)
        right.rowconfigure(3, weight=1)
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        self.log_text = ScrolledText(log_frame, wrap="word", height=26)
        self.log_text.grid(row=0, column=0, sticky="nsew")
        self.log_text.configure(state="disabled")

    def log(self, message: str) -> None:
        timestamp = time.strftime("%H:%M:%S")
        self.log_text.configure(state="normal")
        self.log_text.insert("end", f"{timestamp} {message}\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

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
            elif kind == "temp":
                current, target = payload  # type: ignore[misc]
                self.temp_var.set(f"Hotend: {current:.2f} / {target:.2f} C")
            elif kind == "sd":
                self.sd_var.set(str(payload))
            elif kind == "fw":
                self.fw_var.set(str(payload))
            elif kind == "progress":
                label, value = payload  # type: ignore[misc]
                if str(label).startswith("Upload"):
                    self.progress_bar.stop()
                    self.progress_bar.configure(mode="determinate")
                self.progress_var.set(str(label))
                self.progress_bar["value"] = float(value)
            elif kind == "busy":
                busy, label = payload  # type: ignore[misc]
                self._set_busy_ui(bool(busy), str(label))
            elif kind == "metrics":
                key, value = payload  # type: ignore[misc]
                self.metrics_sections[str(key)] = str(value).strip()
                self._render_metrics()
            elif kind == "sd-files":
                self._apply_sd_files(payload)  # type: ignore[arg-type]
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

    def _apply_sd_files(self, files: list[str]) -> None:
        self.sd_list = files
        self.sd_display_to_path = {}
        self.sd_listbox.delete(0, "end")
        if not files:
            self.sd_listbox.insert("end", "(empty)")
            return
        for entry in files:
            display = entry
            path = entry
            if " " in entry:
                display = entry
                path = entry.split()[0]
            self.sd_display_to_path[display] = path
            self.sd_listbox.insert("end", display)

    def _port(self) -> str:
        return self.port_var.get().strip()

    def _baud(self) -> int:
        return int(self.baud_var.get().strip())

    def _run_task(self, label: str, func) -> None:
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
            filetypes=[("G-code", "*.gcode *.gco *.g"), ("All files", "*.*")],
        )
        if path:
            self.local_gcode_var.set(path)
            self.dest_name_var.set(Path(path).name.upper()[:40])

    def pick_firmware(self) -> None:
        path = filedialog.askopenfilename(
            title="Выбрать прошивку",
            filetypes=[("Firmware", "*.bin"), ("All files", "*.*")],
        )
        if path:
            self.firmware_var.set(path)

    def refresh_status(self) -> None:
        def task() -> None:
            caps, sd = sdtool.preflight(self._port(), self._baud())
            fw_line = next((line for line in caps.splitlines() if line.startswith("FIRMWARE_NAME:")), "Firmware: unknown")
            self._post("fw", fw_line.replace("FIRMWARE_NAME:", "Firmware: ", 1))
            self._post("sd", sd.strip() or "SD: unknown")
            self._post("metrics", ("m115", caps))
            self._post("log", caps.strip())

        self._run_task("Проверка статуса", task)

    def refresh_metrics(self) -> None:
        def task() -> None:
            caps, sd = sdtool.preflight(self._port(), self._baud())
            m503 = sdtool.query_command(self._port(), self._baud(), "M503", wait_before_read=0.6, read_seconds=2.0)
            m114 = sdtool.query_command(self._port(), self._baud(), "M114", wait_before_read=0.3, read_seconds=1.0)
            m105 = sdtool.query_command(self._port(), self._baud(), "M105", wait_before_read=0.3, read_seconds=1.0)
            m27 = sdtool.query_command(self._port(), self._baud(), "M27", wait_before_read=0.3, read_seconds=1.0)
            fw_line = next((line for line in caps.splitlines() if line.startswith("FIRMWARE_NAME:")), "Firmware: unknown")
            self._post("fw", fw_line.replace("FIRMWARE_NAME:", "Firmware: ", 1))
            self._post("sd", sd.strip() or "SD: unknown")
            self._post("metrics", ("m115", caps))
            self._post("metrics", ("m503", m503))
            self._post("metrics", ("m114", m114))
            self._post("metrics", ("m105", m105))
            self._post("metrics", ("m27", m27))

        self._run_task("Снятие всех USB-метрик", task)

    def export_debug_log(self) -> None:
        export_dir = PROJECT_ROOT / "monitor_logs" / "gui_exports"
        export_dir.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y%m%d_%H%M%S")
        target = export_dir / f"little_hands_gui_{stamp}.log"
        log_body = self.log_text.get("1.0", "end").strip()
        metrics_body = self.metrics_text.get("1.0", "end").strip()
        sd_listing = "\n".join(self.sd_list) if self.sd_list else "(empty)"
        body = "\n".join(
            [
                f"Timestamp: {stamp}",
                f"Port: {self._port()}",
                f"Baud: {self._baud()}",
                f"Selected G-code: {self.local_gcode_var.get().strip() or '-'}",
                f"Selected firmware: {self.firmware_var.get().strip() or '-'}",
                "",
                "=== USB Metrics ===",
                metrics_body,
                "",
                "=== SD Listing ===",
                sd_listing,
                "",
                "=== GUI Log ===",
                log_body,
                "",
            ]
        )
        target.write_text(body, encoding="utf-8")
        self.log(f"Лог выгружен: {target}")

    def refresh_sd_files(self) -> None:
        def task() -> None:
            files = sdtool.list_files(self._port(), self._baud())
            self._post("sd-files", files)

        self._run_task("Чтение списка SD", task)

    def upload_gcode(self) -> None:
        source = Path(self.local_gcode_var.get().strip()).expanduser().resolve()
        if not source.is_file():
            messagebox.showerror("K9 Control Center", "Выбери существующий G-code файл.")
            return
        dest = self.dest_name_var.get().strip() or source.name
        size_mib = source.stat().st_size / (1024 * 1024)

        def task() -> None:
            last_stage = {"name": None}

            def on_progress(stage: str, percent: float) -> None:
                self._post("progress", (f"{stage}: {percent:.1f}%", percent))
                if last_stage["name"] != stage:
                    last_stage["name"] = stage
                    self._post("log", f"Этап записи: {stage}")

            self._post("log", f"Локальный файл: {source}")
            self._post("log", f"Размер файла: {size_mib:.2f} MiB. Большие G-code могут писаться 1-5 минут.")
            self._post("progress", ("Upload (preflight): 0.0%", 0.0))
            method = sdtool.upload_gcode_auto(self._port(), self._baud(), source, dest, progress_cb=on_progress)
            self._post("progress", ("Upload complete: 100.0%", 100.0))
            self._post("log", f"Залит G-code: {source.name} -> {dest} ({method})")
            files = sdtool.list_files(self._port(), self._baud())
            self._post("sd-files", files)

        self._run_task("Заливка G-code на SD", task)

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

        def task() -> None:
            sdtool.flash_firmware(self._port(), self._baud(), source, purge_bin=True)
            self._post("log", f"Прошивка залита: {source.name} -> mksLite.bin, отправлен M997")

        self._run_task("Заливка прошивки", task)

    def _selected_sd_path(self) -> str | None:
        selection = self.sd_listbox.curselection()
        if not selection:
            return None
        display = self.sd_listbox.get(selection[0])
        if display == "(empty)":
            return None
        return self.sd_display_to_path.get(display, display)

    def start_selected_print(self) -> None:
        path = self._selected_sd_path()
        if not path:
            messagebox.showerror("K9 Control Center", "Выбери файл на SD.")
            return

        def task() -> None:
            out = sdtool.start_sd_print(self._port(), self._baud(), path)
            self._post("log", out.strip() or f"Печать запущена: {path}")

        self._run_task("Запуск SD-печати", task)

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

    def stop_print(self) -> None:
        def task() -> None:
            out = sdtool.stop_sd_print(self._port(), self._baud())
            self._post("log", out.strip() or "Стоп отправлен")

        self._run_task("Остановка печати", task)

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

    def motor_off(self) -> None:
        def task() -> None:
            out = sdtool.query_command(self._port(), self._baud(), "M18", wait_before_read=0.4, read_seconds=1.0)
            self._post("log", out.strip() or "Моторы отключены")

        self._run_task("Отключение моторов", task)

    def jog_axis(self, axis: str, distance: float) -> None:
        feedrate = 1200 if axis == "Y" else 2400

        def task() -> None:
            out = sdtool.run_commands(
                self._port(),
                self._baud(),
                ["G91", f"G1 {axis}{distance:.3f} F{feedrate}", "G90"],
                final_wait=0.8,
                read_seconds=1.5,
            )
            self._post("log", out.strip() or f"{axis} {'+' if distance >= 0 else ''}{distance:g}")

        self._run_task(f"Сдвиг {axis}", task)

    def move_level_point(self, x: float, z: float) -> None:
        def task() -> None:
            out = sdtool.run_commands(
                self._port(),
                self._baud(),
                ["G90", f"G1 X{x:.2f} Z{z:.2f} F2400"],
                final_wait=0.8,
                read_seconds=1.5,
            )
            self._post("log", out.strip() or f"Переход к точке X{x:.0f} Z{z:.0f}")

        self._run_task(f"Переход к точке X{x:.0f} Z{z:.0f}", task)

    def _poll_status(self) -> None:
        if self.monitor_enabled and not self.user_task_pending and self.serial_lock.acquire(blocking=False):
            threading.Thread(target=self._poll_worker, daemon=True).start()
        self.root.after(2000, self._poll_status)

    def _poll_worker(self) -> None:
        try:
            temp = sdtool.query_command(self._port(), self._baud(), "M105", wait_before_read=0.2, read_seconds=0.8)
            match = TEMP_RE.search(temp)
            if match:
                self._post("temp", (float(match.group(1)), float(match.group(2))))
            self._post("metrics", ("m105", temp))
            sd = sdtool.query_command(self._port(), self._baud(), "M27", wait_before_read=0.3, read_seconds=0.8)
            summary = next((line.strip() for line in sd.splitlines() if line.strip()), "SD: idle")
            self._post("sd", summary)
            progress_match = SD_PROGRESS_RE.search(sd)
            if progress_match:
                done = int(progress_match.group(1))
                total = max(int(progress_match.group(2)), 1)
                pct = max(0.0, min(100.0, (done / total) * 100.0))
                self._post("progress", (f"Print: {pct:.1f}% ({done}/{total})", pct))
            elif "Not SD printing" in sd:
                self._post("progress", ("Print: idle", 0.0))
            self._post("metrics", ("m27", sd))
        except Exception:
            pass
        finally:
            self.serial_lock.release()


def main() -> int:
    root = tk.Tk()
    app = K9ControlCenter(root)
    app.log("Утилита готова. Порт должен быть свободен от Cura и других мониторов.")
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
