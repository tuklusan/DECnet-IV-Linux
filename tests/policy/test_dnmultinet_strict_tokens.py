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
"""The actual PyDECnet MULTINET bridge must reject trailing newline tokens.

Python '$' anchors before a single terminal newline, so regex.match alone is
not sufficient to validate a name later interpolated in routing config lines.
"""

import argparse
from pathlib import Path
import runpy

SOURCE = Path(__file__).resolve().parents[2] / "userspace/dnmultinet/dnmultinet.py"


def check():
    code = runpy.run_path(str(SOURCE), run_name="dniv_source_test")
    node_address = code["node_address"]
    node_name = code["node_name"]
    assert node_address("31.70") == "31.70"
    assert node_address("31.0070") == "31.70"
    assert node_name("Router") == "ROUTER"
    for value in ("31.70\n", "31.70\r", "31.70 ", "0.1", "63.1024"):
        try:
            node_address(value)
        except argparse.ArgumentTypeError:
            continue
        raise AssertionError(f"accepted invalid node address token: {value!r}")
    for value in ("NODE\n", "NODE\r", "NODE ", "TOOLONG", "1NODE", "\n"):
        try:
            node_name(value)
        except argparse.ArgumentTypeError:
            continue
        raise AssertionError(f"accepted invalid node name token: {value!r}")
    print("MULTINET strict whole-token node and name validation passed")


if __name__ == "__main__":
    check()
