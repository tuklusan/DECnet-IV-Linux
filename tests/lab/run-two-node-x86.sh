#!/bin/bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
    echo "usage: $0 BASE-X86_64-QCOW2" >&2
    exit 2
fi

base=$1
repo_root=$(cd "$(dirname "$0")/../.." && pwd)
artifacts=${DNIV_LAB_ARTIFACTS:-"$repo_root/tests/lab/artifacts"}
mkdir -p "$artifacts"

node70="$artifacts/dn70.qcow2"
node71="$artifacts/dn71.qcow2"
log70="$artifacts/dn70.serial.log"
log71="$artifacts/dn71.serial.log"
pcap="$artifacts/lan.pcap"

"$repo_root/tests/lab/prepare-image.sh" "$base" "$node70" 31.70 DN70 aa:00:04:00:47:7c
"$repo_root/tests/lab/prepare-image.sh" "$base" "$node71" 31.71 DN71 aa:00:04:00:46:7c

cleanup() {
    set +e
    [[ -n "${Q70_PID:-}" ]] && kill "$Q70_PID" 2>/dev/null
    [[ -n "${Q71_PID:-}" ]] && kill "$Q71_PID" 2>/dev/null
    [[ -n "${TCPDUMP_PID:-}" ]] && sudo kill "$TCPDUMP_PID" 2>/dev/null
    for tap in dniv70 dniv71; do
        sudo ip link del "$tap" 2>/dev/null
    done
    sudo ip link del dnivbr0 2>/dev/null
}
trap cleanup EXIT INT TERM

sudo ip link add dnivbr0 type bridge
sudo ip link set dnivbr0 up
for tap in dniv70 dniv71; do
    sudo ip tuntap add dev "$tap" mode tap user "$(id -un)"
    sudo ip link set "$tap" master dnivbr0
    sudo ip link set "$tap" up
done

sudo tcpdump -U -i dnivbr0 -w "$pcap" 'ether proto 0x6003' >/dev/null 2>&1 &
TCPDUMP_PID=$!

accel=tcg
if [[ -e /dev/kvm && -r /dev/kvm && -w /dev/kvm ]]; then
    accel=kvm
fi
echo "two-node lab: QEMU acceleration=${accel}"

qemu-system-x86_64 \
    -accel "$accel" -m 256 -smp 1 \
    -drive "file=$node70,if=virtio,format=qcow2" \
    -netdev tap,id=lan,ifname=dniv70,script=no,downscript=no \
    -device virtio-net-pci,netdev=lan,mac=aa:00:04:00:46:7c \
    -display none -monitor none -serial "file:$log70" &
Q70_PID=$!

qemu-system-x86_64 \
    -accel "$accel" -m 256 -smp 1 \
    -drive "file=$node71,if=virtio,format=qcow2" \
    -netdev tap,id=lan,ifname=dniv71,script=no,downscript=no \
    -device virtio-net-pci,netdev=lan,mac=aa:00:04:00:47:7c \
    -display none -monitor none -serial "file:$log71" &
Q71_PID=$!

deadline=$((SECONDS + 180))
finished=0
while (( SECONDS < deadline )); do
    done70=0
    done71=0
    grep -q 'DNIV-LAB-DONE DN70' "$log70" 2>/dev/null && done70=1
    grep -q 'DNIV-LAB-DONE DN71' "$log71" 2>/dev/null && done71=1
    if (( done70 && done71 )); then
        finished=1
        break
    fi
    sleep 2
done

if (( ! finished )); then
    echo "two-node lab: guests did not finish before timeout" >&2
    echo "--- DN70 serial tail ---" >&2
    tail -80 "$log70" 2>/dev/null >&2 || true
    echo "--- DN71 serial tail ---" >&2
    tail -80 "$log71" 2>/dev/null >&2 || true
    exit 1
fi

wait "$Q70_PID"
unset Q70_PID
wait "$Q71_PID"
unset Q71_PID
sudo kill "$TCPDUMP_PID" 2>/dev/null || true
wait "$TCPDUMP_PID" 2>/dev/null || true
unset TCPDUMP_PID

grep -Eq 'Routing frames received = [1-9][0-9]*' "$log70"
grep -Eq 'Routing frames received = [1-9][0-9]*' "$log71"

frames=$(sudo tcpdump -nn -r "$pcap" 'ether proto 0x6003' 2>/dev/null | wc -l)
if (( frames < 2 )); then
    echo "two-node lab: expected DECnet routing frames, saw $frames" >&2
    exit 1
fi

echo "two-node lab: DN70 and DN71 both received EtherType 0x6003 frames ($frames captured)"
