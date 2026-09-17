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

"""Byte-complete exact-tree scan and reproducibility manifest."""

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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rev", required=True)
    parser.add_argument("--pass-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--baseline", type=Path)
    args = parser.parse_args()

    commit = git_text("rev-parse", "--verify", args.rev + "^{commit}")
    head = git_text("rev-parse", "--verify", "HEAD^{commit}")
    if head != commit:
        raise SystemExit(f"SOP-SCAN: checkout {head} is not requested commit {commit}")
    tree = git_text("rev-parse", "--verify", commit + "^{tree}")

    records: list[dict] = []
    aggregate = hashlib.sha256()
    total_bytes = 0

    for mode, blob_sha, path in tree_entries(commit):
        object_data = git_bytes("cat-file", "blob", blob_sha)
        try:
            checkout_data = working_bytes(path, mode)
        except (OSError, UnicodeError, RuntimeError) as exc:
            raise SystemExit(f"SOP-SCAN: cannot verify checkout path {path}: {exc}") from exc
        if checkout_data != object_data:
            raise SystemExit(f"SOP-SCAN: checkout bytes differ from commit object: {path}")

        digest = hashlib.sha256(object_data).hexdigest()
        size = len(object_data)
        lines = line_count(object_data)
        total_bytes += size
        encoded_path = path.encode("utf-8", errors="surrogateescape")
        aggregate.update(mode.encode("ascii") + b"\0")
        aggregate.update(encoded_path + b"\0")
        aggregate.update(blob_sha.encode("ascii") + b"\0")
        aggregate.update(digest.encode("ascii") + b"\0")
        aggregate.update(str(size).encode("ascii") + b"\0")
        aggregate.update(str(lines).encode("ascii") + b"\n")
        records.append(
            {
                "path": path,
                "mode": mode,
                "blob": blob_sha,
                "sha256": digest,
                "bytes": size,
                "lines": lines,
            }
        )

    result = {
        "format": 1,
        "pass_id": args.pass_id,
        "commit": commit,
        "tree": tree,
        "file_count": len(records),
        "byte_count": total_bytes,
        "scan_sha256": aggregate.hexdigest(),
        "files": records,
    }

    if args.baseline:
        baseline = load_summary(args.baseline)
        comparable = ("commit", "tree", "file_count", "byte_count", "scan_sha256", "files")
        differences = [key for key in comparable if baseline.get(key) != result.get(key)]
        if differences:
            raise SystemExit(
                "SOP-SCAN: scan differs from baseline in " + ", ".join(differences)
            )

    atomic_json(args.output, result)
    print(
        "SOP-SCAN: pass=" + args.pass_id
        + f" commit={commit} tree={tree} files={len(records)}"
        + f" bytes={total_bytes} digest={result['scan_sha256']}"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (subprocess.CalledProcessError, RuntimeError) as exc:
        print(f"SOP-SCAN: {exc}", file=sys.stderr)
        raise SystemExit(1)
