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

"""Execute actual guest E4 and PP11-S2 probe-count integer validation."""

from pathlib import Path
import subprocess

SOURCE = Path(__file__).resolve().parents[1] / "lab/dniv-smoke.sh"


def check() -> None:
    source = SOURCE.read_text()
    start = source.index("positive_decimal_count() {")
    end = source.index("\n}\n", start) + 2
    helper = source[start:end]
    assert 'probe_count=$(positive_decimal_count "' in source
    assert 'count=$(positive_decimal_count "' in source
    cases = {
        "1": "1", "180": "180", "1200": "1200",
        "9999": "9999", "10000": "10000",
        "000001": "1", "00010000": "10000",
        "0": None, "00000": None, "": None,
        "10001": None, "18446744073709551616": None,
        "99999999999999999999999999": None,
        "-1": None, "+2": None, "abc": None,
    }
    for raw, expected in cases.items():
        command = "set -eu\n" + helper + '\npositive_decimal_count "$1"\n'
        result = subprocess.run(
            ["/bin/sh", "-c", command, "probe-fixture", raw],
            capture_output=True, text=True, timeout=5, check=False,
        )
        if expected is None:
            assert result.returncode == 1 and not result.stdout, (
                raw, result.returncode, result.stdout, result.stderr
            )
        else:
            assert result.returncode == 0 and result.stdout == f"{expected}\n", (
                raw, result.returncode, result.stdout, result.stderr
            )
    print("guest E4/PP11-S2 count bounds pass")


if __name__ == "__main__":
    check()
