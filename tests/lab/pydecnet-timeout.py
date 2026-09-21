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

TIMEOUT_OBJECT = 247
OBJECT_FAILED = 38
RECOVERY_PAYLOAD = b"DNIV-CR-TIMEOUT-RECOVER"


def main() -> int:
    if len(sys.argv) != 4:
        raise SystemExit(
            f"usage: {sys.argv[0]} API-SOCKET AREA.NODE PYDECNET-SYSTEM"
        )
    api_socket, destination, system = sys.argv[1:4]
    connector = SimpleApiConnector(api_socket)
    try:
        connection, response = connector.connect(
            system=system, dest=destination, remuser=TIMEOUT_OBJECT,
            localuser="TMO1",
        )
        if (connection is not None or response.type != "reject" or
                getattr(response, "reason", None) != OBJECT_FAILED):
            raise RuntimeError(
                "CR timeout result mismatch: "
                f"type={response.type!r} "
                f"reason={getattr(response, 'reason', None)!r}"
            )

        time.sleep(5.0)

        connection, response = connector.connect(
            system=system, dest=destination, remuser=TIMEOUT_OBJECT,
            localuser="TMO2",
        )
        if connection is None or response.type != "accept":
            raise RuntimeError(
                "CR timeout recovery rejected: "
                f"{getattr(response, 'reason', None)!r}"
            )
        connection.data(RECOVERY_PAYLOAD)
        reply = connection.recv()
        if reply.type != "data" or bytes(reply) != RECOVERY_PAYLOAD:
            raise RuntimeError(
                f"CR timeout recovery echo mismatch: "
                f"type={reply.type!r} data={bytes(reply)!r}"
            )
        connection.disconnect()
    finally:
        connector.close()

    print(
        f"pydecnet-timeout: pass peer={destination} "
        f"reason={OBJECT_FAILED} recovery=1"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
