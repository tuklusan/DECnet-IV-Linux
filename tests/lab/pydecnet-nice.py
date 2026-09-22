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
STATUS_REQUEST = bytes.fromhex("14 10 00 00 00")\nCOUNTERS_REQUEST = bytes.fromhex("14 30 00 00 00")
CIRCUIT_REQUEST = bytes.fromhex("14 13 05") + b"ETH-0"
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

        connection.data(STATUS_REQUEST)
        response = connection.recv()
        if response.type != "data":
            raise RuntimeError(
                f"unexpected NICE status response type {response.type!r}"
            )
        status = bytes(response)
        if len(status) < 20 or status[0] != 1 or status[1:4] != b"\xff\xff\x00":
            raise RuntimeError(f"bad NICE status header: {status!r}")
        status_name_len = status[6] & 0x7f
        status_off = 7 + status_name_len
        if status[status_off:status_off + 4] != b"\x00\x00\x81\x00":
            raise RuntimeError(f"missing NICE node state: {status!r}")
        status_off += 4
        if status[status_off:status_off + 3] != b"\x58\x02\x02":
            raise RuntimeError(f"missing NICE active-links parameter: {status!r}")
        active_links = int.from_bytes(status[status_off + 3:status_off + 5],
                                      "little")
        if active_links < 1:
            raise RuntimeError(f"invalid NICE active-links value: {status!r}")

        connection.data(COUNTERS_REQUEST)
        response = connection.recv()
        if response.type != "data":
            raise RuntimeError(
                f"unexpected NICE counters response type {response.type!r}"
            )
        counters = bytes(response)
        if len(counters) < 23 or counters[:4] != b"\x01\xff\xff\x00":
            raise RuntimeError(f"bad NICE counters header: {counters!r}")
        counters_name_len = counters[6] & 0x7f
        counters_off = 7 + counters_name_len
        if counters[counters_off:counters_off + 2] != b"\x60\xe2":
            raise RuntimeError(f"missing NICE total-bytes counter: {counters!r}")
        total_bytes = int.from_bytes(
            counters[counters_off + 2:counters_off + 6], "little"
        )
        counters_off += 6
        if counters[counters_off:counters_off + 2] != b"\x62\xe2":
            raise RuntimeError(
                f"missing NICE total-messages counter: {counters!r}"
            )
        total_messages = int.from_bytes(
            counters[counters_off + 2:counters_off + 6], "little"
        )
        if total_bytes < 1 or total_messages < 1:
            raise RuntimeError(f"invalid NICE counters: {counters!r}")

        connection.data(CIRCUIT_REQUEST)
        response = connection.recv()
        if response.type != "data":
            raise RuntimeError(
                f"unexpected NICE circuit response type {response.type!r}"
            )
        circuit = bytes(response)
        if len(circuit) < 19 or circuit[:4] != b"\x01\xff\xff\x00":
            raise RuntimeError(f"bad NICE circuit header: {circuit!r}")
        name_len = circuit[4]
        if circuit[5:5 + name_len] != b"ETH-0":
            raise RuntimeError(f"bad NICE circuit entity: {circuit!r}")
        off = 5 + name_len
        if circuit[off:off + 4] != b"\x00\x00\x81\x00":
            raise RuntimeError(f"missing NICE circuit state: {circuit!r}")
        off += 4
        if circuit[off:off + 3] != b"\x2a\x03\x02":
            raise RuntimeError(f"missing NICE circuit block size: {circuit!r}")
        block_size = int.from_bytes(circuit[off + 3:off + 5], "little")
        if block_size < 576:
            raise RuntimeError(f"invalid NICE circuit block size: {circuit!r}")
        connection.disconnect()
    finally:
        connector.close()

    print(
        f"pydecnet-nice: pass peer={destination} "
        f"executor={address >> 10}.{address & 1023} name={name.decode('ascii')} "
        f"active_links={active_links} total_bytes={total_bytes} "\n        f"total_messages={total_messages} circuit=ETH-0 block_size={block_size}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
