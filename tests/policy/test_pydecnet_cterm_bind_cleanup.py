#!/usr/bin/env python3
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

"""A failed PyDECnet CTERM listener bind must close every acquired resource."""

import asyncio
import importlib.util
from pathlib import Path
import sys
import types

SOURCE = Path(__file__).resolve().parents[2] / "tests/lab/pydecnet-cterm.py"


def exercise(failure_stage: int):
    state = {"started": False, "closed": False, "listeners": []}

    class FakeListener:
        def __init__(self):
            self.closed = False

        def close(self):
            self.closed = True

    class FakeConnector:
        def __init__(self, socket):
            self.socket = socket
            state["connector"] = self

        async def start(self):
            if failure_stage == 0:
                raise RuntimeError("synthetic start failure")
            state["started"] = True

        async def bind(self, *_args, **_kwargs):
            if len(state["listeners"]) + 1 == failure_stage:
                raise RuntimeError("synthetic bind failure")
            listener = FakeListener()
            state["listeners"].append(listener)
            return listener

        async def close(self):
            state["closed"] = True

    async_mod = types.ModuleType("decnet.async_connectors")
    async_mod.AsyncApiConnector = FakeConnector
    root_mod = types.ModuleType("decnet")
    root_mod.async_connectors = async_mod
    saved = {name: sys.modules.get(name) for name in ("decnet", "decnet.async_connectors")}
    sys.modules.update({"decnet": root_mod, "decnet.async_connectors": async_mod})
    try:
        spec = importlib.util.spec_from_file_location("dniv_cterm_test", SOURCE)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        try:
            asyncio.run(module.serve("unused-local-api", "TEST"))
        except RuntimeError as exc:
            assert str(exc) in ("synthetic start failure", "synthetic bind failure"), exc
        else:
            raise AssertionError("expected startup or bind failure")
    finally:
        for name, original in saved.items():
            if original is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = original
    if not state["closed"]:
        raise AssertionError(f"connector leaked after failure stage {failure_stage}")
    if any(not listener.closed for listener in state["listeners"]):
        raise AssertionError(f"listener leaked after failure stage {failure_stage}")


def main():
    for stage in (0, 1, 2, 3):
        exercise(stage)
    print("PyDECnet CTERM partial listener bind cleanup regression passed")


if __name__ == "__main__":
    main()
