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

if [[ $# -ne 4 ]]; then
    echo "usage: $0 ARCH BASE-TARBALL OUTPUT-QCOW2 BOOT-DIR" >&2
    exit 2
fi

arch=$1
base_tar=$2
output=$3
boot_dir=$4
case "$arch" in
    amd64|arm64) ;;
    *) echo "build-foundation: unsupported architecture: $arch" >&2; exit 2 ;;
esac

script_dir=$(cd "$(dirname "$0")" && pwd)
arm64_normalizer="$script_dir/normalize-arm64-kernel.sh"
arm64_normalizer_sha256=f38f5dd54fdb922ca72404ee054827bacb4037f97df472728445efff596d656d
test -x "$arm64_normalizer"
echo "$arm64_normalizer_sha256  $arm64_normalizer" | sha256sum -c - >/dev/null
# shellcheck disable=SC1091
. "$script_dir/images.env"
snapshot=${UBUNTU_APT_SNAPSHOT:?images.env must pin UBUNTU_APT_SNAPSHOT}
disk_bytes=${DNIV_DISK_BYTES:-4294967296}
if [[ ! "$disk_bytes" =~ ^[0-9]+$ ]] || (( disk_bytes < 4294967296 )); then
    echo "build-foundation: DNIV_DISK_BYTES must be an integer >= 4294967296" >&2
    exit 2
fi
if [[ ! -f "$base_tar" ]]; then
    echo "build-foundation: base tarball not found: $base_tar" >&2
    exit 2
fi

work=$(mktemp -d)
raw="$work/root.raw"
mnt="$work/root"
mkdir -p "$mnt" "$boot_dir" "$(dirname "$output")"
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
        echo "build-foundation: ext4 normalization failed with status $rc" >&2
        return "$rc"
    fi
}

truncate -s "$disk_bytes" "$raw"
mkfs.ext4 -q -F -E lazy_itable_init=0,lazy_journal_init=0 -L dniv-root "$raw"
sudo mount -o loop "$raw" "$mnt"
mounted=1
sudo tar --numeric-owner --xattrs --acls -xpf "$base_tar" -C "$mnt"

sudo rm -f "$mnt/etc/resolv.conf"
sudo cp -L /etc/resolv.conf "$mnt/etc/resolv.conf"
printf 'LABEL=dniv-root / ext4 defaults 0 1\n' | sudo tee "$mnt/etc/fstab" >/dev/null
printf 'dniv-foundation\n' | sudo tee "$mnt/etc/hostname" >/dev/null

sudo mount -t proc proc "$mnt/proc"
sudo mount -t sysfs sysfs "$mnt/sys"
sudo mount --rbind /dev "$mnt/dev"
sudo mount --make-rslave "$mnt/dev"
chroot_mounted=1

sudo tee "$mnt/usr/sbin/policy-rc.d" >/dev/null <<'EOF_POLICY'
#!/bin/sh
exit 101
EOF_POLICY
sudo chmod 0755 "$mnt/usr/sbin/policy-rc.d"

sudo chroot "$mnt" /usr/bin/env UBUNTU_APT_SNAPSHOT="$snapshot" /bin/bash -euxc '
export DEBIAN_FRONTEND=noninteractive
apt-get -o Acquire::https::Verify-Peer=false --snapshot "$UBUNTU_APT_SNAPSHOT" update
apt-get -o Acquire::https::Verify-Peer=false --snapshot "$UBUNTU_APT_SNAPSHOT" install -y --no-install-recommends ca-certificates
update-ca-certificates --fresh
apt-get --snapshot "$UBUNTU_APT_SNAPSHOT" update
apt-get --snapshot "$UBUNTU_APT_SNAPSHOT" install -y --no-install-recommends \
    systemd-sysv kmod iproute2 build-essential initramfs-tools \
    linux-image-virtual-hwe-26.04 linux-headers-virtual-hwe-26.04 \
    python3 libpcap0.8t64 git
krel=$(ls -1 /lib/modules | sort -V | tail -1)
test -n "$krel"
test -s "/boot/initrd.img-$krel"
rm -f /usr/sbin/policy-rc.d
apt-get clean
rm -rf /var/lib/apt/lists/*
'

# Candidate identity belongs only in disposable images. Keep the cached
# foundation source-independent and give every overlay a new machine identity.
sudo rm -rf "$mnt/usr/src/decnet-iv-linux"
sudo rm -f "$mnt/etc/machine-id" "$mnt/var/lib/dbus/machine-id"
sudo touch "$mnt/etc/machine-id"

kernel=$(find "$mnt/boot" -maxdepth 1 -type f -name 'vmlinuz-*' | sort -V | tail -1)
initrd=$(find "$mnt/boot" -maxdepth 1 -type f -name 'initrd.img-*' | sort -V | tail -1)
if [[ -z "$kernel" || -z "$initrd" ]]; then
    echo "build-foundation: installed kernel or initrd not found" >&2
    exit 1
fi

if [[ "$arch" == arm64 ]]; then
    "$arm64_normalizer" "$kernel" "$boot_dir/vmlinuz" "build-foundation"
else
    sudo cp "$kernel" "$boot_dir/vmlinuz"
fi
sudo cp "$initrd" "$boot_dir/initrd.img"
sudo chown "$(id -u):$(id -g)" "$boot_dir/vmlinuz" "$boot_dir/initrd.img"

sudo umount -R "$mnt/dev"
sudo umount "$mnt/sys"
sudo umount "$mnt/proc"
chroot_mounted=0
sudo umount "$mnt"
mounted=0
normalize_ext4 "$raw"

qemu-img convert -f raw -O qcow2 "$raw" "$output"
qemu-img check -f qcow2 "$output"
qemu-img compare -f raw -F qcow2 "$raw" "$output"

echo "build-foundation: created source-independent $arch foundation at $output"
