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

"""Termination-race worker joins share one absolute deadline."""

import ast
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[2] / "tests/lab/pydecnet-termrace.py"


def exercise() -> None:
    module = ast.parse(SOURCE.read_text(encoding="utf-8"))
    main = next(n for n in module.body if isinstance(n, ast.FunctionDef) and n.name == "main")
    join_pos = next(
        i for i, statement in enumerate(main.body)
        if isinstance(statement, ast.For)
        and any(isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                and n.func.attr == "join" for n in ast.walk(statement))
    )
    selected = [main.body[join_pos]]
    preceding = main.body[join_pos - 1]
    if isinstance(preceding, ast.Assign) and any(
        isinstance(target, ast.Name) and target.id == "join_deadline"
        for target in preceding.targets
    ):
        selected.insert(0, preceding)

    class Clock:
        elapsed = 0.0

        def monotonic(self):
            return self.elapsed

    clock = Clock()

    class Worker:
        def join(self, seconds):
            if not 0.0 <= seconds <= 40.0:
                raise AssertionError(f"invalid join timeout {seconds}")
            clock.elapsed += seconds  # A stuck thread consumes the whole timeout

    workers = [Worker() for _ in range(4)]
    block = ast.fix_missing_locations(ast.Module(body=selected, type_ignores=[]))
    namespace = {"threads": workers, "time": clock}
    exec(compile(block, str(SOURCE), "exec"), namespace)
    if not 0.0 <= clock.elapsed <= 40.0:
        raise AssertionError(
            f"termination-race joins multiplied global budget: "
            f"elapsed={clock.elapsed} budget=40.0 workers={len(workers)}"
        )


def main() -> None:
    exercise()
    print("PyDECnet termination-race global deadline regression passed")


if __name__ == "__main__":
    main()
