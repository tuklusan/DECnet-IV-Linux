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
FIRST = b"DNIV-IFLOW-1"
SECOND = b"DNIV-IFLOW-2"
THIRD = b"DNIV-IFLOW-3"
FOURTH = b"DNIV-IFLOW-4"


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


def send_interrupt_credit(
    sock: socket.socket, dst_mac: bytes, src_mac: bytes,
    src_node: int, dst_node: int, dst_link: bytes, src_link: bytes,
    sequence: int, delta: int,
) -> None:
    nsp = (
        b"\x10" + dst_link + src_link + struct.pack("<H", sequence)
        + b"\x04" + struct.pack("b", delta)
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
        raise RuntimeError("short AF_PACKET interrupt-credit send")


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
        while time.monotonic() < deadline:
            nsp = nsp_payload(sniff.recv(4096))
            if nsp is None or nsp[0] != 0x30 or FIRST not in nsp or len(nsp) < 7:
                continue
            links = (nsp[3:5], nsp[1:3])
            break
        if links is None:
            raise RuntimeError("interrupt-flow first Interrupt not observed")

        local_link, remote_link = links
        print("intflow-inject: first Interrupt observed", flush=True)

        # Let the independent peer ACK the Interrupt.  Candidate userspace
        # then proves that ACK_OTHER itself did not replenish credit.
        time.sleep(4.5)

        # Sequence 2 is future while Other-Data receive sequence 1 is missing.
        send_interrupt_credit(
            send, candidate, src_mac, src_node, dst_node,
            local_link, remote_link, 2, 1,
        )
        print("intflow-inject: future credit seq=2 sent", flush=True)

        sniff.settimeout(0.25)
        hold_deadline = time.monotonic() + 2.0
        while time.monotonic() < hold_deadline:
            try:
                nsp = nsp_payload(sniff.recv(4096))
            except TimeoutError:
                continue
            if nsp is not None and nsp[0] == 0x30 and (
                SECOND in nsp or THIRD in nsp
            ):
                raise RuntimeError("future interrupt credit applied before sequence closure")

        send_interrupt_credit(
            send, candidate, src_mac, src_node, dst_node,
            local_link, remote_link, 1, 1,
        )
        print("intflow-inject: in-order credit seq=1 sent", flush=True)

        seen_second = False
        seen_third = False
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            try:
                nsp = nsp_payload(sniff.recv(4096))
            except TimeoutError:
                continue
            if nsp is None or nsp[0] != 0x30:
                continue
            if SECOND in nsp:
                seen_second = True
            if THIRD in nsp:
                seen_third = True
            if seen_second and seen_third:
                break
        if not (seen_second and seen_third):
            raise RuntimeError("cached interrupt credit did not release two Interrupts")

        # Sequence 1 is now stale.  Its large positive delta must be ignored.
        send_interrupt_credit(
            send, candidate, src_mac, src_node, dst_node,
            local_link, remote_link, 1, 100,
        )
        print("intflow-inject: stale duplicate credit seq=1 sent", flush=True)

        quiet_deadline = time.monotonic() + 4.0
        while time.monotonic() < quiet_deadline:
            try:
                nsp = nsp_payload(sniff.recv(4096))
            except TimeoutError:
                continue
            if nsp is not None and nsp[0] == 0x30 and FOURTH in nsp:
                raise RuntimeError("stale duplicate grant restored interrupt credit")

        print(
            "intflow-inject: pass ack_not_credit=1 future_held=1 "
            "gap_release=1 cached_credit=1 stale_duplicate_ignored=1",
            flush=True,
        )
        return 0
    finally:
        sniff.close()
        send.close()


if __name__ == "__main__":
    raise SystemExit(main())
