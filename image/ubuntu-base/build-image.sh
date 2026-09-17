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
    *) echo "build-image: unsupported architecture: $arch" >&2; exit 2 ;;
esac

script_dir=$(cd "$(dirname "$0")" && pwd)
repo_root=$(cd "$script_dir/../.." && pwd)
# shellcheck disable=SC1091
. "$script_dir/images.env"
snapshot=${UBUNTU_APT_SNAPSHOT:?images.env must pin UBUNTU_APT_SNAPSHOT}
disk_bytes=${DNIV_DISK_BYTES:-4294967296}
if [[ ! "$disk_bytes" =~ ^[0-9]+$ ]] || (( disk_bytes < 4294967296 )); then
    echo "build-image: DNIV_DISK_BYTES must be an integer >= 4294967296" >&2
    exit 2
fi
if [[ ! -f "$base_tar" ]]; then
    echo "build-image: base tarball not found: $base_tar" >&2
    exit 2
fi
source_commit=$(git -C "$repo_root" rev-parse --verify 'HEAD^{commit}')

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
        echo "build-image: ext4 normalization failed with status $rc" >&2
        return "$rc"
    fi
}

truncate -s "$disk_bytes" "$raw"
mkfs.ext4 -q -F -E lazy_itable_init=0,lazy_journal_init=0 -L dniv-root "$raw"
sudo mount -o loop "$raw" "$mnt"
mounted=1
sudo tar --numeric-owner --xattrs --acls -xpf "$base_tar" -C "$mnt"

sudo mkdir -p "$mnt/usr/src/decnet-iv-linux" "$mnt/usr/local/sbin" \
    "$mnt/etc/systemd/system/multi-user.target.wants"
# Archive the exact tracked commit, not the mutable workflow checkout. This keeps
# scratch/runtime, restored artifacts and all other untracked build products out
# of the guest source tree while preserving the exact candidate bytes.
git -C "$repo_root" archive --format=tar "$source_commit" | \
    sudo tar -C "$mnt/usr/src/decnet-iv-linux" -xf -
printf '%s\n' "$source_commit" | \
    sudo tee "$mnt/usr/src/decnet-iv-linux/.source-commit" >/dev/null

sudo rm -f "$mnt/etc/resolv.conf"
sudo cp -L /etc/resolv.conf "$mnt/etc/resolv.conf"
printf 'LABEL=dniv-root / ext4 defaults 0 1\n' | sudo tee "$mnt/etc/fstab" >/dev/null
printf 'dniv\n' | sudo tee "$mnt/etc/hostname" >/dev/null

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
# Ubuntu Base has no usable certificate bundle yet. Bootstrap only the
# certificate package with TLS peer verification disabled; repository
# signatures still authenticate snapshot metadata and packages. Immediately
# refresh package-owned trust and prove ordinary verified snapshot access
# before installing anything else.
apt-get -o Acquire::https::Verify-Peer=false --snapshot "$UBUNTU_APT_SNAPSHOT" update
apt-get -o Acquire::https::Verify-Peer=false --snapshot "$UBUNTU_APT_SNAPSHOT" install -y --no-install-recommends ca-certificates
update-ca-certificates --fresh
apt-get --snapshot "$UBUNTU_APT_SNAPSHOT" update
apt-get --snapshot "$UBUNTU_APT_SNAPSHOT" install -y --no-install-recommends \
    systemd-sysv kmod iproute2 build-essential initramfs-tools \
    linux-image-virtual-hwe-26.04 linux-headers-virtual-hwe-26.04
krel=$(ls -1 /lib/modules | sort -V | tail -1)
test -n "$krel"
test -s "/boot/initrd.img-$krel"
make -C /usr/src/decnet-iv-linux/userspace/dnctl clean all
install -m 0755 /usr/src/decnet-iv-linux/userspace/dnctl/dnctl /usr/local/sbin/dnctl
cc -O2 -std=c11 -Wall -Wextra -Werror \
    -o /usr/local/sbin/dnraw /usr/src/decnet-iv-linux/tests/lab/dnraw.c
make -C /usr/src/decnet-iv-linux/kernel/decnet KDIR="/lib/modules/$krel/build" clean all
install -D -m 0644 /usr/src/decnet-iv-linux/kernel/decnet/decnet_iv.ko \
    "/lib/modules/$krel/extra/decnet_iv.ko"
depmod "$krel"
apt-get purge -y build-essential linux-headers-virtual-hwe-26.04 || true
apt-get autoremove -y --purge || true
apt-get clean
rm -rf /var/lib/apt/lists/*
rm -f /usr/sbin/policy-rc.d
'

# Package scripts may create a machine identity. Clear it only after all
# package work so every QCOW2 overlay creates its own identity on first boot.
sudo rm -f "$mnt/etc/machine-id" "$mnt/var/lib/dbus/machine-id"
sudo touch "$mnt/etc/machine-id"

smoke_script_source="$mnt/usr/src/decnet-iv-linux/tests/lab/dniv-smoke.sh"
smoke_unit_source="$mnt/usr/src/decnet-iv-linux/tests/lab/dniv-smoke.service"
smoke_script_dest="$mnt/usr/local/sbin/dniv-smoke"
smoke_unit_dest="$mnt/etc/systemd/system/dniv-smoke.service"
sudo install -m 0755 "$smoke_script_source" "$smoke_script_dest"
sudo install -m 0644 "$smoke_unit_source" "$smoke_unit_dest"
# Use systemd's own offline enable operation and verify the resulting dependency.
# This makes the smoke entry-point dependency an explicit image-build invariant.
sudo systemctl --root="$mnt" enable dniv-smoke.service >/dev/null
[[ "$(sudo systemctl --root="$mnt" is-enabled dniv-smoke.service)" == enabled ]]
sudo test -L "$mnt/etc/systemd/system/multi-user.target.wants/dniv-smoke.service"

# The guest acceptance entry point is part of the image contract. Prove that
# installation preserved the exact archived bytes and that systemd accepts the
# installed unit before the filesystem is converted.
sudo cmp -s "$smoke_script_source" "$smoke_script_dest"
sudo cmp -s "$smoke_unit_source" "$smoke_unit_dest"
sudo chroot "$mnt" systemd-analyze verify /etc/systemd/system/dniv-smoke.service

kernel=$(find "$mnt/boot" -maxdepth 1 -type f -name 'vmlinuz-*' | sort -V | tail -1)
initrd=$(find "$mnt/boot" -maxdepth 1 -type f -name 'initrd.img-*' | sort -V | tail -1)
if [[ -z "$kernel" || -z "$initrd" ]]; then
    echo "build-image: installed kernel or initrd not found" >&2
    exit 1
fi

# QEMU's AArch64 direct loader first peels one outer gzip layer. For a
# non-gzip file it recognizes EFI-zboot and otherwise treats the bytes as a raw
# kernel image. Normalize an exact validated EFI-zboot wrapper to its raw Image
# payload before direct boot; preserve unknown nonempty artifacts for QEMU's raw
# fallback, with VM boot remaining the executable proof.
if [[ "$arch" == arm64 ]]; then
    kernel_magic=$(sudo dd if="$kernel" bs=1 count=2 status=none | od -An -tx1 | tr -d ' \n')
    if [[ "$kernel_magic" == 1f8b ]]; then
        sudo gzip -dc "$kernel" > "$boot_dir/vmlinuz"
    else
        sudo cp "$kernel" "$boot_dir/vmlinuz"
    fi
    sudo chown "$(id -u):$(id -g)" "$boot_dir/vmlinuz"
    test -s "$boot_dir/vmlinuz"

    arm64_magic=$(dd if="$boot_dir/vmlinuz" bs=1 skip=56 count=4 status=none | \
        od -An -tx1 | tr -d ' \n')
    if [[ "$arm64_magic" == 41524d64 ]]; then
        : # current AArch64 Image: "ARM\x64" at offset 56
    else
        zboot_msdos=$(dd if="$boot_dir/vmlinuz" bs=1 count=2 status=none | \
            od -An -tx1 | tr -d ' \n')
        zboot_tag=$(dd if="$boot_dir/vmlinuz" bs=1 skip=4 count=4 status=none | \
            od -An -tx1 | tr -d ' \n')
        zboot_linux_magic=$(dd if="$boot_dir/vmlinuz" bs=1 skip=56 count=4 status=none | \
            od -An -tx1 | tr -d ' \n')

        if [[ "$zboot_msdos" == 4d5a && "$zboot_tag" == 7a696d67 && \
              "$zboot_linux_magic" == cd238281 ]]; then
            zboot_compression=$(dd if="$boot_dir/vmlinuz" bs=1 skip=24 count=32 status=none | \
                tr -d '\000')
            zboot_payload_offset=$(dd if="$boot_dir/vmlinuz" bs=1 skip=8 count=4 status=none | \
                od -An -tu4 | tr -d ' \n')
            zboot_payload_size=$(dd if="$boot_dir/vmlinuz" bs=1 skip=12 count=4 status=none | \
                od -An -tu4 | tr -d ' \n')
            zboot_file_size=$(stat -c '%s' "$boot_dir/vmlinuz")

            if [[ "$zboot_compression" != gzip ]]; then
                echo "build-image: unsupported arm64 EFI-zboot compression: $zboot_compression" >&2
                exit 1
            fi
            if [[ ! "$zboot_payload_offset" =~ ^[0-9]+$ || \
                  ! "$zboot_payload_size" =~ ^[0-9]+$ ]] || \
               (( zboot_payload_offset <= 0 || zboot_payload_size <= 0 || \
                  zboot_payload_offset + zboot_payload_size > zboot_file_size )); then
                echo "build-image: invalid arm64 EFI-zboot payload bounds" >&2
                exit 1
            fi

            zboot_raw="$boot_dir/vmlinuz.raw"
            dd if="$boot_dir/vmlinuz" bs=1 skip="$zboot_payload_offset" \
                count="$zboot_payload_size" status=none | gzip -dc > "$zboot_raw"
            test -s "$zboot_raw"
            zboot_raw_magic=$(dd if="$zboot_raw" bs=1 skip=56 count=4 status=none | \
                od -An -tx1 | tr -d ' \n')
            if [[ "$zboot_raw_magic" != 41524d64 ]]; then
                echo "build-image: arm64 EFI-zboot payload is not a raw Image" >&2
                exit 1
            fi
            mv "$zboot_raw" "$boot_dir/vmlinuz"
        else
            : # QEMU raw-image fallback; boot acceptance is the executable proof.
        fi
    fi
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

# Acceptance correctness wins over file-size optimization. Keep the image
# uncompressed, validate qcow2 structure, then compare guest-visible logical
# content directly across raw and qcow2. qemu-img compare deliberately treats
# sparse/unallocated zero sectors as equal; host-file cmp does not.
qemu-img convert -f raw -O qcow2 "$raw" "$output"
qemu-img check -f qcow2 "$output"
qemu-img compare -f raw -F qcow2 "$raw" "$output"

qemu-img info "$output"
echo "build-image: created $output from source $source_commit with verified direct-boot artifacts in $boot_dir"
