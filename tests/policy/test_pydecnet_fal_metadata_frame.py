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

"""Metadata DAP GET oracle must reject malformed DATA control/record headers."""

import ast
from pathlib import Path
import textwrap


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "tests/lab/pydecnet-fal.py"
EXPECTED = b"PUT-A\x00\x01\x02\x03"
EOF = bytes((9, 0, 0x27, 0x40))


class Reply:
    def __init__(self, data, reply_type="data"):
        self.data = data
        self.type = reply_type

    def __bytes__(self):
        return self.data


class Connection:
    def __init__(self, records):
        self.records = iter(records)

    def recv(self):
        return next(self.records)


def validator():
    source = SOURCE.read_text()
    tree = ast.parse(source, filename=str(SOURCE))
    candidates = [node for node in ast.walk(tree) if isinstance(node, ast.While)
                  and "unexpected metadata GET record" in ast.get_source_segment(source, node)]
    assert len(candidates) == 1, "metadata GET parser not uniquely located"
    loop = textwrap.dedent(ast.get_source_segment(source, candidates[0]))
    namespace = {}
    body = ("def run(connection):\n    payload = bytearray()\n"
            + textwrap.indent(loop, "    ")
            + "\n    return bytes(payload)\n")
    exec(compile(body, str(SOURCE), "exec"), namespace)
    return namespace["run"]


def check():
    run = validator()
    good = [Reply(b"\x08\x00\x00" + EXPECTED[:4]),
            Reply(b"\x08\x00\x00" + EXPECTED[4:]), Reply(EOF)]
    assert run(Connection(good)) == EXPECTED
    malformed = (
        [Reply(b"\x08\xff\xff" + EXPECTED), Reply(EOF)],
        [Reply(b"\x08\x00\x01" + EXPECTED), Reply(EOF)],
        [Reply(b"\x08\x00\x00" + EXPECTED, "disconnect"), Reply(EOF)],
        [Reply(b"\x08\x00\x00" + EXPECTED), Reply(EOF, "reject")],
    )
    for records in malformed:
        try:
            payload = run(Connection(records))
        except RuntimeError:
            continue
        raise AssertionError(f"malformed metadata DATA accepted: {records!r} payload={payload!r}")
    print("PyDECnet FAL metadata GET exact-record regression passed")


if __name__ == "__main__":
    check()
