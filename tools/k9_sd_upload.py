#!/usr/bin/env python3
"""
Upload a sliced G-code file to the printer SD card over Marlin serial.

This uses the M28/M29 SD-upload mode with Marlin line numbers and checksums,
which the upgraded EasyThreeD K9 firmware expects for file content.
"""

from __future__ import annotations

import argparse
import os
import pathlib
import re
import sys
import time

import serial


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


def send_plain(ser: serial.Serial, command: str, wait: float = 0.8) -> str:
    ser.write((command + "\n").encode("ascii"))
    ser.flush()
    time.sleep(wait)
    return read_until_tokens(ser, ("ok", "Error:", "Resend:"), timeout_s=5.0)


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


def upload_file(port: str, baud: int, src: pathlib.Path, target_name: str) -> int:
    text = src.read_text(encoding="utf-8", errors="replace").splitlines()
    upload_lines = [sanitize_gcode_line(raw) for raw in text]
    upload_lines = [line for line in upload_lines if line]
    total = len(upload_lines)

    with serial.Serial(port, baud, timeout=0.4) as ser:
        time.sleep(1.2)
        ser.reset_input_buffer()

        # Reset Marlin's expected line number so each upload can start cleanly.
        reset_reply = send_numbered(ser, 0, "M110 N0")
        if reset_reply:
            print(reset_reply, end="")

        line_no = 1

        print(send_numbered(ser, line_no, "M21"), end="")
        line_no += 1

        delete_reply = send_numbered(ser, line_no, f"M30 /{target_name}")
        if delete_reply:
            print(delete_reply, end="")
        line_no += 1

        print(send_numbered(ser, line_no, f"M28 {target_name}"), end="")
        line_no += 1

        for idx, line in enumerate(upload_lines, start=1):
            packet = marlin_line(line_no, line)
            ser.write((packet + "\n").encode("ascii"))
            ser.flush()
            reply = read_until_tokens(ser, ("ok", "Error:", "Resend:"), timeout_s=5.0)
            if "Error:" in reply or "Resend:" in reply:
                raise RuntimeError(f"Printer rejected line {line_no}: {line}")
            if idx == 1 or idx % 1000 == 0 or idx == total:
                print(f"Uploaded {idx}/{total} G-code lines...")
            line_no += 1

        print(send_numbered(ser, line_no, "M29", wait=1.0), end="")
        line_no += 1
        print(send_numbered(ser, line_no, "M20 L", wait=1.0), end="")

    return 0


def choose_target_name(src: pathlib.Path, explicit: str | None) -> str:
    if explicit:
        name = explicit
    else:
        name = src.name
    name = os.path.basename(name).upper()
    if not name.endswith((".GCO", ".GCODE")):
        name += ".GCO"
    return name


def main() -> int:
    parser = argparse.ArgumentParser(description="Upload a G-code file to the printer SD card over USB.")
    parser.add_argument("gcode", help="Path to the sliced .gcode file")
    parser.add_argument("--port", default="/dev/ttyUSB0", help="Serial port")
    parser.add_argument("--baud", type=int, default=115200, help="Serial baud rate")
    parser.add_argument("--target-name", default=None, help="Filename to use on the printer SD")
    args = parser.parse_args()

    src = pathlib.Path(args.gcode).expanduser().resolve()
    if not src.is_file():
        print(f"Error: file not found: {src}", file=sys.stderr)
        return 1

    target_name = choose_target_name(src, args.target_name)
    print(f"Uploading {src} to printer SD as {target_name} via {args.port}...")
    return upload_file(args.port, args.baud, src, target_name)


if __name__ == "__main__":
    raise SystemExit(main())
