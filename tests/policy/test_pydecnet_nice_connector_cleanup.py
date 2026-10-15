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

"""Every NICE connector must close even if initial connect rejects or throws."""

import importlib.util
from pathlib import Path
import sys
import types
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "tests/lab/pydecnet-nice-concurrent.py"


def check():
    decnet = types.ModuleType("decnet")
    connectors_mod = types.ModuleType("decnet.connectors")
    connectors_mod.SimpleApiConnector = object
    with mock.patch.dict(sys.modules, {"decnet": decnet,
                                      "decnet.connectors": connectors_mod}):
        spec = importlib.util.spec_from_file_location("pydecnet_nice_fixture", SOURCE)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

    for cause in ("raise", "reject"):
        instances = []

        class FakeConnector:
            def __init__(self, _socket):
                self.closed = False
                instances.append(self)

            def connect(self, **_kwargs):
                if cause == "raise":
                    raise OSError("simulated PyDECnet connector failure")
                return None, types.SimpleNamespace(type="reject", reason=6)

            def close(self):
                self.closed = True

        with mock.patch.object(module, "SimpleApiConnector", FakeConnector), \
             mock.patch.object(sys, "argv", ["test", "fake.sock", "31.91", "TEST", "2"]):
            try:
                module.main()
            except (OSError, RuntimeError):
                pass
            else:
                raise AssertionError(f"{cause} should fail closed")
        assert len(instances) == 1 and instances[0].closed, (
            f"PyDECnet connector leaked on {cause}")
    print("PyDECnet concurrent NICE reject/exception cleanup regression passed")


if __name__ == "__main__":
    check()
