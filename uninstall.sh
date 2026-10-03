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
destdir=${DESTDIR:-}
prefix=${PREFIX:-/usr/local}
kernel_release=${KERNEL_RELEASE:-$(uname -r)}
module_root=${MODULE_ROOT:-/lib/modules/$kernel_release}
manifest_rel="$prefix/share/decnet-iv-linux/install-manifest.txt"
manifest="$destdir$manifest_rel"
[[ -z "$destdir" || "$destdir" == /* ]] || { echo "uninstall.sh: DESTDIR must be empty or absolute" >&2; exit 2; }
[[ "$prefix" == /* && "$prefix" != / && "$module_root" == /* && "$module_root" != / ]] || { echo "uninstall.sh: PREFIX and MODULE_ROOT must be absolute non-root paths" >&2; exit 2; }
if [[ -z "$destdir" && ${EUID:-$(id -u)} -ne 0 ]]; then echo "uninstall.sh: live uninstall requires root; use DESTDIR for staging" >&2; exit 2; fi
[[ -f "$manifest" && ! -L "$manifest" ]] || { echo "uninstall.sh: safe install manifest not found: $manifest" >&2; exit 2; }
while IFS= read -r path; do
  [[ "$path" == /* && "$path" != *"/../"* && "$path" != *"/.." ]] || { echo "uninstall.sh: unsafe manifest path: $path" >&2; exit 2; }
  case "$path" in "$prefix"/*|"$module_root"/*) ;; *) echo "uninstall.sh: manifest path outside managed roots: $path" >&2; exit 2 ;; esac
  rm -f -- "$destdir$path"
done <"$manifest"
rm -f -- "$manifest"
for dir in "$destdir$prefix/share/doc/decnet-iv-linux" "$destdir$prefix/share/decnet-iv-linux" "$destdir$prefix/include/netdnet"; do rmdir "$dir" 2>/dev/null || true; done
if [[ -z "$destdir" ]]; then command -v depmod >/dev/null 2>&1 && depmod -a "$kernel_release"; command -v ldconfig >/dev/null 2>&1 && ldconfig; fi
echo "uninstall.sh: PASS"
