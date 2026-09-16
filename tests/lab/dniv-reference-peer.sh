#!/bin/sh
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

set -eu

get_arg() {
    key=$1
    for arg in $(cat /proc/cmdline); do
        case "$arg" in
            "$key"=*) printf '%s\n' "${arg#*=}"; return 0 ;;
        esac
    done
    return 1
}

find_iface() {
    i=0
    while [ "$i" -lt 100 ]; do
        for path in /sys/class/net/*; do
            candidate=${path##*/}
            if [ "$candidate" != lo ]; then
                printf '%s\n' "$candidate"
                return 0
            fi
        done
        i=$((i + 1))
        sleep 0.1
    done
    return 1
}

reference=$(get_arg dniv.reference || true)
expected_sha=$(get_arg dniv.ref_sha || true)
area=$(get_arg dniv.area || true)
node=$(get_arg dniv.node || true)
name=$(get_arg dniv.name || printf 'DN71')
peer_mac=$(get_arg dniv.peer || true)
peer_node=$(get_arg dniv.peer_node || true)
scenario=$(get_arg dniv.scenario || true)
session=$(get_arg dniv.session || printf 'local')

case "$reference" in route20|pydecnet) ;; *) echo "DNIV-REF-FAIL session=$session reason=bad-reference"; exit 1 ;; esac
case "$scenario" in l1|l2|endnode|router-endnode) ;; *) echo "DNIV-REF-FAIL session=$session reason=bad-scenario"; exit 1 ;; esac
if [ "$scenario" = router-endnode ] && [ "$reference" != pydecnet ]; then
    echo "DNIV-REF-FAIL session=$session reason=unsupported-reference-role"
    exit 1
fi
for value in "$expected_sha" "$area" "$node" "$peer_mac" "$peer_node"; do
    [ -n "$value" ] || { echo "DNIV-REF-FAIL session=$session reason=missing-argument"; exit 1; }
done

if grep -q '^decnet_iv ' /proc/modules; then
    echo "DNIV-REF-FAIL session=$session reason=candidate-module-loaded"
    exit 1
fi

mkdir -p /mnt/reference /run/reference
refdev=/dev/vdb
i=0
while [ "$i" -lt 100 ] && [ ! -b "$refdev" ]; do
    i=$((i + 1))
    sleep 0.1
done
[ -b "$refdev" ] || { echo "DNIV-REF-FAIL session=$session reason=no-reference-disk"; exit 1; }
mount -o ro "$refdev" /mnt/reference

manifest_ref=$(sed -n 's/^REFERENCE=//p' /mnt/reference/manifest.env | head -1)
manifest_sha=$(sed -n 's/^REFERENCE_SHA=//p' /mnt/reference/manifest.env | head -1)
[ "$manifest_ref" = "$reference" ] || { echo "DNIV-REF-FAIL session=$session reason=reference-mismatch"; exit 1; }
[ "$manifest_sha" = "$expected_sha" ] || { echo "DNIV-REF-FAIL session=$session reason=sha-mismatch"; exit 1; }
(cd /mnt/reference && sha256sum -c SHA256SUMS)

iface=$(find_iface || true)
[ -n "$iface" ] || { echo "DNIV-REF-FAIL session=$session reason=no-interface"; exit 1; }
ip link set "$iface" up

probe_pid=
peer_pid=
cleanup() {
    set +e
    [ -n "$probe_pid" ] && kill "$probe_pid" 2>/dev/null || true
    [ -n "$peer_pid" ] && kill "$peer_pid" 2>/dev/null || true
    if [ "$reference" = route20 ] && [ -r /var/run/route20.pid ]; then
        kill "$(cat /var/run/route20.pid)" 2>/dev/null || true
    fi
}
trap cleanup EXIT INT TERM

probe_loop() {
    i=0
    while :; do
        i=$((i + 1))
        /usr/local/sbin/dnraw "$iface" "$peer_mac" "DNIV-INTEROP-PROBE-$session-$scenario-$i" || true
        sleep 0.5
    done
}

case "$scenario" in
    l2) ref_level=2; py_type=l2router ;;
    router-endnode) ref_level=1; py_type=endnode ;;
    *) ref_level=1; py_type=l1router ;;
esac

case "$reference" in
route20)
    cp /mnt/reference/route20 /run/reference/route20
    chmod 0755 /run/reference/route20
    cat > /run/reference/route20.ini <<EOF_ROUTE20
[node]
name=$name
level=$ref_level
address=$area.$node
priority=64

[ethernet]
interface=$iface
cost=3
EOF_ROUTE20
    rm -f /var/run/route20.pid
    /run/reference/route20 /run/reference/route20.ini
    i=0
    while [ "$i" -lt 100 ] && [ ! -s /var/run/route20.pid ]; do
        i=$((i + 1))
        sleep 0.1
    done
    [ -s /var/run/route20.pid ] || { echo "DNIV-REF-FAIL session=$session reason=route20-no-pid"; exit 1; }
    peer_pid=$(cat /var/run/route20.pid)
    kill -0 "$peer_pid" 2>/dev/null || { echo "DNIV-REF-FAIL session=$session reason=route20-dead"; exit 1; }
    ;;
pydecnet)
    tar -xf /mnt/reference/pydecnet.tar -C /run/reference
    cat > /run/reference/pydecnet.conf <<EOF_PYDECNET
routing $area.$node --type $py_type
node $area.$node $name
node $peer_node DN70
circuit ETH-0 Ethernet $iface --mode pcap --cost 3 --t3 2 --priority 64
EOF_PYDECNET
    (
        cd /run/reference/pydecnet
        exec env PYTHONPATH=. python3 -m decnet.main /run/reference/pydecnet.conf
    ) &
    peer_pid=$!
    sleep 3
    kill -0 "$peer_pid" 2>/dev/null || { echo "DNIV-REF-FAIL session=$session reason=pydecnet-dead"; exit 1; }
    ;;
esac

probe_loop &
probe_pid=$!
echo "DNIV-REF-READY session=$session reference=$reference sha=$expected_sha scenario=$scenario node=$name"

while kill -0 "$peer_pid" 2>/dev/null; do
    if grep -q '^decnet_iv ' /proc/modules; then
        echo "DNIV-REF-FAIL session=$session reason=candidate-module-loaded-late"
        exit 1
    fi
    sleep 1
done

echo "DNIV-REF-FAIL session=$session reason=reference-exited"
exit 1
