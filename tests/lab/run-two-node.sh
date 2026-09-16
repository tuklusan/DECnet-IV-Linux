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
    echo "usage: $0 BASE-QCOW2 KERNEL INITRD" >&2
    exit 2
fi
base=$1
kernel=$2
initrd=$3
for file in "$base" "$kernel" "$initrd"; do
    [[ -r "$file" ]] || { echo "two-node: missing $file" >&2; exit 2; }
done

mode=${DNIV_LAB_MODE:-phase2}
case "$mode" in
    phase2|e1) ;;
    *) echo "two-node: invalid DNIV_LAB_MODE: $mode" >&2; exit 2 ;;
esac

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
# shellcheck disable=SC1091
. "$script_dir/test-addresses.env"
area=${DECNET_TEST_AREA:?test-addresses.env must set DECNET_TEST_AREA}
node_a=${DECNET_TEST_FIRST_NODE:?test-addresses.env must set DECNET_TEST_FIRST_NODE}
last_node=${DECNET_TEST_LAST_NODE:?test-addresses.env must set DECNET_TEST_LAST_NODE}
name_prefix=${DECNET_TEST_NAME_PREFIX:?test-addresses.env must set DECNET_TEST_NAME_PREFIX}
if [[ ! "$area" =~ ^[1-9][0-9]*$ ]] || (( area > 63 )); then
    echo "two-node: invalid DECnet area in test-addresses.env" >&2
    exit 2
fi
if [[ ! "$node_a" =~ ^[1-9][0-9]*$ ]] || [[ ! "$last_node" =~ ^[1-9][0-9]*$ ]]; then
    echo "two-node: invalid DECnet node pool in test-addresses.env" >&2
    exit 2
fi
node_b=$((node_a + 1))
if (( node_a > 1023 || node_b > last_node || last_node > 1023 )); then
    echo "two-node: invalid DECnet node pool in test-addresses.env" >&2
    exit 2
fi
name_a="${name_prefix}${node_a}"
name_b="${name_prefix}${node_b}"
if [[ ! "$name_a" =~ ^[A-Za-z0-9]{1,6}$ || ! "$name_b" =~ ^[A-Za-z0-9]{1,6}$ ]]; then
    echo "two-node: generated DECnet node name is invalid" >&2
    exit 2
fi

decnet_mac() {
    local area_value=$1 node_value=$2 address
    address=$(((area_value << 10) | node_value))
    printf 'aa:00:04:00:%02x:%02x' "$((address & 0xff))" "$(((address >> 8) & 0xff))"
}
lab_nic_mac() {
    local area_value=$1 node_value=$2 address
    address=$(((area_value << 10) | node_value))
    printf '52:54:00:00:%02x:%02x' "$((address & 0xff))" "$(((address >> 8) & 0xff))"
}
changed_lab_nic_mac() {
    local area_value=$1 node_value=$2 address
    address=$(((area_value << 10) | node_value))
    printf '52:54:01:00:%02x:%02x' "$((address & 0xff))" "$(((address >> 8) & 0xff))"
}
mac_a=$(decnet_mac "$area" "$node_a")
mac_b=$(decnet_mac "$area" "$node_b")
nic_mac_a=$mac_a
nic_mac_b=$mac_b
changed_mac_a=$nic_mac_a
changed_mac_b=$nic_mac_b
if [[ "$mode" == e1 ]]; then
    # Keep the emulated NIC addresses deliberately different from DECnet node
    # MACs so E1 proves that the kernel emits the protocol-derived source MAC.
    # The guests later change these primary MACs again while DECnet is loaded.
    nic_mac_a=$(lab_nic_mac "$area" "$node_a")
    nic_mac_b=$(lab_nic_mac "$area" "$node_b")
    changed_mac_a=$(changed_lab_nic_mac "$area" "$node_a")
    changed_mac_b=$(changed_lab_nic_mac "$area" "$node_b")
fi

artifacts=${DNIV_LAB_ARTIFACTS:-"$(pwd)/tests/lab/artifacts"}
timeout_seconds=${DNIV_LAB_TIMEOUT_SECONDS:-240}
if [[ ! "$timeout_seconds" =~ ^[1-9][0-9]*$ ]]; then
    echo "two-node: invalid DNIV_LAB_TIMEOUT_SECONDS" >&2
    exit 2
fi
session=${DNIV_LAB_SESSION_ID:-"local-$(date -u +%Y%m%dT%H%M%SZ)-$$"}
[[ "$session" =~ ^[A-Za-z0-9._-]+$ ]] || { echo "two-node: invalid session id" >&2; exit 2; }
mkdir -p "$artifacts/$session"
work="$artifacts/$session"
log_a="$work/node-a.serial.log"
log_b="$work/node-b.serial.log"
pcap="$work/lan.pcap"
disk_a="$work/node-a.qcow2"
disk_b="$work/node-b.qcow2"
resume_dir=${DNIV_LAB_RESUME_DIR:-}

if [[ -n "$resume_dir" ]]; then
    for file in "$resume_dir/base.qcow2" "$resume_dir/node-a.qcow2" \
                "$resume_dir/node-b.qcow2" "$resume_dir/vmlinuz" \
                "$resume_dir/initrd.img" "$resume_dir/session.env" \
                "$resume_dir/SHA256SUMS"; do
        [[ -r "$file" ]] || { echo "two-node: incomplete resume state: $file" >&2; exit 2; }
    done
    if grep -q '^MODE=' "$resume_dir/session.env"; then
        grep -Fx "MODE=$mode" "$resume_dir/session.env" >/dev/null || {
            echo "two-node: resume mode does not match $mode" >&2; exit 2;
        }
    elif [[ "$mode" != phase2 ]]; then
        echo "two-node: legacy checkpoint is valid only for phase2 mode" >&2
        exit 2
    fi
    qemu-img check -q -f qcow2 "$resume_dir/node-a.qcow2"
    qemu-img check -q -f qcow2 "$resume_dir/node-b.qcow2"
    cp --reflink=auto "$resume_dir/node-a.qcow2" "$disk_a"
    cp --reflink=auto "$resume_dir/node-b.qcow2" "$disk_b"
    qemu-img rebase -q -u -f qcow2 -F qcow2 -b "$(readlink -f "$base")" "$disk_a"
    qemu-img rebase -q -u -f qcow2 -F qcow2 -b "$(readlink -f "$base")" "$disk_b"
else
    qemu-img create -q -f qcow2 -F qcow2 -b "$(readlink -f "$base")" "$disk_a"
    qemu-img create -q -f qcow2 -F qcow2 -b "$(readlink -f "$base")" "$disk_b"
fi

suffix=$(printf '%s' "$session" | sha256sum | cut -c1-6)
bridge="br${suffix}"
tap_a="da${suffix}"
tap_b="db${suffix}"

terminate_guest() {
    local pid=$1
    local i

    if ! kill -0 "$pid" 2>/dev/null; then
        wait "$pid" 2>/dev/null || true
        return
    fi
    kill "$pid" 2>/dev/null || true
    for i in {1..50}; do
        if ! kill -0 "$pid" 2>/dev/null; then
            wait "$pid" 2>/dev/null || true
            return
        fi
        sleep 0.1
    done
    kill -KILL "$pid" 2>/dev/null || true
    wait "$pid" 2>/dev/null || true
}

cleanup() {
    set +e
    [[ -n "${QA_PID:-}" ]] && terminate_guest "$QA_PID"
    [[ -n "${QB_PID:-}" ]] && terminate_guest "$QB_PID"
    [[ -n "${TCPDUMP_PID:-}" ]] && sudo kill "$TCPDUMP_PID" 2>/dev/null
    for tap in "$tap_a" "$tap_b"; do sudo ip link del "$tap" 2>/dev/null; done
    sudo ip link del "$bridge" 2>/dev/null
}
trap cleanup EXIT INT TERM

sudo ip link add "$bridge" type bridge
sudo ip link set "$bridge" up
for tap in "$tap_a" "$tap_b"; do
    sudo ip tuntap add dev "$tap" mode tap user "$(id -un)"
    sudo ip link set "$tap" master "$bridge"
    sudo ip link set "$tap" up
done
sudo tcpdump -U -i "$bridge" -w "$pcap" 'ether proto 0x6003' >/dev/null 2>&1 &
TCPDUMP_PID=$!
for _ in {1..50}; do
    [[ -s "$pcap" ]] && break
    if ! kill -0 "$TCPDUMP_PID" 2>/dev/null; then
        echo "two-node: tcpdump exited before capture became ready" >&2
        exit 1
    fi
    sleep 0.1
done
[[ -s "$pcap" ]] || { echo "two-node: packet capture did not become ready" >&2; exit 1; }

host_arch=$(uname -m)
accel=tcg
if [[ -e /dev/kvm && -r /dev/kvm && -w /dev/kvm ]]; then accel=kvm; fi

start_node() {
    local name=$1 node=$2 peer_mac=$3 peer_node=$4 role=$5 mac=$6 tap=$7 disk=$8 log=$9
    local common="root=LABEL=dniv-root rootfstype=ext4 rw dniv.smoke=1 dniv.mode=$mode dniv.area=$area dniv.node=$node dniv.name=$name dniv.peer=$peer_mac dniv.peer_node=$area.$peer_node dniv.role=$role dniv.session=$session"
    case "$host_arch" in
        x86_64)
            exec qemu-system-x86_64 -name "$name" -accel "$accel" -m 512 -smp 1 \
                -kernel "$kernel" -initrd "$initrd" \
                -append "$common console=ttyS0" \
                -drive "file=$disk,if=virtio,format=qcow2" \
                -netdev tap,id=lan,ifname="$tap",script=no,downscript=no \
                -device virtio-net-pci,netdev=lan,mac="$mac" \
                -display none -monitor none -serial "file:$log" -no-reboot
            ;;
        aarch64)
            local cpu=max
            [[ "$accel" == kvm ]] && cpu=host
            exec qemu-system-aarch64 -name "$name" -machine virt -accel "$accel" -cpu "$cpu" -m 512 -smp 1 \
                -kernel "$kernel" -initrd "$initrd" \
                -append "$common console=ttyAMA0" \
                -drive "file=$disk,if=virtio,format=qcow2" \
                -netdev tap,id=lan,ifname="$tap",script=no,downscript=no \
                -device virtio-net-pci,netdev=lan,mac="$mac" \
                -display none -monitor none -serial "file:$log" -no-reboot
            ;;
        *) echo "two-node: unsupported host architecture: $host_arch" >&2; return 2 ;;
    esac
}

start_node "$name_a" "$node_a" "$mac_b" "$node_b" A "$nic_mac_a" "$tap_a" "$disk_a" "$log_a" & QA_PID=$!
start_node "$name_b" "$node_b" "$mac_a" "$node_a" B "$nic_mac_b" "$tap_b" "$disk_b" "$log_b" & QB_PID=$!

if [[ "$mode" == e1 ]]; then
    marker=DNIV-E1-PASS
else
    marker=DNIV-LAB-PASS
fi
deadline=$((SECONDS + timeout_seconds))
pass_a=0
pass_b=0
while (( SECONDS < deadline )); do
    grep -Fq "$marker session=$session node=$name_a" "$log_a" 2>/dev/null && pass_a=1
    grep -Fq "$marker session=$session node=$name_b" "$log_b" 2>/dev/null && pass_b=1
    if (( pass_a && pass_b )); then break; fi
    if ! kill -0 "$QA_PID" 2>/dev/null && (( ! pass_a )); then
        grep -Fq "$marker session=$session node=$name_a" "$log_a" 2>/dev/null && pass_a=1
        (( pass_a )) || { echo "two-node: $name_a exited before pass" >&2; break; }
    fi
    if ! kill -0 "$QB_PID" 2>/dev/null && (( ! pass_b )); then
        grep -Fq "$marker session=$session node=$name_b" "$log_b" 2>/dev/null && pass_b=1
        (( pass_b )) || { echo "two-node: $name_b exited before pass" >&2; break; }
    fi
    sleep 1
done

if (( pass_a && pass_b )); then sleep 3; fi
terminate_guest "$QA_PID"
terminate_guest "$QB_PID"
unset QA_PID QB_PID
sudo kill "$TCPDUMP_PID" 2>/dev/null || true
wait "$TCPDUMP_PID" 2>/dev/null || true
unset TCPDUMP_PID

checkpoint="$work/checkpoint"
mkdir -p "$checkpoint"
cp --reflink=auto "$base" "$checkpoint/base.qcow2"
cp --reflink=auto "$kernel" "$checkpoint/vmlinuz"
cp --reflink=auto "$initrd" "$checkpoint/initrd.img"
qemu-img convert -q -f qcow2 -O qcow2 -B "$checkpoint/base.qcow2" -F qcow2 \
    "$disk_a" "$checkpoint/node-a.qcow2"
qemu-img convert -q -f qcow2 -O qcow2 -B "$checkpoint/base.qcow2" -F qcow2 \
    "$disk_b" "$checkpoint/node-b.qcow2"
(
    cd "$checkpoint"
    qemu-img rebase -q -u -f qcow2 -F qcow2 -b base.qcow2 node-a.qcow2
    qemu-img rebase -q -u -f qcow2 -F qcow2 -b base.qcow2 node-b.qcow2
    qemu-img check -q -f qcow2 node-a.qcow2
    qemu-img check -q -f qcow2 node-b.qcow2
    sha256sum base.qcow2 node-a.qcow2 node-b.qcow2 vmlinuz initrd.img > SHA256SUMS
)
{
    printf 'FORMAT=1\n'
    printf 'MODE=%s\n' "$mode"
    printf 'SESSION_ID=%s\n' "$session"
    printf 'ARCH=%s\n' "${DNIV_LAB_ARCH:-$host_arch}"
    printf 'SOURCE_SHA=%s\n' "${DNIV_LAB_SOURCE_SHA:-local}"
    printf 'SOURCE_RUN_ID=%s\n' "${DNIV_LAB_SOURCE_RUN_ID:-local}"
    printf 'SOURCE_RUN_ATTEMPT=%s\n' "${DNIV_LAB_SOURCE_RUN_ATTEMPT:-1}"
    printf 'RESUME_PARENT_RUN_ID=%s\n' "${DNIV_LAB_RESUME_RUN_ID:-}"
} > "$checkpoint/session.env"

if (( ! pass_a || ! pass_b )); then
    echo "--- $name_a ---" >&2; tail -160 "$log_a" >&2 || true
    echo "--- $name_b ---" >&2; tail -160 "$log_b" >&2 || true
    exit 1
fi

frames=$(sudo tcpdump -nn -r "$pcap" 'ether proto 0x6003' 2>/dev/null | wc -l)
if (( frames < 2 )); then
    echo "two-node: expected captured DECnet frames, saw $frames" >&2
    exit 1
fi

if [[ "$mode" == e1 ]]; then
    routers_from_a=$(sudo tcpdump -nn -e -r "$pcap" \
        "ether proto 0x6003 and ether dst ab:00:00:03:00:00 and ether src $mac_a" 2>/dev/null | wc -l)
    routers_from_b=$(sudo tcpdump -nn -e -r "$pcap" \
        "ether proto 0x6003 and ether dst ab:00:00:03:00:00 and ether src $mac_b" 2>/dev/null | wc -l)
    endnodes_from_a=$(sudo tcpdump -nn -e -r "$pcap" \
        "ether proto 0x6003 and ether dst ab:00:00:04:00:00 and ether src $mac_a" 2>/dev/null | wc -l)
    endnodes_from_b=$(sudo tcpdump -nn -e -r "$pcap" \
        "ether proto 0x6003 and ether dst ab:00:00:04:00:00 and ether src $mac_b" 2>/dev/null | wc -l)
    nic_hello_a=$(sudo tcpdump -nn -e -r "$pcap" \
        "ether proto 0x6003 and ether src $nic_mac_a and (ether dst ab:00:00:03:00:00 or ether dst ab:00:00:04:00:00)" 2>/dev/null | wc -l)
    nic_hello_b=$(sudo tcpdump -nn -e -r "$pcap" \
        "ether proto 0x6003 and ether src $nic_mac_b and (ether dst ab:00:00:03:00:00 or ether dst ab:00:00:04:00:00)" 2>/dev/null | wc -l)
    changed_nic_hello_a=$(sudo tcpdump -nn -e -r "$pcap" \
        "ether proto 0x6003 and ether src $changed_mac_a and (ether dst ab:00:00:03:00:00 or ether dst ab:00:00:04:00:00)" 2>/dev/null | wc -l)
    changed_nic_hello_b=$(sudo tcpdump -nn -e -r "$pcap" \
        "ether proto 0x6003 and ether src $changed_mac_b and (ether dst ab:00:00:03:00:00 or ether dst ab:00:00:04:00:00)" 2>/dev/null | wc -l)
    ucast_a_to_b=$(sudo tcpdump -nn -e -r "$pcap" \
        "ether proto 0x6003 and ether src $changed_mac_a and ether dst $mac_b" 2>/dev/null | wc -l)
    ucast_b_to_a=$(sudo tcpdump -nn -e -r "$pcap" \
        "ether proto 0x6003 and ether src $changed_mac_b and ether dst $mac_a" 2>/dev/null | wc -l)
    if (( routers_from_a < 2 || routers_from_b < 2 || endnodes_from_a != 0 || endnodes_from_b < 1 || nic_hello_a != 0 || nic_hello_b != 0 || changed_nic_hello_a != 0 || changed_nic_hello_b != 0 || ucast_a_to_b < 3 || ucast_b_to_a < 3 )); then
        echo "two-node: E1 wire evidence incomplete routersA=$routers_from_a routersB=$routers_from_b endnodesA=$endnodes_from_a endnodesB=$endnodes_from_b nicHelloA=$nic_hello_a nicHelloB=$nic_hello_b changedNicHelloA=$changed_nic_hello_a changedNicHelloB=$changed_nic_hello_b ucastAB=$ucast_a_to_b ucastBA=$ucast_b_to_a" >&2
        exit 1
    fi
    grep -Fq "DNIV-E1-CHANGEADDR session=$session node=$name_a mac=$changed_mac_a" "$log_a" || {
        echo "two-node: E1 node A primary-MAC change was not observed" >&2
        exit 1
    }
    grep -Fq "DNIV-E1-CHANGEADDR session=$session node=$name_b mac=$changed_mac_b" "$log_b" || {
        echo "two-node: E1 node B primary-MAC change was not observed" >&2
        exit 1
    }
    grep -Fq "DNIV-E1-UCAST session=$session node=$name_a" "$log_a" || {
        echo "two-node: E1 node A unicast receive-filter proof was not observed" >&2
        exit 1
    }
    grep -Fq "DNIV-E1-UCAST session=$session node=$name_b" "$log_b" || {
        echo "two-node: E1 node B unicast receive-filter proof was not observed" >&2
        exit 1
    }
    if ! grep -Fq "DNIV-E1-INIT session=$session" "$log_a" && \
       ! grep -Fq "DNIV-E1-INIT session=$session" "$log_b"; then
        echo "two-node: E1 initial INIT state was not observed" >&2
        exit 1
    fi
    grep -Fq "DNIV-E1-EXPIRED session=$session node=$name_b" "$log_b" || {
        echo "two-node: E1 listener expiry was not observed" >&2
        exit 1
    }
    if ! grep -Fq "DNIV-E1-RESTART-INIT session=$session" "$log_a" && \
       ! grep -Fq "DNIV-E1-RESTART-INIT session=$session" "$log_b"; then
        echo "two-node: E1 restart INIT state was not observed" >&2
        exit 1
    fi
    grep -Fq "DNIV-E1-RECOVERED session=$session node=$name_a" "$log_a" || {
        echo "two-node: E1 node A recovery was not observed" >&2
        exit 1
    }
    grep -Fq "DNIV-E1-RECOVERED session=$session node=$name_b" "$log_b" || {
        echo "two-node: E1 node B recovery was not observed" >&2
        exit 1
    }
    echo "two-node: E1 pass on $host_arch for $area.$node_a/$area.$node_b, captured $frames DECnet frames"
else
    echo "two-node: Phase 2 pass on $host_arch for $area.$node_a/$area.$node_b, captured $frames DECnet routing frames"
fi
