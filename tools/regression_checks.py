#!/usr/bin/env python3
"""Lightweight regression checks for the validated Little Hands K9 workflow."""

from __future__ import annotations

import re
import sys
from pathlib import Path

import k9_control_center as appmod
import k9_marlin_sd as sdtool


ROOT = Path(__file__).resolve().parents[1]


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8", errors="replace")


def require(condition: bool, message: str, failures: list[str]) -> None:
    if not condition:
        failures.append(message)


def require_regex(text: str, pattern: str, message: str, failures: list[str]) -> None:
    require(re.search(pattern, text, re.MULTILINE | re.DOTALL) is not None, message, failures)


def main() -> int:
    failures: list[str] = []
    marlin = read("tools/k9_marlin_sd.py")
    app = read("tools/k9_control_center.py")
    slicer = read("tools/k9_cura_slice.py")
    cura_quality = read("docs/cura/quality_changes/codex_k9_warmmat_quality.inst.cfg")
    cura_extruder = read("docs/cura/quality_changes/codex_k9_warmmat_extruder_quality.inst.cfg")
    cura_machine = read("docs/cura/definition_changes/lilHands_k9_warmmat_settings.inst.cfg")

    require("SOFT_TRAVEL_ACCEL = 80" in marlin, "K9 service travel acceleration must remain M204 T80.", failures)
    require(
        "RESTORE_TRAVEL_ACCEL = SOFT_TRAVEL_ACCEL" in marlin,
        "Service moves must not restore aggressive M204 T1000.",
        failures,
    )
    require("SAFE_BED_FEEDRATE = 240" in marlin, "Long bed service/recovery feedrate must remain F240.", failures)
    require("SAFE_X_FEEDRATE = 900" in marlin, "Head X service feedrate must remain F900.", failures)
    require("SAFE_HOME_CLEARANCE_Z = 10.0" in marlin, "Recovery/preheat clearance must keep a 10 mm Z lift.", failures)
    require('"M204 T1000"' not in marlin, "k9_marlin_sd.py must not hard-code M204 T1000.", failures)
    require('"M204 T1000"' not in app, "k9_control_center.py must not hard-code M204 T1000.", failures)
    require("JOG_RESTORE_TRAVEL_ACCEL = 80" in app, "Manual jog must leave service travel acceleration at T80.", failures)
    require("SERVICE_BED_FEEDRATE = 240" in app, "App long bed service moves must remain F240.", failures)
    require("JOG_BED_FEEDRATE = 600" in app, "App manual bed jog must match the validated manual F600 test.", failures)
    require("BED_JOG_SEGMENT_MM" not in app, "Manual bed jog must honor the selected UI step as a single move.", failures)
    require("MAX_MANUAL_BED_JOG_MM" not in app, "Manual bed jog must not be capped; the UI step should be honored.", failures)
    require("BED_RAW_MIN_MM" not in app and "BED_RAW_MAX_MM" not in app, "Raw Y must not be treated as a physical bed-edge guard without homing.", failures)
    require('"Y": JOG_BED_FEEDRATE' in app, "Manual bed jog must use the named conservative bed feedrate.", failures)
    require('"Y": 80' in app, "Manual bed jog acceleration must match the validated manual M204 P80 T80 test.", failures)
    require("M204 P{travel_accel} T{travel_accel}" in app, "Manual jog must soften both print and travel acceleration.", failures)
    require('commands.extend([f"G1 {axis}{distance:.3f} F{feedrate}", "M400"])' in app, "Manual jog must send the selected UI step as one waited move.", failures)
    require("Bed jog context: raw Y=" not in app, "Manual bed jog must not open a separate M114 query before movement.", failures)
    require("HOME_TRUST_TRUSTED" in app and "HOME_TRUST_UNCERTAIN" in app, "Home trust state machine is missing.", failures)
    require("_home_is_trusted()" in app, "Home-sensitive actions must use the explicit home trust guard.", failures)

    require("run_commands_wait_ok" in marlin, "Long service moves must use the ok-waiting command helper.", failures)
    require_regex(
        marlin,
        r"def goto_print_home\(.*?return run_commands_wait_ok",
        "Go-to-start must wait for service moves to complete.",
        failures,
    )
    require_regex(
        marlin,
        r"def goto_print_home_from_predicted_end\(.*?return run_commands_wait_ok",
        "Predicted/post-print recovery must wait for service moves to complete.",
        failures,
    )
    require("send_line_wait_ok" in marlin, "Start-from-home serial service moves must wait for ok.", failures)
    require("lift_from_saved_start_for_preheat" in marlin, "Start workflow must be able to lift from Z0 before preheat.", failures)
    require(
        "def return_from_preheat_lift" in marlin
        and f"G1 Z-{{SAFE_HOME_CLEARANCE_Z:g}} F{{SAFE_VERTICAL_FEEDRATE}}" in marlin,
        "Failed-preheat recovery must undo the known lift with a relative Z move, not trust logical Z0.",
        failures,
    )
    require("_lift_from_saved_start_for_preheat_if_needed" in app, "App must lift from saved Z0 before long SD preheat.", failures)
    require(
        "sdtool.start_sd_print(" not in app,
        "GUI SD-start paths must not bypass start_sd_print_from_home after a preheat clearance lift.",
        failures,
    )
    require(
        "_preheat_hotend_for_sd_start_with_clearance" in app
        and "_return_to_saved_start_after_failed_preheat" in app,
        "Failed hotend preheat after a clearance lift must return to saved start.",
        failures,
    )
    require(
        "sdtool.return_from_preheat_lift" in app
        and "тем же относительным ходом" in app,
        "Failed preheat after a clearance lift must return by undoing the known relative lift.",
        failures,
    )
    require(
        "PRINT_PREHEAT_NO_RISE_GRACE_SEC = 75.0" in app
        and "PRINT_PREHEAT_MIN_RISE_C = 8.0" in app
        and "per_command_timeout=12.0" in app,
        "Failed preheat must abort quickly and must not hang for long if Marlin stops acknowledging recovery commands.",
        failures,
    )
    require(
        app.count("_preheat_hotend_for_sd_start_with_clearance(target)") >= 3,
        "Every GUI SD-start path must use the clearance-aware preheat wrapper.",
        failures,
    )
    require_regex(
        marlin,
        r"def _start_sd_print_from_home_once\(.*?send_line_wait_ok",
        "Start-from-home movement must wait for each move before selecting and starting SD print.",
        failures,
    )
    require("sdtool.run_commands_wait_ok" in app, "App jog/level service moves must use ok-waiting serial commands.", failures)
    require(
        "elif self._can_return_from_known_post_print_pose() and not self._home_is_trusted():" in app,
        "Post-print M114 recovery must not override a still-trusted live session zero.",
        failures,
    )
    require(
        'sdtool.run_commands(self._port(), self._baud(), ["G90", "G28"]' not in app,
        "The app must not send G28 for this no-endstop K9 workflow.",
        failures,
    )

    start_match = re.search(r'start_gcode = """(.*?)"""', slicer, re.DOTALL)
    end_match = re.search(r'end_gcode = """(.*?)"""', slicer, re.DOTALL)
    emitted_gcode = "\n".join(match.group(1) for match in (start_match, end_match) if match)
    require("G92 X0 Y0 Z0" in emitted_gcode, "Generated start G-code must keep manual-zero G92.", failures)
    require(re.search(r"^\s*G28\b", emitted_gcode, re.MULTILINE) is None, "Slicing helper must not emit G28.", failures)
    require("M204 P250 T120" in slicer, "End G-code must start with gentle presentation M204.", failures)
    require("G1 X95 F900" in slicer, "End G-code must keep gentle X presentation move.", failures)
    require("G1 Y95 F240" in slicer, "End G-code must present bed toward the operator at F240.", failures)
    require("M84" not in slicer and "M18" not in slicer, "Slicing helper must not disable steppers at print end.", failures)

    require("is_unvalidated_modulebot_stl" in slicer, "Raw moduleBot STL orientation guard is missing.", failures)
    require(
        "--allow-unvalidated-modulebot-orientation" in slicer,
        "moduleBot raw-orientation override flag is missing.",
        failures,
    )
    require("filament_m > 15.0" in app and "moduleBot" in app, "moduleBot support-heavy G-code guard is missing.", failures)
    require("_can_run_automatic_completion_sequence" in app, "Automatic post-print movement safety guard is missing.", failures)
    require("if self.print_state_restored_from_log:" in app, "Restored print state must block automatic completion moves.", failures)
    require("completion_sequence_allowed" in app and "_run_printer_completion_sequence().strip()" in app, "Completion moves must be explicitly guarded.", failures)
    require(
        "stopped_print_live_return_available" in app and "_confirm_live_stopped_session_return" in app,
        "Stopped-print recovery must offer a guarded live-session return when M114 was not captured.",
        failures,
    )
    require(
        "_can_recover_stale_active_marker_from_predicted_end" in app
        and "ACTIVE_PRINT_RECENT_PROGRESS_BLOCK_SEC" in app,
        "Go-to-start must offer guarded predicted-end recovery for stale active-print markers after USB loss.",
        failures,
    )
    require(
        "_select_single_safe_printer_port_for_recovery" in app
        and "Recovery автоматически переключил порт принтера" in app,
        "Go-to-start recovery must auto-switch to the single safe CH340/ACM printer port after USB re-enumeration.",
        failures,
    )
    require(
        "restore_active_print_marker = False" in app
        and "stale active print marker restored as predicted print-end recovery" in app,
        "Persistent restore must keep valid predicted print-end recovery even when active-print state is stale.",
        failures,
    )
    require(
        "keep_predicted_print_end_for_recovery" in app
        and "Сохраняю predicted print-end" in app,
        "Completion handling must keep predicted print-end recovery when final M114 was not captured.",
        failures,
    )
    require(
        "confirm_print_finished_by_operator" in app
        and "PRINT_END_CONFIRMED_BY_OPERATOR" in app
        and "operator confirmed SD print finished; use saved predicted print-end recovery" in app,
        "The UI must let the operator confirm normal completion after USB loss and keep the predicted print-end recovery pose.",
        failures,
    )
    require(
        "operator-confirmed completion restored as predicted print-end recovery" in app,
        "Operator-confirmed predicted print-end recovery must survive app restart.",
        failures,
    )
    require(
        appmod.should_offer_stale_predicted_end_recovery(
            current_print_file="LIFTERAM.GCO",
            bed_clear_required=True,
            home_trusted=False,
            port_ready=True,
            predicted_valid=True,
            predicted_file="LIFTERAM.GCO",
            predicted_contract=appmod.PRINT_END_CONTRACT,
            predicted_end_z=19.0,
            recent_active_progress=False,
        ),
        "Stale LIFTERAM active marker must choose predicted-end recovery, not block Go to start.",
        failures,
    )
    require(
        not appmod.should_offer_stale_predicted_end_recovery(
            current_print_file="LIFTERAM.GCO",
            bed_clear_required=True,
            home_trusted=False,
            port_ready=True,
            predicted_valid=True,
            predicted_file="LIFTERAM.GCO",
            predicted_contract=appmod.PRINT_END_CONTRACT,
            predicted_end_z=19.0,
            recent_active_progress=True,
        ),
        "Fresh SD progress must still block predicted-end recovery during active printing.",
        failures,
    )
    require(
        not appmod.should_offer_stale_predicted_end_recovery(
            current_print_file="OTHER.GCO",
            bed_clear_required=True,
            home_trusted=False,
            port_ready=True,
            predicted_valid=True,
            predicted_file="LIFTERAM.GCO",
            predicted_contract=appmod.PRINT_END_CONTRACT,
            predicted_end_z=19.0,
            recent_active_progress=False,
        ),
        "Predicted-end recovery must not run for a mismatched active SD file marker.",
        failures,
    )
    require(
        appmod.should_keep_predicted_end_for_stale_active_restore(
            phase="printing",
            updated_ts=1000.0,
            now_ts=1000.0 + appmod.PRINT_STATE_ACTIVE_RESTORE_MAX_AGE_SEC + 1.0,
            predicted={
                "valid": True,
                "file": "LIFTERAM.GCO",
                "contract": appmod.PRINT_END_CONTRACT,
                "end_x": 95.0,
                "end_y": 95.0,
                "end_z": 19.0,
            },
        ),
        "Persistent restore must keep valid predicted print-end after stale active-print timeout.",
        failures,
    )
    require("PRINT_STOP file=" in app and "live_return=" in app, "Stopped-print events must be recorded in the runtime log.", failures)
    require(
        "_update_stopped_print_pose_after_jog" in app and "stopped-jog-updated" in app,
        "Manual jog after Stop must update, not erase, the stopped-print recovery pose.",
        failures,
    )
    require(
        "LH controlled stop lift to Z" in marlin,
        "Normal Stop must try to create a controlled post-stop recovery height.",
        failures,
    )

    require("brim_width = 14" in cura_quality, "Tracked Cura baseline must keep 14 mm brim.", failures)
    require("bottom_layers = 7" in cura_quality and "top_layers = 7" in cura_quality, "Tracked Cura baseline must keep 7 top/bottom layers.", failures)
    require("support_enable = True" in cura_quality, "Tracked Cura baseline must keep supports enabled.", failures)
    require("speed_print = 11" in cura_quality and '"speed_print": "11"' in slicer, "Tracked Cura baseline must keep the 30% slower print speed.", failures)
    require("speed_wall = 8" in cura_quality and '"speed_wall": "8"' in slicer, "Tracked Cura baseline must keep the slower wall speed.", failures)
    require("speed_travel = 25" in cura_quality and '"speed_travel": "25"' in slicer, "Tracked Cura baseline must keep the slower travel speed.", failures)
    require("speed_layer_0 = 6" in cura_quality and '"speed_layer_0": "6"' in slicer, "Tracked Cura baseline must keep practical first-layer speed.", failures)
    require("skirt_brim_speed = 21" in cura_quality and '"skirt_brim_speed": "21"' in slicer, "Tracked Cura baseline must keep practical 30% slower skirt/brim movement.", failures)
    require("initial_layer_line_width_factor = 155" in cura_extruder, "Initial layer width must remain 155%.", failures)
    require("material_print_temperature_layer_0 = 226" in cura_extruder, "First-layer PLA target must remain 226C.", failures)
    require("bridge_skin_speed = 7" in cura_extruder and "bridge_wall_speed = 7" in cura_extruder, "Bridge speeds must remain reduced for the small K9 mechanics.", failures)
    require("cool_fan_enabled = False" in cura_extruder, "K9 part-cooling must remain disabled.", failures)
    require("G1 Y95 F240" in cura_machine, "Tracked Cura machine end G-code must present bed toward operator at F240.", failures)
    require("M84" not in cura_machine and "M18" not in cura_machine, "Tracked Cura machine end G-code must not disable steppers.", failures)

    stopped_sample = (
        "echo:busy: processing\n"
        "X:74.35 Y:73.43 Z:0.36 E:522.14 Count X:42025 Y:-51248 Z:-384\n"
        "echo:busy: processing\n"
        "X:0.00 Y:0.00 Z:5.00 E:522.16 Count X:0 Y:0 Z:2400\n"
    )
    require(
        sdtool.parse_stopped_print_position(stopped_sample) == (74.35, 73.43, 5.0),
        "Stopped-print recovery must keep interrupted X/Y and lifted post-stop Z.",
        failures,
    )
    require(sdtool._stop_recovery_z(0.2) == 10.0, "Low stopped prints must lift to a 10 mm recovery height.", failures)
    require(sdtool._stop_recovery_z(94.0) == 95.0, "High stopped prints must not plan recovery above the K9 Z limit.", failures)

    if failures:
        print("Regression checks failed:")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("Regression checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
