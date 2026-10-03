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

"""Lock the portable source-release contract."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

def read_text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")

def main() -> int:
    required = (
        "build.sh", "install.sh", "uninstall.sh", "INSTALL.md",
        "docs/DELIVERY.md", "docs/FEATURES.md", "docs/COMPONENTS.md",
        "tools/build-source-release.sh", ".github/workflows/source-release.yml",
    )
    for path in required:
        if not (ROOT / path).is_file():
            raise SystemExit(f"source-release gate: missing {path}")
    if (ROOT / ".github/workflows/release-image.yml").exists():
        raise SystemExit("source-release gate: obsolete release-image workflow remains")
    workflow = read_text(".github/workflows/source-release.yml")
    for marker in (
        "Build source archive twice",
        "cmp \"$a\" \"$b\"",
        'build-source-release.sh" relative',
        "Build install and uninstall extracted source",
        "missing-artifact negative unexpectedly succeeded",
        "unmanaged-target negative unexpectedly succeeded",
        "validate-arm64:",
        "  portability:",
        "debian13",
        "fedora42",
        "actions/download-artifact@",
    ):
        if marker not in workflow:
            raise SystemExit(f"source-release gate: workflow safeguard missing: {marker}")
    for forbidden in ("qemu-system", ".qcow2", "dniv.raw", "Release Image"):
        if forbidden in workflow:
            raise SystemExit(f"source-release gate: disk-image release behavior remains: {forbidden}")
    delivery = read_text("docs/DELIVERY.md")
    for marker in ("source tarball", "Disk images are not release artifacts", "x86_64", "aarch64", "Linux 6.8", "Forward compatibility"):
        if marker not in delivery:
            raise SystemExit(f"source-release gate: delivery contract missing: {marker}")
    components = read_text("docs/COMPONENTS.md")
    for directory in sorted(path.name for path in (ROOT / "userspace").iterdir() if path.is_dir()):
        if f"userspace/{directory}" not in components:
            raise SystemExit(f"source-release gate: undocumented userspace component: {directory}")
    builder = read_text("tools/build-source-release.sh")
    for marker in (
        "SOURCE-METADATA",
        "'*.qcow2'", "'*.raw'", "'*.img'", "'*.iso'", "'*.ko'",
        "'*.a'", "'*.so'", "'*.so.*'",
        "generated_paths=(",
        "output_dir=$(cd \"$output_dir\" && pwd -P)",
        "git -C \"$root\" archive",
    ):
        if marker not in builder:
            raise SystemExit(f"source-release gate: archive safeguard missing: {marker}")

    install = read_text("install.sh")
    for marker in (
        "refusing unmanaged existing target",
        'record "$target"',
        'sort -u "$manifest"',
        "unsafe existing manifest",
        "refusing symlink at regular-file target",
        "refusing non-symlink at link target",
        "DESTDIR must be empty or absolute",
    ):
        if marker not in install:
            raise SystemExit(f"source-release gate: installer safety safeguard missing: {marker}")

    uninstall = read_text("uninstall.sh")
    for marker in ("safe install manifest not found", "DESTDIR must be empty or absolute"):
        if marker not in uninstall:
            raise SystemExit(f"source-release gate: uninstaller safety safeguard missing: {marker}")

    build = read_text("build.sh")
    for marker in (
        "include/config/kernel.release",
        "kernelrelease",
        "does not match KDIR release",
        "Clang 16 or later required",
        "GCC-compatible compiler 12 or later required",
        "target kernel build tree was configured with GCC",
        "target kernel build tree was configured with Clang",
        'make clean KDIR="$kdir"',
    ):
        if marker not in build:
            raise SystemExit(f"source-release gate: end-user build safeguard missing: {marker}")

    portability = read_text(".github/workflows/portability.yml")
    for marker in (
        'DNIV_EXPECTED_SHA="$GITHUB_SHA"',
        'sha256sum -c "$(basename "$archive").sha256"',
        'grep -Fqx "source_sha=$DNIV_EXPECTED_SHA" SOURCE-METADATA',
    ):
        if marker not in portability:
            raise SystemExit(f"source-release gate: portability provenance safeguard missing: {marker}")
    if "SOURCE-METADATA 2>/dev/null || true" in portability:
        raise SystemExit("source-release gate: portability provenance check is fail-open")
    for marker in (
        "needs: package-amd64",
        "source-release-portability-${{ matrix.arch }}",
        'source_dir="$RUNNER_TEMP/release"',
        'sha256sum -c "$(basename "$archive").sha256"',
        'grep -Fqx "source_sha=$DNIV_EXPECTED_SHA" SOURCE-METADATA',
        "run_case debian13 debian:13 gcc",
        'if [[ "$DNIV_COMPILER" == clang ]]',
        'kbase=$(make -s -C "$KDIR" kernelversion)',
        "run_case fedora42 fedora:42 clang",
    ):
        if marker not in workflow:
            raise SystemExit(f"source-release gate: exact-artifact portability safeguard missing: {marker}")
    dispatcher = read_text(".github/workflows/repository-policy.yml")
    if "SOURCE_RELEASE source-release.yml" not in dispatcher or "RELEASE_IMAGE release-image.yml" in dispatcher:
        raise SystemExit("source-release gate: acceptance dispatcher not synchronized")
    if "dispatch_and_record PORTABILITY portability.yml" in dispatcher:
        raise SystemExit("source-release gate: full acceptance duplicates portability outside exact release artifact")
    attributes = read_text(".gitattributes")
    if "filter=lfs" in attributes or "qcow2" in attributes.lower():
        raise SystemExit("source-release gate: repository still advertises disk-image delivery")

    install_doc = read_text("INSTALL.md")
    for marker in ("Secure Boot", "MODULE_ROOT", "modprobe -r decnet_iv", "python3 -c 'import decnet'"):
        if marker not in install_doc:
            raise SystemExit(f"source-release gate: installation manual missing: {marker}")

    handover = read_text("docs/HANDOVER.md")
    if "four exact-SHA acceptance depths" not in handover:
        raise SystemExit("source-release gate: handover acceptance-depth model is stale")
    for path in ("README.md", "docs/ROADMAP.md", "docs/ARCHITECTURE.md", "docs/PRE_PRODUCTION_TEST.md"):
        value = read_text(path)
        for stale in ("self-booting QCOW2/RAW images", "Release images remain QCOW2-first", "exact release image"):
            if stale in value:
                raise SystemExit(f"source-release gate: stale release-image contract in {path}: {stale}")
    print("source-release gate passed")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
