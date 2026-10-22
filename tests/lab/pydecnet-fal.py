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

# DAP peers independently advertise their OWN complete-message capacities.
# The client offers 1024; the native FAL server offers its own 2048.
SERVER_BUFFER_LIMIT = 2048
CLIENT_BUFFER_LIMIT = int.from_bytes(CONFIG[2:4], "little")


class BoundedConnection:
    """Reject peer DAP frames exceeding the buffer advertised by this client."""

    def __init__(self, connection):
        self.connection = connection

    def recv(self):
        reply = self.connection.recv()
        if reply.type == "data" and len(bytes(reply)) > CLIENT_BUFFER_LIMIT:
            raise RuntimeError("FAL peer exceeded advertised receive bound")
        return reply

    def __getattr__(self, name):
        return getattr(self.connection, name)


def verify_config_reply(reply):
    raw = bytes(reply)
    if (reply.type != "data" or len(raw) != len(CONFIG) or
            raw[:2] != CONFIG[:2] or raw[4:] != CONFIG[4:] or
            int.from_bytes(raw[2:4], "little") != SERVER_BUFFER_LIMIT):
        raise RuntimeError(
            f"bad FAL CONFIG reply type={reply.type!r} data={raw!r}"
        )

def main() -> int:
    if len(sys.argv) != 4:
        raise SystemExit(f"usage: {sys.argv[0]} API-SOCKET AREA.NODE SYSTEM")
    api_socket, destination, system = sys.argv[1:]
    connector = SimpleApiConnector(api_socket)
    try:
        denied, response = connector.connect(
            system=system,
            dest=destination,
            remuser=17,
            localuser="PYFAL",
            username="FALUSER", password="WRONG", account="FALACCT",
        )
        if denied is None or response.type != "accept":
            raise RuntimeError("FAL negative-auth transport connect failed")
        denied.data(CONFIG)
        reply = denied.recv()
        if reply.type not in ("disconnect", "abort", "reject"):
            raise RuntimeError(
                f"bad FAL negative-auth outcome: {reply.type!r}"
            )
        denied.close()

        connection, response = connector.connect(
            system=system,
            dest=destination,
            remuser=17,
            localuser="PYFAL",
            username="FALUSER", password="FALPASS", account="FALACCT",
        )
        if connection is None or response.type != "accept":
            raise RuntimeError(
                f"FAL connect rejected: {getattr(response, 'reason', 'unknown')}"
            )
        connection = BoundedConnection(connection)
        connection.data(CONFIG)
        verify_config_reply(connection.recv())

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

        connection, response = connector.connect(
            system=system,
            dest=destination,
            remuser=17,
            localuser="PYFAL",
            username="FALUSER", password="FALPASS", account="FALACCT",
        )
        if connection is None or response.type != "accept":
            raise RuntimeError(
                f"FAL create rejected: {getattr(response, 'reason', 'unknown')}"
            )
        connection = BoundedConnection(connection)
        connection.data(CONFIG)
        verify_config_reply(connection.recv())

        name = b"UPLOAD.BIN"
        connection.data(bytes((2, 0, 0x0f, 1, 0, 3, 4)))
        connection.data(bytes((3, 0, 2, 0, len(name))) + name)
        reply = connection.recv()
        if reply.type != "data" or bytes(reply) != bytes((2, 0, 0x0f, 1, 0, 3, 4)):
            raise RuntimeError(f"bad FAL create attributes: {bytes(reply)!r}")
        reply = connection.recv()
        if reply.type != "data" or bytes(reply) != bytes((6, 0)):
            raise RuntimeError(f"bad FAL create ACK: {bytes(reply)!r}")
        connection.data(bytes((4, 0, 2)))
        reply = connection.recv()
        if reply.type != "data" or bytes(reply) != bytes((6, 0)):
            raise RuntimeError(f"bad FAL create connect ACK: {bytes(reply)!r}")
        connection.data(bytes((4, 0, 4)))
        connection.data(bytes((8, 0, 0)) + b"PUT-A")
        connection.data(bytes((8, 0, 0)) + bytes((0, 1, 2, 3)))
        connection.data(bytes((7, 0, 1)))
        reply = connection.recv()
        if reply.type != "data" or bytes(reply) != bytes((7, 0, 2)):
            raise RuntimeError(f"bad FAL create close reply: {bytes(reply)!r}")
        connection.disconnect()

        connection, response = connector.connect(
            system=system, dest=destination, remuser=17, localuser="PYFAL",
            username="FALUSER", password="FALPASS", account="FALACCT",
        )
        if connection is None or response.type != "accept":
            raise RuntimeError("FAL metadata get connect rejected")
        connection = BoundedConnection(connection)
        connection.data(CONFIG)
        verify_config_reply(connection.recv())
        name = b"UPLOAD.BIN"
        connection.data(bytes((3, 0, 1, 0, len(name))) + name)
        reply = connection.recv()
        if reply.type != "data" or bytes(reply) != bytes((2, 0, 0x0f, 1, 0, 3, 4)):
            raise RuntimeError(f"bad persisted FAL metadata: {bytes(reply)!r}")
        reply = connection.recv()
        if reply.type != "data" or bytes(reply) != bytes((6, 0)):
            raise RuntimeError(f"bad metadata-open ACK: {bytes(reply)!r}")
        connection.data(bytes((4, 0, 2)))
        reply = connection.recv()
        if reply.type != "data" or bytes(reply) != bytes((6, 0)):
            raise RuntimeError(f"bad metadata CONNECT ACK: {bytes(reply)!r}")
        connection.data(bytes((4, 0, 1)))
        payload = bytearray()
        while True:
            reply = connection.recv()
            raw = bytes(reply)
            if reply.type != "data":
                raise RuntimeError(f"bad metadata GET message type: {reply.type!r}")
            if raw[:1] == bytes((8,)):
                if len(raw) < 3 or raw[:3] != bytes((8, 0, 0)):
                    raise RuntimeError(f"bad metadata GET DAP DATA: {raw!r}")
                payload += raw[3:]
                continue
            if raw == bytes((9, 0, 0x27, 0x40)):
                break
            raise RuntimeError(f"unexpected metadata GET record: {raw!r}")
        if bytes(payload) != b"PUT-A" + bytes((0, 1, 2, 3)):
            raise RuntimeError(f"bad metadata GET payload: {bytes(payload)!r}")
        connection.data(bytes((7, 0, 1)))
        reply = connection.recv()
        if reply.type != "data" or bytes(reply) != bytes((7, 0, 2)):
            raise RuntimeError(f"bad metadata GET close: {bytes(reply)!r}")
        connection.disconnect()

        connection, response = connector.connect(
            system=system, dest=destination, remuser=17, localuser="PYFAL",
            username="FALUSER", password="FALPASS", account="FALACCT",
        )
        if connection is None or response.type != "accept":
            raise RuntimeError("FAL rename connect rejected")
        connection = BoundedConnection(connection)
        connection.data(CONFIG)
        verify_config_reply(connection.recv())
        oldname = b"UPLOAD.BIN"
        newname = b"RENAMED.BIN"
        connection.data(bytes((3, 0, 3, 0, len(oldname))) + oldname)
        connection.data(bytes((15, 0, 1, len(newname))) + newname)
        reply = connection.recv()
        if reply.type != "data" or bytes(reply) != bytes((7, 0, 2)):
            raise RuntimeError(f"bad FAL rename response: {bytes(reply)!r}")
        connection.disconnect()

        connection, response = connector.connect(
            system=system, dest=destination, remuser=17, localuser="PYFAL",
            username="FALUSER", password="FALPASS", account="FALACCT",
        )
        if connection is None or response.type != "accept":
            raise RuntimeError("FAL directory connect rejected")
        connection = BoundedConnection(connection)
        connection.data(CONFIG)
        verify_config_reply(connection.recv())
        pattern = b"*"
        connection.data(bytes((3, 0, 6, 0, len(pattern))) + pattern)
        names = set()
        while True:
            reply = connection.recv()
            if reply.type != "data":
                raise RuntimeError(f"bad FAL directory type={reply.type!r}")
            raw = bytes(reply)
            if raw == bytes((7, 0, 2)):
                break
            if len(raw) < 4 or raw[0] != 15 or raw[2] != 1 or len(raw) != 4 + raw[3]:
                raise RuntimeError(f"bad FAL directory record: {raw!r}")
            name = raw[4:].decode("ascii")
            if name in names:
                raise RuntimeError(f"duplicate FAL directory entry: {name!r}")
            names.add(name)
        if names != {"SERVER.TXT", "RENAMED.BIN"}:
            raise RuntimeError(f"bad FAL directory names: {sorted(names)!r}")
        connection.disconnect()

        connection, response = connector.connect(
            system=system, dest=destination, remuser=17, localuser="PYFAL",
            username="FALUSER", password="FALPASS", account="FALACCT",
        )
        if connection is None or response.type != "accept":
            raise RuntimeError("FAL erase connect rejected")
        connection = BoundedConnection(connection)
        connection.data(CONFIG)
        verify_config_reply(connection.recv())
        name = b"RENAMED.BIN"
        connection.data(bytes((3, 0, 4, 0, len(name))) + name)
        reply = connection.recv()
        if reply.type != "data" or bytes(reply) != bytes((7, 0, 2)):
            raise RuntimeError(f"bad FAL erase response: {bytes(reply)!r}")
        connection.disconnect()
    finally:
        connector.close()
    print(f"pydecnet-fal: pass peer={destination} object=17 get,put,metadata,rename,dir,erase")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
