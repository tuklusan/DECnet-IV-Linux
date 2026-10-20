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

"""Reject false-green Session CI fields in the actual PCAP acceptance parser."""

import argparse
from pathlib import Path
import runpy

source = runpy.run_path(str(Path(__file__).resolve().parents[1] / 'lab/validate-interop-pcap.py'))
parse = source['session_ci_options']
mac = source['mac']

def counted(value: bytes) -> bytes:
    return bytes((len(value),)) + value

def ci(dest: bytes, sender: bytes, menu: int = 3, user: bytes = b'DNIVUSER',
       password: bytes = b'DNIVPASS', account: bytes = b'DNIVACCT',
       data: bytes = b'dniv-connect', suffix: bytes = b'') -> bytes:
    nsp = bytes((0x18,)) + bytes(8) + dest + sender + bytes((menu,))
    if menu & 1:
        nsp += counted(user) + counted(password) + counted(account)
    if menu & 2:
        nsp += counted(data)
    return nsp + suffix

D = bytes((0,25))
S = bytes((0,1))
expected = ((b'DNIVUSER', b'DNIVPASS', b'DNIVACCT'), b'dniv-connect')
assert parse(ci(D,S)) == expected
assert parse(ci(bytes((1,0,6))+b'MIRROR', bytes((2,0,0,0,0,0,6))+b'PYUSER')) == expected

def rejects(packet):
    try:
        parse(packet)
    except ValueError:
        return
    raise AssertionError(('malformed CI erroneously passed options oracle', packet))

for bad in (
    ci(D,S,menu=0x83), ci(D,S,suffix=b'junk'), ci(bytes((0,0)),S),
    ci(bytes((2,0,0,0,0,0,6))+b'MIRROR',S),
    ci(D, bytes((4,0))+bytes(8)+b'\x01X'),
    ci(D, bytes((1,1,1))+b'X'), ci(D,bytes((1,0,0))),
    ci(D,bytes((2,0,0,0,0,0,13))+b'A'*13),
    ci(D,S,user=b'A'*41), ci(D,S,data=b'B'*17),
):
    rejects(bad)

assert mac('AA:bb:00:01:02:03') == bytes.fromhex('aabb00010203')
for bad in ('aabb00010203', 'aa bb 00 01 02 03', 'AA:bb:00:01:02:03 ',
            'AA:bb:00:01:02:03:00', 'aa:bb:00:01:02:+3'):
    try:
        mac(bad)
    except argparse.ArgumentTypeError:
        continue
    raise AssertionError(('malformed MAC accepted',bad))
print('Interop CI options and six-octet MAC exact parser regression passed')
