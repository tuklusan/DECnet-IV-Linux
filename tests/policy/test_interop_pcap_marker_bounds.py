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

"""Rootless exact-PCAP negative proof for run-interop host marker counting."""
import pathlib
import re
import struct
import subprocess
import sys
import tempfile

source = pathlib.Path(__file__).resolve().parents[1] / "lab" / "run-interop.sh"
text = source.read_text()
function = text.split("pcap_source_marker_count() {", 1)[1].split("\n}\n", 1)[0]
match = re.search(r"<<'PY'\n(.*?)\nPY", function, re.S)
assert match is not None
program = match.group(1)
src = bytes.fromhex("aa000400463d")
marker = b"DNIV-LOSS-PROBE"
nsp = b"\x00\x01\x00\x02\x00\x00\x00" + marker
routing = b"\x06" + bytes(20) + nsp
eth = bytes.fromhex("ab0000030000") + src + bytes.fromhex("6003")
def frame(payload, extra=b""):
    return eth + len(payload).to_bytes(2, "little") + payload + extra
def capture(*frames):
    pcap = bytes.fromhex("d4c3b2a102000400") + bytes(16)
    for item in frames:
        pcap += struct.pack("<IIII", 0, 0, len(item), len(item)) + item
    return pcap
with tempfile.TemporaryDirectory() as folder:
    path = pathlib.Path(folder) / "test.pcap"
    cases = {
        "valid": (frame(routing), 1),
        "trailing-padding": (frame(routing.replace(marker, b"X" * len(marker)), marker), 0),
        "boundary-split": (frame(routing[:-4], routing[-4:]), 0),
        "wrong-source": (frame(routing).replace(src, bytes(6), 1), 0),
        "non-data-control": (frame(routing.replace(b"\x06" + bytes(20) + b"\x00", b"\x06" + bytes(20) + b"\x18", 1)), 0),
    }
    for name, (packet, expected) in cases.items():
        path.write_bytes(capture(packet))
        run = subprocess.run([sys.executable, "-c", program, str(path), src.hex(), marker.decode()],
                             capture_output=True, text=True, check=True)
        got = int(run.stdout.strip())
        assert got == expected, (name, got, expected)
print("source pcap marker bounds regression passed")
