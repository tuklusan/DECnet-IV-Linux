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

from decnet.connectors import SimpleApiConnector

RESET_OBJECT = 244
RESET_ROUNDS = 8
ABORT_NAME = "ABORTER"
SURVIVOR_NAME = "SURVIVOR"
ABORT_DATA = b"py-abort"
SURVIVOR_DONE = b"py-survivor-done"


def connect(api_socket: str, destination: str, system: str, localuser: str):
    connector = SimpleApiConnector(api_socket)
    connection, response = connector.connect(
        system=system,
        dest=destination,
        remuser=RESET_OBJECT,
        localuser=localuser,
    )
    if connection is None or response.type != "accept":
        connector.close()
        raise RuntimeError(
            f"{localuser} connect rejected: "
            f"{getattr(response, 'reason', 'unknown')!r}"
        )
    return connector, connection


def main() -> int:
    if len(sys.argv) != 4:
        raise SystemExit(
            f"usage: {sys.argv[0]} API-SOCKET AREA.NODE PYDECNET-SYSTEM"
        )
    api_socket, destination, system = sys.argv[1:]

    for round_number in range(RESET_ROUNDS):
        abort_connector = survivor_connector = None
        try:
            abort_connector, abort_connection = connect(
                api_socket, destination, system, ABORT_NAME
            )
            survivor_connector, survivor_connection = connect(
                api_socket, destination, system, SURVIVOR_NAME
            )

            abort_connection.abort(ABORT_DATA)

            payload = f"reset-survivor-{round_number}".encode("ascii")
            survivor_connection.data(payload)
            reply = survivor_connection.recv()
            if reply.type != "data" or bytes(reply) != payload:
                raise RuntimeError(
                    f"round {round_number} survivor echo: "
                    f"type={reply.type!r} data={bytes(reply)!r}"
                )
            survivor_connection.disconnect(SURVIVOR_DONE)
        finally:
            if abort_connector is not None:
                abort_connector.close()
            if survivor_connector is not None:
                survivor_connector.close()

    print(
        f"pydecnet-reset: pass peer={destination} rounds={RESET_ROUNDS} "
        "abort-isolation=1 disdata=1"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
