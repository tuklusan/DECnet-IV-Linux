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

"""QMP resume failure must not bypass owned QEMU/tap/bridge cleanup."""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "tests/lab/dniv_lab.py"


def main() -> None:
    parsed = ast.parse(SOURCE.read_text(encoding="utf-8"), filename=str(SOURCE))
    entry = next(node for node in parsed.body
                 if isinstance(node, ast.FunctionDef) and node.name == "main")
    outer = next(node for node in entry.body if isinstance(node, ast.Try))
    cleanup = ast.fix_missing_locations(ast.Module(body=outer.finalbody, type_ignores=[]))
    executable = compile(cleanup, str(SOURCE), "exec")

    class FakeLab:
        def __init__(self, fail_at: int):
            self.fail_at = fail_at
            self.resumed: list[str] = []
            self.closed = 0

        def resume_guest(self, guest: str) -> None:
            self.resumed.append(guest)
            if len(self.resumed) == self.fail_at:
                raise RuntimeError("injected QMP resume failure")

        def close(self) -> None:
            self.closed += 1

    cases = [
        (True, False, False, False, 1, ["a"]),
        (True, True, True, False, 2, ["a", "b"]),
        (True, True, True, False, 3, ["a", "b", "a"]),
        (True, True, True, False, 0, ["a", "b", "a"]),
        (False, False, False, False, 0, []),
    ]
    for startup, paused_b, paused_a, restored, fail_at, expected in cases:
        lab = FakeLab(fail_at)
        context = dict(lab=lab, startup_a_paused=startup,
                       fault_b_paused=paused_b, fault_a_paused=paused_a,
                       fault_restored=restored, guest_a="a", guest_b="b")
        try:
            exec(executable, context)
        except RuntimeError as exc:
            if fail_at == 0 or "injected QMP resume failure" not in str(exc):
                raise
        else:
            if fail_at:
                raise AssertionError("QMP resume failure silently swallowed")
        assert lab.closed == 1, ("QMP resume bypassed owned-resource cleanup", fail_at, lab.closed)
        assert lab.resumed == expected, (fail_at, lab.resumed)
    print("lab QMP resume cleanup: five source-derived offline scenarios passed")


if __name__ == "__main__":
    main()
