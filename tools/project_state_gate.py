#!/usr/bin/env python3
"""Require every substantive commit to refresh the project continuity record."""

from __future__ import annotations

import argparse
import subprocess
import sys

STATE = "docs/PROJECT_STATE.md"
REQUIRED_HEADINGS = ("## Resume point", "## Next action")


def run(*args: str, check: bool = True) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(args, check=check, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def git_text(*args: str) -> str:
    return run("git", *args).stdout.decode("utf-8", errors="strict").strip()


def ensure_commit(rev: str) -> None:
    probe = run("git", "cat-file", "-e", rev + "^{commit}", check=False)
    if probe.returncode == 0:
        return
    fetched = run("git", "fetch", "--no-tags", "--depth=256", "origin", rev, check=False)
    if fetched.returncode != 0:
        sys.stderr.write(fetched.stderr.decode("utf-8", errors="replace"))
        raise RuntimeError(f"unable to fetch revision {rev}")


def validate_state_bytes(data: bytes, label: str) -> list[str]:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        return [f"{label}: {STATE} is not valid UTF-8: {exc}"]
    errors: list[str] = []
    for heading in REQUIRED_HEADINGS:
        pos = text.find(heading)
        if pos < 0:
            errors.append(f"{label}: {STATE} is missing '{heading}'")
            continue
        body = text[pos + len(heading):]
        next_heading = body.find("\n## ")
        if next_heading >= 0:
            body = body[:next_heading]
        if not body.strip():
            errors.append(f"{label}: {heading} must not be empty")
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


def read_staged_state() -> tuple[bytes | None, list[str]]:
    result = run("git", "show", ":" + STATE, check=False)
    if result.returncode != 0:
        return None, [f"staged commit: missing {STATE}"]
    return result.stdout, []


def read_commit_state(commit: str) -> tuple[bytes | None, list[str]]:
    result = run("git", "show", f"{commit}:{STATE}", check=False)
    if result.returncode != 0:
        return None, [f"commit {commit[:12]}: missing {STATE}"]
    return result.stdout, []


def staged_check() -> list[str]:
    paths = git_text("diff", "--cached", "--name-only").splitlines()
    errors = require_state_for_paths(paths, "staged commit")
    data, load_errors = read_staged_state()
    errors.extend(load_errors)
    if data is not None:
        errors.extend(validate_state_bytes(data, "staged commit"))
    return errors


def commits_in_range(base: str | None, head: str) -> list[str]:
    ensure_commit(head)
    if base and set(base) != {"0"}:
        ensure_commit(base)
        return git_text("rev-list", "--reverse", f"{base}..{head}").splitlines()
    return [head]


def commit_paths(commit: str) -> list[str]:
    return git_text("diff-tree", "--root", "--no-commit-id", "--name-only", "-r", commit).splitlines()


def range_check(base: str | None, head: str) -> list[str]:
    errors: list[str] = []
    for commit in commits_in_range(base, head):
        label = f"commit {commit[:12]}"
        errors.extend(require_state_for_paths(commit_paths(commit), label))
        data, load_errors = read_commit_state(commit)
        errors.extend(load_errors)
        if data is not None:
            errors.extend(validate_state_bytes(data, label))
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--staged", action="store_true")
    parser.add_argument("--base")
    parser.add_argument("--head", default="HEAD")
    args = parser.parse_args()
    try:
        errors = staged_check() if args.staged else range_check(args.base, args.head)
    except (subprocess.CalledProcessError, RuntimeError) as exc:
        print(f"project-state gate: {exc}", file=sys.stderr)
        return 1
    if errors:
        for error in errors:
            print(f"project-state gate: {error}", file=sys.stderr)
        return 1
    print("project-state gate: continuity record is current")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
