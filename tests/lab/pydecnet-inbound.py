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

"""Drive pinned PyDECnet into native Linux AF_DECnet listeners."""

from __future__ import annotations

import sys

from decnet.connectors import SimpleApiConnector

SOURCE_NAME = "PYDNIV"
TESTS = ((240, b"numeric-inbound"), ("DNIVTEST", b"named-inbound"))


def main() -> int:
    if len(sys.argv) != 4:
        raise SystemExit(
            f"usage: {sys.argv[0]} API-SOCKET AREA.NODE PYDECNET-SYSTEM"
        )
    api_socket, destination, system = sys.argv[1:]
    connector = SimpleApiConnector(api_socket)
    try:
        for remote_user, payload in TESTS:
            connection, response = connector.connect(
                system=system,
                dest=destination,
                remuser=remote_user,
                localuser=SOURCE_NAME,
            )
            if connection is None or response.type != "accept":
                raise RuntimeError(
                    f"inbound connect rejected for {remote_user!r}: "
                    f"{getattr(response, 'reason', 'unknown')}"
                )
            connection.data(payload)
            reply = connection.recv()
            if reply.type != "data" or bytes(reply) != payload:
                raise RuntimeError(
                    f"bad inbound echo for {remote_user!r}: "
                    f"type={reply.type!r} data={bytes(reply)!r}"
                )
            connection.disconnect()
    finally:
        connector.close()

    print(f"pydecnet-inbound: pass peer={destination} selectors=2")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
