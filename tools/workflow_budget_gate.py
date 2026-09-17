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

"""Enforce hosted-runner duration, queueing, immutable action pins and evidence limits."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath
from typing import Callable

WORKFLOW_ROOT = ".github/workflows/"
MAX_JOB_MINUTES = 75
MAX_EVIDENCE_DAYS = 30
MAX_INTEROP_SCENARIOS_PER_JOB = 2
ACTION_PINS = {
    "actions/checkout": "11d5960a326750d5838078e36cf38b85af677262",
    "actions/upload-artifact": "ea165f8d65b6e75b540449e92b4886f43607fa02",
    "actions/download-artifact": "d3f86a106a0bac45b974a628896c90dbdf5c8093",
}
CHILD_WORKFLOWS = {
    "build.yml", "project-state.yml", "reference-baselines.yml", "vm-lab.yml", "interop.yml",
}
JOB_RE = re.compile(r"^  ([A-Za-z0-9_-]+):\s*$")
TIMEOUT_RE = re.compile(r"^    timeout-minutes:\s*([0-9]+)\s*$")
RETENTION_RE = re.compile(r"^\s+retention-days:\s*([0-9]+)\s*$")
STEP_RE = re.compile(r"^      - name:\s+")
SCENARIOS_RE = re.compile(r"^\s+scenarios:\s*[\"']?([^\"'#]+?)[\"']?\s*$")
CONCURRENCY_RE = re.compile(r"^(\s*)concurrency:\s*$")
USES_RE = re.compile(r"^\s+uses:\s+(actions/(?:checkout|upload-artifact|download-artifact))@([^\s#]+)")


def git(*args: str) -> str:
    return subprocess.check_output(("git", *args), text=True).strip()


def is_workflow(path: str) -> bool:
    return path.startswith(WORKFLOW_ROOT) and PurePosixPath(path).suffix in {".yml", ".yaml"}


def worktree_source() -> tuple[list[str], Callable[[str], str]]:
    root = Path(WORKFLOW_ROOT)
    paths = sorted(str(path.as_posix()) for pattern in ("*.yml", "*.yaml") for path in root.glob(pattern) if path.is_file())
    return paths, lambda path: Path(path).read_text(encoding="utf-8")


def staged_source() -> tuple[list[str], Callable[[str], str]]:
    paths = sorted(path for path in git("ls-files", "--cached").splitlines() if is_workflow(path))
    return paths, lambda path: subprocess.check_output(("git", "show", ":" + path), text=True)


def tree_source(rev: str) -> tuple[list[str], Callable[[str], str]]:
    commit = git("rev-parse", "--verify", rev + "^{commit}")
    paths = sorted(path for path in git("ls-tree", "-r", "--name-only", commit, "--", WORKFLOW_ROOT).splitlines() if is_workflow(path))
    return paths, lambda path: subprocess.check_output(("git", "show", f"{commit}:{path}"), text=True)


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
    return [(name, start, starts[pos + 1][1] if pos + 1 < len(starts) else len(lines))
            for pos, (name, start) in enumerate(starts)]


def nested_block(lines: list[str], start: int) -> list[str]:
    indent = len(lines[start]) - len(lines[start].lstrip())
    end = len(lines)
    for index in range(start + 1, len(lines)):
        line = lines[index]
        if not line.strip():
            continue
        if len(line) - len(line.lstrip()) <= indent:
            end = index
            break
    return lines[start:end]


def upload_block(lines: list[str], uses_index: int) -> list[str]:
    end = len(lines)
    for index in range(uses_index + 1, len(lines)):
        if STEP_RE.match(lines[index]):
            end = index
            break
    return lines[uses_index:end]


def check_workflow(path: str, text: str) -> list[str]:
    name = PurePosixPath(path).name
    lines = text.splitlines()
    errors: list[str] = []
    ranges = job_ranges(lines)
    if not ranges:
        errors.append(f"{path}: no jobs found")
    for job_name, start, end in ranges:
        values = [int(m.group(1)) for line in lines[start:end] if (m := TIMEOUT_RE.match(line))]
        if len(values) != 1:
            errors.append(f"{path}: job {job_name} must declare exactly one timeout-minutes")
        elif not 1 <= values[0] <= MAX_JOB_MINUTES:
            errors.append(f"{path}: job {job_name} timeout {values[0]} exceeds voluntary {MAX_JOB_MINUTES}-minute ceiling")

    for index, line in enumerate(lines):
        if CONCURRENCY_RE.match(line):
            block = nested_block(lines, index)
            queue = [entry.strip() for entry in block if entry.strip().startswith("queue:")]
            if queue != ["queue: max"]:
                errors.append(f"{path}: concurrency block near line {index + 1} must declare exactly queue: max")
            if any(entry.strip() == "cancel-in-progress: true" for entry in block):
                errors.append(f"{path}: queue: max cannot be combined with cancel-in-progress: true")

    for index, line in enumerate(lines):
        match = USES_RE.match(line)
        if match and match.group(2) != ACTION_PINS[match.group(1)]:
            errors.append(f"{path}: {match.group(1)} near line {index + 1} must be pinned to {ACTION_PINS[match.group(1)]}")

    for index, line in enumerate(lines):
        if "uses: actions/upload-artifact@" not in line:
            continue
        block = upload_block(lines, index)
        retention = [int(m.group(1)) for entry in block if (m := RETENTION_RE.match(entry))]
        if len(retention) != 1:
            errors.append(f"{path}: upload-artifact block near line {index + 1} must declare exactly one retention-days")
        elif not 1 <= retention[0] <= MAX_EVIDENCE_DAYS:
            errors.append(f"{path}: artifact retention {retention[0]} days exceeds {MAX_EVIDENCE_DAYS}-day evidence ceiling")

    if name in CHILD_WORKFLOWS:
        for marker in ("expected_sha:", "--expected-sha '${{ inputs.expected_sha }}'"):
            if marker not in text:
                errors.append(f"{path}: missing parent-candidate binding safeguard: {marker}")

    if name == "repository-policy.yml":
        for marker in (
            "github.event.issue.title == 'DNIV branch cleanup'",
            "git/matching-refs/heads",
            '-f expected_sha="$GITHUB_SHA"',
        ):
            if marker not in text:
                errors.append(f"{path}: missing repository-control safeguard: {marker}")

    if name == "vm-lab.yml":
        required = (
            "python3 tests/lab/dniv_lab.py",
            "Build immutable DECnet test base",
            "!${{ env.DNIV_SCRATCH_DIR }}/lab/**/*.qcow2",
            "!${{ env.DNIV_SCRATCH_DIR }}/lab/**/*.qmp",
        )
        forbidden = (
            "resume_run_id:",
            "scratch-vm-lab-checkpoint-",
            "Prune superseded successful VM checkpoints",
            "actions/artifacts?per_page=100",
        )
        for marker in required:
            if marker not in text:
                errors.append(f"{path}: missing Python overlay-lab safeguard: {marker}")
        for marker in forbidden:
            if marker in text:
                errors.append(f"{path}: obsolete resumable-VM machinery remains: {marker}")

    if name == "interop.yml":
        for marker in (
            "!${{ env.DNIV_SCRATCH_DIR }}/interop/**/*.qcow2",
            "scratch-interop-${{ matrix.arch }}-${{ matrix.suite }}-${{ github.run_id }}",
            "${{ github.job }}-${{ matrix.arch }}-${{ matrix.suite }}",
        ):
            if marker not in text:
                errors.append(f"{path}: missing interoperability storage/runtime safeguard: {marker}")
        rows = []
        for line in lines:
            if match := SCENARIOS_RE.match(line):
                scenarios = match.group(1).split()
                rows.append(scenarios)
                if not scenarios or len(scenarios) > MAX_INTEROP_SCENARIOS_PER_JOB:
                    errors.append(f"{path}: interop matrix row has {len(scenarios)} scenarios; maximum is {MAX_INTEROP_SCENARIOS_PER_JOB}")
        if not rows:
            errors.append(f"{path}: no bounded interoperability scenario rows found")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--staged", action="store_true")
    source.add_argument("--tree")
    args = parser.parse_args()
    try:
        if args.staged:
            paths, reader = staged_source(); source_label = "staged index"
        elif args.tree:
            paths, reader = tree_source(args.tree); source_label = args.tree
        else:
            paths, reader = worktree_source(); source_label = "working tree"
    except (OSError, subprocess.CalledProcessError) as exc:
        print(f"workflow-budget: cannot enumerate workflow source: {exc}", file=sys.stderr)
        return 1
    errors: list[str] = []
    if not paths:
        errors.append(f"no workflow files found in {source_label}")
    for path in paths:
        try:
            errors.extend(check_workflow(path, reader(path)))
        except (OSError, subprocess.CalledProcessError, UnicodeError) as exc:
            errors.append(f"{path}: cannot read workflow source: {exc}")
    if errors:
        for error in errors:
            print(f"workflow-budget: {error}", file=sys.stderr)
        return 1
    print(f"workflow-budget: source={source_label} files={len(paths)} jobs<={MAX_JOB_MINUTES}m artifacts<={MAX_EVIDENCE_DAYS}d queue=max actions=pinned interop-scenarios/job<={MAX_INTEROP_SCENARIOS_PER_JOB}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
