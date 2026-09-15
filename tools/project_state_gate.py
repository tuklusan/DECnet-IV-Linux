#!/usr/bin/env python3
"""Require every substantive commit to refresh state and generated handover."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from render_handover import render_handover

STATE = "docs/PROJECT_STATE.md"
HANDOVER = "docs/HANDOVER.md"
CONTINUITY_FILES = {STATE, HANDOVER}
REQUIRED_HEADINGS = ("## Resume point", "## Next action")


def git(*args: str) -> str:
    return subprocess.check_output(("git", *args), text=True).strip()


def git_raw(*args: str) -> str:
    """Return file content exactly; generated handover comparison is byte-for-byte."""
    return subprocess.check_output(("git", *args), text=True)


def git_ok(*args: str) -> bool:
    return subprocess.run(
        ("git", *args), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    ).returncode == 0


def validate_state_text(text: str, label: str) -> list[str]:
    errors: list[str] = []
    for heading in REQUIRED_HEADINGS:
        pos = text.find(heading)
        if pos < 0:
            errors.append(f"{label} is missing '{heading}'")
            continue
        body = text[pos + len(heading):]
        next_heading = body.find("\n## ")
        if next_heading >= 0:
            body = body[:next_heading]
        if not body.strip():
            errors.append(f"{label}: {heading} must not be empty")
    return errors


def validate_text_pair(state_text: str, handover_text: str, label: str) -> list[str]:
    errors = validate_state_text(state_text, f"{label}:{STATE}")
    if errors:
        return errors
    try:
        expected = render_handover(state_text)
    except ValueError as exc:
        return [f"{label}:{STATE}: {exc}"]
    if handover_text != expected:
        errors.append(
            f"{label}:{HANDOVER} is stale; run python3 tools/render_handover.py"
        )
    return errors


def read_worktree_pair() -> tuple[str, str] | None:
    try:
        return (
            Path(STATE).read_text(encoding="utf-8"),
            Path(HANDOVER).read_text(encoding="utf-8"),
        )
    except OSError:
        return None


def read_commit_pair(commit: str) -> tuple[str, str] | None:
    try:
        return (
            git_raw("show", f"{commit}:{STATE}"),
            git_raw("show", f"{commit}:{HANDOVER}"),
        )
    except subprocess.CalledProcessError:
        return None


def require_continuity_for_paths(paths: list[str], label: str) -> list[str]:
    changed = {p for p in paths if p}
    substantive = changed - CONTINUITY_FILES
    errors: list[str] = []
    if substantive:
        missing = CONTINUITY_FILES - changed
        if missing:
            errors.append(
                f"{label} changes project files but does not update "
                + " and ".join(sorted(missing))
            )
            errors.append(
                "refresh Resume point/Next action and regenerate the handover in the same commit"
            )
    return errors


def staged_check() -> list[str]:
    paths = git("diff", "--cached", "--name-only").splitlines()
    errors = require_continuity_for_paths(paths, "staged commit")
    pair = read_worktree_pair()
    if pair is None:
        errors.append(f"missing {STATE} or {HANDOVER}")
    else:
        errors.extend(validate_text_pair(*pair, label="worktree"))
    return errors


def usable_base(base: str | None, head: str) -> str | None:
    """Choose a base that survives force-pushes and still covers the working branch."""
    if base and set(base) != {"0"} and git_ok("cat-file", "-e", f"{base}^{{commit}}"):
        if git_ok("merge-base", "--is-ancestor", base, head):
            return base

    # Working branches are promoted from main.  A force-push can make the push
    # event's previous SHA unreachable, so validate everything since main instead.
    if git_ok("rev-parse", "--verify", "origin/main^{commit}"):
        try:
            return git("merge-base", head, "origin/main")
        except subprocess.CalledProcessError:
            pass

    # Last-resort single-commit validation keeps the gate useful in unusual
    # detached/manual runs rather than accepting an invalid range silently.
    try:
        return git("rev-parse", f"{head}^")
    except subprocess.CalledProcessError:
        return None


def commits_in_range(base: str | None, head: str) -> list[str]:
    chosen = usable_base(base, head)
    if chosen:
        return git("rev-list", "--reverse", f"{chosen}..{head}").splitlines()
    return [head]


def commit_paths(commit: str) -> list[str]:
    return git(
        "diff-tree", "--root", "--no-commit-id", "--name-only", "-r", commit
    ).splitlines()


def range_check(base: str | None, head: str) -> list[str]:
    errors: list[str] = []
    for commit in commits_in_range(base, head):
        short = commit[:12]
        paths = commit_paths(commit)
        errors.extend(require_continuity_for_paths(paths, f"commit {short}"))
        if set(paths) - CONTINUITY_FILES:
            pair = read_commit_pair(commit)
            if pair is None:
                errors.append(f"commit {short} is missing {STATE} or {HANDOVER}")
            else:
                errors.extend(validate_text_pair(*pair, label=f"commit {short}"))
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
    print("project-state gate: continuity record and handover are current")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
