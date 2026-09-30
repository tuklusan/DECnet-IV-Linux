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

candidate="$work/candidate-0"
raw="$work/Image"

hex_bytes() {
    local path=$1 skip=$2 count=$3
    dd if="$path" bs=1 skip="$skip" count="$count" status=none | \
        od -An -tx1 | tr -d ' \n'
}

raw_magic() {
    hex_bytes "$1" 56 4
}

read_source() {
    local source=$1 destination=$2
    if [[ -r "$source" ]]; then
        cat "$source" > "$destination"
    else
        sudo cat "$source" > "$destination"
    fi
}

decompress_zboot_payload() {
    local payload=$1 raw=$2 compression=$3
    case "$compression" in
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
            echo "$label: unsupported arm64 EFI-zboot compression: $compression" >&2
            exit 1
            ;;
    esac
}

extract_pe_linux() {
    local source=$1 destination=$2
    python3 - "$source" "$destination" <<'PY'
import pathlib
import struct
import sys

source = pathlib.Path(sys.argv[1])
destination = pathlib.Path(sys.argv[2])
data = source.read_bytes()
if len(data) < 0x40 or data[:2] != b"MZ":
    raise SystemExit(3)
pe_offset = struct.unpack_from("<I", data, 0x3C)[0]
if pe_offset + 24 > len(data) or data[pe_offset:pe_offset + 4] != b"PE\0\0":
    raise SystemExit(4)
section_count = struct.unpack_from("<H", data, pe_offset + 6)[0]
optional_size = struct.unpack_from("<H", data, pe_offset + 20)[0]
section_table = pe_offset + 24 + optional_size
if section_count == 0 or section_count > 96 or section_table + section_count * 40 > len(data):
    raise SystemExit(4)
matches = []
for index in range(section_count):
    offset = section_table + index * 40
    name = data[offset:offset + 8].split(b"\0", 1)[0]
    if name != b".linux":
        continue
    size = struct.unpack_from("<I", data, offset + 16)[0]
    pointer = struct.unpack_from("<I", data, offset + 20)[0]
    if size == 0 or pointer == 0 or pointer + size > len(data):
        raise SystemExit(4)
    matches.append(data[pointer:pointer + size])
if len(matches) != 1:
    raise SystemExit(3)
destination.write_bytes(matches[0])
PY
}

read_source "$source_kernel" "$candidate"
test -s "$candidate"

formats=()
for depth in 0 1 2 3 4 5; do
    if [[ "$(raw_magic "$candidate")" == 41524d64 ]]; then
        mv "$candidate" "$raw"
        formats+=(raw)
        break
    fi

    magic2=$(hex_bytes "$candidate" 0 2)
    magic4=$(hex_bytes "$candidate" 0 4)
    next="$work/candidate-$((depth + 1))"

    if [[ "$magic2" == 1f8b ]]; then
        gzip -dc "$candidate" > "$next"
        formats+=(gzip)
        candidate=$next
        test -s "$candidate"
        continue
    fi

    if [[ "$magic4" == 28b52ffd ]]; then
        if ! command -v zstd >/dev/null 2>&1; then
            echo "$label: zstd is required to unpack the arm64 kernel" >&2
            exit 1
        fi
        zstd -q -d -c "$candidate" > "$next"
        formats+=(zstd)
        candidate=$next
        test -s "$candidate"
        continue
    fi

    zboot_msdos=$(hex_bytes "$candidate" 0 2)
    zboot_tag=$(hex_bytes "$candidate" 4 4)
    zboot_linux_magic=$(hex_bytes "$candidate" 56 4)
    if [[ "$zboot_msdos" == 4d5a && "$zboot_tag" == 7a696d67 && \
          "$zboot_linux_magic" == cd238281 ]]; then
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

        payload="$work/payload-$depth"
        dd if="$candidate" bs=1 skip="$zboot_payload_offset" \
            count="$zboot_payload_size" status=none > "$payload"
        decompress_zboot_payload "$payload" "$next" "$zboot_compression"
        formats+=("efi-zboot:$zboot_compression")
        candidate=$next
        test -s "$candidate"
        continue
    fi

    if [[ "$magic2" == 4d5a ]]; then
        set +e
        extract_pe_linux "$candidate" "$next"
        pe_rc=$?
        set -e
        case "$pe_rc" in
            0)
                formats+=(pe-linux)
                candidate=$next
                test -s "$candidate"
                continue
                ;;
            3)
                :
                ;;
            *)
                echo "$label: malformed PE arm64 kernel wrapper" >&2
                exit 1
                ;;
        esac
    fi

    echo "$label: unsupported arm64 kernel format; refusing non-Image fallback" >&2
    exit 1
done

if [[ ! -s "$raw" ]]; then
    echo "$label: arm64 kernel wrapper nesting exceeds normalization limit" >&2
    exit 1
fi
if [[ "$(raw_magic "$raw")" != 41524d64 ]]; then
    echo "$label: normalized arm64 kernel is not a raw Linux Image" >&2
    exit 1
fi

mkdir -p "$(dirname "$output")"
mv "$raw" "$output"
chmod 0644 "$output"
format_chain=$(IFS=+; echo "${formats[*]}")
echo "$label: normalized arm64 kernel chain=$format_chain to raw Image"
