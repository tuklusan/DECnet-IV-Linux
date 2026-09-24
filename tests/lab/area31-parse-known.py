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

"""Extract occupied Area-31 identities from NCP SHOW KNOWN NODES output."""

from __future__ import annotations

import pathlib
import re
import sys

EXECUTOR_RE = re.compile(
    r"^\s*Executor node\s*=\s*(31\.(\d{1,4}))"
    r"(?:\s+\(([A-Za-z0-9]{1,6})\))?"
    r",\s*State\s*=\s*(On|Off|Shut|Restricted|Reachable|Unreachable),?\s*$"
)
ROW_RE = re.compile(
    r"^\s*(31\.(\d{1,4}))"
    r"(?:\s+\(([A-Za-z0-9]{1,6})\))?"
    r"\s+(On|Off|Shut|Restricted|Reachable|Unreachable)(?=\s|$)"
)


def occupied_nodes(text: str) -> tuple[int, list[str]]:
    rows = 0
    occupied: set[str] = set()
    for line in text.splitlines():
        executor = EXECUTOR_RE.match(line)
        if executor:
            node_number = int(executor.group(2), 10)
            if 1 <= node_number <= 1023:
                occupied.add(executor.group(1))
            continue
        match = ROW_RE.match(line)
        if not match:
            continue
        node_number = int(match.group(2), 10)
        if not 1 <= node_number <= 1023:
            continue
        rows += 1
        address, name, state = match.group(1), match.group(3), match.group(4)
        if name is not None or state != "Unreachable":
            occupied.add(address)
    return rows, sorted(occupied, key=lambda value: int(value.split(".", 1)[1]))


def selftest() -> int:
    sample = """    Executor node = 31.3 (PYRTR), State = On,
    Identification = DECnet/Python Area-31 Router at Washington, DC

Node            State        Links   Delay  Circuit      Next Node
31.1 (IMPVAX)   Reachable
31.2 (STATIC)   Unreachable
31.4            Unreachable
31.5            Reachable    0
31.6            Unreachable
noise 31.7 Reachable
31.1023          Unreachable
32.4 (OTHER)    Reachable
"""
    rows, occupied = occupied_nodes(sample)
    assert rows == 6
    assert occupied == ["31.1", "31.2", "31.3", "31.5"]
    print("area31-parse-known selftest passed")
    return 0


def main() -> int:
    if sys.argv[1:] == ["--selftest"]:
        return selftest()
    if len(sys.argv) != 2:
        raise SystemExit(f"usage: {sys.argv[0]} NCP-OUTPUT | --selftest")
    text = pathlib.Path(sys.argv[1]).read_text(encoding="utf-8", errors="replace")
    rows, occupied = occupied_nodes(text)
    if rows == 0:
        raise SystemExit("area31-parse-known: no structured Area-31 node rows")
    for address in occupied:
        print(address)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
