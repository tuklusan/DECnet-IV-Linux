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

"""PP-11 S2 must stop an owned active fault injector on host sampler failure."""

import ast
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "tests/lab/dniv_pp11_s2.py"


class Proc:
    def __init__(self, timeout: bool):
        self.timeout = timeout
        self.terminated = 0
        self.killed = 0
        self.waited = 0

    def poll(self):
        return None

    def terminate(self):
        self.terminated += 1

    def wait(self, timeout=None):
        self.waited += 1
        if self.timeout and self.waited == 1:
            raise subprocess.TimeoutExpired(cmd="mock sudo injector", timeout=timeout)
        return 0

    def kill(self):
        self.killed += 1


class Lab:
    def __init__(self):
        self.bridges = ["isolated-a", "isolated-b"]
        self.captures = [SimpleNamespace(poll=lambda: None)]
        self.closed = 0

    def setup_network(self, groups):
        pass

    def start(self, guest):
        pass

    def close(self):
        self.closed += 1


def scenario(timeout: bool) -> None:
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    main = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "main")
    trial = next(node for node in main.body if isinstance(node, ast.Try))
    code = compile(ast.fix_missing_locations(ast.Module(body=[trial], type_ignores=[])), str(SOURCE), "exec")
    lab = Lab()
    injector = Proc(timeout)
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        context = {
            "lab": lab, "a0": SimpleNamespace(taps=["a"]), "a1": SimpleNamespace(taps=["b"]),
            "b0": SimpleNamespace(taps=["c"]), "r0": SimpleNamespace(taps=["d", "e"]),
            "endpoints": [], "guests": [], "session": "offline", "router_mac": "aa:00:04:00:48:7c",
            "wait_for_markers": lambda *args: None, "FAULT_EVENTS": 10000,
            "FAULT_DURATION": 3600.0,
            "time": SimpleNamespace(monotonic=lambda: 0.0, sleep=lambda _: None),
            "subprocess": SimpleNamespace(Popen=lambda *a, **kw: injector,
                                            STDOUT=subprocess.STDOUT,
                                            TimeoutExpired=subprocess.TimeoutExpired),
            "host_sample": lambda *_: (_ for _ in ()).throw(RuntimeError("injected sampler failure")),
            "injector_log": root / "faults.tsv", "injector_out": root / "injector.log",
            "host_resources": root / "resources.tsv", "Path": Path, "__file__": str(SOURCE),
        }
        try:
            exec(code, context)
        except RuntimeError as exc:
            assert str(exc) == "injected sampler failure", str(exc)
        else:
            raise AssertionError("injected host sampler failure was swallowed")
    assert lab.closed == 1, "lab cleanup was skipped"
    assert injector.terminated == 1, "active privileged injector never received terminate"
    assert injector.waited >= 1, "active injector was not reaped"
    assert injector.killed == int(timeout), "timeout must trigger force-kill fallback"


def main() -> None:
    scenario(False)
    scenario(True)
    print("PP11-S2 injector lifetime: two source-extracted offline fault scenarios passed")


if __name__ == "__main__":
    main()
