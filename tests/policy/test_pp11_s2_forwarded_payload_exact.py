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

"""Require PP11-S2 forwarding markers inside the declared DECnet packet."""

import ast
from pathlib import Path
import struct
import tempfile

ROOT = Path(__file__).resolve().parents[2]
MARKER = "DNIV-PP11-S2-VALID-session-DN70-1"
MAC = "aa:00:04:00:48:7c"


def actual_forwarder():
    source = (ROOT / "tests/lab/dniv_pp11_s2.py").read_text(encoding="utf-8")
    matches = [node for node in ast.parse(source).body
               if isinstance(node, ast.FunctionDef) and node.name == "forwarded_timestamps"]
    assert len(matches) == 1
    namespace = {"struct": struct, "Path": Path}
    exec(compile(ast.Module(body=matches, type_ignores=[]), "dniv_pp11_s2.py", "exec"),
         namespace)
    return namespace["forwarded_timestamps"]


def frame(where, mac=MAC, ether=b"\x60\x03", route_type=0x06, visit=1):
    route = bytearray(21)
    route[0] = route_type
    route[18] = visit
    trailer = b""
    if where == "inside":
        route += b"NSP" + MARKER.encode()
    elif where == "trailer":
        trailer = MARKER.encode()
    elif where == "split":
        route += MARKER[:4].encode()
        trailer = MARKER[4:].encode()
    elif where != "absent":
        raise AssertionError(where)
    return (b"\x00" * 6 + bytes.fromhex(mac.replace(":", "")) + ether +
            len(route).to_bytes(2, "little") + route + trailer)


def pcap(path, packet, endian, nanos):
    magic = {("<", False): b"\xd4\xc3\xb2\xa1",
             (">", False): b"\xa1\xb2\xc3\xd4",
             ("<", True): b"\x4d\x3c\xb2\xa1",
             (">", True): b"\xa1\xb2\x3c\x4d"}[(endian, nanos)]
    frac = 250_000_000 if nanos else 250_000
    path.write_bytes(magic + struct.pack(endian + "HHIIII", 2, 4, 0, 0, 65535, 1) +
                     struct.pack(endian + "IIII", 1, frac, len(packet), len(packet)) +
                     packet)


def main():
    count = 0
    fn = actual_forwarder()
    with tempfile.TemporaryDirectory() as temp:
        path = Path(temp) / "s2.pcap"
        for endian in ("<", ">"):
            for nanos in (False, True):
                for where in ("inside", "trailer", "split", "absent"):
                    pcap(path, frame(where), endian, nanos)
                    assert fn(path, MARKER, MAC) == ([1.25] if where == "inside" else []), (endian, nanos, where)
                    count += 1
                for candidate in (frame("inside", mac="02:01:02:03:04:05"),
                                  frame("inside", ether=b"\x08\x00"),
                                  frame("inside", route_type=0x01),
                                  frame("inside", visit=0)):
                    pcap(path, candidate, endian, nanos)
                    assert fn(path, MARKER, MAC) == []
                    count += 1
    print(f"PP11-S2 exact declared routed payload: {count} checks passed")


if __name__ == "__main__":
    main()
