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
LINK_SVC = 0x10


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
    off = 6 if cls == SHORT_DATA else 21 if cls == LONG_DATA else -1
    return route[off:] if off >= 0 and len(route) > off else None


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
    first_links = None
    first_seq = None
    first_at = None
    started = time.monotonic()
    try:
        deadline = started + 13.0
        while time.monotonic() < deadline:
            try:
                frame = sniff.recv(4096)
            except TimeoutError:
                continue
            if frame[6:12] != candidate or frame[0:6] != reference:
                continue
            nsp = nsp_payload(frame)
            if nsp is None or len(nsp) != 9 or nsp[0] != LINK_SVC:
                continue
            if nsp[7] != 0 or nsp[8] != 0:
                continue
            links = (nsp[1:3], nsp[3:5])
            seq = int.from_bytes(nsp[5:7], "little") & 0x0fff
            now = time.monotonic()
            if first_seq is None:
                elapsed = now - started
                if elapsed < 2.5:
                    raise RuntimeError(
                        f"keepalive fired too early: {elapsed:.3f}s"
                    )
                first_links = links
                first_seq = seq
                first_at = now
                print(
                    f"keepalive-observe: first no-op Link Service seq={seq} "
                    f"elapsed={elapsed:.3f}s",
                    flush=True,
                )
                continue
            if links != first_links:
                continue
            if seq == first_seq:
                raise RuntimeError("keepalive retransmitted instead of being acknowledged")
            if seq != ((first_seq + 1) & 0x0fff):
                raise RuntimeError(
                    f"keepalive sequence jumped: first={first_seq} next={seq}"
                )
            elapsed = now - first_at
            if elapsed < 2.5:
                raise RuntimeError(
                    f"second keepalive fired too early: {elapsed:.3f}s"
                )
            print(
                "keepalive-observe: pass no_op=1 peer_acknowledged=1 "
                f"second_sequence={seq} interval={elapsed:.3f}s",
                flush=True,
            )
            return 0
        raise RuntimeError("two acknowledged inactivity keepalives not observed")
    finally:
        sniff.close()


if __name__ == "__main__":
    raise SystemExit(main())
