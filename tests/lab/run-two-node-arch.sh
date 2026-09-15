#!/bin/bash
set -euo pipefail

if [[ $# -ne 3 ]]; then
    echo "usage: $0 MODE BASE-X86_64-QCOW2 BASE-AARCH64-QCOW2" >&2
    echo "MODE is arm-arm, x86-arm, or arm-x86" >&2
    exit 2
fi

mode=$1
base_x86=$2
base_arm=$3
case "$mode" in
    arm-arm)
        arch70=arm64; arch71=arm64; base70=$base_arm; base71=$base_arm ;;
    x86-arm)
        arch70=x86_64; arch71=arm64; base70=$base_x86; base71=$base_arm ;;
    arm-x86)
        arch70=arm64; arch71=x86_64; base70=$base_arm; base71=$base_x86 ;;
    *)
        echo "two-node arch lab: invalid mode: $mode" >&2
        exit 2 ;;
esac

repo_root=$(cd "$(dirname "$0")/../.." && pwd)
artifacts=${DNIV_LAB_ARTIFACTS:-"$repo_root/tests/lab/artifacts"}
run_tag=${GITHUB_RUN_ID:-local}
attempt_tag=${GITHUB_RUN_ATTEMPT:-1}
session_id=${DNIV_LAB_SESSION_ID:-"${mode}-gha-${run_tag}"}
attempt_id=${DNIV_LAB_ATTEMPT_ID:-"gha-${run_tag}-${attempt_tag}-${mode}"}
disk_bytes=${DNIV_LAB_DISK_BYTES:-4294967296}
timeout_seconds=${DNIV_LAB_TIMEOUT_SECONDS:-2400}
firmware=${DNIV_AARCH64_UEFI:-}

for value in "$session_id" "$attempt_id"; do
    if [[ ! "$value" =~ ^[A-Za-z0-9._-]+$ ]]; then
        echo "two-node arch lab: invalid session/attempt id: $value" >&2
        exit 2
    fi
done
if [[ ! "$disk_bytes" =~ ^[0-9]+$ ]] || (( disk_bytes < 1073741824 )); then
    echo "two-node arch lab: DNIV_LAB_DISK_BYTES must be an integer >= 1073741824" >&2
    exit 2
fi
if [[ ! "$timeout_seconds" =~ ^[0-9]+$ ]] || (( timeout_seconds < 60 )); then
    echo "two-node arch lab: DNIV_LAB_TIMEOUT_SECONDS must be an integer >= 60" >&2
    exit 2
fi
if [[ "$arch70" == arm64 || "$arch71" == arm64 ]]; then
    if [[ -z "$firmware" || ! -r "$firmware" ]]; then
        echo "two-node arch lab: DNIV_AARCH64_UEFI must name readable AArch64 UEFI firmware" >&2
        exit 2
    fi
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

mkdir -p "$session_dir" "$attempt_dir"
if [[ -e "$manifest" ]]; then
    echo "two-node arch lab: session $session_id already exists" >&2
    exit 1
fi

cp --reflink=auto "$base70" "$node70"
cp --reflink=auto "$base71" "$node71"
qemu-img resize "$node70" "$disk_bytes"
qemu-img resize "$node71" "$disk_bytes"

"$repo_root/tests/lab/make-nocloud-seed.sh" \
    "$seed70" "$session_id" 31.70 DN70 "$lan70" "$lan71" "$mgmt70"
"$repo_root/tests/lab/make-nocloud-seed.sh" \
    "$seed71" "$session_id" 31.71 DN71 "$lan71" "$lan70" "$mgmt71"

runner_source_rev=$(git -C "$repo_root" rev-parse HEAD 2>/dev/null || printf unknown)
sha70=$(sha256sum "$base70" | awk '{print $1}')
sha71=$(sha256sum "$base71" | awk '{print $1}')
cat >"$manifest" <<EOF_SESSION
LAB_SESSION_ID=$session_id
CREATED_UTC=$(date -u +%Y-%m-%dT%H:%M:%SZ)
SOURCE_REV=$runner_source_rev
MODE=$mode
DN70_ARCH=$arch70
DN71_ARCH=$arch71
DN70_BASE_IMAGE_SHA256=$sha70
DN71_BASE_IMAGE_SHA256=$sha71
DISK_VIRTUAL_SIZE_BYTES=$disk_bytes
DN70_IMAGE=dn70.qcow2
DN71_IMAGE=dn71.qcow2
DN70_SEED=dn70.seed.iso
DN71_SEED=dn71.seed.iso
DN70_LAN_MAC=$lan70
DN71_LAN_MAC=$lan71
DN70_MGMT_MAC=$mgmt70
DN71_MGMT_MAC=$mgmt71
EOF_SESSION

cat >"$attempt_manifest" <<EOF_ATTEMPT
LAB_SESSION_ID=$session_id
LAB_ATTEMPT_ID=$attempt_id
STARTED_UTC=$(date -u +%Y-%m-%dT%H:%M:%SZ)
RUNNER_SOURCE_REV=$runner_source_rev
MODE=$mode
DN70_ARCH=$arch70
DN71_ARCH=$arch71
DN70_BASE_IMAGE_SHA256=$sha70
DN71_BASE_IMAGE_SHA256=$sha71
DISK_VIRTUAL_SIZE_BYTES=$disk_bytes
TIMEOUT_SECONDS=$timeout_seconds
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

host_arch=$(uname -m)
x86_accel=tcg
if [[ "$host_arch" == x86_64 && -e /dev/kvm && -r /dev/kvm && -w /dev/kvm ]]; then
    x86_accel=kvm
fi
arm_accel=tcg
arm_cpu=max
if [[ "$host_arch" == aarch64 && -e /dev/kvm && -r /dev/kvm && -w /dev/kvm ]]; then
    arm_accel=kvm
    arm_cpu=host
fi

echo "two-node arch lab: session=${session_id} mode=${mode} host=${host_arch} x86-accel=${x86_accel} arm-accel=${arm_accel}"

qemu_node() {
    local arch=$1 image=$2 seed=$3 log=$4 pidfile=$5 tap=$6 lan_mac=$7 mgmt_mac=$8 name=$9
    if [[ "$arch" == x86_64 ]]; then
        exec qemu-system-x86_64 \
            -name "${name}-${session_id}" \
            -pidfile "$pidfile" \
            -accel "$x86_accel" -m 512 -smp 1 \
            -smbios type=1,serial=ds=nocloud \
            -drive "file=$image,if=virtio,format=qcow2" \
            -drive "file=$seed,format=raw,media=cdrom,readonly=on" \
            -netdev tap,id=lan,ifname="$tap",script=no,downscript=no \
            -device virtio-net-pci,netdev=lan,mac="$lan_mac" \
            -netdev user,id=mgmt \
            -device virtio-net-pci,netdev=mgmt,mac="$mgmt_mac" \
            -display none -monitor none -serial "file:$log"
    fi

    exec qemu-system-aarch64 \
        -name "${name}-${session_id}" \
        -pidfile "$pidfile" \
        -machine virt -accel "$arm_accel" -cpu "$arm_cpu" -m 1024 -smp 2 \
        -bios "$firmware" \
        -smbios type=1,serial=ds=nocloud \
        -drive "file=$image,if=virtio,format=qcow2" \
        -device virtio-scsi-pci,id=seedscsi \
        -drive "file=$seed,if=none,format=raw,media=cdrom,readonly=on,id=cidata" \
        -device scsi-cd,drive=cidata,bus=seedscsi.0 \
        -netdev tap,id=lan,ifname="$tap",script=no,downscript=no \
        -device virtio-net-pci,netdev=lan,mac="$lan_mac" \
        -netdev user,id=mgmt \
        -device virtio-net-pci,netdev=mgmt,mac="$mgmt_mac" \
        -display none -monitor none -serial "file:$log"
}

qemu_node "$arch70" "$node70" "$seed70" "$log70" "$attempt_dir/dn70.pid" "$tap70" "$lan70" "$mgmt70" DN70 &
Q70_PID=$!
qemu_node "$arch71" "$node71" "$seed71" "$log71" "$attempt_dir/dn71.pid" "$tap71" "$lan71" "$mgmt71" DN71 &
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
    if (( done70 && done71 )); then
        finished=1
        break
    fi
    if (( ! done70 )) && ! guest_running "$Q70_PID"; then
        failure_reason=dn70-exit-before-completion
        echo "two-node arch lab: mode=${mode} DN70 exited before reporting completion" >&2
        break
    fi
    if (( ! done71 )) && ! guest_running "$Q71_PID"; then
        failure_reason=dn71-exit-before-completion
        echo "two-node arch lab: mode=${mode} DN71 exited before reporting completion" >&2
        break
    fi
    sleep 2
done

if (( ! finished )); then
    record_failure "$failure_reason"
    echo "two-node arch lab: session=${session_id} mode=${mode} guests did not finish: ${failure_reason}" >&2
    kill "$Q70_PID" "$Q71_PID" 2>/dev/null || true
    wait "$Q70_PID" 2>/dev/null || true
    wait "$Q71_PID" 2>/dev/null || true
    unset Q70_PID Q71_PID
    echo "--- DN70 serial tail ---" >&2
    tail -160 "$log70" 2>/dev/null >&2 || true
    echo "--- DN71 serial tail ---" >&2
    tail -160 "$log71" 2>/dev/null >&2 || true
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
    echo "two-node arch lab: mode=${mode} guest exit status DN70=${q70_rc} DN71=${q71_rc}" >&2
    exit 1
fi
if ! grep -Eq 'Routing frames received = [1-9][0-9]*' "$log70"; then
    record_failure dn70-no-routing-rx
    echo "two-node arch lab: mode=${mode} DN70 did not report received routing frames" >&2
    exit 1
fi
if ! grep -Eq 'Routing frames received = [1-9][0-9]*' "$log71"; then
    record_failure dn71-no-routing-rx
    echo "two-node arch lab: mode=${mode} DN71 did not report received routing frames" >&2
    exit 1
fi
if ! grep -q 'module=.*/kernel/extra/akms/decnet_iv.ko' "$log70"; then
    record_failure dn70-module-path
    echo "two-node arch lab: mode=${mode} DN70 did not prove the AKMS module path" >&2
    exit 1
fi
if ! grep -q 'module=.*/kernel/extra/akms/decnet_iv.ko' "$log71"; then
    record_failure dn71-module-path
    echo "two-node arch lab: mode=${mode} DN71 did not prove the AKMS module path" >&2
    exit 1
fi
if ! frames=$(sudo tcpdump -nn -r "$pcap" 'ether proto 0x6003' 2>/dev/null | wc -l); then
    record_failure pcap-read
    echo "two-node arch lab: mode=${mode} could not read DECnet routing capture" >&2
    exit 1
fi
if (( frames < 2 )); then
    record_failure pcap-routing-frames
    echo "two-node arch lab: expected DECnet routing frames, saw $frames" >&2
    exit 1
fi

cat >>"$attempt_manifest" <<EOF_RESULT
COMPLETED_UTC=$(date -u +%Y-%m-%dT%H:%M:%SZ)
RESULT=pass
CAPTURED_DECNET_FRAMES=$frames
EOF_RESULT

echo "two-node arch lab: mode=${mode} DN70(${arch70}) and DN71(${arch71}) both received EtherType 0x6003 frames ($frames captured)"
