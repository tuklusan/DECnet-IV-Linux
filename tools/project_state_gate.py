#!/usr/bin/env python3
"""Require every substantive commit to refresh the project continuity record."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

STATE = "docs/PROJECT_STATE.md"
REQUIRED_HEADINGS = ("## Resume point", "## Next action")


def git(*args: str) -> str:
    return subprocess.check_output(("git", *args), text=True).strip()


def validate_state() -> list[str]:
    path = Path(STATE)
    if not path.exists():
        return [f"missing {STATE}"]
    text = path.read_text(encoding="utf-8")
    errors: list[str] = []
    for heading in REQUIRED_HEADINGS:
        pos = text.find(heading)
        if pos < 0:
            errors.append(f"{STATE} is missing '{heading}'")
            continue
        body = text[pos + len(heading):]
        next_heading = body.find("\n## ")
        if next_heading >= 0:
            body = body[:next_heading]
        if not body.strip():
            errors.append(f"{heading} must not be empty")
    return errors


def require_state_for_paths(paths: list[str], label: str) -> list[str]:
    changed = {p for p in paths if p}
    substantive = changed - {STATE}
    if substantive and STATE not in changed:
        return [
            f"{label} changes project files but does not update {STATE}",
            "refresh the Resume point and Next action in the same commit",
        ]
    return []


def staged_check() -> list[str]:
    paths = git("diff", "--cached", "--name-only").splitlines()
    return require_state_for_paths(paths, "staged commit") + validate_state()


def commits_in_range(base: str | None, head: str) -> list[str]:
    if base and set(base) != {"0"}:
        return git("rev-list", "--reverse", f"{base}..{head}").splitlines()
    return [head]


def commit_paths(commit: str) -> list[str]:
    return git(
        "diff-tree", "--root", "--no-commit-id", "--name-only", "-r", commit
    ).splitlines()


def range_check(base: str | None, head: str) -> list[str]:
    errors: list[str] = []
    for commit in commits_in_range(base, head):
        short = commit[:12]
        errors.extend(require_state_for_paths(commit_paths(commit), f"commit {short}"))
    errors.extend(validate_state())
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
    print("project-state gate: continuity record is current")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
