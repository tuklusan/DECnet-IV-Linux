#!/usr/bin/env python3
# ============================================================================
# Copyright (c) 2026 Supratim Sanyal of SANYALnet Labs.
# Proprietary rights reserved except as expressly licensed herein.
#
# DO NOT PANIC PORTFOLIO VISUALIZER
# This file is governed by the SANYALnet Labs Non-Commercial License in the
# root LICENSE file. Non-Commercial use is permitted; Commercial Use and use
# for AI/ML model training are prohibited unless separately authorized.
#
# Attribution is required: "Based on original work by Supratim Sanyal of
# SANYALnet Labs." See LICENSE for full terms, warranty disclaimer, termination,
# patent, trademark, and governing-law provisions.
# ============================================================================

"""Repository policy gate."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

import license_monkey

BLOCKED = (
    "cl" + "aude",
    "a" + "i",
    "op" + "en" + "a" + "i",
    "co" + "dex",
    "chat" + "gpt",
    "anth" + "ropic",
    "sp" + "dx",
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


BLOCKED_PATTERNS = tuple(
    re.compile(rf"(?<![^\W_]){re.escape(fold(term))}(?![^\W_])")
    for term in BLOCKED
)
BLOCKED_BYTES_PATTERN = re.compile(
    rb"(?<![A-Za-z0-9])(?:"
    + rb"|".join(re.escape(term.encode("ascii")) for term in BLOCKED)
    + rb")(?![A-Za-z0-9])",
    re.IGNORECASE,
)


def has_blocked_text(value: str) -> bool:
    value = license_monkey.strip_canonical_header(value)
    value = fold(value)
    return any(pattern.search(value) for pattern in BLOCKED_PATTERNS)


def has_blocked_bytes(value: bytes) -> bool:
    try:
        return has_blocked_text(value.decode("utf-8"))
    except UnicodeDecodeError:
        return bool(BLOCKED_BYTES_PATTERN.search(value))


def matcher_self_check() -> list[str]:
    errors: list[str] = []
    allowed = ("main", "mail", "detail", "maintained", "chair", "domain")
    for value in allowed:
        if has_blocked_text(value):
            errors.append(f"matcher false positive: {value}")
    for term in BLOCKED:
        if not has_blocked_text("/" + term.upper() + "/"):
            errors.append("matcher missed a configured term")
        if not has_blocked_bytes(b" " + term.encode("ascii") + b" "):
            errors.append("byte matcher missed a configured term")
        separated = "_" + term + "_"
        if not has_blocked_text(separated) or not has_blocked_bytes(separated.encode("ascii")):
            errors.append("matcher missed a configured token between underscores")
        embedded = "α" + term + "β"
        if has_blocked_text(embedded) or has_blocked_bytes(embedded.encode("utf-8")):
            errors.append("matcher false positive inside Unicode word")
    required = license_monkey.render_header("hash") + "\n\npayload"
    if has_blocked_text(required):
        errors.append("matcher rejected the mandatory canonical project header")
    return errors


def report(label: str) -> None:
    print(f"repository policy violation: blocked token in {label}", file=sys.stderr)


def check_value(label: str, value: object, failures: list[str]) -> None:
    if value is not None and has_blocked_text(str(value)):
        failures.append(label)
        report(label)


def check_bytes(label: str, value: bytes, failures: list[str]) -> None:
    if has_blocked_bytes(value):
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
        ("issue title", ("issue", "title")),
        ("issue body", ("issue", "body")),
        ("comment body", ("comment", "body")),
        ("discussion title", ("discussion", "title")),
        ("discussion body", ("discussion", "body")),
        ("review body", ("review", "body")),
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
        ("head commit message", ("head_commit", "message")),
        ("head commit author name", ("head_commit", "author", "name")),
        ("head commit author email", ("head_commit", "author", "email")),
        ("head commit committer name", ("head_commit", "committer", "name")),
        ("head commit committer email", ("head_commit", "committer", "email")),
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
                    check_value(f"event commit {index} {who} {key}", details.get(key), failures)


def scan_collaborators(failures: list[str]) -> None:
    check_value("repository identity", os.environ.get(ENV_PREFIX + "_REPOSITORY"), failures)
    check_value("workflow actor", os.environ.get(ENV_PREFIX + "_ACTOR"), failures)
    if os.environ.get("CI", "").casefold() != "true":
        return
    repository = os.environ.get(ENV_PREFIX + "_REPOSITORY")
    token = os.environ.get("GH_TOKEN")
    if not repository or not token:
        failures.append("collaborator inspection")
        print("repository policy error: collaborator inspection unavailable", file=sys.stderr)
        return
    result = run("gh", "api", f"repos/{repository}/collaborators", "--paginate", "--jq", ".[].login", check=False)
    if result.returncode != 0:
        failures.append("collaborator inspection")
        print("repository policy error: collaborator inspection failed", file=sys.stderr)
        return
    for login in result.stdout.decode("utf-8", errors="replace").splitlines():
        check_value("collaborator login", login, failures)


def resolve_target(event: dict) -> tuple[str, str | None]:
    if isinstance(event.get("pull_request"), dict):
        head = dig(event, "pull_request", "head", "sha")
        base = dig(event, "pull_request", "base", "sha")
        if head:
            return str(head), str(base) if base else None
    group = event.get("merge_group")
    if isinstance(group, dict) and group.get("head_sha"):
        return str(group["head_sha"]), str(group.get("base_sha")) if group.get("base_sha") else None
    after = event.get("after")
    if after and str(after).strip("0"):
        before = event.get("before")
        return str(after), str(before) if before and str(before).strip("0") else None
    head = run("git", "rev-parse", "HEAD").stdout.decode().strip()
    return head, head


def ensure_object(rev: str) -> None:
    if run("git", "cat-file", "-e", rev + "^{commit}", check=False).returncode == 0:
        return
    fetched = run("git", "fetch", "--no-tags", "--depth=256", "origin", rev, check=False)
    if fetched.returncode != 0:
        sys.stderr.write(fetched.stderr.decode("utf-8", errors="replace"))
        raise SystemExit("repository policy error: unable to fetch target revision")


def path_text(path: str) -> str:
    prefix = CONTROL_ROOT + "/"
    if path == CONTROL_ROOT:
        return ""
    return path[len(prefix):] if path.startswith(prefix) else path


def tree_sha(rev: str) -> str:
    result = run("git", "rev-parse", "--verify", rev + "^{tree}", check=False)
    return result.stdout.decode("ascii", errors="ignore").strip() if result.returncode == 0 else ""


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
        sha = obj_sha.decode("ascii")
        blob = run("git", "cat-file", "-p", sha).stdout
        header_errors = license_monkey.validate_blob(path, blob, sha)
        for error in header_errors:
            failures.append("license header")
            print(f"repository policy error: {error}", file=sys.stderr)
        if has_blocked_bytes(blob):
            failures.append("file content")
            report(f"file content: {path}")


def scan_tree_once(rev: str, failures: list[str], scanned_trees: set[str]) -> None:
    identity = tree_sha(rev)
    if not identity:
        failures.append("tree inspection")
        print("repository policy error: tree inspection failed", file=sys.stderr)
        return
    if identity not in scanned_trees:
        scanned_trees.add(identity)
        scan_tree(rev, failures)


def commit_list(base: str | None, head: str) -> list[str]:
    if base:
        ensure_object(base)
        raw = run("git", "rev-list", base + ".." + head).stdout
    else:
        raw = run("git", "rev-list", head).stdout
    return [line for line in raw.decode().splitlines() if line]


def scan_commit_metadata(commit: str, failures: list[str]) -> None:
    obj = run("git", "cat-file", "-p", commit, check=False)
    if obj.returncode != 0:
        failures.append("commit object inspection")
        print("repository policy error: commit object inspection failed", file=sys.stderr)
        return
    check_bytes("commit object", obj.stdout, failures)
    raw = run("git", "show", "-s", "--format=%B%x00%an%x00%ae%x00%cn%x00%ce", commit).stdout
    parts = raw.decode("utf-8", errors="replace").split("\0")
    labels = ("commit message", "author name", "author email", "committer name", "committer email")
    for label, value in zip(labels, parts):
        check_value(label, value, failures)


def scan_commits(base: str | None, head: str, failures: list[str], scanned_commits: set[str] | None = None, scanned_trees: set[str] | None = None) -> None:
    scanned_commits = scanned_commits if scanned_commits is not None else set()
    scanned_trees = scanned_trees if scanned_trees is not None else set()
    for commit in commit_list(base, head):
        if commit in scanned_commits:
            continue
        scanned_commits.add(commit)
        scan_commit_metadata(commit, failures)
        scan_tree_once(commit, failures, scanned_trees)


def scan_local_config(failures: list[str]) -> None:
    config = run("git", "config", "--local", "--null", "--list", check=False)
    if config.returncode != 0:
        failures.append("local config inspection")
        print("repository policy error: local config inspection failed", file=sys.stderr)
        return
    for record in config.stdout.split(b"\0"):
        if record and has_blocked_bytes(record):
            failures.append("local git config")
            report("local git config")


def scan_refs_and_config(failures: list[str]) -> None:
    refs = run("git", "for-each-ref", "--format=%(refname)", check=False)
    if refs.returncode != 0:
        failures.append("ref inspection")
        print("repository policy error: ref inspection failed", file=sys.stderr)
    else:
        for ref in refs.stdout.decode("utf-8", errors="replace").splitlines():
            check_value("git ref", ref, failures)
            oid = run("git", "rev-parse", "--verify", ref, check=False)
            if oid.returncode != 0:
                failures.append("ref target inspection")
                continue
            name = oid.stdout.decode("ascii", errors="ignore").strip()
            kind = run("git", "cat-file", "-t", name, check=False)
            if kind.returncode == 0 and kind.stdout.strip() == b"tag":
                tag = run("git", "cat-file", "-p", name, check=False)
                if tag.returncode == 0:
                    check_bytes("tag object", tag.stdout, failures)
                else:
                    failures.append("tag inspection")
    scan_local_config(failures)


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
    for error in license_monkey.validate_entries(license_monkey._index_entries()):
        failures.append("license header")
        print(f"repository policy error: {error}", file=sys.stderr)


def zero_object_id(value: str) -> bool:
    return bool(value) and set(value) == {"0"}


def peel_commit(rev: str) -> str | None:
    result = run("git", "rev-parse", "--verify", rev + "^{commit}", check=False)
    if result.returncode != 0:
        return None
    value = result.stdout.decode("ascii", errors="ignore").strip()
    return value or None


def scan_ref_target_object(rev: str, failures: list[str]) -> str | None:
    kind = run("git", "cat-file", "-t", rev, check=False)
    if kind.returncode != 0:
        failures.append("ref target inspection")
        print("repository policy error: ref target is unavailable", file=sys.stderr)
        return None
    object_type = kind.stdout.decode("ascii", errors="ignore").strip()
    if object_type == "tag":
        tag = run("git", "cat-file", "-p", rev, check=False)
        if tag.returncode != 0:
            failures.append("tag inspection")
            return None
        check_bytes("tag object", tag.stdout, failures)
    elif object_type != "commit":
        failures.append("ref target type")
        print("repository policy error: ref must resolve to a commit", file=sys.stderr)
        return None
    commit = peel_commit(rev)
    if not commit:
        failures.append("ref target commit")
    return commit


def pre_push_checks(hook_context: list[str], failures: list[str]) -> None:
    for index, value in enumerate(hook_context):
        check_value(f"pre-push argument {index}", value, failures)
    scan_local_config(failures)
    scanned_commits: set[str] = set()
    scanned_trees: set[str] = set()
    for line_number, line in enumerate(sys.stdin.buffer.read().splitlines(), 1):
        fields = line.split()
        if len(fields) != 4:
            failures.append("pre-push input")
            print(f"repository policy error: malformed pre-push input line {line_number}", file=sys.stderr)
            continue
        local_ref_raw, local_sha_raw, remote_ref_raw, remote_sha_raw = fields
        try:
            local_sha = local_sha_raw.decode("ascii")
            remote_sha = remote_sha_raw.decode("ascii")
        except UnicodeDecodeError:
            failures.append("pre-push object id")
            continue
        if zero_object_id(local_sha):
            continue
        check_bytes("local push ref", local_ref_raw, failures)
        check_bytes("remote push ref", remote_ref_raw, failures)
        local_commit = scan_ref_target_object(local_sha, failures)
        if not local_commit:
            continue
        base = None if zero_object_id(remote_sha) else peel_commit(remote_sha)
        scan_tree_once(local_commit, failures, scanned_trees)
        scan_commits(base, local_commit, failures, scanned_commits, scanned_trees)


def main() -> int:
    parser = argparse.ArgumentParser(description="Enforce repository policy.")
    parser.add_argument("--staged", action="store_true")
    parser.add_argument("--message-file")
    parser.add_argument("--pre-push", action="store_true")
    parser.add_argument("hook_context", nargs="*")
    args = parser.parse_args()
    selected = int(args.staged) + int(bool(args.message_file)) + int(args.pre_push)
    if selected > 1:
        parser.error("policy modes are mutually exclusive")
    if args.hook_context and not args.pre_push:
        parser.error("hook context is valid only with --pre-push")

    failures = matcher_self_check()
    if failures:
        for error in failures:
            print(f"repository policy error: {error}", file=sys.stderr)
        return 1
    if args.message_file:
        data = Path(args.message_file).read_bytes()
        if has_blocked_bytes(data):
            report("commit message")
            return 1
        return 0
    if args.staged:
        staged_checks(failures)
        scan_refs_and_config(failures)
    elif args.pre_push:
        pre_push_checks(args.hook_context, failures)
    else:
        event = load_event()
        event_checks(event, failures)
        scan_collaborators(failures)
        head, base = resolve_target(event)
        ensure_object(head)
        head_commit = scan_ref_target_object(head, failures)
        base_commit = None
        if base:
            ensure_object(base)
            base_commit = peel_commit(base)
            if not base_commit:
                failures.append("base commit inspection")
        scanned_trees: set[str] = set()
        if head_commit:
            scan_tree_once(head_commit, failures, scanned_trees)
            scan_commits(base_commit, head_commit, failures, scanned_trees=scanned_trees)
        scan_refs_and_config(failures)
    if failures:
        print(f"repository policy failed with {len(failures)} violation(s)", file=sys.stderr)
        return 1
    print("repository policy passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
