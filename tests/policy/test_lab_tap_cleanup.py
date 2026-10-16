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

"""E2/E3/E4 VM lab teardown must remove all owned persistent TAPs."""

import importlib.util
from pathlib import Path
import sys
import tempfile
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
DRIVERS = ("dniv_e2.py", "dniv_e3.py", "dniv_e4.py")


class Capture:
    pid = 1234

    def __init__(self, *args, **kwargs):
        pass

    def poll(self):
        return None

    def wait(self, timeout=None):
        return 0

    def kill(self):
        pass


def exercise(script, tmp, fail_tap):
    spec = importlib.util.spec_from_file_location("dniv_tap_" + script.stem, script)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.modules.pop(spec.name, None)
    taps = set()
    created = 0

    def sudo(*args, **kwargs):
        nonlocal created
        if args[:3] == ("ip", "tuntap", "add"):
            created += 1
            if fail_tap and created == 2:
                raise RuntimeError("injected TAP creation failure")
            taps.add(args[4])
        elif args[:3] == ("ip", "tuntap", "del"):
            taps.discard(args[4])
        # Deleting a Linux bridge does not delete independently owned TAPs.
        return None

    lab = mod.Lab(tmp / "base", tmp / "kernel", tmp / "initrd",
                  tmp, "tap-fixture")
    groups = [["tap-first", "tap-second"]] + [
        [f"tap-extra-{i}"] for i in range(1, len(lab.bridges))]
    with (mock.patch.object(mod, "sudo", sudo),
          mock.patch.object(mod.subprocess, "Popen", Capture),
          mock.patch.object(mod.time, "sleep", lambda seconds: None)):
        try:
            try:
                lab.setup_network(groups)
                assert not fail_tap
            except RuntimeError as exc:
                assert fail_tap and "injected TAP creation" in str(exc)
        finally:
            lab.close()
    assert not taps, f"{script.name}: leaked owned TAP interfaces: {taps}"


def main():
    with tempfile.TemporaryDirectory(prefix="dniv-lab-taps-") as td:
        tmp = Path(td)
        for name in DRIVERS:
            source = ROOT / "tests/lab" / name
            exercise(source, tmp, False)
            exercise(source, tmp, True)
    print("E2/E3/E4 TAP cleanup regressions passed")


if __name__ == "__main__":
    main()
