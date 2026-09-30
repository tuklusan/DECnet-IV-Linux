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

if [[ $# -ne 5 ]]; then
    echo "usage: $0 IMAGE KDIR KERNELRELEASE CONFIG PROFILE" >&2
    exit 2
fi

image=$1
kdir=$2
krel=$3
config=$4
profile=$5
[[ -r "$image" && -d "$kdir" && -r "$config" ]] || {
    echo "install-diagnostic-module: missing input" >&2
    exit 2
}
case "$profile" in
    kasan|kcsan) ;;
    *) echo "install-diagnostic-module: unsupported profile: $profile" >&2; exit 2 ;;
esac
[[ "$krel" == "7.0.0-dniv-$profile" ]] || {
    echo "install-diagnostic-module: unexpected kernel release: $krel" >&2
    exit 2
}

script_dir=$(cd "$(dirname "$0")" && pwd)
repo_root=$(cd "$script_dir/../.." && pwd)
work=$(mktemp -d)
raw="$work/candidate.raw"
mnt="$work/root"
module="$work/decnet_iv.ko"
mkdir -p "$mnt"
mounted=0
cleanup() {
    set +e
    if (( mounted )); then
        sudo umount "$mnt" 2>/dev/null || true
    fi
    make -C "$repo_root/kernel/decnet" KDIR="$kdir" clean >/dev/null 2>&1 || true
    rm -rf "$work"
}
trap cleanup EXIT INT TERM

make -C "$repo_root/kernel/decnet" KDIR="$kdir" clean all
cp "$repo_root/kernel/decnet/decnet_iv.ko" "$module"
vermagic=$(modinfo -F vermagic "$module")
[[ "$vermagic" == "$krel "* ]] || {
    echo "install-diagnostic-module: vermagic mismatch: $vermagic" >&2
    exit 1
}
make -C "$repo_root/kernel/decnet" KDIR="$kdir" clean >/dev/null

qemu-img convert -q -f qcow2 -O raw "$image" "$raw"
sudo mount -o loop "$raw" "$mnt"
mounted=1
sudo install -D -m 0644 "$module" "$mnt/lib/modules/$krel/extra/decnet_iv.ko"
sudo install -m 0644 "$config" "$mnt/boot/config-$krel"
printf '%s\n' "$profile" | sudo tee "$mnt/etc/dniv-diagnostic-profile" >/dev/null
sudo depmod -b "$mnt" "$krel"
sudo test -s "$mnt/lib/modules/$krel/extra/decnet_iv.ko"
sudo test -s "$mnt/lib/modules/$krel/modules.dep"
sudo umount "$mnt"
mounted=0

set +e
sudo e2fsck -fy "$raw"
rc=$?
set -e
(( rc <= 1 )) || exit "$rc"

qemu-img convert -q -f raw -O qcow2 "$raw" "$work/candidate.qcow2"
qemu-img check -q -f qcow2 "$work/candidate.qcow2"
mv "$work/candidate.qcow2" "$image"
echo "install-diagnostic-module: image=$image release=$krel profile=$profile"
