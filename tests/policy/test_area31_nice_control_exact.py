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


"""Execute the delivered Area-31 NICE reader with only a mocked PyDECnet API."""

import importlib.util
from pathlib import Path
import sys
import types

SOURCE = Path(__file__).resolve().parents[1] / "lab/area31-nice.py"


class FakeEntity:
    executor = True

    def __int__(self):
        return (31 << 10) | 123


class FakeNodeReply:
    def __init__(self, payload):
        if payload != b"\x01VALID":
            raise ValueError("not a valid fixture node reply")
        self.entity = FakeEntity()


class Packet:
    type = "data"

    def __init__(self, payload):
        self.payload = payload

    def __bytes__(self):
        return self.payload


class Connection:
    def __init__(self, records):
        self.records = iter(records)

    def recv(self):
        return Packet(next(self.records))


def load_real_source():
    fake = types.ModuleType("decnet")
    common = types.ModuleType("decnet.common")
    common.Nodeid = int
    connectors = types.ModuleType("decnet.connectors")
    connectors.SimpleApiConnector = object
    nice = types.ModuleType("decnet.nicepackets")
    nice.NiceReadNode = object
    nice.NodeReply = FakeNodeReply
    nice.NodeReqEntity = object
    modules = {
        "decnet": fake,
        "decnet.common": common,
        "decnet.connectors": connectors,
        "decnet.nicepackets": nice,
    }
    original = {key: sys.modules.get(key) for key in modules}
    try:
        sys.modules.update(modules)
        spec = importlib.util.spec_from_file_location("dniv_area31_nice_test", SOURCE)
        assert spec and spec.loader
        target = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(target)
        return target
    finally:
        for key, old in original.items():
            if old is None:
                sys.modules.pop(key, None)
            else:
                sys.modules[key] = old


def check():
    module = load_real_source()
    accepted = (b"\x02", b"\x02\x00\x00\x00", b"\x02\x00\x00\x01x")
    done = (b"\x80", b"\x80\x00\x00\x00", b"\x80\x00\x00\x01x")
    for start in accepted:
        for end in done:
            module.read_executor_reply(Connection([start, b"\x01VALID", end]),
                                       "summary", (31 << 10) | 123)
    for bad in (b"\x02\x00", b"\x02\x00\x00", b"\x02\x00\x00\x03x"):
        try:
            module.read_executor_reply(Connection([bad, b"\x01VALID", b"\x80"]),
                                       "summary", (31 << 10) | 123)
        except RuntimeError:
            pass
        else:
            raise AssertionError("malformed ACCEPTED control passed")
    for bad in (b"\x80\x00", b"\x80\x00\x00", b"\x80\x00\x00\x03x"):
        try:
            module.read_executor_reply(Connection([b"\x02", b"\x01VALID", bad]),
                                       "summary", (31 << 10) | 123)
        except RuntimeError:
            pass
        else:
            raise AssertionError("malformed DONE control passed")
    print("Area-31 PyDECnet NICE control exact-length regression passed")


if __name__ == "__main__":
    check()
