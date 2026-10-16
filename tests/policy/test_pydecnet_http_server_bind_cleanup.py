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

"""HTTP PyDECnet connector cleanup must cover pre-listener start/bind errors."""

import asyncio
import importlib.util
from pathlib import Path
import sys
import types

SOURCE = Path(__file__).resolve().parents[2] / "tests/lab/pydecnet-http-server.py"


def check(fail_start: bool) -> None:
    state = {"closed": False}

    class FakeConnector:
        def __init__(self, *_args):
            pass

        async def start(self):
            if fail_start:
                raise RuntimeError("start denied")

        async def bind(self, **_kwargs):
            raise RuntimeError("bind denied")

        async def close(self):
            state["closed"] = True

    module_name = "decnet.async_connectors"
    package = types.ModuleType("decnet")
    module = types.ModuleType(module_name)
    module.AsyncApiConnector = FakeConnector
    saved = {name: sys.modules.get(name) for name in ("decnet", module_name)}
    sys.modules["decnet"] = package
    sys.modules[module_name] = module
    try:
        spec = importlib.util.spec_from_file_location("dniv_http_stub", SOURCE)
        imported = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(imported)
        try:
            asyncio.run(imported.serve_one("unused", "TEST", "HTTP", "MARKER"))
        except RuntimeError as exc:
            if str(exc) != ("start denied" if fail_start else "bind denied"):
                raise
        else:
            raise AssertionError("missing synthetic bind/start error")
    finally:
        for name, previous in saved.items():
            if previous is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = previous
    if not state["closed"]:
        raise AssertionError(f"HTTP connector leaked on fail_start={fail_start}")


def main():
    check(True)
    check(False)
    print("PyDECnet HTTP bind cleanup regression passed")


if __name__ == "__main__":
    main()
