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

"""DAP FAL directory oracle rejects duplicates, not just unexpected names."""

import ast
from pathlib import Path
import textwrap

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "tests/lab/pydecnet-fal.py"


class Reply:
    type = "data"

    def __init__(self, data):
        self.data = data

    def __bytes__(self):
        return self.data


class Connection:
    def __init__(self, records):
        self.records = iter(records)

    def recv(self):
        return next(self.records)


def parser():
    source = SOURCE.read_text()
    tree = ast.parse(source, filename=str(SOURCE))
    candidates = [node for node in ast.walk(tree) if isinstance(node, ast.While)
                  and "bad FAL directory record" in ast.get_source_segment(source, node)]
    assert len(candidates) == 1, "directory parser not uniquely located"
    loop = textwrap.dedent(ast.get_source_segment(source, candidates[0]))
    namespace = {}
    body = ("def run(connection):\n    names = set()\n"
            + textwrap.indent(loop, "    ")
            + "\n    if names != {'SERVER.TXT', 'RENAMED.BIN'}:\n"
              "        raise RuntimeError('bad directory names')\n"
              "    return names\n")
    exec(compile(body, str(SOURCE), "exec"), namespace)
    return namespace["run"]


def name(value):
    encoded = value.encode("ascii")
    return Reply(bytes((15, 0, 1, len(encoded))) + encoded)


def check():
    run = parser()
    eof = Reply(bytes((7, 0, 2)))
    good = [name("SERVER.TXT"), name("RENAMED.BIN"), eof]
    assert run(Connection(good)) == {"SERVER.TXT", "RENAMED.BIN"}
    bad_cases = (
        [name("SERVER.TXT"), name("SERVER.TXT"), name("RENAMED.BIN"), eof],
        [name("SERVER.TXT"), name("RENAMED.BIN"), name("RENAMED.BIN"), eof],
        [name("SERVER.TXT"), name("UNEXPECTED.BIN"), eof],
    )
    for bad in bad_cases:
        try:
            run(Connection(bad))
        except RuntimeError:
            continue
        raise AssertionError(f"duplicate/unexpected FAL name records accepted: {bad!r}")
    print("PyDECnet FAL directory unique-name evidence regression passed")


if __name__ == "__main__":
    check()
