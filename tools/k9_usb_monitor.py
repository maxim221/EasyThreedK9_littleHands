#!/usr/bin/env python3
"""
Minimal USB monitor for the EasyThreeD K9 on Marlin.

Shows live temperature telemetry and periodically asks Marlin for SD print
status so the user can keep an eye on a card-printed job from the PC.
"""

from __future__ import annotations

import argparse
import glob
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import serial


DEFAULT_PORTS = (
    "/dev/ttyUSB0",
    "/dev/ttyACM0",
    "/dev/ttyUSB1",
    "/dev/ttyACM1",
)


@dataclass
class MonitorConfig:
    port: str
    baud: int
    temp_interval: int
    sd_interval: float
    log_file: str | None
    log_max_bytes: int


def detect_port() -> str:
    for candidate in DEFAULT_PORTS:
        if glob.glob(candidate):
            return candidate
    raise FileNotFoundError("No /dev/ttyUSB* or /dev/ttyACM* port found for the printer.")


def timestamp() -> str:
    return time.strftime("%H:%M:%S")


def send_line(ser: serial.Serial, line: str) -> None:
    ser.write((line + "\n").encode("ascii"))
    ser.flush()


def sync_serial(ser: serial.Serial) -> None:
    # This printer often garbles the first command after reconnect.
    # Send a blank line and reset line numbering to settle the parser.
    for line in ("", "M110 N0"):
        send_line(ser, line)
        time.sleep(0.5)
        ser.read_all()


def append_log_line(log_handle, rendered: str, max_bytes: int) -> None:
    print(rendered, file=log_handle, flush=True)
    if log_handle.tell() <= max_bytes:
        return

    log_path = Path(log_handle.name)
    log_handle.close()

    data = log_path.read_bytes()
    if len(data) > max_bytes:
        data = data[-max_bytes:]
        newline = data.find(b"\n")
        if newline != -1 and newline + 1 < len(data):
            data = data[newline + 1:]
        log_path.write_bytes(data)

    reopened = log_path.open("a+", encoding="utf-8")
    return reopened


def print_lines(prefix: str, payload: str, log_handle = None, log_max_bytes: int = 0):
    for raw_line in payload.splitlines():
        line = raw_line.strip()
        if line:
            rendered = f"{timestamp()} {prefix} {line}"
            print(rendered)
            if log_handle:
                log_handle = append_log_line(log_handle, rendered, log_max_bytes) or log_handle
    return log_handle


def run_monitor(cfg: MonitorConfig) -> int:
    log_handle = None
    if cfg.log_file:
        log_path = Path(cfg.log_file).expanduser().resolve()
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_handle = log_path.open("a+", encoding="utf-8")

    with serial.Serial(cfg.port, cfg.baud, timeout=0.4) as ser:
        time.sleep(1.5)
        ser.reset_input_buffer()
        sync_serial(ser)

        send_line(ser, "M115")
        time.sleep(0.8)
        log_handle = print_lines("<", ser.read_all().decode("utf-8", "replace"), log_handle, cfg.log_max_bytes)

        send_line(ser, f"M155 S{cfg.temp_interval}")
        time.sleep(0.8)
        log_handle = print_lines("<", ser.read_all().decode("utf-8", "replace"), log_handle, cfg.log_max_bytes)

        started_line = f"{timestamp()} * Monitoring started on {cfg.port} at {cfg.baud} baud. Press Ctrl+C to stop."
        print(started_line)
        if log_handle:
            log_handle = append_log_line(log_handle, started_line, cfg.log_max_bytes) or log_handle
        next_sd = time.monotonic() + cfg.sd_interval

        try:
            while True:
                time.sleep(0.4)
                payload = ser.read_all().decode("utf-8", "replace")
                if payload:
                    log_handle = print_lines("<", payload, log_handle, cfg.log_max_bytes)

                now = time.monotonic()
                if now >= next_sd:
                    send_line(ser, "M27")
                    next_sd = now + cfg.sd_interval
        except KeyboardInterrupt:
            stopping_line = f"{timestamp()} * Stopping monitor..."
            print(stopping_line)
            if log_handle:
                log_handle = append_log_line(log_handle, stopping_line, cfg.log_max_bytes) or log_handle
            send_line(ser, "M155 S0")
            time.sleep(0.5)
            payload = ser.read_all().decode("utf-8", "replace")
            if payload:
                log_handle = print_lines("<", payload, log_handle, cfg.log_max_bytes)
        finally:
            if log_handle:
                log_handle.close()

    return 0


def parse_args() -> MonitorConfig:
    parser = argparse.ArgumentParser(description="Live USB monitor for the EasyThreeD K9 Marlin firmware.")
    parser.add_argument("--port", default=None, help="Serial port, e.g. /dev/ttyUSB0")
    parser.add_argument("--baud", type=int, default=115200, help="Serial baud rate")
    parser.add_argument("--temp-interval", type=int, default=2, help="Marlin M155 auto-report interval in seconds")
    parser.add_argument("--sd-interval", type=float, default=5.0, help="How often to query SD print status with M27")
    parser.add_argument("--log-file", default=None, help="Optional path to append monitor output")
    parser.add_argument("--log-max-bytes", type=int, default=10 * 1024 * 1024, help="Maximum log size in bytes (default: 10 MiB)")
    args = parser.parse_args()
    return MonitorConfig(
        port=args.port or detect_port(),
        baud=args.baud,
        temp_interval=args.temp_interval,
        sd_interval=args.sd_interval,
        log_file=args.log_file,
        log_max_bytes=args.log_max_bytes,
    )


if __name__ == "__main__":
    try:
        raise SystemExit(run_monitor(parse_args()))
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1)
