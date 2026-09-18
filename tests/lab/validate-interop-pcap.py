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

import argparse
import struct
from pathlib import Path

ALL_ROUTERS = bytes.fromhex("ab0000030000")
ALL_L2 = bytes.fromhex("09002b020000")
ETHERTYPE = 0x6003
ROUTER_HELLO = 0x0B
ENDNODE_HELLO = 0x0D
L1_ROUTING = 0x07
L2_ROUTING = 0x09
MAX_BLOCK = 1498


def mac(text: str) -> bytes:
    value = bytes.fromhex(text.replace(":", ""))
    if len(value) != 6:
        raise argparse.ArgumentTypeError(f"bad MAC address: {text}")
    return value


def packets(path: Path):
    data = path.read_bytes()
    if len(data) < 24:
        raise ValueError("pcap is shorter than its global header")
    magic = data[:4]
    if magic in (b"\xd4\xc3\xb2\xa1", b"\x4d\x3c\xb2\xa1"):
        order = "<"
    elif magic in (b"\xa1\xb2\xc3\xd4", b"\xa1\xb2\x3c\x4d"):
        order = ">"
    else:
        raise ValueError("unsupported pcap magic")
    _major, _minor, _zone, _sig, _snap, linktype = struct.unpack_from(order + "HHiIII", data, 4)
    if linktype != 1:
        raise ValueError(f"expected Ethernet pcap linktype 1, got {linktype}")
    pos = 24
    while pos < len(data):
        if pos + 16 > len(data):
            raise ValueError("truncated pcap record header")
        _sec, _frac, incl, _orig = struct.unpack_from(order + "IIII", data, pos)
        pos += 16
        if pos + incl > len(data):
            raise ValueError("truncated pcap record")
        yield data[pos : pos + incl]
        pos += incl


def routing_payload(frame: bytes) -> tuple[bytes, bytes, bytes] | None:
    if len(frame) < 16 or int.from_bytes(frame[12:14], "big") != ETHERTYPE:
        return None
    body = frame[14:]
    declared = int.from_bytes(body[:2], "little")
    if declared == 0 or declared > MAX_BLOCK or len(body) < 2 + declared:
        raise ValueError("invalid DECnet Ethernet Routing length field")
    payload = body[2 : 2 + declared]
    if payload and payload[0] & 0x80:
        pad = payload[0] & 0x7F
        if pad == 0 or pad >= len(payload):
            raise ValueError("invalid DECnet padding")
        payload = payload[pad:]
    return frame[:6], frame[6:12], payload


def router_entries(payload: bytes) -> list[tuple[bytes, int, bool]]:
    if len(payload) < 27 or payload[0] != ROUTER_HELLO:
        return []
    elist = payload[18]
    rslen = payload[26]
    if elist < 8 or elist != 8 + rslen or rslen % 7 or 19 + elist > len(payload):
        raise ValueError("malformed router hello list")
    entries = []
    for off in range(27, 27 + rslen, 7):
        entries.append((payload[off : off + 6], payload[off + 6] & 0x7F, bool(payload[off + 6] & 0x80)))
    return entries



def route_checksum(words: bytes) -> int:
    total = 1
    for off in range(0, len(words), 2):
        total += int.from_bytes(words[off:off + 2], "little")
    total = (total & 0xFFFF) + (total >> 16)
    total = (total & 0xFFFF) + (total >> 16)
    return total & 0xFFFF


def validate_routing_update(payload: bytes, expected_source: bytes,
                            level: int, self_index: int) -> bool:
    flag = L1_ROUTING if level == 1 else L2_ROUTING
    if len(payload) < 12 or (payload[0] & 0x0F) != flag:
        return False
    if payload[1:3] != expected_source[4:6]:
        raise ValueError("routing update embedded source mismatch")
    body = payload[4:-2]
    if len(body) < 6 or len(body) % 2:
        raise ValueError("malformed routing update length")
    expected = int.from_bytes(payload[-2:], "little")
    if route_checksum(body) != expected:
        raise ValueError("routing update checksum mismatch")

    pos = 0
    self_seen = False
    while pos < len(body):
        if pos + 4 > len(body):
            raise ValueError("truncated routing segment")
        count = int.from_bytes(body[pos:pos + 2], "little")
        start = int.from_bytes(body[pos + 2:pos + 4], "little")
        pos += 4
        if count == 0 or pos + 2 * count > len(body):
            raise ValueError("malformed routing segment bounds")
        if level == 1 and start + count > 1024:
            raise ValueError("L1 routing segment out of range")
        if level == 2 and (start < 1 or start + count > 64):
            raise ValueError("L2 routing segment out of range")
        for index in range(count):
            entry = int.from_bytes(body[pos + 2 * index:pos + 2 * index + 2],
                                   "little")
            if start + index == self_index:
                self_seen = True
                if entry != 0:
                    raise ValueError("routing update self metric is not zero")
        pos += 2 * count
    return self_seen


def validate_endnode(payload: bytes, source: bytes, destination: bytes, who: str) -> None:
    if len(payload) < 32 or payload[4:10] != source:
        raise ValueError(f"malformed {who} endnode hello")
    test_len = payload[31]
    if test_len != 50 or len(payload) < 32 + test_len or any(b != 0xAA for b in payload[32 : 32 + test_len]):
        raise ValueError(f"{who} endnode test-data image mismatch")
    if destination != ALL_ROUTERS:
        raise ValueError(f"{who} endnode hello used wrong multicast destination")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("pcap", type=Path)
    p.add_argument("reference", choices=("route20", "pydecnet"))
    p.add_argument("scenario", choices=("l1", "l2", "endnode", "router-endnode"))
    p.add_argument("candidate_mac", type=mac)
    p.add_argument("candidate_hw", type=mac)
    p.add_argument("candidate_changed_hw", type=mac)
    p.add_argument("reference_mac", type=mac)
    p.add_argument("reference_hw", type=mac)
    args = p.parse_args()

    counts = {
        "candidate_router": 0,
        "candidate_endnode": 0,
        "reference_router": 0,
        "reference_endnode": 0,
        "candidate_lists_reference": 0,
        "reference_lists_candidate": 0,
        "candidate_l2": 0,
        "reference_l2": 0,
        "candidate_l1_updates": 0,
        "candidate_l2_updates": 0,
        "candidate_l2_allrouters": 0,
        "candidate_l2_alll2": 0,
        "probes": 0,
    }
    bad_hello_hw = 0

    for frame in packets(args.pcap):
        parsed = routing_payload(frame)
        if parsed is None:
            continue
        dst, src, payload = parsed
        if src == args.reference_hw and dst == args.candidate_mac and payload and payload[0] not in (ROUTER_HELLO, ENDNODE_HELLO):
            counts["probes"] += 1
        if payload and src == args.candidate_mac and payload[0] == L1_ROUTING:
            if dst != ALL_ROUTERS:
                raise ValueError("candidate L1 update used wrong multicast")
            if validate_routing_update(payload, args.candidate_mac, 1,
                                       int.from_bytes(args.candidate_mac[4:6], "little") & 0x03FF):
                counts["candidate_l1_updates"] += 1
            continue
        if payload and src == args.candidate_mac and payload[0] == L2_ROUTING:
            if dst not in (ALL_ROUTERS, ALL_L2):
                raise ValueError("candidate L2 update used wrong multicast")
            area = int.from_bytes(args.candidate_mac[4:6], "little") >> 10
            if validate_routing_update(payload, args.candidate_mac, 2, area):
                counts["candidate_l2_updates"] += 1
                if dst == ALL_ROUTERS:
                    counts["candidate_l2_allrouters"] += 1
                elif dst == ALL_L2:
                    counts["candidate_l2_alll2"] += 1
            continue
        if not payload or payload[0] not in (ROUTER_HELLO, ENDNODE_HELLO):
            continue
        if src in (args.candidate_hw, args.candidate_changed_hw, args.reference_hw):
            bad_hello_hw += 1
        if payload[0] == ROUTER_HELLO:
            if len(payload) < 27:
                raise ValueError("short router hello")
            embedded = payload[4:10]
            if src == args.candidate_mac:
                counts["candidate_router"] += 1
                if embedded != args.candidate_mac:
                    raise ValueError("candidate router hello embedded source mismatch")
                if dst == ALL_L2:
                    counts["candidate_l2"] += 1
                for entry, _priority, twoway in router_entries(payload):
                    if entry == args.reference_mac and twoway:
                        counts["candidate_lists_reference"] += 1
            elif src == args.reference_mac:
                counts["reference_router"] += 1
                if embedded != args.reference_mac:
                    raise ValueError("reference router hello embedded source mismatch")
                if dst == ALL_L2:
                    counts["reference_l2"] += 1
                for entry, _priority, twoway in router_entries(payload):
                    if entry == args.candidate_mac and twoway:
                        counts["reference_lists_candidate"] += 1
        elif src == args.candidate_mac:
            counts["candidate_endnode"] += 1
            validate_endnode(payload, args.candidate_mac, dst, "candidate")
        elif src == args.reference_mac:
            counts["reference_endnode"] += 1
            validate_endnode(payload, args.reference_mac, dst, "reference")

    if bad_hello_hw:
        raise SystemExit(f"interop pcap: {bad_hello_hw} hello frame(s) used hardware source MAC")
    if counts["probes"] < 3:
        raise SystemExit("interop pcap: insufficient post-boot raw unicast probes")
    if args.scenario == "router-endnode":
        if args.reference != "pydecnet":
            raise SystemExit("interop pcap: router-endnode requires PyDECnet")
        if counts["candidate_router"] < 2:
            raise SystemExit("interop pcap: insufficient candidate router hellos")
        if counts["reference_endnode"] < 2:
            raise SystemExit("interop pcap: insufficient independent endnode hellos")
    else:
        if counts["reference_router"] < 2:
            raise SystemExit("interop pcap: insufficient reference router hellos")
        if args.scenario == "endnode":
            if counts["candidate_endnode"] < 2:
                raise SystemExit("interop pcap: insufficient candidate endnode hellos")
        else:
            if counts["candidate_router"] < 2:
                raise SystemExit("interop pcap: insufficient candidate router hellos")
            if counts["candidate_lists_reference"] < 1 or counts["reference_lists_candidate"] < 1:
                raise SystemExit("interop pcap: missing two-way router-list evidence")
            if args.scenario == "l1" and counts["candidate_l1_updates"] < 1:
                raise SystemExit("interop pcap: candidate emitted no valid L1 routing update")
            if args.scenario == "l2":
                if counts["candidate_l2_updates"] < 1:
                    raise SystemExit("interop pcap: candidate emitted no valid L2 routing update")
                if counts["candidate_l2_allrouters"] < 1 or counts["candidate_l2_alll2"] < 1:
                    raise SystemExit("interop pcap: candidate L2 update missing one Phase IV multicast target")
    if args.scenario == "l2":
        if counts["candidate_l2"] < 1:
            raise SystemExit("interop pcap: candidate missed All-Level-2-Routers multicast transmission")
        # Route20 implements the dedicated Phase IV L2-router multicast and is
        # the independent oracle for that behavior. This exact PyDECnet pin
        # interoperates as an L2 router through All-Routers and does not emit
        # router hellos to ALL_L2, so requiring it here would be a false gate.
        if args.reference == "route20" and counts["reference_l2"] < 1:
            raise SystemExit("interop pcap: Route20 missed All-Level-2-Routers multicast transmission")
    print("interop pcap: evidence passed " + " ".join(f"{k}={v}" for k, v in sorted(counts.items())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
