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

from __future__ import annotations

import socket
import sys
import time

ETHERTYPE = 0x6003
SHORT_DATA = 0x02
LONG_DATA = 0x06
DATA_CLASS_MASK = 0xC7
DI = 0x38


def mac(text: str) -> bytes:
    value = bytes.fromhex(text.replace(":", ""))
    if len(value) != 6:
        raise ValueError(text)
    return value


def nsp_payload(frame: bytes) -> bytes | None:
    if len(frame) < 16 or int.from_bytes(frame[12:14], "big") != ETHERTYPE:
        return None
    body = frame[14:]
    declared = int.from_bytes(body[:2], "little")
    if not declared or len(body) < 2 + declared:
        return None
    route = body[2:2 + declared]
    if route and route[0] & 0x80:
        pad = route[0] & 0x7f
        if not pad or pad >= len(route):
            return None
        route = route[pad:]
    if not route:
        return None
    cls = route[0] & DATA_CLASS_MASK
    if cls == SHORT_DATA:
        off = 6
    elif cls == LONG_DATA:
        off = 21
    else:
        return None
    return route[off:] if len(route) > off else None


def main() -> int:
    if len(sys.argv) != 4:
        raise SystemExit(
            f"usage: {sys.argv[0]} IFACE CANDIDATE-MAC REFERENCE-MAC"
        )
    iface, candidate_s, reference_s = sys.argv[1:]
    candidate = mac(candidate_s)
    reference = mac(reference_s)

    sniff = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.htons(0x0003))
    sniff.bind((iface, 0))
    sniff.settimeout(0.5)
    try:
        first = None
        first_at = 0.0
        deadline = time.monotonic() + 14.0
        while time.monotonic() < deadline:
            try:
                frame = sniff.recv(4096)
            except TimeoutError:
                continue
            if frame[6:12] != candidate or frame[0:6] != reference:
                continue
            nsp = nsp_payload(frame)
            if nsp is None or len(nsp) < 7 or nsp[0] != DI:
                continue
            now = time.monotonic()
            if first is None:
                first = bytes(nsp)
                first_at = now
                print("diloss-observe: first Disconnect Initiate observed", flush=True)
                continue
            if bytes(nsp) != first:
                continue
            elapsed = now - first_at
            if elapsed < 3.5:
                raise RuntimeError(
                    f"Disconnect Initiate retransmitted too early: {elapsed:.3f}s"
                )
            print(
                "diloss-observe: pass duplicate_disconnect_initiate=1 "
                f"elapsed={elapsed:.3f}s",
                flush=True,
            )
            return 0
        raise RuntimeError("duplicate Disconnect Initiate not observed")
    finally:
        sniff.close()


if __name__ == "__main__":
    raise SystemExit(main())
