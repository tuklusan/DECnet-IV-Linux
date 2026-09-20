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

QUEUE_COUNT = 4
QUEUE_OBJECT = 241
OVERFLOW_COUNT = 3
OVERFLOW_OBJECT = 242
CLOSE_RACE_OBJECT = 243
OBJECT_BUSY = 6


def worker(api_socket: str, destination: str, system: str, index: int,
           object_number: int, barrier: threading.Barrier,
           results: list[str | None], errors: list[str]) -> None:
    connector = SimpleApiConnector(api_socket)
    try:
        barrier.wait()
        connection, response = connector.connect(
            system=system,
            dest=destination,
            remuser=object_number,
            localuser=f"BKL{index}",
        )
        if connection is None or response.type != "accept":
            reason = getattr(response, "reason", None)
            if object_number == OVERFLOW_OBJECT and reason == OBJECT_BUSY:
                results[index] = "busy"
                return
            raise RuntimeError(f"connect {index} rejected: {reason!r}")
        payload = f"backlog-{index}".encode("ascii")
        connection.data(payload)
        reply = connection.recv()
        if reply.type != "data" or bytes(reply) != payload:
            raise RuntimeError(
                f"bad echo {index}: type={reply.type!r} data={bytes(reply)!r}"
            )
        connection.disconnect()
        results[index] = "accept"
    except Exception as exc:
        errors.append(f"{index}:{exc!r}")
    finally:
        connector.close()


def main() -> int:
    if len(sys.argv) not in (4, 5):
        raise SystemExit(
            f"usage: {sys.argv[0]} API-SOCKET AREA.NODE PYDECNET-SYSTEM [overflow|close-race]"
        )
    api_socket, destination, system = sys.argv[1:4]
    mode = sys.argv[4] if len(sys.argv) == 5 else "queue"
    if mode not in ("queue", "overflow", "close-race"):
        raise SystemExit(f"unsupported backlog mode: {mode}")
    overflow = mode == "overflow"
    close_race = mode == "close-race"
    count = OVERFLOW_COUNT if overflow else QUEUE_COUNT
    object_number = (OVERFLOW_OBJECT if overflow else
                     CLOSE_RACE_OBJECT if close_race else QUEUE_OBJECT)
    barrier = threading.Barrier(count)
    errors: list[str] = []
    results: list[str | None] = [None] * count
    threads = [
        threading.Thread(
            target=worker,
            args=(
                api_socket, destination, system, i, object_number,
                barrier, results, errors,
            ),
            daemon=True,
        )
        for i in range(count)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(40.0)
    if any(thread.is_alive() for thread in threads):
        raise RuntimeError("backlog workers timed out")
    if errors:
        raise RuntimeError("; ".join(errors))
    if overflow:
        accepted = results.count("accept")
        busy = results.count("busy")
        if accepted != 2 or busy != 1:
            raise RuntimeError(
                f"overflow outcomes unexpected: accepted={accepted} busy={busy} "
                f"results={results!r}"
            )
        print(
            f"pydecnet-backlog: overflow pass peer={destination} "
            f"accepted={accepted} busy={busy}"
        )
    else:
        if results != ["accept"] * count:
            raise RuntimeError(f"{mode} outcomes unexpected: {results!r}")
        if close_race:
            print(f"pydecnet-backlog: close-race pass peer={destination} cycles={count}")
        else:
            print(f"pydecnet-backlog: pass peer={destination} queued={count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
