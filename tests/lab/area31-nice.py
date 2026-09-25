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

"""Minimal Area-31 NICE/NML reachability checks through the MULTINET gateway."""

from __future__ import annotations

import os
import sys

from decnet.connectors import SimpleApiConnector

VERSION = bytes((4, 0, 0))
REQUESTS = (
    ("summary", bytes.fromhex("14 20 00 00 00")),
    ("status", bytes.fromhex("14 10 00 00 00")),
    ("counters", bytes.fromhex("14 30 00 00 00")),
)


def positive_nice_reply(data: bytes) -> bool:
    return len(data) >= 4 and data[0] == 1 and data[1:4] == b"\xff\xff\x00"


def main() -> int:
    if len(sys.argv) != 3:
        raise SystemExit(f"usage: {sys.argv[0]} API-SOCKET GATEWAY-NAME")
    destination = os.environ.get("VAX_ADDR")
    if not destination:
        raise SystemExit("area31-nice: VAX_ADDR is required")

    api_socket, system = sys.argv[1:]
    connector = SimpleApiConnector(api_socket)
    try:
        connection, response = connector.connect(
            system=system,
            dest=destination,
            remuser=19,
            localuser="NCP",
            data=VERSION,
        )
        if connection is None or response.type != "accept":
            raise RuntimeError("NML connect rejected")
        try:
            for label, request in REQUESTS:
                connection.data(request)
                response = connection.recv()
                payload = bytes(response) if response.type == "data" else b""
                if response.type != "data" or not positive_nice_reply(payload):
                    raise RuntimeError(
                        f"NICE {label} failed: type={response.type} "
                        f"data={payload[:64].hex()}"
                    )
        finally:
            connection.disconnect()
    finally:
        connector.close()

    print("area31-nice: executor summary/status/counters pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
