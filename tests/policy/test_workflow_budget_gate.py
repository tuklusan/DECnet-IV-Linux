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

"""Regression tests for workflow duration, queueing, pins and exact-source parsing."""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GATE = ROOT / "tools" / "workflow_budget_gate.py"
UPLOAD_PIN = "ea165f8d65b6e75b540449e92b4886f43607fa02"
CACHE_PIN = "0057852bfaa89a56745cba8c7296529d2fc39830"

GOOD = f"""name: Budget Test
on: workflow_dispatch
concurrency:
  group: budget-test
  queue: max
  cancel-in-progress: false
jobs:
  test:
    runs-on: ubuntu-latest
    timeout-minutes: 75
    steps:
      - name: Restore cache
        uses: actions/cache/restore@{CACHE_PIN}
        with:
          path: cache
          key: cache-key
      - name: Save cache
        uses: actions/cache/save@{CACHE_PIN}
        with:
          path: cache
          key: cache-key
      - name: First artifact
        uses: actions/upload-artifact@{UPLOAD_PIN}
        with:
          name: first
          path: one
          retention-days: 30
      - name: Second artifact
        uses: actions/upload-artifact@{UPLOAD_PIN}
        with:
          name: second
          path: two
          retention-days: 3
"""

INTEROP_GOOD = f"""name: Interop Budget Test
on:
  workflow_dispatch:
    inputs:
      expected_sha:
        required: false
        type: string
concurrency:
  group: interop-test
  queue: max
  cancel-in-progress: false
jobs:
  live-interop:
    runs-on: ubuntu-latest
    timeout-minutes: 75
    concurrency:
      group: dniv-runner-x64
      queue: max
      cancel-in-progress: false
    strategy:
      matrix:
        include:
          - arch: amd64
            suite: routing
            scenarios: \"l1 l2\"
    env:
      DNIV_SCRATCH_DIR: ${{{{ github.workspace }}}}/scratch/runtime/${{{{ github.run_id }}}}/${{{{ github.job }}}}-${{{{ matrix.arch }}}}-${{{{ matrix.suite }}}}
      DNIV_OUTER_SESSION_ID: outer-v1-${{{{ matrix.arch }}}}-${{{{ github.sha }}}}
    steps:
      - name: Bind candidate
        run: python3 tools/scratch_state.py init --expected-sha '${{{{ inputs.expected_sha }}}}'
      - name: Restore outer
        uses: actions/cache/restore@{CACHE_PIN}
      - name: Save outer
        uses: actions/cache/save@{CACHE_PIN}
      - name: Prepare disposable interoperability images
        run: true
      - name: Preserve evidence
        uses: actions/upload-artifact@{UPLOAD_PIN}
        with:
          name: scratch-interop-${{{{ matrix.arch }}}}-${{{{ matrix.suite }}}}-${{{{ github.run_id }}}}
          path: |
            ${{{{ env.DNIV_SCRATCH_DIR }}}}/
            !${{{{ env.DNIV_SCRATCH_DIR }}}}/interop/**/*.qcow2
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
            raise SystemExit("workflow budget rejected valid committed controls")

        bad_queue = GOOD.replace("  queue: max\n", "", 1)
        sample.write_text(bad_queue, encoding="utf-8")
        run(root, "git", "add", str(sample.relative_to(root)))
        sample.write_text(GOOD, encoding="utf-8")
        result = invoke(root, "--staged")
        if result.returncode == 0 or "queue: max" not in result.stderr:
            raise SystemExit("workflow budget failed to reject missing staged queue:max")

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

        bad_pin = GOOD.replace(UPLOAD_PIN, "v4", 1)
        sample.write_text(bad_pin, encoding="utf-8")
        run(root, "git", "add", str(sample.relative_to(root)))
        sample.write_text(GOOD, encoding="utf-8")
        result = invoke(root, "--staged")
        if result.returncode == 0 or "must be pinned" not in result.stderr:
            raise SystemExit("workflow budget failed to reject a movable artifact action tag")

        bad_cache_pin = GOOD.replace(CACHE_PIN, "v4", 1)
        sample.write_text(bad_cache_pin, encoding="utf-8")
        run(root, "git", "add", str(sample.relative_to(root)))
        sample.write_text(GOOD, encoding="utf-8")
        result = invoke(root, "--staged")
        if result.returncode == 0 or "actions/cache/restore" not in result.stderr:
            raise SystemExit("workflow budget failed to reject a movable cache action tag")

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
