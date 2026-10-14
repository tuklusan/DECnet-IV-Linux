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

"""Reject persistent TAP leaks from the scale/PP11-S2 QEMU lab."""

from pathlib import Path
import os
import sys
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests" / "lab"))
import dniv_scale  # noqa: E402


class DummyCapture:
    pid = 1234567

    def poll(self):
        return None

    def wait(self, timeout=None):
        return 0

    def kill(self):
        return None


def main() -> None:
    tap = f"dnt{os.getpid()}"
    assert not Path(f"/sys/class/net/{tap}").exists(), "test tap already exists"
    seen: list[tuple[str, ...]] = []

    def fake_sudo(*args: str, **kwargs: object) -> None:
        seen.append(tuple(args))

    lab = dniv_scale.Lab(Path("/unused-base"), Path("/unused-kernel"),
                         Path("/unused-initrd"), Path("/tmp"),
                         f"tap-lifecycle-{os.getpid()}", 1)
    with mock.patch.object(dniv_scale, "sudo", side_effect=fake_sudo), \
            mock.patch.object(dniv_scale.subprocess, "Popen", return_value=DummyCapture()), \
            mock.patch.object(dniv_scale.time, "sleep", return_value=None):
        lab.setup_network([["lo", tap]])
        lab.close()

    assert ("ip", "tuntap", "add", "dev", tap, "mode", "tap", "user", str(os.getuid())) in seen, seen
    assert ("ip", "tuntap", "del", "dev", tap, "mode", "tap") in seen, seen
    assert not any(call[:4] == ("ip", "tuntap", "del", "dev") and
                   call[4] == "lo" for call in seen), seen
    assert ("ip", "link", "del", lab.bridges[0]) in seen, seen
    print("scale tap cleanup: created TAP removed; pre-existing interface preserved")


if __name__ == "__main__":
    main()
