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

"""NICE status Active Links parameter must have BOTH declared value octets."""

from pathlib import Path
import textwrap

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "tests/lab/pydecnet-nice.py"


def validator():
    source = SOURCE.read_text()
    begin = source.index('        if len(status) < 20 or status[0] != 1')
    end = source.index('        connection.data(COUNTERS_REQUEST)', begin)
    block = textwrap.dedent(source[begin:end])
    code = 'def run(status):\n' + textwrap.indent(block, '    ') + '\n    return active_links\n'
    ns = {}
    exec(compile(code, str(SOURCE), 'exec'), ns)
    return ns['run']


def fixture(value: bytes) -> bytes:
    name = b'ABCDE'
    return (bytes.fromhex('01 ff ff 00 3c 7c') + bytes((0x80 | len(name),)) +
            name + bytes.fromhex('00 00 81 00 58 02 02') + value)


def check():
    run = validator()
    assert run(fixture(b'\x02\x00')) == 2
    assert run(fixture(b'\x01\x00')) == 1
    for truncated in (fixture(b'\x02'), fixture(b'')):
        assert len(truncated) >= 19
        try:
            run(truncated)
        except RuntimeError:
            continue
        raise AssertionError(f'truncated NICE Active Links field accepted: {truncated!r}')
    print('NICE Active Links declared-width source regression passed')


if __name__ == '__main__':
    check()
