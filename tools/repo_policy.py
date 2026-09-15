#!/usr/bin/env python3
"""Repository policy gate."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import unicodedata
from pathlib import Path

BLOCKED = (
    "cl" + "aude",
    "open" + "ai",
    "co" + "dex",
    "chat" + "gpt",
)
CONTROL_ROOT = "." + "git" + "hub"
ENV_PREFIX = ("git" + "hub").upper()


def run(*args: str, check: bool = True) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        args,
        check=check,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def fold(value: str) -> str:
    return unicodedata.normalize("NFKC", value).casefold()


def has_blocked_text(value: str) -> bool:
    value = fold(value)
    return any(fold(term) in value for term in BLOCKED)


def has_blocked_bytes(value: bytes) -> bool:
    lowered = value.lower()
    if any(term.encode("ascii") in lowered for term in BLOCKED):
        return True
    return has_blocked_text(value.decode("utf-8", errors="ignore"))


def report(label: str) -> None:
    print(f"repository policy violation: blocked token in {label}", file=sys.stderr)


def check_value(label: str, value: object, failures: list[str]) -> None:
    if value is None:
        return
    text = str(value)
    if has_blocked_text(text):
        failures.append(label)
        report(label)


def load_event() -> dict:
    path = os.environ.get(ENV_PREFIX + "_EVENT_PATH")
    if not path:
        return {}
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
            return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def dig(data: dict, *parts: str) -> object:
    current: object = data
    for part in parts:
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def event_checks(event: dict, failures: list[str]) -> None:
    fields = (
        ("sender login", ("sender", "login")),
        ("member login", ("member", "login")),
        ("pull request title", ("pull_request", "title")),
        ("pull request body", ("pull_request", "body")),
        ("pull request author", ("pull_request", "user", "login")),
        ("pull request head ref", ("pull_request", "head", "ref")),
        ("pull request head label", ("pull_request", "head", "label")),
        ("pull request head owner", ("pull_request", "head", "user", "login")),
        ("pull request base ref", ("pull_request", "base", "ref")),
        ("merge head ref", ("merge_group", "head_ref")),
        ("merge base ref", ("merge_group", "base_ref")),
        ("push ref", ("ref",)),
        ("pusher name", ("pusher", "name")),
        ("pusher email", ("pusher", "email")),
    )
    for label, parts in fields:
        check_value(label, dig(event, *parts), failures)

    for index, commit in enumerate(event.get("commits", ())):
        if not isinstance(commit, dict):
            continue
        check_value(f"event commit {index} message", commit.get("message"), failures)
        for who in ("author", "committer"):
            details = commit.get(who)
            if isinstance(details, dict):
                for key in ("name", "email", "username"):
                    check_value(
                        f"event commit {index} {who} {key}",
                        details.get(key),
                        failures,
                    )


def scan_collaborators(failures: list[str]) -> None:
    check_value(
        "repository identity",
        os.environ.get(ENV_PREFIX + "_REPOSITORY"),
        failures,
    )
    check_value(
        "workflow actor",
        os.environ.get(ENV_PREFIX + "_ACTOR"),
        failures,
    )

    if os.environ.get("CI", "").casefold() != "true":
        return

    repository = os.environ.get(ENV_PREFIX + "_REPOSITORY")
    token = os.environ.get("GH_TOKEN")
    if not repository or not token:
        failures.append("collaborator inspection")
        print(
            "repository policy error: collaborator inspection unavailable",
            file=sys.stderr,
        )
        return

    result = run(
        "gh",
        "api",
        f"repos/{repository}/collaborators",
        "--paginate",
        "--jq",
        ".[].login",
        check=False,
    )
    if result.returncode != 0:
        failures.append("collaborator inspection")
        print(
            "repository policy error: collaborator inspection failed",
            file=sys.stderr,
        )
        return

    for login in result.stdout.decode("utf-8", errors="replace").splitlines():
        check_value("collaborator login", login, failures)


def resolve_target(event: dict) -> tuple[str, str | None]:
    pr = event.get("pull_request")
    if isinstance(pr, dict):
        head = dig(event, "pull_request", "head", "sha")
        base = dig(event, "pull_request", "base", "sha")
        if head:
            return str(head), str(base) if base else None

    group = event.get("merge_group")
    if isinstance(group, dict):
        head = group.get("head_sha")
        base = group.get("base_sha")
        if head:
            return str(head), str(base) if base else None

    after = event.get("after")
    if after and str(after).strip("0"):
        before = event.get("before")
        if before and str(before).strip("0"):
            return str(after), str(before)
        return str(after), None

    head = run("git", "rev-parse", "HEAD").stdout.decode().strip()
    return head, None


def ensure_object(rev: str) -> None:
    probe = run("git", "cat-file", "-e", rev + "^{commit}", check=False)
    if probe.returncode == 0:
        return
    fetched = run(
        "git",
        "fetch",
        "--no-tags",
        "--depth=256",
        "origin",
        rev,
        check=False,
    )
    if fetched.returncode != 0:
        sys.stderr.write(fetched.stderr.decode("utf-8", errors="replace"))
        raise SystemExit("repository policy error: unable to fetch target revision")


def path_text(path: str) -> str:
    prefix = CONTROL_ROOT + "/"
    if path == CONTROL_ROOT:
        return ""
    if path.startswith(prefix):
        return path[len(prefix):]
    return path


def scan_tree(rev: str, failures: list[str]) -> None:
    raw = run("git", "ls-tree", "-r", "-z", rev).stdout
    for record in raw.split(b"\0"):
        if not record:
            continue
        meta, raw_path = record.split(b"\t", 1)
        fields = meta.split()
        if len(fields) != 3:
            continue
        _mode, obj_type, obj_sha = fields
        path = raw_path.decode("utf-8", errors="surrogateescape")
        if has_blocked_text(path_text(path)):
            failures.append("path")
            report("path")
        if obj_type != b"blob":
            continue
        blob = run("git", "cat-file", "-p", obj_sha.decode()).stdout
        if has_blocked_bytes(blob):
            failures.append("file content")
            report(f"file content: {path}")


def commit_list(base: str | None, head: str) -> list[str]:
    if base:
        ensure_object(base)
        raw = run("git", "rev-list", base + ".." + head).stdout
    else:
        raw = run("git", "rev-list", head).stdout
    return [line for line in raw.decode().splitlines() if line]


def scan_commits(base: str | None, head: str, failures: list[str]) -> None:
    for commit in commit_list(base, head):
        raw = run(
            "git",
            "show",
            "-s",
            "--format=%B%x00%an%x00%ae%x00%cn%x00%ce",
            commit,
        ).stdout
        parts = raw.decode("utf-8", errors="replace").split("\0")
        labels = (
            "commit message",
            "author name",
            "author email",
            "committer name",
            "committer email",
        )
        for label, value in zip(labels, parts):
            check_value(label, value, failures)


def staged_checks(failures: list[str]) -> None:
    raw = run("git", "diff", "--cached", "--name-only", "-z", "--diff-filter=ACMR").stdout
    for raw_path in raw.split(b"\0"):
        if not raw_path:
            continue
        path = raw_path.decode("utf-8", errors="surrogateescape")
        if has_blocked_text(path_text(path)):
            failures.append("staged path")
            report("staged path")
        blob = run("git", "show", ":" + path, check=False)
        if blob.returncode == 0 and has_blocked_bytes(blob.stdout):
            failures.append("staged content")
            report(f"staged content: {path}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Enforce repository policy.")
    parser.add_argument("--staged", action="store_true")
    parser.add_argument("--message-file")
    args = parser.parse_args()

    failures: list[str] = []

    if args.message_file:
        data = Path(args.message_file).read_bytes()
        if has_blocked_bytes(data):
            report("commit message")
            return 1
        return 0

    if args.staged:
        staged_checks(failures)
    else:
        event = load_event()
        event_checks(event, failures)
        scan_collaborators(failures)
        head, base = resolve_target(event)
        ensure_object(head)
        scan_tree(head, failures)
        scan_commits(base, head, failures)

    if failures:
        print(f"repository policy failed with {len(failures)} violation(s)", file=sys.stderr)
        return 1

    print("repository policy passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
