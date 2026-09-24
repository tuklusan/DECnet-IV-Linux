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
    echo "DNIV-AREA31-NATIVE-FAIL reason=$1"
    poweroff -f || true
    exit 1
}

parse_node() {
    case "$1" in
        31.*) ;;
        *) return 1 ;;
    esac
    node=${1#31.}
    case "$node" in
        ''|*[!0-9]*) return 1 ;;
    esac
    [ "$node" -ge 1 ] && [ "$node" -le 1023 ]
}

parse_name() {
    case "$1" in
        [A-Za-z][A-Za-z0-9]|[A-Za-z][A-Za-z0-9][A-Za-z0-9]|[A-Za-z][A-Za-z0-9][A-Za-z0-9][A-Za-z0-9]|[A-Za-z][A-Za-z0-9][A-Za-z0-9][A-Za-z0-9][A-Za-z0-9]|[A-Za-z][A-Za-z0-9][A-Za-z0-9][A-Za-z0-9][A-Za-z0-9][A-Za-z0-9]|[A-Za-z]) return 0 ;;
        *) return 1 ;;
    esac
}

read_field() {
    key=$1
    sed -n "s/^${key}=//p" "$config" | tail -1
}

mkdir -p /run/dniv-area31
device=
for _ in $(seq 1 100); do
    device=$(blkid -L DNIVCTL 2>/dev/null || true)
    [ -n "$device" ] && break
    sleep 0.1
done
[ -n "$device" ] || fail no-control-disk
mount -o ro "$device" /run/dniv-area31 || fail mount-control
config=/run/dniv-area31/dniv-area31.env
[ -r "$config" ] || fail no-control-config

linux_node=$(read_field DNIV_LINUX_NODE)
linux_name=$(read_field DNIV_LINUX_NAME)
gateway_node=$(read_field DNIV_GATEWAY_NODE)
target=$(read_field DNIV_VAX_ADDR)

parse_node "$linux_node" || fail bad-linux-node
parse_node "$gateway_node" || fail bad-gateway-node
parse_node "$target" || fail bad-target
parse_name "$linux_name" || fail bad-linux-name
[ "$linux_node" != "$gateway_node" ] || fail duplicate-node
[ "$linux_node" != "$target" ] || fail duplicate-node
[ "$gateway_node" != "$target" ] || fail duplicate-node

iface=
for _ in $(seq 1 100); do
    for path in /sys/class/net/*; do
        candidate=${path##*/}
        if [ "$candidate" != lo ]; then
            iface=$candidate
            break
        fi
    done
    [ -n "$iface" ] && break
    sleep 0.1
done
[ -n "$iface" ] || fail no-interface

area=31
node=${linux_node#31.}
modprobe decnet_iv default_area="$area" default_node="$node" default_name="$linux_name" \
    default_node_type=3 hello_interval=2 || fail module
/usr/local/sbin/dnctl set "$linux_node" "$linux_name" >/dev/null || fail identity
ip link set "$iface" up || fail link

ready=0
for _ in $(seq 1 320); do
    output=$(/usr/local/sbin/dnctl adjacencies 2>/dev/null || true)
    if printf '%s\n' "$output" | grep -F "$gateway_node via " | grep -Fq ' UP '; then
        ready=1
        break
    fi
    sleep 0.25
done
[ "$ready" -eq 1 ] || fail gateway-adjacency

DNIV_AREA31_TARGET="$target" /usr/local/sbin/dniv-area31-native >/dev/null ||
    fail remote-protocol
echo "DNIV-AREA31-NATIVE-PASS"
sync
poweroff -f || true
