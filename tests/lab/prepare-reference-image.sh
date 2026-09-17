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
    echo "usage: $0 BASE-QCOW2 OUTPUT-QCOW2" >&2
    exit 2
fi
base=$1
output=$2
[[ -r "$base" ]] || { echo "prepare-reference-image: missing $base" >&2; exit 2; }

work=$(mktemp -d)
raw="$work/reference.raw"
mnt="$work/root"
mkdir -p "$mnt" "$(dirname "$output")"
mounted=0
chroot_mounted=0
cleanup() {
    set +e
    if (( chroot_mounted )); then
        sudo umount -R "$mnt/dev" 2>/dev/null || true
        sudo umount "$mnt/sys" 2>/dev/null || true
        sudo umount "$mnt/proc" 2>/dev/null || true
    fi
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

qemu-img convert -q -f qcow2 -O raw "$base" "$raw"
sudo mount -o loop "$raw" "$mnt"
mounted=1
archived_source="$mnt/usr/src/decnet-iv-linux"
test -r "$archived_source/.source-commit"
source_commit=$(sudo cat "$archived_source/.source-commit")
[[ "$source_commit" =~ ^[0-9a-f]{40}$ ]] || {
    echo "prepare-reference-image: invalid archived source commit" >&2
    exit 1
}
test -r "$archived_source/tests/lab/dniv-reference-peer.sh"
test -r "$archived_source/image/ubuntu-base/images.env"
# shellcheck disable=SC1090
. "$archived_source/image/ubuntu-base/images.env"
snapshot=${UBUNTU_APT_SNAPSHOT:?archived images.env must pin UBUNTU_APT_SNAPSHOT}
sudo install -m 0755 "$archived_source/tests/lab/dniv-reference-peer.sh" \
    "$mnt/usr/local/sbin/dniv-reference-peer"
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

sudo mount -t proc proc "$mnt/proc"
sudo mount -t sysfs sysfs "$mnt/sys"
sudo mount --rbind /dev "$mnt/dev"
sudo mount --make-rslave "$mnt/dev"
chroot_mounted=1
sudo chroot "$mnt" /usr/bin/env UBUNTU_APT_SNAPSHOT="$snapshot" /bin/bash -euxc '
export DEBIAN_FRONTEND=noninteractive
apt-get --snapshot "$UBUNTU_APT_SNAPSHOT" update
apt-get --snapshot "$UBUNTU_APT_SNAPSHOT" install -y --no-install-recommends \
    python3 libpcap0.8t64
apt-get clean
rm -rf /var/lib/apt/lists/*
'
sudo umount -R "$mnt/dev"
sudo umount "$mnt/sys"
sudo umount "$mnt/proc"
chroot_mounted=0
sudo umount "$mnt"
mounted=0
normalize_ext4 "$raw"

# Acceptance correctness wins over file-size optimization. Keep the derived
# image uncompressed, validate its qcow2 structure, then compare guest-visible
# logical content directly across raw and qcow2. Sparse zero allocation is an
# implementation detail, not a content difference.
qemu-img convert -q -f raw -O qcow2 "$raw" "$output"
qemu-img check -q -f qcow2 "$output"
qemu-img compare -q -f raw -F qcow2 "$raw" "$output"
echo "prepare-reference-image: created $output from archived source $source_commit"
