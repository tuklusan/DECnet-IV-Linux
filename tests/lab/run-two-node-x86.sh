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
disk_bytes=${DNIV_LAB_DISK_BYTES:-4294967296}
timeout_seconds=${DNIV_LAB_TIMEOUT_SECONDS:-1200}

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
if [[ ! "$disk_bytes" =~ ^[0-9]+$ ]] || (( disk_bytes < 1073741824 )); then
    echo "two-node lab: DNIV_LAB_DISK_BYTES must be an integer >= 1073741824" >&2
    exit 2
fi
if [[ ! "$timeout_seconds" =~ ^[0-9]+$ ]] || (( timeout_seconds < 60 )); then
    echo "two-node lab: DNIV_LAB_TIMEOUT_SECONDS must be an integer >= 60" >&2
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

grow_qcow2() {
    local image=$1 current
    current=$(qemu-img info --output=json "$image" | python3 -c 'import json,sys; print(json.load(sys.stdin)["virtual-size"])')
    if (( current < disk_bytes )); then
        echo "two-node lab: growing $(basename "$image") from ${current} to ${disk_bytes} bytes"
        qemu-img resize "$image" "$disk_bytes"
    fi
}

set_manifest_value() {
    local key=$1 value=$2 file=$3 tmp
    tmp="${file}.tmp"
    awk -F= -v key="$key" -v value="$value" '
        BEGIN { found = 0 }
        $1 == key { print key "=" value; found = 1; next }
        { print }
        END { if (!found) print key "=" value }
    ' "$file" >"$tmp"
    mv "$tmp" "$file"
}

reset_incomplete_bootstrap() (
    set -euo pipefail
    local image=$1 node_name=$2 nbd=/dev/nbd0 rootdev mnt
    mnt=$(mktemp -d)
    cleanup_nbd() {
        set +e
        mountpoint -q "$mnt" && sudo umount "$mnt"
        sudo qemu-nbd --disconnect "$nbd" >/dev/null 2>&1
        rmdir "$mnt" 2>/dev/null
    }
    trap cleanup_nbd EXIT

    sudo modprobe nbd max_part=16
    sudo qemu-nbd --disconnect "$nbd" >/dev/null 2>&1 || true
    sudo qemu-nbd --connect="$nbd" "$image"
    sudo udevadm settle || true

    rootdev=$(lsblk -nrpo NAME,FSTYPE,LABEL "$nbd" | awk '$2 ~ /^ext[234]$/ && $3 == "/" { print $1; exit }')
    if [[ -z "$rootdev" ]]; then
        rootdev=$(lsblk -nrpo NAME,FSTYPE "$nbd" | awk '$2 ~ /^ext[234]$/ { print $1; exit }')
    fi
    if [[ -z "$rootdev" ]]; then
        echo "two-node lab: cannot find ext root filesystem in $image" >&2
        exit 1
    fi

    sudo mount "$rootdev" "$mnt"
    if sudo test -f "$mnt/var/lib/decnet-lab/provisioned"; then
        echo "two-node lab: ${node_name} already provisioned; preserving Tiny Cloud completion state" >&2
        printf '%s\n' provisioned
    else
        sudo rm -f "$mnt/var/lib/cloud/.bootstrap-complete"
        echo "two-node lab: ${node_name} incomplete; Tiny Cloud bootstrap reset for retry" >&2
        printf '%s\n' incomplete
    fi
)

mkdir -p "$artifacts/sessions"
if [[ "$resume" == 0 && -e "$manifest" ]]; then
    echo "two-node lab: session $session_id already exists; set DNIV_LAB_RESUME=1 to reuse it" >&2
    exit 1
fi
mkdir -p "$session_dir" "$attempt_dir"

runner_source_rev=$(git -C "$repo_root" rev-parse HEAD 2>/dev/null || printf unknown)
runner_base_sha256=$(sha256sum "$base" | awk '{print $1}')
session_source_rev=$runner_source_rev
session_base_sha256=$runner_base_sha256
seed70_source_rev=$runner_source_rev
seed71_source_rev=$runner_source_rev

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
    session_source_rev=${SOURCE_REV:-unknown}
    session_base_sha256=${BASE_IMAGE_SHA256:-unknown}
    seed70_source_rev=${DN70_SEED_SOURCE_REV:-$session_source_rev}
    seed71_source_rev=${DN71_SEED_SOURCE_REV:-$session_source_rev}

    grow_qcow2 "$node70"
    grow_qcow2 "$node71"
    state70=$(reset_incomplete_bootstrap "$node70" DN70)
    state71=$(reset_incomplete_bootstrap "$node71" DN71)

    if [[ "$state70" == incomplete ]]; then
        "$repo_root/tests/lab/make-nocloud-seed.sh" \
            "$seed70" "$session_id" 31.70 DN70 "$lan70" "$lan71" "$mgmt70"
        seed70_source_rev=$runner_source_rev
        set_manifest_value DN70_SEED_SOURCE_REV "$seed70_source_rev" "$manifest"
    fi
    if [[ "$state71" == incomplete ]]; then
        "$repo_root/tests/lab/make-nocloud-seed.sh" \
            "$seed71" "$session_id" 31.71 DN71 "$lan71" "$lan70" "$mgmt71"
        seed71_source_rev=$runner_source_rev
        set_manifest_value DN71_SEED_SOURCE_REV "$seed71_source_rev" "$manifest"
    fi
    set_manifest_value DISK_VIRTUAL_SIZE_BYTES "$disk_bytes" "$manifest"

    echo "two-node lab: resuming session=${session_id} attempt=${attempt_id} session-source=${session_source_rev} runner-source=${runner_source_rev}"
else
    cp --reflink=auto "$base" "$node70"
    cp --reflink=auto "$base" "$node71"
    grow_qcow2 "$node70"
    grow_qcow2 "$node71"

    "$repo_root/tests/lab/make-nocloud-seed.sh" \
        "$seed70" "$session_id" 31.70 DN70 "$lan70" "$lan71" "$mgmt70"
    "$repo_root/tests/lab/make-nocloud-seed.sh" \
        "$seed71" "$session_id" 31.71 DN71 "$lan71" "$lan70" "$mgmt71"

    cat >"$manifest" <<EOF_SESSION
LAB_SESSION_ID=$session_id
CREATED_UTC=$(date -u +%Y-%m-%dT%H:%M:%SZ)
SOURCE_REV=$runner_source_rev
BASE_IMAGE_SHA256=$runner_base_sha256
DISK_VIRTUAL_SIZE_BYTES=$disk_bytes
DN70_IMAGE=dn70.qcow2
DN71_IMAGE=dn71.qcow2
DN70_SEED=dn70.seed.iso
DN71_SEED=dn71.seed.iso
DN70_SEED_SOURCE_REV=$seed70_source_rev
DN71_SEED_SOURCE_REV=$seed71_source_rev
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
SOURCE_REV=$session_source_rev
SESSION_SOURCE_REV=$session_source_rev
RUNNER_SOURCE_REV=$runner_source_rev
BASE_IMAGE_SHA256=$session_base_sha256
SESSION_BASE_IMAGE_SHA256=$session_base_sha256
RUNNER_BASE_IMAGE_SHA256=$runner_base_sha256
DISK_VIRTUAL_SIZE_BYTES=$disk_bytes
TIMEOUT_SECONDS=$timeout_seconds
DN70_SEED_SOURCE_REV=$seed70_source_rev
DN71_SEED_SOURCE_REV=$seed71_source_rev
DN70_LOG=dn70.serial.log
DN71_LOG=dn71.serial.log
PCAP=lan.pcap
EOF_ATTEMPT
printf '%s\n' "$attempt_id" >"$session_dir/latest-attempt"

guest_running() {
    local pid=$1 stat tail proc_state proc_ppid rest
    [[ -r "/proc/$pid/stat" ]] || return 1
    IFS= read -r stat <"/proc/$pid/stat" || return 1
    tail=${stat##*) }
    read -r proc_state proc_ppid rest <<<"$tail"
    [[ "$proc_ppid" == "$$" && "$proc_state" != Z && "$proc_state" != X && "$proc_state" != x ]]
}

record_failure() {
    local reason=$1
    cat >>"$attempt_manifest" <<EOF_FAILURE
COMPLETED_UTC=$(date -u +%Y-%m-%dT%H:%M:%SZ)
RESULT=fail
FAILURE_REASON=$reason
EOF_FAILURE
}

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
    -smbios type=1,serial=ds=nocloud \
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
    -smbios type=1,serial=ds=nocloud \
    -drive "file=$node71,if=virtio,format=qcow2" \
    -drive "file=$seed71,format=raw,media=cdrom,readonly=on" \
    -netdev tap,id=lan71,ifname="$tap71",script=no,downscript=no \
    -device virtio-net-pci,netdev=lan71,mac="$lan71" \
    -netdev user,id=mgmt71 \
    -device virtio-net-pci,netdev=mgmt71,mac="$mgmt71" \
    -display none -monitor none -serial "file:$log71" &
Q71_PID=$!

marker70="DNIV-LAB-DONE session=${session_id} node=DN70"
marker71="DNIV-LAB-DONE session=${session_id} node=DN71"
deadline=$((SECONDS + timeout_seconds))
finished=0
failure_reason=timeout
while (( SECONDS < deadline )); do
    done70=0
    done71=0
    grep -Fq "$marker70" "$log70" 2>/dev/null && done70=1
    grep -Fq "$marker71" "$log71" 2>/dev/null && done71=1

    if (( ! done70 )) && ! guest_running "$Q70_PID"; then
        grep -Fq "$marker70" "$log70" 2>/dev/null && done70=1
        if (( ! done70 )); then
            failure_reason=dn70-exit-before-completion
            echo "two-node lab: DN70 exited before reporting completion" >&2
            break
        fi
    fi
    if (( ! done71 )) && ! guest_running "$Q71_PID"; then
        grep -Fq "$marker71" "$log71" 2>/dev/null && done71=1
        if (( ! done71 )); then
            failure_reason=dn71-exit-before-completion
            echo "two-node lab: DN71 exited before reporting completion" >&2
            break
        fi
    fi
    if (( done70 && done71 )); then
        finished=1
        break
    fi
    sleep 2
done

if (( ! finished )); then
    record_failure "$failure_reason"
    echo "two-node lab: session=${session_id} attempt=${attempt_id} guests did not finish: ${failure_reason}" >&2
    kill "$Q70_PID" "$Q71_PID" 2>/dev/null || true
    wait "$Q70_PID" 2>/dev/null || true
    wait "$Q71_PID" 2>/dev/null || true
    unset Q70_PID Q71_PID
    echo "--- DN70 serial tail ---" >&2
    tail -120 "$log70" 2>/dev/null >&2 || true
    echo "--- DN71 serial tail ---" >&2
    tail -120 "$log71" 2>/dev/null >&2 || true
    exit 1
fi

q70_rc=0
q71_rc=0
wait "$Q70_PID" || q70_rc=$?
unset Q70_PID
wait "$Q71_PID" || q71_rc=$?
unset Q71_PID
sudo kill "$TCPDUMP_PID" 2>/dev/null || true
wait "$TCPDUMP_PID" 2>/dev/null || true
unset TCPDUMP_PID

if (( q70_rc != 0 || q71_rc != 0 )); then
    record_failure qemu-exit-status
    echo "two-node lab: guest exit status DN70=${q70_rc} DN71=${q71_rc}" >&2
    exit 1
fi
if ! grep -Eq 'Routing frames received = [1-9][0-9]*' "$log70"; then
    record_failure dn70-no-routing-rx
    echo "two-node lab: DN70 did not report received routing frames" >&2
    exit 1
fi
if ! grep -Eq 'Routing frames received = [1-9][0-9]*' "$log71"; then
    record_failure dn71-no-routing-rx
    echo "two-node lab: DN71 did not report received routing frames" >&2
    exit 1
fi
if ! grep -q 'module=.*/kernel/extra/akms/decnet_iv.ko' "$log70"; then
    record_failure dn70-module-path
    echo "two-node lab: DN70 did not prove the AKMS module path" >&2
    exit 1
fi
if ! grep -q 'module=.*/kernel/extra/akms/decnet_iv.ko' "$log71"; then
    record_failure dn71-module-path
    echo "two-node lab: DN71 did not prove the AKMS module path" >&2
    exit 1
fi
if ! frames=$(sudo tcpdump -nn -r "$pcap" 'ether proto 0x6003' 2>/dev/null | wc -l); then
    record_failure pcap-read
    echo "two-node lab: could not read DECnet routing capture" >&2
    exit 1
fi
if (( frames < 2 )); then
    record_failure pcap-routing-frames
    echo "two-node lab: expected DECnet routing frames, saw $frames" >&2
    exit 1
fi

cat >>"$attempt_manifest" <<EOF_RESULT
COMPLETED_UTC=$(date -u +%Y-%m-%dT%H:%M:%SZ)
RESULT=pass
CAPTURED_DECNET_FRAMES=$frames
EOF_RESULT

echo "two-node lab: session=${session_id} DN70 and DN71 both received EtherType 0x6003 frames ($frames captured)"
