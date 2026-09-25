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

"""Parse PYRTR NCP SHOW KNOWN NODES output for allocation and survey."""

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


def parsed_rows(text: str) -> tuple[int, list[tuple[str, str, str]]]:
    row_count = 0
    by_address: dict[str, tuple[str, str, str]] = {}

    def remember(address: str, number: str, name: str | None, state: str) -> None:
        node_number = int(number, 10)
        if not 1 <= node_number <= 1023:
            return
        candidate = (address, name or "-", state)
        current = by_address.get(address)
        if current is None:
            by_address[address] = candidate
            return
        if current[1] == "-" and candidate[1] != "-":
            by_address[address] = candidate
            return
        if current[2] == "Unreachable" and candidate[2] != "Unreachable":
            by_address[address] = candidate

    for line in text.splitlines():
        executor = EXECUTOR_RE.match(line)
        if executor:
            remember(executor.group(1), executor.group(2), executor.group(3),
                     executor.group(4))
            continue
        match = ROW_RE.match(line)
        if not match:
            continue
        node_number = int(match.group(2), 10)
        if not 1 <= node_number <= 1023:
            continue
        row_count += 1
        remember(match.group(1), match.group(2), match.group(3), match.group(4))

    rows = sorted(by_address.values(),
                  key=lambda row: int(row[0].split(".", 1)[1]))
    return row_count, rows


def occupied_rows(text: str) -> tuple[int, list[tuple[str, str, str]]]:
    row_count, rows = parsed_rows(text)
    occupied = [
        row for row in rows
        if row[1] != "-" or row[2] != "Unreachable"
    ]
    return row_count, occupied


def occupied_nodes(text: str) -> tuple[int, list[str]]:
    row_count, rows = occupied_rows(text)
    return row_count, [row[0] for row in rows]


def selftest() -> int:
    sample = """    Executor node = 31.3 (PYRTR), State = On,
    Identification = DECnet/Python Area-31 Router at Washington, DC

Node            State        Links   Delay  Circuit      Next Node
31.1 (IMPVAX)   Reachable
31.2 (STATIC)   Unreachable
31.3            Unreachable
31.4            Unreachable
31.5            Reachable    0
31.6            Unreachable
noise 31.7 Reachable
31.1023          Unreachable
32.4 (OTHER)    Reachable
"""
    rows, occupied = occupied_nodes(sample)
    assert rows == 7
    assert occupied == ["31.1", "31.2", "31.3", "31.5"]
    _, manifest = occupied_rows(sample)
    assert manifest == [
        ("31.1", "IMPVAX", "Reachable"),
        ("31.2", "STATIC", "Unreachable"),
        ("31.3", "PYRTR", "On"),
        ("31.5", "-", "Reachable"),
    ]
    print("area31-parse-known selftest passed")
    return 0


def main() -> int:
    if sys.argv[1:] == ["--selftest"]:
        return selftest()
    manifest = len(sys.argv) == 3 and sys.argv[1] == "--manifest"
    if manifest:
        path = sys.argv[2]
    elif len(sys.argv) == 2:
        path = sys.argv[1]
    else:
        raise SystemExit(
            f"usage: {sys.argv[0]} NCP-OUTPUT | --manifest NCP-OUTPUT | --selftest"
        )
    text = pathlib.Path(path).read_text(encoding="utf-8", errors="replace")
    rows, occupied = occupied_rows(text)
    if rows == 0:
        raise SystemExit("area31-parse-known: no structured Area-31 node rows")
    if manifest:
        for address, name, state in occupied:
            print(f"{address}\t{name}\t{state}")
    else:
        for address, _name, _state in occupied:
            print(address)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
