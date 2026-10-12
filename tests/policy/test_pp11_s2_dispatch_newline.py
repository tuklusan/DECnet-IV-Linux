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

"""All PP-11 S2 dispatcher environment records must be newline-delimited."""

from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    workflow = (ROOT / ".github/workflows/repository-policy.yml").read_text(
        encoding="utf-8"
    )
    matches = [
        line.strip()
        for line in workflow.splitlines()
        if "printf 'VM_LAB_PP11_S2=vm-lab.yml:pp11s2:" in line
    ]
    if len(matches) != 2:
        raise AssertionError(f"expected full and targeted S2 dispatches: {len(matches)}")
    for line in matches:
        if r"1vcpu\\n'" in line:
            raise AssertionError("PP-11 S2 dispatcher emits a literal backslash-n")
        if r"1vcpu\n'" not in line:
            raise AssertionError("PP-11 S2 dispatcher missing newline conversion")

    with tempfile.TemporaryDirectory() as d:
        log = Path(d) / "dispatch.env"
        for line in matches:
            command = line.replace('"$DNIV_SCRATCH_DIR/dispatch.env"', repr(str(log)))
            subprocess.run(["bash", "-e", "-c", command], check=True, timeout=5)
        records = log.read_text(encoding="utf-8").splitlines(keepends=True)
        if len(records) != 2 or any(not x.endswith("\n") for x in records):
            raise AssertionError(f"PP-11 S2 records were concatenated: {records!r}")
    print("PP-11 S2 full/targeted dispatch records are newline-delimited")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
