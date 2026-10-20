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

"""Strict source helper identity syntax before any privileged packet operations."""

from pathlib import Path
import runpy

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = [
    "inject-nsp-ackrange.py", "inject-nsp-flow.py", "inject-nsp-intflow.py",
    "inject-nsp-intloss.py", "inject-nsp-reserved.py", "inject-pp11-s2.py",
    "observe-nsp-ccretry.py", "observe-nsp-diloss.py", "observe-nsp-keepalive.py",
]
BAD_MAC = [
    "aabbccddeeff", "aa:bb:cc:dd:ee:ff ", " aa:bb:cc:dd:ee:ff",
    "aa:bb:cc:dd:ee:ff\t", "a:abb:cc:dd:ee:ff", "aa:bb:cc:dd:ee:+f",
    "aa:bb:cc:dd:ee:fg", "aa:bb:cc:dd:ee:100",
]
BAD_NODE = [
    "+31.70", "31.+70", "-31.70", "31.-70", " 31.70", "31. 70",
    "31.70\t", "٣١.70", "31.٧٠", "31.70junk", "64.1", "31.1024",
]

for script in SCRIPTS:
    source = runpy.run_path(str(ROOT / "tests/lab" / script))
    mac = source["mac"]
    assert mac("AA:bb:01:00:eF:FE") == bytes.fromhex("aa bb 01 00 ef fe"), script
    for item in BAD_MAC:
        try:
            mac(item)
        except (ValueError, TypeError):
            continue
        raise AssertionError((script, "accepted malformed MAC", item))
    if "nodeaddr" in source:
        nodeaddr = source["nodeaddr"]
        assert nodeaddr("031.00070") == ((31 << 10) | 70), script
        for item in BAD_NODE:
            try:
                nodeaddr(item)
            except (ValueError, TypeError):
                continue
            raise AssertionError((script, "accepted malformed DECnet node", item))

print("privileged lab NSP injector/observer exact identity parsing passed")
