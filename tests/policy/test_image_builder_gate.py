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

"""Gate direct-boot image/kernel construction and critical guest-byte checks."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BUILDER = "image/ubuntu-base/build-image.sh"
INSTALL_PREFIX = 'apt-get --snapshot "$UBUNTU_APT_SNAPSHOT" install -y --no-install-recommends'
INITRD_CHECK = 'test -s "/boot/initrd.img-$krel"'
REQUIRED_SNIPPETS = {
    "installed smoke script byte comparison": 'sudo cmp -s "$smoke_script_source" "$smoke_script_dest"',
    "installed smoke unit byte comparison": 'sudo cmp -s "$smoke_unit_source" "$smoke_unit_dest"',
    "systemd unit validation": 'systemd-analyze verify /etc/systemd/system/dniv-smoke.service',
    "arm64 gzip decompression": 'sudo gzip -dc "$kernel" > "$boot_dir/vmlinuz"',
    "arm64 Image magic validation": 'if [[ "$arm64_magic" != 41524d64 ]]; then',
    "qcow2 structural validation": 'qemu-img check -f qcow2 "$output"',
    "qcow2-to-raw verification round trip": 'qemu-img convert -f qcow2 -O raw "$output" "$verify_raw"',
    "post-conversion smoke script checksum": 'verify_script_sha=$(sudo sha256sum "$verify_mnt/usr/local/sbin/dniv-smoke"',
    "post-conversion smoke unit checksum": 'verify_unit_sha=$(sudo sha256sum "$verify_mnt/etc/systemd/system/dniv-smoke.service"',
}
FORBIDDEN_COMPRESSED_CONVERT = 'qemu-img convert -f raw -O qcow2 -c '


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
    missing_safeguards = [name for name, snippet in REQUIRED_SNIPPETS.items() if snippet not in text]
    if missing_safeguards:
        raise SystemExit(
            "image-builder gate: required safeguard(s) missing: "
            + ", ".join(missing_safeguards)
        )
    if FORBIDDEN_COMPRESSED_CONVERT in text:
        raise SystemExit(
            "image-builder gate: acceptance base image conversion must not use qcow2 compression"
        )
    print(
        "image-builder gate: source=" + source_label
        + " initrd, arm64 direct boot and image-integrity safeguards verified"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
