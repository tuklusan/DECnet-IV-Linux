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
root=$(cd "$(dirname "$0")" && pwd)
cd "$root"
python=${PYTHON:-python3}
cc=${CC:-cc}
need() { command -v "$1" >/dev/null 2>&1 || { echo "build.sh: required command not found: $1" >&2; exit 2; }; }
for command in bash make "$cc" "$python" install ln rm find sort grep sed; do need "$command"; done
"$python" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)' || { echo "build.sh: Python 3.10 or later is required" >&2; exit 2; }
case "$(uname -m)" in x86_64|aarch64) ;; *) echo "build.sh: supported architectures are x86_64 and aarch64" >&2; exit 2 ;; esac

if [[ -n ${KDIR:-} ]]; then
    kdir=$KDIR
else
    kernel_release=${KERNEL_RELEASE:-$(uname -r)}
    kdir=/lib/modules/$kernel_release/build
fi
test -r "$kdir/Makefile" || { echo "build.sh: matching kernel build tree not found: $kdir" >&2; exit 2; }
detected_release=$(make -s -C "$kdir" kernelrelease)
kernel_release=${KERNEL_RELEASE:-$detected_release}
[[ "$kernel_release" == "$detected_release" ]] || {
    echo "build.sh: KERNEL_RELEASE=$kernel_release does not match KDIR release $detected_release" >&2
    exit 2
}
kernel_version=$(make -s -C "$kdir" kernelversion)
first=$(printf '%s\n%s\n' 6.8 "$kernel_version" | sort -V | head -1)
[[ "$first" == 6.8 ]] || { echo "build.sh: Linux 6.8 or later required; target reports $kernel_version" >&2; exit 2; }

compiler_line=$("$cc" --version | head -1)
compiler_version=$("$cc" -dumpfullversion -dumpversion 2>/dev/null || "$cc" -dumpversion)
compiler_major=${compiler_version%%.*}
[[ "$compiler_major" =~ ^[0-9]+$ ]] || { echo "build.sh: cannot determine compiler version from $cc" >&2; exit 2; }
case "$compiler_line" in
    *[Cc]lang*)
        (( compiler_major >= 16 )) || { echo "build.sh: Clang 16 or later required; found $compiler_version" >&2; exit 2; }
        llvm=1
        ;;
    *)
        (( compiler_major >= 12 )) || { echo "build.sh: GCC-compatible compiler 12 or later required; found $compiler_version" >&2; exit 2; }
        llvm=0
        ;;
esac

printf 'DECnet-IV-Linux build\n  kernel release: %s\n  kernel version: %s\n  kernel build:   %s\n  compiler:       %s\n' "$kernel_release" "$kernel_version" "$kdir" "$compiler_line"
make clean KDIR="$kdir"
make userspace CC="$cc" PYTHON="$python"
if (( llvm )); then
    make kernel KDIR="$kdir" CC="$cc" LLVM=1
else
    make kernel KDIR="$kdir" CC="$cc"
fi
test -s kernel/decnet/decnet_iv.ko
echo "build.sh: PASS"
