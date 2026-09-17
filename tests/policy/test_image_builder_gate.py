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

"""Gate release images, persistent foundations and disposable candidate images."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RELEASE_BUILDER = "image/ubuntu-base/build-image.sh"
FOUNDATION_BUILDER = "image/ubuntu-base/build-foundation.sh"
CANDIDATE_BUILDER = "tests/lab/prepare-candidate-image.sh"
REFERENCE_BUILDER = "tests/lab/prepare-reference-image.sh"
INSTALL_PREFIX = 'apt-get --snapshot "$UBUNTU_APT_SNAPSHOT" install -y --no-install-recommends'
INITRD_CHECK = 'test -s "/boot/initrd.img-$krel"'
HOST_RAW_CMP = 'cmp -s "$raw"'
EXT4_NORMALIZE_CALL = 'normalize_ext4 "$raw"'
EXT4_FSCK = 'sudo e2fsck -fy "$image"'
EXT4_FSCK_FATAL = 'if (( rc > 1 )); then'

COMMON_IMAGE_REQUIRED = {
    "ext4 synchronization and repair probe": EXT4_FSCK,
    "ext4 repair status validation": EXT4_FSCK_FATAL,
    "post-unmount ext4 normalization": EXT4_NORMALIZE_CALL,
}
DERIVED_REQUIRED = {
    **COMMON_IMAGE_REQUIRED,
    "uncompressed qcow2 conversion": 'qemu-img convert -q -f raw -O qcow2 "$raw" "$output"',
    "qcow2 structural validation": 'qemu-img check -q -f qcow2 "$output"',
    "logical raw/qcow2 comparison": 'qemu-img compare -q -f raw -F qcow2 "$raw" "$output"',
}
FOUNDATION_REQUIRED = {
    **COMMON_IMAGE_REQUIRED,
    "eager ext4 metadata initialization": 'mkfs.ext4 -q -F -E lazy_itable_init=0,lazy_journal_init=0 -L dniv-root "$raw"',
    "generated initrd validation": INITRD_CHECK,
    "arm64 outer gzip decompression": 'sudo gzip -dc "$kernel" > "$boot_dir/vmlinuz"',
    "arm64 Image magic probe": 'arm64_magic=$(dd if="$boot_dir/vmlinuz" bs=1 skip=56 count=4 status=none |',
    "arm64 EFI-zboot recognition": 'if [[ "$zboot_msdos" == 4d5a && "$zboot_tag" == 7a696d67 &&',
    "arm64 QEMU raw fallback": ': # QEMU raw-image fallback; boot acceptance is the executable proof.',
    "qcow2 structural validation": 'qemu-img check -f qcow2 "$output"',
    "logical raw/qcow2 comparison": 'qemu-img compare -f raw -F qcow2 "$raw" "$output"',
    "candidate source purge": 'sudo rm -rf "$mnt/usr/src/decnet-iv-linux"',
}
CANDIDATE_REQUIRED = {
    **DERIVED_REQUIRED,
    "exact candidate commit": "source_commit=$(git -C \"$repo_root\" rev-parse --verify 'HEAD^{commit}')",
    "exact candidate archive": 'git -C "$repo_root" archive --format=tar "$source_commit" |',
    "candidate provenance marker": 'sudo tee "$mnt/usr/src/decnet-iv-linux/.source-commit"',
    "kernel module build": 'make -C /usr/src/decnet-iv-linux/kernel/decnet KDIR="/lib/modules/$krel/build" clean all',
    "dnctl build": 'make -C /usr/src/decnet-iv-linux/userspace/dnctl clean all',
    "dnraw build": '-o /usr/local/sbin/dnraw /usr/src/decnet-iv-linux/tests/lab/dnraw.c',
    "two-node smoke install": 'dniv-smoke.sh',
    "interop smoke install": 'dniv-interop-smoke.sh',
    "candidate SHA marker": '/etc/dniv-candidate-sha',
}
REFERENCE_REQUIRED = {
    **DERIVED_REQUIRED,
    "exact harness commit": "source_commit=$(git -C \"$repo_root\" rev-parse --verify 'HEAD^{commit}')",
    "reference peer install": 'dniv-reference-peer.sh',
    "reference dnraw build": '-o "$mnt/usr/local/sbin/dnraw" "$repo_root/tests/lab/dnraw.c"',
    "harness SHA marker": '/etc/dniv-reference-harness-sha',
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
        raise SystemExit(f"image-builder gate: {label} required safeguard(s) missing: " + ", ".join(missing))


def reject_bad_image_compare(label: str, text: str) -> None:
    if HOST_RAW_CMP in text:
        raise SystemExit(f"image-builder gate: {label} must compare logical image content with qemu-img")
    if has_strict_qemu_img_compare(text):
        raise SystemExit(f"image-builder gate: {label} qemu-img compare must not use strict allocation mode")
    if has_compressed_qcow2_convert(text):
        raise SystemExit(f"image-builder gate: {label} qcow2 conversion must remain uncompressed")


def main() -> int:
    parser = argparse.ArgumentParser()
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--staged", action="store_true")
    source.add_argument("--tree")
    args = parser.parse_args()

    try:
        release, source_label = read_path(RELEASE_BUILDER, args.staged, args.tree)
        foundation = read_path(FOUNDATION_BUILDER, args.staged, args.tree)[0]
        candidate = read_path(CANDIDATE_BUILDER, args.staged, args.tree)[0]
        reference = read_path(REFERENCE_BUILDER, args.staged, args.tree)[0]
    except (OSError, subprocess.CalledProcessError) as exc:
        raise SystemExit(f"image-builder gate: cannot read exact source: {exc}") from exc

    release_packages = install_tokens(release)
    release_required = {"initramfs-tools", "linux-image-virtual-hwe-26.04", "linux-headers-virtual-hwe-26.04"}
    missing = sorted(release_required - release_packages)
    if missing:
        raise SystemExit("image-builder gate: release direct-boot package(s) missing: " + ", ".join(missing))
    if INITRD_CHECK not in release:
        raise SystemExit("image-builder gate: release image does not validate generated initrd")
    for marker in (
        'sudo cmp -s "$smoke_script_source" "$smoke_script_dest"',
        'systemd-analyze verify /etc/systemd/system/dniv-smoke.service',
        'qemu-img check -f qcow2 "$output"',
        'qemu-img compare -f raw -F qcow2 "$raw" "$output"',
    ):
        if marker not in release:
            raise SystemExit(f"image-builder gate: release image safeguard missing: {marker}")
    reject_bad_image_compare("release image", release)

    foundation_packages = install_tokens(foundation)
    foundation_required_packages = {
        "build-essential", "initramfs-tools", "linux-image-virtual-hwe-26.04",
        "linux-headers-virtual-hwe-26.04", "python3", "libpcap0.8t64",
    }
    missing = sorted(foundation_required_packages - foundation_packages)
    if missing:
        raise SystemExit("image-builder gate: foundation package(s) missing: " + ", ".join(missing))
    require_snippets("architecture foundation", foundation, FOUNDATION_REQUIRED)
    for forbidden in (
        "source_commit=", 'git -C "$repo_root" archive',
        "make -C /usr/src/decnet-iv-linux", "dniv-smoke.service",
    ):
        if forbidden in foundation:
            raise SystemExit(f"image-builder gate: source-dependent content leaked into foundation: {forbidden}")
    reject_bad_image_compare("architecture foundation", foundation)

    require_snippets("disposable candidate", candidate, CANDIDATE_REQUIRED)
    if "apt-get" in candidate:
        raise SystemExit("image-builder gate: disposable candidate must not repeat package installation")
    reject_bad_image_compare("disposable candidate", candidate)

    require_snippets("disposable reference image", reference, REFERENCE_REQUIRED)
    if "apt-get" in reference:
        raise SystemExit("image-builder gate: disposable reference image must not repeat package installation")
    reject_bad_image_compare("disposable reference image", reference)

    print(
        "image-builder gate: source=" + source_label
        + " release image, source-independent architecture foundation, and exact-candidate disposable layers verified"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
