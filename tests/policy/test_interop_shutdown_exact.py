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

"""Reject a false-green interop PASS when guest/QEMU fails to shut down."""

from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[2]
source = (ROOT / "tests/lab/run-interop.sh").read_text()
helper = re.search(r"wait_candidate_shutdown\(\) \{\n.*?\n\}", source, re.S)
assert helper, "missing bounded guest shutdown helper"
assert 'if ! wait_candidate_shutdown "$CANDIDATE_PID" 60; then' in source
assert 'wait "$CANDIDATE_PID" 2>/dev/null || true' not in source

# Source-derived helper, tested as the parent shell of each background child.
for child, expected in (("(exit 0)", 0), ("(exit 42)", 42), ("sleep 5", 124)):
    script = (
        "set -euo pipefail\n" + helper.group() + "\n"
        + child + " &\nCANDIDATE_PID=$!\n"
        + "rc=0\nwait_candidate_shutdown \"$CANDIDATE_PID\" 1 || rc=$?\n"
        + "[[ $rc -eq " + str(expected) + " ]]\n"
        + "[[ $rc -ne 124 ]] || { kill \"$CANDIDATE_PID\" 2>/dev/null || true; wait \"$CANDIDATE_PID\" 2>/dev/null || true; }\n"
    )
    run = subprocess.run(["bash", "-c", script], capture_output=True, text=True,
                         timeout=8)
    assert run.returncode == 0, (child, run.returncode, run.stdout, run.stderr)
print("Interop guest shutdown exact-status and bounded-wait regression passed")
