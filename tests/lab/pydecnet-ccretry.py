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

import sys
import time

from decnet.connectors import SimpleApiConnector

RETRY_OBJECT = 248
PAYLOAD = b"DNIV-CC-RETRY"


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
            remuser=RETRY_OBJECT,
            localuser="CCRT",
        )
        if connection is None or response.type != "accept":
            raise RuntimeError(
                "CC retry connect rejected: "
                f"{getattr(response, 'reason', None)!r}"
            )

        # Keep Session Control quiet while the host proves the lost CC ACK
        # causes a duplicate Connect Confirm and then restores the path.
        time.sleep(13.0)

        connection.data(PAYLOAD)
        reply = connection.recv()
        if reply.type != "data" or bytes(reply) != PAYLOAD:
            raise RuntimeError(
                f"CC retry recovery echo mismatch: "
                f"type={reply.type!r} data={bytes(reply)!r}"
            )
        connection.disconnect()
    finally:
        connector.close()

    print(f"pydecnet-ccretry: pass peer={destination} duplicate-confirm=1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
