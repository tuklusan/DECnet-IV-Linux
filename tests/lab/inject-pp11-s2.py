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

"""Deterministic PP-11 S2 malformed-frame injector."""

from __future__ import annotations
import argparse
import socket
import time
from pathlib import Path

ETH_P_DECNET = 0x6003
MARKER = b"DNIV-S2-FAULT-"


def mac(text: str) -> bytes:
    parts = text.split(":")
    if len(parts) != 6:
        raise ValueError("bad MAC")
    return bytes(int(part, 16) for part in parts)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--interface", action="append", required=True)
    parser.add_argument("--destination", required=True)
    parser.add_argument("--events", type=int, default=10000)
    parser.add_argument("--duration", type=float, default=3600.0)
    parser.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args()
    if len(args.interface) < 2 or args.events < 10000 or args.duration < 3600.0:
        raise SystemExit("pp11-s2 injector requires >=2 interfaces, >=10000 events and >=3600s")
    destination = mac(args.destination)
    source = mac("02:44:4e:49:56:02")
    sockets = []
    for interface in args.interface:
        sock = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.htons(ETH_P_DECNET))
        sock.bind((interface, 0))
        sockets.append(sock)
    args.evidence.parent.mkdir(parents=True, exist_ok=True)
    start = time.monotonic()
    sent = 0
    with args.evidence.open("w", encoding="utf-8") as evidence:
        evidence.write(f"EVENTS_REQUESTED={args.events}\nDURATION_REQUESTED={args.duration:.3f}\n")
        for index in range(args.events):
            interface_index = index % len(sockets)
            marker = MARKER + f"{index + 1:05d}".encode("ascii")
            payload = (100).to_bytes(2, "little") + bytes([0x06]) + marker
            frame = destination + source + ETH_P_DECNET.to_bytes(2, "big") + payload
            actual = sockets[interface_index].send(frame)
            if actual != len(frame):
                raise RuntimeError(f"pp11-s2 short raw send {actual}/{len(frame)}")
            sent += 1
            evidence.write(f"{index + 1}\t{args.interface[interface_index]}\t{marker.decode()}\n")
            if (index + 1) % 100 == 0:
                evidence.flush()
            target = start + ((index + 1) * args.duration / args.events)
            while True:
                remaining = target - time.monotonic()
                if remaining <= 0:
                    break
                time.sleep(min(remaining, 0.1))
        elapsed = time.monotonic() - start
        evidence.write(f"EVENTS_SENT={sent}\nDURATION_ACTUAL={elapsed:.3f}\nRESULT=PASS\n")
        evidence.flush()
    for sock in sockets:
        sock.close()
    if sent != args.events or elapsed < args.duration:
        raise RuntimeError(f"pp11-s2 injector envelope sent={sent} elapsed={elapsed:.3f}")
    print(f"pp11-s2-inject: pass events={sent} duration={elapsed:.3f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
