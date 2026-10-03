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
module_root_is_default=1
if [[ -n ${MODULE_ROOT:-} ]]; then module_root_is_default=0; fi
module_root=${MODULE_ROOT:-/lib/modules/$kernel_release}

while [[ "$prefix" != / && "$prefix" == */ ]]; do prefix=${prefix%/}; done
if [[ -n "$destdir" ]]; then
    while [[ "$destdir" != / && "$destdir" == */ ]]; do destdir=${destdir%/}; done
fi
while [[ "$module_root" != / && "$module_root" == */ ]]; do module_root=${module_root%/}; done
manifest_rel="$prefix/share/decnet-iv-linux/install-manifest.txt"
manifest="$destdir$manifest_rel"
safe_root() {
    local path=$1
    [[ "$path" == /* && "$path" != / &&
       "$path" != *$'\n'* && "$path" != *$'\r'* &&
       "$path" != *"//"* &&
       "$path" != *"/../"* && "$path" != */.. &&
       "$path" != *"/./"* && "$path" != */. ]]
}
if [[ -n "$destdir" ]] && ! safe_root "$destdir"; then
    echo "uninstall.sh: DESTDIR must be empty or a normalized absolute non-root path" >&2
    exit 2
fi
safe_root "$prefix" && safe_root "$module_root" || {
    echo "uninstall.sh: PREFIX and MODULE_ROOT must be normalized absolute non-root paths" >&2
    exit 2
}

check_staged_parent() {
    local target=$1 full current part i
    local -a parts
    [[ -n "$destdir" ]] || return 0
    full="$destdir$target"
    current=/
    IFS=/ read -r -a parts <<<"${full#/}"
    for ((i = 0; i + 1 < ${#parts[@]}; i++)); do
        part=${parts[i]}
        [[ -n "$part" ]] || continue
        current="${current%/}/$part"
        if [[ -L "$current" ]]; then
            echo "uninstall.sh: staged path crosses symlink parent: $current" >&2
            return 1
        fi
        if [[ -e "$current" && ! -d "$current" ]]; then
            echo "uninstall.sh: staged path crosses non-directory parent: $current" >&2
            return 1
        fi
    done
}

safe_default_module_path() {
    local path=$1 rest release
    case "$path" in /lib/modules/*/extra/decnet_iv.ko) ;; *) return 1 ;; esac
    rest=${path#/lib/modules/}
    release=${rest%%/*}
    [[ -n "$release" && "$rest" == "$release/extra/decnet_iv.ko" ]]
}

safe_managed_path() {
    local path=$1
    [[ "$path" == /* && "$path" != *$'\n'* && "$path" != *$'\r'* &&
        "$path" != *"//"* &&
        "$path" != *"/../"* && "$path" != *"/.." &&
        "$path" != *"/./"* && "$path" != *"/." ]] || return 1
    case "$path" in "$prefix"/*|"$module_root"/*) return 0 ;; esac
    (( module_root_is_default )) && safe_default_module_path "$path"
}

if [[ -z "$destdir" && -n ${MODULE_ROOT:-} ]]; then
  echo "uninstall.sh: custom MODULE_ROOT is supported only with non-empty DESTDIR" >&2
  exit 2
fi
if [[ -z "$destdir" && ${EUID:-$(id -u)} -ne 0 ]]; then echo "uninstall.sh: live uninstall requires root; use DESTDIR for staging" >&2; exit 2; fi
command -v stat >/dev/null 2>&1 || { echo "uninstall.sh: required command not found: stat" >&2; exit 2; }
if [[ -z "$destdir" ]]; then
  command -v depmod >/dev/null 2>&1 || { echo "uninstall.sh: required command not found: depmod" >&2; exit 2; }
fi
check_staged_parent "$manifest_rel" || exit 2
[[ -f "$manifest" && ! -L "$manifest" && $(stat -c %h -- "$manifest") == 1 ]] || { echo "uninstall.sh: safe install manifest not found: $manifest" >&2; exit 2; }
mapfile -t paths <"$manifest"
module_releases=()
for path in "${paths[@]}"; do
  [[ -z "$path" ]] && continue
  safe_managed_path "$path" || { echo "uninstall.sh: manifest path outside managed roots: $path" >&2; exit 2; }
  check_staged_parent "$path" || exit 2
  if (( module_root_is_default )) && safe_default_module_path "$path"; then
    rest=${path#/lib/modules/}
    module_releases+=("${rest%%/*}")
  fi
done
for path in "${paths[@]}"; do
  [[ -z "$path" ]] && continue
  rm -f -- "$destdir$path"
done
rm -f -- "$manifest"
for rel in "$prefix/share/doc/decnet-iv-linux" "$prefix/share/decnet-iv-linux" "$prefix/include/netdnet"; do
  check_staged_parent "$rel" || exit 2
  rmdir "$destdir$rel" 2>/dev/null || true
done
if [[ -z "$destdir" ]]; then
  printf '%s\n' "$kernel_release" "${module_releases[@]}" | sort -u | while IFS= read -r release; do
    [[ -z "$release" ]] || depmod -a "$release"
  done
  command -v ldconfig >/dev/null 2>&1 && ldconfig
fi
echo "uninstall.sh: PASS"
