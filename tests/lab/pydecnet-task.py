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

"""Drive a pinned PyDECnet peer into an arbitrary native named object."""

from __future__ import annotations

import sys

from decnet.connectors import SimpleApiConnector

OBJECT = "DNIVTASK"
PAYLOADS = (b"task-object", bytes(range(64)))


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
            remuser=OBJECT,
            localuser="PYTASK",
            data=b"task-connect",
        )
        if connection is None or response.type != "accept":
            raise RuntimeError(
                f"task connect rejected: {getattr(response, 'reason', 'unknown')}"
            )

        for payload in PAYLOADS:
            connection.data(payload)
            reply = connection.recv()
            if reply.type != "data" or bytes(reply) != payload:
                raise RuntimeError(
                    f"bad task echo type={reply.type!r} data={bytes(reply)!r}"
                )
        connection.disconnect()
    finally:
        connector.close()

    print(
        f"pydecnet-task: pass peer={destination} object={OBJECT} "
        f"records={len(PAYLOADS)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
