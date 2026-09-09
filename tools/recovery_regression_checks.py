"""Offline recovery checks; never open a physical serial port."""
import copy
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

import k9_control_center as appmod
import k9_recovery as recovery


class RecoveryChecks(unittest.TestCase):
    def setUp(self):
        self.paused = {"confirmed": True, "file": "TEST.GCO", "byte": 120, "total": 1000,
                       "xyz": [41.3, 59.39, 0.36], "temperature": [224, 224, 60, 60, 60, 127]}
        self.commands = []

    def reply(self, ser, command, **kwargs):
        self.commands.append(command)
        return {"M105": "ok T:224 /224 B:60 /60 @:60 B@:127\n",
                "M27 C": "Current file: /TEST.GCO\nok\n",
                "M27": "SD printing byte 120/1000\nok\n",
                "M114": "X:41.30 Y:59.39 Z:0.36 E:507.95\nok\n"}.get(command, "ok\n")

    def test_progress_parser_refuses_missing_and_invalid_reports(self):
        for raw in ("", "SD: printing", "SD printing byte 50/0", "SD printing byte 1001/1000"):
            self.assertIsNone(recovery.sd_progress(raw))
        self.assertEqual(recovery.sd_progress("SD printing byte 1/1000\nSD printing byte 2/1000\nok\n"), (2, 1000))

    def test_samples_keep_real_times_and_raw_axes(self):
        record = {}
        recovery.observe(record, "sd", "SD printing byte 120/1000", timestamp=10)
        recovery.observe(record, "position", "X:41.3 Y:59.39 Z:0.36", timestamp=12)
        self.assertFalse(recovery.observe(record, "sd", "SD: state unknown", timestamp=20))
        self.assertEqual(record["samples"]["sd"]["captured_ts"], 10)
        self.assertEqual(record["samples"]["position"]["xyz"], [41.3, 59.39, 0.36])
        with self.assertRaises(recovery.RecoveryError):
            recovery.validate_resume(record, self.paused)

    def test_resume_blocks_changed_or_incomplete_state(self):
        recovery.validate_resume(self.paused, copy.deepcopy(self.paused))
        changes = [dict(file="OTHER.GCO"), dict(byte=121), dict(total=1001),
                   dict(xyz=[41.3, 59.39, 10.36]), dict(xyz=[41.3]),
                   dict(xyz=[float("nan"), 59.39, 0.36]),
                   dict(temperature=[25, 224, 127, 60, 60, 127]),
                   dict(temperature=[224, 0, 0, 60, 60, 127]),
                   dict(temperature=[224, 224, 60, 55, 60, 127]),
                   dict(temperature=[224, 224, 60, 60, 0, 0]),
                   dict(temperature=[224, 224, 60, 70, 70, 127]),
                   dict(temperature=[224, 224, 60, float("nan"), 60, 127])]
        for change in changes:
            with self.subTest(change=change), self.assertRaises(recovery.RecoveryError):
                recovery.validate_resume(self.paused, {**self.paused, **change})
        for pause in ({}, {**self.paused, "confirmed": False}, {**self.paused, "byte": 0},
                      {**self.paused, "byte": 1000}):
            with self.assertRaises(recovery.RecoveryError):
                recovery.validate_resume(pause, self.paused)

    def test_external_warm_mat_needs_no_firmware_bed_sensor(self):
        no_bed = {**self.paused, "temperature": [224, 224, 60, None, None, None], "expected_hotbed_target": 0}
        recovery.validate_resume(no_bed, no_bed)
        controlled_bed = {**no_bed, "expected_hotbed_target": 60}
        with self.assertRaises(recovery.RecoveryError):
            recovery.validate_resume(controlled_bed, no_bed)

    def test_restored_corrupt_or_expired_pause_cannot_enable_resume(self):
        pause = {**self.paused, "captured_ts": time.time()}
        record = {"file": "TEST.GCO", "pause": pause, "samples": []}
        self.assertTrue(recovery.restore_record(record)["pause"]["confirmed"])
        for bad in ([], "yes", {**pause, "captured_ts": 1}, {**pause, "file": "OTHER.GCO"},
                    {**pause, "confirmed": "yes"}, {**pause, "xyz": [float("nan"), 0, 0]}):
            self.assertNotIn("pause", recovery.restore_record({**record, "pause": bad}))

    def test_capture_pause_waits_for_motion_after_pause(self):
        with patch.object(recovery.sdtool, "open_serial"), patch.object(recovery.sdtool, "send_line_wait_ok", side_effect=self.reply):
            paused = recovery.capture_pause("fake", 115200, "TEST.GCO", appmod.parse_m105_temperatures)
        self.assertTrue(paused["confirmed"])
        self.assertEqual(self.commands[:3], ["M27 C", "M25", "M400"])
        self.assertEqual(paused["xyz"], self.paused["xyz"])

    def test_unconfirmed_pause_is_not_saved(self):
        def fail(ser, command, **kwargs):
            if command == "M400":
                raise RuntimeError("No acknowledgement")
            return self.reply(ser, command, **kwargs)
        with patch.object(recovery.sdtool, "open_serial"), patch.object(recovery.sdtool, "send_line_wait_ok", side_effect=fail):
            with self.assertRaises(RuntimeError):
                recovery.capture_pause("fake", 115200, "TEST.GCO", appmod.parse_m105_temperatures)
        self.assertNotIn("M24", self.commands)

    def test_resume_is_consumed_before_m24_and_never_reselects_file(self):
        def consumed():
            self.assertNotIn("M24", self.commands)
            self.commands.append("persist-consumed")
        with patch.object(recovery.sdtool, "open_serial"), patch.object(recovery.sdtool, "send_line_wait_ok", side_effect=self.reply):
            recovery.resume_retained_pause("fake", 115200, self.paused, appmod.parse_m105_temperatures, consumed)
        self.assertEqual(self.commands[-2:], ["persist-consumed", "M24"])
        self.assertTrue(all(c in {"M105", "M27 C", "M27", "M114", "persist-consumed", "M24"} for c in self.commands))

    def test_write_failure_or_progress_change_prevents_m24(self):
        for mode in ("write_failure", "progress_changed"):
            self.commands = []
            def reply(ser, command, **kwargs):
                result = self.reply(ser, command, **kwargs)
                if mode == "progress_changed" and command == "M27" and self.commands.count("M27") > 1:
                    return "SD printing byte 121/1000\nok\n"
                return result
            consume = Mock(side_effect=OSError("disk full"))
            with patch.object(recovery.sdtool, "open_serial"), patch.object(recovery.sdtool, "send_line_wait_ok", side_effect=reply):
                with self.assertRaises((OSError, recovery.RecoveryError)):
                    recovery.resume_retained_pause("fake", 115200, self.paused, appmod.parse_m105_temperatures, consume)
            self.assertNotIn("M24", self.commands)

    def test_m24_timeout_still_consumes_pause_exactly_once(self):
        def reply(ser, command, **kwargs):
            result = self.reply(ser, command, **kwargs)
            if command == "M24":
                raise RuntimeError("USB reply lost after write")
            return result
        consumed = Mock()
        with patch.object(recovery.sdtool, "open_serial"), patch.object(recovery.sdtool, "send_line_wait_ok", side_effect=reply):
            with self.assertRaises(RuntimeError):
                recovery.resume_retained_pause("fake", 115200, self.paused, appmod.parse_m105_temperatures, consumed)
        consumed.assert_called_once()
        self.assertEqual(self.commands.count("M24"), 1)

    def test_atomic_failure_keeps_previous_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            recovery.atomic_json(path, {"old": True})
            with patch.object(recovery.os, "replace", side_effect=OSError("disk full")):
                with self.assertRaises(OSError):
                    recovery.atomic_json(path, {"new": True})
            self.assertEqual(json.loads(path.read_text()), {"old": True})
            self.assertEqual(list(Path(tmp).iterdir()), [path])

    def test_stop_attempts_both_heaters_after_failed_acknowledgement(self):
        commands = []
        def fail(ser, command, **kwargs):
            commands.append(command)
            raise RuntimeError("No acknowledgement")
        with patch.object(recovery.sdtool, "open_serial"), \
             patch.object(recovery.sdtool, "sync_ascii"), \
             patch.object(recovery.sdtool, "send_line"), \
             patch.object(recovery.sdtool, "read_for", return_value=""), \
             patch.object(recovery.sdtool.time, "sleep"), \
             patch.object(recovery.sdtool, "send_line_wait_ok", side_effect=fail):
            reply, pose = recovery.sdtool.stop_sd_print_with_position("fake", 115200)
        self.assertIsNone(pose)
        self.assertIn("M104 S0", commands)
        self.assertIn("M140 S0", commands)
        self.assertIn(";LH_STOP_CONFIRMED:0", reply)
        self.assertFalse(any(c.startswith("G") for c in commands))

    def test_rejected_or_corrupt_reply_is_not_acknowledged_by_trailing_ok(self):
        bad = [b'echo:Unknown command: "M104 S0"\nok\n',
               b'echo:Unknown command: "\xffM108"\nok\n',
               b'\xff\nok\n', b'\x0e\nok\n',
               b'echo: token received\n', b'echo: ok\n',
               b'Error: heater halted\nok\n', b'Resend: 10\nok\n']
        for raw in bad:
            lines = iter(raw.splitlines(keepends=True))
            ser = Mock()
            ser.readline.side_effect = lambda: next(lines, b'')
            with self.subTest(reply=raw), self.assertRaises(RuntimeError):
                recovery.sdtool.send_line_wait_ok(ser, 'M104 S0', timeout_s=.01)

    def test_real_ack_and_complete_m114_position_remain_supported(self):
        for command, raw in [('M104 S0', b'ok\n'),
                             ('M400', b'ok N12 P15 B3\n'),
                             ('M105', b'ok T:41.23 /0.00 B:55.16 /0.00 @:0 B@:0\n'),
                             ('M114', b'X:0.00 Y:0.00 Z:10.00 E:0.00\n')]:
            lines = iter(raw.splitlines(keepends=True))
            ser = Mock()
            ser.readline.side_effect = lambda: next(lines, b'')
            with self.subTest(command=command):
                self.assertEqual(recovery.sdtool.send_line_wait_ok(ser, command, timeout_s=.01), raw.decode())
        ser = Mock()
        lines = iter([b'X:0.00\n'])
        ser.readline.side_effect = lambda: next(lines, b'')
        with self.assertRaises(RuntimeError):
            recovery.sdtool.send_line_wait_ok(ser, 'M114', timeout_s=.01)

    def test_rejected_mode_command_prevents_following_service_move(self):
        ser = Mock()
        lines = iter([b'echo:Unknown command: "G90"\n', b'ok\n'])
        ser.readline.side_effect = lambda: next(lines, b'')
        with patch.object(recovery.sdtool, 'open_serial') as opened, \
             patch.object(recovery.sdtool, 'sync_ascii'):
            opened.return_value.__enter__.return_value = ser
            with self.assertRaises(RuntimeError):
                recovery.sdtool.run_commands_wait_ok('fake', 115200, ['G90', 'G1 Z0 F600'])
        self.assertEqual([call.args[0] for call in ser.write.call_args_list], [b'G90\n'])


if __name__ == "__main__":
    unittest.main()
