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

"""Keep the E1 silence window between listener expiry and DR eligibility."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SMOKE = (ROOT / "tests/lab/dniv-smoke.sh").read_text(encoding="utf-8")
WIRE = (ROOT / "include/decnet_iv_wire.h").read_text(encoding="utf-8")
ETHERNET = (ROOT / "kernel/decnet/decnet_iv_ethernet.c").read_text(encoding="utf-8")


def one(pattern: str, text: str, label: str) -> int:
    matches = re.findall(pattern, text, re.MULTILINE)
    if len(matches) != 1:
        raise SystemExit(f"e1-silence regression: {label}: expected one match, saw {len(matches)}")
    return int(matches[0])


def main() -> int:
    hello_seconds = one(
        r"default_node_type=2 router_priority=64 hello_interval=(\d+)",
        SMOKE,
        "router hello interval",
    )
    silence_seconds = one(
        r"DNIV-E1-SILENT[^\n]*\n\s*sleep (\d+)",
        SMOKE,
        "silent interval",
    )
    listen_multiplier_ms = one(
        r"return interval \* (\d+)U;",
        WIRE,
        "listen multiplier",
    )
    dr_delay_seconds = one(
        r"^#define DNIV_DR_DELAY_SECONDS (\d+)U$",
        ETHERNET,
        "DR delay",
    )

    expiry_seconds = hello_seconds * listen_multiplier_ms / 1000.0
    dr_eligible_seconds = expiry_seconds + dr_delay_seconds

    if silence_seconds <= expiry_seconds:
        raise SystemExit(
            "e1-silence regression: silence must outlast listener expiry "
            f"({silence_seconds}s <= {expiry_seconds:.1f}s)"
        )
    if silence_seconds >= dr_eligible_seconds:
        raise SystemExit(
            "e1-silence regression: silence must end before DR eligibility "
            f"({silence_seconds}s >= {dr_eligible_seconds:.1f}s)"
        )

    print(
        "e1-silence regression passed: "
        f"expiry={expiry_seconds:.1f}s silence={silence_seconds}s "
        f"dr={dr_eligible_seconds:.1f}s"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
