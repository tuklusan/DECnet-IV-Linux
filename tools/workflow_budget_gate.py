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

"""Enforce hosted-runner duration and scratch-artifact storage limits."""

from __future__ import annotations

import re
import sys
from pathlib import Path

WORKFLOW_DIR = Path(".github/workflows")
MAX_JOB_MINUTES = 75
MAX_EVIDENCE_DAYS = 30
VM_CHECKPOINT_DAYS = 3

JOB_RE = re.compile(r"^  ([A-Za-z0-9_-]+):\s*$")
TIMEOUT_RE = re.compile(r"^    timeout-minutes:\s*([0-9]+)\s*$")
RETENTION_RE = re.compile(r"^\s+retention-days:\s*([0-9]+)\s*$")
STEP_RE = re.compile(r"^      - name:\s+")


def job_ranges(lines: list[str]) -> list[tuple[str, int, int]]:
    try:
        jobs_line = next(i for i, line in enumerate(lines) if line == "jobs:")
    except StopIteration:
        return []
    starts: list[tuple[str, int]] = []
    for index in range(jobs_line + 1, len(lines)):
        line = lines[index]
        if line and not line.startswith(" "):
            break
        match = JOB_RE.match(line)
        if match:
            starts.append((match.group(1), index))
    result: list[tuple[str, int, int]] = []
    for pos, (name, start) in enumerate(starts):
        end = starts[pos + 1][1] if pos + 1 < len(starts) else len(lines)
        result.append((name, start, end))
    return result


def upload_block(lines: list[str], uses_index: int) -> list[str]:
    end = len(lines)
    for index in range(uses_index + 1, len(lines)):
        if STEP_RE.match(lines[index]):
            end = index
            break
    return lines[uses_index:end]


def check_workflow(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    errors: list[str] = []

    ranges = job_ranges(lines)
    if not ranges:
        errors.append(f"{path}: no jobs found")
    for name, start, end in ranges:
        values = []
        for line in lines[start:end]:
            match = TIMEOUT_RE.match(line)
            if match:
                values.append(int(match.group(1)))
        if len(values) != 1:
            errors.append(f"{path}: job {name} must declare exactly one timeout-minutes")
        elif values[0] < 1 or values[0] > MAX_JOB_MINUTES:
            errors.append(
                f"{path}: job {name} timeout {values[0]} exceeds voluntary {MAX_JOB_MINUTES}-minute ceiling"
            )

    upload_lines = [i for i, line in enumerate(lines) if "uses: actions/upload-artifact@" in line]
    for index in upload_lines:
        block = upload_block(lines, index)
        retention = [int(match.group(1)) for line in block if (match := RETENTION_RE.match(line))]
        if len(retention) != 1:
            errors.append(f"{path}: upload-artifact block near line {index + 1} must declare exactly one retention-days")
        elif retention[0] < 1 or retention[0] > MAX_EVIDENCE_DAYS:
            errors.append(
                f"{path}: artifact retention {retention[0]} days exceeds {MAX_EVIDENCE_DAYS}-day evidence ceiling"
            )

    if path.name == "vm-lab.yml":
        required = (
            "scratch-vm-lab-checkpoint-${{ matrix.arch }}-${{ github.run_id }}",
            f"retention-days: {VM_CHECKPOINT_DAYS}",
            "Prune superseded successful VM checkpoints",
            "!${{ env.DNIV_SCRATCH_DIR }}/lab/**/checkpoint/*.qcow2",
            "!${{ env.DNIV_SCRATCH_DIR }}/lab/**/checkpoint/vmlinuz",
            "!${{ env.DNIV_SCRATCH_DIR }}/lab/**/checkpoint/initrd.img",
            "actions: write",
        )
        for marker in required:
            if marker not in text:
                errors.append(f"{path}: missing VM checkpoint storage safeguard: {marker}")
    if path.name == "interop.yml":
        marker = "!${{ env.DNIV_SCRATCH_DIR }}/interop/**/*.qcow2"
        if marker not in text:
            errors.append(f"{path}: transient interoperability disks are not excluded from artifacts")

    return errors


def main() -> int:
    paths = sorted(set(WORKFLOW_DIR.glob("*.yml")) | set(WORKFLOW_DIR.glob("*.yaml")))
    errors: list[str] = []
    if not paths:
        errors.append("workflow-budget: no workflow files found")
    for path in paths:
        errors.extend(check_workflow(path))
    if errors:
        for error in errors:
            print(f"workflow-budget: {error}", file=sys.stderr)
        return 1
    print(
        f"workflow-budget: {len(paths)} workflow files verified; jobs <= {MAX_JOB_MINUTES} minutes, artifacts <= {MAX_EVIDENCE_DAYS} days"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
