#!/bin/bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
    echo "usage: $0 BASE-X86_64-QCOW2" >&2
    exit 2
fi

base=$1
repo_root=$(cd "$(dirname "$0")/../.." && pwd)
artifacts=${DNIV_LAB_ARTIFACTS:-"$repo_root/tests/lab/artifacts"}
session_id=${DNIV_LAB_SESSION_ID:-"local-$(date -u +%Y%m%dT%H%M%SZ)-$$"}
attempt_id=${DNIV_LAB_ATTEMPT_ID:-"attempt-$(date -u +%Y%m%dT%H%M%SZ)-$$"}
resume=${DNIV_LAB_RESUME:-0}

for value in "$session_id" "$attempt_id"; do
    if [[ ! "$value" =~ ^[A-Za-z0-9._-]+$ ]]; then
        echo "two-node lab: invalid session/attempt id: $value" >&2
        exit 2
    fi
done
if [[ "$resume" != 0 && "$resume" != 1 ]]; then
    echo "two-node lab: DNIV_LAB_RESUME must be 0 or 1" >&2
    exit 2
fi

session_dir="$artifacts/sessions/$session_id"
attempt_dir="$session_dir/attempts/$attempt_id"
node70="$session_dir/dn70.qcow2"
node71="$session_dir/dn71.qcow2"
seed70="$session_dir/dn70.seed.iso"
seed71="$session_dir/dn71.seed.iso"
manifest="$session_dir/session.env"
attempt_manifest="$attempt_dir/attempt.env"
log70="$attempt_dir/dn70.serial.log"
log71="$attempt_dir/dn71.serial.log"
pcap="$attempt_dir/lan.pcap"

lan70=aa:00:04:00:46:7c
lan71=aa:00:04:00:47:7c
mgmt70=52:54:00:70:00:01
mgmt71=52:54:00:71:00:01

mkdir -p "$artifacts/sessions"
if [[ "$resume" == 0 && -e "$manifest" ]]; then
    echo "two-node lab: session $session_id already exists; set DNIV_LAB_RESUME=1 to reuse it" >&2
    exit 1
fi
mkdir -p "$session_dir" "$attempt_dir"

source_rev=$(git -C "$repo_root" rev-parse HEAD 2>/dev/null || printf unknown)
base_sha256=$(sha256sum "$base" | awk '{print $1}')

if [[ "$resume" == 1 ]]; then
    for required in "$manifest" "$node70" "$node71" "$seed70" "$seed71"; do
        if [[ ! -f "$required" ]]; then
            echo "two-node lab: cannot resume $session_id; missing $required" >&2
            exit 1
        fi
    done
    # shellcheck disable=SC1090
    source "$manifest"
    if [[ "${LAB_SESSION_ID:-}" != "$session_id" ]]; then
        echo "two-node lab: session manifest mismatch" >&2
        exit 1
    fi
    echo "two-node lab: resuming session=${session_id} attempt=${attempt_id}"
else
    cp --reflink=auto "$base" "$node70"
    cp --reflink=auto "$base" "$node71"

    "$repo_root/tests/lab/make-nocloud-seed.sh" \
        "$seed70" "$session_id" 31.70 DN70 "$lan70" "$lan71" "$mgmt70"
    "$repo_root/tests/lab/make-nocloud-seed.sh" \
        "$seed71" "$session_id" 31.71 DN71 "$lan71" "$lan70" "$mgmt71"

    cat >"$manifest" <<EOF_SESSION
LAB_SESSION_ID=$session_id
CREATED_UTC=$(date -u +%Y-%m-%dT%H:%M:%SZ)
SOURCE_REV=$source_rev
BASE_IMAGE_SHA256=$base_sha256
DN70_IMAGE=dn70.qcow2
DN71_IMAGE=dn71.qcow2
DN70_SEED=dn70.seed.iso
DN71_SEED=dn71.seed.iso
DN70_LAN_MAC=$lan70
DN71_LAN_MAC=$lan71
DN70_MGMT_MAC=$mgmt70
DN71_MGMT_MAC=$mgmt71
EOF_SESSION
    echo "two-node lab: created session=${session_id} attempt=${attempt_id}"
fi

cat >"$attempt_manifest" <<EOF_ATTEMPT
LAB_SESSION_ID=$session_id
LAB_ATTEMPT_ID=$attempt_id
RESUME=$resume
STARTED_UTC=$(date -u +%Y-%m-%dT%H:%M:%SZ)
SOURCE_REV=$source_rev
BASE_IMAGE_SHA256=$base_sha256
DN70_LOG=dn70.serial.log
DN71_LOG=dn71.serial.log
PCAP=lan.pcap
EOF_ATTEMPT
printf '%s\n' "$attempt_id" >"$session_dir/latest-attempt"

suffix=$(printf '%s' "$session_id" | sha256sum | cut -c1-6)
bridge="db${suffix}"
tap70="d70${suffix}"
tap71="d71${suffix}"

cleanup() {
    set +e
    [[ -n "${Q70_PID:-}" ]] && kill "$Q70_PID" 2>/dev/null
    [[ -n "${Q71_PID:-}" ]] && kill "$Q71_PID" 2>/dev/null
    [[ -n "${TCPDUMP_PID:-}" ]] && sudo kill "$TCPDUMP_PID" 2>/dev/null
    for tap in "$tap70" "$tap71"; do
        sudo ip link del "$tap" 2>/dev/null
    done
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

accel=tcg
if [[ -e /dev/kvm && -r /dev/kvm && -w /dev/kvm ]]; then
    accel=kvm
fi
echo "two-node lab: session=${session_id} attempt=${attempt_id} QEMU acceleration=${accel}"

qemu-system-x86_64 \
    -name "DN70-${session_id}" \
    -pidfile "$attempt_dir/dn70.pid" \
    -accel "$accel" -m 512 -smp 1 \
    -drive "file=$node70,if=virtio,format=qcow2" \
    -drive "file=$seed70,format=raw,media=cdrom,readonly=on" \
    -netdev tap,id=lan70,ifname="$tap70",script=no,downscript=no \
    -device virtio-net-pci,netdev=lan70,mac="$lan70" \
    -netdev user,id=mgmt70 \
    -device virtio-net-pci,netdev=mgmt70,mac="$mgmt70" \
    -display none -monitor none -serial "file:$log70" &
Q70_PID=$!

qemu-system-x86_64 \
    -name "DN71-${session_id}" \
    -pidfile "$attempt_dir/dn71.pid" \
    -accel "$accel" -m 512 -smp 1 \
    -drive "file=$node71,if=virtio,format=qcow2" \
    -drive "file=$seed71,format=raw,media=cdrom,readonly=on" \
    -netdev tap,id=lan71,ifname="$tap71",script=no,downscript=no \
    -device virtio-net-pci,netdev=lan71,mac="$lan71" \
    -netdev user,id=mgmt71 \
    -device virtio-net-pci,netdev=mgmt71,mac="$mgmt71" \
    -display none -monitor none -serial "file:$log71" &
Q71_PID=$!

deadline=$((SECONDS + 600))
finished=0
while (( SECONDS < deadline )); do
    done70=0
    done71=0
    grep -q "DNIV-LAB-DONE session=${session_id} node=DN70" "$log70" 2>/dev/null && done70=1
    grep -q "DNIV-LAB-DONE session=${session_id} node=DN71" "$log71" 2>/dev/null && done71=1
    if (( done70 && done71 )); then
        finished=1
        break
    fi
    sleep 2
done

if (( ! finished )); then
    echo "two-node lab: session=${session_id} attempt=${attempt_id} guests did not finish before timeout" >&2
    echo "--- DN70 serial tail ---" >&2
    tail -120 "$log70" 2>/dev/null >&2 || true
    echo "--- DN71 serial tail ---" >&2
    tail -120 "$log71" 2>/dev/null >&2 || true
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
grep -q 'module=.*/kernel/extra/akms/decnet_iv.ko' "$log70"
grep -q 'module=.*/kernel/extra/akms/decnet_iv.ko' "$log71"

frames=$(sudo tcpdump -nn -r "$pcap" 'ether proto 0x6003' 2>/dev/null | wc -l)
if (( frames < 2 )); then
    echo "two-node lab: expected DECnet routing frames, saw $frames" >&2
    exit 1
fi

cat >>"$attempt_manifest" <<EOF_RESULT
COMPLETED_UTC=$(date -u +%Y-%m-%dT%H:%M:%SZ)
RESULT=pass
CAPTURED_DECNET_FRAMES=$frames
EOF_RESULT

echo "two-node lab: session=${session_id} DN70 and DN71 both received EtherType 0x6003 frames ($frames captured)"
