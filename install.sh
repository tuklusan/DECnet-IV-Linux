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
kernel_release=${KERNEL_RELEASE:-$(uname -r)}
module_root=${MODULE_ROOT:-/lib/modules/$kernel_release}
manifest_rel="$prefix/share/decnet-iv-linux/install-manifest.txt"
manifest="$destdir$manifest_rel"
manifest_tmp="$manifest.tmp.$$"

[[ -z "$destdir" || "$destdir" == /* ]] || {
    echo "install.sh: DESTDIR must be empty or absolute" >&2
    exit 2
}
[[ "$prefix" == /* && "$prefix" != / && "$module_root" == /* && "$module_root" != / ]] || {
    echo "install.sh: PREFIX and MODULE_ROOT must be absolute non-root paths" >&2
    exit 2
}
if [[ -z "$destdir" && ${EUID:-$(id -u)} -ne 0 ]]; then
    echo "install.sh: live installation requires root; use DESTDIR for staging" >&2
    exit 2
fi

safe_managed_path() {
    local path=$1
    [[ "$path" == /* && "$path" != *"/../"* && "$path" != *"/.." ]] || return 1
    case "$path" in
        "$prefix"/*|"$module_root"/*) return 0 ;;
        *) return 1 ;;
    esac
}

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
    if [[ -e "$full" || -L "$full" ]]; then
        managed "$target" || {
            echo "install.sh: refusing unmanaged existing target: $target" >&2
            exit 2
        }
    fi
}

record() {
    local target=$1
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
    [[ ! -L "$destdir$target" ]] || {
        echo "install.sh: refusing symlink at regular-file target: $target" >&2
        exit 2
    }
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

put 0644 kernel/decnet/decnet_iv.ko "$module_root/extra/decnet_iv.ko"

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
