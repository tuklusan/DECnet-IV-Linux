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

"""Prove the native FAL listener CONFIG exchange from pinned PyDECnet."""

from __future__ import annotations
import sys
from decnet.connectors import SimpleApiConnector

CONFIG = bytes((1, 0, 0, 4, 128, 128, 4, 1, 0, 0, 0, 0))

def main() -> int:
    if len(sys.argv) != 4:
        raise SystemExit(f"usage: {sys.argv[0]} API-SOCKET AREA.NODE SYSTEM")
    api_socket, destination, system = sys.argv[1:]
    connector = SimpleApiConnector(api_socket)
    try:
        connection, response = connector.connect(
            system=system,
            dest=destination,
            remuser=17,
            localuser="PYFAL",
        )
        if connection is None or response.type != "accept":
            raise RuntimeError(
                f"FAL connect rejected: {getattr(response, 'reason', 'unknown')}"
            )
        connection.data(CONFIG)
        reply = connection.recv()
        if reply.type != "data" or bytes(reply) != CONFIG:
            raise RuntimeError(
                f"bad FAL CONFIG reply type={reply.type!r} data={bytes(reply)!r}"
            )

        name = b"SERVER.TXT"
        connection.data(bytes((3, 0, 1, 0, len(name))) + name)
        reply = connection.recv()
        if reply.type != "data" or bytes(reply) != bytes((2, 0, 4, 1)):
            raise RuntimeError(f"bad FAL attributes: {bytes(reply)!r}")
        reply = connection.recv()
        if reply.type != "data" or bytes(reply) != bytes((6, 0)):
            raise RuntimeError(f"bad FAL open ACK: {bytes(reply)!r}")
        connection.data(bytes((4, 0, 2)))
        reply = connection.recv()
        if reply.type != "data" or bytes(reply) != bytes((6, 0)):
            raise RuntimeError(f"bad FAL connect ACK: {bytes(reply)!r}")
        connection.data(bytes((4, 0, 1)))
        payload = bytearray()
        while True:
            reply = connection.recv()
            raw = bytes(reply)
            if reply.type != "data":
                raise RuntimeError(f"bad FAL transfer message type={reply.type!r}")
            if raw[:1] == bytes((8,)):
                if len(raw) < 3 or raw[1:3] != bytes((0, 0)):
                    raise RuntimeError(f"bad FAL DATA: {raw!r}")
                payload += raw[3:]
                continue
            if raw == bytes((9, 0, 0x27, 0x40)):
                break
            raise RuntimeError(f"unexpected FAL transfer message: {raw!r}")
        if bytes(payload) != b"SERVER-FAL\n":
            raise RuntimeError(f"bad FAL payload: {bytes(payload)!r}")
        connection.data(bytes((7, 0, 1)))
        reply = connection.recv()
        if reply.type != "data" or bytes(reply) != bytes((7, 0, 2)):
            raise RuntimeError(f"bad FAL close reply: {bytes(reply)!r}")
        connection.disconnect()
    finally:
        connector.close()
    print(f"pydecnet-fal: pass peer={destination} object=17 get=SERVER.TXT")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
