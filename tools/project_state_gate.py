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

"""Require substantive commits to refresh both durable continuity records."""

from __future__ import annotations

import argparse
import subprocess
import sys
from collections.abc import Callable

PROJECT_STATE = "docs/PROJECT_STATE.md"
SCRATCH_RESUME = "scratch/RESUME.md"
CONTINUITY = (PROJECT_STATE, SCRATCH_RESUME)
REQUIRED_HEADINGS = {
    PROJECT_STATE: ("## Resume point", "## Next action"),
    SCRATCH_RESUME: ("## Current checkpoint", "## Next action"),
}


def git(*args: str) -> str:
    return subprocess.check_output(("git", *args), text=True).strip()


def git_file(spec: str) -> str:
    return subprocess.check_output(("git", "show", spec), text=True)


def validate_record_text(path_text: str, text: str) -> list[str]:
    errors: list[str] = []
    for heading in REQUIRED_HEADINGS[path_text]:
        pos = text.find(heading)
        if pos < 0:
            errors.append(f"{path_text} is missing '{heading}'")
            continue
        body = text[pos + len(heading) :]
        next_heading = body.find("\n## ")
        if next_heading >= 0:
            body = body[:next_heading]
        if not body.strip():
            errors.append(f"{path_text} {heading} must not be empty")
    return errors


def validate_state(reader: Callable[[str], str]) -> list[str]:
    errors: list[str] = []
    for path in CONTINUITY:
        try:
            text = reader(path)
        except subprocess.CalledProcessError:
            errors.append(f"missing {path}")
            continue
        errors.extend(validate_record_text(path, text))
    return errors


def require_state_for_paths(paths: list[str], label: str) -> list[str]:
    changed = {p for p in paths if p}
    continuity = set(CONTINUITY)
    substantive = changed - continuity
    missing = continuity - changed
    if substantive and missing:
        return [
            f"{label} changes project files but does not update " + ", ".join(sorted(missing)),
            "refresh both durable continuity records in the same commit",
        ]
    return []


def staged_check() -> list[str]:
    paths = git("diff", "--cached", "--name-only").splitlines()
    return require_state_for_paths(paths, "staged commit") + validate_state(
        lambda path: git_file(":" + path)
    )


def commits_in_range(base: str | None, head: str) -> list[str]:
    if base and set(base) != {"0"}:
        return git("rev-list", "--reverse", f"{base}..{head}").splitlines()
    return [git("rev-parse", "--verify", head + "^{commit}")]


def commit_paths(commit: str) -> list[str]:
    return git(
        "diff-tree", "--root", "--no-commit-id", "--name-only", "-r", commit
    ).splitlines()


def range_check(base: str | None, head: str) -> list[str]:
    errors: list[str] = []
    commits = commits_in_range(base, head)
    for commit in commits:
        short = commit[:12]
        errors.extend(require_state_for_paths(commit_paths(commit), f"commit {short}"))
        errors.extend(validate_state(lambda path, commit=commit: git_file(f"{commit}:{path}")))
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--staged", action="store_true")
    parser.add_argument("--base")
    parser.add_argument("--head", default="HEAD")
    args = parser.parse_args()

    errors = staged_check() if args.staged else range_check(args.base, args.head)
    if errors:
        for error in errors:
            print(f"project-state gate: {error}", file=sys.stderr)
        return 1
    print("project-state gate: durable continuity records are current")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
