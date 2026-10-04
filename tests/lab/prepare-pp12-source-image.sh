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
    echo "usage: $0 FOUNDATION-QCOW2 SOURCE-TARBALL CHECKSUM-FILE OUTPUT-QCOW2 EXPECTED-SHA" >&2
    exit 2
fi
foundation=$1
archive=$2
checksum=$3
output=$4
expected_sha=$5
[[ -r "$foundation" ]] || { echo "prepare-pp12-source-image: missing foundation" >&2; exit 2; }
[[ -r "$archive" ]] || { echo "prepare-pp12-source-image: missing source archive" >&2; exit 2; }
[[ -r "$checksum" ]] || { echo "prepare-pp12-source-image: missing checksum" >&2; exit 2; }
[[ "$expected_sha" =~ ^[0-9a-f]{40}$ ]] || { echo "prepare-pp12-source-image: invalid expected SHA" >&2; exit 2; }

foundation=$(readlink -f "$foundation")
archive=$(readlink -f "$archive")
checksum=$(readlink -f "$checksum")
mkdir -p "$(dirname "$output")"
output=$(readlink -m "$output")
if [[ "$(basename "$checksum")" != "$(basename "$archive").sha256" ]]; then
    echo "prepare-pp12-source-image: checksum filename does not match archive" >&2
    exit 2
fi
(cd "$(dirname "$archive")" && sha256sum -c "$(basename "$checksum")")
archive_sha=$(sha256sum "$archive" | awk '{print $1}')

work=$(mktemp -d)
raw="$work/candidate.raw"
mnt="$work/root"
release="$work/release"
mkdir -p "$mnt" "$release"
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
        echo "prepare-pp12-source-image: ext4 normalization failed with status $rc" >&2
        return "$rc"
    fi
}

tar -xJf "$archive" -C "$release"
mapfile -t roots < <(find "$release" -mindepth 1 -maxdepth 1 -type d -print)
[[ ${#roots[@]} -eq 1 ]] || { echo "prepare-pp12-source-image: archive must contain one top-level directory" >&2; exit 1; }
src=${roots[0]}
[[ ! -e "$src/.git" ]] || { echo "prepare-pp12-source-image: source archive contains .git" >&2; exit 1; }
grep -Fqx "source_sha=$expected_sha" "$src/SOURCE-METADATA" || {
    echo "prepare-pp12-source-image: SOURCE-METADATA SHA mismatch" >&2
    exit 1
}

qemu-img convert -q -f qcow2 -O raw "$foundation" "$raw"
sudo mount -o loop "$raw" "$mnt"
mounted=1
sudo rm -rf "$mnt/usr/src/decnet-iv-linux"
sudo mkdir -p "$mnt/usr/src/decnet-iv-linux" "$mnt/usr/local/sbin"     "$mnt/etc/systemd/system/multi-user.target.wants"
tar -C "$src" -cf - . | sudo tar -C "$mnt/usr/src/decnet-iv-linux" -xf -
printf '%s\n' "$expected_sha" | sudo tee "$mnt/usr/src/decnet-iv-linux/.source-commit" >/dev/null
printf '%s\n' "$expected_sha" | sudo tee "$mnt/etc/dniv-source-release-sha" >/dev/null
printf '%s\n' "$archive_sha" | sudo tee "$mnt/etc/dniv-source-release-archive-sha256" >/dev/null

sudo mount -t proc proc "$mnt/proc"
sudo mount -t sysfs sysfs "$mnt/sys"
sudo mount --rbind /dev "$mnt/dev"
sudo mount --make-rslave "$mnt/dev"
chroot_mounted=1
sudo chroot "$mnt" /bin/bash -euxc '
expected=$(cat /etc/dniv-source-release-sha)
cd /usr/src/decnet-iv-linux
grep -Fqx "source_sha=$expected" SOURCE-METADATA
krel=$(ls -1 /lib/modules | sort -V | tail -1)
test -n "$krel"
test -d "/lib/modules/$krel/build"
KDIR="/lib/modules/$krel/build" KERNEL_RELEASE="$krel" ./build.sh
KERNEL_RELEASE="$krel" ./install.sh
manifest=/usr/local/share/decnet-iv-linux/install-manifest.txt
test -s "$manifest"
sha256sum "$manifest" >/etc/dniv-pp12-manifest-first.sha256
KERNEL_RELEASE="$krel" ./install.sh
sha256sum -c /etc/dniv-pp12-manifest-first.sha256
cc -Iuserspace/libdnet/include -Iinclude/uapi -Iinclude     -O2 -std=c11 -Wall -Wextra -Werror     -o /usr/local/sbin/dniv-area31-native tests/lab/area31-native.c     userspace/libdnet/libdnet.a
printf "SOURCE_SHA=%s\nKERNEL_RELEASE=%s\n" "$expected" "$krel" >/etc/dniv-pp12-provenance.env
'

sudo install -m 0755 "$mnt/usr/src/decnet-iv-linux/tests/lab/dniv-area31-smoke.sh"     "$mnt/usr/local/sbin/dniv-area31-smoke"
sudo install -m 0644 "$mnt/usr/src/decnet-iv-linux/tests/lab/dniv-area31-smoke.service"     "$mnt/etc/systemd/system/dniv-area31-smoke.service"
sudo ln -sf ../dniv-area31-smoke.service     "$mnt/etc/systemd/system/multi-user.target.wants/dniv-area31-smoke.service"
sudo install -m 0755 "$mnt/usr/src/decnet-iv-linux/tests/lab/dniv-pp12-smoke.sh"     "$mnt/usr/local/sbin/dniv-pp12-smoke"
sudo install -m 0644 "$mnt/usr/src/decnet-iv-linux/tests/lab/dniv-pp12-smoke.service"     "$mnt/etc/systemd/system/dniv-pp12-smoke.service"
sudo ln -sf ../dniv-pp12-smoke.service     "$mnt/etc/systemd/system/multi-user.target.wants/dniv-pp12-smoke.service"

if [[ -n "${DNIV_PP12_EVIDENCE_DIR:-}" ]]; then
    mkdir -p "$DNIV_PP12_EVIDENCE_DIR"
    sudo cp "$mnt/etc/dniv-pp12-provenance.env" "$DNIV_PP12_EVIDENCE_DIR/provenance.env"
    sudo chown "$(id -u):$(id -g)" "$DNIV_PP12_EVIDENCE_DIR/provenance.env"
    printf 'ARCHIVE=%s\nARCHIVE_SHA256=%s\n' "$(basename "$archive")" "$archive_sha"         >>"$DNIV_PP12_EVIDENCE_DIR/provenance.env"
fi

sudo umount -R "$mnt/dev"
sudo umount "$mnt/sys"
sudo umount "$mnt/proc"
chroot_mounted=0
sudo umount "$mnt"
mounted=0
normalize_ext4 "$raw"
qemu-img convert -q -f raw -O qcow2 "$raw" "$output"
qemu-img check -q -f qcow2 "$output"
qemu-img compare -q -f raw -F qcow2 "$raw" "$output"
echo "prepare-pp12-source-image: created $output from exact archive $(basename "$archive") sha256=$archive_sha source=$expected_sha"
