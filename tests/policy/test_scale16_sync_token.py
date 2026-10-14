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

"""Untrusted sync tokens must never form unquoted remote SSH commands."""

from pathlib import Path
import sys
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests" / "lab"))
import dniv_scale16_distributed as scale16  # noqa: E402


def main() -> None:
    for token in ("x;touch /tmp/unsafe", "../escape", "x$(whoami)", "bad space", "", "a" * 97):
        with mock.patch.object(scale16.subprocess, "run", side_effect=AssertionError("SSH executed")):
            try:
                scale16.ssh_sync(Path("/unused-ssh-config"), token, "a")
            except RuntimeError as exc:
                assert "invalid synchronization token" in str(exc), str(exc)
            else:
                raise AssertionError(f"invalid token accepted: {token!r}")
    with mock.patch.object(scale16.subprocess, "run", side_effect=AssertionError("SSH executed")):
        try:
            scale16.ssh_sync(Path("/unused-ssh-config"), "valid-123", "a;touch /tmp/unsafe")
        except RuntimeError as exc:
            assert "invalid synchronization side" in str(exc), str(exc)
        else:
            raise AssertionError("invalid side accepted")
    calls = []
    def fake_run(command, **kwargs):
        calls.append(command)
        return SimpleNamespace(returncode=0, stderr="")
    with mock.patch.object(scale16.subprocess, "run", side_effect=fake_run):
        scale16.ssh_sync(Path("/unused-ssh-config"), "12345-1-arm64", "a")
    assert len(calls) == 1, calls
    assert "/tmp/dniv-scale16-12345-1-arm64-a.ready" in calls[0][-1], calls
    print("scale16 sync token validation: invalid rejected before SSH; CI token accepted")


if __name__ == "__main__":
    main()
