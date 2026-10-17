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

"""Reject wrong disk-size bounds and parse positive decimal sizes without octal traps.

All cases stop at the missing base archive: no loop device, sudo, VM or network.
"""

import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
BUILDER = ROOT / "image/ubuntu-base/build-foundation.sh"
MISSING = ROOT / ".dniv-nonexistent-foundation-input.tar"
assert not MISSING.exists(), "disk-size regression needs a guaranteed absent tarball"

cases = (
    ("4294967296", True),
    ("5000000000", True),
    ("05000000000", True),
    ("08000000000", True),
    ("00000008000000000", True),
    ("4294967295", False),
    ("0", False),
    ("00000000", False),
    ("bad", False),
    ("5GB", False),
)
for decimal_size, valid in cases:
    env = dict(os.environ, DNIV_DISK_BYTES=decimal_size)
    result = subprocess.run(
        ["bash", str(BUILDER), "amd64", str(MISSING),
         str(ROOT / ".dniv-unwritten.qcow2"), str(ROOT / ".dniv-unwritten-boot")],
        cwd=ROOT, env=env, capture_output=True, text=True, timeout=10,
        check=False,
    )
    diagnostic = result.stderr
    assert result.returncode == 2, (decimal_size, result.returncode, diagnostic)
    assert "value too great for base" not in diagnostic, (decimal_size, diagnostic)
    if valid:
        assert "base tarball not found:" in diagnostic, (decimal_size, diagnostic)
        assert "DNIV_DISK_BYTES must be" not in diagnostic, (decimal_size, diagnostic)
    else:
        assert "DNIV_DISK_BYTES must be" in diagnostic, (decimal_size, diagnostic)
        assert "base tarball not found:" not in diagnostic, (decimal_size, diagnostic)
print("foundation disk-size decimal/leading-zero/bounds regression passed")
