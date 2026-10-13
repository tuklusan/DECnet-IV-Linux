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

"""Require the PP-12 post-unload check to detect a still loaded kernel module."""

import pathlib
import re
import subprocess
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
smoke = (ROOT / "tests/lab/dniv-pp12-smoke.sh").read_text(encoding="utf-8")
matches = re.findall(r"grep -Eq '([^']+)' /proc/modules \|\| fail module-still-loaded-1", smoke)
assert len(matches) == 1, "PP-12 post-unload check must be a real regex assertion"
pattern = matches[0]

with tempfile.TemporaryDirectory(prefix="dniv-pp12-module-") as tmp:
    module_list = pathlib.Path(tmp) / "modules"
    for body, expected in (
        ("decnet_iv 123 0 - Live 0x0\\n", True),
        ("other 123 0 - Live 0x0\\ndecnet_iv 123 0 - Live 0x0\\n", True),
        ("other_decnet_iv 123 0 - Live 0x0\\n", False),
        ("other 123 0 - Live 0x0\\n", False),
        ("", False),
    ):
        module_list.write_text(body.replace("\\n", "\n"), encoding="utf-8")
        match = subprocess.run(["grep", "-Eq", pattern, str(module_list)], check=False)
        assert (match.returncode == 0) is expected, (body, match.returncode)
print("PP-12 module-unload assertion policy regression passed")
