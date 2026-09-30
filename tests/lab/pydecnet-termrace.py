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
import threading

from decnet.connectors import SimpleApiConnector

TERM_OBJECT = 246
CLIENTS = (("ABORT0", "abort"), ("ABORT1", "abort"),
           ("DISC0", "disconnect"), ("DISC1", "disconnect"))
RECOVER_NAME = "RECOVER"
RECOVER_PAYLOAD = b"term-recover"
RECOVER_DONE = b"recover-done"


def terminate_worker(api_socket: str, destination: str, system: str,
                     name: str, action: str, barrier: threading.Barrier,
                     errors: list[str]) -> None:
    connector = SimpleApiConnector(api_socket)
    try:
        connection, response = connector.connect(
            system=system,
            dest=destination,
            remuser=TERM_OBJECT,
            localuser=name,
        )
        if connection is None or response.type != "accept":
            raise RuntimeError(
                f"{name} rejected: {getattr(response, 'reason', None)!r}"
            )
        barrier.wait()
        index = name[-1]
        if action == "abort":
            connection.abort(f"abort-{index}".encode("ascii"))
        else:
            connection.disconnect(f"disconnect-{index}".encode("ascii"))
    except Exception as exc:
        errors.append(f"{name}:{exc!r}")
    finally:
        connector.close()


def main() -> int:
    if len(sys.argv) != 4:
        raise SystemExit(
            f"usage: {sys.argv[0]} API-SOCKET AREA.NODE PYDECNET-SYSTEM"
        )
    api_socket, destination, system = sys.argv[1:]
    barrier = threading.Barrier(len(CLIENTS))
    errors: list[str] = []
    threads = [
        threading.Thread(
            target=terminate_worker,
            args=(api_socket, destination, system, name, action,
                  barrier, errors),
            daemon=True,
        )
        for name, action in CLIENTS
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(40.0)
    if any(thread.is_alive() for thread in threads):
        raise RuntimeError("termination-race workers timed out")
    if errors:
        raise RuntimeError("; ".join(errors))

    connector = SimpleApiConnector(api_socket)
    try:
        connection, response = connector.connect(
            system=system,
            dest=destination,
            remuser=TERM_OBJECT,
            localuser=RECOVER_NAME,
        )
        if connection is None or response.type != "accept":
            raise RuntimeError(
                f"recovery rejected: {getattr(response, 'reason', None)!r}"
            )
        connection.data(RECOVER_PAYLOAD)
        reply = connection.recv()
        if reply.type != "data" or bytes(reply) != RECOVER_PAYLOAD:
            raise RuntimeError(
                f"bad recovery echo: type={reply.type!r} data={bytes(reply)!r}"
            )
        connection.disconnect(RECOVER_DONE)
    finally:
        connector.close()

    print(
        f"pydecnet-termrace: pass peer={destination} concurrent=4 "
        "abort=2 disconnect=2 recovery=1"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
