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
        r"\s*diagnostic_completion_seconds=\d+\n"
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

    diagnostic_default = re.findall(
        r"^diagnostic_completion_seconds=(\d+)$", SCRIPT, re.MULTILINE
    )
    diagnostic_arm = re.findall(
        r'if \[\[ "\$host_arch" == aarch64 \]\]; then\n'
        r"\s*reference_ready_seconds=\d+\n"
        r"\s*diagnostic_completion_seconds=(\d+)\n"
        r"fi",
        SCRIPT,
        re.MULTILINE,
    )
    if diagnostic_default != ["60"]:
        raise SystemExit(
            "interop-ready regression: amd64/default diagnostic bound changed: "
            f"{diagnostic_default}"
        )
    if diagnostic_arm != ["180"]:
        raise SystemExit(
            "interop-ready regression: ARM64 diagnostic bound changed: "
            f"{diagnostic_arm}"
        )
    if int(diagnostic_arm[0]) <= int(diagnostic_default[0]):
        raise SystemExit(
            "interop-ready regression: ARM64 diagnostic bound must exceed default"
        )
    if int(diagnostic_arm[0]) > int(arm[0]):
        raise SystemExit(
            "interop-ready regression: diagnostic bound must not exceed reference-ready bound"
        )

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


    convergence_watches = [
        r'DNIV-INTEROP-READY-STOP[^\n]*"\$CANDIDATE_PID" "\$REFERENCE_PID"',
        r'DNIV-INTEROP-PASS[^\n]*"\$CANDIDATE_PID" "\$REFERENCE_PID"',
    ]
    for pattern in convergence_watches:
        if not re.search(pattern, SCRIPT):
            raise SystemExit(
                "interop-ready regression: candidate convergence must fail fast "
                "when the reference VM exits"
            )



    waiter = re.search(
        r"wait_candidate_marker\(\) \{(?P<body>.*?)\n\}",
        SCRIPT,
        re.DOTALL,
    )
    if waiter is None:
        raise SystemExit("interop-ready regression: wait_candidate_marker function missing")
    body = waiter.group("body")
    fail_check = body.find('grep -Fq "$fail_marker" "$reference_log"')
    success_check = body.find('grep -Fq "$marker" "$log"')
    if fail_check < 0 or success_check < 0 or fail_check > success_check:
        raise SystemExit(
            "interop-ready regression: reference failure marker must be checked "
            "before candidate success during convergence"
        )

    required_route20_diagnostics = [
        "route20-diagnostic",
        "route20-diagnostic-shim.c",
        "-rdynamic",
        "DNIV-ROUTE20-SIGNAL",
        "DNIV-ROUTE20-EVENT",
        "Route20 diagnostic session-bound patch anchor mismatch",
        "diag_launcher_pid=$!",
        "session-init-bounds=survived",
        "diag_deadline=$((SECONDS + diagnostic_completion_seconds))",
        "DNIV-REF-DIAG-DONE session=$session reference=route20",
        "wait_candidate_marker",
    ]
    combined = SCRIPT + "\n" + REFERENCE_IMAGE + "\n" + (
        ROOT / ".github/workflows/interop.yml"
    ).read_text(encoding="utf-8") + "\n" + (
        ROOT / "tests/lab/dniv-reference-peer.sh"
    ).read_text(encoding="utf-8") + "\n" + (
        ROOT / "tests/lab/route20-diagnostic-shim.c"
    ).read_text(encoding="utf-8")
    for fragment in required_route20_diagnostics:
        if fragment not in combined:
            raise SystemExit(
                "interop-ready regression: Route20 post-failure backtrace path incomplete: "
                f"{fragment!r}"
            )

    print("interop-ready regression passed: ready-amd64=180s ready-arm64=360s diag-amd64=60s diag-arm64=180s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
