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
import struct
import sys
import time
from pathlib import Path

ETHERTYPE = 0x6003
UNKNOWN_LOCAL = 0x6A42
UNKNOWN_REMOTE = 0x6A41
CI_BASE = 0x7000
CI_COUNT = 320


def nodeaddr(text: str) -> int:
    area_s, node_s = text.split(".", 1)
    area = int(area_s)
    node = int(node_s)
    if not (1 <= area <= 63 and 1 <= node <= 1023):
        raise ValueError(text)
    return (area << 10) | node


def mac(text: str) -> bytes:
    value = bytes.fromhex(text.replace(":", ""))
    if len(value) != 6:
        raise ValueError(text)
    return value


def send_nsp(sock: socket.socket, dst_mac: bytes, src_mac: bytes,
             src_node: int, dst_node: int, nsp: bytes) -> None:
    route = (
        b"\x02"
        + struct.pack("<H", dst_node)
        + struct.pack("<H", src_node)
        + b"\x00"
        + nsp
    )
    frame = (
        dst_mac
        + src_mac
        + struct.pack("!H", ETHERTYPE)
        + struct.pack("<H", len(route))
        + route
    )
    sent = sock.send(frame)
    if sent != len(frame):
        raise RuntimeError(f"short AF_PACKET send: {sent}/{len(frame)}")


def main() -> int:
    if len(sys.argv) != 5:
        raise SystemExit(
            f"usage: {sys.argv[0]} IFACE CANDIDATE-MAC SRC-AREA.NODE DST-AREA.NODE"
        )
    iface, candidate_mac_s, src_s, dst_s = sys.argv[1:5]
    candidate_mac = mac(candidate_mac_s)
    src_node = nodeaddr(src_s)
    dst_node = nodeaddr(dst_s)
    src_mac = mac(Path(f"/sys/class/net/{iface}/address").read_text().strip())

    sock = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.htons(ETHERTYPE))
    try:
        sock.bind((iface, 0))
        cc = (
            b"\x28"
            + struct.pack("<H", UNKNOWN_LOCAL)
            + struct.pack("<H", UNKNOWN_REMOTE)
            + b"\x01\x00"
            + struct.pack("<H", 576)
            + b"\x00"
        )
        send_nsp(sock, candidate_mac, src_mac, src_node, dst_node, cc)
        time.sleep(0.02)

        session = b"\x00\xfa\x01\x00\x07RAWTEST\x00"
        for i in range(CI_COUNT):
            ci = (
                b"\x18\x00\x00"
                + struct.pack("<H", CI_BASE + i)
                + b"\x01\x00"
                + struct.pack("<H", 576)
                + session
            )
            send_nsp(sock, candidate_mac, src_mac, src_node, dst_node, ci)
            time.sleep(0.002)
    finally:
        sock.close()

    print(f"reserved-inject: pass cc=1 ci={CI_COUNT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
