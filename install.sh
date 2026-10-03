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
tmp_manifest=$(mktemp)
trap 'rm -f "$tmp_manifest"' EXIT
[[ "$prefix" == /* && "$module_root" == /* ]] || { echo "install.sh: PREFIX and MODULE_ROOT must be absolute" >&2; exit 2; }
if [[ -z "$destdir" && ${EUID:-$(id -u)} -ne 0 ]]; then echo "install.sh: live installation requires root; use DESTDIR for staging" >&2; exit 2; fi
record() { printf '%s\n' "$1" >>"$tmp_manifest"; }
put() { local mode=$1 source=$2 target=$3; test -e "$source" || { echo "install.sh: missing built artifact: $source" >&2; exit 2; }; install -D -m "$mode" "$source" "$destdir$target"; record "$target"; }
link_to() { local target=$1 link=$2; mkdir -p "$(dirname "$destdir$link")"; ln -sfn "$target" "$destdir$link"; record "$link"; }
put 0644 kernel/decnet/decnet_iv.ko "$module_root/extra/decnet_iv.ko"
for pair in   "userspace/dnctl/dnctl:$prefix/sbin/dnctl"   "userspace/dnetd/dnetd:$prefix/sbin/dnetd"   "userspace/dnfald/dnfald:$prefix/sbin/dnfald"   "userspace/dnnml/dnnml:$prefix/sbin/dnnml"   "userspace/dnphone/dnphoned:$prefix/sbin/dnphoned"   "userspace/dnmail/dnmaild:$prefix/sbin/dnmaild"   "userspace/dnhttpd/dnhttpd:$prefix/sbin/dnhttpd"   "userspace/dnmultinet/dnmultinet.py:$prefix/sbin/dnmultinet"   "userspace/ncp/ncp:$prefix/bin/ncp"   "userspace/dnlogin/dnlogin:$prefix/bin/dnlogin"   "userspace/dncopy/dncopy:$prefix/bin/dncopy"   "userspace/dntask/dntask:$prefix/bin/dntask"   "userspace/dnnice/dnnice:$prefix/bin/dnnice"   "userspace/dnmirror/dnmirror:$prefix/bin/dnmirror"   "userspace/dnobject/dnobject:$prefix/bin/dnobject"   "userspace/dnphone/phone:$prefix/bin/phone"   "userspace/dnmail/dnmail:$prefix/bin/dnmail"   "userspace/dnlynx/dnlynx:$prefix/bin/dnlynx"   "userspace/dnping/dnping:$prefix/bin/dnping"; do
    put 0755 "${pair%%:*}" "${pair#*:}"
done
link_to dnlogin "$prefix/bin/sethost"
for alias in dntype dndir dndel dnrename dnsubmit dnprint; do link_to dncopy "$prefix/bin/$alias"; done
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
for doc in README.md INSTALL.md LICENSE docs/DELIVERY.md docs/FEATURES.md docs/COMPONENTS.md docs/ARCHITECTURE.md; do put 0644 "$doc" "$prefix/share/doc/decnet-iv-linux/$(basename "$doc")"; done
if [[ -f SOURCE-METADATA ]]; then put 0644 SOURCE-METADATA "$prefix/share/doc/decnet-iv-linux/SOURCE-METADATA"; fi
mkdir -p "$(dirname "$manifest")"
sort -u "$tmp_manifest" >"$manifest"
if [[ -z "$destdir" ]]; then command -v depmod >/dev/null 2>&1 && depmod -a "$kernel_release"; command -v ldconfig >/dev/null 2>&1 && ldconfig; fi
echo "install.sh: installed manifest $manifest_rel"
