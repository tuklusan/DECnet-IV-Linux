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
# PyDECnet's independent peer uses its native Linux TAP backend directly on
# the host bridge, avoiding the architecture-sensitive guest virtio+pcap path.
# Keep the TAP device's Linux MAC distinct from the DECnet logical MAC: making
# them identical creates a local bridge FDB entry and traps DECnet unicast in
# the host instead of delivering it to the TAP queue. Route20 retains the
# independent guest/pcap path.
if [[ "$reference" == pydecnet ]]; then
    reference_hw=$reference_mac
fi

artifacts=${DNIV_INTEROP_ARTIFACTS:-"$(pwd)/tests/lab/artifacts"}
timeout_seconds=${DNIV_INTEROP_TIMEOUT_SECONDS:-}
if [[ -z "$timeout_seconds" ]]; then
    timeout_seconds=420
    if [[ "$(uname -m)" == aarch64 ]]; then
        timeout_seconds=720
    fi
fi
[[ "$timeout_seconds" =~ ^[1-9][0-9]*$ ]] || { echo "interop: bad timeout" >&2; exit 2; }
session=${DNIV_INTEROP_SESSION_ID:-"local-$(date -u +%Y%m%dT%H%M%SZ)-$-$reference-$scenario"}
[[ "$session" =~ ^[A-Za-z0-9._-]+$ ]] || { echo "interop: bad session id" >&2; exit 2; }
timer_proof=${DNIV_INTEROP_TIMER_PROOF:-0}
[[ "$timer_proof" =~ ^[01]$ ]] || { echo "interop: bad timer-proof selector" >&2; exit 2; }
peer_segsize=${DNIV_INTEROP_PEER_SEGMENT_SIZE:-0}
[[ "$peer_segsize" =~ ^[0-9]+$ ]] || { echo "interop: bad peer segment size" >&2; exit 2; }
flow_proof=${DNIV_INTEROP_FLOW_PROOF:-0}
[[ "$flow_proof" =~ ^[01]$ ]] || { echo "interop: bad flow-proof selector" >&2; exit 2; }
if (( peer_segsize != 0 && (peer_segsize < 64 || peer_segsize > 563) )); then
    echo "interop: peer segment size out of bounded proof range" >&2
    exit 2
fi
reserved_proof=0
if [[ "$reference" == pydecnet && "$scenario" == l1 && "$(uname -m)" == x86_64 ]]; then
    reserved_proof=1
fi
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
host_pydecnet_api="/tmp/dniv-api-${suffix}.sock"
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
    terminate_pid "${HOST_PROBE_PID:-}"
    terminate_pid "${CCRETRY_PID:-}"
    if [[ -n "${LOSS_QDISC:-}" || -n "${RESERVED_QDISC:-}" ]]; then
        sudo tc qdisc del dev "$tap_reference" clsact 2>/dev/null || true
    fi
    rm -f "${host_pydecnet_api:-}"
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

if [[ "$reference" == pydecnet ]]; then
    host_dnraw="$work/dnraw-host"
    cc -O2 -Wall -Wextra "$script_dir/dnraw.c" -o "$host_dnraw"
    (
        probe_i=0
        while :; do
            probe_i=$((probe_i + 1))
            sudo "$host_dnraw" "$bridge" "$candidate_mac"                 "DNIV-INTEROP-PROBE-$session-$scenario-host-$probe_i" || true
            sleep 0.5
        done
    ) &
    HOST_PROBE_PID=$!
fi

host_arch=$(uname -m)
reference_ready_seconds=180
if [[ "$host_arch" == aarch64 ]]; then
    reference_ready_seconds=600
fi
if [[ "$reference" == pydecnet ]]; then
    reference_ready_seconds=60
    host_pydecnet="$work/host-pydecnet"
    mkdir -p "$host_pydecnet"
    tar -xf "$bundle/pydecnet.tar" -C "$host_pydecnet"
    if (( peer_segsize != 0 )); then
        cat > "$host_pydecnet/pydecnet/sitecustomize.py" <<EOF_SITE
import decnet.common as _dniv_common
_dniv_common.MSS = $peer_segsize
EOF_SITE
    fi
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
    if [[ "$reference" == pydecnet ]]; then
        local py_type=l1router
        [[ "$scenario" == l2 ]] && py_type=l2router
        [[ "$scenario" == router-endnode ]] && py_type=endnode
        cat > "$host_pydecnet/pydecnet.conf" <<EOF_PYDECNET
routing $ref_area.$ref_node --type $py_type
node $ref_area.$ref_node $ref_name
node $area.$node $name
circuit ETH-0 Ethernet $tap_reference --mode tap --cost 3 --t3 2 --priority 64
EOF_PYDECNET
        cat > "$host_pydecnet/api.conf" <<EOF_API
api $host_pydecnet_api --mode 600
EOF_API
        rm -f "$host_pydecnet_api"
        : > "$log"
        cd "$host_pydecnet/pydecnet"
        exec env PYTHONPATH=. python3 -u -m decnet.main \
            "$host_pydecnet/pydecnet.conf" "$host_pydecnet/api.conf" >>"$log" 2>&1
    fi
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
reference_ready_marker="DNIV-REF-READY session=$session reference=$reference sha=$expected_sha scenario=$scenario"
if [[ "$reference" == pydecnet ]]; then
    reference_ready_marker='DECnet/Python is running'
fi
if ! wait_marker "$ref1_log" "$reference_ready_marker" "$reference_ready_seconds" "$REFERENCE_PID"; then
    tail -160 "$ref1_log" >&2 || true
    exit 1
fi

candidate_common="root=LABEL=dniv-root rootfstype=ext4 rw dniv.interop=1 dniv.reference=$reference dniv.area=$area dniv.node=$node dniv.name=$name dniv.peer_node=$ref_area.$ref_node dniv.scenario=$scenario dniv.session=$session dniv.timer_proof=$timer_proof dniv.reserved_proof=$reserved_proof dniv.flow_proof=$flow_proof"
start_vm "candidate-$scenario" "$candidate_disk" "$tap_candidate" "$candidate_hw" "$candidate_log" "$candidate_common" & CANDIDATE_PID=$!
if [[ "$reference" == pydecnet ]]; then
    if ! wait_candidate_marker "$candidate_log" "DNIV-INTEROP-CTERM-READY session=$session scenario=$scenario" "$timeout_seconds" "$CANDIDATE_PID" "$REFERENCE_PID" "$ref1_log"; then
        tail -220 "$candidate_log" >&2 || true
        tail -160 "$ref1_log" >&2 || true
        exit 1
    fi
    if ! timeout 60s env PYTHONPATH="$host_pydecnet/pydecnet" python3 \
        "$script_dir/pydecnet-cterm.py" "$host_pydecnet_api" "$ref_name"; then
        tail -240 "$candidate_log" >&2 || true
        tail -180 "$ref1_log" >&2 || true
        exit 1
    fi
    if ! wait_candidate_marker "$candidate_log" "DNIV-INTEROP-CTERM-PASS session=$session scenario=$scenario" 30 "$CANDIDATE_PID" "$REFERENCE_PID" "$ref1_log"; then
        tail -240 "$candidate_log" >&2 || true
        tail -180 "$ref1_log" >&2 || true
        exit 1
    fi
    if ! wait_candidate_marker "$candidate_log" "DNIV-INTEROP-NML-READY session=$session scenario=$scenario" "$timeout_seconds" "$CANDIDATE_PID" "$REFERENCE_PID" "$ref1_log"; then
        tail -220 "$candidate_log" >&2 || true
        tail -160 "$ref1_log" >&2 || true
        exit 1
    fi
    if ! env PYTHONPATH="$host_pydecnet/pydecnet" python3 \
        "$script_dir/pydecnet-nice.py" "$host_pydecnet_api" \
        "$area.$node" "$ref_name"; then
        tail -220 "$candidate_log" >&2 || true
        tail -160 "$ref1_log" >&2 || true
        exit 1
    fi
    if ! wait_candidate_marker "$candidate_log" "DNIV-INTEROP-NML-PASS session=$session scenario=$scenario" 30 "$CANDIDATE_PID" "$REFERENCE_PID" "$ref1_log"; then
        tail -220 "$candidate_log" >&2 || true
        tail -160 "$ref1_log" >&2 || true
        exit 1
    fi
    if ! wait_candidate_marker "$candidate_log" "DNIV-INTEROP-NML-CONCURRENT-READY session=$session scenario=$scenario" 30 "$CANDIDATE_PID" "$REFERENCE_PID" "$ref1_log"; then
        tail -220 "$candidate_log" >&2 || true
        tail -160 "$ref1_log" >&2 || true
        exit 1
    fi
    if ! env PYTHONPATH="$host_pydecnet/pydecnet" python3 \
        "$script_dir/pydecnet-nice-concurrent.py" "$host_pydecnet_api" \
        "$area.$node" "$ref_name" 3; then
        tail -220 "$candidate_log" >&2 || true
        tail -160 "$ref1_log" >&2 || true
        exit 1
    fi
    if ! wait_candidate_marker "$candidate_log" "DNIV-INTEROP-NML-CONCURRENT-PASS session=$session scenario=$scenario" 30 "$CANDIDATE_PID" "$REFERENCE_PID" "$ref1_log"; then
        tail -220 "$candidate_log" >&2 || true
        tail -160 "$ref1_log" >&2 || true
        exit 1
    fi
    if ! wait_candidate_marker "$candidate_log" "DNIV-INTEROP-NML-RESTART-READY session=$session scenario=$scenario" 30 "$CANDIDATE_PID" "$REFERENCE_PID" "$ref1_log"; then
        tail -220 "$candidate_log" >&2 || true
        tail -160 "$ref1_log" >&2 || true
        exit 1
    fi
    if ! env PYTHONPATH="$host_pydecnet/pydecnet" python3 \
        "$script_dir/pydecnet-nice.py" "$host_pydecnet_api" \
        "$area.$node" "$ref_name"; then
        tail -220 "$candidate_log" >&2 || true
        tail -160 "$ref1_log" >&2 || true
        exit 1
    fi
    if ! wait_candidate_marker "$candidate_log" "DNIV-INTEROP-NML-RESTART-PASS session=$session scenario=$scenario" 30 "$CANDIDATE_PID" "$REFERENCE_PID" "$ref1_log"; then
        tail -220 "$candidate_log" >&2 || true
        tail -160 "$ref1_log" >&2 || true
        exit 1
    fi
    if ! wait_candidate_marker "$candidate_log" "DNIV-INTEROP-MIRROR-READY session=$session scenario=$scenario" 30 "$CANDIDATE_PID" "$REFERENCE_PID" "$ref1_log"; then
        tail -220 "$candidate_log" >&2 || true
        tail -160 "$ref1_log" >&2 || true
        exit 1
    fi
    if ! env PYTHONPATH="$host_pydecnet/pydecnet" python3 \
        "$script_dir/pydecnet-mirror.py" "$host_pydecnet_api" \
        "$area.$node" "$ref_name"; then
        tail -220 "$candidate_log" >&2 || true
        tail -160 "$ref1_log" >&2 || true
        exit 1
    fi
    if ! wait_candidate_marker "$candidate_log" "DNIV-INTEROP-MIRROR-PASS session=$session scenario=$scenario" 30 "$CANDIDATE_PID" "$REFERENCE_PID" "$ref1_log"; then
        tail -220 "$candidate_log" >&2 || true
        tail -160 "$ref1_log" >&2 || true
        exit 1
    fi
    if ! wait_candidate_marker "$candidate_log" "DNIV-INTEROP-MIRROR-NAME-READY session=$session scenario=$scenario" 30 "$CANDIDATE_PID" "$REFERENCE_PID" "$ref1_log"; then
        tail -220 "$candidate_log" >&2 || true
        tail -160 "$ref1_log" >&2 || true
        exit 1
    fi
    if ! env PYTHONPATH="$host_pydecnet/pydecnet" python3 \
        "$script_dir/pydecnet-mirror.py" "$host_pydecnet_api" \
        "$area.$node" "$ref_name" MIRROR; then
        tail -220 "$candidate_log" >&2 || true
        tail -160 "$ref1_log" >&2 || true
        exit 1
    fi
    if ! wait_candidate_marker "$candidate_log" "DNIV-INTEROP-MIRROR-NAME-PASS session=$session scenario=$scenario" 30 "$CANDIDATE_PID" "$REFERENCE_PID" "$ref1_log"; then
        tail -220 "$candidate_log" >&2 || true
        tail -160 "$ref1_log" >&2 || true
        exit 1
    fi
    if ! wait_candidate_marker "$candidate_log" "DNIV-INTEROP-MIRROR-ACCESS-READY session=$session scenario=$scenario" 30 "$CANDIDATE_PID" "$REFERENCE_PID" "$ref1_log"; then
        tail -220 "$candidate_log" >&2 || true
        tail -160 "$ref1_log" >&2 || true
        exit 1
    fi
    if ! env PYTHONPATH="$host_pydecnet/pydecnet" python3 \
        "$script_dir/pydecnet-access.py" "$host_pydecnet_api" \
        "$area.$node" "$ref_name" MIRROR DNIVUSER DNIVPASS DNIVACCT accept; then
        tail -220 "$candidate_log" >&2 || true
        tail -160 "$ref1_log" >&2 || true
        exit 1
    fi
    if ! wait_candidate_marker "$candidate_log" "DNIV-INTEROP-MIRROR-ACCESS-PASS session=$session scenario=$scenario" 30 "$CANDIDATE_PID" "$REFERENCE_PID" "$ref1_log"; then
        tail -220 "$candidate_log" >&2 || true
        tail -160 "$ref1_log" >&2 || true
        exit 1
    fi
    if ! wait_candidate_marker "$candidate_log" "DNIV-INTEROP-MIRROR-ACCESS-REJECT-READY session=$session scenario=$scenario" 30 "$CANDIDATE_PID" "$REFERENCE_PID" "$ref1_log"; then
        tail -220 "$candidate_log" >&2 || true
        tail -160 "$ref1_log" >&2 || true
        exit 1
    fi
    if ! env PYTHONPATH="$host_pydecnet/pydecnet" python3 \
        "$script_dir/pydecnet-access.py" "$host_pydecnet_api" \
        "$area.$node" "$ref_name" MIRROR DNIVUSER WRONG DNIVACCT reject=34; then
        tail -220 "$candidate_log" >&2 || true
        tail -160 "$ref1_log" >&2 || true
        exit 1
    fi
    if ! wait_candidate_marker "$candidate_log" "DNIV-INTEROP-MIRROR-ACCESS-REJECT-PASS session=$session scenario=$scenario" 30 "$CANDIDATE_PID" "$REFERENCE_PID" "$ref1_log"; then
        tail -220 "$candidate_log" >&2 || true
        tail -160 "$ref1_log" >&2 || true
        exit 1
    fi
    if ! wait_candidate_marker "$candidate_log" "DNIV-INTEROP-TASK-READY session=$session scenario=$scenario" 30 "$CANDIDATE_PID" "$REFERENCE_PID" "$ref1_log"; then
        tail -220 "$candidate_log" >&2 || true
        tail -160 "$ref1_log" >&2 || true
        exit 1
    fi
    if ! env PYTHONPATH="$host_pydecnet/pydecnet" python3 \
        "$script_dir/pydecnet-task.py" "$host_pydecnet_api" \
        "$area.$node" "$ref_name"; then
        tail -220 "$candidate_log" >&2 || true
        tail -160 "$ref1_log" >&2 || true
        exit 1
    fi
    if ! wait_candidate_marker "$candidate_log" "DNIV-INTEROP-TASK-PASS session=$session scenario=$scenario" 30 "$CANDIDATE_PID" "$REFERENCE_PID" "$ref1_log"; then
        tail -220 "$candidate_log" >&2 || true
        tail -160 "$ref1_log" >&2 || true
        exit 1
    fi
    if ! wait_candidate_marker "$candidate_log" "DNIV-INTEROP-FAL-READY session=$session scenario=$scenario" 30 "$CANDIDATE_PID" "$REFERENCE_PID" "$ref1_log"; then
        tail -220 "$candidate_log" >&2 || true
        tail -160 "$ref1_log" >&2 || true
        exit 1
    fi
    if ! env PYTHONPATH="$host_pydecnet/pydecnet" python3 \
        "$script_dir/pydecnet-fal.py" "$host_pydecnet_api" \
        "$area.$node" "$ref_name"; then
        tail -220 "$candidate_log" >&2 || true
        tail -160 "$ref1_log" >&2 || true
        exit 1
    fi
    if ! wait_candidate_marker "$candidate_log" "DNIV-INTEROP-FAL-PASS session=$session scenario=$scenario" 30 "$CANDIDATE_PID" "$REFERENCE_PID" "$ref1_log"; then
        tail -220 "$candidate_log" >&2 || true
        tail -160 "$ref1_log" >&2 || true
        exit 1
    fi
    if ! wait_candidate_marker "$candidate_log" "DNIV-INTEROP-HTTP-READY session=$session scenario=$scenario" 30 "$CANDIDATE_PID" "$REFERENCE_PID" "$ref1_log"; then
        tail -220 "$candidate_log" >&2 || true
        tail -160 "$ref1_log" >&2 || true
        exit 1
    fi
    if ! env PYTHONPATH="$host_pydecnet/pydecnet" python3 \
        "$script_dir/pydecnet-http.py" "$host_pydecnet_api" \
        "$area.$node" "$ref_name"; then
        tail -220 "$candidate_log" >&2 || true
        tail -160 "$ref1_log" >&2 || true
        exit 1
    fi
    if ! wait_candidate_marker "$candidate_log" "DNIV-INTEROP-HTTP-PASS session=$session scenario=$scenario" 30 "$CANDIDATE_PID" "$REFERENCE_PID" "$ref1_log"; then
        tail -220 "$candidate_log" >&2 || true
        tail -160 "$ref1_log" >&2 || true
        exit 1
    fi
fi
if [[ "$reference" == pydecnet ]]; then
    loss_marker="DNIV-INTEROP-LOSS-READY session=$session scenario=$scenario"
    if ! wait_candidate_marker "$candidate_log" "$loss_marker" "$timeout_seconds" "$CANDIDATE_PID" "$REFERENCE_PID" "$ref1_log"; then
        tail -240 "$candidate_log" >&2 || true
        tail -180 "$ref1_log" >&2 || true
        exit 1
    fi

    loss_fault_log="$work/nsp-loss-fault.log"
    : > "$loss_fault_log"
    sudo tc qdisc add dev "$tap_reference" clsact
    LOSS_QDISC=1
    sudo tc filter add dev "$tap_reference" ingress protocol all pref 10 flower \
        src_mac "$reference_mac" dst_mac "$candidate_mac" action drop
    printf 'fault=reference-unicast-drop duration=8s source=%s destination=%s\n' \
        "$reference_mac" "$candidate_mac" >> "$loss_fault_log"
    sleep 8
    loss_stats=$(sudo tc -s filter show dev "$tap_reference" ingress)
    printf '%s\n' "$loss_stats" >> "$loss_fault_log"
    if ! printf '%s\n' "$loss_stats" | grep -Eq 'Sent [0-9]+ bytes [1-9][0-9]* pkt'; then
        echo "interop: NSP loss injector matched no frames" >&2
        cat "$loss_fault_log" >&2
        exit 1
    fi
    sudo tc qdisc del dev "$tap_reference" clsact
    unset LOSS_QDISC

    if ! wait_candidate_marker "$candidate_log" "DNIV-INTEROP-LOSS-PASS session=$session scenario=$scenario" 30 "$CANDIDATE_PID" "$REFERENCE_PID" "$ref1_log"; then
        tail -260 "$candidate_log" >&2 || true
        tail -200 "$ref1_log" >&2 || true
        cat "$loss_fault_log" >&2 || true
        exit 1
    fi

    drain_marker="DNIV-INTEROP-DRAIN-READY session=$session scenario=$scenario"
    if ! wait_candidate_marker "$candidate_log" "$drain_marker" 30 "$CANDIDATE_PID" "$REFERENCE_PID" "$ref1_log"; then
        tail -280 "$candidate_log" >&2 || true
        tail -220 "$ref1_log" >&2 || true
        exit 1
    fi
    drain_fault_log="$work/nsp-drain-fault.log"
    : > "$drain_fault_log"
    sudo tc qdisc add dev "$tap_reference" clsact
    LOSS_QDISC=1
    sudo tc filter add dev "$tap_reference" ingress protocol all pref 10 flower \
        src_mac "$reference_mac" dst_mac "$candidate_mac" action drop
    printf 'fault=reference-unicast-drop-clean-drain duration=7s source=%s destination=%s\n' \
        "$reference_mac" "$candidate_mac" >> "$drain_fault_log"
    if ! wait_candidate_marker "$candidate_log" "DNIV-INTEROP-DRAIN-CLOSED session=$session scenario=$scenario" 15 "$CANDIDATE_PID" "$REFERENCE_PID" "$ref1_log"; then
        tail -300 "$candidate_log" >&2 || true
        tail -240 "$ref1_log" >&2 || true
        exit 1
    fi
    sleep 7
    drain_stats=$(sudo tc -s filter show dev "$tap_reference" ingress)
    printf '%s\n' "$drain_stats" >> "$drain_fault_log"
    if ! printf '%s\n' "$drain_stats" | grep -Eq 'Sent [0-9]+ bytes [1-9][0-9]* pkt'; then
        echo "interop: NSP clean-drain injector matched no frames" >&2
        cat "$drain_fault_log" >&2
        exit 1
    fi
    sudo tc qdisc del dev "$tap_reference" clsact
    unset LOSS_QDISC
    if ! wait_candidate_marker "$candidate_log" "DNIV-INTEROP-DRAIN-PASS session=$session scenario=$scenario" 30 "$CANDIDATE_PID" "$REFERENCE_PID" "$ref1_log"; then
        tail -320 "$candidate_log" >&2 || true
        tail -260 "$ref1_log" >&2 || true
        cat "$drain_fault_log" >&2 || true
        exit 1
    fi

    if [[ "$flow_proof" == 1 ]]; then
        if ! wait_candidate_marker "$candidate_log" "DNIV-INTEROP-FLOW-READY session=$session scenario=$scenario" 30 "$CANDIDATE_PID" "$REFERENCE_PID" "$ref1_log"; then
            tail -320 "$candidate_log" >&2 || true
            tail -260 "$ref1_log" >&2 || true
            exit 1
        fi
        if ! wait_candidate_marker "$candidate_log" "DNIV-INTEROP-FLOW-CONNECTED session=$session scenario=$scenario" 20 "$CANDIDATE_PID" "$REFERENCE_PID" "$ref1_log"; then
            tail -340 "$candidate_log" >&2 || true
            tail -280 "$ref1_log" >&2 || true
            exit 1
        fi
        flow_fault_log="$work/nsp-flow-fault.log"
        : > "$flow_fault_log"
        sudo tc qdisc add dev "$tap_reference" clsact
        LOSS_QDISC=1
        sudo tc filter add dev "$tap_reference" ingress protocol all pref 10 flower \
            src_mac "$reference_mac" dst_mac "$candidate_mac" action drop
        printf 'fault=reference-unicast-drop-flow-xoff source=%s destination=%s\n' \
            "$reference_mac" "$candidate_mac" >> "$flow_fault_log"
        if ! timeout 40s sudo python3 "$script_dir/inject-nsp-flow.py" \
            "$bridge" "$bridge" "$candidate_mac" \
            "$ref_area.$ref_node" "$area.$node"; then
            tail -340 "$candidate_log" >&2 || true
            tail -280 "$ref1_log" >&2 || true
            sudo tc -s filter show dev "$tap_reference" ingress >> "$flow_fault_log" 2>&1 || true
            cat "$flow_fault_log" >&2 || true
            exit 1
        fi
        flow_stats=$(sudo tc -s filter show dev "$tap_reference" ingress)
        printf '%s\n' "$flow_stats" >> "$flow_fault_log"
        if ! printf '%s\n' "$flow_stats" | grep -Eq 'Sent [0-9]+ bytes [1-9][0-9]* pkt'; then
            echo "interop: NSP flow-control fault matched no reference replies" >&2
            cat "$flow_fault_log" >&2
            exit 1
        fi
        sudo tc qdisc del dev "$tap_reference" clsact
        unset LOSS_QDISC
        if ! wait_candidate_marker "$candidate_log" "DNIV-INTEROP-FLOW-PASS session=$session scenario=$scenario" 20 "$CANDIDATE_PID" "$REFERENCE_PID" "$ref1_log"; then
            tail -340 "$candidate_log" >&2 || true
            tail -280 "$ref1_log" >&2 || true
            cat "$flow_fault_log" >&2 || true
            exit 1
        fi

        if ! wait_candidate_marker "$candidate_log" "DNIV-INTEROP-ACKRANGE-READY session=$session scenario=$scenario" 30 "$CANDIDATE_PID" "$REFERENCE_PID" "$ref1_log"; then
            tail -360 "$candidate_log" >&2 || true
            tail -300 "$ref1_log" >&2 || true
            exit 1
        fi
        if ! wait_candidate_marker "$candidate_log" "DNIV-INTEROP-ACKRANGE-CONNECTED session=$session scenario=$scenario" 20 "$CANDIDATE_PID" "$REFERENCE_PID" "$ref1_log"; then
            tail -360 "$candidate_log" >&2 || true
            tail -300 "$ref1_log" >&2 || true
            exit 1
        fi
        ackrange_fault_log="$work/nsp-ackrange-fault.log"
        : > "$ackrange_fault_log"
        sudo tc qdisc add dev "$tap_reference" clsact
        LOSS_QDISC=1
        sudo tc filter add dev "$tap_reference" ingress protocol all pref 10 flower \
            src_mac "$reference_mac" dst_mac "$candidate_mac" action drop
        printf 'fault=reference-unicast-drop-ackrange source=%s destination=%s\n' \
            "$reference_mac" "$candidate_mac" >> "$ackrange_fault_log"
        if ! timeout 30s sudo python3 "$script_dir/inject-nsp-ackrange.py" \
            "$bridge" "$bridge" "$candidate_mac" \
            "$ref_area.$ref_node" "$area.$node"; then
            tail -380 "$candidate_log" >&2 || true
            tail -320 "$ref1_log" >&2 || true
            sudo tc -s filter show dev "$tap_reference" ingress >> "$ackrange_fault_log" 2>&1 || true
            cat "$ackrange_fault_log" >&2 || true
            exit 1
        fi
        ackrange_stats=$(sudo tc -s filter show dev "$tap_reference" ingress)
        printf '%s\n' "$ackrange_stats" >> "$ackrange_fault_log"
        if ! printf '%s\n' "$ackrange_stats" | grep -Eq 'Sent [0-9]+ bytes [1-9][0-9]* pkt'; then
            echo "interop: NSP ack-range fault matched no reference replies" >&2
            cat "$ackrange_fault_log" >&2
            exit 1
        fi
        sudo tc qdisc del dev "$tap_reference" clsact
        unset LOSS_QDISC
        if ! wait_candidate_marker "$candidate_log" "DNIV-INTEROP-ACKRANGE-PASS session=$session scenario=$scenario" 20 "$CANDIDATE_PID" "$REFERENCE_PID" "$ref1_log"; then
            tail -380 "$candidate_log" >&2 || true
            tail -320 "$ref1_log" >&2 || true
            cat "$ackrange_fault_log" >&2 || true
            exit 1
        fi

        if ! wait_candidate_marker "$candidate_log" "DNIV-INTEROP-INTLOSS-READY session=$session scenario=$scenario" 30 "$CANDIDATE_PID" "$REFERENCE_PID" "$ref1_log"; then
            tail -400 "$candidate_log" >&2 || true
            tail -340 "$ref1_log" >&2 || true
            exit 1
        fi
        if ! wait_candidate_marker "$candidate_log" "DNIV-INTEROP-INTLOSS-CONNECTED session=$session scenario=$scenario" 20 "$CANDIDATE_PID" "$REFERENCE_PID" "$ref1_log"; then
            tail -400 "$candidate_log" >&2 || true
            tail -340 "$ref1_log" >&2 || true
            exit 1
        fi
        intloss_fault_log="$work/nsp-intloss-fault.log"
        : > "$intloss_fault_log"
        sudo tc qdisc add dev "$tap_reference" clsact
        LOSS_QDISC=1
        sudo tc filter add dev "$tap_reference" ingress protocol all pref 10 flower \
            src_mac "$reference_mac" dst_mac "$candidate_mac" action drop
        printf 'fault=reference-unicast-drop-interrupt-ack source=%s destination=%s\n' \
            "$reference_mac" "$candidate_mac" >> "$intloss_fault_log"
        if ! timeout 30s sudo python3 "$script_dir/inject-nsp-intloss.py" \
            "$bridge" "$bridge" "$candidate_mac" \
            "$ref_area.$ref_node" "$area.$node"; then
            tail -420 "$candidate_log" >&2 || true
            tail -360 "$ref1_log" >&2 || true
            sudo tc -s filter show dev "$tap_reference" ingress >> "$intloss_fault_log" 2>&1 || true
            cat "$intloss_fault_log" >&2 || true
            exit 1
        fi
        intloss_stats=$(sudo tc -s filter show dev "$tap_reference" ingress)
        printf '%s\n' "$intloss_stats" >> "$intloss_fault_log"
        if ! printf '%s\n' "$intloss_stats" | grep -Eq 'Sent [0-9]+ bytes [1-9][0-9]* pkt'; then
            echo "interop: NSP interrupt-loss fault matched no reference replies" >&2
            cat "$intloss_fault_log" >&2
            exit 1
        fi
        sudo tc qdisc del dev "$tap_reference" clsact
        unset LOSS_QDISC
        if ! wait_candidate_marker "$candidate_log" "DNIV-INTEROP-INTLOSS-PASS session=$session scenario=$scenario" 25 "$CANDIDATE_PID" "$REFERENCE_PID" "$ref1_log"; then
            tail -420 "$candidate_log" >&2 || true
            tail -360 "$ref1_log" >&2 || true
            cat "$intloss_fault_log" >&2 || true
            exit 1
        fi

        if ! wait_candidate_marker "$candidate_log" "DNIV-INTEROP-INTFLOW-READY session=$session scenario=$scenario" 30 "$CANDIDATE_PID" "$REFERENCE_PID" "$ref1_log"; then
            tail -440 "$candidate_log" >&2 || true
            tail -380 "$ref1_log" >&2 || true
            exit 1
        fi
        if ! wait_candidate_marker "$candidate_log" "DNIV-INTEROP-INTFLOW-CONNECTED session=$session scenario=$scenario" 20 "$CANDIDATE_PID" "$REFERENCE_PID" "$ref1_log"; then
            tail -440 "$candidate_log" >&2 || true
            tail -380 "$ref1_log" >&2 || true
            exit 1
        fi
        if ! timeout 35s sudo python3 "$script_dir/inject-nsp-intflow.py" \
            "$bridge" "$bridge" "$candidate_mac" \
            "$ref_area.$ref_node" "$area.$node"; then
            tail -460 "$candidate_log" >&2 || true
            tail -400 "$ref1_log" >&2 || true
            exit 1
        fi
        if ! wait_candidate_marker "$candidate_log" "DNIV-INTEROP-INTFLOW-PASS session=$session scenario=$scenario" 25 "$CANDIDATE_PID" "$REFERENCE_PID" "$ref1_log"; then
            tail -460 "$candidate_log" >&2 || true
            tail -400 "$ref1_log" >&2 || true
            exit 1
        fi

        if ! wait_candidate_marker "$candidate_log" "DNIV-INTEROP-CCRETRY-READY session=$session scenario=$scenario" 30 "$CANDIDATE_PID" "$REFERENCE_PID" "$ref1_log"; then
            tail -480 "$candidate_log" >&2 || true
            tail -420 "$ref1_log" >&2 || true
            exit 1
        fi
        cc_retry_peer_log="$work/nsp-ccretry-peer.log"
        : > "$cc_retry_peer_log"
        env PYTHONPATH="$host_pydecnet/pydecnet" python3 \
            "$script_dir/pydecnet-ccretry.py" "$host_pydecnet_api" \
            "$area.$node" "$ref_name" >"$cc_retry_peer_log" 2>&1 &
        CCRETRY_PID=$!
        if ! wait_candidate_marker "$candidate_log" "DNIV-INTEROP-CCRETRY-ACCEPTED session=$session scenario=$scenario" 20 "$CANDIDATE_PID" "$REFERENCE_PID" "$ref1_log"; then
            cat "$cc_retry_peer_log" >&2 || true
            tail -480 "$candidate_log" >&2 || true
            tail -420 "$ref1_log" >&2 || true
            exit 1
        fi

        cc_retry_fault_log="$work/nsp-ccretry-fault.log"
        : > "$cc_retry_fault_log"
        sudo tc qdisc add dev "$tap_reference" clsact
        LOSS_QDISC=1
        sudo tc filter add dev "$tap_reference" ingress protocol all pref 10 flower \
            src_mac "$reference_mac" dst_mac "$candidate_mac" action drop
        printf 'fault=reference-unicast-drop-cc-ack source=%s destination=%s\n' \
            "$reference_mac" "$candidate_mac" >> "$cc_retry_fault_log"
        if ! timeout 20s sudo python3 "$script_dir/observe-nsp-ccretry.py" \
            "$bridge" "$candidate_mac" "$reference_mac"; then
            sudo tc -s filter show dev "$tap_reference" ingress >> "$cc_retry_fault_log" 2>&1 || true
            cat "$cc_retry_peer_log" >&2 || true
            cat "$cc_retry_fault_log" >&2 || true
            tail -500 "$candidate_log" >&2 || true
            tail -440 "$ref1_log" >&2 || true
            exit 1
        fi
        cc_retry_stats=$(sudo tc -s filter show dev "$tap_reference" ingress)
        printf '%s\n' "$cc_retry_stats" >> "$cc_retry_fault_log"
        if ! printf '%s\n' "$cc_retry_stats" | grep -Eq 'Sent [0-9]+ bytes [1-9][0-9]* pkt'; then
            echo "interop: NSP CC retry fault matched no peer acknowledgements" >&2
            cat "$cc_retry_fault_log" >&2
            exit 1
        fi
        sudo tc qdisc del dev "$tap_reference" clsact
        unset LOSS_QDISC
        if ! wait "$CCRETRY_PID"; then
            cat "$cc_retry_peer_log" >&2 || true
            tail -500 "$candidate_log" >&2 || true
            tail -440 "$ref1_log" >&2 || true
            exit 1
        fi
        unset CCRETRY_PID
        if ! wait_candidate_marker "$candidate_log" "DNIV-INTEROP-CCRETRY-PASS session=$session scenario=$scenario" 25 "$CANDIDATE_PID" "$REFERENCE_PID" "$ref1_log"; then
            cat "$cc_retry_peer_log" >&2 || true
            cat "$cc_retry_fault_log" >&2 || true
            tail -500 "$candidate_log" >&2 || true
            tail -440 "$ref1_log" >&2 || true
            exit 1
        fi

        if ! wait_candidate_marker "$candidate_log" "DNIV-INTEROP-DILOSS-CONNECTED session=$session scenario=$scenario" 30 "$CANDIDATE_PID" "$REFERENCE_PID" "$ref1_log"; then
            tail -520 "$candidate_log" >&2 || true
            tail -460 "$ref1_log" >&2 || true
            exit 1
        fi
        di_loss_fault_log="$work/nsp-di-loss-fault.log"
        : > "$di_loss_fault_log"
        sudo tc qdisc add dev "$tap_reference" clsact
        LOSS_QDISC=1
        sudo tc filter add dev "$tap_reference" ingress protocol all pref 10 flower \
            src_mac "$reference_mac" dst_mac "$candidate_mac" action drop
        printf 'fault=reference-unicast-drop-dc source=%s destination=%s\n' \
            "$reference_mac" "$candidate_mac" >> "$di_loss_fault_log"
        if ! timeout 20s sudo python3 "$script_dir/observe-nsp-diloss.py" \
            "$bridge" "$candidate_mac" "$reference_mac"; then
            sudo tc -s filter show dev "$tap_reference" ingress >> "$di_loss_fault_log" 2>&1 || true
            cat "$di_loss_fault_log" >&2 || true
            tail -540 "$candidate_log" >&2 || true
            tail -480 "$ref1_log" >&2 || true
            exit 1
        fi
        di_loss_stats=$(sudo tc -s filter show dev "$tap_reference" ingress)
        printf '%s\n' "$di_loss_stats" >> "$di_loss_fault_log"
        if ! printf '%s\n' "$di_loss_stats" | grep -Eq 'Sent [0-9]+ bytes [1-9][0-9]* pkt'; then
            echo "interop: NSP DI loss fault matched no peer confirmations" >&2
            cat "$di_loss_fault_log" >&2
            exit 1
        fi
        sudo tc qdisc del dev "$tap_reference" clsact
        unset LOSS_QDISC
        if ! wait_candidate_marker "$candidate_log" "DNIV-INTEROP-DILOSS-PASS session=$session scenario=$scenario" 30 "$CANDIDATE_PID" "$REFERENCE_PID" "$ref1_log"; then
            cat "$di_loss_fault_log" >&2 || true
            tail -540 "$candidate_log" >&2 || true
            tail -480 "$ref1_log" >&2 || true
            exit 1
        fi

        if ! wait_candidate_marker "$candidate_log" "DNIV-INTEROP-DIEXHAUST-READY session=$session scenario=$scenario" 30 "$CANDIDATE_PID" "$REFERENCE_PID" "$ref1_log"; then
            tail -560 "$candidate_log" >&2 || true
            tail -500 "$ref1_log" >&2 || true
            exit 1
        fi
        di_exhaust_fault_log="$work/nsp-di-exhaust-fault.log"
        : > "$di_exhaust_fault_log"
        sudo tc qdisc add dev "$tap_reference" clsact
        LOSS_QDISC=1
        sudo tc filter add dev "$tap_reference" ingress protocol all pref 10 flower \
            src_mac "$reference_mac" dst_mac "$candidate_mac" action drop
        printf 'fault=reference-unicast-drop-until-di-retry-exhaustion source=%s destination=%s\n' \
            "$reference_mac" "$candidate_mac" >> "$di_exhaust_fault_log"
        if ! wait_candidate_marker "$candidate_log" "DNIV-INTEROP-DIEXHAUSTED session=$session scenario=$scenario errno=113" 38 "$CANDIDATE_PID" "$REFERENCE_PID" "$ref1_log"; then
            sudo tc -s filter show dev "$tap_reference" ingress >> "$di_exhaust_fault_log" 2>&1 || true
            cat "$di_exhaust_fault_log" >&2 || true
            tail -580 "$candidate_log" >&2 || true
            tail -520 "$ref1_log" >&2 || true
            exit 1
        fi
        di_exhaust_stats=$(sudo tc -s filter show dev "$tap_reference" ingress)
        printf '%s\n' "$di_exhaust_stats" >> "$di_exhaust_fault_log"
        if ! printf '%s\n' "$di_exhaust_stats" | grep -Eq 'Sent [0-9]+ bytes [1-9][0-9]* pkt'; then
            echo "interop: NSP DI exhaustion fault matched no peer confirmations" >&2
            cat "$di_exhaust_fault_log" >&2
            exit 1
        fi
        sudo tc qdisc del dev "$tap_reference" clsact
        unset LOSS_QDISC
        if ! wait_candidate_marker "$candidate_log" "DNIV-INTEROP-DIEXHAUST-PASS session=$session scenario=$scenario" 20 "$CANDIDATE_PID" "$REFERENCE_PID" "$ref1_log"; then
            cat "$di_exhaust_fault_log" >&2 || true
            tail -580 "$candidate_log" >&2 || true
            tail -520 "$ref1_log" >&2 || true
            exit 1
        fi

        if ! wait_candidate_marker "$candidate_log" "DNIV-INTEROP-KEEPALIVE-READY session=$session scenario=$scenario" 20 "$CANDIDATE_PID" "$REFERENCE_PID" "$ref1_log"; then
            tail -600 "$candidate_log" >&2 || true
            tail -540 "$ref1_log" >&2 || true
            exit 1
        fi
        if ! wait_candidate_marker "$candidate_log" "DNIV-INTEROP-KEEPALIVE-CONNECTED session=$session scenario=$scenario" 20 "$CANDIDATE_PID" "$REFERENCE_PID" "$ref1_log"; then
            tail -600 "$candidate_log" >&2 || true
            tail -540 "$ref1_log" >&2 || true
            exit 1
        fi
        if ! timeout 16s sudo python3 "$script_dir/observe-nsp-keepalive.py" \
            "$bridge" "$candidate_mac" "$reference_mac"; then
            tail -620 "$candidate_log" >&2 || true
            tail -560 "$ref1_log" >&2 || true
            exit 1
        fi
        if ! wait_candidate_marker "$candidate_log" "DNIV-INTEROP-KEEPALIVE-PASS session=$session scenario=$scenario" 20 "$CANDIDATE_PID" "$REFERENCE_PID" "$ref1_log"; then
            tail -620 "$candidate_log" >&2 || true
            tail -560 "$ref1_log" >&2 || true
            exit 1
        fi

        if ! wait_candidate_marker "$candidate_log" "DNIV-INTEROP-WINDOW-READY session=$session scenario=$scenario" 30 "$CANDIDATE_PID" "$REFERENCE_PID" "$ref1_log"; then
            tail -640 "$candidate_log" >&2 || true
            tail -580 "$ref1_log" >&2 || true
            exit 1
        fi
        window_fault_log="$work/nsp-window-fault.log"
        : > "$window_fault_log"
        sudo tc qdisc add dev "$tap_reference" clsact
        LOSS_QDISC=1
        sudo tc filter add dev "$tap_reference" ingress protocol all pref 10 flower \
            src_mac "$reference_mac" dst_mac "$candidate_mac" action drop
        printf 'fault=reference-unicast-drop-full-window source=%s destination=%s\n' \
            "$reference_mac" "$candidate_mac" >> "$window_fault_log"
        if ! wait_candidate_marker "$candidate_log" "DNIV-INTEROP-WINDOW-FULL session=$session scenario=$scenario" 20 "$CANDIDATE_PID" "$REFERENCE_PID" "$ref1_log"; then
            tail -660 "$candidate_log" >&2 || true
            tail -600 "$ref1_log" >&2 || true
            sudo tc -s filter show dev "$tap_reference" ingress >> "$window_fault_log" 2>&1 || true
            exit 1
        fi
        window_stats=$(sudo tc -s filter show dev "$tap_reference" ingress)
        printf '%s\n' "$window_stats" >> "$window_fault_log"
        if ! printf '%s\n' "$window_stats" | grep -Eq 'Sent [0-9]+ bytes [1-9][0-9]* pkt'; then
            echo "interop: NSP full-window injector matched no frames" >&2
            cat "$window_fault_log" >&2
            exit 1
        fi
        sudo tc qdisc del dev "$tap_reference" clsact
        unset LOSS_QDISC
        if ! wait_candidate_marker "$candidate_log" "DNIV-INTEROP-WINDOW-PASS session=$session scenario=$scenario" 45 "$CANDIDATE_PID" "$REFERENCE_PID" "$ref1_log"; then
            tail -680 "$candidate_log" >&2 || true
            tail -620 "$ref1_log" >&2 || true
            cat "$window_fault_log" >&2 || true
            exit 1
        fi
    fi

    exhaust_marker="DNIV-INTEROP-EXHAUST-READY session=$session scenario=$scenario"
    if ! wait_candidate_marker "$candidate_log" "$exhaust_marker" 30 "$CANDIDATE_PID" "$REFERENCE_PID" "$ref1_log"; then
        tail -280 "$candidate_log" >&2 || true
        tail -220 "$ref1_log" >&2 || true
        exit 1
    fi
    exhaust_fault_log="$work/nsp-exhaust-fault.log"
    : > "$exhaust_fault_log"
    sudo tc qdisc add dev "$tap_reference" clsact
    LOSS_QDISC=1
    sudo tc filter add dev "$tap_reference" ingress protocol all pref 10 flower \
        src_mac "$reference_mac" dst_mac "$candidate_mac" action drop
    printf 'fault=reference-unicast-drop-until-retry-exhaustion source=%s destination=%s\n' \
        "$reference_mac" "$candidate_mac" >> "$exhaust_fault_log"

    if ! wait_candidate_marker "$candidate_log" "DNIV-INTEROP-EXHAUST-PASS session=$session scenario=$scenario" 40 "$CANDIDATE_PID" "$REFERENCE_PID" "$ref1_log"; then
        tail -300 "$candidate_log" >&2 || true
        tail -240 "$ref1_log" >&2 || true
        sudo tc -s filter show dev "$tap_reference" ingress >> "$exhaust_fault_log" 2>&1 || true
        cat "$exhaust_fault_log" >&2 || true
        exit 1
    fi
    exhaust_stats=$(sudo tc -s filter show dev "$tap_reference" ingress)
    printf '%s\n' "$exhaust_stats" >> "$exhaust_fault_log"
    if ! printf '%s\n' "$exhaust_stats" | grep -Eq 'Sent [0-9]+ bytes [1-9][0-9]* pkt'; then
        echo "interop: NSP exhaustion injector matched no frames" >&2
        cat "$exhaust_fault_log" >&2
        exit 1
    fi
    sudo tc qdisc del dev "$tap_reference" clsact
    unset LOSS_QDISC

    if ! wait_candidate_marker "$candidate_log" "DNIV-INTEROP-EXHAUST-RECOVERED session=$session scenario=$scenario" 30 "$CANDIDATE_PID" "$REFERENCE_PID" "$ref1_log"; then
        tail -320 "$candidate_log" >&2 || true
        tail -260 "$ref1_log" >&2 || true
        cat "$exhaust_fault_log" >&2 || true
        exit 1
    fi

    if ! wait_candidate_marker "$candidate_log" "DNIV-INTEROP-CI-EXHAUST-READY session=$session scenario=$scenario" 30 "$CANDIDATE_PID" "$REFERENCE_PID" "$ref1_log"; then
        tail -320 "$candidate_log" >&2 || true
        tail -260 "$ref1_log" >&2 || true
        exit 1
    fi
    ci_fault_log="$work/nsp-ci-exhaust-fault.log"
    : > "$ci_fault_log"
    sudo tc qdisc add dev "$tap_reference" clsact
    LOSS_QDISC=1
    sudo tc filter add dev "$tap_reference" ingress protocol all pref 10 flower \
        src_mac "$reference_mac" dst_mac "$candidate_mac" action drop
    printf 'fault=reference-unicast-drop-until-ci-retry-exhaustion source=%s destination=%s\n' \
        "$reference_mac" "$candidate_mac" >> "$ci_fault_log"
    if ! wait_candidate_marker "$candidate_log" "DNIV-INTEROP-CI-EXHAUSTED session=$session scenario=$scenario errno=113" 40 "$CANDIDATE_PID" "$REFERENCE_PID" "$ref1_log"; then
        tail -340 "$candidate_log" >&2 || true
        tail -280 "$ref1_log" >&2 || true
        sudo tc -s filter show dev "$tap_reference" ingress >> "$ci_fault_log" 2>&1 || true
        cat "$ci_fault_log" >&2 || true
        exit 1
    fi
    ci_stats=$(sudo tc -s filter show dev "$tap_reference" ingress)
    printf '%s\n' "$ci_stats" >> "$ci_fault_log"
    if ! printf '%s\n' "$ci_stats" | grep -Eq 'Sent [0-9]+ bytes [1-9][0-9]* pkt'; then
        echo "interop: NSP CI exhaustion injector matched no frames" >&2
        cat "$ci_fault_log" >&2
        exit 1
    fi
    sudo tc qdisc del dev "$tap_reference" clsact
    unset LOSS_QDISC
    if ! wait_candidate_marker "$candidate_log" "DNIV-INTEROP-CI-EXHAUST-PASS session=$session scenario=$scenario" 30 "$CANDIDATE_PID" "$REFERENCE_PID" "$ref1_log"; then
        tail -340 "$candidate_log" >&2 || true
        tail -280 "$ref1_log" >&2 || true
        cat "$ci_fault_log" >&2 || true
        exit 1
    fi

    if [[ "$timer_proof" == 1 ]]; then
        if [[ "$scenario" != l1 ]]; then
            echo "interop: timer proof requires PyDECnet L1" >&2
            exit 2
        fi
        if ! wait_candidate_marker "$candidate_log" "DNIV-INTEROP-CR-TIMEOUT-READY session=$session scenario=$scenario" 30 "$CANDIDATE_PID" "$REFERENCE_PID" "$ref1_log"; then
            tail -360 "$candidate_log" >&2 || true
            tail -300 "$ref1_log" >&2 || true
            exit 1
        fi
        if ! timeout 60s env PYTHONPATH="$host_pydecnet/pydecnet" python3 \
            "$script_dir/pydecnet-timeout.py" "$host_pydecnet_api" \
            "$area.$node" "$ref_name"; then
            tail -380 "$candidate_log" >&2 || true
            tail -320 "$ref1_log" >&2 || true
            exit 1
        fi
        if ! wait_candidate_marker "$candidate_log" "DNIV-INTEROP-CR-TIMEOUT-PASS session=$session scenario=$scenario" 20 "$CANDIDATE_PID" "$REFERENCE_PID" "$ref1_log"; then
            tail -380 "$candidate_log" >&2 || true
            tail -320 "$ref1_log" >&2 || true
            exit 1
        fi
    fi
fi
if [[ "$reference" == pydecnet && "$scenario" != router-endnode ]]; then
    listen_marker="DNIV-INTEROP-LISTEN-READY session=$session scenario=$scenario"
    if ! wait_candidate_marker "$candidate_log" "$listen_marker" "$timeout_seconds" "$CANDIDATE_PID" "$REFERENCE_PID" "$ref1_log"; then
        tail -220 "$candidate_log" >&2 || true
        tail -160 "$ref1_log" >&2 || true
        exit 1
    fi
    if ! env PYTHONPATH="$host_pydecnet/pydecnet" python3 \
        "$script_dir/pydecnet-inbound.py" "$host_pydecnet_api" \
        "$area.$node" "$ref_name"; then
        tail -220 "$candidate_log" >&2 || true
        tail -160 "$ref1_log" >&2 || true
        exit 1
    fi
    if ! wait_candidate_marker "$candidate_log" "DNIV-INTEROP-LISTEN-PASS session=$session scenario=$scenario" 90 "$CANDIDATE_PID" "$REFERENCE_PID" "$ref1_log"; then
        tail -220 "$candidate_log" >&2 || true
        tail -160 "$ref1_log" >&2 || true
        exit 1
    fi
    if ! wait_candidate_marker "$candidate_log" "DNIV-INTEROP-BACKLOG-READY session=$session scenario=$scenario" 30 "$CANDIDATE_PID" "$REFERENCE_PID" "$ref1_log"; then
        tail -220 "$candidate_log" >&2 || true
        tail -160 "$ref1_log" >&2 || true
        exit 1
    fi
    if ! env PYTHONPATH="$host_pydecnet/pydecnet" python3 \
        "$script_dir/pydecnet-backlog.py" "$host_pydecnet_api" \
        "$area.$node" "$ref_name"; then
        tail -220 "$candidate_log" >&2 || true
        tail -160 "$ref1_log" >&2 || true
        exit 1
    fi
    if ! wait_candidate_marker "$candidate_log" "DNIV-INTEROP-BACKLOG-PASS session=$session scenario=$scenario" 90 "$CANDIDATE_PID" "$REFERENCE_PID" "$ref1_log"; then
        tail -220 "$candidate_log" >&2 || true
        tail -160 "$ref1_log" >&2 || true
        exit 1
    fi
    if ! wait_candidate_marker "$candidate_log" "DNIV-INTEROP-OVERFLOW-READY session=$session scenario=$scenario" 30 "$CANDIDATE_PID" "$REFERENCE_PID" "$ref1_log"; then
        tail -220 "$candidate_log" >&2 || true
        tail -160 "$ref1_log" >&2 || true
        exit 1
    fi
    if ! env PYTHONPATH="$host_pydecnet/pydecnet" python3 \
        "$script_dir/pydecnet-backlog.py" "$host_pydecnet_api" \
        "$area.$node" "$ref_name" overflow; then
        tail -220 "$candidate_log" >&2 || true
        tail -160 "$ref1_log" >&2 || true
        exit 1
    fi
    if ! wait_candidate_marker "$candidate_log" "DNIV-INTEROP-OVERFLOW-PASS session=$session scenario=$scenario" 90 "$CANDIDATE_PID" "$REFERENCE_PID" "$ref1_log"; then
        tail -220 "$candidate_log" >&2 || true
        tail -160 "$ref1_log" >&2 || true
        exit 1
    fi
    if ! wait_candidate_marker "$candidate_log" "DNIV-INTEROP-CLOSE-RACE-READY session=$session scenario=$scenario" 30 "$CANDIDATE_PID" "$REFERENCE_PID" "$ref1_log"; then
        tail -220 "$candidate_log" >&2 || true
        tail -160 "$ref1_log" >&2 || true
        exit 1
    fi
    for close_race_round in 1 2 3 4; do
        if ! env PYTHONPATH="$host_pydecnet/pydecnet" python3 \
            "$script_dir/pydecnet-backlog.py" "$host_pydecnet_api" \
            "$area.$node" "$ref_name" close-race; then
            echo "close-race round $close_race_round failed" >&2
            tail -260 "$candidate_log" >&2 || true
            tail -180 "$ref1_log" >&2 || true
            exit 1
        fi
    done
    if ! wait_candidate_marker "$candidate_log" "DNIV-INTEROP-CLOSE-RACE-PASS session=$session scenario=$scenario" 90 "$CANDIDATE_PID" "$REFERENCE_PID" "$ref1_log"; then
        tail -220 "$candidate_log" >&2 || true
        tail -160 "$ref1_log" >&2 || true
        exit 1
    fi
    if ! wait_candidate_marker "$candidate_log" "DNIV-INTEROP-RESET-READY session=$session scenario=$scenario" 30 "$CANDIDATE_PID" "$REFERENCE_PID" "$ref1_log"; then
        tail -240 "$candidate_log" >&2 || true
        tail -180 "$ref1_log" >&2 || true
        exit 1
    fi
    if ! env PYTHONPATH="$host_pydecnet/pydecnet" python3 \
        "$script_dir/pydecnet-reset.py" "$host_pydecnet_api" \
        "$area.$node" "$ref_name"; then
        tail -260 "$candidate_log" >&2 || true
        tail -200 "$ref1_log" >&2 || true
        exit 1
    fi
    if ! wait_candidate_marker "$candidate_log" "DNIV-INTEROP-RESET-PASS session=$session scenario=$scenario" 90 "$CANDIDATE_PID" "$REFERENCE_PID" "$ref1_log"; then
        tail -260 "$candidate_log" >&2 || true
        tail -200 "$ref1_log" >&2 || true
        exit 1
    fi
    if ! wait_candidate_marker "$candidate_log" "DNIV-INTEROP-LISTENER-CLOSE-READY session=$session scenario=$scenario" 30 "$CANDIDATE_PID" "$REFERENCE_PID" "$ref1_log"; then
        tail -260 "$candidate_log" >&2 || true
        tail -200 "$ref1_log" >&2 || true
        exit 1
    fi
    if ! env PYTHONPATH="$host_pydecnet/pydecnet" python3 \
        "$script_dir/pydecnet-backlog.py" "$host_pydecnet_api" \
        "$area.$node" "$ref_name" listener-close; then
        tail -280 "$candidate_log" >&2 || true
        tail -220 "$ref1_log" >&2 || true
        exit 1
    fi
    if ! wait_candidate_marker "$candidate_log" "DNIV-INTEROP-LISTENER-CLOSE-PASS session=$session scenario=$scenario" 90 "$CANDIDATE_PID" "$REFERENCE_PID" "$ref1_log"; then
        tail -280 "$candidate_log" >&2 || true
        tail -220 "$ref1_log" >&2 || true
        exit 1
    fi
    if ! wait_candidate_marker "$candidate_log" "DNIV-INTEROP-TERM-RACE-READY session=$session scenario=$scenario" 30 "$CANDIDATE_PID" "$REFERENCE_PID" "$ref1_log"; then
        tail -280 "$candidate_log" >&2 || true
        tail -220 "$ref1_log" >&2 || true
        exit 1
    fi
    if ! env PYTHONPATH="$host_pydecnet/pydecnet" python3 \
        "$script_dir/pydecnet-termrace.py" "$host_pydecnet_api" \
        "$area.$node" "$ref_name"; then
        tail -300 "$candidate_log" >&2 || true
        tail -240 "$ref1_log" >&2 || true
        exit 1
    fi
    if ! wait_candidate_marker "$candidate_log" "DNIV-INTEROP-TERM-RACE-PASS session=$session scenario=$scenario" 90 "$CANDIDATE_PID" "$REFERENCE_PID" "$ref1_log"; then
        tail -300 "$candidate_log" >&2 || true
        tail -240 "$ref1_log" >&2 || true
        exit 1
    fi
fi
if [[ "$reserved_proof" == 1 ]]; then
    if ! wait_candidate_marker "$candidate_log" "DNIV-INTEROP-RESERVED-READY session=$session scenario=$scenario" 30 "$CANDIDATE_PID" "$REFERENCE_PID" "$ref1_log"; then
        tail -320 "$candidate_log" >&2 || true
        tail -260 "$ref1_log" >&2 || true
        exit 1
    fi

    # The synthetic CIs use the live peer's node address so candidate replies
    # have a valid route.  Prevent the independent peer from consuming those
    # replies and immediately confirming each rejected CI, which would recycle
    # connection slots before the bounded table can actually be exhausted.
    # Bridge capture still sees candidate replies before this TAP egress drop.
    sudo tc qdisc add dev "$tap_reference" clsact
    RESERVED_QDISC=1
    sudo tc filter add dev "$tap_reference" egress protocol all pref 20 flower \
        src_mac "$candidate_mac" dst_mac "$reference_mac" action drop

    if ! sudo python3 "$script_dir/inject-nsp-reserved.py" "$bridge" "$candidate_mac" "$ref_area.$ref_node" "$area.$node"; then
        tail -320 "$candidate_log" >&2 || true
        tail -260 "$ref1_log" >&2 || true
        exit 1
    fi
    if ! wait_candidate_marker "$candidate_log" "DNIV-INTEROP-RESERVED-PASS session=$session scenario=$scenario" 30 "$CANDIDATE_PID" "$REFERENCE_PID" "$ref1_log"; then
        tail -340 "$candidate_log" >&2 || true
        tail -280 "$ref1_log" >&2 || true
        exit 1
    fi
    reserved_stats=$(sudo tc -s filter show dev "$tap_reference" egress)
    if ! printf '%s\n' "$reserved_stats" | grep -Eq 'Sent [0-9]+ bytes [1-9][0-9]* pkt'; then
        echo "interop: reserved-port peer-isolation filter matched no replies" >&2
        printf '%s\n' "$reserved_stats" >&2
        exit 1
    fi
    sudo tc qdisc del dev "$tap_reference" clsact
    unset RESERVED_QDISC
fi
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
if ! wait_marker "$ref2_log" "$reference_ready_marker" "$reference_ready_seconds" "$REFERENCE_PID"; then
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

validator_args=()
if [[ "$timer_proof" == 1 ]]; then
    validator_args+=(--timer-proof)
fi
if [[ "$reserved_proof" == 1 ]]; then
    validator_args+=(--reserved-proof)
fi
if (( peer_segsize != 0 )); then
    validator_args+=(--peer-segsize "$peer_segsize")
fi
python3 "$script_dir/validate-interop-pcap.py" "$pcap" "$reference" "$scenario" \
    "$candidate_mac" "$candidate_hw" "$candidate_changed_hw" \
    "$reference_mac" "$reference_hw" "${validator_args[@]}"

grep -Fq "DNIV-INTEROP-RECOVERED session=$session scenario=$scenario" "$candidate_log"
! grep -Fq 'DNIV-INTEROP-FAIL' "$candidate_log"
! grep -Fq 'DNIV-REF-FAIL' "$ref1_log"
! grep -Fq 'DNIV-REF-FAIL' "$ref2_log"
echo "interop: pass reference=$reference scenario=$scenario arch=$host_arch"
