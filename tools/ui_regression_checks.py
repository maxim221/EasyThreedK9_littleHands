#!/usr/bin/env python3
"""Offline UI checks: xvfb-run -a python3 tools/ui_regression_checks.py."""

from contextlib import ExitStack
from pathlib import Path
import tempfile
import tkinter as tk
import unittest
from unittest.mock import Mock, patch

import k9_control_center as appmod


class OfflineUiChecks(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        tmp = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        for name in ("LOG_DIR", "GUI_EXPORT_DIR"):
            self.stack.enter_context(patch.object(appmod, name, tmp))
        for name in ("RUNTIME_LOG_PATH", "UI_STATE_PATH", "PRINT_STATE_PATH"):
            self.stack.enter_context(patch.object(appmod, name, tmp / name))
        for name in ("_load_recent_temp_history_from_log", "_restore_persistent_print_state", "_save_ui_state"):
            self.stack.enter_context(patch.object(appmod.K9ControlCenter, name))
        self.stack.enter_context(patch.object(appmod.K9ControlCenter, "_load_ui_state", return_value={}))
        # Disable scheduled polling and fail immediately if any path opens USB.
        self.stack.enter_context(patch.object(tk.Tk, "after", return_value="disabled"))
        self.stack.enter_context(patch.object(appmod.sdtool.serial, "Serial", side_effect=AssertionError("USB forbidden in UI checks")))
        self.root = tk.Tk()
        self.addCleanup(self.root.destroy)
        self.app = appmod.K9ControlCenter(self.root)
        self.root.update_idletasks()

    def test_manual_switches_language_in_place(self):
        self.app.show_manual()
        for language in ("ru", "en", "zh"):
            self.app.lang_var.set(language)
            self.app._apply_language()
            text = self.app.manual_text_widget.get("1.0", "end").strip()
            self.assertEqual(text, appmod.load_manual(language))
            self.assertIn("60", text)
            self.assertIn("180", text)
            self.assertIn("0.05", text)
            self.assertNotIn("/home/maxim", text)

    def test_heat_buttons_and_print_locks(self):
        self.app.set_hotbed_target = Mock()
        for language in ("ru", "en", "zh"):
            self.app.lang_var.set(language)
            self.app._apply_language()
            self.app.current_print_file = "-"
            self.app._sync_home_controls()
            for target in (35, 40, 50, 55, 60):
                button = getattr(self.app, f"hotbed_{target}_button")
                self.assertEqual(str(button.cget("state")), "normal")
                button.invoke()
                self.app.set_hotbed_target.assert_called_with(target)
            self.app.current_print_file = "TEST.GCO"
            self.app._sync_home_controls()
            for target in (35, 40, 50, 55, 60):
                self.assertEqual(str(getattr(self.app, f"hotbed_{target}_button").cget("state")), "disabled")
            self.assertEqual(str(self.app.hotbed_off_button.cget("state")), "normal")

    def test_language_rebuild_preserves_guards_and_widgets(self):
        self.app.show_files_firmware_window()
        count = len(self.app.action_widgets)
        for language in ("en", "zh", "ru") * 3:
            self.app.lang_var.set(language)
            self.app._apply_language()
            self.assertEqual(len(self.app.action_widgets), count)
            self.assertEqual(str(self.app.upload_and_start_button.cget("state")), "disabled")
        self.app.user_task_pending = True
        self.app._set_busy_ui(True)
        self.app.lang_var.set("en")
        self.app._apply_language()
        for button in (self.app.upload_gcode_button, self.app.upload_and_start_button,
                       self.app.flash_firmware_button, self.app.find_port_button, self.app.disconnect_port_button):
            self.assertEqual(str(button.cget("state")), "disabled")
        self.assertEqual(str(self.app.port_combo.cget("state")), "disabled")
        self.app.user_task_pending = False
        self.app._set_busy_ui(False)
        self.assertEqual(str(self.app.port_combo.cget("state")), "readonly")

    def test_busy_state_is_set_before_worker_starts(self):
        with patch.object(appmod.threading, "Thread") as thread:
            self.app._run_task("Test", lambda: None, require_port=False)
            self.assertTrue(self.app.user_task_pending)
            self.assertEqual(str(self.app.port_combo.cget("state")), "disabled")
            self.assertEqual(str(self.app.disconnect_port_button.cget("state")), "disabled")
            thread.return_value.start.assert_called_once()

    def test_close_during_operation_keeps_app_and_port(self):
        self.app.port_var.set("test-port")
        self.app.user_task_pending = True
        with patch.object(appmod.messagebox, "showinfo") as info:
            self.app._on_close()
            info.assert_called_once()
        self.assertTrue(self.root.winfo_exists())
        self.assertEqual(self.app.port_var.get(), "test-port")
        self.assertTrue(self.app.monitor_enabled)

    def test_controls_fit_supported_window_sizes(self):
        for language in ("ru", "en", "zh"):
            self.app.lang_var.set(language)
            self.app._apply_language()
            for geometry in ("1080x680+0+0", "1280x780+0+0"):
                self.root.geometry(geometry)
                self.root.update()
                self.app._init_pane_layout()
                self.root.update()
                self.app._resize_panels()
                self.root.update()
                for name in ("hotbed_60_button", "hotbed_off_button", "level_back_right_button",
                             "stop_button", "start_print_button", "capture_metrics_button", "save_log_button"):
                    widget = getattr(self.app, name)
                    self.assertTrue(widget.winfo_ismapped(), (language, geometry, name))
                    x, y = widget.winfo_rootx(), widget.winfo_rooty()
                    right, bottom = x + widget.winfo_width(), y + widget.winfo_height()
                    parent = widget.master
                    while parent is not None:
                        bounds = (parent.winfo_rootx(), parent.winfo_rooty(),
                                  parent.winfo_rootx() + parent.winfo_width(),
                                  parent.winfo_rooty() + parent.winfo_height())
                        self.assertTrue(x >= bounds[0] and y >= bounds[1] and right <= bounds[2] and bottom <= bounds[3],
                                        (language, geometry, name, bounds, (x, y, right, bottom)))
                        parent = parent.master


if __name__ == "__main__":
    unittest.main()
