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
import asyncio
import sys
from decnet.async_connectors import AsyncApiConnector

def valid_object(name: str) -> bool:
    return 1 <= len(name) <= 16 and name[0].isalpha() and name.isalnum()

async def serve_one(api_socket: str, system: str, object_name: str, marker: str) -> None:
    if not valid_object(object_name):
        raise RuntimeError("invalid DECnet object name")
    body=(marker+"\n").encode("ascii")
    connector=AsyncApiConnector(api_socket)
    await connector.start()
    listener=await connector.bind(name=object_name,auth="off",system=system)
    print(f"pydecnet-http-server: ready object={object_name}",flush=True)
    try:
        conn=await asyncio.wait_for(listener.listen(),45)
        request=await asyncio.wait_for(conn.recv(),15)
        if request.type!="connect": raise RuntimeError(f"expected connect, got {request.type!r}")
        await conn.accept()
        data=await asyncio.wait_for(conn.recv(),15)
        if data.type!="data": raise RuntimeError(f"expected request data, got {data.type!r}")
        raw=bytes(data)
        if not raw.startswith(b"GET / HTTP/1.0\r\n") or b"\r\n\r\n" not in raw:
            conn.abort(); raise RuntimeError(f"bad HTTP request: {raw!r}")
        header=(b"HTTP/1.0 200 OK\r\n"+f"Content-Length: {len(body)}\r\n".encode("ascii")+
                b"Content-Type: text/plain\r\nConnection: close\r\n\r\n")
        conn.data(header); conn.data(body); conn.disconnect()
        print("pydecnet-http-server: pass",flush=True)
    finally:
        listener.close()
        await connector.close()

def main() -> int:
    if len(sys.argv) not in (3,4,5):
        raise SystemExit(f"usage: {sys.argv[0]} API-SOCKET SYSTEM [OBJECT [MARKER]]")
    object_name=sys.argv[3] if len(sys.argv)>=4 else "HTTP"
    marker=sys.argv[4] if len(sys.argv)>=5 else "PYDECNET-DNLYNX-PASS"
    asyncio.run(serve_one(sys.argv[1],sys.argv[2],object_name,marker)); return 0

if __name__=="__main__":
    raise SystemExit(main())
