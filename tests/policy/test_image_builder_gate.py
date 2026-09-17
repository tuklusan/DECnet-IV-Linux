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

"""Gate direct-boot and acceptance-image integrity safeguards."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE_BUILDER = "image/ubuntu-base/build-image.sh"
DERIVED_BUILDERS = (
    "tests/lab/prepare-interop-candidate.sh",
    "tests/lab/prepare-reference-image.sh",
)
INSTALL_PREFIX = 'apt-get --snapshot "$UBUNTU_APT_SNAPSHOT" install -y --no-install-recommends'
INITRD_CHECK = 'test -s "/boot/initrd.img-$krel"'
ARM64_OWNER_FIX = 'sudo chown "$(id -u):$(id -g)" "$boot_dir/vmlinuz"'
ARM64_MAGIC_READ = 'arm64_magic=$(dd if="$boot_dir/vmlinuz" bs=1 skip=56 count=4 status=none |'
BASE_REQUIRED_SNIPPETS = {
    "installed smoke script byte comparison": 'sudo cmp -s "$smoke_script_source" "$smoke_script_dest"',
    "installed smoke unit byte comparison": 'sudo cmp -s "$smoke_unit_source" "$smoke_unit_dest"',
    "systemd unit validation": 'systemd-analyze verify /etc/systemd/system/dniv-smoke.service',
    "arm64 gzip decompression": 'sudo gzip -dc "$kernel" > "$boot_dir/vmlinuz"',
    "arm64 boot artifact ownership": ARM64_OWNER_FIX,
    "arm64 Image magic read": ARM64_MAGIC_READ,
    "arm64 Image magic validation": 'if [[ "$arm64_magic" != 41524d64 ]]; then',
    "qcow2 structural validation": 'qemu-img check -f qcow2 "$output"',
    "qcow2-to-raw verification round trip": 'qemu-img convert -f qcow2 -O raw "$output" "$verify_raw"',
    "full RAW content comparison": 'cmp -s "$raw" "$verify_raw"',
}
DERIVED_REQUIRED_SNIPPETS = {
    "uncompressed qcow2 conversion": 'qemu-img convert -q -f raw -O qcow2 "$raw" "$output"',
    "qcow2 structural validation": 'qemu-img check -q -f qcow2 "$output"',
    "qcow2-to-raw verification round trip": 'qemu-img convert -q -f qcow2 -O raw "$output" "$verify_raw"',
    "full RAW content comparison": 'cmp -s "$raw" "$verify_raw"',
    "archived source provenance read": 'source_commit=$(sudo cat "$archived_source/.source-commit")',
    "archived source provenance validation": '[[ "$source_commit" =~ ^[0-9a-f]{40}$ ]] || {',
}


def git(*args: str) -> str:
    return subprocess.check_output(("git", *args), text=True).strip()


def read_path(path: str, staged: bool, tree: str | None) -> tuple[str, str]:
    if staged:
        return subprocess.check_output(("git", "show", ":" + path), text=True), "staged index"
    if tree:
        commit = git("rev-parse", "--verify", tree + "^{commit}")
        return subprocess.check_output(("git", "show", f"{commit}:{path}"), text=True), commit
    return (ROOT / path).read_text(encoding="utf-8"), "working tree"


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


def has_compressed_qcow2_convert(text: str) -> bool:
    logical_text = text.replace(chr(92) + "\n", " ")
    for line in logical_text.splitlines():
        tokens = line.split()
        if len(tokens) < 2 or tokens[:2] != ["qemu-img", "convert"]:
            continue
        if "-c" in tokens and "-O" in tokens:
            out_index = tokens.index("-O") + 1
            if out_index < len(tokens) and tokens[out_index] == "qcow2":
                return True
    return False


def require_snippets(label: str, text: str, snippets: dict[str, str]) -> None:
    missing = [name for name, snippet in snippets.items() if snippet not in text]
    if missing:
        raise SystemExit(
            f"image-builder gate: {label} required safeguard(s) missing: "
            + ", ".join(missing)
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--staged", action="store_true")
    source.add_argument("--tree")
    args = parser.parse_args()

    try:
        base_text, source_label = read_path(BASE_BUILDER, args.staged, args.tree)
        derived = {
            path: read_path(path, args.staged, args.tree)[0]
            for path in DERIVED_BUILDERS
        }
    except (OSError, subprocess.CalledProcessError) as exc:
        raise SystemExit(f"image-builder gate: cannot read exact source: {exc}") from exc

    packages = install_tokens(base_text)
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
    if INITRD_CHECK not in base_text:
        raise SystemExit(
            "image-builder gate: generated initrd is not checked before build cleanup"
        )
    require_snippets("base image", base_text, BASE_REQUIRED_SNIPPETS)
    if base_text.index(ARM64_OWNER_FIX) > base_text.index(ARM64_MAGIC_READ):
        raise SystemExit(
            "image-builder gate: arm64 direct-boot kernel must become runner-readable "
            "before the non-root Image-header probe"
        )
    if has_compressed_qcow2_convert(base_text):
        raise SystemExit(
            "image-builder gate: acceptance base image conversion must not use qcow2 compression"
        )

    for path, text in derived.items():
        require_snippets(path, text, DERIVED_REQUIRED_SNIPPETS)
        if has_compressed_qcow2_convert(text):
            raise SystemExit(
                f"image-builder gate: derived acceptance image conversion in {path} "
                "must not use qcow2 compression"
            )

    print(
        "image-builder gate: source=" + source_label
        + " initrd, arm64 direct boot and base/derived image-integrity safeguards verified"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
