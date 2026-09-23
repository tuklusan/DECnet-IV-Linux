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

stats_snapshot() {
    tries=${1:-8}
    dnctl=${DNIV_DNCTL:-/usr/local/sbin/dnctl}
    i=0
    while [ "$i" -lt "$tries" ]; do
        stats=$("$dnctl" stats 2>/dev/null || true)
        routing=$(printf '%s\n' "$stats" | sed -n 's/^Routing frames received[[:space:]]*=[[:space:]]*//p')
        hello=$(printf '%s\n' "$stats" | sed -n 's/^Hello frames received[[:space:]]*=[[:space:]]*//p')
        valid=1
        for value in "$routing" "$hello"; do
            case "$value" in
                ''|*[!0-9]*) valid=0 ;;
            esac
        done
        if [ "$valid" -eq 1 ] && [ "$routing" -ge "$hello" ]; then
            printf '%s %s\n' "$routing" "$hello"
            return 0
        fi
        i=$((i + 1))
        sleep 0.02
    done
    return 1
}

wait_peer_up() {
    peer_address=$1
    peer_kind=$2
    marker=$3
    tries=$4
    init_seen=0
    i=0
    while [ "$i" -lt "$tries" ]; do
        output=$(/usr/local/sbin/dnctl adjacencies 2>/dev/null || true)
        printf '%s\n' "$output"
        if [ "$init_seen" -eq 0 ] && \
           printf '%s\n' "$output" | grep -F "$peer_address via " | \
               grep -Fq " $peer_kind INIT "; then
            init_seen=1
            echo "$marker-INIT session=$session scenario=$scenario node=$name peer=$peer_address"
        fi
        if printf '%s\n' "$output" | grep -F "$peer_address via " | \
           grep -Fq " $peer_kind UP "; then
            return 0
        fi
        i=$((i + 1))
        sleep 0.25
    done
    return 1
}

wait_post_change_hello() {
    peer_address=$1
    peer_kind=$2
    hello_baseline=$3
    tries=$4
    i=0
    while [ "$i" -lt "$tries" ]; do
        output=$(/usr/local/sbin/dnctl adjacencies 2>/dev/null || true)
        snapshot=$(stats_snapshot 8) || return 1
        set -- $snapshot
        hello_now=$2
        if [ "$hello_now" -gt "$hello_baseline" ] && \
           printf '%s\n' "$output" | grep -F "$peer_address via " | \
               grep -Fq " $peer_kind UP "; then
            return 0
        fi
        i=$((i + 1))
        sleep 0.25
    done
    return 1
}

nonhello_value() {
    snapshot=$(stats_snapshot 8) || return 1
    set -- $snapshot
    printf '%s\n' "$(($1 - $2))"
}

wait_unicast_delta() {
    baseline=$1
    tries=$2
    i=0
    while [ "$i" -lt "$tries" ]; do
        now=$(nonhello_value || true)
        case "$now" in
            ''|*[!0-9]*) return 1 ;;
        esac
        if [ "$((now - baseline))" -ge 3 ]; then
            echo "DNIV-INTEROP-UCAST session=$session scenario=$scenario node=$name delta=$((now - baseline))"
            return 0
        fi
        i=$((i + 1))
        sleep 0.25
    done
    return 1
}

poweroff_pass() {
    echo "DNIV-INTEROP-PASS session=$session scenario=$scenario node=$name"
    sync
    sleep 2
    poweroff -f
    exit 0
}

if [ "${1:-}" = --stats-selftest ]; then
    stats_snapshot "${2:-8}"
    exit $?
fi

area=$(get_arg dniv.area || printf '31')
node=$(get_arg dniv.node || printf '70')
name=$(get_arg dniv.name || printf 'DN70')
peer_node=$(get_arg dniv.peer_node || true)
reference=$(get_arg dniv.reference || true)
scenario=$(get_arg dniv.scenario || true)
session=$(get_arg dniv.session || printf 'local')
timer_proof=$(get_arg dniv.timer_proof || printf '0')
reserved_proof=$(get_arg dniv.reserved_proof || printf '0')
flow_proof=$(get_arg dniv.flow_proof || printf '0')

case "$reference" in
    route20|pydecnet) ;;
    *) echo "DNIV-INTEROP-FAIL session=$session reason=bad-reference"; exit 1 ;;
esac
case "$timer_proof" in
    0|1) ;;
    *) echo "DNIV-INTEROP-FAIL session=$session reason=bad-timer-proof"; exit 1 ;;
esac
case "$reserved_proof" in
    0|1) ;;
    *) echo "DNIV-INTEROP-FAIL session=$session reason=bad-reserved-proof"; exit 1 ;;
esac
case "$scenario" in
    l1) local_type=2; peer_kind='L1 router' ;;
    l2) local_type=1; peer_kind='L2 router' ;;
    endnode) local_type=3; peer_kind='L1 router' ;;
    router-endnode) local_type=2; peer_kind='endnode' ;;
    *) echo "DNIV-INTEROP-FAIL session=$session reason=bad-scenario"; exit 1 ;;
esac
[ -n "$peer_node" ] || { echo "DNIV-INTEROP-FAIL session=$session reason=missing-peer"; exit 1; }

iface=$(find_iface || true)
[ -n "$iface" ] || { echo "DNIV-INTEROP-FAIL session=$session reason=no-interface"; exit 1; }

modprobe decnet_iv default_area="$area" default_node="$node" default_name="$name" \
    default_node_type="$local_type" router_priority=64 hello_interval=2
/usr/local/sbin/dnctl set "$area.$node" "$name"
/usr/local/sbin/dnctl reset-stats
ip link set "$iface" up

if ! wait_peer_up "$peer_node" "$peer_kind" DNIV-INTEROP-INITIAL 600; then
    echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=initial-adjacency"
    exit 1
fi
echo "DNIV-INTEROP-UP session=$session scenario=$scenario node=$name peer=$peer_node"

if [ "$reference" = pydecnet ]; then
    snapshot=$(stats_snapshot 8) || {
        echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=nsp-ready-stats"
        exit 1
    }
    set -- $snapshot
    hello_ready_before=$2
    if ! wait_post_change_hello "$peer_node" "$peer_kind" "$hello_ready_before" 240; then
        echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=nsp-peer-not-responsive"
        exit 1
    fi
    echo "DNIV-INTEROP-NSP-READY session=$session scenario=$scenario node=$name peer=$peer_node"
    if ! /usr/local/sbin/dnnice "$peer_node"; then
        echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=remote-nice-read-node"
        exit 1
    fi
    for nice_query in status characteristics counters; do
        if ! /usr/local/sbin/dnnice "$peer_node" "$nice_query"; then
            echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=remote-nice-$nice_query"
            exit 1
        fi
    done
    if ! /usr/local/sbin/dnnice "$peer_node" node "$area.$node" status; then
        echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=remote-nice-specific-node"
        exit 1
    fi
    if ! /usr/local/sbin/dnnice "$peer_node" circuit ETH-0 status; then
        echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=remote-nice-circuit-status"
        exit 1
    fi
    if ! /usr/local/sbin/dnnice "$peer_node" circuit ETH-0 counters; then
        echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=remote-nice-circuit-counters"
        exit 1
    fi
    # The candidate can observe the peer endnode before that peer has
    # processed our router hello.  Bound the independent peer's reciprocal
    # adjacency convergence rather than treating the first empty NICE
    # "adjacent nodes" reply as a protocol failure.
    multi_nodes=
    multi_nodes_ok=0
    i=0
    while [ "$i" -lt 40 ]; do
        if multi_nodes=$(/usr/local/sbin/dnnice "$peer_node" nodes adjacent status); then
            multi_nodes_ok=1
            if printf '%s\n' "$multi_nodes" | grep -Fq "Node = $area.$node"; then
                break
            fi
        else
            multi_nodes_ok=0
        fi
        i=$((i + 1))
        sleep 0.25
    done
    if [ "$multi_nodes_ok" -ne 1 ]; then
        echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=remote-nice-multiple-nodes"
        exit 1
    fi
    printf '%s\n' "$multi_nodes"
    if ! printf '%s\n' "$multi_nodes" | grep -Fq "Node = $area.$node"; then
        echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=remote-nice-multiple-node-missing"
        exit 1
    fi
    multi_circuits=$(/usr/local/sbin/dnnice "$peer_node" circuits active status) || {
        echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=remote-nice-multiple-circuits"
        exit 1
    }
    printf '%s\n' "$multi_circuits"
    if ! printf '%s\n' "$multi_circuits" | grep -Fq "Circuit = ETH-0"; then
        echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=remote-nice-multiple-circuit-missing"
        exit 1
    fi
    multi_counters=$(/usr/local/sbin/dnnice "$peer_node" circuits active counters) || {
        echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=remote-nice-multiple-circuit-counters"
        exit 1
    }
    printf '%s\n' "$multi_counters"
    if ! printf '%s\n' "$multi_counters" | grep -Fq "Circuit = ETH-0"; then
        echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=remote-nice-multiple-circuit-counter-missing"
        exit 1
    fi
    echo "DNIV-INTEROP-REMOTE-NICE session=$session scenario=$scenario node=$name peer=$peer_node queries=summary,status,characteristics,counters,specific-node,circuit-status,circuit-counters,multiple-nodes,multiple-circuits,multiple-circuit-counters"
    if ! /usr/local/sbin/ncp tell "$peer_node" show executor status; then
        echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=ncp-remote-show"
        exit 1
    fi
    echo "DNIV-INTEROP-NCP session=$session scenario=$scenario node=$name peer=$peer_node command=show-executor-status"
    echo "DNIV-INTEROP-CTERM-READY session=$session scenario=$scenario node=$name peer=$peer_node"
    cterm_ok=0
    i=0
    while [ "$i" -lt 40 ]; do
        if /usr/local/sbin/dnlogin --probe "$peer_node"; then
            cterm_ok=1
            break
        fi
        i=$((i + 1))
        sleep 0.25
    done
    if [ "$cterm_ok" -ne 1 ]; then
        echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=cterm-foundation"
        exit 1
    fi
    sethost_ok=0
    for attempt in 1 2 3 4 5; do
        if /usr/local/bin/sethost --probe "$peer_node"; then
            sethost_ok=1
            break
        fi
        sleep 0.1
    done
    if [ "$sethost_ok" -ne 1 ]; then
        echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=sethost-foundation"
        exit 1
    fi
    dap_ok=0
    for attempt in 1 2 3 4 5; do
        if /usr/local/bin/dncopy --probe "$peer_node"; then
            dap_ok=1
            break
        fi
        sleep 0.1
    done
    if [ "$dap_ok" -ne 1 ]; then
        echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=dap-config"
        exit 1
    fi
    if ! dap_output=$(/usr/local/bin/dncopy --get "$peer_node" PHASE7.TXT); then
        echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=dap-get"
        exit 1
    fi
    if [ "$dap_output" != "DAP-PHASE7" ]; then
        echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=dap-get-content"
        printf '%s\n' "$dap_output"
        exit 1
    fi
    dap_local="/tmp/dniv-dap-phase7.$$"
    rm -f "$dap_local"
    if ! /usr/local/bin/dncopy -u DAPUSER -p DAPPASS -a DAPACCT --get-to "$peer_node" PHASE7.TXT "$dap_local"; then
        echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=dap-get-to"
        exit 1
    fi
    if [ "$(cat "$dap_local")" != "DAP-PHASE7" ]; then
        echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=dap-get-to-content"
        rm -f "$dap_local"
        exit 1
    fi
    rm -f "$dap_local"
    if ! dap_text_output=$(/usr/local/bin/dncopy --get-text "$peer_node" TEXT.TXT); then
        echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=dap-get-text"
        exit 1
    fi
    if [ "$dap_text_output" != "$(printf 'LINE1\nLINE2')" ]; then
        echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=dap-get-text-content"
        printf '%s\n' "$dap_text_output"
        exit 1
    fi
    dap_put="/tmp/dniv-dap-put.$$"
    if ! dd if=/dev/zero of="$dap_put" bs=1024 count=3 status=none; then
        echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=dap-put-fixture"
        exit 1
    fi
    if ! /usr/local/bin/dncopy --put "$dap_put" "$peer_node" UPLOAD.TXT; then
        echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=dap-put"
        rm -f "$dap_put"
        exit 1
    fi
    rm -f "$dap_put"
    dap_put_text="/tmp/dniv-dap-put-text.$"
    printf 'ALPHA\nBETA\n' >"$dap_put_text"
    if ! /usr/local/bin/dncopy --put-text "$dap_put_text" "$peer_node" TEXTUP.TXT; then
        echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=dap-put-text"
        rm -f "$dap_put_text"
        exit 1
    fi
    rm -f "$dap_put_text"
    if ! /usr/local/bin/dndel "$peer_node::UPLOAD.TXT"; then
        echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=dap-delete"
        exit 1
    fi
    if ! dap_dir_output=$(/usr/local/bin/dncopy --dir "$peer_node" '*.TXT'); then
        echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=dap-dir"
        exit 1
    fi
    if [ "$dap_dir_output" != "$(printf 'PHASE7.TXT\nTEXTUP.TXT')" ]; then
        echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=dap-dir-content"
        printf '%s\n' "$dap_dir_output"
        exit 1
    fi
    if ! dap_type_output=$(/usr/local/bin/dntype "$peer_node::PHASE7.TXT"); then
        echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=dntype"
        exit 1
    fi
    if [ "$dap_type_output" != "DAP-PHASE7" ]; then
        echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=dntype-content"
        printf '%s\n' "$dap_type_output"
        exit 1
    fi
    if ! dap_dndir_output=$(/usr/local/bin/dndir "$peer_node::*.TXT"); then
        echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=dndir"
        exit 1
    fi
    if [ "$dap_dndir_output" != "$(printf 'PHASE7.TXT\nTEXTUP.TXT')" ]; then
        echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=dndir-content"
        printf '%s\n' "$dap_dndir_output"
        exit 1
    fi
    dap_copy_local="/tmp/dniv-dap-copy.$$"
    rm -f "$dap_copy_local"
    if ! /usr/local/bin/dncopy "$peer_node::PHASE7.TXT" "$dap_copy_local"; then
        echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=dncopy-transparent-get"
        exit 1
    fi
    if [ "$(cat "$dap_copy_local")" != "DAP-PHASE7" ]; then
        echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=dncopy-transparent-get-content"
        rm -f "$dap_copy_local"
        exit 1
    fi
    printf 'COPY-A\nCOPY-B\n' >"$dap_copy_local"
    if ! /usr/local/bin/dncopy "$dap_copy_local" "$peer_node::COPYUP.TXT"; then
        echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=dncopy-transparent-put"
        rm -f "$dap_copy_local"
        exit 1
    fi
    rm -f "$dap_copy_local"
    printf 'META-A\nMETA-B\n' >"$dap_copy_local"
    if ! /usr/local/bin/dncopy -r vfc -c prn "$dap_copy_local" "$peer_node::METADATA.TXT"; then
        echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=dncopy-metadata-put"
        rm -f "$dap_copy_local"
        exit 1
    fi
    rm -f "$dap_copy_local"
    dap_block="/tmp/dniv-dap-block.$"
    rm -f "$dap_block"
    if ! /usr/local/bin/dncopy -m block "$peer_node::BLOCK.BIN" "$dap_block"; then
        echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=dncopy-block-get"
        exit 1
    fi
    if [ "$(od -An -tx1 -v "$dap_block" | tr -d ' \n')" != "00010203" ]; then
        echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=dncopy-block-get-content"
        rm -f "$dap_block"
        exit 1
    fi
    printf '\000\001\002\003' >"$dap_block"
    if ! /usr/local/bin/dncopy -m block "$dap_block" "$peer_node::BLOCKUP.BIN"; then
        echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=dncopy-block-put"
        rm -f "$dap_block"
        exit 1
    fi
    rm -f "$dap_block"
    if ! task_output=$(/usr/local/bin/dntask "$peer_node::TASKTEST"); then
        echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=dntask"
        exit 1
    fi
    if [ "$task_output" != "$(printf 'TASK-A\nTASK-B')" ]; then
        echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=dntask-content"
        printf '%s\n' "$task_output"
        exit 1
    fi
    echo "DNIV-INTEROP-DNTASK-PASS session=$session scenario=$scenario node=$name peer=$peer_node object=TASKTEST"
    if ! /usr/local/bin/dnsubmit "$peer_node::JOB.COM"; then
        echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=dnsubmit"
        exit 1
    fi
    echo "DNIV-INTEROP-DNSUBMIT-PASS session=$session scenario=$scenario node=$name peer=$peer_node file=JOB.COM"
    if ! /usr/local/bin/dnprint "$peer_node::PRINTME.LIS"; then
        echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=dnprint"
        exit 1
    fi
    echo "DNIV-INTEROP-DNPRINT-PASS session=$session scenario=$scenario node=$name peer=$peer_node file=PRINTME.LIS"
    if ! cterm_output=$(printf '\003phase7\r' | /usr/local/sbin/dnlogin -u CTERMUSER -p CTERMPASS -a CTERMACCT "$peer_node" 2>&1); then
        printf '%s\n' "$cterm_output"
        echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=cterm-interactive"
        exit 1
    fi
    printf '%s\n' "$cterm_output"
    if ! printf '%s\n' "$cterm_output" | grep -Fq "CTERM-READY" ||
       ! printf '%s\n' "$cterm_output" | grep -Fq "CTERM-DONE"; then
        echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=cterm-write-read"
        exit 1
    fi
    echo "DNIV-INTEROP-CTERM-PASS session=$session scenario=$scenario node=$name peer=$peer_node mode=interactive"
    /usr/local/sbin/dnnml --once &
    nml_pid=$!
    sleep 2
    if ! kill -0 "$nml_pid" 2>/dev/null; then
        echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=nml-listener-start"
        exit 1
    fi
    echo "DNIV-INTEROP-NML-READY session=$session scenario=$scenario node=$name peer=$peer_node"
    if ! wait "$nml_pid"; then
        echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=nml-read-node"
        exit 1
    fi
    echo "DNIV-INTEROP-NML-PASS session=$session scenario=$scenario node=$name peer=$peer_node"
    /usr/local/sbin/dnnml --sessions 3 &
    nml_pid=$!
    sleep 2
    if ! kill -0 "$nml_pid" 2>/dev/null; then
        echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=nml-concurrent-listener-start"
        exit 1
    fi
    echo "DNIV-INTEROP-NML-CONCURRENT-READY session=$session scenario=$scenario node=$name peer=$peer_node"
    if ! wait "$nml_pid"; then
        echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=nml-concurrent-sessions"
        exit 1
    fi
    echo "DNIV-INTEROP-NML-CONCURRENT-PASS session=$session scenario=$scenario node=$name peer=$peer_node"
    /usr/local/sbin/dnnml --once &
    nml_pid=$!
    sleep 2
    if ! kill -0 "$nml_pid" 2>/dev/null; then
        echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=nml-restart-listener-start"
        exit 1
    fi
    echo "DNIV-INTEROP-NML-RESTART-READY session=$session scenario=$scenario node=$name peer=$peer_node"
    if ! wait "$nml_pid"; then
        echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=nml-restart-session"
        exit 1
    fi
    echo "DNIV-INTEROP-NML-RESTART-PASS session=$session scenario=$scenario node=$name peer=$peer_node"
    /usr/local/sbin/dnmirror --once &
    mirror_pid=$!
    sleep 1
    if ! kill -0 "$mirror_pid" 2>/dev/null; then
        echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=mirror-listener-start"
        exit 1
    fi
    echo "DNIV-INTEROP-MIRROR-READY session=$session scenario=$scenario node=$name peer=$peer_node"
    if ! wait "$mirror_pid"; then
        echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=mirror-session"
        exit 1
    fi
    echo "DNIV-INTEROP-MIRROR-PASS session=$session scenario=$scenario node=$name peer=$peer_node"
    /usr/local/sbin/dnmirror --once --name &
    mirror_pid=$!
    sleep 1
    if ! kill -0 "$mirror_pid" 2>/dev/null; then
        echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=mirror-name-listener-start"
        exit 1
    fi
    echo "DNIV-INTEROP-MIRROR-NAME-READY session=$session scenario=$scenario node=$name peer=$peer_node"
    if ! wait "$mirror_pid"; then
        echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=mirror-name-session"
        exit 1
    fi
    echo "DNIV-INTEROP-MIRROR-NAME-PASS session=$session scenario=$scenario node=$name peer=$peer_node"
    /usr/local/sbin/dnmirror --once --name --require-access DNIVUSER DNIVPASS DNIVACCT &
    mirror_pid=$!
    sleep 1
    if ! kill -0 "$mirror_pid" 2>/dev/null; then
        echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=mirror-access-listener-start"
        exit 1
    fi
    echo "DNIV-INTEROP-MIRROR-ACCESS-READY session=$session scenario=$scenario node=$name peer=$peer_node"
    if ! wait "$mirror_pid"; then
        echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=mirror-access-session"
        exit 1
    fi
    echo "DNIV-INTEROP-MIRROR-ACCESS-PASS session=$session scenario=$scenario node=$name peer=$peer_node"
    /usr/local/sbin/dnmirror --once --name --require-access DNIVUSER DNIVPASS DNIVACCT &
    mirror_pid=$!
    sleep 1
    if ! kill -0 "$mirror_pid" 2>/dev/null; then
        echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=mirror-access-reject-listener-start"
        exit 1
    fi
    echo "DNIV-INTEROP-MIRROR-ACCESS-REJECT-READY session=$session scenario=$scenario node=$name peer=$peer_node"
    if ! wait "$mirror_pid"; then
        echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=mirror-access-reject-session"
        exit 1
    fi
    echo "DNIV-INTEROP-MIRROR-ACCESS-REJECT-PASS session=$session scenario=$scenario node=$name peer=$peer_node"
    /usr/local/sbin/dnobject --name DNIVTASK --once &
    task_pid=$!
    sleep 1
    if ! kill -0 "$task_pid" 2>/dev/null; then
        echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=task-listener-start"
        exit 1
    fi
    echo "DNIV-INTEROP-TASK-READY session=$session scenario=$scenario node=$name peer=$peer_node"
    if ! wait "$task_pid"; then
        echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=task-session"
        exit 1
    fi
    echo "DNIV-INTEROP-TASK-PASS session=$session scenario=$scenario node=$name peer=$peer_node"
    fal_root="/tmp/dniv-fal-root.$"
    rm -rf "$fal_root"
    mkdir -p "$fal_root"
    printf 'SERVER-FAL\n' >"$fal_root/SERVER.TXT"
    /usr/local/sbin/dnfald --root "$fal_root" --once &
    fal_pid=$!
    sleep 1
    if ! kill -0 "$fal_pid" 2>/dev/null; then
        echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=fal-listener-start"
        exit 1
    fi
    echo "DNIV-INTEROP-FAL-READY session=$session scenario=$scenario node=$name peer=$peer_node"
    if ! wait "$fal_pid"; then
        echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=fal-config-session"
        exit 1
    fi
    rm -rf "$fal_root"
    echo "DNIV-INTEROP-FAL-PASS session=$session scenario=$scenario node=$name peer=$peer_node operation=get"
    if ! /usr/local/sbin/dnmrr "$peer_node"; then
        echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=nsp-mirror"
        exit 1
    fi
    echo "DNIV-INTEROP-NSP session=$session scenario=$scenario node=$name peer=$peer_node"
    if ! /usr/local/sbin/dnstream "$peer_node"; then
        echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=nsp-stream"
        exit 1
    fi
    echo "DNIV-INTEROP-STREAM session=$session scenario=$scenario node=$name peer=$peer_node"
    if ! /usr/local/sbin/dnsocklife "$peer_node"; then
        echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=nsp-socket-lifecycle"
        exit 1
    fi
    echo "DNIV-INTEROP-SOCKET-LIFECYCLE session=$session scenario=$scenario node=$name peer=$peer_node"
    if ! /usr/local/sbin/dnsockstress "$peer_node"; then
        echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=nsp-socket-stress"
        exit 1
    fi
    echo "DNIV-INTEROP-SOCKET-STRESS session=$session scenario=$scenario node=$name peer=$peer_node"
    if ! /usr/local/sbin/dnsignal "$peer_node"; then
        echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=nsp-signal-eintr"
        exit 1
    fi
    echo "DNIV-INTEROP-SIGNAL-EINTR session=$session scenario=$scenario node=$name peer=$peer_node"
    if ! /usr/local/sbin/dnfair "$peer_node"; then
        echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=nsp-receiver-stall-fairness"
        exit 1
    fi
    echo "DNIV-INTEROP-FAIRNESS session=$session scenario=$scenario node=$name peer=$peer_node"
    if ! /usr/local/sbin/dnloss "$peer_node" "$session" "$scenario"; then
        echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=nsp-loss-retransmit"
        exit 1
    fi
    echo "DNIV-INTEROP-LOSS-PASS session=$session scenario=$scenario node=$name peer=$peer_node"
    if ! /usr/local/sbin/dndrain "$peer_node" "$session" "$scenario"; then
        echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=nsp-clean-drain"
        exit 1
    fi
    sleep 5
    if ! /usr/local/sbin/dnmrr "$peer_node"; then
        echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=nsp-clean-drain-recovery"
        exit 1
    fi
    echo "DNIV-INTEROP-DRAIN-PASS session=$session scenario=$scenario node=$name peer=$peer_node"
    if [ "$flow_proof" = 1 ]; then
        echo "DNIV-INTEROP-FLOW-READY session=$session scenario=$scenario node=$name peer=$peer_node"
        sleep 2
        if ! /usr/local/sbin/dnflow "$peer_node" "$session" "$scenario"; then
            echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=nsp-flow-control"
            exit 1
        fi
        echo "DNIV-INTEROP-FLOW-PASS session=$session scenario=$scenario node=$name peer=$peer_node"
        echo "DNIV-INTEROP-ACKRANGE-READY session=$session scenario=$scenario node=$name peer=$peer_node"
        sleep 2
        if ! /usr/local/sbin/dnackrange "$peer_node" "$session" "$scenario"; then
            echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=nsp-ack-range"
            exit 1
        fi
        echo "DNIV-INTEROP-ACKRANGE-PASS session=$session scenario=$scenario node=$name peer=$peer_node"
        if ! /usr/local/sbin/dnseqwrap "$peer_node"; then
            echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=nsp-sequence-wrap"
            exit 1
        fi
        echo "DNIV-INTEROP-SEQWRAP-PASS session=$session scenario=$scenario node=$name peer=$peer_node"
        echo "DNIV-INTEROP-INTLOSS-READY session=$session scenario=$scenario node=$name peer=$peer_node"
        sleep 2
        if ! /usr/local/sbin/dnintloss "$peer_node" "$session" "$scenario"; then
            echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=nsp-interrupt-loss"
            exit 1
        fi
        echo "DNIV-INTEROP-INTLOSS-PASS session=$session scenario=$scenario node=$name peer=$peer_node"
        echo "DNIV-INTEROP-INTFLOW-READY session=$session scenario=$scenario node=$name peer=$peer_node"
        sleep 2
        if ! /usr/local/sbin/dnintflow "$peer_node" "$session" "$scenario"; then
            echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=nsp-interrupt-flow"
            exit 1
        fi
        echo "DNIV-INTEROP-INTFLOW-PASS session=$session scenario=$scenario node=$name peer=$peer_node"
        if ! /usr/local/sbin/dnccretry "$peer_node" "$session" "$scenario"; then
            echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=nsp-cc-retry"
            exit 1
        fi
        echo "DNIV-INTEROP-CCRETRY-PASS session=$session scenario=$scenario node=$name peer=$peer_node"
        if ! /usr/local/sbin/dndiloss "$peer_node" "$session" "$scenario"; then
            echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=nsp-di-loss"
            exit 1
        fi
        echo "DNIV-INTEROP-DILOSS-PASS session=$session scenario=$scenario node=$name peer=$peer_node"
        if ! /usr/local/sbin/dndiexhaust "$peer_node" "$session" "$scenario"; then
            echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=nsp-di-exhaustion"
            exit 1
        fi
        echo "DNIV-INTEROP-DIEXHAUST-PASS session=$session scenario=$scenario node=$name peer=$peer_node"
        echo 4 > /sys/module/decnet_iv/parameters/nsp_inactivity_seconds
        echo "DNIV-INTEROP-KEEPALIVE-READY session=$session scenario=$scenario node=$name peer=$peer_node"
        sleep 2
        if ! /usr/local/sbin/dnkeepalive "$peer_node" "$session" "$scenario"; then
            echo 300 > /sys/module/decnet_iv/parameters/nsp_inactivity_seconds
            echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=nsp-keepalive"
            exit 1
        fi
        echo 300 > /sys/module/decnet_iv/parameters/nsp_inactivity_seconds
        echo "DNIV-INTEROP-KEEPALIVE-PASS session=$session scenario=$scenario node=$name peer=$peer_node"
        if ! /usr/local/sbin/dnwindow "$peer_node" "$session" "$scenario"; then
            echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=nsp-full-window"
            exit 1
        fi
        echo "DNIV-INTEROP-WINDOW-PASS session=$session scenario=$scenario node=$name peer=$peer_node"
    fi
    if ! /usr/local/sbin/dnexhaust "$peer_node" "$session" "$scenario"; then
        echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=nsp-retransmit-exhaustion"
        exit 1
    fi
    echo "DNIV-INTEROP-EXHAUST-PASS session=$session scenario=$scenario node=$name peer=$peer_node"
    sleep 2
    if ! /usr/local/sbin/dnmrr "$peer_node"; then
        echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=nsp-post-exhaust-recovery"
        exit 1
    fi
    echo "DNIV-INTEROP-EXHAUST-RECOVERED session=$session scenario=$scenario node=$name peer=$peer_node"
    if ! /usr/local/sbin/dnconnectloss "$peer_node" "$session" "$scenario"; then
        echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=nsp-connect-retransmit-exhaustion"
        exit 1
    fi
    echo "DNIV-INTEROP-CI-EXHAUST-PASS session=$session scenario=$scenario node=$name peer=$peer_node"
    if [ "$timer_proof" = 1 ]; then
        if [ "$scenario" != l1 ]; then
            echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=timer-proof-scenario"
            exit 1
        fi
        if ! /usr/local/sbin/dntimeout "$peer_node" "$session" "$scenario"; then
            echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=cr-timeout"
            exit 1
        fi
        echo "DNIV-INTEROP-CR-TIMEOUT-PASS session=$session scenario=$scenario node=$name peer=$peer_node"
    fi
    if [ "$scenario" != router-endnode ]; then
        /usr/local/sbin/dnaccept "$peer_node" "$session" "$scenario" &
        accept_pid=$!
        if ! wait "$accept_pid"; then
            echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=inbound-listener"
            exit 1
        fi
        echo "DNIV-INTEROP-LISTEN-PASS session=$session scenario=$scenario node=$name peer=$peer_node"
        /usr/local/sbin/dnbacklog "$peer_node" "$session" "$scenario" &
        backlog_pid=$!
        if ! wait "$backlog_pid"; then
            echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=inbound-backlog"
            exit 1
        fi
        echo "DNIV-INTEROP-BACKLOG-PASS session=$session scenario=$scenario node=$name peer=$peer_node"
        /usr/local/sbin/dnbacklog "$peer_node" "$session" "$scenario" overflow &
        overflow_pid=$!
        if ! wait "$overflow_pid"; then
            echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=inbound-backlog-overflow"
            exit 1
        fi
        echo "DNIV-INTEROP-OVERFLOW-PASS session=$session scenario=$scenario node=$name peer=$peer_node"
        /usr/local/sbin/dnbacklog "$peer_node" "$session" "$scenario" close-race &
        close_race_pid=$!
        if ! wait "$close_race_pid"; then
            echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=inbound-close-race"
            exit 1
        fi
        echo "DNIV-INTEROP-CLOSE-RACE-PASS session=$session scenario=$scenario node=$name peer=$peer_node"
        /usr/local/sbin/dnreset "$peer_node" "$session" "$scenario" &
        reset_pid=$!
        if ! wait "$reset_pid"; then
            echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=inbound-peer-reset"
            exit 1
        fi
        echo "DNIV-INTEROP-RESET-PASS session=$session scenario=$scenario node=$name peer=$peer_node"
        /usr/local/sbin/dnbacklog "$peer_node" "$session" "$scenario" listener-close &
        listener_close_pid=$!
        if ! wait "$listener_close_pid"; then
            echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=listener-close-pending"
            exit 1
        fi
        echo "DNIV-INTEROP-LISTENER-CLOSE-PASS session=$session scenario=$scenario node=$name peer=$peer_node"
        /usr/local/sbin/dntermrace "$peer_node" "$session" "$scenario" &
        term_race_pid=$!
        if ! wait "$term_race_pid"; then
            echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=simultaneous-termination"
            exit 1
        fi
        echo "DNIV-INTEROP-TERM-RACE-PASS session=$session scenario=$scenario node=$name peer=$peer_node"
    fi
    if [ "$reserved_proof" = 1 ]; then
        reserved_before=$(nonhello_value || true)
        case "$reserved_before" in
            ''|*[!0-9]*)
                echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=reserved-stats"
                exit 1
                ;;
        esac
        echo "DNIV-INTEROP-RESERVED-READY session=$session scenario=$scenario node=$name"
        i=0
        reserved_seen=0
        while [ "$i" -lt 200 ]; do
            reserved_now=$(nonhello_value || true)
            case "$reserved_now" in
                ''|*[!0-9]*)
                    echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=reserved-stats"
                    exit 1
                    ;;
            esac
            if [ "$((reserved_now - reserved_before))" -ge 260 ]; then
                reserved_seen=1
                break
            fi
            i=$((i + 1))
            sleep 0.1
        done
        if [ "$reserved_seen" -ne 1 ]; then
            echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=reserved-injection-timeout"
            exit 1
        fi
        echo "DNIV-INTEROP-RESERVED-PASS session=$session scenario=$scenario node=$name"
    fi
fi

snapshot=$(stats_snapshot 8) || {
    echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario reason=bad-hello-stats"
    exit 1
}
set -- $snapshot
hello_before=$2
address=$((area * 1024 + node))
changed_mac=$(printf '52:54:01:00:%02x:%02x' \
    "$((address & 255))" "$(((address >> 8) & 255))")
ip link set dev "$iface" down
ip link set dev "$iface" address "$changed_mac"
ip link set dev "$iface" up
echo "DNIV-INTEROP-CHANGEADDR session=$session scenario=$scenario node=$name mac=$changed_mac"
if ! wait_post_change_hello "$peer_node" "$peer_kind" "$hello_before" 240; then
    echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=changeaddr-hello"
    exit 1
fi

nonhello_before=$(nonhello_value || true)
case "$nonhello_before" in
    ''|*[!0-9]*) echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario reason=bad-routing-stats"; exit 1 ;;
esac
if ! wait_unicast_delta "$nonhello_before" 160; then
    echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=no-unicast-probes"
    exit 1
fi

echo "DNIV-INTEROP-READY-STOP session=$session scenario=$scenario node=$name peer=$peer_node"

expired=0
i=0
while [ "$i" -lt 720 ]; do
    output=$(/usr/local/sbin/dnctl adjacencies 2>/dev/null || true)
    if ! printf '%s\n' "$output" | grep -Fq "$peer_node via "; then
        expired=1
        echo "DNIV-INTEROP-EXPIRED session=$session scenario=$scenario node=$name peer=$peer_node"
        break
    fi
    i=$((i + 1))
    sleep 0.25
done
[ "$expired" -eq 1 ] || {
    echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=no-expiry"
    exit 1
}

if ! wait_peer_up "$peer_node" "$peer_kind" DNIV-INTEROP-RECOVERY 720; then
    echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=no-recovery"
    exit 1
fi
echo "DNIV-INTEROP-RECOVERED session=$session scenario=$scenario node=$name peer=$peer_node"
poweroff_pass
