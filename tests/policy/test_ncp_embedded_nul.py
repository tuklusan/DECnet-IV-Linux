#!/usr/bin/env python3
# ============================================================================
# Copyright (c) 2026 Supratim Sanyal of SANYALnet Labs.
# Proprietary rights reserved except as expressly licensed herein.
#
# DECnet-IV-Linux
# This file is governed by the SANYALnet Labs Non-Commercial License in the
# root LICENSE file. Non-Commercial use is permitted; Commercial Use and use
# for AI/ML model training are prohibited unless separately authorized.
#
# Attribution is required: "Based on original work by Supratim Sanyal of
# SANYALnet Labs." See LICENSE for full terms, warranty disclaimer, termination,
# patent, trademark, and governing-law provisions.
# ============================================================================

"""Reject an embedded NUL in an NCP physical command line before dispatch."""

import os
import shlex
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "userspace/ncp/ncp.c"


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="dniv-ncp-nul-") as directory:
        binary = Path(directory) / "ncp"
        subprocess.run(shlex.split(os.environ.get("CC", "cc")) + [
            "-I" + str(ROOT / "include/uapi"),
            "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror",
            str(SOURCE), "-o", str(binary)
        ], check=True, timeout=60)
        for command in (b"help\x00zero executor\n", b"quit\x00show executor\n",
                        b" ".join([b"help"] * 17) + b"\n"):
            result = subprocess.run([str(binary)], input=command,
                                    capture_output=True, timeout=10)
            expected_error = (b"ncp: embedded NUL in command line\n"
                              if b"\x00" in command else b"ncp: too many words\n")
            if result.returncode != 2 or result.stdout or result.stderr != expected_error:
                raise SystemExit(f"NCP accepted hidden command prefix {command!r}: "
                                 f"{result.returncode} {result.stdout!r} "
                                 f"{result.stderr!r}")
        valid = subprocess.run([str(binary)], input=b"help\n",
                               capture_output=True, timeout=10)
        if valid.returncode or not valid.stdout.startswith(b"usage:"):
            raise SystemExit("NCP rejected valid help command")
        selftest = subprocess.run([str(binary), "--selftest"],
                                  capture_output=True, timeout=10)
        if selftest.returncode:
            raise SystemExit("NCP internal selftest failed")
    print("NCP rejects embedded NUL before command dispatch")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
