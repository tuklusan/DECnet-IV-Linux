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
if (( ${#VAX_USERNAME} > 40 || ${#VAX_PASSWORD} > 40 )); then
    echo "area31-proof: VAX access credentials are invalid" >&2
    exit 2
fi
if [[ "$VAX_USERNAME" == *$'\n'* || "$VAX_USERNAME" == *$'\r'* ||
      "$VAX_PASSWORD" == *$'\n'* || "$VAX_PASSWORD" == *$'\r'* ]]; then
    echo "area31-proof: VAX access credentials are invalid" >&2
    exit 2
fi
gateway_node=${DNIV_AREA31_GATEWAY_NODE:-}
gateway_name=${DNIV_AREA31_GATEWAY_NAME:-}
linux_node=${DNIV_AREA31_LINUX_NODE:-}
linux_name=${DNIV_AREA31_LINUX_NAME:-}
qcocal_node=${DNIV_QCOCAL_NODE:-}
area31_arch=${DNIV_AREA31_ARCH:-amd64}
case "$area31_arch" in
    amd64|arm64) ;;
    *)
        echo "area31-proof: DNIV_AREA31_ARCH must be amd64 or arm64" >&2
        exit 2
        ;;
esac
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
if [[ -n "$qcocal_node" ]]; then
    if [[ ! "$qcocal_node" =~ ^31\.([0-9]{1,4})$ ]] ||
       (( 10#${BASH_REMATCH[1]} < 1 || 10#${BASH_REMATCH[1]} > 1023 )); then
        echo "area31-proof: DNIV_QCOCAL_NODE must identify an Area-31 node" >&2
        exit 2
    fi
    if [[ "$qcocal_node" == "$gateway_node" || "$qcocal_node" == "$linux_node" ||
          "$qcocal_node" == "$VAX_ADDR" ]]; then
        echo "area31-proof: QCOCAL identity must be distinct" >&2
        exit 2
    fi
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
if [[ "$area31_arch" == amd64 ]]; then
    qemu_bin=qemu-system-x86_64
else
    qemu_bin=qemu-system-aarch64
fi
for cmd in "$qemu_bin" qemu-img mke2fs; do
    command -v "$cmd" >/dev/null || { echo "area31-proof: missing native VM dependency" >&2; exit 2; }
done
qemu_vde=0
if "$qemu_bin" -netdev help 2>&1 | grep -qw vde; then
    qemu_vde=1
else
    for cmd in ip vde_plug2tap; do
        command -v "$cmd" >/dev/null || {
            echo "area31-proof: QEMU lacks VDE and TAP fallback dependency is missing" >&2
            exit 2
        }
    done
fi

work=$(mktemp -d /tmp/dniv-area31.XXXXXX)
gateway_pid=
switch_pid=
tap_bridge_pid=
tap_name=
vm_pid=

cleanup() {
    set +e
    [[ -z "${gateway_pid:-}" ]] || kill "$gateway_pid" 2>/dev/null || true
    [[ -z "${gateway_pid:-}" ]] || wait "$gateway_pid" 2>/dev/null || true
    [[ -z "${vm_pid:-}" ]] || kill "$vm_pid" 2>/dev/null || true
    [[ -z "${vm_pid:-}" ]] || wait "$vm_pid" 2>/dev/null || true
    [[ -z "${tap_bridge_pid:-}" ]] || kill "$tap_bridge_pid" 2>/dev/null || true
    [[ -z "${tap_bridge_pid:-}" ]] || wait "$tap_bridge_pid" 2>/dev/null || true
    if [[ -n "${tap_name:-}" ]]; then
        sudo ip link set dev "$tap_name" down 2>/dev/null || true
        sudo ip tuntap del dev "$tap_name" mode tap 2>/dev/null || true
    fi
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
gateway_log="$work/gateway.log"
show_gateway_log() {
    sed \
        -e "s#${MULTINET_REMOTE_HOST//[#\\&]/\\&}#[masked-host]#g" \
        -e "s#${MULTINET_REMOTE_PORT//[#\\&]/\\&}#[masked-port]#g" \
        -e "s#${VAX_ADDR//[#\\&]/\\&}#[masked-vax]#g" \
        -e "s#${VAX_USERNAME//[#\\&]/\\&}#[masked-user]#g" \
        -e "s#${VAX_PASSWORD//[#\\&]/\\&}#[masked-password]#g" \
        "$gateway_log" >&2 || true
}
ncp_app="$work/pydecnet/pydecnet/applications/ncp"
run_ncp() {
    env DECNETAPI="$api_sock" PYTHONPATH="$work/pydecnet/pydecnet" \
        "$work/venv/bin/python" "$ncp_app" "$@"
}
wait_gateway_wan() {
    for _ in $(seq 1 180); do
        kill -0 "$gateway_pid" 2>/dev/null || {
            echo "area31-proof: gateway exited before PYRTR adjacency became usable" >&2
            show_gateway_log
            return 1
        }
        if [[ -S "$api_sock" ]] &&
           grep -Fq "Circuit up" "$gateway_log" &&
           grep -Fq "Adjacent node = 31.3" "$gateway_log"; then
            return 0
        fi
        sleep 1
    done
    echo "area31-proof: PYRTR MULTINET adjacency did not converge" >&2
    show_gateway_log
    return 1
}
query_pyrtr_known() {
    local outfile=$1 tmp="${1}.tmp"
    for _ in $(seq 1 30); do
        : >"$tmp"
        run_ncp tell 31.3 show known nodes >"$tmp" 2>&1 || true
        if grep -Eq '31\.[0-9]{1,4}' "$tmp" &&
           ! grep -Eq 'Error processing command|Error connecting to NML|Unexpected reply' "$tmp"; then
            mv "$tmp" "$outfile"
            return 0
        fi
        sleep 2
    done
    echo "area31-proof: PYRTR NML SHOW KNOWN NODES failed" >&2
    cat "$tmp" >&2 || true
    rm -f "$tmp"
    return 1
}
wait_vax_nice() {
    for _ in $(seq 1 60); do
        if env PYTHONPATH="$work/pydecnet/pydecnet" VAX_ADDR="$VAX_ADDR" \
            "$work/venv/bin/python" "$script_dir/area31-nice.py" \
            "$api_sock" "$gateway_name" >/dev/null 2>&1; then
            env PYTHONPATH="$work/pydecnet/pydecnet" VAX_ADDR="$VAX_ADDR" \
                "$work/venv/bin/python" "$script_dir/area31-nice.py" \
                "$api_sock" "$gateway_name" >/dev/null
            return 0
        fi
        sleep 1
    done
    echo "area31-proof: VAX NICE reachability did not converge" >&2
    show_gateway_log
    return 1
}
"$work/venv/bin/python" "$repo_root/userspace/dnmultinet/dnmultinet.py" \
    --node "$gateway_node" --name "$gateway_name" --type l2router \
    --vde "vde://$sock" --mode connect --runtime-peer-env \
    --api-socket "$api_sock" --pydecnet-dir "$work/pydecnet/pydecnet" \
    >"$gateway_log" 2>&1 &
gateway_pid=$!

wait_gateway_wan || exit 1

known_file="$work/pyrtr-known.txt"
query_pyrtr_known "$known_file" || exit 1
seed=${DNIV_AREA31_SEED:-0}
[[ "$seed" =~ ^[0-9]+$ ]] || { echo "area31-proof: invalid allocation seed" >&2; exit 2; }
vax_num=${VAX_ADDR#31.}
free=()
for step in $(seq 0 1022); do
    n=$((1 + ((seed + step * 257) % 1023)))
    (( n != vax_num && n != 3 )) || continue
    grep -Eq "(^|[^0-9])31\\.${n}([^0-9]|$)" "$known_file" && continue
    free+=("$n")
    (( ${#free[@]} == 2 )) && break
done
(( ${#free[@]} == 2 )) || { echo "area31-proof: no two free Area-31 identities found from PYRTR known nodes" >&2; exit 1; }
final_gateway="31.${free[0]}"
final_linux="31.${free[1]}"
if [[ "$gateway_node" != "$final_gateway" || "$linux_node" != "$final_linux" ]]; then
    kill "$gateway_pid" 2>/dev/null || true
    wait "$gateway_pid" 2>/dev/null || true
    gateway_pid=
    gateway_node=$final_gateway
    gateway_name=$(printf 'DG%04d' "${free[0]}")
    linux_node=$final_linux
    linux_name=$(printf 'DL%04d' "${free[1]}")
    rm -f "$api_sock"
    : >"$gateway_log"
    "$work/venv/bin/python" "$repo_root/userspace/dnmultinet/dnmultinet.py" \
        --node "$gateway_node" --name "$gateway_name" --type l2router \
        --vde "vde://$sock" --mode connect --runtime-peer-env \
        --api-socket "$api_sock" --pydecnet-dir "$work/pydecnet/pydecnet" \
        >"$gateway_log" 2>&1 &
    gateway_pid=$!
    wait_gateway_wan || exit 1
fi
echo "area31-proof: selected two Area-31 identities absent from PYRTR known nodes"
wait_vax_nice || exit 1

discovered_qcocal=$(env PYTHONPATH="$work/pydecnet/pydecnet" \
    "$work/venv/bin/python" "$script_dir/area31-find-node.py" \
    "$api_sock" "$gateway_name" "$VAX_ADDR" QCOCAL 2>/dev/null || true)
if [[ -n "$qcocal_node" ]]; then
    if [[ -n "$discovered_qcocal" && "$discovered_qcocal" != "$qcocal_node" ]]; then
        echo "area31-proof: explicit QCOCAL address disagrees with NICE" >&2
        exit 1
    fi
elif [[ -n "$discovered_qcocal" ]]; then
    qcocal_node=$discovered_qcocal
    echo "area31-proof: QCOCAL discovered by NICE"
fi
unset discovered_qcocal

control_dir="$work/control"
mkdir -p "$control_dir"
cat >"$control_dir/dniv-area31.env" <<EOF
DNIV_LINUX_NODE=$linux_node
DNIV_LINUX_NAME=$linux_name
DNIV_GATEWAY_NODE=$gateway_node
DNIV_VAX_ADDR=$VAX_ADDR
DNIV_QCOCAL_ADDR=$qcocal_node
EOF
if [[ -n "$qcocal_node" ]]; then
    python3 "$script_dir/vax/make-http-com.py" "$control_dir/DNIVHT.COM"
    python3 "$script_dir/vax/make-task-com.py" "$control_dir/DNIVTK.COM"
fi
printf '%s' "$VAX_USERNAME" >"$control_dir/vax-user"
printf '%s' "$VAX_PASSWORD" >"$control_dir/vax-password"
chmod 600 "$control_dir/dniv-area31.env" "$control_dir/vax-user" "$control_dir/vax-password"
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
qemu_args=(-name dniv-area31 -accel "$accel" -smp 1)
if (( qemu_vde )); then
    netdev_arg="vde,id=lan,sock=$sock"
else
    tap_name=$(printf 'dnivtap%05d' "$((BASHPID % 100000))")
    sudo ip tuntap add dev "$tap_name" mode tap user "$(id -un)"
    sudo ip link set dev "$tap_name" up
    vde_plug2tap -s "$sock" "$tap_name" >/dev/null 2>&1 &
    tap_bridge_pid=$!
    sleep 1
    kill -0 "$tap_bridge_pid" 2>/dev/null || {
        echo "area31-proof: VDE-to-TAP bridge did not start" >&2
        exit 1
    }
    netdev_arg="tap,id=lan,ifname=$tap_name,script=no,downscript=no"
fi
if [[ "$area31_arch" == amd64 ]]; then
    qemu_args+=(-m 512)
    console="console=ttyS0"
else
    if [[ "$accel" == kvm ]]; then
        machine="virt,gic-version=host"
        cpu=host
    else
        machine="virt,gic-version=3"
        cpu=max
    fi
    qemu_args+=(-machine "$machine" -cpu "$cpu" -m 1024)
    console="earlycon=pl011,0x09000000 console=ttyAMA0"
fi
"$qemu_bin" "${qemu_args[@]}" \
    -kernel "$DNIV_AREA31_KERNEL" -initrd "$DNIV_AREA31_INITRD" \
    -append "root=LABEL=dniv-root rootfstype=ext4 rw dniv.area31=1 $console" \
    -drive "file=$candidate,if=virtio,format=qcow2" \
    -drive "file=$control_img,if=virtio,format=raw,readonly=on" \
    -netdev "$netdev_arg" \
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
