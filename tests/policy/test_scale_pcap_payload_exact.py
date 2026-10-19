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

"""Scale PCAP markers must be inside declared DECnet data, never Ethernet padding."""
import importlib.util
from pathlib import Path
import struct
import sys
import tempfile

SOURCE = Path(__file__).resolve().parents[2] / "tests/lab/dniv_scale.py"
spec = importlib.util.spec_from_file_location("dniv_scale_under_test", SOURCE)
assert spec and spec.loader
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)

marker = "DNIV-E4-fixture-A3170-"
source = bytes.fromhex("aa000400ff00")


def capture(route: bytes, suffix: bytes = b"") -> bytes:
    frame = b"\xaa" * 6 + source + b"\x60\x03" + struct.pack("<H", len(route)) + route + suffix
    return (struct.pack("<IHHIIII", 0xa1b2c3d4, 2, 4, 0, 0, 65535, 1)
            + struct.pack("<IIII", 0, 0, len(frame), len(frame)) + frame)


route = bytearray(21)
route[0] = 0x06
route[18] = 1
with tempfile.TemporaryDirectory() as directory:
    path = Path(directory) / "scale.pcap"
    path.write_bytes(capture(route + marker.encode()))
    assert mod.marker_sources(path, marker) == [("aa:00:04:00:ff:00", 1)], (
        "valid long-route payload marker must be accepted")
    path.write_bytes(capture(route, marker.encode()))
    assert mod.marker_sources(path, marker) == [], (
        "marker in Ethernet trailing padding falsely counts as routed traffic")
    path.write_bytes(capture(route + marker.encode()[:5], marker.encode()[5:]))
    assert mod.marker_sources(path, marker) == [], (
        "marker straddling declared route length falsely counts as routed traffic")
print("scale PCAP route-boundary regression passed")
