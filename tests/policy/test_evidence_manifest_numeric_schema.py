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

"""Reject JSON booleans/floats masquerading as integer evidence schema fields."""

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

GUARD = Path(__file__).resolve().parents[2] / "tools" / "evidence_guard.py"


def check(version, size, success):
    with tempfile.TemporaryDirectory(prefix="dniv-evidence-schema-") as directory:
        root = Path(directory)
        (root / "result.log").write_bytes(b"X")
        manifest = root / "manifest.json"
        manifest.write_text(json.dumps({
            "version": version,
            "files": [{"path": "result.log", "size": size,
                       "sha256": hashlib.sha256(b"X").hexdigest()}],
        }), encoding="utf-8")
        result = subprocess.run([
            sys.executable, str(GUARD), "verify", "--root", str(root),
            "--manifest", str(manifest),
        ], capture_output=True, text=True, check=False)
        if (result.returncode == 0) != success:
            raise AssertionError(
                f"evidence schema accepted invalid numeric type "
                f"version={version!r} size={size!r}: "
                f"rc={result.returncode} {result.stdout!r} {result.stderr!r}"
            )


check(1, 1, True)
check(True, 1, False)
check(1.0, 1, False)
check(1, True, False)
check(1, 1.0, False)
check("1", 1, False)
check(1, "1", False)
print("evidence manifest numeric schema regression passed")
