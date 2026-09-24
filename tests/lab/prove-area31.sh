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

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
repo_root=$(CDPATH= cd -- "$script_dir/../.." && pwd)

required=(
    MULTINET_REMOTE_HOST
    MULTINET_REMOTE_PORT
    VAX_ADDR
    VAX_USERNAME
    VAX_PASSWORD
)
missing=()
for name in "${required[@]}"; do
    [[ -n "${!name:-}" ]] || missing+=("$name")
done
if (( ${#missing[@]} )); then
    printf 'area31-proof: missing required secret: %s\n' "${missing[@]}" >&2
    exit 2
fi

if [[ ! "$MULTINET_REMOTE_PORT" =~ ^[0-9]+$ ]] ||
   (( MULTINET_REMOTE_PORT < 1 || MULTINET_REMOTE_PORT > 65535 )); then
    echo "area31-proof: MULTINET_REMOTE_PORT is invalid" >&2
    exit 2
fi
if [[ ! "$VAX_ADDR" =~ ^31\.([0-9]{1,4})$ ]] ||
   (( 10#${BASH_REMATCH[1]} < 1 || 10#${BASH_REMATCH[1]} > 1023 )); then
    echo "area31-proof: VAX_ADDR must identify an Area-31 node" >&2
    exit 2
fi

gateway_node=${DNIV_AREA31_GATEWAY_NODE:-}
gateway_name=${DNIV_AREA31_GATEWAY_NAME:-}
linux_node=${DNIV_AREA31_LINUX_NODE:-}
linux_name=${DNIV_AREA31_LINUX_NAME:-}
if [[ ! "$gateway_node" =~ ^31\.([0-9]{1,4})$ ]] ||
   (( 10#${BASH_REMATCH[1]} < 1 || 10#${BASH_REMATCH[1]} > 1023 )); then
    echo "area31-proof: DNIV_AREA31_GATEWAY_NODE must identify an assigned Area-31 node" >&2
    exit 2
fi
if [[ ! "$gateway_name" =~ ^[A-Za-z][A-Za-z0-9]{0,5}$ ]]; then
    echo "area31-proof: DNIV_AREA31_GATEWAY_NAME must be a 1..6 character DECnet name" >&2
    exit 2
fi
if [[ ! "$linux_node" =~ ^31\.([0-9]{1,4})$ ]] ||
   (( 10#${BASH_REMATCH[1]} < 1 || 10#${BASH_REMATCH[1]} > 1023 )); then
    echo "area31-proof: DNIV_AREA31_LINUX_NODE must identify an assigned Area-31 node" >&2
    exit 2
fi
if [[ ! "$linux_name" =~ ^[A-Za-z][A-Za-z0-9]{0,5}$ ]]; then
    echo "area31-proof: DNIV_AREA31_LINUX_NAME must be a 1..6 character DECnet name" >&2
    exit 2
fi
if [[ "$linux_node" == "$gateway_node" || "$linux_node" == "$VAX_ADDR" ||
      "$gateway_node" == "$VAX_ADDR" ]]; then
    echo "area31-proof: assigned Area-31 node identities must be distinct" >&2
    exit 2
fi

if [[ "${1:-}" == "--preflight-only" ]]; then
    echo "area31-proof: preflight pass"
    exit 0
fi
if (( $# != 0 )); then
    echo "usage: $0 [--preflight-only]" >&2
    exit 2
fi

source "$repo_root/tests/reference/refs.env"

if [[ -z "${DNIV_AREA31_CANDIDATE_IMAGE:-}" ||
      -z "${DNIV_AREA31_KERNEL:-}" || -z "${DNIV_AREA31_INITRD:-}" ]]; then
    echo "area31-proof: native candidate image/kernel/initrd are required" >&2
    exit 2
fi
for path in "$DNIV_AREA31_CANDIDATE_IMAGE" "$DNIV_AREA31_KERNEL" "$DNIV_AREA31_INITRD"; do
    [[ -r "$path" ]] || { echo "area31-proof: native candidate input is unreadable" >&2; exit 2; }
done
for cmd in qemu-system-x86_64 qemu-img mke2fs; do
    command -v "$cmd" >/dev/null || { echo "area31-proof: missing native VM dependency" >&2; exit 2; }
done
qemu-system-x86_64 -netdev help 2>&1 | grep -qw vde || {
    echo "area31-proof: QEMU VDE netdev support is unavailable" >&2
    exit 2
}

work=$(mktemp -d /tmp/dniv-area31.XXXXXX)
gateway_pid=
switch_pid=
vm_pid=

cleanup() {
    set +e
    [[ -z "${gateway_pid:-}" ]] || kill "$gateway_pid" 2>/dev/null || true
    [[ -z "${gateway_pid:-}" ]] || wait "$gateway_pid" 2>/dev/null || true
    [[ -z "${vm_pid:-}" ]] || kill "$vm_pid" 2>/dev/null || true
    [[ -z "${vm_pid:-}" ]] || wait "$vm_pid" 2>/dev/null || true
    [[ -z "${switch_pid:-}" ]] || kill "$switch_pid" 2>/dev/null || true
    rm -rf "$work"
}
trap cleanup EXIT INT TERM

git clone -q https://github.com/tuklusan/pydecnet.git "$work/pydecnet"
git -C "$work/pydecnet" checkout -q "$PYDECNET_REF"
test "$(git -C "$work/pydecnet" rev-parse HEAD)" = "$PYDECNET_REF"

python3 -m venv "$work/venv"
"$work/venv/bin/python" -m pip install -q --upgrade pip setuptools
"$work/venv/bin/python" -m pip install -q "$work/pydecnet/pydecnet"

sock="$work/vde.ctl"
vde_switch -daemon -sock "$sock" >/dev/null 2>&1
for _ in $(seq 1 50); do
    switch_pid=$(pgrep -f "vde_switch.*-sock $sock" | head -n1 || true)
    [[ -n "$switch_pid" && -S "$sock/ctl" ]] && break
    sleep 0.1
done
[[ -n "$switch_pid" && -S "$sock/ctl" ]] || {
    echo "area31-proof: VDE switch did not start" >&2
    exit 1
}

api_sock="$work/decnetapi.sock"
"$work/venv/bin/python" "$repo_root/userspace/dnmultinet/dnmultinet.py" \
    --node "$gateway_node" --name "$gateway_name" --type l2router \
    --vde "vde://$sock" --mode connect --runtime-peer-env \
    --api-socket "$api_sock" --pydecnet-dir "$work/pydecnet/pydecnet" \
    >/dev/null 2>&1 &
gateway_pid=$!

for _ in $(seq 1 300); do
    kill -0 "$gateway_pid" 2>/dev/null || {
        echo "area31-proof: gateway exited before remote routing became usable" >&2
        exit 1
    }
    if [[ -S "$api_sock" ]] &&
       env PYTHONPATH="$work/pydecnet/pydecnet" VAX_ADDR="$VAX_ADDR" \
           "$work/venv/bin/python" "$script_dir/area31-nice.py" \
           "$api_sock" "$gateway_name" >/dev/null 2>&1; then
        env PYTHONPATH="$work/pydecnet/pydecnet" VAX_ADDR="$VAX_ADDR" \
            "$work/venv/bin/python" "$script_dir/area31-nice.py" \
            "$api_sock" "$gateway_name" >/dev/null
        break
    fi
    sleep 1
done

if ! env PYTHONPATH="$work/pydecnet/pydecnet" VAX_ADDR="$VAX_ADDR" \
    "$work/venv/bin/python" "$script_dir/area31-nice.py" "$api_sock" "$gateway_name" \
    >/dev/null 2>&1; then
    echo "area31-proof: VAX NICE reachability did not converge" >&2
    exit 1
fi

control_dir="$work/control"
mkdir -p "$control_dir"
cat >"$control_dir/dniv-area31.env" <<EOF
DNIV_LINUX_NODE=$linux_node
DNIV_LINUX_NAME=$linux_name
DNIV_GATEWAY_NODE=$gateway_node
DNIV_VAX_ADDR=$VAX_ADDR
EOF
chmod 600 "$control_dir/dniv-area31.env"
control_img="$work/control.ext4"
truncate -s 8M "$control_img"
mke2fs -q -F -t ext4 -L DNIVCTL -d "$control_dir" "$control_img"

candidate="$work/candidate.qcow2"
qemu-img create -q -f qcow2 -F qcow2 -b "$(readlink -f "$DNIV_AREA31_CANDIDATE_IMAGE")" "$candidate"
vm_log="$work/candidate.log"
node_num=${linux_node#31.}
mac=$(printf 'aa:00:04:00:%02x:%02x' "$((node_num & 255))" "$(((31 << 2) | (node_num >> 8)) & 255)")
accel=tcg
[[ -r /dev/kvm && -w /dev/kvm ]] && accel=kvm
qemu-system-x86_64 -name dniv-area31 -accel "$accel" -m 512 -smp 1 \
    -kernel "$DNIV_AREA31_KERNEL" -initrd "$DNIV_AREA31_INITRD" \
    -append "root=LABEL=dniv-root rootfstype=ext4 rw dniv.area31=1 console=ttyS0" \
    -drive "file=$candidate,if=virtio,format=qcow2" \
    -drive "file=$control_img,if=virtio,format=raw,readonly=on" \
    -netdev "vde,id=lan,sock=$sock" \
    -device "virtio-net-pci,netdev=lan,mac=$mac" \
    -display none -monitor none -serial "file:$vm_log" -no-reboot &
vm_pid=$!

for _ in $(seq 1 360); do
    if grep -Fq 'DNIV-AREA31-NATIVE-PASS' "$vm_log" 2>/dev/null; then
        wait "$vm_pid" 2>/dev/null || true
        vm_pid=
        echo "area31-proof: native Linux routing NICE NSP Session path pass"
        exit 0
    fi
    if ! kill -0 "$vm_pid" 2>/dev/null; then
        echo "area31-proof: native candidate exited before proof completed" >&2
        exit 1
    fi
    sleep 1
done
echo "area31-proof: native candidate proof timed out" >&2
exit 1
