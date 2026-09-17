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
ARM64_HARD_REJECT = 'arm64 direct-boot kernel is neither raw Image nor EFI zboot'
HOST_RAW_CMP = 'cmp -s "$raw"'
EXT4_NORMALIZE_CALL = 'normalize_ext4 "$raw"'
EXT4_FSCK = 'sudo e2fsck -fy "$image"'
EXT4_FSCK_FATAL = 'if (( rc > 1 )); then'
BASE_REQUIRED_SNIPPETS = {
    "eager ext4 metadata initialization": 'mkfs.ext4 -q -F -E lazy_itable_init=0,lazy_journal_init=0 -L dniv-root "$raw"',
    "ext4 synchronization and repair probe": EXT4_FSCK,
    "ext4 repair status validation": EXT4_FSCK_FATAL,
    "post-unmount ext4 normalization": EXT4_NORMALIZE_CALL,
    "installed smoke script byte comparison": 'sudo cmp -s "$smoke_script_source" "$smoke_script_dest"',
    "installed smoke unit byte comparison": 'sudo cmp -s "$smoke_unit_source" "$smoke_unit_dest"',
    "systemd unit validation": 'systemd-analyze verify /etc/systemd/system/dniv-smoke.service',
    "systemd offline enable": 'systemctl --root="$mnt" enable dniv-smoke.service',
    "systemd enabled-state validation": 'systemctl --root="$mnt" is-enabled dniv-smoke.service',
    "systemd wants-link validation": 'sudo test -L "$mnt/etc/systemd/system/multi-user.target.wants/dniv-smoke.service"',
    "arm64 outer gzip decompression": 'sudo gzip -dc "$kernel" > "$boot_dir/vmlinuz"',
    "arm64 boot artifact ownership": ARM64_OWNER_FIX,
    "arm64 boot artifact nonempty check": 'test -s "$boot_dir/vmlinuz"',
    "arm64 Image magic read": ARM64_MAGIC_READ,
    "arm64 current Image recognition": 'if [[ "$arm64_magic" == 41524d64 ]]; then',
    "arm64 EFI-zboot MZ read": 'zboot_msdos=$(dd if="$boot_dir/vmlinuz" bs=1 count=2 status=none |',
    "arm64 EFI-zboot tag read": 'zboot_tag=$(dd if="$boot_dir/vmlinuz" bs=1 skip=4 count=4 status=none |',
    "arm64 EFI-zboot Linux magic read": 'zboot_linux_magic=$(dd if="$boot_dir/vmlinuz" bs=1 skip=56 count=4 status=none |',
    "arm64 EFI-zboot recognition": 'if [[ "$zboot_msdos" == 4d5a && "$zboot_tag" == 7a696d67 &&',
    "arm64 EFI-zboot compression read": 'zboot_compression=$(dd if="$boot_dir/vmlinuz" bs=1 skip=24 count=32 status=none |',
    "arm64 EFI-zboot payload offset read": 'zboot_payload_offset=$(dd if="$boot_dir/vmlinuz" bs=1 skip=8 count=4 status=none |',
    "arm64 EFI-zboot payload size read": 'zboot_payload_size=$(dd if="$boot_dir/vmlinuz" bs=1 skip=12 count=4 status=none |',
    "arm64 EFI-zboot file size read": 'zboot_file_size=$(stat -c \'%s\' "$boot_dir/vmlinuz")',
    "arm64 EFI-zboot compression validation": 'if [[ "$zboot_compression" != gzip ]]; then',
    "arm64 EFI-zboot payload bounds": 'zboot_payload_offset + zboot_payload_size > zboot_file_size',
    "arm64 EFI-zboot payload extraction": 'count="$zboot_payload_size" status=none | gzip -dc > "$zboot_raw"',
    "arm64 EFI-zboot raw Image validation": 'if [[ "$zboot_raw_magic" != 41524d64 ]]; then',
    "arm64 EFI-zboot replacement": 'mv "$zboot_raw" "$boot_dir/vmlinuz"',
    "arm64 QEMU raw fallback": ': # QEMU raw-image fallback; boot acceptance is the executable proof.',
    "qcow2 structural validation": 'qemu-img check -f qcow2 "$output"',
    "logical raw/qcow2 comparison": 'qemu-img compare -f raw -F qcow2 "$raw" "$output"',
}
DERIVED_REQUIRED_SNIPPETS = {
    "ext4 synchronization and repair probe": EXT4_FSCK,
    "ext4 repair status validation": EXT4_FSCK_FATAL,
    "post-unmount ext4 normalization": EXT4_NORMALIZE_CALL,
    "uncompressed qcow2 conversion": 'qemu-img convert -q -f raw -O qcow2 "$raw" "$output"',
    "qcow2 structural validation": 'qemu-img check -q -f qcow2 "$output"',
    "logical raw/qcow2 comparison": 'qemu-img compare -q -f raw -F qcow2 "$raw" "$output"',
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


def qemu_img_lines(text: str, subcommand: str) -> list[list[str]]:
    logical_text = text.replace(chr(92) + "\n", " ")
    commands: list[list[str]] = []
    for line in logical_text.splitlines():
        tokens = line.split()
        for index, token in enumerate(tokens[:-1]):
            if token == "qemu-img" and tokens[index + 1] == subcommand:
                commands.append(tokens[index:])
                break
    return commands


def has_compressed_qcow2_convert(text: str) -> bool:
    for tokens in qemu_img_lines(text, "convert"):
        if "-c" not in tokens or "-O" not in tokens:
            continue
        out_index = tokens.index("-O") + 1
        if out_index < len(tokens) and tokens[out_index] == "qcow2":
            return True
    return False


def has_strict_qemu_img_compare(text: str) -> bool:
    return any("-s" in tokens for tokens in qemu_img_lines(text, "compare"))


def require_snippets(label: str, text: str, snippets: dict[str, str]) -> None:
    missing = [name for name, snippet in snippets.items() if snippet not in text]
    if missing:
        raise SystemExit(
            f"image-builder gate: {label} required safeguard(s) missing: "
            + ", ".join(missing)
        )


def reject_bad_image_compare(label: str, text: str) -> None:
    if HOST_RAW_CMP in text:
        raise SystemExit(
            f"image-builder gate: {label} must compare logical image content with qemu-img, "
            "not host RAW file bytes"
        )
    if has_strict_qemu_img_compare(text):
        raise SystemExit(
            f"image-builder gate: {label} qemu-img compare must not use strict allocation mode"
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
    if ARM64_HARD_REJECT in base_text:
        raise SystemExit(
            "image-builder gate: arm64 builder must preserve QEMU raw-image fallback "
            "instead of requiring ARM64 or EFI-zboot magic"
        )
    if base_text.index(ARM64_OWNER_FIX) > base_text.index(ARM64_MAGIC_READ):
        raise SystemExit(
            "image-builder gate: arm64 direct-boot kernel must become runner-readable "
            "before the non-root format probe"
        )
    if has_compressed_qcow2_convert(base_text):
        raise SystemExit(
            "image-builder gate: acceptance base image conversion must not use qcow2 compression"
        )
    reject_bad_image_compare("base image", base_text)

    for path, text in derived.items():
        require_snippets(path, text, DERIVED_REQUIRED_SNIPPETS)
        if has_compressed_qcow2_convert(text):
            raise SystemExit(
                f"image-builder gate: derived acceptance image conversion in {path} "
                "must not use qcow2 compression"
            )
        reject_bad_image_compare(path, text)

    print(
        "image-builder gate: source=" + source_label
        + " initrd, stable ext4 images, arm64 QEMU-compatible direct boot and logical image-integrity safeguards verified"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
