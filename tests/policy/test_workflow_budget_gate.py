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

"""Regression tests for workflow duration, storage and exact-source parsing."""

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

INTEROP_GOOD = """name: Interop Budget Test
on: workflow_dispatch
jobs:
  live-interop:
    runs-on: ubuntu-latest
    timeout-minutes: 75
    strategy:
      matrix:
        include:
          - arch: amd64
            suite: routing
            scenarios: \"l1 l2\"
    env:
      DNIV_SCRATCH_DIR: ${{ github.workspace }}/scratch/runtime/${{ github.run_id }}/${{ github.job }}-${{ matrix.arch }}-${{ matrix.suite }}
    steps:
      - name: Preserve evidence
        uses: actions/upload-artifact@v4
        with:
          name: scratch-interop-${{ matrix.arch }}-${{ matrix.suite }}-${{ github.run_id }}
          path: |
            ${{ env.DNIV_SCRATCH_DIR }}/
            !${{ env.DNIV_SCRATCH_DIR }}/interop/**/*.qcow2
          retention-days: 30
"""


def run(root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=root,
        check=check,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def invoke(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return run(root, sys.executable, str(GATE), *args, check=False)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="dniv-workflow-budget-") as temporary:
        root = Path(temporary)
        workflows = root / ".github" / "workflows"
        workflows.mkdir(parents=True)
        sample = workflows / "sample.yml"
        interop = workflows / "interop.yml"

        run(root, "git", "init", "-q", "-b", "main")
        run(root, "git", "config", "user.name", "Workflow Budget Test")
        run(root, "git", "config", "user.email", "workflow-budget@example.invalid")
        sample.write_text(GOOD, encoding="utf-8")
        interop.write_text(INTEROP_GOOD, encoding="utf-8")
        run(root, "git", "add", ".")
        run(root, "git", "commit", "-q", "-m", "good workflows")

        result = invoke(root, "--tree", "HEAD")
        if result.returncode != 0:
            raise SystemExit("workflow budget rejected valid committed adjacent artifacts or bounded interop rows")

        bad_timeout = GOOD.replace("timeout-minutes: 75", "timeout-minutes: 76")
        sample.write_text(bad_timeout, encoding="utf-8")
        run(root, "git", "add", str(sample.relative_to(root)))
        sample.write_text(GOOD, encoding="utf-8")
        result = invoke(root, "--staged")
        if result.returncode == 0 or "76" not in result.stderr:
            raise SystemExit("staged budget gate read working-tree bytes instead of the index")
        result = invoke(root, "--tree", "HEAD")
        if result.returncode != 0:
            raise SystemExit("tree budget gate read mutable working/index bytes instead of the commit")

        run(root, "git", "reset", "-q", "HEAD", "--", str(sample.relative_to(root)))
        interop_bad = INTEROP_GOOD.replace('scenarios: "l1 l2"', 'scenarios: "l1 l2 endnode"')
        interop.write_text(interop_bad, encoding="utf-8")
        run(root, "git", "add", str(interop.relative_to(root)))
        interop.write_text(INTEROP_GOOD, encoding="utf-8")
        result = invoke(root, "--staged")
        if result.returncode == 0 or "3 scenarios" not in result.stderr:
            raise SystemExit("workflow budget failed to reject an oversized staged interop scenario group")

    print("workflow budget regression tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
