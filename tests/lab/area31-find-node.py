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


def reply_code(data: bytes) -> int:
    code = data[0]
    return code - 256 if code >= 128 else code


def exact_control_reply(payload: bytes, code: int) -> bool:
    if not payload or payload[0] != code:
        return False
    if len(payload) == 1:
        return True
    return len(payload) >= 4 and len(payload) == 4 + payload[3]


def find_node(api_socket: str, system: str, manager: str, wanted: str) -> str | None:
    connector = SimpleApiConnector(api_socket)
    try:
        connection, response = connector.connect(
            system=system,
            dest=manager,
            remuser=19,
            localuser="DNIV",
            data=VERSION,
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
                seen = set()
                while True:
                    response = connection.recv()
                    if response.type != "data":
                        raise RuntimeError("unexpected NML reply")
                    raw = bytes(response)
                    if not raw:
                        raise RuntimeError("empty NML reply")
                    code = reply_code(raw)
                    if code == 2:
                        if not exact_control_reply(raw, 2):
                            raise RuntimeError("malformed NICE ACCEPTED control")
                        continue
                    if code == -128:
                        if not exact_control_reply(raw, 0x80):
                            raise RuntimeError("malformed NICE DONE control")
                        break
                    if code < 0:
                        if permanent:
                            raise RuntimeError(
                                f"NICE permanent known-node request failed: {code}"
                            )
                        seen.clear()
                        break
                    reply = NodeReply(raw)
                    entity = reply.entity
                    name = getattr(entity, "nodename", "").upper()
                    if name == wanted.upper():
                        address = str(Nodeid(int(entity)))
                        if address in seen:
                            raise RuntimeError("duplicate named node")
                        seen.add(address)
                if len(seen) == 1:
                    return next(iter(seen))
            return None
        finally:
            connection.disconnect()
    finally:
        connector.close()


def selftest() -> int:
    assert reply_code(b"\x01") == 1
    assert reply_code(b"\x80") == -128
    assert str(Nodeid((31 << 10) | 123)) == "31.123"
    print("area31-find-node selftest passed")
    return 0


def main() -> int:
    if sys.argv[1:] == ["--selftest"]:
        return selftest()
    if len(sys.argv) != 5:
        raise SystemExit(
            f"usage: {sys.argv[0]} API-SOCKET GATEWAY-NAME MANAGER-NODE NODE-NAME"
        )
    found = find_node(*sys.argv[1:])
    if not found:
        return 1
    print(found)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
