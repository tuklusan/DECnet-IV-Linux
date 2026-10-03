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
    for marker in ("Build source archive twice", "cmp \"$a\" \"$b\"", "Build install and uninstall extracted source", "validate-arm64:", "actions/download-artifact@"):
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
    for marker in ("SOURCE-METADATA", "'*.qcow2'", "'*.raw'", "'*.img'", "'*.iso'", "'*.ko'", "git -C \"$root\" archive"):
        if marker not in builder:
            raise SystemExit(f"source-release gate: archive safeguard missing: {marker}")
    dispatcher = read_text(".github/workflows/repository-policy.yml")
    if "SOURCE_RELEASE source-release.yml" not in dispatcher or "RELEASE_IMAGE release-image.yml" in dispatcher:
        raise SystemExit("source-release gate: acceptance dispatcher not synchronized")
    attributes = read_text(".gitattributes")
    if "filter=lfs" in attributes or "qcow2" in attributes.lower():
        raise SystemExit("source-release gate: repository still advertises disk-image delivery")
    for path in ("README.md", "docs/ROADMAP.md", "docs/ARCHITECTURE.md", "docs/PRE_PRODUCTION_TEST.md"):
        value = read_text(path)
        for stale in ("self-booting QCOW2/RAW images", "Release images remain QCOW2-first", "exact release image"):
            if stale in value:
                raise SystemExit(f"source-release gate: stale release-image contract in {path}: {stale}")
    print("source-release gate passed")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
