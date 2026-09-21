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
SHORT_DATA = 0x02
LONG_DATA = 0x06
DATA_CLASS_MASK = 0xC7
NSP_CONTROL = {0x04, 0x10, 0x14, 0x18, 0x24, 0x28, 0x30, 0x38, 0x48, 0x68}
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


def routed_nsp_payload(payload: bytes) -> bytes | None:
    if not payload:
        return None
    data_class = payload[0] & DATA_CLASS_MASK
    if data_class == SHORT_DATA:
        header_len = 6
    elif data_class == LONG_DATA:
        header_len = 21
    else:
        return None
    if len(payload) <= header_len:
        return None
    nsp = payload[header_len:]
    flag = nsp[0]
    if (flag & 0x83) == 0 and (flag & 0x9F) == 0:
        return nsp
    if flag in NSP_CONTROL:
        return nsp
    return None


def enduser_end(buf: bytes, off: int) -> int:
    if off + 2 > len(buf):
        raise ValueError("truncated Session end-user")
    fmt = buf[off]
    if fmt == 0:
        return off + 2
    if fmt == 1:
        prefix = 2
    elif fmt == 2:
        prefix = 6
    elif fmt == 4:
        prefix = 10
    else:
        raise ValueError("invalid Session end-user format")
    pos = off + prefix
    if pos >= len(buf):
        raise ValueError("truncated Session end-user name")
    length = buf[pos]
    end = pos + 1 + length
    if end > len(buf):
        raise ValueError("truncated Session end-user value")
    return end


def counted_field(buf: bytes, off: int) -> tuple[bytes, int]:
    if off >= len(buf):
        raise ValueError("truncated Session counted field")
    length = buf[off]
    end = off + 1 + length
    if end > len(buf):
        raise ValueError("truncated Session counted value")
    return buf[off + 1 : end], end


def session_ci_options(nsp: bytes) -> tuple[tuple[bytes, bytes, bytes], bytes] | None:
    if not nsp or nsp[0] not in (0x18, 0x68):
        return None
    off = 9
    off = enduser_end(nsp, off)
    off = enduser_end(nsp, off)
    if off >= len(nsp):
        raise ValueError("truncated Session CI menu")
    menu = nsp[off]
    off += 1
    access = (b"", b"", b"")
    conndata = b""
    if menu & 0x01:
        fields = []
        for _ in range(3):
            field, off = counted_field(nsp, off)
            fields.append(field)
        access = tuple(fields)
    if menu & 0x02:
        conndata, off = counted_field(nsp, off)
    return access, conndata


def data_payload_len(nsp: bytes) -> int | None:
    if not nsp or (nsp[0] & 0x9F) != 0:
        return None
    off = 5
    for _ in range(2):
        if off + 2 <= len(nsp) and int.from_bytes(nsp[off:off + 2], "little") & 0x8000:
            off += 2
    if off + 2 > len(nsp):
        raise ValueError("truncated NSP Data segment")
    return len(nsp) - off - 2


def cc_data(nsp: bytes) -> bytes | None:
    if not nsp or nsp[0] != 0x28:
        return None
    if len(nsp) < 10:
        raise ValueError("truncated NSP Connect Confirm data")
    length = nsp[9]
    if 10 + length > len(nsp):
        raise ValueError("truncated NSP Connect Confirm payload")
    return nsp[10 : 10 + length]


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
    p.add_argument("--timer-proof", action="store_true")
    p.add_argument("--reserved-proof", action="store_true")
    p.add_argument("--peer-segsize", type=int, default=0)
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
        "candidate_nsp": 0,
        "reference_nsp": 0,
        "candidate_interrupt": 0,
        "reference_interrupt": 0,
        "candidate_option_ci": 0,
        "reference_option_ci": 0,
        "candidate_accept_data": 0,
        "candidate_loss_probe": 0,
        "reference_loss_probe": 0,
        "candidate_drain_probe": 0,
        "candidate_drain_retransmit_before_di": 0,
        "candidate_exhaust_probe": 0,
        "candidate_ci_exhaust": 0,
        "candidate_ci_exhaust_rci": 0,
        "candidate_ci_recover": 0,
        "candidate_ci_recover_data": 0,
        "reference_ci_recover_data": 0,
        "candidate_cr_timeout_reason38": 0,
        "candidate_cr_timeout_recovery": 0,
        "reference_cr_timeout_recovery": 0,
        "candidate_no_resources_dc": 0,
        "candidate_no_link_dc": 0,
        "candidate_data_segments": 0,
        "candidate_full_peer_segments": 0,
        "reference_peer_segsize_cc": 0,
        "probes": 0,
    }
    bad_hello_hw = 0
    drain_link = None
    drain_data_seen = 0

    for frame in packets(args.pcap):
        parsed = routing_payload(frame)
        if parsed is None:
            continue
        dst, src, payload = parsed
        nsp = routed_nsp_payload(payload)
        if nsp is not None:
            if src == args.candidate_mac:
                counts["candidate_nsp"] += 1
                dlen = data_payload_len(nsp)
                if dlen is not None:
                    counts["candidate_data_segments"] += 1
                    if args.peer_segsize:
                        if dlen > args.peer_segsize:
                            raise ValueError(
                                f"candidate Data payload {dlen} exceeds negotiated {args.peer_segsize}")
                        if dlen == args.peer_segsize:
                            counts["candidate_full_peer_segments"] += 1
                if b"DNIV-LOSS-PROBE" in nsp:
                    counts["candidate_loss_probe"] += 1
                if b"DNIV-DRAIN-PROBE" in nsp:
                    counts["candidate_drain_probe"] += 1
                    if len(nsp) >= 5:
                        link = nsp[3:5]
                        if drain_link is None:
                            drain_link = link
                        if link == drain_link:
                            drain_data_seen += 1
                if b"DNIV-EXHAUST-PROBE" in nsp:
                    counts["candidate_exhaust_probe"] += 1
                if b"CI-EXHAUST" in nsp:
                    counts["candidate_ci_exhaust"] += 1
                    if nsp[0] == 0x68:
                        counts["candidate_ci_exhaust_rci"] += 1
                if b"CI-RECOVER" in nsp:
                    counts["candidate_ci_recover"] += 1
                if b"DNIV-CI-RECOVER-DATA" in nsp:
                    counts["candidate_ci_recover_data"] += 1
                if b"DNIV-CR-TIMEOUT-RECOVER" in nsp:
                    counts["candidate_cr_timeout_recovery"] += 1
                if nsp[0] == 0x38 and len(nsp) >= 5 and drain_link is not None and \
                        nsp[3:5] == drain_link and drain_data_seen >= 2:
                    counts["candidate_drain_retransmit_before_di"] += 1
                if nsp[0] == 0x38 and len(nsp) >= 7 and \
                        int.from_bytes(nsp[5:7], "little") == 38:
                    counts["candidate_cr_timeout_reason38"] += 1
                if nsp[0] == 0x48 and len(nsp) >= 7:
                    reason = int.from_bytes(nsp[5:7], "little")
                    if reason == 1:
                        counts["candidate_no_resources_dc"] += 1
                    elif reason == 41:
                        counts["candidate_no_link_dc"] += 1
                if nsp[0] == 0x30:
                    counts["candidate_interrupt"] += 1
                opts = session_ci_options(nsp)
                if opts == (
                    (b"DNIVUSER", b"DNIVPASS", b"DNIVACCT"),
                    b"dniv-connect",
                ):
                    counts["candidate_option_ci"] += 1
                if cc_data(nsp) == b"linux-accept":
                    counts["candidate_accept_data"] += 1
            elif src == args.reference_mac:
                counts["reference_nsp"] += 1
                if args.peer_segsize and nsp[0] == 0x28 and len(nsp) >= 9 and \
                        int.from_bytes(nsp[7:9], "little") == args.peer_segsize:
                    counts["reference_peer_segsize_cc"] += 1
                if b"DNIV-LOSS-PROBE" in nsp:
                    counts["reference_loss_probe"] += 1
                if b"DNIV-CI-RECOVER-DATA" in nsp:
                    counts["reference_ci_recover_data"] += 1
                if b"DNIV-CR-TIMEOUT-RECOVER" in nsp:
                    counts["reference_cr_timeout_recovery"] += 1
                if nsp[0] == 0x30:
                    counts["reference_interrupt"] += 1
                opts = session_ci_options(nsp)
                if opts == (
                    (b"PYUSER", b"PYPASS", b"PYACCT"),
                    b"py-connect",
                ):
                    counts["reference_option_ci"] += 1
        if dst == args.candidate_mac and payload.startswith(b"DNIV-INTEROP-PROBE-"):
            if args.reference == "route20" and src != args.reference_hw:
                raise ValueError("raw unicast probe source MAC mismatch")
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
        hardware_only = src in (args.candidate_hw, args.candidate_changed_hw)
        if args.reference_hw != args.reference_mac and src == args.reference_hw:
            hardware_only = True
        if hardware_only:
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
    if args.reference == "pydecnet":
        if counts["candidate_nsp"] < 5 or counts["reference_nsp"] < 5:
            raise SystemExit("interop pcap: insufficient bidirectional NSP socket traffic")
        if counts["candidate_option_ci"] < 1:
            raise SystemExit("interop pcap: missing candidate access/connect-data CI")
        if args.peer_segsize:
            if counts["reference_peer_segsize_cc"] < 1:
                raise SystemExit("interop pcap: peer never advertised requested small NSP segment size")
            if counts["candidate_full_peer_segments"] < 2:
                raise SystemExit("interop pcap: candidate did not segment normal Data at peer limit")
        if counts["candidate_loss_probe"] < 2:
            raise SystemExit("interop pcap: missing candidate NSP timeout retransmission")
        if counts["reference_loss_probe"] < 1:
            raise SystemExit("interop pcap: missing post-fault reference loss-probe response")
        if counts["candidate_drain_probe"] < 2:
            raise SystemExit("interop pcap: clean disconnect did not retransmit unacknowledged Data")
        if counts["candidate_drain_retransmit_before_di"] < 1:
            raise SystemExit("interop pcap: clean disconnect DI preceded Data drain")
        if counts["candidate_exhaust_probe"] < 5:
            raise SystemExit("interop pcap: retransmit-limit probe did not reach all five attempts")
        if counts["candidate_ci_exhaust"] < 5 or counts["candidate_ci_exhaust_rci"] < 4:
            raise SystemExit("interop pcap: missing CI/RCI retransmit-limit sequence")
        if counts["candidate_ci_recover"] < 1:
            raise SystemExit("interop pcap: missing fresh CI after connect retry exhaustion")
        if counts["candidate_ci_recover_data"] < 1 or counts["reference_ci_recover_data"] < 1:
            raise SystemExit("interop pcap: missing data recovery after connect retry exhaustion")
        if args.timer_proof:
            if counts["candidate_cr_timeout_reason38"] < 1:
                raise SystemExit("interop pcap: missing candidate CR-timeout reason-38 DI")
            if counts["candidate_cr_timeout_recovery"] < 1 or \
                    counts["reference_cr_timeout_recovery"] < 1:
                raise SystemExit("interop pcap: missing CR-timeout fresh-link recovery")
        if args.reserved_proof:
            if counts["candidate_no_resources_dc"] < 1:
                raise SystemExit("interop pcap: missing candidate DC No Resources response")
            if counts["candidate_no_link_dc"] < 1:
                raise SystemExit("interop pcap: missing candidate DC No Link response")
        if args.scenario != "router-endnode":
            if counts["candidate_interrupt"] < 2:
                raise SystemExit("interop pcap: missing candidate NSP interrupt traffic")
            if counts["reference_interrupt"] < 4:
                raise SystemExit("interop pcap: missing repeated reference NSP interrupt traffic")
            if counts["reference_option_ci"] < 2:
                raise SystemExit("interop pcap: missing reference access/connect-data CI")
            if counts["candidate_accept_data"] < 2:
                raise SystemExit("interop pcap: missing candidate Connect Confirm data")
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
