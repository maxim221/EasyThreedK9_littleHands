#!/usr/bin/env python3
"""
Stream a G-code file directly to Marlin over USB.

This mode prints without using the printer SD card. The computer must stay
connected for the whole print.
"""

from __future__ import annotations

import argparse
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


def sanitize_gcode_line(raw: str) -> str:
    no_semicolon = raw.split(";", 1)[0]
    no_parens = re.sub(r"\([^()]*\)", "", no_semicolon)
    return no_parens.strip()


def read_reply(ser: serial.Serial, timeout_s: float = 10.0) -> tuple[str, bool, int | None]:
    deadline = time.monotonic() + timeout_s
    chunks: list[str] = []
    resend_to: int | None = None
    while time.monotonic() < deadline:
        raw = ser.readline()
        if not raw:
            continue
        text = raw.decode("utf-8", "replace")
        chunks.append(text)
        if "Resend:" in text:
            match = re.search(r"Resend:\s*(\d+)", text)
            if match:
                resend_to = int(match.group(1))
            return ("".join(chunks), False, resend_to)
        if "Error:" in text:
            return ("".join(chunks), False, resend_to)
        if text.strip() == "ok" or text.rstrip().endswith("ok"):
            return ("".join(chunks), True, resend_to)
    return ("".join(chunks), False, resend_to)


def prepare_lines(src: pathlib.Path) -> list[str]:
    text = src.read_text(encoding="utf-8", errors="replace").splitlines()
    return [line for line in (sanitize_gcode_line(raw) for raw in text) if line]


def command_timeout(command: str) -> float:
    upper = command.upper()
    if upper.startswith("M109") or upper.startswith("M190"):
        return 900.0
    if upper.startswith("G28"):
        return 120.0
    return 10.0


def stream_print(port: str, baud: int, src: pathlib.Path, progress_every: int) -> int:
    lines = prepare_lines(src)
    total = len(lines)

    print(f"Streaming {src} to printer over {port} ({total} G-code lines)...", flush=True)

    with serial.Serial(port, baud, timeout=0.4) as ser:
        time.sleep(1.5)
        ser.reset_input_buffer()

        # Clear any lingering wait state from a previous interrupted session.
        for prep in ("M108", "M104 S0"):
            ser.write((prep + "\n").encode("ascii"))
            ser.flush()
            prep_reply, _, _ = read_reply(ser, timeout_s=5.0)
            if prep_reply:
                print(prep_reply, end="", flush=True)

        reset_packet = marlin_line(0, "M110 N0")
        ser.write((reset_packet + "\n").encode("ascii"))
        ser.flush()
        reply, ok, _ = read_reply(ser)
        if reply:
            print(reply, end="", flush=True)
        if not ok:
            raise RuntimeError("Failed to reset Marlin line numbering before print.")

        line_no = 1
        index = 0
        while index < total:
            line = lines[index]
            packet = marlin_line(line_no, line)
            ser.write((packet + "\n").encode("ascii"))
            ser.flush()

            reply, ok, resend_to = read_reply(ser, timeout_s=command_timeout(line))
            if reply and ("Error:" in reply or "Resend:" in reply):
                print(reply, end="", flush=True)

            if ok:
                index += 1
                if index == 1 or index % progress_every == 0 or index == total:
                    print(f"Sent {index}/{total} lines...", flush=True)
                line_no += 1
                continue

            if resend_to is not None:
                # We stream one line at a time, so Resend should only target the
                # current line or an earlier already-sent line. Rewind to that
                # line index and continue from there.
                if resend_to <= 0:
                    line_no = 1
                    index = 0
                else:
                    line_no = resend_to
                    index = resend_to - 1
                continue

            raise RuntimeError(f"Printer rejected line {line_no}: {line}")

    print("USB print stream completed.", flush=True)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Stream a G-code file directly to Marlin over USB.")
    parser.add_argument("gcode", help="Path to the sliced .gcode file")
    parser.add_argument("--port", default="/dev/ttyUSB0", help="Serial port")
    parser.add_argument("--baud", type=int, default=115200, help="Serial baud rate")
    parser.add_argument("--progress-every", type=int, default=1000, help="Progress print interval in G-code lines")
    args = parser.parse_args()

    src = pathlib.Path(args.gcode).expanduser().resolve()
    if not src.is_file():
        print(f"Error: file not found: {src}", file=sys.stderr)
        return 1

    return stream_print(args.port, args.baud, src, args.progress_every)


if __name__ == "__main__":
    raise SystemExit(main())
