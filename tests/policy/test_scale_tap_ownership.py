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

"""Scale/PP11-S2 must not enslave a foreign pre-existing host TAP/interface."""

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock
import importlib
import os
import sys

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "tests/lab/dniv_scale.py"


class Capture:
    pid = 199999

    def poll(self):
        return None

    def wait(self, timeout=None):
        return 0

    def kill(self):
        pass


def scenario(colliding: bool, external: bool = False) -> None:
    sys.path.insert(0, str(SOURCE.parent))
    module = importlib.import_module("dniv_scale")
    with TemporaryDirectory() as d:
        root = Path(d)
        lab = module.Lab(root / "base", root / "kernel", root / "initrd",
                         root, "offline-test", 1)
        tap = "preexisting-host" if colliding else "new-dniv-host"
        seen: list[tuple[str, ...]] = []
        def fake_exists(path):
            return colliding and str(path) == f"/sys/class/net/{tap}"
        def fake_sudo(*argv, **kw):
            seen.append(argv)
        with mock.patch.object(Path, "exists", fake_exists), \
                mock.patch.object(module, "sudo", side_effect=fake_sudo), \
                mock.patch.object(module.subprocess, "Popen", return_value=Capture()), \
                mock.patch.object(module.time, "sleep", return_value=None):
            try:
                try:
                    lab.setup_network([[tap]], external_taps={tap} if external else None)
                except RuntimeError as exc:
                    if colliding == external or not any(token in str(exc) for token in ("pre-existing", "missing")):
                        raise
                else:
                    if colliding != external:
                        raise AssertionError("accepted forbidden TAP ownership state")
            finally:
                lab.close()
        if colliding:
            if not external:
                assert not any(argv[:3] == ("ip", "link", "set") and tap in argv
                               for argv in seen), "unowned host interface mutated"
            else:
                assert ("ip", "link", "set", tap, "master", lab.bridges[0]) in seen
            assert ("ip", "tuntap", "del", "dev", tap, "mode", "tap") not in seen
        elif external:
            assert ("ip", "link", "set", tap, "master", lab.bridges[0]) not in seen
        else:
            assert ("ip", "tuntap", "add", "dev", tap, "mode", "tap", "user", str(os.getuid())) in seen
            assert ("ip", "tuntap", "del", "dev", tap, "mode", "tap") in seen


def scenario_duplicate() -> None:
    import dniv_scale
    with TemporaryDirectory() as d:
        root = Path(d)
        lab = dniv_scale.Lab(root / "base", root / "kernel", root / "initrd",
                             root, "duplicate-test", 1)
        calls = []
        with mock.patch.object(Path, "exists", return_value=False), \
                mock.patch.object(dniv_scale, "sudo", side_effect=lambda *args, **kw: calls.append(args)), \
                mock.patch.object(dniv_scale.subprocess, "Popen", return_value=Capture()), \
                mock.patch.object(dniv_scale.time, "sleep", return_value=None):
            try:
                try:
                    lab.setup_network([["repeatedtap", "repeatedtap"]])
                except RuntimeError as exc:
                    assert "more than once" in str(exc), exc
                else:
                    raise AssertionError("same TAP attached twice")
            finally:
                lab.close()
        creates = [a for a in calls if a[:3] == ("ip", "tuntap", "add")]
        deletes = [a for a in calls if a[:3] == ("ip", "tuntap", "del")]
        assert len(creates) == len(deletes) == 1, (creates, deletes)


def main():
    scenario(True)
    scenario(False)
    scenario(True, external=True)
    scenario(False, external=True)
    scenario_duplicate()
    print("scale TAP ownership: five offline collision/external/owned/duplicate cases passed")


if __name__ == "__main__":
    main()
