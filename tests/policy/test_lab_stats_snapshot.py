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

"""Regression test for coherent E1 counter sampling under concurrent hellos."""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

override = os.environ.get("DNIV_TEST_ROOT")
ROOT = Path(override) if override else Path(__file__).resolve().parents[2]
SMOKE = ROOT / "tests/lab/dniv-smoke.sh"


def fake_dnctl(directory: Path, coherent_after: int | None) -> tuple[Path, Path]:
    counter = directory / "count"
    script = directory / "dnctl"
    threshold = coherent_after if coherent_after is not None else 999999
    script.write_text(
        "#!/bin/sh\n"
        "set -eu\n"
        f"counter={counter!s}\n"
        "n=0\n"
        "[ ! -f \"$counter\" ] || n=$(cat \"$counter\")\n"
        "n=$((n + 1))\n"
        "printf '%s\\n' \"$n\" > \"$counter\"\n"
        f"if [ \"$n\" -lt {threshold} ]; then\n"
        "  routing=4\n"
        "  hello=5\n"
        "else\n"
        "  routing=6\n"
        "  hello=5\n"
        "fi\n"
        "cat <<EOF\n"
        "Routing frames received = $routing\n"
        "Routing bytes received  = 100\n"
        "Hello frames received   = $hello\n"
        "Hello frames sent       = 2\n"
        "Hello errors            = 0\n"
        "Adjacencies up          = 1\n"
        "Adjacencies down        = 0\n"
        "EOF\n",
        encoding="utf-8",
    )
    script.chmod(0o755)
    return script, counter


def run_selftest(fake: Path, tries: int) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["DNIV_DNCTL"] = str(fake)
    return subprocess.run(
        ["sh", str(SMOKE), "--stats-selftest", str(tries)],
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        directory = Path(tmp)
        fake, counter = fake_dnctl(directory, coherent_after=2)
        result = run_selftest(fake, 4)
        if result.returncode != 0 or result.stdout.strip() != "6 5 2":
            raise SystemExit(
                "lab-stats regression: transient inconsistent sample was not retried: "
                f"rc={result.returncode} stdout={result.stdout!r} stderr={result.stderr!r}"
            )
        if counter.read_text(encoding="utf-8").strip() != "2":
            raise SystemExit("lab-stats regression: expected exactly two counter snapshots")

    with tempfile.TemporaryDirectory() as tmp:
        directory = Path(tmp)
        fake, counter = fake_dnctl(directory, coherent_after=None)
        result = run_selftest(fake, 3)
        if result.returncode == 0:
            raise SystemExit("lab-stats regression: persistent inconsistent counters must fail")
        if counter.read_text(encoding="utf-8").strip() != "3":
            raise SystemExit("lab-stats regression: retry bound was not enforced")

    print("lab-stats regression passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
