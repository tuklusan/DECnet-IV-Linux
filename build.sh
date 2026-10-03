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
kernel_release=${KERNEL_RELEASE:-$(uname -r)}
kdir=${KDIR:-/lib/modules/$kernel_release/build}
python=${PYTHON:-python3}
cc=${CC:-cc}
need() { command -v "$1" >/dev/null 2>&1 || { echo "build.sh: required command not found: $1" >&2; exit 2; }; }
for command in bash make "$cc" "$python" install ln rm find sort grep sed; do need "$command"; done
"$python" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)' || { echo "build.sh: Python 3.10 or later is required" >&2; exit 2; }
test -r "$kdir/Makefile" || { echo "build.sh: matching kernel build tree not found: $kdir" >&2; exit 2; }
case "$(uname -m)" in x86_64|aarch64) ;; *) echo "build.sh: supported architectures are x86_64 and aarch64" >&2; exit 2 ;; esac
kernel_version=$(make -s -C "$kdir" kernelversion)
first=$(printf '%s\n%s\n' 6.12 "$kernel_version" | sort -V | head -1)
[[ "$first" == 6.12 ]] || { echo "build.sh: Linux 6.12 or later required; target reports $kernel_version" >&2; exit 2; }
compiler_line=$("$cc" --version | head -1)
printf 'DECnet-IV-Linux build\n  kernel release: %s\n  kernel version: %s\n  kernel build:   %s\n  compiler:       %s\n' "$kernel_release" "$kernel_version" "$kdir" "$compiler_line"
make userspace CC="$cc" PYTHON="$python"
case "$compiler_line" in
  *[Cc]lang*) make kernel KDIR="$kdir" CC="$cc" LLVM=1 ;;
  *) make kernel KDIR="$kdir" CC="$cc" ;;
esac
test -s kernel/decnet/decnet_iv.ko
echo "build.sh: PASS"
