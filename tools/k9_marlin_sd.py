#!/usr/bin/env python3
"""
Manage the printer SD card over Marlin USB.

Supports:
- listing files on the printer SD
- deleting files from the printer SD
- binary uploading regular G-code files
- binary uploading firmware as mksLite.bin and requesting M997 reboot

This tool is intended for the EasyThreeD K9 / ET-4000+ workflow where
the SD card stays inside the printer and Marlin exposes:
- BINARY_FILE_TRANSFER
- CUSTOM_FIRMWARE_UPLOAD
- SD_WRITE
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import re
import sys
import time
from pathlib import Path

import serial
from serial.tools import list_ports
from typing import Callable


PROJECT_ROOT = Path("/home/maxim/draftCode/littleHands")
MBP_PATH = PROJECT_ROOT / "firmware_src/ECF-Marlin-upstream/buildroot/share/scripts/MarlinBinaryProtocol.py"
ProgressCb = Callable[[str, float], None]


def list_serial_ports() -> list[dict[str, str]]:
    ports: list[dict[str, str]] = []
    for info in list_ports.comports():
        ports.append({
            "device": info.device or "",
            "description": info.description or "",
            "hwid": info.hwid or "",
            "manufacturer": info.manufacturer or "",
            "product": info.product or "",
            "serial_number": info.serial_number or "",
            "vid": f"{info.vid:04X}" if info.vid is not None else "",
            "pid": f"{info.pid:04X}" if info.pid is not None else "",
        })
    return ports


def _port_score(meta: dict[str, str]) -> int:
    hay = " ".join(meta.values()).lower()
    score = 0
    if meta.get("device", "").startswith("/dev/ttyUSB"):
        score += 6
    if meta.get("device", "").startswith("/dev/ttyACM"):
        score += 5
    for token, bonus in (
        ("ch340", 8),
        ("wch", 6),
        ("usb-serial", 6),
        ("serial", 3),
        ("marlin", 8),
        ("stm32", 4),
        ("arduino", 3),
        ("usb", 2),
    ):
        if token in hay:
            score += bonus
    return score


def detect_printer_port(baud: int = 115200, probe_timeout_s: float = 2.8) -> tuple[str | None, list[dict[str, str]]]:
    candidates = list_serial_ports()
    if not candidates:
        return None, []

    ranked = sorted(candidates, key=_port_score, reverse=True)
    likely = [
        meta for meta in ranked
        if meta.get("device", "").startswith(("/dev/ttyUSB", "/dev/ttyACM"))
        or _port_score(meta) >= 6
    ] or ranked[:6]

    for meta in likely[:8]:
        device = meta.get("device", "")
        if not device:
            continue
        try:
            with open_serial(device, baud, timeout=0.5) as ser:
                sync_ascii(ser)
                send_line(ser, "M115")
                time.sleep(0.45)
                caps = read_for(ser, 0.9)
                if "FIRMWARE_NAME:" not in caps:
                    send_line(ser, "M105")
                    time.sleep(0.25)
                    caps += read_for(ser, 0.7)
            if "FIRMWARE_NAME:" in caps:
                meta["detected"] = "marlin"
                return device, ranked
            if "T:" in caps and "ok" in caps:
                meta["detected"] = "marlin-like"
                return device, ranked
            if probe_timeout_s and _port_score(meta) <= 0:
                meta["detected"] = "timeout"
        except Exception:
            continue
    return None, ranked


def make_sd_name(source_name: str) -> str:
    src = Path(source_name)
    stem = re.sub(r"[^A-Za-z0-9]+", "_", src.stem.upper()).strip("_") or "MODEL"
    stem = stem[:8]
    return f"{stem}.GCO"


def load_mbp():
    spec = importlib.util.spec_from_file_location("MarlinBinaryProtocol", MBP_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load MarlinBinaryProtocol from {MBP_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["MarlinBinaryProtocol"] = module
    spec.loader.exec_module(module)
    return module


def open_serial(port: str, baud: int, timeout: float = 1.0) -> serial.Serial:
    ser = serial.Serial(port, baudrate=baud, timeout=timeout, write_timeout=timeout)
    time.sleep(1.5)
    ser.reset_input_buffer()
    return ser


def send_line(ser: serial.Serial, line: str) -> None:
    ser.write((line + "\n").encode("ascii"))
    ser.flush()


def read_for(ser: serial.Serial, seconds: float) -> str:
    end = time.monotonic() + seconds
    chunks: list[str] = []
    while time.monotonic() < end:
        raw = ser.readline()
        if not raw:
            continue
        try:
            chunks.append(raw.decode("utf-8", "replace"))
        except Exception:
            pass
    return "".join(chunks)


def sync_ascii(ser: serial.Serial) -> None:
    # This printer often garbles the first command after reconnect.
    for line in ("", "M110 N0"):
        send_line(ser, line)
        time.sleep(0.5)
        ser.read_all()


def ensure_sd_ready(ser: serial.Serial) -> str:
    send_line(ser, "M21")
    time.sleep(0.8)
    out = read_for(ser, 1.0)
    if "No SD card" in out or "No media" in out:
        raise RuntimeError("Printer reports no SD card / no media")
    if "SD card ok" not in out and "SD init fail" in out:
        raise RuntimeError("Printer reports SD init failure")
    return out


def preflight(port: str, baud: int) -> tuple[str, str]:
    last_caps = ""
    for _attempt in range(3):
        with open_serial(port, baud) as ser:
            sync_ascii(ser)
            send_line(ser, "M115")
            time.sleep(1.0)
            caps = read_for(ser, 1.6)
            sd = ensure_sd_ready(ser)
        last_caps = caps
        if "FIRMWARE_NAME:" in caps:
            return caps, sd
        time.sleep(0.5)
    return last_caps, sd


def query_command(
    port: str,
    baud: int,
    command: str,
    *,
    wait_before_read: float = 0.8,
    read_seconds: float = 1.5,
    sync: bool = True,
) -> str:
    with open_serial(port, baud) as ser:
        if sync:
            sync_ascii(ser)
        send_line(ser, command)
        time.sleep(wait_before_read)
        return read_for(ser, read_seconds)


def run_commands(
    port: str,
    baud: int,
    commands: list[str],
    *,
    settle_after_each: float = 0.2,
    final_wait: float = 0.8,
    read_seconds: float = 1.5,
) -> str:
    with open_serial(port, baud) as ser:
        sync_ascii(ser)
        for command in commands:
            send_line(ser, command)
            time.sleep(settle_after_each)
        time.sleep(final_wait)
        return read_for(ser, read_seconds)


def parse_m20_listing(text: str) -> list[str]:
    files: list[str] = []
    in_list = False
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if "Begin file list" in line:
            in_list = True
            continue
        if "End file list" in line:
            break
        lower = line.lower()
        if not in_list:
            # Some K9 builds return file rows without "Begin file list".
            looks_like_file = (
                lower.endswith((".gco", ".gcode", ".g"))
                or ".gco " in lower
                or ".gcode" in lower
                or lower.endswith("eeprom.dat")
                or "eeprom.dat" in lower
                or lower.endswith("mkslite.bin")
                or "mkslite.bin" in lower
                or lower.endswith("mkslite.cur")
                or "mkslite.cur" in lower
            )
            if not looks_like_file:
                continue
        if line == "ok":
            continue
        files.append(line)
    return files


def read_sd_listing(port: str, baud: int, firmware_only: bool = False) -> tuple[list[str], str, str]:
    commands = ["M20 F"] if firmware_only else ["M20 L", "M20"]
    last_out = ""
    last_status = "unavailable"

    for cmd in commands:
        for _attempt in range(2):
            with open_serial(port, baud) as ser:
                sync_ascii(ser)
                ensure_sd_ready(ser)
                send_line(ser, cmd)
                time.sleep(1.2)
                out = read_for(ser, 2.0)
            last_out = out
            if "No SD card" in out or "No media" in out:
                raise RuntimeError("Printer reports no SD card / no media")
            files = parse_m20_listing(out)
            if "Begin file list" in out or ("End file list" in out and files) or files:
                return files, "ok", out
            lowered = out.lower()
            if "busy" in lowered or "processing" in lowered or "sd printing byte" in lowered:
                return [], "busy", out
            last_status = "unavailable"
            time.sleep(0.3)

    if not last_out.strip():
        return [], "unavailable", last_out
    return [], last_status, last_out


def list_files(port: str, baud: int, firmware_only: bool = False) -> list[str]:
    files, status, _raw = read_sd_listing(port, baud, firmware_only=firmware_only)
    if status == "busy":
        raise RuntimeError("Printer is busy printing; SD file listing is unavailable right now")
    if status == "unavailable":
        raise RuntimeError("Printer did not return a usable SD file list")
    return files


def delete_file(port: str, baud: int, path: str) -> str:
    target = path if path.startswith("/") else f"/{path}"
    with open_serial(port, baud) as ser:
        sync_ascii(ser)
        ensure_sd_ready(ser)
        send_line(ser, f"M30 {target}")
        time.sleep(0.8)
        out = read_for(ser, 2.0)
    if "File deleted" not in out and "ok" not in out:
        raise RuntimeError(f"Delete may have failed for {target}: {out.strip() or '<no response>'}")
    return out


def start_sd_print(port: str, baud: int, path: str) -> str:
    target = path if path.startswith("/") else f"/{path}"
    with open_serial(port, baud) as ser:
        sync_ascii(ser)
        ensure_sd_ready(ser)
        send_line(ser, f"M23 {target}")
        time.sleep(0.8)
        send_line(ser, "M24")
        time.sleep(0.8)
        out = read_for(ser, 2.0)
    if "File opened" not in out and "ok" not in out and "echo:Now fresh file" not in out:
        raise RuntimeError(f"Start print may have failed for {target}: {out.strip() or '<no response>'}")
    return out


def set_current_home_zero(port: str, baud: int) -> str:
    return run_commands(
        port,
        baud,
        ["G90", "G92 X0 Y0 Z0", "M114"],
        final_wait=0.8,
        read_seconds=1.5,
    )


def pseudo_home_to_zero(port: str, baud: int) -> str:
    """
    Drive the K9 into its known mechanical print-start pose and declare it X0 Y0 Z0.

    This printer does not provide reliable conventional endstop-based homing on
    the current baseline. Instead we:
    - lift Z to avoid scraping while moving laterally
    - drive X and Y far enough in the negative direction to reach the hard stops
    - lower Z slowly back to the print-start contact point
    - set the resulting pose as logical zero
    """
    return run_commands(
        port,
        baud,
        [
            "M17",
            "G90",
            "M211 S0",
            "G91",
            "G1 Z15 F600",
            "M400",
            "G1 X-130 F1800",
            "M400",
            "G1 Y-130 F1800",
            "M400",
            "G1 Z-120 F300",
            "M400",
            "G90",
            "G92 X0 Y0 Z0",
            "M114",
        ],
        settle_after_each=0.5,
        final_wait=5.0,
        read_seconds=5.5,
    )


def goto_print_home(port: str, baud: int) -> str:
    return run_commands(
        port,
        baud,
        ["G90", "M211 S0", "G1 Z10 F600", "G1 X0 Y0 F1800", "G1 Z0 F600", "M114"],
        final_wait=0.8,
        read_seconds=2.0,
    )


def start_sd_print_from_home(port: str, baud: int, path: str) -> str:
    target = path if path.startswith("/") else f"/{path}"
    with open_serial(port, baud) as ser:
        sync_ascii(ser)
        ensure_sd_ready(ser)
        for line in ("G90", "M211 S0", "G1 Z10 F600", "G1 X0 Y0 F1800", "G1 Z0 F600"):
            send_line(ser, line)
            time.sleep(0.5)
        _ = read_for(ser, 2.0)
        send_line(ser, f"M23 {target}")
        time.sleep(0.8)
        send_line(ser, "M24")
        time.sleep(0.8)
        out = read_for(ser, 2.5)
    if "File opened" not in out and "ok" not in out and "echo:Now fresh file" not in out:
        raise RuntimeError(f"Start print from home may have failed for {target}: {out.strip() or '<no response>'}")
    return out


def start_sd_print_from_pseudo_home(port: str, baud: int, path: str) -> str:
    target = path if path.startswith("/") else f"/{path}"
    with open_serial(port, baud) as ser:
        sync_ascii(ser)
        ensure_sd_ready(ser)
        for line in (
            "M17",
            "G90",
            "M211 S0",
            "G91",
            "G1 Z15 F600",
            "M400",
            "G1 X-130 F1800",
            "M400",
            "G1 Y-130 F1800",
            "M400",
            "G1 Z-120 F300",
            "M400",
            "G90",
            "G92 X0 Y0 Z0",
        ):
            send_line(ser, line)
            time.sleep(0.5)
        _ = read_for(ser, 5.0)
        send_line(ser, f"M23 {target}")
        time.sleep(0.8)
        send_line(ser, "M24")
        time.sleep(0.8)
        out = read_for(ser, 2.5)
    if "File opened" not in out and "ok" not in out and "echo:Now fresh file" not in out:
        raise RuntimeError(f"Start print from pseudo-home may have failed for {target}: {out.strip() or '<no response>'}")
    return out


def pause_sd_print(port: str, baud: int) -> str:
    return query_command(port, baud, "M25", wait_before_read=0.6, read_seconds=1.5)


def stop_sd_print(port: str, baud: int) -> str:
    return run_commands(
        port,
        baud,
        ["M524", "M104 S0", "M140 S0", "M107", "M400"],
        settle_after_each=0.4,
        final_wait=1.2,
        read_seconds=2.5,
    )


def resume_sd_print(port: str, baud: int) -> str:
    return query_command(port, baud, "M24", wait_before_read=0.6, read_seconds=1.5)


def upload_binary(
    port: str,
    baud: int,
    source: Path,
    dest_name: str,
    compression: bool = False,
    progress_cb: ProgressCb | None = None,
) -> None:
    mbp = load_mbp()

    caps, _sd = preflight(port, baud)
    if progress_cb:
        progress_cb("Upload (binary connect)", 0.0)
    if "Cap:BINARY_FILE_TRANSFER:1" not in caps:
        print("Warning: M115 did not clearly advertise BINARY_FILE_TRANSFER; trying binary protocol anyway.", file=sys.stderr)
    if "Cap:SD_WRITE:1" not in caps:
        print("Warning: M115 did not clearly advertise SD_WRITE; trying binary protocol anyway.", file=sys.stderr)

    protocol = None
    try:
        protocol = mbp.Protocol(port, baud, 512, 0.0, 3000)
        protocol.connect()
        ftp = mbp.FileTransferProtocol(protocol)
        if progress_cb:
            progress_cb("Upload (binary open)", 0.0)
        if progress_cb:
            original_write = ftp.write

            total_bytes = max(source.stat().st_size, 1)
            sent = {"bytes": 0}

            def wrapped_write(data):
                result = original_write(data)
                sent["bytes"] += len(data)
                pct = max(0.0, min(100.0, (sent["bytes"] / total_bytes) * 100.0))
                progress_cb("Upload (binary)", pct)
                return result

            ftp.write = wrapped_write
        ok = ftp.copy(str(source), dest_name, compression=compression, dummy=False)
        try:
            protocol.disconnect()
        except Exception:
            pass
        protocol.shutdown()
        protocol = None
        if not ok:
            raise RuntimeError("Binary transfer reported failure")
    finally:
        if protocol is not None:
            try:
                protocol.shutdown()
            except Exception:
                pass

    # Marlin / SD state can stay stale right after binary transfer.
    # Force an SD remount before any follow-up M20 / M23 operations.
    with open_serial(port, baud) as ser:
        sync_ascii(ser)
        send_line(ser, "M21")
        time.sleep(1.0)
        _ = read_for(ser, 1.2)


def marlin_line(number: int, command: str) -> str:
    payload = f"N{number} {command}"
    checksum = 0
    for byte in payload.encode("ascii"):
        checksum ^= byte
    return f"{payload}*{checksum}"


def read_until_tokens(ser: serial.Serial, stop_tokens: tuple[str, ...], timeout_s: float = 5.0) -> str:
    chunks: list[str] = []
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        raw = ser.readline()
        if not raw:
            continue
        text = raw.decode("utf-8", "replace")
        chunks.append(text)
        if any(token in text for token in stop_tokens):
            break
    return "".join(chunks)


def send_numbered(ser: serial.Serial, number: int, command: str, wait: float = 0.8) -> str:
    packet = marlin_line(number, command)
    ser.write((packet + "\n").encode("ascii"))
    ser.flush()
    time.sleep(wait)
    return read_until_tokens(ser, ("ok", "Error:", "Resend:"), timeout_s=5.0)


def sanitize_gcode_line(raw: str) -> str:
    no_semicolon = raw.split(";", 1)[0]
    no_parens = re.sub(r"\([^()]*\)", "", no_semicolon)
    return no_parens.strip()


def upload_gcode_text(
    port: str,
    baud: int,
    source: Path,
    dest_name: str,
    progress_cb: ProgressCb | None = None,
) -> None:
    text = source.read_text(encoding="utf-8", errors="replace").splitlines()
    upload_lines = [sanitize_gcode_line(raw) for raw in text]
    upload_lines = [line for line in upload_lines if line]
    total_lines = max(len(upload_lines), 1)
    if progress_cb:
        progress_cb("Upload (text prepare)", 0.0)

    with serial.Serial(port, baud, timeout=0.4) as ser:
        time.sleep(1.2)
        ser.reset_input_buffer()

        reset_reply = send_numbered(ser, 0, "M110 N0")
        if "Error:" in reset_reply or "Resend:" in reset_reply:
            raise RuntimeError(f"Failed to reset line numbering: {reset_reply.strip()}")

        line_no = 1
        m21_reply = send_numbered(ser, line_no, "M21")
        if "Error:" in m21_reply or "Resend:" in m21_reply:
            raise RuntimeError(f"SD init failed before text upload: {m21_reply.strip()}")
        line_no += 1

        _delete_reply = send_numbered(ser, line_no, f"M30 /{dest_name}")
        line_no += 1

        m28_reply = send_numbered(ser, line_no, f"M28 {dest_name}")
        if "Error:" in m28_reply or "Resend:" in m28_reply:
            raise RuntimeError(f"Failed to open SD file for writing: {m28_reply.strip()}")
        line_no += 1
        if progress_cb:
            progress_cb("Upload (text)", 0.0)

        for line in upload_lines:
            packet = marlin_line(line_no, line)
            ser.write((packet + "\n").encode("ascii"))
            ser.flush()
            reply = read_until_tokens(ser, ("ok", "Error:", "Resend:"), timeout_s=5.0)
            if "Error:" in reply or "Resend:" in reply:
                raise RuntimeError(f"Printer rejected line {line_no}: {line}")
            if progress_cb:
                done = line_no - 3
                pct = max(0.0, min(100.0, (done / total_lines) * 100.0))
                progress_cb("Upload (text)", pct)
            line_no += 1

        m29_reply = send_numbered(ser, line_no, "M29", wait=1.0)
        if "Error:" in m29_reply or "Resend:" in m29_reply:
            raise RuntimeError(f"Failed to finalize SD file: {m29_reply.strip()}")
        if progress_cb:
            progress_cb("Upload (verify SD)", 100.0)


def upload_gcode_auto(
    port: str,
    baud: int,
    source: Path,
    dest_name: str,
    progress_cb: ProgressCb | None = None,
) -> str:
    source = source.expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(f"G-code file not found: {source}")
    transfer_error: Exception | None = None
    try:
        upload_binary(port, baud, source, dest_name, compression=False, progress_cb=progress_cb)
        method = "binary"
    except Exception as exc:
        transfer_error = exc
        if progress_cb:
            progress_cb("Upload (fallback)", 0.0)
        upload_gcode_text(port, baud, source, dest_name, progress_cb=progress_cb)
        method = f"text-fallback ({exc})"

    visible = "\n".join(list_files(port, baud))
    if dest_name not in visible and f"/{dest_name}" not in visible:
        if transfer_error is not None:
            raise RuntimeError(f"G-code upload did not produce a visible SD file after fallback. First failure: {transfer_error}")
        raise RuntimeError("G-code upload finished but the file is not visible on printer SD")
    return method


def flash_firmware(port: str, baud: int, source: Path, purge_bin: bool = False) -> None:
    if purge_bin:
        files = list_files(port, baud, firmware_only=True)
        for entry in files:
            # M20 F may include metadata prefixes; keep the visible filename.
            match = re.search(r"([A-Za-z0-9._-]+\.bin)\b", entry, re.IGNORECASE)
            if match:
                delete_file(port, baud, match.group(1))

    upload_binary(port, baud, source, "mksLite.bin", compression=False)

    with open_serial(port, baud) as ser:
        sync_ascii(ser)
        send_line(ser, "M997")
        time.sleep(0.3)
        _ = read_for(ser, 0.8)


def cmd_status(args: argparse.Namespace) -> int:
    caps, sd = preflight(args.port, args.baud)
    print(caps.strip())
    print(sd.strip())
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    files = list_files(args.port, args.baud, firmware_only=args.firmware_only)
    if not files:
        print("(empty)")
        return 0
    for item in files:
        print(item)
    return 0


def cmd_delete(args: argparse.Namespace) -> int:
    print(delete_file(args.port, args.baud, args.path).strip())
    return 0


def cmd_upload(args: argparse.Namespace) -> int:
    source = Path(args.source).expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    dest_name = args.dest or source.name
    if args.compression:
        upload_binary(args.port, args.baud, source, dest_name, compression=True)
        method = "binary+compression"
    else:
        method = upload_gcode_auto(args.port, args.baud, source, dest_name)
    print(f"Uploaded {source.name} -> {dest_name} via {method}")
    return 0


def cmd_flash_firmware(args: argparse.Namespace) -> int:
    source = Path(args.source).expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    flash_firmware(args.port, args.baud, source, purge_bin=args.purge_bin)
    print(f"Uploaded firmware {source.name} -> mksLite.bin and sent M997")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage printer SD over Marlin USB binary transfer.")
    parser.add_argument("--port", default="/dev/ttyUSB0", help="Serial port")
    parser.add_argument("--baud", type=int, default=115200, help="Serial baud rate")

    sub = parser.add_subparsers(dest="command", required=True)

    p_status = sub.add_parser("status", help="Check printer capabilities and SD readiness")
    p_status.set_defaults(func=cmd_status)

    p_list = sub.add_parser("list", help="List files on printer SD")
    p_list.add_argument("--firmware-only", action="store_true", help="Use M20 F to list BIN firmware files only")
    p_list.set_defaults(func=cmd_list)

    p_delete = sub.add_parser("delete", help="Delete a file from printer SD")
    p_delete.add_argument("path", help="Filename or /path on printer SD")
    p_delete.set_defaults(func=cmd_delete)

    p_upload = sub.add_parser("upload", help="Upload a regular file to printer SD using binary transfer")
    p_upload.add_argument("source", help="Local file to upload")
    p_upload.add_argument("--dest", default=None, help="Destination filename on printer SD")
    p_upload.add_argument("--compression", action="store_true", help="Enable heatshrink compression if host/printer both support it")
    p_upload.set_defaults(func=cmd_upload)

    p_flash = sub.add_parser("flash-firmware", help="Upload firmware as mksLite.bin and send M997 reboot")
    p_flash.add_argument("source", help="Local firmware .bin to upload")
    p_flash.add_argument("--purge-bin", action="store_true", help="Delete existing visible .bin files before upload")
    p_flash.set_defaults(func=cmd_flash_firmware)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1)
