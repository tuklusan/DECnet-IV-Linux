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

"""Regression checks for direct-boot image kernel/initrd construction."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BUILDER = ROOT / "image" / "ubuntu-base" / "build-image.sh"
INSTALL_PREFIX = 'apt-get --snapshot "$UBUNTU_APT_SNAPSHOT" install -y --no-install-recommends'
INITRD_CHECK = 'test -s "/boot/initrd.img-$krel"'


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
    text = BUILDER.read_text(encoding="utf-8")
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
    print("image-builder gate: explicit initramfs generation safeguards verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
