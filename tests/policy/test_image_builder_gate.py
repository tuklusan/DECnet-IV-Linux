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

"""Gate direct-boot image kernel/initrd construction from an exact source."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BUILDER = "image/ubuntu-base/build-image.sh"
INSTALL_PREFIX = 'apt-get --snapshot "$UBUNTU_APT_SNAPSHOT" install -y --no-install-recommends'
INITRD_CHECK = 'test -s "/boot/initrd.img-$krel"'


def git(*args: str) -> str:
    return subprocess.check_output(("git", *args), text=True).strip()


def read_builder(staged: bool, tree: str | None) -> tuple[str, str]:
    if staged:
        return subprocess.check_output(("git", "show", ":" + BUILDER), text=True), "staged index"
    if tree:
        commit = git("rev-parse", "--verify", tree + "^{commit}")
        return subprocess.check_output(("git", "show", f"{commit}:{BUILDER}"), text=True), commit
    return (ROOT / BUILDER).read_text(encoding="utf-8"), "working tree"


def install_tokens(text: str) -> set[str]:
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if not line.startswith(INSTALL_PREFIX):
            continue
        block = [line]
        while block[-1].rstrip().endswith("\\"):
            index += 1
            if index >= len(lines):
                raise SystemExit("image-builder gate: unterminated package install block")
            block.append(lines[index])
        return set(" ".join(block).replace("\\", " ").split())
    raise SystemExit("image-builder gate: pinned package install block not found")


def main() -> int:
    parser = argparse.ArgumentParser()
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--staged", action="store_true")
    source.add_argument("--tree")
    args = parser.parse_args()

    try:
        text, source_label = read_builder(args.staged, args.tree)
    except (OSError, subprocess.CalledProcessError) as exc:
        raise SystemExit(f"image-builder gate: cannot read exact source: {exc}") from exc

    packages = install_tokens(text)
    required = {
        "initramfs-tools",
        "linux-image-virtual-hwe-26.04",
        "linux-headers-virtual-hwe-26.04",
    }
    missing = sorted(required - packages)
    if missing:
        raise SystemExit(
            "image-builder gate: explicit direct-boot package(s) missing: "
            + ", ".join(missing)
        )
    if INITRD_CHECK not in text:
        raise SystemExit(
            "image-builder gate: generated initrd is not checked before build cleanup"
        )
    print(
        "image-builder gate: source=" + source_label
        + " explicit initramfs generation safeguards verified"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
