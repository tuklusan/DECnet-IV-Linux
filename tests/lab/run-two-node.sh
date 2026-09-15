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

artifacts=${DNIV_LAB_ARTIFACTS:-"$(pwd)/tests/lab/artifacts"}
timeout_seconds=${DNIV_LAB_TIMEOUT_SECONDS:-240}
session=${DNIV_LAB_SESSION_ID:-"local-$(date -u +%Y%m%dT%H%M%SZ)-$$"}
[[ "$session" =~ ^[A-Za-z0-9._-]+$ ]] || { echo "two-node: invalid session id" >&2; exit 2; }
mkdir -p "$artifacts/$session"
work="$artifacts/$session"
log70="$work/dn70.serial.log"
log71="$work/dn71.serial.log"
pcap="$work/lan.pcap"
node70="$work/dn70.qcow2"
node71="$work/dn71.qcow2"

qemu-img create -q -f qcow2 -F qcow2 -b "$(readlink -f "$base")" "$node70"
qemu-img create -q -f qcow2 -F qcow2 -b "$(readlink -f "$base")" "$node71"

suffix=$(printf '%s' "$session" | sha256sum | cut -c1-6)
bridge="db${suffix}"
tap70="d70${suffix}"
tap71="d71${suffix}"
cleanup() {
    set +e
    [[ -n "${Q70_PID:-}" ]] && kill "$Q70_PID" 2>/dev/null
    [[ -n "${Q71_PID:-}" ]] && kill "$Q71_PID" 2>/dev/null
    [[ -n "${TCPDUMP_PID:-}" ]] && sudo kill "$TCPDUMP_PID" 2>/dev/null
    for tap in "$tap70" "$tap71"; do sudo ip link del "$tap" 2>/dev/null; done
    sudo ip link del "$bridge" 2>/dev/null
}
trap cleanup EXIT INT TERM

sudo ip link add "$bridge" type bridge
sudo ip link set "$bridge" up
for tap in "$tap70" "$tap71"; do
    sudo ip tuntap add dev "$tap" mode tap user "$(id -un)"
    sudo ip link set "$tap" master "$bridge"
    sudo ip link set "$tap" up
done
sudo tcpdump -U -i "$bridge" -w "$pcap" 'ether proto 0x6003' >/dev/null 2>&1 &
TCPDUMP_PID=$!

host_arch=$(uname -m)
accel=tcg
if [[ -e /dev/kvm && -r /dev/kvm && -w /dev/kvm ]]; then accel=kvm; fi

start_node() {
    local name=$1 node=$2 peer=$3 mac=$4 tap=$5 disk=$6 log=$7
    local common="root=LABEL=dniv-root rootfstype=ext4 rw dniv.smoke=1 dniv.node=$node dniv.name=$name dniv.peer=$peer dniv.session=$session"
    case "$host_arch" in
        x86_64)
            qemu-system-x86_64 -name "$name" -accel "$accel" -m 512 -smp 1 \
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
            qemu-system-aarch64 -name "$name" -machine virt -accel "$accel" -cpu "$cpu" -m 512 -smp 1 \
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

mac70=aa:00:04:00:46:7c
mac71=aa:00:04:00:47:7c
start_node DN70 70 "$mac71" "$mac70" "$tap70" "$node70" "$log70" & Q70_PID=$!
start_node DN71 71 "$mac70" "$mac71" "$tap71" "$node71" "$log71" & Q71_PID=$!

deadline=$((SECONDS + timeout_seconds))
pass70=0
pass71=0
while (( SECONDS < deadline )); do
    grep -Fq "DNIV-LAB-PASS session=$session node=DN70" "$log70" 2>/dev/null && pass70=1
    grep -Fq "DNIV-LAB-PASS session=$session node=DN71" "$log71" 2>/dev/null && pass71=1
    if (( pass70 && pass71 )); then break; fi
    if ! kill -0 "$Q70_PID" 2>/dev/null && (( ! pass70 )); then
        grep -Fq "DNIV-LAB-PASS session=$session node=DN70" "$log70" 2>/dev/null && pass70=1
        (( pass70 )) || { echo "two-node: DN70 exited before pass" >&2; break; }
    fi
    if ! kill -0 "$Q71_PID" 2>/dev/null && (( ! pass71 )); then
        grep -Fq "DNIV-LAB-PASS session=$session node=DN71" "$log71" 2>/dev/null && pass71=1
        (( pass71 )) || { echo "two-node: DN71 exited before pass" >&2; break; }
    fi
    sleep 1
done

wait "$Q70_PID" 2>/dev/null || true
wait "$Q71_PID" 2>/dev/null || true
unset Q70_PID Q71_PID
sudo kill "$TCPDUMP_PID" 2>/dev/null || true
wait "$TCPDUMP_PID" 2>/dev/null || true
unset TCPDUMP_PID

if (( ! pass70 || ! pass71 )); then
    echo "--- DN70 ---" >&2; tail -120 "$log70" >&2 || true
    echo "--- DN71 ---" >&2; tail -120 "$log71" >&2 || true
    exit 1
fi
frames=$(sudo tcpdump -nn -r "$pcap" 'ether proto 0x6003' 2>/dev/null | wc -l)
if (( frames < 2 )); then
    echo "two-node: expected captured DECnet frames, saw $frames" >&2
    exit 1
fi
echo "two-node: pass on $host_arch, captured $frames DECnet routing frames"
