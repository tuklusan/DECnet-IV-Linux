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

"""PHONE directory oracle must not pass solely due to a TEST substring."""

from pathlib import Path
import runpy
import sys
import types

pkg = types.ModuleType('decnet')
pkg.__path__ = []
mod = types.ModuleType('decnet.connectors')
mod.SimpleApiConnector = object
sys.modules['decnet'] = pkg
sys.modules['decnet.connectors'] = mod
phone = runpy.run_path(str(Path(__file__).resolve().parents[1] / 'lab/pydecnet-phone.py'))
verify = phone['valid_directory_reply']
expected = f"{'TEST':<15} {'TEST':<15} {'LOCAL':<15} Available".encode('ascii')
assert verify(expected)
# Previously bytes(reply) just had to contain b'TEST'. Even a bogus greeting
# would be counted as a directory PASS.
for forged in (b'NOTEST', b'TEST', b'TEST\0', expected[:-1], expected+b'X',
               b'BAD!' + expected, b'Available ' + expected):
    assert b'TEST' in forged
    assert not verify(forged), forged
for i in range(len(expected)):
    broken = bytearray(expected)
    broken[i] ^= 1
    assert not verify(bytes(broken)), i
print('PHONE directory exact reply regression passed')
