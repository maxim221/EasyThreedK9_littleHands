#!/usr/bin/env python3
"""Command-line client for a running Little Hands Control Center."""

from __future__ import annotations

import argparse
import json
import socket
import sys
import time
from pathlib import Path

from k9_agent_control import MAX_REQUEST_BYTES, PROTOCOL_VERSION, default_socket_path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOG_DIR = PROJECT_ROOT / "monitor_logs"
DEFAULT_SOCKET = default_socket_path(PROJECT_ROOT)
DEFAULT_TOKEN = LOG_DIR / "little_hands_control.token"


def wire_value(value: object) -> object:
    """Convert argparse values to JSON-safe local API values."""
    if isinstance(value, Path):
        return str(value.expanduser().resolve())
    return value


def call(socket_path: Path, token_path: Path, command: str, arguments: dict[str, object]) -> dict[str, object]:
    token = token_path.read_text(encoding="ascii").strip()
    request = {
        "version": PROTOCOL_VERSION,
        "token": token,
        "command": command,
        "arguments": arguments,
    }
    payload = json.dumps(request, ensure_ascii=False).encode("utf-8") + b"\n"
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(20.0)
        client.connect(str(socket_path))
        client.sendall(payload)
        data = bytearray()
        while b"\n" not in data:
            chunk = client.recv(4096)
            if not chunk:
                break
            data.extend(chunk)
            if len(data) > MAX_REQUEST_BYTES:
                raise RuntimeError("response too large")
    return json.loads(bytes(data).split(b"\n", 1)[0].decode("utf-8"))


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--socket", type=Path, default=DEFAULT_SOCKET)
    result.add_argument("--token-file", type=Path, default=DEFAULT_TOKEN)
    sub = result.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    watch = sub.add_parser("watch")
    watch.add_argument("--interval", type=float, default=5.0)
    watch.add_argument("--count", type=int, default=0, help="0 means run until interrupted")
    sub.add_parser("sd-files")
    log_tail = sub.add_parser("log-tail")
    log_tail.add_argument("--lines", type=int, default=80)
    sub.add_parser("refresh-sd")
    select = sub.add_parser("select-sd")
    select.add_argument("file")
    upload = sub.add_parser("upload-gcode")
    upload.add_argument("path", type=Path)
    upload.add_argument("--dest")
    upload.add_argument("--confirm", required=True, choices=["write-printer-sd"])
    sub.add_parser("cancel")
    close = sub.add_parser("close")
    close.add_argument("--confirm", required=True, choices=["close-control-center"])
    heaters_off = sub.add_parser("heaters-off")
    heaters_off.add_argument("--confirm", required=True, choices=["safety-shutdown"])
    pause = sub.add_parser("pause")
    pause.add_argument("--confirm", required=True, choices=["operator-watching"])
    resume = sub.add_parser("resume")
    resume.add_argument("--confirm", required=True, choices=["power-axes-part-untouched"])
    stop = sub.add_parser("stop")
    stop.add_argument("--confirm", required=True, choices=["operator-watching"])
    jog = sub.add_parser("jog")
    jog.add_argument("axis", choices=["X", "Y", "Z"])
    jog.add_argument("distance", type=float)
    jog.add_argument("--confirm", required=True, choices=["operator-watching"])
    bed = sub.add_parser("hotbed")
    bed.add_argument("target", type=float)
    bed.add_argument("--confirm", choices=["operator-watching"])
    hotend = sub.add_parser("hotend")
    hotend.add_argument("target", type=float)
    hotend.add_argument("--confirm", choices=["operator-watching"])
    motor_off = sub.add_parser("motor-off")
    motor_off.add_argument("--confirm", required=True, choices=["invalidate-home"])
    save = sub.add_parser("save-start")
    save.add_argument("--confirm", required=True, choices=["physical-start-verified"])
    save.add_argument("--power-cycled", choices=["yes", "no"])
    start = sub.add_parser("start")
    start.add_argument("file", nargs="?")
    start.add_argument("--confirm", required=True, choices=["physical-start-and-watch"])
    start.add_argument("--power-cycled", choices=["yes", "no"])
    delete = sub.add_parser("delete-sd")
    delete.add_argument("file")
    delete.add_argument("--confirm", required=True, choices=["delete-this-file"])
    return result


def main() -> int:
    args = parser().parse_args()
    if args.command == "watch":
        interval = max(0.5, float(args.interval))
        count = max(0, int(args.count))
        emitted = 0
        try:
            while count == 0 or emitted < count:
                response = call(args.socket, args.token_file, "status", {})
                print(json.dumps(response, ensure_ascii=False, sort_keys=True), flush=True)
                emitted += 1
                if count == 0 or emitted < count:
                    time.sleep(interval)
        except KeyboardInterrupt:
            return 130
        except (OSError, ValueError, RuntimeError) as exc:
            print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), flush=True)
            return 2
        return 0
    arguments = {
        key: wire_value(value)
        for key, value in vars(args).items()
        if key not in {"socket", "token_file", "command"} and value is not None
    }
    try:
        response = call(args.socket, args.token_file, args.command, arguments)
    except (OSError, ValueError, RuntimeError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        return 2
    print(json.dumps(response, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if response.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
