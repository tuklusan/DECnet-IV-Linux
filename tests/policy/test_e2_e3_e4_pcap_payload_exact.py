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

"""Count E2/E3/E4 forwarding markers only inside declared DECnet payload."""

import ast
from pathlib import Path
import struct
import tempfile

ROOT = Path(__file__).resolve().parents[2]
MARKER = "DNIV-EVIDENCE-7"
ROUTER_MAC = "52:54:02:00:00:72"
ROUTER_BYTES = bytes.fromhex(ROUTER_MAC.replace(":", ""))


def source_function(filename, function):
    parsed = ast.parse((ROOT / "tests/lab" / filename).read_text(encoding="utf-8"),
                       filename=filename)
    functions = [node for node in parsed.body
                 if isinstance(node, ast.FunctionDef) and node.name == function]
    assert len(functions) == 1, (filename, function)
    namespace = {"struct": struct, "Path": Path}
    exec(compile(ast.Module(body=functions, type_ignores=[]), filename, "exec"),
         namespace)
    return namespace[function]


def packet(position, long_type=0x06, ether_type=b"\x60\x03",
           link_source=ROUTER_BYTES, marker=MARKER.encode()):
    route = bytearray(21)
    route[0] = long_type
    route[18] = 1
    route[7:9] = ((31 << 10) | 70).to_bytes(2, "little")
    route[15:17] = ((31 << 10) | 99).to_bytes(2, "little")
    if position == "payload":
        route += b"prefix" + marker + b"suffix"
        trailer = b""
    elif position == "trailer":
        trailer = marker
    elif position == "split":
        route += marker[:4]
        trailer = marker[4:]
    elif position == "absent":
        trailer = b"none"
    else:
        raise AssertionError(position)
    return (b"\x00\x11\x22\x33\x44\x55" + link_source + ether_type +
            len(route).to_bytes(2, "little") + bytes(route) + trailer)


def write_pcap(path, frames, endian="<"):
    magic = b"\xd4\xc3\xb2\xa1" if endian == "<" else b"\xa1\xb2\xc3\xd4"
    raw = bytearray(magic + struct.pack(endian + "HHIIII", 2, 4, 0, 0, 65535, 1))
    for frame in frames:
        raw += struct.pack(endian + "IIII", 1, 0, len(frame), len(frame))
        raw += frame
    path.write_bytes(raw)


def main():
    e2 = source_function("dniv_e2.py", "pcap_forwarded_long_visits")
    e2_rts = source_function("dniv_e2.py", "pcap_rts_returns")
    e3 = source_function("dniv_e3.py", "marker_sources")
    e4 = source_function("dniv_e4.py", "marker_sources")
    cases = 0
    with tempfile.TemporaryDirectory() as root:
        file = Path(root) / "evidence.pcap"
        for endian in ("<", ">"):
            for position in ("payload", "trailer", "split", "absent"):
                write_pcap(file, [packet(position)], endian)
                expected = [1] if position == "payload" else []
                assert e2(file, MARKER) == expected, ("E2", endian, position)
                sources = [(ROUTER_MAC, 1)] if position == "payload" else []
                for label, func in (("E3", e3), ("E4", e4)):
                    assert func(file, MARKER) == sources, (label, endian, position)
                    cases += 1
                write_pcap(file, [packet(position, long_type=0x16)], endian)
                assert e2_rts(file, MARKER, ROUTER_MAC, (31 << 10) | 70,
                              (31 << 10) | 99) == expected, ("E2-RTS", endian, position)
                cases += 2
            for kind in ("ether", "route"):
                frame = (packet("payload", ether_type=b"\x08\x00") if kind == "ether"
                         else packet("payload", long_type=0x01))
                write_pcap(file, [frame], endian)
                assert e2(file, MARKER) == []
                assert e3(file, MARKER) == []
                assert e4(file, MARKER) == []
                cases += 3
        write_pcap(file, [packet("payload", long_type=0x16,
                                 link_source=b"\x02\x01\x02\x03\x04\x05")])
        assert e2_rts(file, MARKER, ROUTER_MAC, (31 << 10) | 70,
                      (31 << 10) | 99) == []
        cases += 1
    print(f"E2/E3/E4 exact declared-payload PCAP evidence passed: {cases} checks")


if __name__ == "__main__":
    main()
