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

"""Fail-closed evidence preflight, manifest and integrity verification."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from pathlib import Path
import tempfile


def die(message: str) -> "NoReturn":
    raise SystemExit(f"evidence-guard: {message}")


def rooted(root: Path, rel: str) -> Path:
    candidate = Path(rel)
    if candidate.is_absolute() or ".." in candidate.parts or rel in {"", "."}:
        die(f"invalid relative evidence path: {rel!r}")
    resolved_root = root.resolve()
    resolved = (root / candidate).resolve()
    try:
        resolved.relative_to(resolved_root)
    except ValueError:
        die(f"evidence path escapes root: {rel}")
    return resolved


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def preflight(root: Path, min_free_bytes: int, min_free_inodes: int) -> None:
    try:
        root.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        die(f"cannot create evidence directory: {exc}")
    if not root.is_dir():
        die(f"evidence root is not a directory: {root}")
    try:
        stats = os.statvfs(root)
    except OSError as exc:
        die(f"cannot stat evidence directory: {exc}")
    free_bytes = stats.f_bavail * stats.f_frsize
    if free_bytes < min_free_bytes:
        die(f"insufficient free evidence bytes: have={free_bytes} need={min_free_bytes}")
    if stats.f_favail < min_free_inodes:
        die(f"insufficient free evidence inodes: have={stats.f_favail} need={min_free_inodes}")

    probe = root / ".dniv-evidence-probe"
    try:
        fd = os.open(probe, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            os.write(fd, b"DNIV-EVIDENCE-PROBE\n")
            os.fsync(fd)
        finally:
            os.close(fd)
        probe.unlink()
    except OSError as exc:
        try:
            probe.unlink(missing_ok=True)
        except OSError:
            pass
        die(f"evidence directory write probe failed: {exc}")


def manifest(root: Path, output: Path, required: list[str]) -> None:
    if not required:
        die("manifest requires at least one evidence file")
    entries = []
    seen: set[str] = set()
    for rel in required:
        if rel in seen:
            die(f"duplicate required evidence path: {rel}")
        seen.add(rel)
        path = rooted(root, rel)
        try:
            if path.is_symlink() or not path.is_file():
                die(f"required evidence is not a regular file: {rel}")
            size = path.stat().st_size
        except OSError as exc:
            die(f"cannot stat required evidence {rel}: {exc}")
        if size <= 0:
            die(f"required evidence is empty: {rel}")
        entries.append({"path": rel, "size": size, "sha256": digest(path)})

    resolved_root = root.resolve()
    resolved_output = output.resolve()
    try:
        resolved_output.relative_to(resolved_root)
    except ValueError:
        die("manifest output must be inside evidence root")
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = {"version": 1, "files": sorted(entries, key=lambda item: item["path"])}
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=output.parent,
            prefix=".dniv-evidence-", delete=False,
        ) as handle:
            json.dump(payload, handle, sort_keys=True, separators=(",", ":"))
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
            temporary = Path(handle.name)
        os.replace(temporary, output)
    except OSError as exc:
        die(f"cannot write evidence manifest: {exc}")


def verify(root: Path, manifest_path: Path) -> None:
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        die(f"invalid evidence manifest: {exc}")
    if not isinstance(payload, dict) or payload.get("version") != 1:
        die("invalid evidence manifest version")
    files = payload.get("files")
    if not isinstance(files, list) or not files:
        die("evidence manifest has no files")

    seen: set[str] = set()
    for entry in files:
        if not isinstance(entry, dict):
            die("invalid evidence manifest entry")
        rel = entry.get("path")
        size = entry.get("size")
        expected = entry.get("sha256")
        if not isinstance(rel, str) or rel in seen:
            die("invalid or duplicate manifest path")
        seen.add(rel)
        if not isinstance(size, int) or size <= 0:
            die(f"invalid manifest size for {rel}")
        if not isinstance(expected, str) or len(expected) != 64:
            die(f"invalid manifest hash for {rel}")
        path = rooted(root, rel)
        if path.is_symlink() or not path.is_file():
            die(f"required evidence is missing or non-regular: {rel}")
        actual_size = path.stat().st_size
        if actual_size != size:
            die(f"evidence size mismatch for {rel}: have={actual_size} expected={size}")
        actual = digest(path)
        if actual != expected:
            die(f"evidence hash mismatch for {rel}")



FOUNDATION_MEMBERS = ("base.qcow2", "boot/vmlinuz", "boot/initrd.img", "session.env")
FOUNDATION_KEYS = (
    "FORMAT",
    "SESSION_ID",
    "ARCH",
    "FOUNDATION_FINGERPRINT",
    "UBUNTU_BASE_RELEASE",
    "UBUNTU_APT_SNAPSHOT",
)


def foundation_member(root: Path, rel: str) -> Path:
    path = rooted(root, rel)
    try:
        if path.is_symlink() or not path.is_file():
            die(f"foundation member missing or non-regular: {rel}")
        if path.stat().st_size <= 0:
            die(f"foundation member is empty: {rel}")
    except OSError as exc:
        die(f"cannot stat foundation member {rel}: {exc}")
    return path


def verify_foundation(
    root: Path,
    session_id: str,
    arch: str,
    fingerprint: str,
    release: str,
    snapshot: str,
) -> None:
    if root.is_symlink() or not root.is_dir():
        die(f"foundation root missing or non-directory: {root}")

    members = {rel: foundation_member(root, rel) for rel in FOUNDATION_MEMBERS}
    sums_path = foundation_member(root, "SHA256SUMS")

    try:
        env_text = members["session.env"].read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        die(f"invalid foundation session.env: {exc}")

    metadata: dict[str, str] = {}
    for line in env_text.splitlines():
        if not line or "=" not in line:
            die("invalid foundation session.env line")
        key, value = line.split("=", 1)
        if not key or key in metadata:
            die(f"duplicate or invalid foundation metadata key: {key!r}")
        metadata[key] = value

    if "SOURCE_SHA" in metadata:
        die("forbidden foundation metadata key: SOURCE_SHA")
    if set(metadata) != set(FOUNDATION_KEYS):
        missing = sorted(set(FOUNDATION_KEYS) - set(metadata))
        extra = sorted(set(metadata) - set(FOUNDATION_KEYS))
        die(
            "foundation metadata keys mismatch: "
            f"missing={','.join(missing) or '-'} extra={','.join(extra) or '-'}"
        )

    expected = {
        "FORMAT": "2",
        "SESSION_ID": session_id,
        "ARCH": arch,
        "FOUNDATION_FINGERPRINT": fingerprint,
        "UBUNTU_BASE_RELEASE": release,
        "UBUNTU_APT_SNAPSHOT": snapshot,
    }
    for key, value in expected.items():
        if metadata[key] != value:
            die(
                f"foundation metadata mismatch {key}: "
                f"have={metadata[key]} expected={value}"
            )

    try:
        sums_text = sums_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        die(f"invalid foundation SHA256SUMS: {exc}")

    recorded: dict[str, str] = {}
    for line in sums_text.splitlines():
        match = re.fullmatch(r"([0-9a-f]{64})  ([^\n]+)", line)
        if match is None:
            die("malformed foundation SHA256SUMS line")
        expected_hash, rel = match.groups()
        if rel in recorded:
            die(f"duplicate foundation checksum member: {rel}")
        recorded[rel] = expected_hash

    required = set(FOUNDATION_MEMBERS)
    if set(recorded) != required:
        missing = sorted(required - set(recorded))
        extra = sorted(set(recorded) - required)
        die(
            "foundation checksum members mismatch: "
            f"missing={','.join(missing) or '-'} extra={','.join(extra) or '-'}"
        )

    for rel in FOUNDATION_MEMBERS:
        actual = digest(members[rel])
        if actual != recorded[rel]:
            die(
                f"foundation hash mismatch for {rel}: "
                f"have={actual} expected={recorded[rel]}"
            )


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("preflight")
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--min-free-bytes", type=int, default=16 * 1024 * 1024)
    p.add_argument("--min-free-inodes", type=int, default=32)

    p = sub.add_parser("manifest")
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--require", action="append", default=[])

    p = sub.add_parser("verify")
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--manifest", type=Path, required=True)

    p = sub.add_parser("foundation")
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--session-id", required=True)
    p.add_argument("--arch", choices=("amd64", "arm64"), required=True)
    p.add_argument("--fingerprint", required=True)
    p.add_argument("--release", required=True)
    p.add_argument("--snapshot", required=True)

    args = parser.parse_args()
    if args.command == "preflight":
        if args.min_free_bytes < 0 or args.min_free_inodes < 0:
            die("free-space thresholds must be non-negative")
        preflight(args.root, args.min_free_bytes, args.min_free_inodes)
        print("evidence-guard: preflight passed")
    elif args.command == "manifest":
        manifest(args.root, args.output, args.require)
        print(f"evidence-guard: manifest={args.output} files={len(args.require)}")
    elif args.command == "verify":
        verify(args.root, args.manifest)
        print("evidence-guard: verification passed")
    else:
        verify_foundation(
            args.root,
            args.session_id,
            args.arch,
            args.fingerprint,
            args.release,
            args.snapshot,
        )
        print("evidence-guard: foundation verification passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
