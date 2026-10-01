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
CHECKOUT_PIN = "11d5960a326750d5838078e36cf38b85af677262"
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
          name: first-${{{{ github.run_attempt }}}}
          path: one
          if-no-files-found: error
          retention-days: 30
          overwrite: false
      - name: Second artifact
        uses: actions/upload-artifact@{UPLOAD_PIN}
        with:
          name: second-${{{{ github.run_attempt }}}}
          path: two
          if-no-files-found: error
          retention-days: 3
          overwrite: false
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
            scenarios: \"l1\"
    env:
      DNIV_SCRATCH_DIR: ${{{{ github.workspace }}}}/scratch/runtime/${{{{ github.run_id }}}}/${{{{ github.job }}}}-${{{{ matrix.arch }}}}-${{{{ matrix.suite }}}}
    steps:
      - name: Bind candidate
        run: python3 tools/scratch_state.py init --expected-sha '${{{{ inputs.expected_sha }}}}'
      - name: Compute stable foundation
        run: |
          fingerprint=abc
          session=\"outer-v2-${{{{ matrix.arch }}}}-$fingerprint\"
          echo build-foundation.sh
      - name: Restore outer
        uses: actions/cache/restore@{CACHE_PIN}
      - name: Save outer
        uses: actions/cache/save@{CACHE_PIN}
      - name: Verify source-independent architecture foundation
        run: "! grep -q '^SOURCE_SHA=' session.env"
      - name: Prepare disposable exact-candidate and reference images
        run: |
          tests/lab/prepare-candidate-image.sh base candidate
          tests/lab/prepare-reference-image.sh base reference
      - name: Preserve evidence
        uses: actions/upload-artifact@{UPLOAD_PIN}
        with:
          name: scratch-interop-${{{{ matrix.arch }}}}-${{{{ matrix.suite }}}}-${{{{ github.run_id }}}}-${{{{ github.run_attempt }}}}
          path: |
            ${{{{ env.DNIV_SCRATCH_DIR }}}}/
            !${{{{ env.DNIV_SCRATCH_DIR }}}}/interop/**/*.qcow2
          if-no-files-found: error
          retention-days: 30
          overwrite: false
"""


FALSE_GREEN_GOOD = f"""name: False Green Budget Test
on:
  workflow_dispatch:
    inputs:
      expected_sha:
        required: false
        type: string
      retry_probe:
        required: false
        type: boolean
        default: false
concurrency:
  group: false-green-test
  queue: max
  cancel-in-progress: false
jobs:
  false-green:
    runs-on: ubuntu-latest
    timeout-minutes: 15
    steps:
      - name: Check out
        uses: actions/checkout@{CHECKOUT_PIN}
      - name: Bind
        run: python3 tools/scratch_state.py init --expected-sha '${{{{ inputs.expected_sha }}}}'
      - name: PP-10 controls
        run: |
          echo "mount -t tmpfs"
          echo "gh run download"
          echo "inputs.retry_probe && github.run_attempt > 1"
          echo "inputs.retry_probe && github.run_attempt == 1"
          echo "--require evidence-byte-exhaustion.log"
          echo "--require evidence-inode-exhaustion.log"
      - name: Seal final false-green evidence
        run: echo seal
      - name: Preserve
        uses: actions/upload-artifact@{UPLOAD_PIN}
        with:
          name: false-green-${{{{ github.run_attempt }}}}
          path: scratch
          if-no-files-found: error
          retention-days: 30
          overwrite: false
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
            raise SystemExit("workflow budget rejected valid committed controls: " + result.stderr)

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

        missing_attempt = GOOD.replace("-${{ github.run_attempt }}", "", 1)
        sample.write_text(missing_attempt, encoding="utf-8")
        run(root, "git", "add", str(sample.relative_to(root)))
        sample.write_text(GOOD, encoding="utf-8")
        result = invoke(root, "--staged")
        if result.returncode == 0 or "github.run_attempt" not in result.stderr:
            raise SystemExit("workflow budget failed to reject retry-overwriting artifact names")

        warning_only = GOOD.replace("if-no-files-found: error", "if-no-files-found: warn", 1)
        sample.write_text(warning_only, encoding="utf-8")
        run(root, "git", "add", str(sample.relative_to(root)))
        sample.write_text(GOOD, encoding="utf-8")
        result = invoke(root, "--staged")
        if result.returncode == 0 or "must fail when evidence is missing" not in result.stderr:
            raise SystemExit("workflow budget failed to reject warning-only evidence upload")

        overwriting = GOOD.replace("overwrite: false", "overwrite: true", 1)
        sample.write_text(overwriting, encoding="utf-8")
        run(root, "git", "add", str(sample.relative_to(root)))
        sample.write_text(GOOD, encoding="utf-8")
        result = invoke(root, "--staged")
        if result.returncode == 0 or "overwrite:false" not in result.stderr:
            raise SystemExit("workflow budget failed to reject retry-overwriting evidence upload")

        run(root, "git", "reset", "-q", "HEAD", "--", str(sample.relative_to(root)))
        interop_bad = INTEROP_GOOD.replace('scenarios: "l1"', 'scenarios: "l1 l2"')
        interop.write_text(interop_bad, encoding="utf-8")
        run(root, "git", "add", str(interop.relative_to(root)))
        interop.write_text(INTEROP_GOOD, encoding="utf-8")
        result = invoke(root, "--staged")
        if result.returncode == 0 or "2 scenarios" not in result.stderr:
            raise SystemExit("workflow budget failed to reject an oversized staged interop scenario group")

        run(root, "git", "reset", "-q", "HEAD", "--", str(interop.relative_to(root)))
        sha_keyed = INTEROP_GOOD.replace(
            'session="outer-v2-${{ matrix.arch }}-$fingerprint"',
            'session="outer-v1-${{ matrix.arch }}-${{ github.sha }}"',
        )
        interop.write_text(sha_keyed, encoding="utf-8")
        run(root, "git", "add", str(interop.relative_to(root)))
        result = invoke(root, "--staged")
        if result.returncode == 0 or "outer-v1" not in result.stderr:
            raise SystemExit("workflow budget failed to reject source-SHA-keyed full foundations")

        run(root, "git", "reset", "-q", "HEAD", "--", str(interop.relative_to(root)))
        false_green = workflows / "false-green.yml"
        false_green.write_text(FALSE_GREEN_GOOD, encoding="utf-8")
        run(root, "git", "add", str(false_green.relative_to(root)))
        result = invoke(root, "--staged")
        if result.returncode != 0:
            raise SystemExit("workflow budget rejected valid PP-10 retry controls: " + result.stderr)

        missing_retry_proof = FALSE_GREEN_GOOD.replace("gh run download", "gh run fetch", 1)
        false_green.write_text(missing_retry_proof, encoding="utf-8")
        run(root, "git", "add", str(false_green.relative_to(root)))
        result = invoke(root, "--staged")
        if result.returncode == 0 or "gh run download" not in result.stderr:
            raise SystemExit("workflow budget failed to reject missing PP-10 retry evidence proof")

    print("workflow budget regression tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
