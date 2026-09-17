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

"""Regression tests for workflow duration and artifact-budget parsing."""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GATE = ROOT / "tools" / "workflow_budget_gate.py"

GOOD = """name: Budget Test
on: workflow_dispatch
jobs:
  test:
    runs-on: ubuntu-latest
    timeout-minutes: 75
    steps:
      - name: First artifact
        uses: actions/upload-artifact@v4
        with:
          name: first
          path: one
          retention-days: 30
      - name: Second artifact
        uses: actions/upload-artifact@v4
        with:
          name: second
          path: two
          retention-days: 3
"""

BAD = GOOD.replace("timeout-minutes: 75", "timeout-minutes: 76")


def invoke(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        (sys.executable, str(GATE)),
        cwd=root,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="dniv-workflow-budget-") as temporary:
        root = Path(temporary)
        workflows = root / ".github" / "workflows"
        workflows.mkdir(parents=True)
        path = workflows / "sample.yml"
        path.write_text(GOOD, encoding="utf-8")
        result = invoke(root)
        if result.returncode != 0:
            raise SystemExit("workflow budget rejected adjacent valid artifact blocks")

        path.write_text(BAD, encoding="utf-8")
        result = invoke(root)
        if result.returncode == 0 or "76" not in result.stderr:
            raise SystemExit("workflow budget failed to reject a job above 75 minutes")

    print("workflow budget regression tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
