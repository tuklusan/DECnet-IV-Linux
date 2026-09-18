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

"""Regression for bounded architecture-specific interop reference readiness."""

from __future__ import annotations

import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (ROOT / "tests/lab/run-interop.sh").read_text(encoding="utf-8")
REFERENCE_IMAGE = (ROOT / "tests/lab/prepare-reference-image.sh").read_text(encoding="utf-8")


def main() -> int:
    default = re.findall(r"^reference_ready_seconds=(\d+)$", SCRIPT, re.MULTILINE)
    arm = re.findall(
        r'if \[\[ "\$host_arch" == aarch64 \]\]; then\n'
        r"\s*reference_ready_seconds=(\d+)\n"
        r"fi",
        SCRIPT,
        re.MULTILINE,
    )
    if default != ["180"]:
        raise SystemExit(f"interop-ready regression: amd64/default bound changed: {default}")
    if arm != ["360"]:
        raise SystemExit(f"interop-ready regression: ARM64 bound changed: {arm}")
    if int(arm[0]) <= int(default[0]):
        raise SystemExit("interop-ready regression: ARM64 bound must exceed default")
    if int(arm[0]) > 420:
        raise SystemExit("interop-ready regression: ARM64 reference-ready bound is excessive")

    executable_paths = [
        ROOT / "tests/lab/prepare-reference-image.sh",
        ROOT / "tests/lab/run-interop.sh",
    ]
    for executable_path in executable_paths:
        if not os.access(executable_path, os.X_OK):
            raise SystemExit(
                "interop-ready regression: interop harness executable bit missing: "
                f"{executable_path.relative_to(ROOT)}"
            )

    required_service_fragments = [
        "After=multi-user.target systemd-udev-settle.service",
        "ExecStartPre=/bin/sleep 60",
        "WantedBy=graphical.target",
        "graphical.target.wants/dniv-reference-peer.service",
    ]
    for fragment in required_service_fragments:
        if fragment not in REFERENCE_IMAGE:
            raise SystemExit(
                "interop-ready regression: reference guest must idle for 60 seconds "
                f"after multi-user boot before peer startup; missing {fragment!r}"
            )

    uses = re.findall(
        r'DNIV-REF-READY[^\n]*" "\$reference_ready_seconds" "\$REFERENCE_PID"',
        SCRIPT,
    )
    if len(uses) != 2:
        raise SystemExit(
            "interop-ready regression: both initial and restart reference boots "
            f"must use the bounded architecture value; saw {len(uses)}"
        )
    if re.search(r'DNIV-REF-READY[^\n]*" [0-9]+ "\$REFERENCE_PID"', SCRIPT):
        raise SystemExit("interop-ready regression: hardcoded readiness wait remains")

    print("interop-ready regression passed: amd64=180s arm64=360s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
