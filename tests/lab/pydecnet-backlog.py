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

COUNT = 4
OBJECT = 241


def worker(api_socket: str, destination: str, system: str, index: int,
           barrier: threading.Barrier, errors: list[str]) -> None:
    connector = SimpleApiConnector(api_socket)
    try:
        barrier.wait()
        connection, response = connector.connect(
            system=system,
            dest=destination,
            remuser=OBJECT,
            localuser=f"BKL{index}",
        )
        if connection is None or response.type != "accept":
            raise RuntimeError(f"connect {index} rejected: {getattr(response, 'reason', None)!r}")
        payload = f"backlog-{index}".encode("ascii")
        connection.data(payload)
        reply = connection.recv()
        if reply.type != "data" or bytes(reply) != payload:
            raise RuntimeError(f"bad echo {index}: type={reply.type!r} data={bytes(reply)!r}")
        connection.disconnect()
    except Exception as exc:
        errors.append(f"{index}:{exc!r}")
    finally:
        connector.close()


def main() -> int:
    if len(sys.argv) != 4:
        raise SystemExit(f"usage: {sys.argv[0]} API-SOCKET AREA.NODE PYDECNET-SYSTEM")
    api_socket, destination, system = sys.argv[1:]
    barrier = threading.Barrier(COUNT)
    errors: list[str] = []
    threads = [
        threading.Thread(
            target=worker,
            args=(api_socket, destination, system, i, barrier, errors),
            daemon=True,
        )
        for i in range(COUNT)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(40.0)
    if any(thread.is_alive() for thread in threads):
        raise RuntimeError("backlog workers timed out")
    if errors:
        raise RuntimeError("; ".join(errors))
    print(f"pydecnet-backlog: pass peer={destination} queued={COUNT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
