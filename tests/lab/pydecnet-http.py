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
            system=system, dest=destination, remuser="HTTP", localuser="PYHTTP"
        )
        if connection is None or response.type != "accept":
            raise RuntimeError("HTTP object connect rejected")
        connection.data(b"GET / HTTP/1.0\r\nHost: decnet\r\n\r\n")
        parts = []
        while True:
            reply = connection.recv()
            if reply.type == "data":
                parts.append(bytes(reply))
                continue
            if reply.type in ("disconnect", "reject"):
                break
            raise RuntimeError(f"unexpected HTTP event {reply.type!r}")
        raw = b"".join(parts)
        if b"HTTP/1.0 200 OK\r\n" not in raw or b"DECNET-WEB-PASS\n" not in raw:
            raise RuntimeError(f"bad HTTP response: {raw!r}")
    finally:
        connector.close()
    print(f"pydecnet-http: pass peer={destination} object=HTTP")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
