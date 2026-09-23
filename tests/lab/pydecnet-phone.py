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

def main() -> int:
    if len(sys.argv) != 4:
        raise SystemExit(f"usage: {sys.argv[0]} API-SOCKET AREA.NODE SYSTEM")
    api_socket, destination, system = sys.argv[1:]
    connector = SimpleApiConnector(api_socket)
    try:
        connection, response = connector.connect(
            system=system, dest=destination, remuser=29, localuser="PYPHONE"
        )
        if connection is None or response.type != "accept":
            raise RuntimeError("PHONE object connect rejected")
        source = b"DN71::CALLER"
        target = b"DN70::TEST"
        connection.data(bytes((0x07,)) + source + b"\0" + target + b"\0")
        reply = connection.recv()
        if reply.type != "data" or bytes(reply) != b"\x01":
            raise RuntimeError(f"bad PHONE CONNECT reply: {bytes(reply)!r}")
        connection.data(bytes((0x08,)) + source + b"\0\x01")
        reply = connection.recv()
        if reply.type != "data" or bytes(reply) != b"\x01":
            raise RuntimeError(f"bad PHONE DIAL reply: {bytes(reply)!r}")
        connection.disconnect()
    finally:
        connector.close()
    print(f"pydecnet-phone: pass peer={destination} object=29")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
