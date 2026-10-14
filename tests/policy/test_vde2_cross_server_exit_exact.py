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

"""A positive server bridge exit is required even when elapsed time looks sane."""

from pathlib import Path
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
path = ROOT / "tests/lab/prove-vde2-cross-runner.sh"
src = path.read_text()
reject = re.search(
    r"        if \(\( rc != 0 \)\); then\n"
    r".*?\n        fi", src, re.S,
)
assert reject, "missing nonzero server bridge rejection"
assert src.index("if (( rc == 124 || rc == 137 )); then") < reject.start()
assert reject.end() < src.index('kill -0 "$echo_pid" 2>/dev/null')
subprocess.run(["bash", "-n", str(path)], check=True)

with tempfile.TemporaryDirectory() as tmp:
    log = Path(tmp) / "relay.log"
    log.write_text("")
    for status, expected in ((0, 0), (42, 1), (143, 1), (124, 1)):
        case = (
            f"set -euo pipefail\nlog={log}\nsession=2\nrc={status}\n"
            + reject.group()
            + "\nprintf 'ACCEPTED\\n'\n"
        )
        result = subprocess.run(["bash", "-c", case],
                                capture_output=True, text=True)
        assert result.returncode == expected, (
            status, expected, result.returncode, result.stderr
        )
        assert ("ACCEPTED" in result.stdout) == (status == 0), status
print("VDE2 cross-runner server bridge exit-status regression passed")
