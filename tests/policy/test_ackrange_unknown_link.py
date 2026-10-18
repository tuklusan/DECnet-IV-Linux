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

"""Exercise unknown-NSP-link DC with an explicit candidate MAC, no network access."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import struct


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "tests/lab/inject-nsp-ackrange.py"


class FakeSniff:
    def __init__(self, frame: bytes):
        self.frame = frame

    def recv(self, count: int) -> bytes:
        return self.frame


def dc_frame(candidate: bytes, src_link: bytes, dst_link: bytes, reason: int) -> bytes:
    nsp = b"\x48" + src_link + dst_link + struct.pack("<H", reason)
    route = b"\x02" + struct.pack("<H", 0x7c46) + struct.pack("<H", 0x7c47) + b"\x00" + nsp
    return b"\x00" * 6 + candidate + b"\x60\x03" + struct.pack("<H", len(route)) + route


def main() -> int:
    spec = importlib.util.spec_from_file_location("dniv_ackrange_inject", SOURCE)
    if spec is None or spec.loader is None:
        raise SystemExit("ack-range regression: cannot load actual source")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    candidate = bytes.fromhex("aa000400467c")
    dst_link, src_link = b"\x11\x22", b"\x33\x44"
    for label in ("Data", "Connect Confirm", "Disconnect Initiate",
                  "Interrupt", "Link Service"):
        module.expect_no_link(
            FakeSniff(dc_frame(candidate, src_link, dst_link, 41)),
            dst_link, src_link, candidate, label,
        )
    try:
        module.expect_no_link(
            FakeSniff(dc_frame(candidate, src_link, dst_link, 42)),
            dst_link, src_link, candidate, "Data",
        )
    except RuntimeError as exc:
        if "reason=42, expected 41" not in str(exc):
            raise SystemExit("ack-range regression: wrong rejection reason") from exc
    else:
        raise SystemExit("ack-range regression: incorrect DC reason accepted")
    print("ack-range unknown-link exact-source regression passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
