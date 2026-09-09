#!/usr/bin/env python3
"""Offline UI checks: xvfb-run -a python3 tools/ui_regression_checks.py."""

from contextlib import ExitStack
from pathlib import Path
import tempfile
import time
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

    def test_preheat_cancel_stays_available_in_every_language(self):
        self.app.user_task_pending = True
        self.app.preheat_active = True
        self.app._run_task = Mock()
        for language in ('ru', 'en', 'zh'):
            self.app.preheat_cancel_requested.clear()
            self.app.lang_var.set(language)
            self.app._apply_language()
            self.app._set_busy_ui(True)
            self.assertEqual(str(self.app.stop_button.cget('state')), 'normal')
            self.assertEqual(self.app.stop_button.cget('text'), self.app._t('cancel_preheat'))
            for geometry in ('1080x680+0+0', '1280x780+0+0'):
                self.root.geometry(geometry)
                self.root.update()
                self.app._init_pane_layout()
                self.root.update()
                self.app._resize_panels()
                self.root.update()
                button = self.app.stop_button
                font = appmod.tkfont.Font(font=appmod.ttk.Style().lookup(button.cget('style') or 'TButton', 'font'))
                self.assertLessEqual(font.measure(button.cget('text')) + 8, button.winfo_width())
                self.assertLessEqual(button.winfo_rooty() + button.winfo_height(), self.root.winfo_rooty()+self.root.winfo_height())
            for button in (self.app.head_down_button, self.app.find_port_button, self.app.disconnect_port_button):
                self.assertEqual(str(button.cget('state')), 'disabled')
            self.app.stop_button.invoke()
            self.assertTrue(self.app.preheat_cancel_requested.is_set())
            self.assertEqual(str(self.app.stop_button.cget('state')), 'disabled')
        self.app._run_task.assert_not_called()

    def test_close_during_preheat_waits_for_verified_shutdown(self):
        for verified in (False, True):
            self.app.user_task_pending = True
            self.app.preheat_active = True
            self.app.preheat_cancel_requested.clear()
            with patch.object(self.root, 'destroy') as destroy, patch.object(appmod.messagebox, 'showinfo') as info:
                self.app._on_close()
                self.assertTrue(self.app.preheat_cancel_requested.is_set())
                self.assertTrue(self.app.close_after_preheat)
                destroy.assert_not_called()
                info.assert_not_called()
                self.app.preheat_active = False
                self.app.preheat_cleanup_confirmed = verified
                self.app.user_task_pending = False
                self.app._post('preheat-task-finished', None)
                self.app._drain_events()
                self.assertEqual(destroy.called, verified)

    def test_save_start_cannot_silently_discard_a_failed_lift(self):
        self.app.preheat_lift_recovery_available = True
        self.app._run_task = Mock()
        with patch.object(appmod.messagebox, 'askyesno', return_value=False) as question:
            self.app.set_current_home_zero()
        self.app._run_task.assert_not_called()
        self.assertTrue(self.app.preheat_lift_recovery_available)
        self.assertEqual(question.call_args.kwargs['default'], appmod.messagebox.NO)
        with patch.object(appmod.messagebox, 'askyesno', return_value=True):
            self.app.set_current_home_zero()
        self.app._run_task.assert_called_once()
        # The worker must finish successfully before discarding the marker.
        self.assertTrue(self.app.preheat_lift_recovery_available)

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

    def test_derived_sd_status_does_not_refresh_sample_time(self):
        self.app.last_sd_sample_ts = 123.0
        self.app._post("sd", "SD: state unknown")
        self.app._drain_events()
        self.assertEqual(self.app.last_sd_sample_ts, 123.0)
        self.app._post("sd-reply", "SD printing byte 120/1000")
        self.app._drain_events()
        self.assertGreater(self.app.last_sd_sample_ts, 123.0)

    def test_freshness_covers_poll_interval_but_not_a_failed_reply(self):
        self.app._port = lambda: "fake"
        self.app.last_temp_current = 224.0
        self.app.last_temp_target = 224.0
        self.app.last_temp_sample_ts = time.time() - 8
        self.app._refresh_header_from_cache()
        self.assertIn("224.00", self.app.temp_var.get())
        self.app.usb_silence_since = time.time()
        self.app._refresh_header_from_cache()
        self.assertIn("?", self.app.temp_var.get())

    def test_resume_without_confirmed_pause_never_touches_printer(self):
        self.app.recovery_record = {"file": "TEST.GCO", "samples": {"sd": {"byte": 120, "total": 1000}}}
        self.app.show_recovery = Mock()
        with patch.object(appmod.messagebox, "showinfo"), patch.object(appmod.recovery, "resume_retained_pause") as resume:
            self.app.resume_print()
        resume.assert_not_called()

    def test_resume_after_disconnect_requires_operator_confirmation(self):
        self.app.recovery_record = {"file": "TEST.GCO", "pause": {"confirmed": True}}
        self.app.pause_session_continuous = False
        with patch.object(appmod.messagebox, "askyesno", return_value=False) as confirm, \
             patch.object(appmod.recovery, "resume_retained_pause") as resume:
            self.app.resume_print()
        confirm.assert_called_once()
        resume.assert_not_called()

    def test_recovery_view_switches_language_without_serial_access(self):
        self.app.recovery_record = {"file": "TEST.GCO", "samples": {}}
        self.app.show_recovery()
        for lang in ("en", "zh", "ru"):
            self.app.lang_var.set(lang)
            self.app._apply_language()
            self.assertEqual(self.app.recovery_window.title(), self.app._recovery_text("title"))
            self.assertIn(self.app._recovery_text("no_pause"), self.app._recovery_report())
            self.root.update()
            row = self.app.recovery_window.winfo_children()[-1]
            for button in row.winfo_children():
                self.assertTrue(button.winfo_ismapped())
                self.assertLessEqual(button.winfo_rooty() + button.winfo_height(),
                                     self.app.recovery_window.winfo_rooty() + self.app.recovery_window.winfo_height())

    def test_poll_reuses_one_port_and_saves_individual_samples(self):
        self.app._port = lambda: "fake"
        self.app.current_print_file = "TEST.GCO"
        self.app.current_print_start_ts = time.time() - 1000
        self.app.print_was_active = True
        self.app.last_fw_line = "Known firmware"
        self.app.serial_lock.acquire()
        ser = Mock()
        replies = ["ok T:224 /224 B:60 /60 @:60 B@:127\n", "SD printing byte 120/1000\nok\n", "X:41.3 Y:59.39 Z:0.36\nok\n"]
        with patch.object(appmod.sdtool, "open_serial", return_value=ser) as opened, \
             patch.object(appmod.sdtool, "send_line") as send, \
             patch.object(appmod.sdtool, "read_for", side_effect=replies), patch.object(appmod.time, "sleep"):
            self.app._poll_worker()
        opened.assert_called_once()
        ser.close.assert_called_once()
        self.assertEqual([c.args[1] for c in send.call_args_list], ["M105", "M27", "M114"])
        samples = self.app.recovery_record["samples"]
        self.assertEqual(samples["sd"]["byte"], 120)
        self.assertEqual(samples["position"]["xyz"], [41.3, 59.39, 0.36])
        self.assertIn("temperature", samples)
        self.assertGreater(self.app.next_poll_ts, time.time() + 3)

    def test_silent_poll_keeps_evidence_and_invalidates_live_session(self):
        self.app._port = lambda: "fake"
        self.app.current_print_file = "TEST.GCO"
        self.app.current_print_start_ts = time.time() - 1000
        self.app.print_was_active = True
        self.app.usb_silence_since = time.time() - 20
        self.app.recovery_record = {"file": "TEST.GCO", "samples": {"sd": {"byte": 120, "captured_ts": 123.0}}}
        self.app.serial_lock.acquire()
        with patch.object(appmod.sdtool, "open_serial"), patch.object(appmod.sdtool, "send_line") as send, \
             patch.object(appmod.sdtool, "read_for", return_value=""), patch.object(appmod.time, "sleep"):
            self.app._poll_worker()
        self.assertEqual([c.args[1] for c in send.call_args_list], ["M105"])
        self.assertEqual(self.app.recovery_record["samples"]["sd"]["captured_ts"], 123.0)
        self.assertTrue(self.app.print_state_restored_from_log)
        self.assertFalse(self.app._can_run_automatic_completion_sequence()[0])
        self.assertGreater(self.app.next_poll_ts, time.time() + 14)

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
                             "stop_button", "start_print_button", "capture_metrics_button", "recovery_button", "save_log_button"):
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
