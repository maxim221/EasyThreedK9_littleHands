#!/usr/bin/env python3
"""Capture camera snapshots when Little Hands print progress crosses 5% steps."""

from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
import time
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LOG = PROJECT_ROOT / "monitor_logs" / "little_hands_runtime.log"
LATEST_WATCH = PROJECT_ROOT / "monitor_logs" / "print_watch" / "latest_zeroBottom_watch.txt"
TELEMETRY_RE = re.compile(
    r"(?P<clock>\d{2}:\d{2}:\d{2})\s+TELEMETRY\s+"
    r"file=(?P<file>\S+)\s+progress=(?P<progress>\d+(?:\.\d+)?)%\s+"
    r"temp=(?P<temp>[-\d.]+)/(?:[-\d.]+)"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--log", type=Path, default=DEFAULT_LOG)
    parser.add_argument("--camera", default="/dev/video2")
    parser.add_argument("--video-size", default="1280x720")
    parser.add_argument("--out-dir", type=Path)
    parser.add_argument("--poll-seconds", type=float, default=1.0)
    return parser.parse_args()


def default_out_dir() -> Path:
    try:
        latest = LATEST_WATCH.read_text(encoding="utf-8").strip()
    except OSError:
        latest = ""
    base = Path(latest) if latest else PROJECT_ROOT / "monitor_logs" / "print_watch"
    if not base.is_absolute():
        base = PROJECT_ROOT / base
    return base / "progress_5pct"


def parse_telemetry(line: str) -> dict[str, object] | None:
    match = TELEMETRY_RE.search(line)
    if not match:
        return None
    return {
        "clock": match.group("clock"),
        "file": match.group("file"),
        "progress": float(match.group("progress")),
        "temp": float(match.group("temp")),
        "line": line.rstrip(),
    }


def capture(args: argparse.Namespace, out_dir: Path, label: str, telemetry: dict[str, object]) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    progress = float(telemetry["progress"])
    filename = f"{stamp}_{label}_progress_{progress:05.1f}.jpg"
    path = out_dir / filename
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "v4l2",
            "-input_format",
            "mjpeg",
            "-video_size",
            args.video_size,
            "-i",
            args.camera,
            "-frames:v",
            "1",
            str(path),
        ],
        check=True,
    )
    manifest = out_dir / "manifest.jsonl"
    with manifest.open("a", encoding="utf-8") as handle:
        handle.write(
            json.dumps(
                {
                    "captured_at": datetime.now().isoformat(timespec="seconds"),
                    "label": label,
                    "image": str(path),
                    **telemetry,
                },
                ensure_ascii=False,
            )
            + "\n"
        )
    return path


def next_five_percent(progress: float) -> int:
    return int(math.floor(progress / 5.0) * 5 + 5)


def main() -> int:
    args = parse_args()
    log_path = args.log.expanduser().resolve()
    out_dir = (args.out_dir.expanduser().resolve() if args.out_dir else default_out_dir())

    latest: dict[str, object] | None = None
    if log_path.exists():
        with log_path.open("r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                parsed = parse_telemetry(line)
                if parsed:
                    latest = parsed

    if latest is None:
        latest = {
            "clock": "",
            "file": "-",
            "progress": 0.0,
            "temp": 0.0,
            "line": "no telemetry seen yet",
        }

    current = capture(args, out_dir, "current", latest)
    threshold = next_five_percent(float(latest["progress"]))
    print(f"progress watch: current={latest['progress']}% next={threshold}% image={current}", flush=True)

    with log_path.open("r", encoding="utf-8", errors="replace") as handle:
        handle.seek(0, 2)
        while threshold <= 100:
            line = handle.readline()
            if not line:
                time.sleep(args.poll_seconds)
                continue
            parsed = parse_telemetry(line)
            if not parsed:
                continue
            progress = float(parsed["progress"])
            if progress < threshold:
                continue
            label = f"{threshold:03d}pct"
            path = capture(args, out_dir, label, parsed)
            print(f"progress watch: crossed {threshold}% at {progress:.1f}% image={path}", flush=True)
            threshold = next_five_percent(progress)
            if threshold <= progress:
                threshold = int(math.floor(progress / 5.0) * 5 + 5)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
