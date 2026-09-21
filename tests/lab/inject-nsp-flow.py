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

ETHERTYPE = 0x6003
SHORT_DATA = 0x02
LONG_DATA = 0x06
DATA_CLASS_MASK = 0xC7
FIRST = b"DNIV-FLOW-FIRST"
XON_TAG = b"DNIV-FLOW-XON"


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


def send_ls(sock: socket.socket, dst_mac: bytes, src_mac: bytes,
            src_node: int, dst_node: int, dst_link: bytes, src_link: bytes,
            sequence: int, fcmod: int) -> None:
    nsp = (
        b"\x10" + dst_link + src_link + struct.pack("<H", sequence)
        + bytes((fcmod, 0))
    )
    route = (
        b"\x02" + struct.pack("<H", dst_node)
        + struct.pack("<H", src_node) + b"\x00" + nsp
    )
    frame = (
        dst_mac + src_mac + struct.pack("!H", ETHERTYPE)
        + struct.pack("<H", len(route)) + route
    )
    if sock.send(frame) != len(frame):
        raise RuntimeError("short AF_PACKET flow-control send")


def main() -> int:
    if len(sys.argv) != 5:
        raise SystemExit(
            f"usage: {sys.argv[0]} IFACE CANDIDATE-MAC SRC-AREA.NODE DST-AREA.NODE"
        )
    iface, candidate_s, src_s, dst_s = sys.argv[1:5]
    candidate = mac(candidate_s)
    src_node = nodeaddr(src_s)
    dst_node = nodeaddr(dst_s)
    src_mac = bytes((0xAA, 0x00, 0x04, 0x00,
                     src_node & 0xFF, (src_node >> 8) & 0xFF))

    sock = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.htons(ETHERTYPE))
    sock.bind((iface, 0))
    sock.settimeout(15.0)
    try:
        deadline = time.monotonic() + 15.0
        links = None
        while time.monotonic() < deadline:
            nsp = nsp_payload(sock.recv(4096))
            if nsp is None or FIRST not in nsp or len(nsp) < 5:
                continue
            # Candidate Data has destination=peer link, source=local link.
            links = (nsp[3:5], nsp[1:3])
            break
        if links is None:
            raise RuntimeError("flow-control probe Data not observed")

        local_link, remote_link = links
        send_ls(sock, candidate, src_mac, src_node, dst_node,
                local_link, remote_link, 1, 1)
        time.sleep(4.0)
        send_ls(sock, candidate, src_mac, src_node, dst_node,
                local_link, remote_link, 2, 2)

        deadline = time.monotonic() + 10.0
        while time.monotonic() < deadline:
            nsp = nsp_payload(sock.recv(4096))
            if nsp is not None and XON_TAG in nsp:
                print("flow-inject: pass xoff=1 xon=1 resumed=1")
                return 0
        raise RuntimeError("candidate did not resume Data after XON")
    finally:
        sock.close()


if __name__ == "__main__":
    raise SystemExit(main())
