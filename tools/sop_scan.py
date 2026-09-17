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

"""Diff-scoped candidate scan with explicit full-tree opt-in."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"


def git_bytes(*args: str) -> bytes:
    return subprocess.check_output(("git", *args))


def git_text(*args: str) -> str:
    return git_bytes(*args).decode("utf-8").strip()


def line_count(data: bytes) -> int:
    if not data:
        return 0
    return data.count(b"\n") + (0 if data.endswith(b"\n") else 1)


def working_bytes(path: str, mode: str) -> bytes:
    info = os.lstat(path)
    if mode == "120000":
        if not stat.S_ISLNK(info.st_mode):
            raise RuntimeError(f"expected symlink checkout object: {path}")
        return os.readlink(path).encode("utf-8", errors="surrogateescape")
    if not stat.S_ISREG(info.st_mode):
        raise RuntimeError(f"expected regular checkout object: {path}")
    expected_exec = mode == "100755"
    actual_exec = bool(info.st_mode & stat.S_IXUSR)
    if expected_exec != actual_exec:
        raise RuntimeError(f"checkout executable mode differs from tree: {path}")
    return Path(path).read_bytes()


def tree_entries(rev: str):
    raw = git_bytes("ls-tree", "-r", "-z", rev)
    for record in raw.split(b"\0"):
        if not record:
            continue
        meta, raw_path = record.split(b"\t", 1)
        mode, kind, sha = meta.split()
        if kind != b"blob":
            raise RuntimeError(
                f"unsupported tracked object {kind.decode(errors='replace')} at "
                f"{raw_path.decode(errors='replace')}"
            )
        yield (
            mode.decode("ascii"),
            sha.decode("ascii"),
            raw_path.decode("utf-8", errors="surrogateescape"),
        )


def tree_entry(rev: str, path: str) -> tuple[str, str] | None:
    raw = git_bytes("ls-tree", "-z", rev, "--", path)
    records = [record for record in raw.split(b"\0") if record]
    if not records:
        return None
    if len(records) != 1:
        raise RuntimeError(f"ambiguous tree entry for {path}")
    meta, raw_path = records[0].split(b"\t", 1)
    mode, kind, sha = meta.split()
    decoded = raw_path.decode("utf-8", errors="surrogateescape")
    if decoded != path or kind != b"blob":
        raise RuntimeError(f"unsupported tree entry for {path}")
    return mode.decode("ascii"), sha.decode("ascii")


def resolve_base(commit: str, requested: str | None) -> str:
    if requested:
        return git_text("rev-parse", "--verify", requested + "^{commit}")
    parents = git_text("rev-list", "--parents", "-n", "1", commit).split()
    if len(parents) > 2:
        raise RuntimeError(
            "merge candidate requires explicit --base for a bounded review diff"
        )
    if len(parents) == 2:
        return parents[1]
    return EMPTY_TREE


def changed_paths(base: str, commit: str) -> list[str]:
    raw = git_bytes(
        "diff", "--name-only", "-z", "--no-renames", base, commit, "--"
    )
    return [
        item.decode("utf-8", errors="surrogateescape")
        for item in raw.split(b"\0")
        if item
    ]


def load_summary(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise RuntimeError(f"invalid baseline manifest: {path}")
    return data


def atomic_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def scan_blob(path: str, mode: str, blob_sha: str, verify_checkout: bool) -> dict:
    object_data = git_bytes("cat-file", "blob", blob_sha)
    if verify_checkout:
        try:
            checkout_data = working_bytes(path, mode)
        except (OSError, UnicodeError, RuntimeError) as exc:
            raise RuntimeError(f"cannot verify checkout path {path}: {exc}") from exc
        if checkout_data != object_data:
            raise RuntimeError(f"checkout bytes differ from commit object: {path}")
    return {
        "path": path,
        "mode": mode,
        "blob": blob_sha,
        "sha256": hashlib.sha256(object_data).hexdigest(),
        "bytes": len(object_data),
        "lines": line_count(object_data),
    }


def full_tree_scan(commit: str) -> tuple[list[dict], int, str]:
    records: list[dict] = []
    aggregate = hashlib.sha256()
    total_bytes = 0
    for mode, blob_sha, path in tree_entries(commit):
        record = scan_blob(path, mode, blob_sha, True)
        total_bytes += record["bytes"]
        aggregate.update(json.dumps(record, sort_keys=True).encode("utf-8") + b"\n")
        records.append(record)
    return records, total_bytes, aggregate.hexdigest()


def diff_scan(base: str, commit: str) -> tuple[list[dict], int, str, bytes]:
    status = git_text("status", "--porcelain=v1", "--untracked-files=no")
    if status:
        raise RuntimeError("tracked checkout differs from requested commit")

    patch = git_bytes(
        "diff",
        "--binary",
        "--full-index",
        "--no-ext-diff",
        "--no-color",
        "--unified=3",
        "--no-renames",
        base,
        commit,
        "--",
    )
    records: list[dict] = []
    total_bytes = 0
    aggregate = hashlib.sha256(patch)

    for path in changed_paths(base, commit):
        old_entry = tree_entry(base, path)
        new_entry = tree_entry(commit, path)
        if old_entry is None and new_entry is None:
            raise RuntimeError(f"changed path missing from both trees: {path}")

        if new_entry is None:
            mode, blob_sha = old_entry
            record = scan_blob(path, mode, blob_sha, False)
            record["status"] = "deleted"
            if os.path.lexists(path):
                raise RuntimeError(f"deleted path still present in checkout: {path}")
        else:
            mode, blob_sha = new_entry
            record = scan_blob(path, mode, blob_sha, True)
            record["status"] = "added" if old_entry is None else "changed"
            if old_entry is not None:
                record["old_mode"] = old_entry[0]
                record["old_blob"] = old_entry[1]

        total_bytes += record["bytes"]
        aggregate.update(json.dumps(record, sort_keys=True).encode("utf-8") + b"\n")
        records.append(record)

    return records, total_bytes, aggregate.hexdigest(), patch


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rev", required=True)
    parser.add_argument("--pass-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--base")
    parser.add_argument(
        "--full-tree",
        action="store_true",
        help="explicit opt-in for a complete tracked-tree scan",
    )
    args = parser.parse_args()

    commit = git_text("rev-parse", "--verify", args.rev + "^{commit}")
    head = git_text("rev-parse", "--verify", "HEAD^{commit}")
    if head != commit:
        raise SystemExit(f"SOP-SCAN: checkout {head} is not requested commit {commit}")
    tree = git_text("rev-parse", "--verify", commit + "^{tree}")

    if args.full_tree:
        records, total_bytes, scan_sha256 = full_tree_scan(commit)
        result = {
            "format": 2,
            "scope": "full-tree",
            "pass_id": args.pass_id,
            "commit": commit,
            "tree": tree,
            "file_count": len(records),
            "byte_count": total_bytes,
            "scan_sha256": scan_sha256,
            "files": records,
        }
    else:
        base = resolve_base(commit, args.base)
        records, total_bytes, scan_sha256, patch = diff_scan(base, commit)
        result = {
            "format": 2,
            "scope": "diff",
            "context_lines": 3,
            "pass_id": args.pass_id,
            "base": base,
            "commit": commit,
            "tree": tree,
            "file_count": len(records),
            "byte_count": total_bytes,
            "diff_bytes": len(patch),
            "diff_lines": line_count(patch),
            "diff_sha256": hashlib.sha256(patch).hexdigest(),
            "scan_sha256": scan_sha256,
            "files": records,
        }

    if args.baseline:
        baseline = load_summary(args.baseline)
        comparable = tuple(key for key in result if key != "pass_id")
        differences = [
            key
            for key in comparable
            if baseline.get(key) != result.get(key)
        ]
        extra = [key for key in baseline if key not in result and key != "pass_id"]
        differences.extend(extra)
        if differences:
            raise SystemExit(
                "SOP-SCAN: scan differs from baseline in "
                + ", ".join(sorted(set(differences)))
            )

    atomic_json(args.output, result)
    detail = (
        f" base={result['base']} diff-lines={result['diff_lines']}"
        if result["scope"] == "diff"
        else ""
    )
    print(
        "SOP-SCAN: pass="
        + args.pass_id
        + f" scope={result['scope']} commit={commit} tree={tree}"
        + f" files={len(records)} bytes={total_bytes}{detail}"
        + f" digest={result['scan_sha256']}"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (subprocess.CalledProcessError, RuntimeError) as exc:
        print(f"SOP-SCAN: {exc}", file=sys.stderr)
        raise SystemExit(1)
