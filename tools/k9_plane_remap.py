#!/usr/bin/env python3
"""
Remap standard slicer G-code for the EasyThreed K9 X/Z print plane.

This printer, on the currently chosen plain ECF firmware baseline, behaves as:
  - X: printhead left/right
  - Y: printhead up/down (true vertical axis)
  - Z: bed in/out (second bed-plane axis)

Normal slicers emit G-code assuming:
  - X/Y = print plane
  - Z   = layer height / vertical

To make a normal sliced file printable on this K9 baseline, swap Y and Z on
motion commands so that:
  - slicer Y -> printer Z
  - slicer Z -> printer Y

This tool intentionally only rewrites G-code text; it does not touch firmware.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

AXIS_RE = re.compile(r"([XYZEFIJR])([-+]?\d*\.?\d+)")
MOTION_PREFIXES = ("G0", "G1", "G2", "G3", "G5", "G92")
META_SWAP_PREFIXES = (";MINY:", ";MINZ:", ";MAXY:", ";MAXZ:")


def swap_yz_tokens(code: str) -> str:
    tokens: list[tuple[str, str]] = []
    last_end = 0

    for match in AXIS_RE.finditer(code):
        axis, value = match.group(1), match.group(2)
        tokens.append((axis, value))

    if not tokens:
        return code

    values = {axis: value for axis, value in tokens}
    if "Y" not in values and "Z" not in values:
        return code

    swapped_parts: list[str] = []

    for match in AXIS_RE.finditer(code):
        axis, value = match.group(1), match.group(2)
        swapped_parts.append(code[last_end:match.start()])
        if axis == "Y":
            swapped_parts.append(f"Z{value}")
        elif axis == "Z":
            swapped_parts.append(f"Y{value}")
        else:
            swapped_parts.append(f"{axis}{value}")
        last_end = match.end()

    swapped_parts.append(code[last_end:])
    return "".join(swapped_parts)


def remap_line(line: str) -> str:
    stripped = line.lstrip()

    for prefix in META_SWAP_PREFIXES:
        if stripped.startswith(prefix):
            alt_prefix = (
                prefix.replace("Y", "__TMP__")
                .replace("Z", "Y")
                .replace("__TMP__", "Z")
            )
            value = stripped.split(":", 1)[1]
            leading = line[: len(line) - len(stripped)]
            return f"{leading}{alt_prefix}{value}"

    if not stripped or stripped.startswith(";"):
        return line

    code, sep, comment = line.partition(";")
    code_stripped = code.strip()
    if not code_stripped:
        return line

    first_word = code_stripped.split(None, 1)[0].upper()
    if not first_word.startswith(MOTION_PREFIXES):
        return line

    remapped_code = swap_yz_tokens(code)
    if sep:
        return f"{remapped_code};{comment}"
    return remapped_code


def remap_file(src: Path, dst: Path) -> None:
    remapped = [
        ";REMAPPED_FOR_K9_XZ_PLANE\n",
        ";slicer Y -> printer Z, slicer Z -> printer Y\n",
    ]
    with src.open("r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            remapped.append(remap_line(line))
    dst.write_text("".join(remapped), encoding="utf-8")


def default_output_path(src: Path) -> Path:
    return src.with_name(f"{src.stem}_k9xz{src.suffix}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Remap standard G-code to the EasyThreed K9 X/Z print plane."
    )
    parser.add_argument("input", type=Path, help="Input G-code file")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Output file path (default: <input>_k9xz.gcode)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    src = args.input.expanduser().resolve()
    if not src.is_file():
        raise SystemExit(f"Input file not found: {src}")
    dst = (args.output.expanduser().resolve() if args.output else default_output_path(src))
    remap_file(src, dst)
    print(dst)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
