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

"""All backlog workers share one bounded join deadline, not N deadlines."""

import ast
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[2] / "tests/lab/pydecnet-backlog.py"


def exercise(pressure: bool) -> None:
    module = ast.parse(SOURCE.read_text(encoding="utf-8"))
    main = next(n for n in module.body if isinstance(n, ast.FunctionDef) and n.name == "main")
    join_pos = next(
        i for i, statement in enumerate(main.body)
        if isinstance(statement, ast.For)
        and any(isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                and n.func.attr == "join" for n in ast.walk(statement))
    )
    selected = [main.body[join_pos]]
    if isinstance(main.body[join_pos - 1], ast.Assign) and any(
        isinstance(target, ast.Name) and target.id == "join_deadline"
        for target in main.body[join_pos - 1].targets
    ):
        selected.insert(0, main.body[join_pos - 1])

    class Clock:
        elapsed = 0.0

        def monotonic(self):
            return self.elapsed

    clock = Clock()
    class Worker:
        def join(self, seconds):
            if seconds < 0:
                raise AssertionError("negative join timeout")
            clock.elapsed += seconds  # Simulate a stuck worker that consumes its entire wait

    workers = [Worker() for _ in range(65 if pressure else 4)]
    block = ast.fix_missing_locations(ast.Module(body=selected, type_ignores=[]))
    namespace = {"threads": workers, "pressure": pressure, "time": clock}
    exec(compile(block, str(SOURCE), "exec"), namespace)
    limit = 90.0 if pressure else 40.0
    if not 0.0 <= clock.elapsed <= limit:
        raise AssertionError(
            f"join budget multiplied across workers: elapsed={clock.elapsed} "
            f"budget={limit} count={len(workers)}"
        )


def main():
    exercise(False)
    exercise(True)
    print("PyDECnet backlog worker global deadline regression passed")


if __name__ == "__main__":
    main()
