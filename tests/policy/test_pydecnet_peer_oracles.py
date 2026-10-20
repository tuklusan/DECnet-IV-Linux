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

"""Check independent PyDECnet peer source oracles without running network code."""

import runpy
import sys
import types
from pathlib import Path

pkg = types.ModuleType('decnet')
pkg.__path__ = []
conn_mod = types.ModuleType('decnet.connectors')
conn_mod.SimpleApiConnector = object
async_mod = types.ModuleType('decnet.async_connectors')
async_mod.AsyncApiConnector = object
sys.modules['decnet'] = pkg
sys.modules['decnet.connectors'] = conn_mod
sys.modules['decnet.async_connectors'] = async_mod
base = Path(__file__).resolve().parents[1] / 'lab'

http = runpy.run_path(str(base / 'pydecnet-http-server.py'))
valid = http['valid_object']
assert valid('HTTP') and valid('http2') and valid('A123456789012345')
for text in ('', '123HTTP', 'A'*17, 'HTΤP', 'MÄIL', 'HTTP-', 'AB C'):
    assert not valid(text), ('non-ASCII or malformed DECnet object', text)

mail = runpy.run_path(str(base / 'pydecnet-mail.py'))
verify_mail = mail['valid_mail_accept']
canonical = bytes((3, 1, 0, 18, 0, 0, 0, 0, 0xa0, 2, 0, 0, 1, 0, 0, 0))
assert verify_mail(canonical)
for i in range(len(canonical)):
    wrong = bytearray(canonical)
    wrong[i] ^= 1
    assert not verify_mail(bytes(wrong)), ('bad MAIL-11 negotiation accepted', i)
assert not verify_mail(canonical + b'\0')
assert not verify_mail(canonical[:-1])

nice = runpy.run_path(str(base / 'pydecnet-nice-concurrent.py'))
verify_status = nice['valid_status']
name = b'NODE'
header = bytes((1, 255, 255, 0)) + (31 << 10 | 70).to_bytes(2, 'little') + bytes((0x80 | len(name),)) + name
state = bytes((0, 0, 0x81, 0))
active_links = bytes((0x58, 0x02, 0x02, 2, 0))
positive = header + state + active_links
assert verify_status(positive)
# Old checker only verified len>=20 + status 4-byte prefix + state marker;
# thus a missing/corrupted Active Links entry passed the concurrent test.
missing = header + state + bytes((0, 0, 0, 0, 0))
assert len(missing) >= 20 and missing[:4] == b'\x01\xff\xff\x00'
assert missing[7 + len(name):11 + len(name)] == state
assert not verify_status(missing)
assert not verify_status(positive[:-1])
assert not verify_status(positive[:6] + bytes((0x00,)) + positive[7:])
assert not verify_status(positive[:-2] + bytes((0, 0)))
print('PyDECnet HTTP/MAIL/NICE exact peer source-oracle regression passed')
