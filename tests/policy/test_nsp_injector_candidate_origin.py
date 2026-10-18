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

"""Ensure raw NSP fault injectors never credit reference-origin packet markers."""

import importlib.util
from pathlib import Path
import struct

LAB = Path(__file__).resolve().parents[1] / "lab"
CANDIDATE = bytes.fromhex("aa000400467c")
REFERENCE = bytes.fromhex("aa000400477c")
TAG = b"DNIV-ACKRANGE-PROBE"


def frame(source: bytes) -> bytes:
    nsp = b"\x60\x01\x00\x02\x00\x80\x00" + TAG
    route = b"\x02\x01\x00\x02\x00\x00" + nsp
    return (
        REFERENCE + source + struct.pack("!H", 0x6003)
        + struct.pack("<H", len(route)) + route
    )


def check() -> None:
    for name in ("inject-nsp-ackrange", "inject-nsp-flow", "inject-nsp-intflow"):
        path = LAB / (name + ".py")
        source = path.read_text(encoding="utf-8")
        assert "nsp_payload(sniff.recv(4096))" not in source, name
        assert "candidate_nsp(sniff.recv(4096), candidate)" in source, name
        spec = importlib.util.spec_from_file_location(name.replace("-", "_"), path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        # The original parser accepts both frames, demonstrating why it is
        # not a candidate-origin proof by itself.
        assert module.nsp_payload(frame(CANDIDATE)) is not None
        assert module.nsp_payload(frame(REFERENCE)) is not None
        assert module.candidate_nsp(frame(CANDIDATE), CANDIDATE) is not None
        assert module.candidate_nsp(frame(REFERENCE), CANDIDATE) is None
        assert module.candidate_nsp(frame(CANDIDATE)[:12], CANDIDATE) is None
    print("NSP candidate-origin packet evidence isolation: passed")


if __name__ == "__main__":
    check()
