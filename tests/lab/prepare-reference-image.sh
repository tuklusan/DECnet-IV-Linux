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

if [[ $# -ne 2 ]]; then
    echo "usage: $0 FOUNDATION-QCOW2 OUTPUT-QCOW2" >&2
    exit 2
fi
foundation=$1
output=$2
[[ -r "$foundation" ]] || { echo "prepare-reference-image: missing $foundation" >&2; exit 2; }

script_dir=$(cd "$(dirname "$0")" && pwd)
repo_root=$(cd "$script_dir/../.." && pwd)
source_commit=$(git -C "$repo_root" rev-parse --verify 'HEAD^{commit}')
[[ "$source_commit" =~ ^[0-9a-f]{40}$ ]] || {
    echo "prepare-reference-image: invalid source commit" >&2
    exit 1
}

work=$(mktemp -d)
raw="$work/reference.raw"
mnt="$work/root"
mkdir -p "$mnt" "$(dirname "$output")"
mounted=0
cleanup() {
    set +e
    if (( mounted )); then
        sudo umount "$mnt" 2>/dev/null || true
    fi
    rm -rf "$work"
}
trap cleanup EXIT INT TERM

normalize_ext4() {
    local image=$1 rc
    sync
    set +e
    sudo e2fsck -fy "$image"
    rc=$?
    set -e
    if (( rc > 1 )); then
        echo "prepare-reference-image: ext4 normalization failed with status $rc" >&2
        return "$rc"
    fi
}

qemu-img convert -q -f qcow2 -O raw "$foundation" "$raw"
sudo mount -o loop "$raw" "$mnt"
mounted=1
sudo mkdir -p "$mnt/usr/local/sbin" "$mnt/etc/systemd/system/multi-user.target.wants"
sudo install -m 0755 "$repo_root/tests/lab/dniv-reference-peer.sh" \
    "$mnt/usr/local/sbin/dniv-reference-peer"
sudo cc -O2 -std=c11 -Wall -Wextra -Werror \
    -o "$mnt/usr/local/sbin/dnraw" "$repo_root/tests/lab/dnraw.c"
sudo tee "$mnt/etc/systemd/system/dniv-reference-peer.service" >/dev/null <<'EOF_SERVICE'
[Unit]
Description=Independent DECnet reference peer
After=systemd-udev-settle.service

[Service]
Type=simple
ExecStart=/usr/local/sbin/dniv-reference-peer
StandardOutput=journal+console
StandardError=journal+console
Restart=no

[Install]
WantedBy=multi-user.target
EOF_SERVICE
sudo ln -sf ../dniv-reference-peer.service \
    "$mnt/etc/systemd/system/multi-user.target.wants/dniv-reference-peer.service"
printf '%s\n' "$source_commit" | sudo tee "$mnt/etc/dniv-reference-harness-sha" >/dev/null
sudo test -x "$mnt/usr/local/sbin/dniv-reference-peer"
sudo test -x "$mnt/usr/local/sbin/dnraw"
sudo test "$(sudo cat "$mnt/etc/dniv-reference-harness-sha")" = "$source_commit"

sudo umount "$mnt"
mounted=0
normalize_ext4 "$raw"

qemu-img convert -q -f raw -O qcow2 "$raw" "$output"
qemu-img check -q -f qcow2 "$output"
qemu-img compare -q -f raw -F qcow2 "$raw" "$output"
echo "prepare-reference-image: created $output with harness from exact source $source_commit"
