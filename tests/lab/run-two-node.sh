#!/usr/bin/env bash
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
mac_a=$(decnet_mac "$area" "$node_a")
mac_b=$(decnet_mac "$area" "$node_b")

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

qemu-img create -q -f qcow2 -F qcow2 -b "$(readlink -f "$base")" "$disk_a"
qemu-img create -q -f qcow2 -F qcow2 -b "$(readlink -f "$base")" "$disk_b"

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
    local name=$1 node=$2 peer=$3 mac=$4 tap=$5 disk=$6 log=$7
    local common="root=LABEL=dniv-root rootfstype=ext4 rw dniv.smoke=1 dniv.area=$area dniv.node=$node dniv.name=$name dniv.peer=$peer dniv.session=$session"
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

start_node "$name_a" "$node_a" "$mac_b" "$mac_a" "$tap_a" "$disk_a" "$log_a" & QA_PID=$!
start_node "$name_b" "$node_b" "$mac_a" "$mac_b" "$tap_b" "$disk_b" "$log_b" & QB_PID=$!

deadline=$((SECONDS + timeout_seconds))
pass_a=0
pass_b=0
while (( SECONDS < deadline )); do
    grep -Fq "DNIV-LAB-PASS session=$session node=$name_a" "$log_a" 2>/dev/null && pass_a=1
    grep -Fq "DNIV-LAB-PASS session=$session node=$name_b" "$log_b" 2>/dev/null && pass_b=1
    if (( pass_a && pass_b )); then break; fi
    if ! kill -0 "$QA_PID" 2>/dev/null && (( ! pass_a )); then
        grep -Fq "DNIV-LAB-PASS session=$session node=$name_a" "$log_a" 2>/dev/null && pass_a=1
        (( pass_a )) || { echo "two-node: $name_a exited before pass" >&2; break; }
    fi
    if ! kill -0 "$QB_PID" 2>/dev/null && (( ! pass_b )); then
        grep -Fq "DNIV-LAB-PASS session=$session node=$name_b" "$log_b" 2>/dev/null && pass_b=1
        (( pass_b )) || { echo "two-node: $name_b exited before pass" >&2; break; }
    fi
    sleep 1
done

# Let successful guests flush their final reciprocal frames and normal shutdown,
# but never let guest teardown turn a failed lab into an unbounded wait.
if (( pass_a && pass_b )); then sleep 3; fi
terminate_guest "$QA_PID"
terminate_guest "$QB_PID"
unset QA_PID QB_PID
sudo kill "$TCPDUMP_PID" 2>/dev/null || true
wait "$TCPDUMP_PID" 2>/dev/null || true
unset TCPDUMP_PID

if (( ! pass_a || ! pass_b )); then
    echo "--- $name_a ---" >&2; tail -120 "$log_a" >&2 || true
    echo "--- $name_b ---" >&2; tail -120 "$log_b" >&2 || true
    exit 1
fi
frames=$(sudo tcpdump -nn -r "$pcap" 'ether proto 0x6003' 2>/dev/null | wc -l)
if (( frames < 2 )); then
    echo "two-node: expected captured DECnet frames, saw $frames" >&2
    exit 1
fi
echo "two-node: pass on $host_arch for $area.$node_a/$area.$node_b, captured $frames DECnet routing frames"
