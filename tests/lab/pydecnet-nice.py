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

"""Query the candidate object-19 NICE listener from pinned PyDECnet."""

from __future__ import annotations

import sys

from decnet.connectors import SimpleApiConnector

REQUEST = bytes.fromhex("14 20 00 00 00")
VERSION = bytes((4, 0, 0))
IDENT = b"DECnet-IV-Linux"


def main() -> int:
    if len(sys.argv) != 4:
        raise SystemExit(
            f"usage: {sys.argv[0]} API-SOCKET AREA.NODE PYDECNET-SYSTEM"
        )
    api_socket, destination, system = sys.argv[1:]
    connector = SimpleApiConnector(api_socket)
    try:
        connection, response = connector.connect(
            system=system,
            dest=destination,
            remuser=19,
            localuser="NCP",
            data=VERSION,
        )
        if connection is None or response.type != "accept":
            raise RuntimeError(
                f"NML connect rejected: {getattr(response, 'reason', 'unknown')}"
            )
        if bytes(response) != VERSION:
            raise RuntimeError(f"bad NML accept data: {bytes(response)!r}")
        connection.data(REQUEST)
        response = connection.recv()
        if response.type != "data":
            raise RuntimeError(f"unexpected NICE response type {response.type!r}")
        data = bytes(response)
        if len(data) < 15 or data[0] != 1 or data[1:4] != b"\xff\xff\x00":
            raise RuntimeError(f"bad NICE reply header: {data!r}")
        address = int.from_bytes(data[4:6], "little")
        namelen = data[6] & 0x7f
        if not (data[6] & 0x80) or not namelen:
            raise RuntimeError(f"bad NICE node entity: {data!r}")
        name = data[7:7 + namelen]
        off = 7 + namelen
        if data[off:off + 2] != (100).to_bytes(2, "little"):
            raise RuntimeError(f"missing NICE identification: {data!r}")
        if data[off + 2] != 0x40 or data[off + 3] != len(IDENT):
            raise RuntimeError(f"bad NICE identification type: {data!r}")
        if data[off + 4:off + 4 + len(IDENT)] != IDENT:
            raise RuntimeError(f"bad NICE identification value: {data!r}")
        if address == 0 or not name:
            raise RuntimeError(f"invalid NICE executor identity: {data!r}")
        connection.disconnect()
    finally:
        connector.close()

    print(
        f"pydecnet-nice: pass peer={destination} "
        f"executor={address >> 10}.{address & 1023} name={name.decode('ascii')}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
