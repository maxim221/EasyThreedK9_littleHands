#!/usr/bin/env python3
"""
Slice STL files with the validated Little Hands K9 warm-mat Cura profile.

This helper intentionally uses the UltiMaker Cura 5.11 AppImage, then runs the
bundled CuraEngine directly.  It reproduces the profile we validated for the
EasyThreeD K9 manual-zero workflow and refuses to copy unsafe out-of-bounds
G-code to an SD card.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import shutil
import struct
import subprocess
import sys
import time
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_APPIMAGE = Path("~/Applications/UltiMaker-Cura-5.11.0-linux-X64.AppImage").expanduser()
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "exports"


def parse_binary_stl_bounds(path: Path) -> tuple[float, float, float, float, float, float]:
    data = path.read_bytes()
    if len(data) < 84:
        raise ValueError(f"STL is too small: {path}")
    triangle_count = struct.unpack_from("<I", data, 80)[0]
    expected_size = 84 + triangle_count * 50
    if expected_size > len(data):
        raise ValueError(f"Only binary STL is supported by this helper: {path}")

    xs: list[float] = []
    ys: list[float] = []
    zs: list[float] = []
    offset = 84
    for _ in range(triangle_count):
        values = struct.unpack_from("<12fH", data, offset)
        points = values[3:12]
        for idx in range(0, 9, 3):
            xs.append(points[idx])
            ys.append(points[idx + 1])
            zs.append(points[idx + 2])
        offset += 50

    return min(xs), max(xs), min(ys), max(ys), min(zs), max(zs)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def mount_appimage(appimage: Path) -> tuple[Path, subprocess.Popen[str]]:
    proc = subprocess.Popen(
        [str(appimage), "--appimage-mount"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert proc.stdout is not None
    mount_line = proc.stdout.readline().strip()
    if not mount_line:
        stderr = proc.stderr.read() if proc.stderr else ""
        proc.kill()
        raise RuntimeError(f"Could not mount Cura AppImage: {stderr.strip()}")
    mount_point = Path(mount_line)
    if not (mount_point / "CuraEngine").exists():
        proc.kill()
        raise RuntimeError(f"CuraEngine not found in AppImage mount: {mount_point}")
    return mount_point, proc


def cura_engine_prefix(mount_point: Path) -> list[str]:
    library_path = ":".join(
        str(path)
        for path in [
            mount_point / "runtime/compat",
            mount_point / "runtime/compat/lib/x86_64-linux-gnu",
            mount_point,
            mount_point / "usr/lib/x86_64-linux-gnu",
            mount_point / "usr/lib",
            mount_point / "lib/x86_64-linux-gnu",
            mount_point / "runtime/compat/lib64",
            mount_point / "runtime/compat/usr/lib/x86_64-linux-gnu",
        ]
    )
    return [
        str(mount_point / "runtime/compat/lib64/ld-linux-x86-64.so.2"),
        "--library-path",
        library_path,
        str(mount_point / "CuraEngine"),
    ]


def k9_profile_settings(brim_width: float) -> tuple[dict[str, str], dict[str, str]]:
    start_gcode = """; Little Hands manual-zero workflow for EasyThreed K9 / K9 Plus
; Expected fixed start pose on this printer:
; X = fully left, Y = bed fully back (away from operator), Z = nozzle touching bed
; This pose is treated as logical 0,0,0. Do not G28 before print.
G92 X0 Y0 Z0
G1 Z10.0 F1800
G92 E0"""
    end_gcode = """M104 S0 ;Hotend off
M140 S0 ;Bed off in G-code even though bed is external
G91
G1 E-1 F1800
G1 Z10 F1200
G90
M204 P250 T300 ;Gentle final presentation moves
G1 X95 F1800
G1 Y95 F1800 ;Move bed toward the operator"""

    global_settings = {
        "machine_name": "lilHands K9 warm mat",
        "machine_width": "100",
        "machine_depth": "100",
        "machine_height": "100",
        "machine_center_is_zero": "False",
        "machine_gcode_flavor": "RepRap (RepRap)",
        "machine_start_gcode": start_gcode,
        "machine_end_gcode": end_gcode,
        "extruders_enabled_count": "1",
        "adhesion_type": "brim",
        "brim_width": f"{brim_width:g}",
        "bottom_layers": "6",
        "infill_pattern": "lines",
        "infill_before_walls": "False",
        "infill_sparse_density": "20",
        "acceleration_enabled": "True",
        "acceleration_infill": "250",
        "acceleration_ironing": "120",
        "acceleration_layer_0": "150",
        "acceleration_print": "250",
        "acceleration_skirt_brim": "150",
        "acceleration_support": "220",
        "acceleration_support_bottom": "160",
        "acceleration_support_infill": "220",
        "acceleration_support_interface": "160",
        "acceleration_support_roof": "160",
        "acceleration_topbottom": "180",
        "acceleration_travel": "300",
        "acceleration_travel_enabled": "True",
        "acceleration_wall": "180",
        "acceleration_wall_0": "150",
        "acceleration_wall_x": "200",
        "ironing_enabled": "True",
        "ironing_flow": "7",
        "ironing_line_spacing": "0.12",
        "ironing_only_highest_layer": "True",
        "ironing_pattern": "concentric",
        "layer_height": "0.16",
        "layer_height_0": "0.2",
        "material_bed_temperature": "0",
        "relative_extrusion": "True",
        "speed_infill": "15",
        "speed_ironing": "8",
        "speed_layer_0": "6",
        "speed_print": "15",
        "speed_topbottom": "11",
        "speed_travel": "35",
        "speed_wall": "12",
        "support_angle": "35",
        "support_enable": "True",
        "support_infill_rate": "10",
        "support_interface_density": "65",
        "support_interface_enable": "True",
        "support_interface_height": "0.48",
        "support_interface_pattern": "lines",
        "support_pattern": "zigzag",
        "support_roof_density": "65",
        "support_roof_enable": "True",
        "support_roof_height": "0.48",
        "support_structure": "normal",
        "support_top_distance": "0.16",
        "support_type": "everywhere",
        "support_xy_distance": "0.3",
        "support_z_distance": "0.16",
        "top_bottom_pattern": "lines",
        "top_bottom_pattern_0": "concentric",
        "top_layers": "6",
        "wall_line_count": "5",
        # Cura GUI normally resolves these defaults; direct CuraEngine needs them.
        "roofing_layer_count": "0",
        "flooring_layer_count": "0",
        "support_z_seam_away_from_model": "False",
        "z_seam_type": "random",
    }
    extruder_settings = {
        "material_diameter": "1.75",
        "material_print_temperature": "224",
        "material_print_temperature_layer_0": "225",
        "material_flow": "103",
        "wall_material_flow": "103",
        "wall_0_material_flow": "102",
        "wall_x_material_flow": "103",
        "skin_material_flow": "102",
        "infill_material_flow": "101",
        "material_bed_temperature": "0",
        "retraction_amount": "6.5",
        "retraction_enable": "True",
        "retraction_prime_speed": "25",
        "retraction_retract_speed": "25",
        "cool_fan_enabled": "False",
        "cool_fan_speed": "0",
        "cool_fan_speed_min": "0",
        "cool_fan_speed_max": "0",
        "cool_fan_speed_0": "0",
        "cool_min_layer_time": "10",
        "bridge_settings_enabled": "True",
        "bridge_fan_speed": "0",
        "bridge_skin_material_flow": "90",
        "bridge_skin_speed": "10",
        "bridge_wall_material_flow": "90",
        "bridge_wall_speed": "10",
        "initial_layer_line_width_factor": "150",
        "acceleration_enabled": "True",
        "acceleration_infill": "250",
        "acceleration_ironing": "120",
        "acceleration_layer_0": "150",
        "acceleration_print": "250",
        "acceleration_skirt_brim": "150",
        "acceleration_support": "220",
        "acceleration_support_bottom": "160",
        "acceleration_support_infill": "220",
        "acceleration_support_interface": "160",
        "acceleration_support_roof": "160",
        "acceleration_topbottom": "180",
        "acceleration_travel": "300",
        "acceleration_travel_enabled": "True",
        "acceleration_wall": "180",
        "acceleration_wall_0": "150",
        "acceleration_wall_x": "200",
        "ironing_enabled": "True",
        "ironing_flow": "7",
        "ironing_line_spacing": "0.12",
        "ironing_only_highest_layer": "True",
        "ironing_pattern": "concentric",
        "speed_infill": "15",
        "speed_ironing": "8",
        "speed_layer_0": "6",
        "speed_print": "15",
        "speed_topbottom": "11",
        "speed_travel": "35",
        "speed_wall": "12",
    }
    return global_settings, extruder_settings


def build_cura_command(
    mount_point: Path,
    stl: Path,
    output: Path,
    brim_width: float,
    mesh_position_x: float,
    mesh_position_y: float,
) -> list[str]:
    definitions = mount_point / "share/cura/resources/definitions"
    extruders = mount_point / "share/cura/resources/extruders"
    global_settings, extruder_settings = k9_profile_settings(brim_width)

    cmd = cura_engine_prefix(mount_point) + [
        "slice",
        "-p",
        "-d",
        f"{definitions}:{extruders}",
        "-j",
        str(definitions / "custom.def.json"),
    ]
    for key, value in global_settings.items():
        cmd += ["-s", f"{key}={value}"]
    cmd += ["-e0"]
    for key, value in extruder_settings.items():
        cmd += ["-s", f"{key}={value}"]
    cmd += [
        "-o",
        str(output),
        "-s",
        f"mesh_position_x={mesh_position_x:g}",
        "-s",
        f"mesh_position_y={mesh_position_y:g}",
        "-l",
        str(stl),
    ]
    return cmd


def strip_gcode_comment(line: str) -> str:
    return line.split(";", 1)[0].strip()


def gcode_bounds(path: Path) -> tuple[float, float, float, float, float]:
    text = path.read_text(encoding="utf-8", errors="replace")
    xs: list[float] = []
    ys: list[float] = []
    zs: list[float] = []
    real_g28: list[str] = []
    for line in text.splitlines():
        command = strip_gcode_comment(line)
        if command.startswith("G28"):
            real_g28.append(line)
        if not command.startswith(("G0", "G1")):
            continue
        mz = re.search(r"\bZ(-?\d+(?:\.\d+)?)", command)
        if mz:
            zs.append(float(mz.group(1)))
        if " E" not in f" {command}":
            continue
        mx = re.search(r"\bX(-?\d+(?:\.\d+)?)", command)
        my = re.search(r"\bY(-?\d+(?:\.\d+)?)", command)
        if mx and my:
            xs.append(float(mx.group(1)))
            ys.append(float(my.group(1)))
    if real_g28:
        raise ValueError(f"Unsafe G28 command found in sliced G-code: {real_g28[0]}")
    if not xs or not ys:
        raise ValueError("No extrusion XY moves found in sliced G-code")
    return min(xs), max(xs), min(ys), max(ys), max(zs) if zs else 0.0


def estimate_filament_m(lines: list[str]) -> float:
    total_mm = 0.0
    relative_extrusion = False
    last_absolute_e: float | None = None
    for line in lines:
        command = strip_gcode_comment(line).upper()
        if not command:
            continue
        if command.startswith("M83"):
            relative_extrusion = True
            last_absolute_e = None
            continue
        if command.startswith("M82"):
            relative_extrusion = False
            last_absolute_e = None
            continue
        if command.startswith("G92"):
            match = re.search(r"\bE(-?\d+(?:\.\d+)?)", command)
            if match:
                last_absolute_e = float(match.group(1))
            continue
        if not command.startswith(("G0", "G1")):
            continue
        match = re.search(r"\bE(-?\d+(?:\.\d+)?)", command)
        if not match:
            continue
        e_value = float(match.group(1))
        if relative_extrusion:
            if e_value > 0:
                total_mm += e_value
        else:
            if last_absolute_e is not None:
                delta = e_value - last_absolute_e
                if delta > 0:
                    total_mm += delta
            last_absolute_e = e_value
    return total_mm / 1000.0


def replace_early_m109_with_m104(lines: list[str]) -> bool:
    for index, line in enumerate(lines[:120]):
        stripped = line.strip()
        if stripped.startswith(";LAYER:") or stripped.startswith(";LAYER_COUNT:"):
            return False
        if not stripped or stripped.startswith(";"):
            continue
        command = stripped.split(";", 1)[0].strip()
        if not command.upper().startswith("M109"):
            continue
        match = re.search(r"\bS([-+]?\d+(?:\.\d+)?)\b", command, re.IGNORECASE)
        if not match:
            continue
        target = float(match.group(1))
        prefix = line[: len(line) - len(line.lstrip())]
        lines[index] = (
            f"{prefix}M104 S{target:g} ; LH: non-blocking heat target; "
            "Little Hands preheats before SD start"
        )
        return True
    return False


def remove_slicer_fan_commands(lines: list[str]) -> int:
    replacements = 0
    for index, line in enumerate(lines):
        command = strip_gcode_comment(line).upper()
        if not command.startswith(("M106", "M107")):
            continue
        prefix = line[: len(line) - len(line.lstrip())]
        comment = ""
        if ";" in line:
            comment = " ;" + line.split(";", 1)[1]
        lines[index] = (
            f"{prefix}; LH: removed slicer fan command '{command}' "
            f"because K9 has one firmware-managed hotend fan{comment}"
        )
        replacements += 1
    return replacements


def patch_header_and_footer(path: Path, bounds: tuple[float, float, float, float, float], brim_width: float) -> None:
    min_x, max_x, min_y, max_y, max_z = bounds
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    filament_m = estimate_filament_m(lines)
    replace_early_m109_with_m104(lines)
    remove_slicer_fan_commands(lines)
    for index, line in enumerate(lines[:25]):
        if line.startswith(";Filament used:") and filament_m > 0:
            lines[index] = f";Filament used: {filament_m:.3f}m"
        elif line.startswith(";MINX:"):
            lines[index] = f";MINX:{min_x:.3f}"
        elif line.startswith(";MAXX:"):
            lines[index] = f";MAXX:{max_x:.3f}"
        elif line.startswith(";MINY:"):
            lines[index] = f";MINY:{min_y:.3f}"
        elif line.startswith(";MAXY:"):
            lines[index] = f";MAXY:{max_y:.3f}"
        elif line.startswith(";MINZ:"):
            lines[index] = ";MINZ:0.2"
        elif line.startswith(";MAXZ:"):
            lines[index] = f";MAXZ:{max_z:.2f}"

    footer = (
        ';SETTING_3 {"global_quality": "[values]\\n'
        f'adhesion_type = brim\\nbrim_width = {brim_width:g}\\n'
        'layer_height = 0.16\\nlayer_height_0 = 0.2\\nspeed_layer_0 = 6\\n'
        'wall_line_count = 5\\n'
        'support_enable = True\\nsupport_type = everywhere\\nsupport_angle = 35\\n'
        'support_infill_rate = 10\\nsupport_xy_distance = 0.3\\n'
        'support_interface_enable = True\\nsupport_interface_density = 65\\n'
        'support_interface_height = 0.48\\nsupport_roof_enable = True\\n'
        'support_roof_density = 65\\nsupport_roof_height = 0.48\\n'
        'z_seam_type = random\\n", '
        '"extruder_quality": ["[values]\\nmaterial_print_temperature = 224\\n'
        'material_print_temperature_layer_0 = 225\\nretraction_enable = True\\n'
        'retraction_amount = 6.5\\nmaterial_flow = 103\\nwall_material_flow = 103\\n'
        'cool_fan_enabled = False\\n'
        'cool_fan_speed = 0\\nbridge_fan_speed = 0\\n"]}'
    )
    if not any(line.startswith(";SETTING_3") for line in lines[-80:]):
        lines.append(footer)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def validate_bounds(bounds: tuple[float, float, float, float, float], bed_size: float) -> None:
    min_x, max_x, min_y, max_y, _ = bounds
    if min_x < 0 or min_y < 0 or max_x > bed_size or max_y > bed_size:
        raise ValueError(
            "Sliced G-code is outside the validated bed area: "
            f"X {min_x:.3f}..{max_x:.3f}, Y {min_y:.3f}..{max_y:.3f}, bed {bed_size:g}x{bed_size:g}"
        )


def copy_to_sd(src: Path, sd_mount: Path, target_name: str) -> Path:
    if not sd_mount.is_dir():
        raise ValueError(f"SD mount is not a directory: {sd_mount}")
    dst = sd_mount / target_name
    shutil.copy2(src, dst)
    os.sync()
    if sha256(src) != sha256(dst):
        raise ValueError(f"SD copy verification failed: {dst}")
    return dst


def main() -> int:
    parser = argparse.ArgumentParser(description="Slice an STL for the Little Hands K9 warm-mat profile.")
    parser.add_argument("stl", type=Path, help="Input STL file")
    parser.add_argument("--output", type=Path, default=None, help="Output G-code path")
    parser.add_argument("--appimage", type=Path, default=DEFAULT_APPIMAGE, help="UltiMaker Cura 5.11 AppImage")
    parser.add_argument("--brim-width", type=float, default=12.0, help="Brim width in mm")
    parser.add_argument("--bed-size", type=float, default=100.0, help="Validated square bed size in mm")
    parser.add_argument("--sd-mount", type=Path, default=None, help="Optional mounted SD card path to copy to")
    parser.add_argument("--sd-name", default=None, help="Optional filename to use on SD")
    args = parser.parse_args()

    stl = args.stl.expanduser().resolve()
    if not stl.is_file():
        print(f"Error: STL not found: {stl}", file=sys.stderr)
        return 1
    appimage = args.appimage.expanduser().resolve()
    if not appimage.is_file():
        print(f"Error: Cura AppImage not found: {appimage}", file=sys.stderr)
        return 1

    output = args.output
    if output is None:
        DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        output = DEFAULT_OUTPUT_DIR / f"{stl.stem}.gcode"
    output = output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    stl_min_x, stl_max_x, stl_min_y, stl_max_y, _, _ = parse_binary_stl_bounds(stl)
    mesh_position_x = -((stl_min_x + stl_max_x) / 2.0)
    mesh_position_y = -((stl_min_y + stl_max_y) / 2.0)

    mount_point, mount_proc = mount_appimage(appimage)
    try:
        cmd = build_cura_command(mount_point, stl, output, args.brim_width, mesh_position_x, mesh_position_y)
        started = time.monotonic()
        proc = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        if proc.returncode:
            print(proc.stdout[-6000:], file=sys.stderr)
            return proc.returncode
        bounds = gcode_bounds(output)
        validate_bounds(bounds, args.bed_size)
        patch_header_and_footer(output, bounds, args.brim_width)
        print(f"Sliced {stl.name} -> {output}")
        print(
            "Bounds: "
            f"X {bounds[0]:.3f}..{bounds[1]:.3f}, "
            f"Y {bounds[2]:.3f}..{bounds[3]:.3f}, Z {bounds[4]:.2f}"
        )
        print(f"SHA256: {sha256(output)}")
        print(f"Elapsed: {time.monotonic() - started:.1f}s")

        if args.sd_mount:
            target_name = args.sd_name or output.name
            copied = copy_to_sd(output, args.sd_mount.expanduser().resolve(), target_name)
            print(f"Copied to SD: {copied}")
    finally:
        mount_proc.terminate()
        try:
            mount_proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            mount_proc.kill()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
