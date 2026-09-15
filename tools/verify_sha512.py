#!/usr/bin/env python3
"""Verify a file against a SHA-512 sidecar without assuming one checksum syntax."""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
from pathlib import Path

HEX = r"[0-9a-fA-F]{128}"


def parse_expected(text: str) -> str:
    line = text.strip()
    if re.fullmatch(HEX, line):
        return line.lower()

    match = re.fullmatch(rf"({HEX})\s+\*?.+", line)
    if match:
        return match.group(1).lower()

    match = re.fullmatch(rf"SHA512 \(.+\) = ({HEX})", line)
    if match:
        return match.group(1).lower()

    raise ValueError("unrecognized SHA-512 sidecar format")


def digest(path: Path) -> str:
    h = hashlib.sha512()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("image", type=Path)
    parser.add_argument("sidecar", type=Path)
    args = parser.parse_args()

    try:
        expected = parse_expected(args.sidecar.read_text(encoding="ascii"))
        actual = digest(args.image)
    except (OSError, UnicodeError, ValueError) as exc:
        print(f"sha512 verify: {exc}", file=sys.stderr)
        return 1

    if actual != expected:
        print(f"sha512 verify: digest mismatch for {args.image}", file=sys.stderr)
        return 1

    print(f"sha512 verify: {args.image.name} OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
