#!/bin/sh
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

set -eu

fail() {
    echo "DNIV-PP12-LIFECYCLE-FAIL reason=$1"
    poweroff -f || true
    exit 1
}

source_root=/usr/src/decnet-iv-linux
state_dir=/var/lib/dniv-pp12
stage_file=$state_dir/stage
mkdir -p "$state_dir"
[ -r /etc/dniv-source-release-sha ] || fail no-source-sha
expected=$(cat /etc/dniv-source-release-sha)
grep -Fqx "source_sha=$expected" "$source_root/SOURCE-METADATA" || fail source-metadata

iface=
for _ in $(seq 1 100); do
    for path in /sys/class/net/*; do
        candidate=${path##*/}
        [ "$candidate" = lo ] && continue
        iface=$candidate
        break
    done
    [ -n "$iface" ] && break
    sleep 0.1
done
[ -n "$iface" ] || fail no-interface

stage=0
[ ! -r "$stage_file" ] || stage=$(cat "$stage_file" 2>/dev/null || printf 0)
case "$stage" in 0|1) ;; *) fail bad-stage ;; esac

if [ "$stage" -eq 0 ]; then
    ip link set "$iface" down || fail link-down
    modprobe decnet_iv default_area=31 default_node=950 default_name=P12A default_node_type=3 hello_interval=2 || fail module-load-1
    /usr/local/sbin/dnctl set 31.950 P12A >/dev/null || fail identity-1
    /usr/local/sbin/dnctl show >/dev/null || fail show-1
    ip link set "$iface" up || fail link-up
    ip link set "$iface" down || fail link-down-2
    modprobe -r decnet_iv || fail module-unload-1
    ! grep -Fq '^decnet_iv ' /proc/modules || fail module-still-loaded-1
    printf '1\n' >"$stage_file"
    sync
    echo "DNIV-PP12-BOOT1-PASS source=$expected iface=$iface"
    reboot -f
    exit 0
fi

manifest=/usr/local/share/decnet-iv-linux/install-manifest.txt
[ -s "$manifest" ] || fail no-manifest
sha256sum -c /etc/dniv-pp12-manifest-first.sha256 >/dev/null || fail reinstall-manifest
modprobe decnet_iv default_area=31 default_node=950 default_name=P12A default_node_type=3 hello_interval=2 || fail module-load-2
/usr/local/sbin/dnctl set 31.950 P12A >/dev/null || fail identity-2
/usr/local/sbin/dnctl stats >/dev/null || fail stats-2
ip link set "$iface" down || fail link-down-3
modprobe -r decnet_iv || fail module-unload-2

cd "$source_root"
krel=$(uname -r)
KERNEL_RELEASE="$krel" ./uninstall.sh || fail live-uninstall
[ ! -e /usr/local/bin/ncp ] || fail uninstall-ncp
[ ! -e "/lib/modules/$krel/extra/decnet_iv.ko" ] || fail uninstall-module
KERNEL_RELEASE="$krel" ./install.sh || fail live-reinstall
[ -s /usr/local/bin/ncp ] || fail reinstall-ncp
[ -s "/lib/modules/$krel/extra/decnet_iv.ko" ] || fail reinstall-module
sha256sum -c /etc/dniv-pp12-manifest-first.sha256 >/dev/null || fail reinstall-manifest-2

/usr/local/bin/ncp --selftest >/dev/null || fail selftest-ncp
/usr/local/bin/dnlogin --selftest >/dev/null || fail selftest-dnlogin
/usr/local/bin/sethost --selftest >/dev/null || fail selftest-sethost
/usr/local/bin/dncopy --selftest >/dev/null || fail selftest-dncopy
/usr/local/bin/dntask --selftest >/dev/null || fail selftest-dntask
/usr/local/bin/dnping --selftest >/dev/null || fail selftest-dnping
/usr/local/bin/dnlynx --selftest >/dev/null || fail selftest-dnlynx
/usr/local/bin/phone --selftest >/dev/null || fail selftest-phone
/usr/local/bin/dnmail --selftest >/dev/null || fail selftest-dnmail

depmod "$krel" || fail depmod
modprobe decnet_iv default_area=31 default_node=950 default_name=P12A default_node_type=3 hello_interval=2 || fail module-load-3
/usr/local/sbin/dnctl set 31.950 P12A >/dev/null || fail identity-3
/usr/local/sbin/dnctl show >/dev/null || fail show-3
ip link set "$iface" down || fail link-down-4
modprobe -r decnet_iv || fail module-unload-3

rm -f "$stage_file"
sync
echo "DNIV-PP12-LIFECYCLE-PASS source=$expected kernel=$krel"
poweroff -f || true
