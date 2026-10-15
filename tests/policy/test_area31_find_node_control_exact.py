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


"""Reject malformed NICE list controls in the real Area-31 name resolver."""

import importlib.util
from pathlib import Path
import sys
import types

SOURCE = Path(__file__).resolve().parents[1] / "lab/area31-find-node.py"
TARGET = (31 << 10) | 42


class FakeNodeid(int):
    def __str__(self):
        return f"{int(self) >> 10}.{int(self) & 1023}"


class FakeEntity:
    nodename = "QCOCAL"

    def __int__(self):
        return TARGET


class FakeNodeReply:
    def __init__(self, data):
        if data != b"\x01VALID":
            raise ValueError("unexpected data reply")
        self.entity = FakeEntity()


class FakeRequest:
    def encode(self):
        return b"READ"


class FakeRecord:
    type = "data"

    def __init__(self, data):
        self.data = data

    def __bytes__(self):
        return self.data


class FakeConnection:
    def __init__(self, records):
        self.records = iter(records)
        self.disconnected = False

    def data(self, data):
        assert data == b"READ"

    def recv(self):
        return FakeRecord(next(self.records))

    def disconnect(self):
        self.disconnected = True


class FakeConnector:
    records = ()
    last = None

    def __init__(self, api_socket):
        assert api_socket == "/nonexistent/mock.sock"

    def connect(self, **kwargs):
        assert kwargs["remuser"] == 19
        self.last = FakeConnection(self.records)
        FakeConnector.last = self.last
        return self.last, types.SimpleNamespace(type="accept")

    def close(self):
        pass


def load_actual_source():
    mods = {name: types.ModuleType(name) for name in (
        "decnet", "decnet.common", "decnet.connectors", "decnet.nicepackets"
    )}
    mods["decnet.common"].Nodeid = FakeNodeid
    mods["decnet.connectors"].SimpleApiConnector = FakeConnector
    mods["decnet.nicepackets"].NiceReadNode = FakeRequest
    mods["decnet.nicepackets"].NodeReply = FakeNodeReply
    mods["decnet.nicepackets"].NodeReqEntity = lambda node: node
    old = {name: sys.modules.get(name) for name in mods}
    try:
        sys.modules.update(mods)
        spec = importlib.util.spec_from_file_location("dniv_find_node_exact", SOURCE)
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        for name, value in old.items():
            if value is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = value


def check():
    module = load_actual_source()
    good_prefix = (b"\x02", b"\x02\x00\x00\x00",
                   b"\x02\x00\x00\x01x")
    good_suffix = (b"\x80", b"\x80\x00\x00\x00",
                   b"\x80\x00\x00\x01x")
    for before in good_prefix:
        for after in good_suffix:
            FakeConnector.records = (before, b"\x01VALID", after)
            found = module.find_node("/nonexistent/mock.sock", "gw", "31.3", "QCOCAL")
            assert found == "31.42", found
            assert FakeConnector.last.disconnected
    for before in (b"\x02\x00", b"\x02\x00\x00", b"\x02\x00\x00\x02x"):
        FakeConnector.records = (before, b"\x01VALID", b"\x80")
        try:
            module.find_node("/nonexistent/mock.sock", "gw", "31.3", "QCOCAL")
        except RuntimeError:
            pass
        else:
            raise AssertionError("malformed ACCEPTED control passed")
        assert FakeConnector.last.disconnected
    for after in (b"\x80\x00", b"\x80\x00\x00", b"\x80\x00\x00\x02x"):
        FakeConnector.records = (b"\x02", b"\x01VALID", after)
        try:
            module.find_node("/nonexistent/mock.sock", "gw", "31.3", "QCOCAL")
        except RuntimeError:
            pass
        else:
            raise AssertionError("malformed DONE control passed")
        assert FakeConnector.last.disconnected
    print("area31-find-node exact NICE controls passed")


if __name__ == "__main__":
    check()
