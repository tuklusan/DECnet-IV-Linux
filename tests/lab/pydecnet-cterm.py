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

"""Serve bounded CTERM/Foundation probe and interactive sessions from PyDECnet."""

from __future__ import annotations
import asyncio
import sys
from decnet.async_connectors import AsyncApiConnector

FOUND_BIND = 1
FOUND_BIND_ACCEPT = 4
FOUND_COMMON_DATA = 9
CTERM_INITIATE = 1
CTERM_START_READ = 2
CTERM_READ_DATA = 3
CTERM_WRITE = 7

def foundation_bind() -> bytes:
    msg = bytearray(17)
    msg[0] = FOUND_BIND
    msg[1:4] = bytes((2, 4, 0))
    msg[4:6] = (7).to_bytes(2, "little")
    return bytes(msg)

def common(body: bytes) -> bytes:
    return bytes((FOUND_COMMON_DATA, 0)) + len(body).to_bytes(2, "little") + body

def cterm_initiate() -> bytes:
    return common(bytes((CTERM_INITIATE, 0, 1, 4, 0)))

def cterm_write(data: bytes) -> bytes:
    return common(bytes((CTERM_WRITE, 0, 0, 0, 0)) + data)

def cterm_start_read(maximum: int = 80) -> bytes:
    body = bytearray(17)
    body[0] = CTERM_START_READ
    flags = 2 << 14
    body[1:4] = flags.to_bytes(3, "little")
    body[4:6] = maximum.to_bytes(2, "little")
    return common(bytes(body))

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

def read_data(msg: bytes) -> tuple[int, bytes]:
    if len(msg) < 12 or msg[0] != FOUND_COMMON_DATA:
        raise RuntimeError(f"bad READ DATA foundation record: {msg!r}")
    length = int.from_bytes(msg[2:4], "little")
    if len(msg) != length + 4 or length < 8 or msg[4] != CTERM_READ_DATA:
        raise RuntimeError(f"bad READ DATA CTERM record: {msg!r}")
    body = msg[4:]
    return int.from_bytes(body[6:8], "little"), body[8:]

async def handshake(conn) -> None:
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

async def serve(api_socket: str, system: str) -> int:
    connector = AsyncApiConnector(api_socket)
    await connector.start()
    listener = await connector.bind(42, "CTERM", system=system)
    try:
        print("pydecnet-cterm: ready", flush=True)
        probe = await listener.listen()
        await handshake(probe)
        probe.disconnect()

        interactive = await listener.listen()
        await handshake(interactive)
        interactive.data(cterm_write(b"CTERM-READY\r\n"))
        interactive.data(cterm_start_read())
        reply = await interactive.recv()
        if reply.type != "data":
            raise RuntimeError(f"expected READ DATA, got {reply.type!r}")
        term_pos, data = read_data(bytes(reply))
        if data != b"phase7\r" or term_pos != 6:
            raise RuntimeError(
                f"bad interactive input term_pos={term_pos} data={data!r}"
            )
        interactive.data(cterm_write(b"CTERM-DONE\r\n"))
        interactive.disconnect()
        print("pydecnet-cterm: pass object=42 sessions=2 interactive=1", flush=True)
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
