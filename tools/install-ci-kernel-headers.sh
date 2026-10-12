#!/usr/bin/env bash
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

set -euo pipefail

# A runner can see a newer linux-headers-generic meta package before its
# versioned dependency is published on the matching Ubuntu architecture.
# Do not skip the kernel build: use the newest actually installable complete
# generic header package or fail closed if no such build tree can be installed.
if sudo apt-get -o Acquire::Retries=3 install -y linux-headers-generic; then
    exit 0
fi

echo "ci-kernel-headers: generic meta package unavailable; probing installable matching headers" >&2
mapfile -t candidates < <(
    apt-cache pkgnames |
        grep -E '^linux-headers-[0-9]+\.[0-9]+\.[0-9]+-[0-9]+-generic$' |
        sort -Vr
)
for package in "${candidates[@]}"; do
    if apt-get -s -o Acquire::Retries=3 install "$package" >/dev/null 2>&1; then
        echo "ci-kernel-headers: installing $package" >&2
        sudo apt-get -o Acquire::Retries=3 install -y "$package"
        exit 0
    fi
done
echo "ci-kernel-headers: no complete installable generic kernel headers; refusing a false-green build" >&2
exit 2
