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

"""Run original interop input guards without requiring networking or QEMU."""

from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
source = (ROOT / "tests/lab/run-interop.sh").read_text(encoding="utf-8")
start = source.index("peer_segsize=${DNIV_INTEROP_PEER_SEGMENT_SIZE:-0}")
end = source.index("reserved_proof=0", start)
guards = source[start:end]

cases = (
    ("0", "16", True),
    ("64", "1", True),
    ("128", "10000", True),
    ("563", "9999", True),
    ("63", "16", False),
    ("564", "16", False),
    ("1000", "16", False),
    ("18446744073709551616", "16", False),
    ("18446744073709551617", "16", False),
    ("08", "16", False),
    ("000", "16", False),
    ("0", "0", False),
    ("0", "08", False),
    ("0", "010", False),
    ("0", "10001", False),
    ("0", "18446744073709551616", False),
    ("0", "18446744073709551617", False),
    ("0", "9999999999999999999999999999999999", False),
)
for segment, churn, valid in cases:
    run = subprocess.run(
        ["bash", "-c", "set -euo pipefail\n" + guards + "\nprintf 'GUARDS-ACCEPTED\\n'\n"],
        env={"DNIV_INTEROP_PEER_SEGMENT_SIZE": segment,
             "DNIV_INTEROP_CHURN_CYCLES": churn,
             "PATH": "/usr/bin:/bin"},
        text=True, capture_output=True, timeout=3,
    )
    accepted = run.returncode == 0 and "GUARDS-ACCEPTED" in run.stdout
    assert accepted == valid, (segment, churn, run.returncode, run.stdout, run.stderr)
print("Source-derived interop segment and churn numeric bound checks pass")
