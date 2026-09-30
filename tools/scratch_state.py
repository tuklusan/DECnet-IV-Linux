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

"""Create and update durable workflow state stored below scratch/."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import tempfile
from pathlib import Path


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def git_text(*args: str) -> str:
    return subprocess.check_output(("git", *args), text=True).strip()


def state_path(directory: Path) -> Path:
    return directory / "state.json"


def atomic_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2, sort_keys=True)
            handle.write("\n")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def read_state(directory: Path) -> dict:
    path = state_path(directory)
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("format") != 1:
        raise SystemExit(f"scratch-state: invalid state file: {path}")
    return data


def init_state(args: argparse.Namespace) -> int:
    directory = args.dir
    directory.mkdir(parents=True, exist_ok=True)
    source_sha = args.source_sha or os.environ.get("GITHUB_SHA") or git_text("rev-parse", "HEAD")
    source_sha = git_text("rev-parse", "--verify", source_sha + "^{commit}")
    source_tree = git_text("rev-parse", "--verify", source_sha + "^{tree}")
    expected_sha = ""
    if args.expected_sha:
        expected_sha = git_text("rev-parse", "--verify", args.expected_sha + "^{commit}")
        if source_sha != expected_sha:
            raise SystemExit(
                "scratch-state: workflow source commit does not match parent expected SHA"
            )
    if args.parent_run_id and not expected_sha:
        raise SystemExit(
            "scratch-state: parent_run_id requires expected_sha to bind the child run"
        )
    timestamp = now()
    data = {
        "format": 1,
        "workflow": args.workflow,
        "job": args.job,
        "arch": args.arch or "",
        "mode": args.mode or "",
        "status": "started",
        "created_utc": timestamp,
        "updated_utc": timestamp,
        "source_sha": source_sha,
        "source_tree": source_tree,
        "expected_sha": expected_sha,
        "repository": os.environ.get("GITHUB_REPOSITORY", ""),
        "ref": os.environ.get("GITHUB_REF", ""),
        "event": os.environ.get("GITHUB_EVENT_NAME", ""),
        "run_id": os.environ.get("GITHUB_RUN_ID", "local"),
        "run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT", "1"),
        "parent_run_id": args.parent_run_id or "",
        "resume_run_id": args.resume_run_id or "",
        "resume_run_attempt": args.resume_run_attempt or "",
        "runner_name": os.environ.get("RUNNER_NAME", ""),
        "runner_os": os.environ.get("RUNNER_OS", ""),
        "runner_arch": os.environ.get("RUNNER_ARCH", ""),
        "milestones": [],
        "values": {},
    }
    atomic_json(state_path(directory), data)
    print(f"scratch-state: initialized {state_path(directory)}")
    return 0


def mark_state(args: argparse.Namespace) -> int:
    data = read_state(args.dir)
    data["status"] = args.status
    data["updated_utc"] = now()
    milestone = {"utc": data["updated_utc"], "status": args.status}
    if args.note:
        milestone["note"] = args.note
    data.setdefault("milestones", []).append(milestone)
    atomic_json(state_path(args.dir), data)
    print(f"scratch-state: status={args.status}")
    return 0


def set_value(args: argparse.Namespace) -> int:
    data = read_state(args.dir)
    data.setdefault("values", {})[args.key] = args.value
    data["updated_utc"] = now()
    atomic_json(state_path(args.dir), data)
    print(f"scratch-state: {args.key}={args.value}")
    return 0


def verify_state(args: argparse.Namespace) -> int:
    data = read_state(args.dir)
    head = git_text("rev-parse", "--verify", "HEAD^{commit}")
    tree = git_text("rev-parse", "--verify", "HEAD^{tree}")
    if data.get("source_sha") != head or data.get("source_tree") != tree:
        raise SystemExit(
            "scratch-state: checkout no longer matches recorded source commit/tree"
        )
    expected_sha = data.get("expected_sha", "")
    if expected_sha and expected_sha != head:
        raise SystemExit(
            "scratch-state: checkout no longer matches parent expected SHA"
        )
    if data.get("parent_run_id") and not expected_sha:
        raise SystemExit(
            "scratch-state: parent run lineage is not bound to an expected SHA"
        )
    print(f"scratch-state: exact source verified {head} {tree}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init")
    init.add_argument("--dir", type=Path, required=True)
    init.add_argument("--workflow", required=True)
    init.add_argument("--job", required=True)
    init.add_argument("--arch")
    init.add_argument("--mode")
    init.add_argument("--source-sha")
    init.add_argument("--parent-run-id")
    init.add_argument("--expected-sha")
    init.add_argument("--resume-run-id")
    init.add_argument("--resume-run-attempt")
    init.set_defaults(func=init_state)

    mark = sub.add_parser("mark")
    mark.add_argument("--dir", type=Path, required=True)
    mark.add_argument("--status", required=True)
    mark.add_argument("--note")
    mark.set_defaults(func=mark_state)

    value = sub.add_parser("set")
    value.add_argument("--dir", type=Path, required=True)
    value.add_argument("--key", required=True)
    value.add_argument("--value", required=True)
    value.set_defaults(func=set_value)

    verify = sub.add_parser("verify")
    verify.add_argument("--dir", type=Path, required=True)
    verify.set_defaults(func=verify_state)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
