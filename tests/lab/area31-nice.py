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

from decnet.common import Nodeid
from decnet.connectors import SimpleApiConnector
from decnet.nicepackets import NiceReadNode, NodeReply, NodeReqEntity

VERSION = bytes((4, 0, 0))
REQUESTS = (
    ("summary", 0),
    ("status", 1),
    ("counters", 3),
)


def reply_code(data: bytes) -> int:
    if not data:
        raise ValueError("empty NICE reply")
    code = data[0]
    return code - 256 if code >= 128 else code


def executor_request(info: int) -> bytes:
    request = NiceReadNode()
    request.permanent = 0
    request.info = info
    request.entity = NodeReqEntity(0, 0)
    return request.encode()


def read_executor_reply(connection, label: str, destination: Nodeid) -> None:
    multiple = False
    saw_item = False
    for _ in range(64):
        response = connection.recv()
        payload = bytes(response) if response.type == "data" else b""
        if response.type != "data" or not payload:
            raise RuntimeError(
                f"NICE {label} failed: type={response.type} "
                f"data={payload[:64].hex()}"
            )

        code = reply_code(payload)
        if code == 2:
            if multiple or saw_item:
                raise RuntimeError(
                    f"NICE {label} malformed multiple header: "
                    f"data={payload[:64].hex()}"
                )
            multiple = True
            continue
        if code == -128:
            if not multiple or not saw_item:
                raise RuntimeError(
                    f"NICE {label} unexpected list end: "
                    f"data={payload[:64].hex()}"
                )
            return
        if code < 0:
            raise RuntimeError(
                f"NICE {label} error {code}: data={payload[:64].hex()}"
            )

        try:
            reply = NodeReply(payload)
        except Exception as exc:
            raise RuntimeError(
                f"NICE {label} invalid node reply: "
                f"data={payload[:64].hex()}"
            ) from exc
        entity = reply.entity
        if not getattr(entity, "executor", False) and int(entity) != int(destination):
            raise RuntimeError(f"NICE {label} returned the wrong node")
        saw_item = True
        if not multiple:
            return

    raise RuntimeError(f"NICE {label} reply sequence exceeded 64 frames")


def main() -> int:
    if len(sys.argv) != 3:
        raise SystemExit(f"usage: {sys.argv[0]} API-SOCKET GATEWAY-NAME")
    destination_text = os.environ.get("VAX_ADDR")
    if not destination_text:
        raise SystemExit("area31-nice: VAX_ADDR is required")
    destination = Nodeid(destination_text)

    api_socket, system = sys.argv[1:]
    connector = SimpleApiConnector(api_socket)
    try:
        connection, response = connector.connect(
            system=system,
            dest=destination_text,
            remuser=19,
            localuser="NCP",
            data=VERSION,
        )
        if connection is None or response.type != "accept":
            raise RuntimeError("NML connect rejected")
        try:
            for label, info in REQUESTS:
                connection.data(executor_request(info))
                read_executor_reply(connection, label, destination)
        finally:
            connection.disconnect()
    finally:
        connector.close()

    print("area31-nice: executor summary/status/counters pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
