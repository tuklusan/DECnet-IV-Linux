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

"""Hold several simultaneous object-19 NICE sessions against the candidate."""

from __future__ import annotations

import sys

from decnet.connectors import SimpleApiConnector

STATUS_REQUEST = bytes.fromhex("14 10 00 00 00")
VERSION = bytes((4, 0, 0))


def main() -> int:
    if len(sys.argv) != 5:
        raise SystemExit(
            f"usage: {sys.argv[0]} API-SOCKET AREA.NODE PYDECNET-SYSTEM COUNT"
        )
    api_socket, destination, system, count_text = sys.argv[1:]
    count = int(count_text)
    if count < 2 or count > 16:
        raise SystemExit("COUNT must be between 2 and 16")

    connectors = []
    connections = []
    try:
        for _ in range(count):
            connector = SimpleApiConnector(api_socket)
            connection, response = connector.connect(
                system=system,
                dest=destination,
                remuser=19,
                localuser="NCP",
                data=VERSION,
            )
            if connection is None or response.type != "accept":
                raise RuntimeError(
                    "concurrent NML connect rejected: "
                    f"{getattr(response, 'reason', 'unknown')}"
                )
            if bytes(response) != VERSION:
                raise RuntimeError(
                    f"bad concurrent NML accept data: {bytes(response)!r}"
                )
            connectors.append(connector)
            connections.append(connection)

        for connection in connections:
            connection.data(STATUS_REQUEST)
        for connection in connections:
            response = connection.recv()
            if response.type != "data":
                raise RuntimeError(
                    f"unexpected concurrent NICE response {response.type!r}"
                )
            data = bytes(response)
            if len(data) < 20 or data[:4] != b"\x01\xff\xff\x00":
                raise RuntimeError(f"bad concurrent NICE status: {data!r}")
            name_len = data[6] & 0x7f
            off = 7 + name_len
            if data[off:off + 4] != b"\x00\x00\x81\x00":
                raise RuntimeError(
                    f"concurrent NICE state missing: {data!r}"
                )

        for connection in connections:
            connection.disconnect()
    finally:
        for connector in connectors:
            connector.close()

    print(
        f"pydecnet-nice-concurrent: pass peer={destination} sessions={count}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
