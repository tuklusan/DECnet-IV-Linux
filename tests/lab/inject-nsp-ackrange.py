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
TAG = b"DNIV-ACKRANGE-PROBE"


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


def data_sequence(nsp: bytes) -> int:
    if len(nsp) < 7:
        raise ValueError("short Data packet")
    off = 5
    for _ in range(2):
        if off + 2 > len(nsp):
            raise ValueError("short optional ACK")
        word = int.from_bytes(nsp[off:off + 2], "little")
        if not (word & 0x8000):
            break
        off += 2
    if off + 2 > len(nsp):
        raise ValueError("missing Data sequence")
    return int.from_bytes(nsp[off:off + 2], "little") & 0x0fff


def send_ack(sock: socket.socket, dst_mac: bytes, src_mac: bytes,
             src_node: int, dst_node: int, dst_link: bytes, src_link: bytes,
             ack: int, qual: int = 0) -> None:
    ackword = 0x8000 | ((qual & 0x3) << 12) | (ack & 0x0fff)
    nsp = b"\x04" + dst_link + src_link + struct.pack("<H", ackword)
    route = (
        b"\x02" + struct.pack("<H", dst_node)
        + struct.pack("<H", src_node) + b"\x00" + nsp
    )
    frame = (
        dst_mac + src_mac + struct.pack("!H", ETHERTYPE)
        + struct.pack("<H", len(route)) + route
    )
    if sock.send(frame) != len(frame):
        raise RuntimeError("short AF_PACKET ACK send")


def main() -> int:
    if len(sys.argv) != 6:
        raise SystemExit(
            f"usage: {sys.argv[0]} SNIFF-IFACE SEND-IFACE CANDIDATE-MAC "
            "SRC-AREA.NODE DST-AREA.NODE"
        )
    sniff_iface, send_iface, candidate_s, src_s, dst_s = sys.argv[1:6]
    candidate = mac(candidate_s)
    src_node = nodeaddr(src_s)
    dst_node = nodeaddr(dst_s)
    src_mac = bytes((0xAA, 0x00, 0x04, 0x00,
                     src_node & 0xFF, (src_node >> 8) & 0xFF))

    sniff = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.htons(0x0003))
    send = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.htons(ETHERTYPE))
    sniff.bind((sniff_iface, 0))
    send.bind((send_iface, 0))
    sniff.settimeout(15.0)
    try:
        deadline = time.monotonic() + 15.0
        links = None
        seq = None
        while time.monotonic() < deadline:
            nsp = nsp_payload(sniff.recv(4096))
            if nsp is None or TAG not in nsp or len(nsp) < 7:
                continue
            links = (nsp[3:5], nsp[1:3])
            seq = data_sequence(nsp)
            break
        if links is None or seq is None:
            raise RuntimeError("ack-range tagged Data not observed")

        local_link, remote_link = links
        forged = (seq + 7) & 0x0fff
        send_ack(send, candidate, src_mac, src_node, dst_node,
                 local_link, remote_link, forged)
        print(f"ack-range-inject: future ACK sent seq={seq} ack={forged}", flush=True)

        sniff.settimeout(0.5)
        deadline = time.monotonic() + 10.0
        while time.monotonic() < deadline:
            try:
                nsp = nsp_payload(sniff.recv(4096))
            except TimeoutError:
                continue
            if nsp is not None and TAG in nsp:
                break
        else:
            raise RuntimeError("candidate did not retransmit after forged future ACK")

        nak = (seq - 1) & 0x0fff
        sent_at = time.monotonic()
        send_ack(send, candidate, src_mac, src_node, dst_node,
                 local_link, remote_link, nak, 1)
        print(f"ack-range-inject: NAK sent ack={nak}", flush=True)

        deadline = sent_at + 2.5
        while time.monotonic() < deadline:
            try:
                nsp = nsp_payload(sniff.recv(4096))
            except TimeoutError:
                continue
            if nsp is not None and TAG in nsp:
                elapsed = time.monotonic() - sent_at
                print(
                    "ack-range-inject: pass future_ack_ignored=1 "
                    f"timer_retransmit=1 nak_retransmit=1 elapsed={elapsed:.3f}s"
                )
                return 0
        raise RuntimeError("candidate did not promptly retransmit after NAK")
    finally:
        sniff.close()
        send.close()


if __name__ == "__main__":
    raise SystemExit(main())
