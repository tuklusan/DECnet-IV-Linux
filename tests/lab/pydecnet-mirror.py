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

"""Drive pinned PyDECnet into the native Linux MIRROR object 25."""

from __future__ import annotations

import sys

from decnet.connectors import SimpleApiConnector

PAYLOADS = (
    b"\x00",
    b"\x00phase6-mirror",
    b"\x00" + bytes((i * 37 + 11) & 0xff for i in range(1023)),
)


def main() -> int:
    if len(sys.argv) not in (4, 5):
        raise SystemExit(
            f"usage: {sys.argv[0]} API-SOCKET AREA.NODE PYDECNET-SYSTEM [OBJECT]"
        )

    api_socket, destination, system = sys.argv[1:4]
    selector = sys.argv[4] if len(sys.argv) == 5 else "25"
    remuser = int(selector) if selector.isdigit() else selector
    connector = SimpleApiConnector(api_socket)
    try:
        connection, response = connector.connect(
            system=system,
            dest=destination,
            remuser=remuser,
            localuser="PYMIRROR",
        )
        if connection is None or response.type != "accept":
            raise RuntimeError(
                f"MIRROR connect rejected: {getattr(response, 'reason', 'unknown')}"
            )
        if bytes(response) != b"\xff\xff":
            raise RuntimeError(f"bad MIRROR accept data: {bytes(response)!r}")

        for payload in PAYLOADS:
            connection.data(payload)
            reply = connection.recv()
            expected = b"\x01" + payload[1:]
            if reply.type != "data" or bytes(reply) != expected:
                raise RuntimeError(
                    f"bad MIRROR reply type={reply.type!r} data={bytes(reply)!r}"
                )

        connection.data(b"\x7fmalformed")
        reply = connection.recv()
        if reply.type != "data" or bytes(reply) != b"\xff":
            raise RuntimeError(
                f"bad MIRROR failure reply type={reply.type!r} data={bytes(reply)!r}"
            )
        connection.disconnect()
    finally:
        connector.close()

    print(
        f"pydecnet-mirror: pass peer={destination} object={selector} "
        f"records={len(PAYLOADS)} negative=1"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
