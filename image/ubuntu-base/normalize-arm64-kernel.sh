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

if [[ $# -ne 3 ]]; then
    echo "usage: $0 SOURCE-KERNEL OUTPUT-IMAGE LABEL" >&2
    exit 2
fi

source_kernel=$1
output=$2
label=$3

if [[ ! -s "$source_kernel" ]]; then
    echo "$label: arm64 source kernel missing or empty: $source_kernel" >&2
    exit 1
fi

work=$(mktemp -d)
cleanup() {
    rm -rf "$work"
}
trap cleanup EXIT INT TERM

candidate="$work/candidate"
payload="$work/payload"
raw="$work/Image"

hex_bytes() {
    local path=$1 skip=$2 count=$3
    dd if="$path" bs=1 skip="$skip" count="$count" status=none | \
        od -An -tx1 | tr -d ' \n'
}

raw_magic() {
    hex_bytes "$1" 56 4
}

outer_magic=$(sudo dd if="$source_kernel" bs=1 count=2 status=none | \
    od -An -tx1 | tr -d ' \n')
if [[ "$outer_magic" == 1f8b ]]; then
    sudo gzip -dc "$source_kernel" > "$candidate"
    outer_format=gzip
else
    sudo cat "$source_kernel" > "$candidate"
    outer_format=plain
fi
test -s "$candidate"

if [[ "$(raw_magic "$candidate")" == 41524d64 ]]; then
    mv "$candidate" "$raw"
    inner_format=raw
else
    zboot_msdos=$(hex_bytes "$candidate" 0 2)
    zboot_tag=$(hex_bytes "$candidate" 4 4)
    zboot_linux_magic=$(hex_bytes "$candidate" 56 4)
    if [[ "$zboot_msdos" != 4d5a || "$zboot_tag" != 7a696d67 || \
          "$zboot_linux_magic" != cd238281 ]]; then
        echo "$label: unsupported arm64 kernel format; refusing non-Image fallback" >&2
        exit 1
    fi

    zboot_payload_offset=$(dd if="$candidate" bs=1 skip=8 count=4 status=none | \
        od -An -tu4 | tr -d ' \n')
    zboot_payload_size=$(dd if="$candidate" bs=1 skip=12 count=4 status=none | \
        od -An -tu4 | tr -d ' \n')
    zboot_compression=$(dd if="$candidate" bs=1 skip=24 count=32 status=none | tr -d '\000')
    zboot_file_size=$(stat -c '%s' "$candidate")

    if [[ ! "$zboot_payload_offset" =~ ^[0-9]+$ || \
          ! "$zboot_payload_size" =~ ^[0-9]+$ ]] || \
       (( zboot_payload_offset <= 0 || zboot_payload_size <= 0 || \
          zboot_payload_offset + zboot_payload_size > zboot_file_size )); then
        echo "$label: invalid arm64 EFI-zboot payload bounds" >&2
        exit 1
    fi

    dd if="$candidate" bs=1 skip="$zboot_payload_offset" \
        count="$zboot_payload_size" status=none > "$payload"
    case "$zboot_compression" in
        gzip)
            gzip -dc "$payload" > "$raw"
            ;;
        zstd)
            if ! command -v zstd >/dev/null 2>&1; then
                echo "$label: zstd is required to unpack the arm64 EFI-zboot kernel" >&2
                exit 1
            fi
            zstd -q -d -c "$payload" > "$raw"
            ;;
        *)
            echo "$label: unsupported arm64 EFI-zboot compression: $zboot_compression" >&2
            exit 1
            ;;
    esac
    inner_format="efi-zboot:$zboot_compression"
fi

test -s "$raw"
if [[ "$(raw_magic "$raw")" != 41524d64 ]]; then
    echo "$label: normalized arm64 kernel is not a raw Linux Image" >&2
    exit 1
fi

mkdir -p "$(dirname "$output")"
mv "$raw" "$output"
chmod 0644 "$output"
echo "$label: normalized arm64 kernel outer=$outer_format inner=$inner_format to raw Image"
