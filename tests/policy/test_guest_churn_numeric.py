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

"""Reject overlarge guest churn-cycle selectors before shell arithmetic wraps."""

from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "tests/lab/dniv-interop-smoke.sh"


def check() -> None:
    source = SOURCE.read_text()
    start = source.index('case "$churn_cycles" in')
    end = source.index('case "$scenario" in', start)
    block = source[start:end]
    cases = {
        "1": "1", "10000": "10000", "00001": "1",
        "00010000": "10000", "00000000000000000000001": "1",
        "0": None, "00000": None, "10001": None,
        "18446744073709551616": None,
        "99999999999999999999999999999999999999": None,
        "-1": None, "+1": None, "abc": None, "": None,
    }
    command = (
        "set -eu\nsession=local\nchurn_cycles=$1\n" + block +
        '\nprintf "VALID=%s\\n" "$churn_cycles"\n'
    )
    for arg, canonical in cases.items():
        result = subprocess.run(
            ["/bin/sh", "-c", command, "churn-fixture", arg],
            capture_output=True, text=True, timeout=5, check=False,
        )
        if canonical is None:
            if result.returncode != 1 or "reason=bad-churn-cycles" not in result.stdout:
                raise AssertionError(
                    f"invalid churn={arg!r} accepted rc={result.returncode} "
                    f"stdout={result.stdout!r} stderr={result.stderr!r}"
                )
        elif result.returncode != 0 or result.stdout != f"VALID={canonical}\n":
            raise AssertionError(
                f"valid churn={arg!r} incorrect rc={result.returncode} "
                f"stdout={result.stdout!r} stderr={result.stderr!r}"
            )
    print("guest interop churn-cycle integer bounds passed")


if __name__ == "__main__":
    check()
