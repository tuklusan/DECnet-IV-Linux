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

"""Bad guest flow-proof selectors must fail before module or peer activity."""

from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "tests/lab/dniv-interop-smoke.sh"


def verify():
    source = SOURCE.read_text()
    first = source.index('case "$timer_proof" in\n')
    last = source.index('case "$scenario" in\n', first)
    guard = source[first:last]
    for flow, should_pass in (("0", True), ("1", True), ("invalid", False)):
        # Executes the actual guest validation block, not a reconstructed
        # condition. Never invokes modprobe, networks, or changes a guest.
        setup = ("session=selector-test\n"
                 "timer_proof=0\nreserved_proof=0\npp11_pressure=0\n"
                 "churn_cycles=16\nflow_proof=" + flow + "\n")
        result = subprocess.run(["sh", "-eu", "-c", setup + guard],
                                text=True, capture_output=True, timeout=5)
        if should_pass:
            assert result.returncode == 0, (flow, result.stderr, result.stdout)
        else:
            assert result.returncode != 0, "invalid flow-proof selector accepted"
            assert "reason=bad-flow-proof" in result.stdout, result.stdout
    print("interop flow-proof selector guard passed")


if __name__ == "__main__":
    verify()
