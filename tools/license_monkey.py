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

"""Enforce the canonical DECnet-IV-Linux project header and root license."""

from __future__ import annotations

import argparse
import io
import subprocess
import sys
import tarfile
from pathlib import PurePosixPath

PROJECT_NAME = "DECnet-IV-Linux"
DEVELOPER = "Supratim Sanyal"
ORGANIZATION = "SANYALnet Labs"
LICENSE_PATH = "LICENSE"
LICENSE_BLOB = "c6dabab19a2d36bffddabe7584a932c72fa272c3"

# Keep stale prior-project identities out of readable project text without
# carrying those names in readable source. Matching is case-insensitive.
_LEGACY_PROJECTS = (
    bytes.fromhex(
        "444f204e4f542050414e494320504f5254464f4c494f2056495355414c495a4552"
    ).lower(),
    bytes.fromhex(
        "444f2d4e4f542d50414e49432d504f5254464f4c494f2d56495355414c495a4552"
    ).lower(),
)

_CORE = (
    "============================================================================",
    f"Copyright (c) 2026 {DEVELOPER} of {ORGANIZATION}.",
    "Proprietary rights reserved except as expressly licensed herein.",
    "",
    PROJECT_NAME,
    f"This file is governed by the {ORGANIZATION} Non-Commercial License in the",
    "root LICENSE file. Non-Commercial use is permitted; Commercial Use and use",
    "for " + "A" + "I/ML model training are prohibited unless separately authorized.",
    "",
    f'Attribution is required: "Based on original work by {DEVELOPER} of',
    f'{ORGANIZATION}." See LICENSE for full terms, warranty disclaimer, termination,',
    "patent, trademark, and governing-law provisions.",
    "============================================================================",
)

_BINARY_SUFFIXES = {
    ".7z", ".bz2", ".gif", ".gz", ".ico", ".img", ".iso", ".jpeg", ".jpg",
    ".ko", ".o", ".pcap", ".pdf", ".png", ".qcow2", ".raw", ".tar", ".xz",
    ".zip",
}

# Exclude generated/cache and repository-metadata directories at the Git
# enumeration command itself so their contents never reach validation.
_PRUNED_PATHS = (
    ":(exclude,glob)**/__pycache__/**",
    ":(exclude,glob)**/.git/**",
)


def _run(*args: str) -> bytes:
    return subprocess.check_output(("git", *args))


def style_for(path: str) -> str | None:
    if path == LICENSE_PATH:
        return None
    suffix = PurePosixPath(path).suffix.casefold()
    if suffix in _BINARY_SUFFIXES:
        return None
    if suffix in {".c", ".h"}:
        return "slash"
    if suffix == ".md":
        return "html"
    return "hash"


def render_header(style: str) -> str:
    if style == "slash":
        return "\n".join("//" if not line else "// " + line for line in _CORE)
    if style == "hash":
        return "\n".join("#" if not line else "# " + line for line in _CORE)
    if style == "html":
        return "\n".join("<!-- -->" if not line else f"<!-- {line} -->" for line in _CORE)
    raise ValueError(f"unsupported header style: {style}")


def _split_shebang(text: str) -> tuple[str, str]:
    if not text.startswith("#!"):
        return "", text
    end = text.find("\n")
    if end < 0:
        return text, ""
    return text[: end + 1], text[end + 1 :]


def strip_canonical_header(text: str) -> str:
    """Remove one exact canonical leading header for other policy scanners."""
    shebang, body = _split_shebang(text)
    del shebang
    for style in ("slash", "hash", "html"):
        header = render_header(style)
        if body.startswith(header):
            body = body[len(header) :]
            if body.startswith("\n"):
                body = body[1:]
            return body
    return text


def validate_blob(path: str, data: bytes, blob_sha: str | None = None) -> list[str]:
    folded = data.lower()
    if any(identity in folded for identity in _LEGACY_PROJECTS):
        return [f"obsolete project identity present: {path}"]

    if path == LICENSE_PATH:
        if blob_sha and blob_sha != LICENSE_BLOB:
            return [f"{LICENSE_PATH} does not match the canonical {PROJECT_NAME} license"]
        return []

    style = style_for(path)
    if style is None:
        return []

    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return [f"project-owned text artifact is not UTF-8: {path}"]

    shebang, body = _split_shebang(text)
    del shebang
    header = render_header(style)
    if not body.startswith(header + "\n\n"):
        return [f"missing or non-canonical project header: {path}"]

    remainder = body[len(header) + 2 :]
    leading = "\n".join(remainder.splitlines()[:8]).casefold()
    if "license-identifier:" in leading or "// license:" in leading or "# license:" in leading:
        return [f"competing source header follows canonical header: {path}"]
    return []


def _tree_entries(rev: str):
    # git ls-tree does not support exclude pathspec magic. git archive does,
    # so use it strictly for pruned path enumeration, then resolve each
    # retained path back to its exact blob object for validation.
    raw = _run("archive", "--format=tar", rev, "--", ".", *_PRUNED_PATHS)
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:") as archive:
        for member in archive.getmembers():
            if not (member.isfile() or member.issym()):
                continue
            path = member.name.removeprefix("./")
            sha = _run("rev-parse", f"{rev}:{path}").strip().decode("ascii")
            yield path, sha


def _index_entries():
    raw = _run("ls-files", "--stage", "-z", "--", ".", *_PRUNED_PATHS)
    for record in raw.split(b"\0"):
        if not record:
            continue
        meta, raw_path = record.split(b"\t", 1)
        mode, sha, stage = meta.split()
        del mode
        if stage != b"0":
            continue
        yield raw_path.decode("utf-8", errors="surrogateescape"), sha.decode("ascii")


def validate_entries(entries) -> list[str]:
    errors: list[str] = []
    seen_license = False
    for path, sha in entries:
        if path == LICENSE_PATH:
            seen_license = True
        data = _run("cat-file", "-p", sha)
        errors.extend(validate_blob(path, data, sha))
    if not seen_license:
        errors.append(f"missing {LICENSE_PATH}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Enforce canonical project licensing headers.")
    parser.add_argument("--staged", action="store_true")
    parser.add_argument("--tree", default="HEAD")
    args = parser.parse_args()

    entries = _index_entries() if args.staged else _tree_entries(args.tree)
    errors = validate_entries(entries)
    if errors:
        for error in errors:
            print(f"LICENSE-MONKEY: {error}", file=sys.stderr)
        return 1
    print("LICENSE-MONKEY: canonical license and headers verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
