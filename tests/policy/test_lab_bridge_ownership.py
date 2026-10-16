#!/usr/bin/env python3
# ============================================================================
# Copyright (c) 2026 Supratim Sanyal of SANYALnet Labs.
# Proprietary rights reserved except as expressly licensed herein.
# DECnet-IV-Linux
# This file is governed by the SANYALnet Labs Non-Commercial License in the
# root LICENSE file. Non-Commercial use is permitted; Commercial Use and use
# for AI/ML model training are prohibited unless separately authorized.
# Attribution is required: "Based on original work by Supratim Sanyal of
# SANYALnet Labs." See LICENSE for full terms.
# ============================================================================
"""Failed bridge creation must not delete an unowned host network interface."""

from pathlib import Path
from unittest import mock
import importlib
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests/lab"))


class Capture:
    pid = 123456

    def poll(self):
        return None

    def wait(self, timeout=None):
        return 0

    def kill(self):
        return None


def scenario(name: str, fail_index: int | None) -> None:
    module = importlib.import_module(name)
    single = name == "dniv_lab"
    lab = module.Lab.__new__(module.Lab)
    lab.guests = []
    lab.captures = []
    lab.created_taps = []
    lab.bridges = ["owned-bridge", "foreign-bridge"]
    lab.bridge = "foreign-bridge"
    lab.tcpdump = None
    lab.created_bridges = []
    lab.created_bridge = False
    seen = []
    with tempfile.TemporaryDirectory() as d:
        lab.pcaps = [Path(d) / "one.pcap", Path(d) / "two.pcap"]
        lab.pcap = Path(d) / "single.pcap"
        lab.pcap.write_bytes(b"pcap")

        def fake_sudo(*args, **kwargs):
            seen.append(args)
            if args[:3] == ("ip", "link", "add") and (
                (single and fail_index == 0) or
                (not single and fail_index is not None and
                 args[3] == lab.bridges[fail_index])
            ):
                raise subprocess.CalledProcessError(2, args)

        with mock.patch.object(module, "sudo", side_effect=fake_sudo), \
                mock.patch.object(module.subprocess, "Popen", return_value=Capture()), \
                mock.patch.object(module.time, "sleep", return_value=None):
            try:
                if single:
                    lab.create_network([])
                else:
                    lab.setup_network([[], []])
            except subprocess.CalledProcessError:
                if fail_index is None:
                    raise
            else:
                if fail_index is not None:
                    raise AssertionError(f"{name}: failed bridge creation accepted")
            finally:
                lab.close()

    deletes = [args[3] for args in seen if args[:3] == ("ip", "link", "del")]
    if single:
        expected = [] if fail_index == 0 else ["foreign-bridge"]
    elif fail_index == 0:
        expected = []
    elif fail_index == 1:
        expected = ["owned-bridge"]
    else:
        expected = ["foreign-bridge", "owned-bridge"]
    if deletes != expected:
        raise AssertionError(f"{name} fail_index={fail_index}: deleted {deletes}; expected {expected}")


def main() -> None:
    for name in ("dniv_e2", "dniv_e3", "dniv_e4", "dniv_scale", "dniv_lab"):
        scenario(name, 0)
        if name != "dniv_lab":
            scenario(name, 1)
        scenario(name, None)
    print("lab bridge ownership: 14 mocked failure/success cases passed")


if __name__ == "__main__":
    main()
