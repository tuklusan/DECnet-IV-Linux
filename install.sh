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

destdir=${DESTDIR:-}
prefix=${PREFIX:-/usr/local}
module_path=kernel/decnet/decnet_iv.ko

while [[ "$prefix" != / && "$prefix" == */ ]]; do prefix=${prefix%/}; done
if [[ -n "$destdir" ]]; then
    while [[ "$destdir" != / && "$destdir" == */ ]]; do destdir=${destdir%/}; done
fi

test -r "$module_path" || {
    echo "install.sh: built kernel module not found: $module_path" >&2
    exit 2
}
command -v modinfo >/dev/null 2>&1 || {
    echo "install.sh: required command not found: modinfo" >&2
    exit 2
}
vermagic=$(modinfo -F vermagic "$module_path") || {
    echo "install.sh: cannot read module vermagic: $module_path" >&2
    exit 2
}
read -r module_release _ <<<"$vermagic"
[[ -n "$module_release" ]] || {
    echo "install.sh: cannot determine built module kernel release" >&2
    exit 2
}
if [[ -n ${KERNEL_RELEASE:-} && "$KERNEL_RELEASE" != "$module_release" ]]; then
    echo "install.sh: KERNEL_RELEASE=$KERNEL_RELEASE does not match module vermagic release $module_release" >&2
    exit 2
fi
kernel_release=${KERNEL_RELEASE:-$module_release}
module_root_is_default=1
if [[ -n ${MODULE_ROOT:-} ]]; then module_root_is_default=0; fi
module_root=${MODULE_ROOT:-/lib/modules/$kernel_release}
while [[ "$module_root" != / && "$module_root" == */ ]]; do module_root=${module_root%/}; done
manifest_rel="$prefix/share/decnet-iv-linux/install-manifest.txt"
manifest="$destdir$manifest_rel"
manifest_tmp="$manifest.tmp.$$"

safe_root() {
    local path=$1
    [[ "$path" == /* && "$path" != / &&
       "$path" != *"//"* &&
       "$path" != *"/../"* && "$path" != */.. &&
       "$path" != *"/./"* && "$path" != */. ]]
}

if [[ -n "$destdir" ]] && ! safe_root "$destdir"; then
    echo "install.sh: DESTDIR must be empty or a normalized absolute non-root path" >&2
    exit 2
fi
safe_root "$prefix" && safe_root "$module_root" || {
    echo "install.sh: PREFIX and MODULE_ROOT must be normalized absolute non-root paths" >&2
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
            echo "install.sh: staged path crosses symlink parent: $current" >&2
            return 1
        fi
        if [[ -e "$current" && ! -d "$current" ]]; then
            echo "install.sh: staged path crosses non-directory parent: $current" >&2
            return 1
        fi
    done
}

if [[ -z "$destdir" && ${EUID:-$(id -u)} -ne 0 ]]; then
    echo "install.sh: live installation requires root; use DESTDIR for staging" >&2
    exit 2
fi

safe_default_module_path() {
    local path=$1 rest release
    case "$path" in /lib/modules/*/extra/decnet_iv.ko) ;; *) return 1 ;; esac
    rest=${path#/lib/modules/}
    release=${rest%%/*}
    [[ -n "$release" && "$rest" == "$release/extra/decnet_iv.ko" ]]
}

safe_managed_path() {
    local path=$1
    [[ "$path" == /* && "$path" != *"//"* &&
       "$path" != *"/../"* && "$path" != *"/.." &&
       "$path" != *"/./"* && "$path" != *"/." ]] || return 1
    case "$path" in
        "$prefix"/*|"$module_root"/*) return 0 ;;
    esac
    (( module_root_is_default )) && safe_default_module_path "$path"
}

check_staged_parent "$manifest_rel" || exit 2
mkdir -p "$(dirname "$manifest")"
if [[ -e "$manifest" || -L "$manifest" ]]; then
    [[ -f "$manifest" && ! -L "$manifest" ]] || {
        echo "install.sh: unsafe existing manifest: $manifest" >&2
        exit 2
    }
    while IFS= read -r path; do
        [[ -z "$path" ]] && continue
        safe_managed_path "$path" || {
            echo "install.sh: unsafe existing manifest path: $path" >&2
            exit 2
        }
        check_staged_parent "$path" || exit 2
    done <"$manifest"
else
    : >"$manifest"
fi

trap 'rm -f "$manifest_tmp"' EXIT

managed() {
    grep -Fxq -- "$1" "$manifest" 2>/dev/null
}

check_target() {
    local target=$1
    local full="$destdir$target"
    check_staged_parent "$target" || exit 2
    if [[ -e "$full" || -L "$full" ]]; then
        managed "$target" || {
            echo "install.sh: refusing unmanaged existing target: $target" >&2
            exit 2
        }
    fi
}

record() {
    local target=$1
    check_staged_parent "$target" || exit 2
    safe_managed_path "$target" || {
        echo "install.sh: unsafe install target: $target" >&2
        exit 2
    }
    managed "$target" || printf '%s\n' "$target" >>"$manifest"
}

put() {
    local mode=$1 source=$2 target=$3
    test -e "$source" || {
        echo "install.sh: missing built artifact: $source" >&2
        exit 2
    }
    check_target "$target"
    if [[ -e "$destdir$target" || -L "$destdir$target" ]]; then
        [[ -f "$destdir$target" && ! -L "$destdir$target" ]] || {
            echo "install.sh: refusing non-regular file at regular-file target: $target" >&2
            exit 2
        }
    fi
    record "$target"
    install -D -m "$mode" "$source" "$destdir$target"
}

link_to() {
    local target=$1 link=$2
    check_target "$link"
    if [[ -e "$destdir$link" && ! -L "$destdir$link" ]]; then
        echo "install.sh: refusing non-symlink at link target: $link" >&2
        exit 2
    fi
    record "$link"
    mkdir -p "$(dirname "$destdir$link")"
    ln -sfn "$target" "$destdir$link"
}

put 0644 "$module_path" "$module_root/extra/decnet_iv.ko"

put 0755 userspace/dnctl/dnctl "$prefix/sbin/dnctl"
put 0755 userspace/dnetd/dnetd "$prefix/sbin/dnetd"
put 0755 userspace/dnfald/dnfald "$prefix/sbin/dnfald"
put 0755 userspace/dnnml/dnnml "$prefix/sbin/dnnml"
put 0755 userspace/dnphone/dnphoned "$prefix/sbin/dnphoned"
put 0755 userspace/dnmail/dnmaild "$prefix/sbin/dnmaild"
put 0755 userspace/dnhttpd/dnhttpd "$prefix/sbin/dnhttpd"
put 0755 userspace/dnmultinet/dnmultinet.py "$prefix/sbin/dnmultinet"

put 0755 userspace/ncp/ncp "$prefix/bin/ncp"
put 0755 userspace/dnlogin/dnlogin "$prefix/bin/dnlogin"
link_to dnlogin "$prefix/bin/sethost"
put 0755 userspace/dncopy/dncopy "$prefix/bin/dncopy"
for alias in dntype dndir dndel dnrename dnsubmit dnprint; do
    link_to dncopy "$prefix/bin/$alias"
done
put 0755 userspace/dntask/dntask "$prefix/bin/dntask"
put 0755 userspace/dnnice/dnnice "$prefix/bin/dnnice"
put 0755 userspace/dnmirror/dnmirror "$prefix/bin/dnmirror"
put 0755 userspace/dnobject/dnobject "$prefix/bin/dnobject"
put 0755 userspace/dnphone/phone "$prefix/bin/phone"
put 0755 userspace/dnmail/dnmail "$prefix/bin/dnmail"
put 0755 userspace/dnlynx/dnlynx "$prefix/bin/dnlynx"
put 0755 userspace/dnping/dnping "$prefix/bin/dnping"

put 0644 userspace/libdnet/libdnet.a "$prefix/lib/libdnet.a"
put 0755 userspace/libdnet/libdnet.so.1.0 "$prefix/lib/libdnet.so.1.0"
link_to libdnet.so.1.0 "$prefix/lib/libdnet.so.1"
link_to libdnet.so.1 "$prefix/lib/libdnet.so"
put 0644 userspace/libdnet/libdnet_daemon.a "$prefix/lib/libdnet_daemon.a"
put 0755 userspace/libdnet/libdnet_daemon.so.1.0 "$prefix/lib/libdnet_daemon.so.1.0"
link_to libdnet_daemon.so.1.0 "$prefix/lib/libdnet_daemon.so.1"
link_to libdnet_daemon.so.1 "$prefix/lib/libdnet_daemon.so"

put 0644 userspace/libdnet/include/netdnet/dn.h "$prefix/include/netdnet/dn.h"
put 0644 userspace/libdnet/include/netdnet/dnetdb.h "$prefix/include/netdnet/dnetdb.h"
put 0644 include/uapi/linux/dn.h "$prefix/include/linux/dn.h"
put 0644 include/uapi/linux/decnet_iv.h "$prefix/include/linux/decnet_iv.h"

for doc in README.md INSTALL.md LICENSE docs/DELIVERY.md docs/FEATURES.md docs/COMPONENTS.md docs/ARCHITECTURE.md; do
    put 0644 "$doc" "$prefix/share/doc/decnet-iv-linux/$(basename "$doc")"
done
if [[ -f SOURCE-METADATA ]]; then
    put 0644 SOURCE-METADATA "$prefix/share/doc/decnet-iv-linux/SOURCE-METADATA"
fi

sort -u "$manifest" >"$manifest_tmp"
chmod 0644 "$manifest_tmp"
mv -f "$manifest_tmp" "$manifest"

if [[ -z "$destdir" ]]; then
    command -v depmod >/dev/null 2>&1 && depmod -a "$kernel_release"
    command -v ldconfig >/dev/null 2>&1 && ldconfig
fi

echo "install.sh: installed manifest $manifest_rel"
