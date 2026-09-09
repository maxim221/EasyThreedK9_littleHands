"""Offline recovery records and conservative checks for a retained SD pause.

Telemetry is evidence, never an executable restart checkpoint. This module
does not derive G92 coordinates or a G-code tail from sampled SD byte counts.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import re
import tempfile
import time

import k9_marlin_sd as sdtool


class RecoveryError(RuntimeError):
    pass


def atomic_json(path: Path, data: dict) -> None:
    """A failed write must leave the last complete recovery record intact."""
    path.parent.mkdir(parents=True, exist_ok=True)
    name = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=path.name + ".", suffix=".tmp", delete=False) as f:
            name = f.name
            json.dump(data, f, ensure_ascii=False, indent=2, allow_nan=False)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(name, path)
    finally:
        if name and os.path.exists(name):
            os.unlink(name)


def source_identity(path: Path) -> dict:
    content = path.read_bytes()
    return {"path": str(path.resolve()), "size": len(content),
            "sha256": hashlib.sha256(content).hexdigest()}


def sd_progress(raw: str) -> tuple[int, int] | None:
    matches = re.findall(r"^\s*SD printing byte\s+(\d+)/(\d+)\s*$", raw, re.MULTILINE)
    if not matches:
        return None
    done, total = map(int, matches[-1])
    return (done, total) if total > 0 and 0 <= done <= total else None


def sd_name(value: str) -> str:
    return str(value).strip().replace("\\", "/").rsplit("/", 1)[-1].upper()


def selected_file(raw: str) -> str:
    matches = re.findall(r"^Current file:\s*(\S+)\s*$", raw, re.MULTILINE)
    return sd_name(matches[-1]) if matches else ""


def observe(record: dict, kind: str, raw: str, *, timestamp: float | None = None) -> bool:
    """Record real replies separately, including their individual sample times."""
    stamp = time.time() if timestamp is None else timestamp
    item = {"captured_ts": stamp, "raw": raw.strip()[-4000:]}
    if kind == "sd":
        progress = sd_progress(raw)
        if progress is None:
            return False
        item.update(byte=progress[0], total=progress[1])
    elif kind == "position":
        positions = sdtool.parse_positions(raw)
        if not positions or not all(math.isfinite(v) for v in positions[-1]):
            return False
        item["xyz"] = list(positions[-1])  # Raw G-code axes, never operator-display Y/Z.
    elif kind != "temperature":
        raise ValueError(kind)
    record.setdefault("samples", {})[kind] = item
    return True


def query(ser, command: str) -> str:
    return sdtool.send_line_wait_ok(ser, command, timeout_s=12.0)


def live_snapshot(ser, parse_temperature) -> dict:
    # No SD mount/select, coordinate declaration, or axis movement here.
    temp_raw = query(ser, "M105")
    filename = selected_file(query(ser, "M27 C"))
    progress = sd_progress(query(ser, "M27"))
    pose_raw = query(ser, "M114")
    poses = sdtool.parse_positions(pose_raw)
    temperatures = list(parse_temperature(temp_raw))
    if not filename or progress is None or not poses:
        raise RecoveryError("missing_state")
    if not all(math.isfinite(v) for v in poses[-1]):
        raise RecoveryError("missing_state")
    if any(temperatures[i] is None or not math.isfinite(temperatures[i]) for i in (0, 1)):
        raise RecoveryError("temperature")
    if (temperatures[3] is None) != (temperatures[4] is None):
        raise RecoveryError("temperature")
    return {"file": filename, "byte": progress[0], "total": progress[1],
            "xyz": list(poses[-1]), "temperature": temperatures, "captured_ts": time.time()}


def validate_resume(paused: dict, live: dict) -> None:
    """Fail closed on missing, changed, cooled, completed, or corrupt state."""
    if not paused or paused.get("confirmed") is not True:
        raise RecoveryError("no_pause")
    try:
        if not paused.get("file") or sd_name(paused["file"]) != sd_name(live["file"]):
            raise RecoveryError("file_changed")
        if (type(paused["byte"]) is not int or type(paused["total"]) is not int
                or not 0 < paused["byte"] < paused["total"]
                or (paused["byte"], paused["total"]) != (live["byte"], live["total"])):
            raise RecoveryError("progress_changed")
        if len(paused["xyz"]) != 3 or len(live["xyz"]) != 3:
            raise RecoveryError("position_changed")
        if any(not math.isfinite(float(a)) or not math.isfinite(float(b)) or abs(float(a) - float(b)) > 0.03
               for a, b in zip(paused["xyz"], live["xyz"])):
            raise RecoveryError("position_changed")
        before, now = paused["temperature"], live["temperature"]
        if len(before) != 6 or len(now) != 6:
            raise RecoveryError("temperature")
        if any(v is None or not math.isfinite(float(v)) for v in (before[1], now[0], now[1])):
            raise RecoveryError("temperature")
        hot, target, bed, bed_target = now[0], now[1], now[3], now[4]
        expected_bed = float(paused.get("expected_hotbed_target", before[4] or 0))
        if (not 180 <= target <= 260 or abs(target - before[1]) > 0.5
                or not target - 3 <= hot <= target + 8 or not 0 <= expected_bed <= 60):
            raise RecoveryError("temperature")
        if expected_bed > 0:
            if any(v is None or not math.isfinite(float(v)) for v in (before[4], bed, bed_target)):
                raise RecoveryError("temperature")
            if (abs(bed_target - expected_bed) > 0.5 or abs(bed_target - before[4]) > 0.5
                    or not bed_target - 2 <= bed <= bed_target + 5):
                raise RecoveryError("temperature")
        elif bed_target is not None and (not math.isfinite(float(bed_target)) or abs(bed_target) > 0.5):
            raise RecoveryError("temperature")
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        raise RecoveryError("missing_state") from exc


def restore_record(value) -> dict:
    if not isinstance(value, dict):
        return {}
    record = dict(value)
    samples = record.get("samples", {})
    record["samples"] = {k: v for k, v in samples.items() if isinstance(v, dict)} if isinstance(samples, dict) else {}
    paused = record.get("pause")
    try:
        if not isinstance(paused, dict):
            raise RecoveryError("no_pause")
        validate_resume(paused, paused)
        if sd_name(paused["file"]) != sd_name(str(record.get("file", ""))):
            raise RecoveryError("file_changed")
        stamp = paused.get("captured_ts")
        if not isinstance(stamp, (float, int)) or not 0 <= time.time() - stamp <= 48 * 3600:
            raise RecoveryError("missing_state")
    except (RecoveryError, TypeError, ValueError, AttributeError):
        record.pop("pause", None)
    return record


def capture_pause(port: str, baud: int, filename: str, parse_temperature) -> dict:
    with sdtool.open_serial(port, baud, reset_input=False) as ser:
        # Verify the file before pausing; M400 is used only AFTER acknowledged M25.
        if selected_file(query(ser, "M27 C")) != sd_name(filename):
            raise RecoveryError("file_changed")
        query(ser, "M25")
        sdtool.send_line_wait_ok(ser, "M400", timeout_s=60.0)
        paused = live_snapshot(ser, parse_temperature)
        if paused["file"] != sd_name(filename) or not 0 < paused["byte"] < paused["total"]:
            raise RecoveryError("missing_state")
        paused["confirmed"] = True
        return paused


def resume_retained_pause(port: str, baud: int, paused: dict, parse_temperature, consume_pause) -> str:
    with sdtool.open_serial(port, baud, reset_input=False) as ser:
        live = live_snapshot(ser, parse_temperature)
        validate_resume(paused, live)
        # Recheck position/SD cursor after the other queries. A running file is
        # never treated as a retained pause merely because one sample matched.
        progress = sd_progress(query(ser, "M27"))
        if progress != (paused["byte"], paused["total"]):
            raise RecoveryError("progress_changed")
        # Persist BEFORE M24: a timeout/crash may mean the command did execute.
        consume_pause()
        return query(ser, "M24")
