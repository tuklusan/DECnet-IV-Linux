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

ACK = bytes((1, 0, 0, 0))
MAIL11_V3 = bytes((3, 0, 0, 18, 0, 0, 0, 0, 0, 0, 0, 0, 2, 2, 0, 0))

def main() -> int:
    if len(sys.argv) != 4:
        raise SystemExit(f"usage: {sys.argv[0]} API-SOCKET AREA.NODE SYSTEM")
    api_socket, destination, system = sys.argv[1:]
    connector = SimpleApiConnector(api_socket)
    try:
        connection, response = connector.connect(
            system=system,
            dest=destination,
            remuser=27,
            localuser="PYMAIL",
            data=MAIL11_V3,
        )
        if connection is None or response.type != "accept":
            raise RuntimeError("MAIL object connect rejected")
        if len(response) != 16 or response[0] != 3:
            raise RuntimeError(f"bad MAIL-11 v3 accept data: {bytes(response)!r}")
        connection.data(b"PYDECNET")
        connection.data(b"TEST")
        reply = connection.recv()
        if reply.type != "data" or bytes(reply) != ACK:
            raise RuntimeError(f"bad MAIL recipient ACK: {bytes(reply)!r}")
        connection.data(b"SECOND")
        reply = connection.recv()
        if reply.type != "data" or bytes(reply) != ACK:
            raise RuntimeError(f"bad second MAIL recipient ACK: {bytes(reply)!r}")
        connection.data(b"\0")
        connection.data(b"PYNODE::TEST")
        connection.data(b"MAIL-11-PROOF")
        connection.data(b"BODY-ONE")
        connection.data(b"BODY-TWO")
        connection.data(b"\0")
        reply = connection.recv()
        if reply.type != "data" or bytes(reply) != ACK:
            raise RuntimeError(f"bad MAIL delivery ACK: {bytes(reply)!r}")
        connection.disconnect()
    finally:
        connector.close()
    print(f"pydecnet-mail: pass peer={destination} object=27 recipients=2 v3=1")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
