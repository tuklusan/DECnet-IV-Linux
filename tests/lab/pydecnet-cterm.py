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

"""Serve one CTERM/Foundation handshake from pinned PyDECnet."""

from __future__ import annotations
import asyncio
import sys
from decnet.async_connectors import AsyncApiConnector

FOUND_BIND = 1
FOUND_BIND_ACCEPT = 4
FOUND_COMMON_DATA = 9
CTERM_INITIATE = 1

def foundation_bind() -> bytes:
    msg = bytearray(17)
    msg[0] = FOUND_BIND
    msg[1:4] = bytes((2, 4, 0))
    msg[4:6] = (7).to_bytes(2, "little")
    return bytes(msg)

def cterm_initiate() -> bytes:
    body = bytes((CTERM_INITIATE, 0, 1, 4, 0))
    return bytes((FOUND_COMMON_DATA, 0)) + len(body).to_bytes(2, "little") + body

def valid_bind_accept(msg: bytes) -> bool:
    return (
        len(msg) == 17
        and msg[0] == FOUND_BIND_ACCEPT
        and msg[1:4] == bytes((2, 4, 0))
        and int.from_bytes(msg[4:6], "little") == 193
    )

def valid_cterm_reply(msg: bytes) -> bool:
    if len(msg) < 5 or msg[0] != FOUND_COMMON_DATA:
        return False
    length = int.from_bytes(msg[2:4], "little")
    return length >= 1 and len(msg) == length + 4 and msg[4] == CTERM_INITIATE

async def serve(api_socket: str, system: str) -> int:
    connector = AsyncApiConnector(api_socket)
    await connector.start()
    listener = await connector.bind(42, "CTERM", system=system)
    try:
        print("pydecnet-cterm: ready", flush=True)
        conn = await listener.listen()
        request = await conn.recv()
        if request.type != "connect":
            raise RuntimeError(f"expected connect, got {request.type!r}")
        await conn.accept()
        conn.data(foundation_bind())
        reply = await conn.recv()
        if reply.type != "data" or not valid_bind_accept(bytes(reply)):
            raise RuntimeError(
                f"bad Foundation bind accept type={reply.type!r} data={bytes(reply)!r}"
            )
        conn.data(cterm_initiate())
        reply = await conn.recv()
        if reply.type != "data" or not valid_cterm_reply(bytes(reply)):
            raise RuntimeError(
                f"bad CTERM initiate reply type={reply.type!r} data={bytes(reply)!r}"
            )
        conn.disconnect()
        print("pydecnet-cterm: pass object=42", flush=True)
        return 0
    finally:
        listener.close()
        await connector.close()

def main() -> int:
    if len(sys.argv) != 3:
        raise SystemExit(f"usage: {sys.argv[0]} API-SOCKET PYDECNET-SYSTEM")
    return asyncio.run(serve(sys.argv[1], sys.argv[2]))

if __name__ == "__main__":
    raise SystemExit(main())
