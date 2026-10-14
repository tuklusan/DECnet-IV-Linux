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

"""Keep the standalone VM scale scripts directly executable in source releases."""

from pathlib import Path
import stat

ROOT = Path(__file__).resolve().parents[2]
for relative in ("tests/lab/dniv_scale.py", "tests/lab/dniv_scale16_distributed.py"):
    path = ROOT / relative
    contents = path.read_bytes()
    if not contents.startswith(b"#!/usr/bin/env python3\n"):
        raise AssertionError(f"scale source missing executable shebang: {relative}")
    actual_mode = stat.S_IMODE(path.stat().st_mode)
    if actual_mode != 0o755:
        raise AssertionError(
            f"source release driver mode {actual_mode:o} != 755: {relative}"
        )

print("scale 4/8/16 and distributed VM drivers remain directly executable")

