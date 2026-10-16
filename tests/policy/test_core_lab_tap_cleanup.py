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

"""The Phase2/E1 lab must release TAPs even before guests are launched."""

import importlib.util
from pathlib import Path
import sys
import tempfile
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "tests/lab/dniv_lab.py"


class Capture:
    pid = 2222

    def __init__(self, *args, **kwargs):
        pass

    def poll(self):
        return None

    def wait(self, timeout=None):
        return 0

    def kill(self):
        pass


def check_one(mod, root, fail_second):
    owned = set()
    count = 0

    def sudo(*args, **kwargs):
        nonlocal count
        if args[:3] == ("ip", "tuntap", "add"):
            count += 1
            if fail_second and count == 2:
                raise RuntimeError("injected second TAP failure")
            owned.add(args[4])
        elif args[:3] == ("ip", "tuntap", "del"):
            owned.discard(args[4])
        elif args[:3] == ("ip", "link", "del"):
            # ip link del can remove the named interface, but deleting a
            # bridge does not remove its separately created persistent TAPs.
            owned.discard(args[3])
        return None

    work = root / ("failed" if fail_second else "normal")
    work.mkdir()
    (work / "lan.pcap").write_bytes(b"pcap")
    lab = mod.Lab(root / "base", root / "kernel", None, work,
                  "phase2", "test", "virtio-net-pci", 1, "none", 512, False)
    with (mock.patch.object(mod, "sudo", sudo),
          mock.patch.object(mod.subprocess, "Popen", Capture)):
        try:
            try:
                lab.create_network(["dnivtesttap0", "dnivtesttap1"])
                assert not fail_second
            except RuntimeError as exc:
                assert fail_second and "injected second TAP" in str(exc)
        finally:
            # No QEMU guests started yet: their inventory is empty.
            assert lab.guests == []
            lab.close()
    assert not owned, f"Phase2/E1 lab left TAPs behind: {owned}"


def check():
    spec = importlib.util.spec_from_file_location("dniv_phase2_tap_lab", SOURCE)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.modules.pop(spec.name, None)
    with tempfile.TemporaryDirectory(prefix="dniv-phase2-tap-") as d:
        root = Path(d)
        check_one(mod, root, False)
        check_one(mod, root, True)
    print("Phase2/E1 TAP ownership regression passed")


if __name__ == "__main__":
    check()
