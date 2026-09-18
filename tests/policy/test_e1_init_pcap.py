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

import importlib.util
import struct
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("dniv_lab", ROOT / "tests/lab/dniv_lab.py")
assert SPEC and SPEC.loader
LAB = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = LAB
SPEC.loader.exec_module(LAB)

A = "aa:00:04:00:46:7c"
B = "aa:00:04:00:47:7c"


def mb(text):
    return bytes(int(x, 16) for x in text.split(":"))


def hello(src, peer, listed):
    rs = peer + b"\x40" if listed else b""
    route = bytearray(27 + len(rs))
    route[0] = 0x0b
    route[18] = 8 + len(rs)
    route[26] = len(rs)
    route[27:] = rs
    frame = bytearray(16 + len(route))
    frame[0:6] = b"\xab\x00\x00\x03\x00\x00"
    frame[6:12] = src
    frame[12:14] = b"\x60\x03"
    frame[14:16] = len(route).to_bytes(2, "little")
    frame[16:] = route
    return bytes(frame)


def write_pcap(path, frames):
    out = bytearray(b"\xd4\xc3\xb2\xa1" + b"\x02\x00\x04\x00" +
                    b"\x00" * 8 + struct.pack("<II", 65535, 1))
    for i, frame in enumerate(frames):
        out += struct.pack("<IIII", i + 1, 0, len(frame), len(frame))
        out += frame
    path.write_bytes(out)


def main():
    a, b = mb(A), mb(B)
    with tempfile.TemporaryDirectory(prefix="dniv-e1-init-") as td:
        p = Path(td) / "x.pcap"
        write_pcap(p, [hello(a, b, False)])
        assert not LAB.pcap_router_init_seen(p, A, B)
        write_pcap(p, [hello(a, b, True)])
        assert not LAB.pcap_router_init_seen(p, A, B)
        write_pcap(p, [hello(a, b, False), hello(a, b, True)])
        assert LAB.pcap_router_init_seen(p, A, B)
        write_pcap(p, [hello(b, a, False), hello(b, a, True)])
        assert LAB.pcap_router_init_seen(p, A, B)
    print("e1 INIT PCAP regression passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
