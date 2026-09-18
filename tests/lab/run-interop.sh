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

if [[ $# -ne 7 ]]; then
    echo "usage: $0 BASE-QCOW2 REFERENCE-QCOW2 KERNEL INITRD REFERENCE BUNDLE-DIR SCENARIO" >&2
    exit 2
fi
base=$1
ref_base=$2
kernel=$3
initrd=$4
reference=$5
bundle=$6
scenario=$7
case "$reference" in route20|pydecnet) ;; *) echo "interop: bad reference: $reference" >&2; exit 2 ;; esac
case "$scenario" in l1|l2|endnode|router-endnode) ;; *) echo "interop: bad scenario: $scenario" >&2; exit 2 ;; esac
if [[ "$scenario" == router-endnode && "$reference" != pydecnet ]]; then
    echo "interop: router-endnode requires pydecnet" >&2
    exit 2
fi
for file in "$base" "$ref_base" "$kernel" "$initrd" "$bundle/manifest.env" "$bundle/SHA256SUMS"; do
    [[ -r "$file" ]] || { echo "interop: missing $file" >&2; exit 2; }
done

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
# shellcheck disable=SC1091
. "$script_dir/../reference/refs.env"
case "$reference" in
    route20) expected_sha=$ROUTE20_REF ;;
    pydecnet) expected_sha=$PYDECNET_REF ;;
esac
grep -Fx "REFERENCE=$reference" "$bundle/manifest.env" >/dev/null
grep -Fx "REFERENCE_SHA=$expected_sha" "$bundle/manifest.env" >/dev/null
(cd "$bundle" && sha256sum -c SHA256SUMS)

area=31
node=70
ref_area=31
ref_node=71
if [[ "$scenario" == l2 ]]; then ref_area=32; fi
name=DN70
ref_name=DN71
addr=$((area * 1024 + node))
ref_addr=$((ref_area * 1024 + ref_node))
printf -v candidate_mac 'aa:00:04:00:%02x:%02x' "$((addr & 255))" "$(((addr >> 8) & 255))"
printf -v reference_mac 'aa:00:04:00:%02x:%02x' "$((ref_addr & 255))" "$(((ref_addr >> 8) & 255))"
printf -v candidate_hw '52:54:00:00:%02x:%02x' "$((addr & 255))" "$(((addr >> 8) & 255))"
printf -v candidate_changed_hw '52:54:01:00:%02x:%02x' "$((addr & 255))" "$(((addr >> 8) & 255))"
printf -v reference_hw '52:54:00:00:%02x:%02x' "$((ref_addr & 255))" "$(((ref_addr >> 8) & 255))"

artifacts=${DNIV_INTEROP_ARTIFACTS:-"$(pwd)/tests/lab/artifacts"}
timeout_seconds=${DNIV_INTEROP_TIMEOUT_SECONDS:-420}
[[ "$timeout_seconds" =~ ^[1-9][0-9]*$ ]] || { echo "interop: bad timeout" >&2; exit 2; }
session=${DNIV_INTEROP_SESSION_ID:-"local-$(date -u +%Y%m%dT%H%M%SZ)-$$-$reference-$scenario"}
[[ "$session" =~ ^[A-Za-z0-9._-]+$ ]] || { echo "interop: bad session id" >&2; exit 2; }
work="$artifacts/$session"
mkdir -p "$work"
pcap="$work/lan.pcap"
candidate_log="$work/candidate.serial.log"
ref1_log="$work/reference-1.serial.log"
ref2_log="$work/reference-2.serial.log"
candidate_disk="$work/candidate.qcow2"
ref1_disk="$work/reference-1.qcow2"
ref2_disk="$work/reference-2.qcow2"
qemu-img create -q -f qcow2 -F qcow2 -b "$(readlink -f "$base")" "$candidate_disk"
qemu-img create -q -f qcow2 -F qcow2 -b "$(readlink -f "$ref_base")" "$ref1_disk"
qemu-img create -q -f qcow2 -F qcow2 -b "$(readlink -f "$ref_base")" "$ref2_disk"

suffix=$(printf '%s' "$session" | sha256sum | cut -c1-6)
bridge="bi${suffix}"
tap_candidate="ci${suffix}"
tap_reference="ri${suffix}"

terminate_pid() {
    local pid=${1:-}
    [[ -n "$pid" ]] || return 0
    if kill -0 "$pid" 2>/dev/null; then
        kill "$pid" 2>/dev/null || true
        for _ in {1..30}; do
            kill -0 "$pid" 2>/dev/null || break
            sleep 0.1
        done
        kill -KILL "$pid" 2>/dev/null || true
    fi
    wait "$pid" 2>/dev/null || true
}
cleanup() {
    set +e
    terminate_pid "${CANDIDATE_PID:-}"
    terminate_pid "${REFERENCE_PID:-}"
    [[ -n "${TCPDUMP_PID:-}" ]] && sudo kill "$TCPDUMP_PID" 2>/dev/null
    sudo ip link del "$tap_candidate" 2>/dev/null
    sudo ip link del "$tap_reference" 2>/dev/null
    sudo ip link del "$bridge" 2>/dev/null
}
trap cleanup EXIT INT TERM

sudo ip link add "$bridge" type bridge
sudo ip link set "$bridge" up
for tap in "$tap_candidate" "$tap_reference"; do
    sudo ip tuntap add dev "$tap" mode tap user "$(id -un)"
    sudo ip link set "$tap" master "$bridge"
    sudo ip link set "$tap" up
done
sudo tcpdump -U -i "$bridge" -w "$pcap" 'ether proto 0x6003' >/dev/null 2>&1 &
TCPDUMP_PID=$!
sleep 1
kill -0 "$TCPDUMP_PID"

host_arch=$(uname -m)
reference_ready_seconds=180
if [[ "$host_arch" == aarch64 ]]; then
    reference_ready_seconds=360
fi
accel=tcg
if [[ -e /dev/kvm && -r /dev/kvm && -w /dev/kvm ]]; then accel=kvm; fi

start_vm() {
    local role=$1 disk=$2 tap=$3 hw=$4 log=$5 common=$6
    case "$host_arch" in
        x86_64)
            exec qemu-system-x86_64 -name "$role" -accel "$accel" -m 512 -smp 1 \
                -kernel "$kernel" -initrd "$initrd" -append "$common console=ttyS0" \
                -drive "file=$disk,if=virtio,format=qcow2" \
                -netdev tap,id=lan,ifname="$tap",script=no,downscript=no \
                -device virtio-net-pci,netdev=lan,mac="$hw" \
                -display none -monitor none -serial "file:$log" -no-reboot
            ;;
        aarch64)
            local cpu=max machine=virt,gic-version=3
            if [[ "$accel" == kvm ]]; then
                cpu=host
                machine=virt,gic-version=host
            fi
            exec qemu-system-aarch64 -name "$role" -machine "$machine" -accel "$accel" -cpu "$cpu" -m 1024 -smp 1 \
                -kernel "$kernel" -initrd "$initrd" -append "$common earlycon=pl011,0x09000000 console=ttyAMA0" \
                -drive "file=$disk,if=virtio,format=qcow2" \
                -netdev tap,id=lan,ifname="$tap",script=no,downscript=no \
                -device virtio-net-pci,netdev=lan,mac="$hw" \
                -display none -monitor none -serial "file:$log" -no-reboot
            ;;
        *) echo "interop: unsupported host architecture: $host_arch" >&2; return 2 ;;
    esac
}

start_reference() {
    local disk=$1 log=$2
    local common="root=LABEL=dniv-root rootfstype=ext4 rw dniv.reference=$reference dniv.ref_sha=$expected_sha dniv.area=$ref_area dniv.node=$ref_node dniv.name=$ref_name dniv.peer=$candidate_mac dniv.peer_node=$area.$node dniv.scenario=$scenario dniv.session=$session"
    case "$host_arch" in
        x86_64)
            exec qemu-system-x86_64 -name "ref-$reference-$scenario" -accel "$accel" -m 512 -smp 1 \
                -kernel "$kernel" -initrd "$initrd" -append "$common console=ttyS0" \
                -drive "file=$disk,if=virtio,format=qcow2" \
                -drive "file=fat:ro:$bundle,if=virtio,format=raw,readonly=on" \
                -netdev tap,id=lan,ifname="$tap_reference",script=no,downscript=no \
                -device virtio-net-pci,netdev=lan,mac="$reference_hw" \
                -display none -monitor none -serial "file:$log" -no-reboot
            ;;
        aarch64)
            local cpu=max machine=virt,gic-version=3
            if [[ "$accel" == kvm ]]; then
                cpu=host
                machine=virt,gic-version=host
            fi
            exec qemu-system-aarch64 -name "ref-$reference-$scenario" -machine "$machine" -accel "$accel" -cpu "$cpu" -m 1024 -smp 1 \
                -kernel "$kernel" -initrd "$initrd" -append "$common earlycon=pl011,0x09000000 console=ttyAMA0" \
                -drive "file=$disk,if=virtio,format=qcow2" \
                -drive "file=fat:ro:$bundle,if=virtio,format=raw,readonly=on" \
                -netdev tap,id=lan,ifname="$tap_reference",script=no,downscript=no \
                -device virtio-net-pci,netdev=lan,mac="$reference_hw" \
                -display none -monitor none -serial "file:$log" -no-reboot
            ;;
    esac
}

wait_marker() {
    local log=$1 marker=$2 seconds=$3 pid=${4:-} peer_pid=${5:-}
    local deadline=$((SECONDS + seconds))
    while (( SECONDS < deadline )); do
        grep -Fq "$marker" "$log" 2>/dev/null && return 0
        if [[ -n "$pid" ]] && ! kill -0 "$pid" 2>/dev/null; then
            return 1
        fi
        if [[ -n "$peer_pid" ]] && ! kill -0 "$peer_pid" 2>/dev/null; then
            return 1
        fi
        sleep 1
    done
    return 1
}


wait_candidate_marker() {
    local log=$1 marker=$2 seconds=$3 candidate_pid=$4 reference_pid=$5 reference_log=$6
    local deadline=$((SECONDS + seconds))
    local fail_marker="DNIV-REF-FAIL session=$session"
    while (( SECONDS < deadline )); do
        if grep -Fq "$fail_marker" "$reference_log" 2>/dev/null; then
            return 1
        fi
        grep -Fq "$marker" "$log" 2>/dev/null && return 0
        kill -0 "$candidate_pid" 2>/dev/null || return 1
        kill -0 "$reference_pid" 2>/dev/null || return 1
        sleep 1
    done
    return 1
}

start_reference "$ref1_disk" "$ref1_log" & REFERENCE_PID=$!
if ! wait_marker "$ref1_log" "DNIV-REF-READY session=$session reference=$reference sha=$expected_sha scenario=$scenario" "$reference_ready_seconds" "$REFERENCE_PID"; then
    tail -160 "$ref1_log" >&2 || true
    exit 1
fi

candidate_common="root=LABEL=dniv-root rootfstype=ext4 rw dniv.interop=1 dniv.area=$area dniv.node=$node dniv.name=$name dniv.peer_node=$ref_area.$ref_node dniv.scenario=$scenario dniv.session=$session"
start_vm "candidate-$scenario" "$candidate_disk" "$tap_candidate" "$candidate_hw" "$candidate_log" "$candidate_common" & CANDIDATE_PID=$!
if ! wait_candidate_marker "$candidate_log" "DNIV-INTEROP-READY-STOP session=$session scenario=$scenario" "$timeout_seconds" "$CANDIDATE_PID" "$REFERENCE_PID" "$ref1_log"; then
    tail -220 "$candidate_log" >&2 || true
    tail -160 "$ref1_log" >&2 || true
    exit 1
fi

kill -KILL "$REFERENCE_PID" 2>/dev/null || true
wait "$REFERENCE_PID" 2>/dev/null || true
unset REFERENCE_PID
if ! wait_marker "$candidate_log" "DNIV-INTEROP-EXPIRED session=$session scenario=$scenario" 150 "$CANDIDATE_PID"; then
    tail -220 "$candidate_log" >&2 || true
    exit 1
fi

start_reference "$ref2_disk" "$ref2_log" & REFERENCE_PID=$!
if ! wait_marker "$ref2_log" "DNIV-REF-READY session=$session reference=$reference sha=$expected_sha scenario=$scenario" "$reference_ready_seconds" "$REFERENCE_PID"; then
    tail -160 "$ref2_log" >&2 || true
    exit 1
fi
if ! wait_candidate_marker "$candidate_log" "DNIV-INTEROP-PASS session=$session scenario=$scenario" 180 "$CANDIDATE_PID" "$REFERENCE_PID" "$ref2_log"; then
    tail -220 "$candidate_log" >&2 || true
    tail -160 "$ref2_log" >&2 || true
    exit 1
fi

wait "$CANDIDATE_PID" 2>/dev/null || true
unset CANDIDATE_PID
terminate_pid "$REFERENCE_PID"
unset REFERENCE_PID
sudo kill "$TCPDUMP_PID" 2>/dev/null || true
wait "$TCPDUMP_PID" 2>/dev/null || true
unset TCPDUMP_PID

python3 "$script_dir/validate-interop-pcap.py" "$pcap" "$reference" "$scenario" \
    "$candidate_mac" "$candidate_hw" "$candidate_changed_hw" \
    "$reference_mac" "$reference_hw"

grep -Fq "DNIV-INTEROP-RECOVERED session=$session scenario=$scenario" "$candidate_log"
! grep -Fq 'DNIV-INTEROP-FAIL' "$candidate_log"
! grep -Fq 'DNIV-REF-FAIL' "$ref1_log"
! grep -Fq 'DNIV-REF-FAIL' "$ref2_log"
echo "interop: pass reference=$reference scenario=$scenario arch=$host_arch"
