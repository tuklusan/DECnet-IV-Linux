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
[[ -r "$base" ]] || { echo "prepare-interop-candidate: missing $base" >&2; exit 2; }
work=$(mktemp -d)
raw="$work/candidate.raw"
verify_raw="$work/verify.raw"
mnt="$work/root"
mkdir -p "$mnt" "$(dirname "$output")"
mounted=0
cleanup() {
    set +e
    (( mounted )) && sudo umount "$mnt" 2>/dev/null || true
    rm -rf "$work"
}
trap cleanup EXIT INT TERM
qemu-img convert -q -f qcow2 -O raw "$base" "$raw"
sudo mount -o loop "$raw" "$mnt"
mounted=1
archived_source="$mnt/usr/src/decnet-iv-linux"
test -r "$archived_source/.source-commit"
source_commit=$(sudo cat "$archived_source/.source-commit")
[[ "$source_commit" =~ ^[0-9a-f]{40}$ ]] || {
    echo "prepare-interop-candidate: invalid archived source commit" >&2
    exit 1
}
test -r "$archived_source/tests/lab/dniv-interop-smoke.sh"
sudo install -m 0755 "$archived_source/tests/lab/dniv-interop-smoke.sh" \
    "$mnt/usr/local/sbin/dniv-interop-smoke"
sudo tee "$mnt/etc/systemd/system/dniv-interop-smoke.service" >/dev/null <<'EOF_SERVICE'
[Unit]
Description=DECnet Phase IV independent-peer interoperability test
After=systemd-udev-settle.service
ConditionKernelCommandLine=dniv.interop=1

[Service]
Type=oneshot
ExecStart=/usr/local/sbin/dniv-interop-smoke
StandardOutput=journal+console
StandardError=journal+console

[Install]
WantedBy=multi-user.target
EOF_SERVICE
sudo ln -sf ../dniv-interop-smoke.service \
    "$mnt/etc/systemd/system/multi-user.target.wants/dniv-interop-smoke.service"
sudo umount "$mnt"
mounted=0

# Acceptance correctness wins over file-size optimization. Keep the derived
# image uncompressed, validate its qcow2 structure, then prove that converting
# it back to RAW reproduces the complete intended disk byte-for-byte.
qemu-img convert -q -f raw -O qcow2 "$raw" "$output"
qemu-img check -q -f qcow2 "$output"
qemu-img convert -q -f qcow2 -O raw "$output" "$verify_raw"
if ! cmp -s "$raw" "$verify_raw"; then
    echo "prepare-interop-candidate: full RAW content changed during image conversion" >&2
    exit 1
fi
rm -f "$verify_raw"
echo "prepare-interop-candidate: created $output from archived source $source_commit"
