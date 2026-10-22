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

"""Real FAL CONFIG independence and bounded DAP record evidence."""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "tests/lab/pydecnet-fal.py"


class Reply:
    def __init__(self, value, reply_type="data"):
        self.value = value
        self.type = reply_type

    def __bytes__(self):
        return self.value


class Connection:
    def __init__(self, records):
        self.records = iter(records)

    def recv(self):
        return next(self.records)


def extract_contract():
    source = SOURCE.read_text()
    tree = ast.parse(source, filename=str(SOURCE))
    wanted_assignments = {"CONFIG", "CLIENT_BUFFER_LIMIT", "SERVER_BUFFER_LIMIT"}
    wanted_defs = {"BoundedConnection", "verify_config_reply"}
    selected = []
    for node in tree.body:
        if (isinstance(node, ast.Assign) and
                any(isinstance(target, ast.Name) and
                    target.id in wanted_assignments for target in node.targets)):
            selected.append(node)
        elif isinstance(node, (ast.ClassDef, ast.FunctionDef)) and node.name in wanted_defs:
            selected.append(node)
    assert len(selected) == 5, "missing CONFIG/oracle code in actual lab script"
    assert source.count("verify_config_reply(connection.recv())") == 6
    assert source.count("connection = BoundedConnection(connection)") == 6
    assert "bytes(reply) != CONFIG" not in source
    namespace = {}
    exec(compile(ast.Module(body=selected, type_ignores=[]),
                 str(SOURCE), "exec"), namespace)
    return namespace


def check():
    source = extract_contract()
    request = source["CONFIG"]
    bound = source["CLIENT_BUFFER_LIMIT"]
    server_bound = source["SERVER_BUFFER_LIMIT"]
    verify = source["verify_config_reply"]
    wrapped = source["BoundedConnection"]
    assert bound == 1024 and server_bound == 2048

    observed = request[:2] + server_bound.to_bytes(2, "little") + request[4:]
    assert observed != request, "regression must differ from the old echo oracle"
    verify(Reply(observed))

    malformed = (
        Reply(request),                              # client echo is NOT server CONFIG
        Reply(observed, "reject"),                 # wrong event
        Reply(observed[:-1]),                       # truncation
        Reply(observed + b"\x00"),                # trailing bytes
        Reply(b"\x01\x01" + observed[2:]),    # reserved flags
        Reply(observed[:4] + b"\x00" + observed[5:]), # wrong capability
        Reply(observed[:2] + b"\x00\x00" + observed[4:]),
        Reply(observed[:2] + b"\x00\x04" + observed[4:]),
    )
    for reply in malformed:
        try:
            verify(reply)
        except RuntimeError:
            continue
        raise AssertionError(f"accepted malformed FAL CONFIG: {bytes(reply)!r}")

    assert len(bytes(wrapped(Connection([Reply(b"X" * bound)])).recv())) == bound
    try:
        wrapped(Connection([Reply(b"X" * (bound + 1))])).recv()
    except RuntimeError:
        pass
    else:
        raise AssertionError("accepted frame above client advertised bound")
    # Peer disconnects remain typed events; framing checks target DAP DATA only.
    assert wrapped(Connection([Reply(b"", "disconnect")])).recv().type == "disconnect"
    print("FAL CONFIG own-capacity, malformed-peer and receive-bound regression passed")


if __name__ == "__main__":
    check()
