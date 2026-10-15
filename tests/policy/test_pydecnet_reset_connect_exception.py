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

"""Reset stress connector must close if initial connect throws or is refused."""

import importlib.util
from pathlib import Path
import sys
import types
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "tests/lab/pydecnet-reset.py"


def check():
    package = types.ModuleType("decnet")
    connectors = types.ModuleType("decnet.connectors")
    connectors.SimpleApiConnector = object
    with mock.patch.dict(sys.modules, {"decnet": package, "decnet.connectors": connectors}):
        spec = importlib.util.spec_from_file_location("dniv_reset_test", SOURCE)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    for mode in ("raise", "reject", "success"):
        created = []

        class Fake:
            def __init__(self, _socket):
                self.closed = False
                created.append(self)

            def connect(self, **_kwargs):
                if mode == "raise":
                    raise OSError("injected connector failure")
                if mode == "reject":
                    return None, types.SimpleNamespace(type="reject", reason=38)
                return object(), types.SimpleNamespace(type="accept")

            def close(self):
                self.closed = True

        with mock.patch.object(mod, "SimpleApiConnector", Fake):
            if mode == "success":
                connector, conn = mod.connect("fake.sock", "31.91", "TEST", "ABORTER")
                assert conn is not None and not connector.closed
                connector.close()
            else:
                try:
                    mod.connect("fake.sock", "31.91", "TEST", "ABORTER")
                except (OSError, RuntimeError):
                    pass
                else:
                    raise AssertionError(f"{mode}: expected failure")
        assert len(created) == 1 and created[0].closed, f"{mode}: leaked connector"
    print("PyDECnet reset connector exception/reject cleanup regression passed")


if __name__ == "__main__":
    check()
