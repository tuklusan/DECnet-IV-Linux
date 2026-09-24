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
from decnet.common import Nodeid
from decnet.connectors import SimpleApiConnector
from decnet.nicepackets import NiceReadNode, NodeReply, NodeReqEntity

VERSION = bytes((4, 0, 0))

def reply_code(raw: bytes) -> int:
    return raw[0] - 256 if raw[0] >= 128 else raw[0]

def main() -> int:
    if len(sys.argv) != 4:
        raise SystemExit(f"usage: {sys.argv[0]} API-SOCKET GATEWAY-NAME MANAGER-NODE")
    api_socket, system, manager = sys.argv[1:]
    connector = SimpleApiConnector(api_socket)
    seen: dict[str, str] = {}
    try:
        connection, response = connector.connect(
            system=system, dest=manager, remuser=19, localuser="DNIV", data=VERSION
        )
        if connection is None or response.type != "accept":
            raise RuntimeError("NML connect rejected")
        try:
            for permanent in (0, 1):
                req = NiceReadNode()
                req.permanent = permanent
                req.info = 0
                req.entity = NodeReqEntity(-1)
                connection.data(req.encode())
                while True:
                    response = connection.recv()
                    if response.type != "data":
                        raise RuntimeError("unexpected NML reply")
                    raw = bytes(response)
                    if not raw:
                        raise RuntimeError("empty NML reply")
                    code = reply_code(raw)
                    if code == 2:
                        continue
                    if code == -128:
                        break
                    if code < 0:
                        if permanent:
                            raise RuntimeError(f"NICE request failed: {code}")
                        break
                    entity = NodeReply(raw).entity
                    address = str(Nodeid(int(entity)))
                    if address.startswith("31."):
                        seen[address] = getattr(entity, "nodename", "").upper()
        finally:
            connection.disconnect()
    finally:
        connector.close()
    for address, name in sorted(
        seen.items(), key=lambda item: int(item[0].split(".")[1])
    ):
        print(address, name)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
