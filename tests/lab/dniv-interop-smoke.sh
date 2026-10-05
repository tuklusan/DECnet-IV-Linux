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

pp11_link_count() {
    /usr/local/sbin/dnctl links 2>/dev/null | awk '/^link / { n++ } END { print n + 0 }'
}

pp11_snapshot_links() {
    /usr/local/sbin/dnctl links 2>/dev/null | awk '/^link / { print $2 }' > "$1"
}

pp11_wait_new_link() {
    baseline=$1
    tries=$2
    i=0
    while [ "$i" -lt "$tries" ]; do
        for link in $(/usr/local/sbin/dnctl links 2>/dev/null | awk '/^link / { print $2 }'); do
            if ! grep -Fxq "$link" "$baseline" 2>/dev/null; then
                printf '%s\n' "$link"
                return 0
            fi
        done
        i=$((i + 1))
        sleep 0.1
    done
    return 1
}

pp11_link_metric() {
    wanted_link=$1
    wanted_key=$2
    /usr/local/sbin/dnctl links 2>/dev/null | awk -v link="$wanted_link" -v key="$wanted_key" '
        $1 == "link" && $2 == link {
            for (i = 1; i <= NF; i++) {
                split($i, part, "=")
                if (part[1] == key) {
                    print part[2] + 0
                    found = 1
                    exit
                }
            }
        }
        END { if (!found) print -1 }
    '
}

pp11_wait_link_metric_exact() {
    link=$1
    key=$2
    target=$3
    tries=$4
    i=0
    while [ "$i" -lt "$tries" ]; do
        value=$(pp11_link_metric "$link" "$key")
        if [ "$value" -gt "$target" ]; then
            return 2
        fi
        if [ "$value" -eq "$target" ]; then
            return 0
        fi
        i=$((i + 1))
        sleep 0.1
    done
    return 1
}

pp11_wait_link_metric_range() {
    link=$1
    key=$2
    minimum=$3
    maximum=$4
    tries=$5
    i=0
    while [ "$i" -lt "$tries" ]; do
        value=$(pp11_link_metric "$link" "$key")
        if [ "$value" -gt "$maximum" ]; then
            return 2
        fi
        if [ "$value" -ge "$minimum" ]; then
            return 0
        fi
        i=$((i + 1))
        sleep 0.1
    done
    return 1
}

pp11_wait_link_count_exact() {
    target=$1
    tries=$2
    i=0
    while [ "$i" -lt "$tries" ]; do
        value=$(pp11_link_count)
        if [ "$value" -gt "$target" ]; then
            return 2
        fi
        if [ "$value" -eq "$target" ]; then
            return 0
        fi
        i=$((i + 1))
        sleep 0.1
    done
    return 1
}

pp11_wait_link_count_le() {
    target=$1
    tries=$2
    i=0
    while [ "$i" -lt "$tries" ]; do
        value=$(pp11_link_count)
        if [ "$value" -le "$target" ]; then
            return 0
        fi
        i=$((i + 1))
        sleep 0.1
    done
    return 1
}

pp11_slab_bytes() {
    awk 'NR > 2 { total += $3 * $4 } END { printf "%.0f\n", total + 0 }' /proc/slabinfo
}

pp11_require_seq_live() {
    seq_pid=$1
    seq_log=$2
    baseline_lines=$3
    round=$4
    phase=$5
    i=0
    while [ "$i" -lt 80 ]; do
        kill -0 "$seq_pid" 2>/dev/null || return 1
        lines=$(wc -l < "$seq_log")
        if [ "$lines" -gt "$baseline_lines" ]; then
            echo "DNIV-INTEROP-PP11-MIRROR-LIVE session=$session scenario=$scenario round=$round phase=$phase lines=$lines"
            return 0
        fi
        i=$((i + 1))
        sleep 0.25
    done
    return 1
}

pp11_wait_round_recovery() {
    slab_baseline=$1
    round=$2
    slab_limit=$((slab_baseline + 67108864))
    i=0
    while [ "$i" -lt 1200 ]; do
        links=$(/usr/local/sbin/dnctl links 2>/dev/null || true)
        count=$(printf '%s\n' "$links" | awk '/^link / { n++ } END { print n + 0 }')
        nonzero=$(printf '%s\n' "$links" | awk '
            /^link / {
                for (i = 1; i <= NF; i++) {
                    if ($i ~ /^(tx-data|tx-other|rx)=/ && $i !~ /=0$/)
                        bad++
                }
            }
            END { print bad + 0 }
        ')
        slab_now=$(pp11_slab_bytes)
        adjacency=$(/usr/local/sbin/dnctl adjacencies 2>/dev/null || true)
        if [ "$count" -le 8 ] && [ "$nonzero" -eq 0 ] &&            [ "$slab_now" -le "$slab_limit" ] &&            printf '%s\n' "$adjacency" | grep -F "$peer_node via " |                grep -Fq " $peer_kind UP "; then
            echo "DNIV-INTEROP-PP11-RECOVERED session=$session scenario=$scenario round=$round links=$count slab=$slab_now baseline=$slab_baseline"
            return 0
        fi
        i=$((i + 1))
        sleep 0.1
    done
    return 1
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
pp11_pressure=$(get_arg dniv.pp11_pressure || printf '0')
churn_cycles=$(get_arg dniv.churn_cycles || printf '16')

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
case "$pp11_pressure" in
    0|1) ;;
    *) echo "DNIV-INTEROP-FAIL session=$session reason=bad-pp11-pressure"; exit 1 ;;
esac
case "$churn_cycles" in
    ''|*[!0-9]*) echo "DNIV-INTEROP-FAIL session=$session reason=bad-churn-cycles"; exit 1 ;;
esac
if [ "$churn_cycles" -lt 1 ] || [ "$churn_cycles" -gt 10000 ]; then
    echo "DNIV-INTEROP-FAIL session=$session reason=bad-churn-cycles"
    exit 1
fi
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
        if /usr/local/bin/dnlogin --probe "$peer_node"; then
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
    dap_local=$(mktemp /tmp/dniv-dap-phase7.XXXXXX)
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
    dap_put=$(mktemp /tmp/dniv-dap-put.XXXXXX)
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
    dap_put_text=$(mktemp /tmp/dniv-dap-put-text.XXXXXX)
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
    dap_copy_local=$(mktemp /tmp/dniv-dap-copy.XXXXXX)
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
    printf 'META-A\nMETA-B\n' >"$dap_copy_local"
    if ! /usr/local/bin/dncopy -r vfc -c prn "$dap_copy_local" "$peer_node::METADATA.TXT"; then
        echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=dncopy-metadata-put"
        rm -f "$dap_copy_local"
        exit 1
    fi
    rm -f "$dap_copy_local"
    dap_block=$(mktemp /tmp/dniv-dap-block.XXXXXX)
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
    if ! cterm_output=$(printf '\003phase7\r' | /usr/local/bin/dnlogin -u CTERMUSER -p CTERMPASS -a CTERMACCT "$peer_node" 2>&1); then
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
    cat > /etc/decnet.conf <<EOF_DECNET_CONF
executor $area.$node name $name line $iface
node $peer_node name PEER
EOF_DECNET_CONF
    if ! /usr/local/sbin/dnetlib-mirror PEER "$peer_node" "$area.$node"; then
        echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=libdnet-dnet-conn-mirror"
        exit 1
    fi
    echo "DNIV-INTEROP-LIBDNET-CONN-PASS session=$session scenario=$scenario node=$name peer=$peer_node object=MIRROR node-db=PEER"
    if ! /usr/local/bin/dnping -q -c 3 -s 128 -w 10 PEER; then
        echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=dnping"
        exit 1
    fi
    echo "DNIV-INTEROP-DNPING-PASS session=$session scenario=$scenario node=$name peer=$peer_node packets=3 size=128"
    /usr/local/sbin/dnetlib-daemon &
    libdaemon_pid=$!
    sleep 1
    if ! kill -0 "$libdaemon_pid" 2>/dev/null; then
        echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=libdnet-daemon-listener-start"
        exit 1
    fi
    echo "DNIV-INTEROP-LIBDNET-DAEMON-READY session=$session scenario=$scenario node=$name peer=$peer_node"
    if ! wait "$libdaemon_pid"; then
        echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=libdnet-daemon-session"
        exit 1
    fi
    echo "DNIV-INTEROP-LIBDNET-DAEMON-PASS session=$session scenario=$scenario node=$name peer=$peer_node object=LIBMIRROR"
    dnetd_conf=$(mktemp /tmp/dniv-dnetd.XXXXXX)
    cat >"$dnetd_conf" <<EOF_DNETD
DNETDTEST 0 N,N root /usr/local/sbin/dnetd-mirror
EOF_DNETD
    /usr/local/sbin/dnetd -d --once -c "$dnetd_conf" &
    dnetd_pid=$!
    sleep 1
    if ! kill -0 "$dnetd_pid" 2>/dev/null; then
        echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=dnetd-listener-start"
        exit 1
    fi
    echo "DNIV-INTEROP-DNETD-READY session=$session scenario=$scenario node=$name peer=$peer_node"
    if ! wait "$dnetd_pid"; then
        echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=dnetd-session"
        exit 1
    fi
    rm -f "$dnetd_conf"
    echo "DNIV-INTEROP-DNETD-PASS session=$session scenario=$scenario node=$name peer=$peer_node object=DNETDTEST"
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
    fal_root=$(mktemp -d /tmp/dniv-fal-root.XXXXXX)
    printf 'SERVER-FAL\n' >"$fal_root/SERVER.TXT"
    /usr/local/sbin/dnfald --root "$fal_root" --sessions 7 \
        --user FALUSER --password FALPASS --account FALACCT &
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
    if [ -e "$fal_root/UPLOAD.BIN" ]; then
        echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=fal-erase-content"
        rm -rf "$fal_root"
        exit 1
    fi
    rm -rf "$fal_root"
    echo "DNIV-INTEROP-FAL-PASS session=$session scenario=$scenario node=$name peer=$peer_node operations=get,put,dir,erase"
    http_root=$(mktemp -d /tmp/dniv-http-root.XXXXXX)
    printf 'DECNET-WEB-PASS\n' >"$http_root/index.html"
    /usr/local/sbin/dnhttpd --once --root "$http_root" &
    http_pid=$!
    sleep 1
    if ! kill -0 "$http_pid" 2>/dev/null; then
        echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=http-listener-start"
        rm -rf "$http_root"
        exit 1
    fi
    echo "DNIV-INTEROP-HTTP-READY session=$session scenario=$scenario node=$name peer=$peer_node"
    if ! wait "$http_pid"; then
        echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=http-session"
        rm -rf "$http_root"
        exit 1
    fi
    rm -rf "$http_root"
    echo "DNIV-INTEROP-HTTP-PASS session=$session scenario=$scenario node=$name peer=$peer_node"
    echo "DNIV-INTEROP-DNLYNX-READY session=$session scenario=$scenario node=$name peer=$peer_node"
    dnlynx_ok=0
    i=0
    while [ "$i" -lt 40 ]; do
        i=$((i + 1))
        if output=$(/usr/local/bin/dnlynx "$peer_node" / 2>/dev/null) &&
           printf '%s\n' "$output" | grep -Fq 'PYDECNET-DNLYNX-PASS'; then
            dnlynx_ok=1
            break
        fi
        sleep 0.5
    done
    if [ "$dnlynx_ok" -ne 1 ]; then
        echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=dnlynx-client"
        exit 1
    fi
    echo "DNIV-INTEROP-DNLYNX-PASS session=$session scenario=$scenario node=$name peer=$peer_node"
    echo "DNIV-INTEROP-DNLYNX-OBJECT-READY session=$session scenario=$scenario node=$name peer=$peer_node"
    dnlynx_object_ok=0
    i=0
    while [ "$i" -lt 40 ]; do
        i=$((i + 1))
        if output=$(/usr/local/bin/dnlynx -o DNIVHT "$peer_node" / 2>/dev/null) &&
           printf '%s\n' "$output" | grep -Fq 'PYDECNET-DNLYNX-OBJECT-PASS'; then
            dnlynx_object_ok=1
            break
        fi
        sleep 0.5
    done
    if [ "$dnlynx_object_ok" -ne 1 ]; then
        echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=dnlynx-object-client"
        exit 1
    fi
    echo "DNIV-INTEROP-DNLYNX-OBJECT-PASS session=$session scenario=$scenario node=$name peer=$peer_node"
    /usr/local/sbin/dnphoned --sessions 2 --user TEST &
    phone_pid=$!
    sleep 1
    if ! kill -0 "$phone_pid" 2>/dev/null; then
        echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=phone-listener-start"
        exit 1
    fi
    echo "DNIV-INTEROP-PHONE-READY session=$session scenario=$scenario node=$name peer=$peer_node"
    if ! wait "$phone_pid"; then
        echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=phone-session"
        exit 1
    fi
    echo "DNIV-INTEROP-PHONE-PASS session=$session scenario=$scenario node=$name peer=$peer_node"
    mail_root=$(mktemp -d /tmp/dniv-mail-root.XXXXXX)
    mail_sendmail="$mail_root/fake-sendmail"
    cat > "$mail_sendmail" <<'EOF_DNIV_SENDMAIL'
#!/bin/sh
root=${0%/*}
printf '%s\n' "$*" > "$root/sendmail.args"
cat > "$root/delivered.eml"
EOF_DNIV_SENDMAIL
    chmod 0755 "$mail_sendmail"
    /usr/local/sbin/dnmaild --once --root "$mail_root" --sendmail "$mail_sendmail" &
    mail_pid=$!
    sleep 1
    if ! kill -0 "$mail_pid" 2>/dev/null; then
        echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=mail-listener-start"
        rm -rf "$mail_root"
        exit 1
    fi
    echo "DNIV-INTEROP-MAIL-READY session=$session scenario=$scenario node=$name peer=$peer_node"
    if ! wait "$mail_pid"; then
        echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=mail-session"
        rm -rf "$mail_root"
        exit 1
    fi
    if ! grep -Fq 'From: PYDECNET' "$mail_root/mailbox.log" ||
       ! grep -Fq 'To: TEST,SECOND' "$mail_root/mailbox.log" ||
       ! grep -Fq 'Subject: MAIL-11-PROOF' "$mail_root/mailbox.log" ||
       ! grep -Fq 'BODY-ONE' "$mail_root/mailbox.log" ||
       ! grep -Fq 'BODY-TWO' "$mail_root/mailbox.log"; then
        echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=mail-spool-content"
        rm -rf "$mail_root"
        exit 1
    fi
    if ! grep -Fxq -- '-i -t' "$mail_root/sendmail.args" ||
       ! grep -Fq 'From: PYDECNET' "$mail_root/delivered.eml" ||
       ! grep -Fq 'To: TEST,SECOND' "$mail_root/delivered.eml" ||
       ! grep -Fq 'Subject: MAIL-11-PROOF' "$mail_root/delivered.eml" ||
       ! grep -Fq 'BODY-ONE' "$mail_root/delivered.eml" ||
       ! grep -Fq 'BODY-TWO' "$mail_root/delivered.eml"; then
        echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=mail-sendmail-delivery"
        rm -rf "$mail_root"
        exit 1
    fi
    echo "DNIV-INTEROP-MAIL-PASS session=$session scenario=$scenario node=$name peer=$peer_node"
    /usr/local/sbin/dnsmtpfake 2525 "$mail_root/smtp.eml" &
    smtp_fake_pid=$!
    /usr/local/sbin/dnmaild --once --root "$mail_root" --smtp 127.0.0.1 \
        --smtp-port 2525 --smtp-from mail11@localhost &
    mail_pid=$!
    sleep 1
    if ! kill -0 "$smtp_fake_pid" 2>/dev/null || ! kill -0 "$mail_pid" 2>/dev/null; then
        echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=mail-smtp-start"
        rm -rf "$mail_root"
        exit 1
    fi
    echo "DNIV-INTEROP-MAIL-SMTP-READY session=$session scenario=$scenario node=$name peer=$peer_node"
    if ! wait "$mail_pid" || ! wait "$smtp_fake_pid"; then
        echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=mail-smtp-session"
        rm -rf "$mail_root"
        exit 1
    fi
    if ! grep -Fq 'From: PYDECNET' "$mail_root/smtp.eml" ||
       ! grep -Fq 'To: TEST,SECOND' "$mail_root/smtp.eml" ||
       ! grep -Fq 'Subject: MAIL-11-PROOF' "$mail_root/smtp.eml" ||
       ! grep -Fq 'BODY-ONE' "$mail_root/smtp.eml" ||
       ! grep -Fq 'BODY-TWO' "$mail_root/smtp.eml"; then
        echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=mail-smtp-content"
        rm -rf "$mail_root"
        exit 1
    fi
    rm -rf "$mail_root"
    echo "DNIV-INTEROP-MAIL-SMTP-PASS session=$session scenario=$scenario node=$name peer=$peer_node"
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
    if ! /usr/local/sbin/dnsocklife "$peer_node" "$churn_cycles"; then
        echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=nsp-socket-lifecycle"
        exit 1
    fi
    echo "DNIV-INTEROP-SOCKET-LIFECYCLE session=$session scenario=$scenario node=$name peer=$peer_node cycles=$churn_cycles"
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
    if [ "$pp11_pressure" = 1 ]; then
        if [ "$scenario" != l1 ]; then
            echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=pp11-pressure-scenario"
            exit 1
        fi
        slab_baseline=$(pp11_slab_bytes)
        round=1
        while [ "$round" -le 3 ]; do
            seq_log="/run/dniv-pp11-seqwrap-$round.log"
            rm -f "$seq_log"
            /usr/local/sbin/dnseqwrap "$peer_node" pressure "$round" >"$seq_log" 2>&1 &
            seq_pid=$!
            i=0
            while [ "$i" -lt 100 ]; do
                grep -Fq "DNIV-PP11-SEQWRAP-START round=$round " "$seq_log" 2>/dev/null && break
                kill -0 "$seq_pid" 2>/dev/null || {
                    cat "$seq_log" || true
                    echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=pp11-seqwrap-start"
                    exit 1
                }
                i=$((i + 1))
                sleep 0.1
            done
            if ! grep -Fq "DNIV-PP11-SEQWRAP-START round=$round " "$seq_log"; then
                echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=pp11-seqwrap-start-timeout"
                exit 1
            fi
            echo "DNIV-INTEROP-PP11-ROUND-START session=$session scenario=$scenario round=$round"

            seq_lines=$(wc -l < "$seq_log")
            echo "DNIV-INTEROP-PP11-TABLE-READY session=$session scenario=$scenario round=$round"
            if ! pp11_wait_link_count_exact 256 500; then
                echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=pp11-table-limit round=$round"
                exit 1
            fi
            echo "DNIV-INTEROP-PP11-TABLE-LIMIT session=$session scenario=$scenario round=$round count=256"
            if ! pp11_require_seq_live "$seq_pid" "$seq_log" "$seq_lines" "$round" table; then
                echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=pp11-table-mirror round=$round"
                exit 1
            fi
            if ! pp11_wait_link_count_le 8 800; then
                echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=pp11-table-recovery round=$round"
                exit 1
            fi

            seq_lines=$(wc -l < "$seq_log")
            rx_before="/run/dniv-pp11-rx-before-$round"
            pp11_snapshot_links "$rx_before"
            echo "DNIV-INTEROP-PP11-RX-READY session=$session scenario=$scenario round=$round"
            sleep 2
            /usr/local/sbin/dnackrange "$peer_node" "$session" "$scenario" pressure "$round" &
            rx_pid=$!
            rx_link=$(pp11_wait_new_link "$rx_before" 100) || {
                echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=pp11-rx-link round=$round"
                exit 1
            }
            # rx= is the aggregate of the independently bounded data and
            # other-data receive subchannels.  The injected 32 future Link
            # Service records fill the other-data channel; concurrently ready
            # normal data may legitimately make the aggregate exceed 32.
            if ! pp11_wait_link_metric_range "$rx_link" rx 32 64 160; then
                echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=pp11-rx-limit round=$round link=$rx_link"
                exit 1
            fi
            rx_total=$(pp11_link_metric "$rx_link" rx)
            echo "DNIV-INTEROP-PP11-RX-LIMIT session=$session scenario=$scenario round=$round link=$rx_link channel-limit=32 total=$rx_total"
            if ! pp11_require_seq_live "$seq_pid" "$seq_log" "$seq_lines" "$round" rx; then
                echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=pp11-rx-mirror round=$round"
                exit 1
            fi
            if ! wait "$rx_pid"; then
                echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=pp11-rx-client round=$round"
                exit 1
            fi

            seq_lines=$(wc -l < "$seq_log")
            /usr/local/sbin/dnbacklog "$peer_node" "$session" "$scenario" pressure "$round" &
            backlog_pid=$!
            if ! wait "$backlog_pid"; then
                echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=pp11-backlog round=$round"
                exit 1
            fi
            echo "DNIV-INTEROP-PP11-BACKLOG-PASS session=$session scenario=$scenario round=$round accepted=64 busy=1"
            if ! pp11_require_seq_live "$seq_pid" "$seq_log" "$seq_lines" "$round" backlog; then
                echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=pp11-backlog-mirror round=$round"
                exit 1
            fi

            seq_lines=$(wc -l < "$seq_log")
            window_before="/run/dniv-pp11-window-before-$round"
            pp11_snapshot_links "$window_before"
            /usr/local/sbin/dnwindow "$peer_node" "$session" "$scenario" pressure "$round" &
            window_pid=$!
            window_link=$(pp11_wait_new_link "$window_before" 100) || {
                echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=pp11-window-link round=$round"
                exit 1
            }
            echo "DNIV-INTEROP-PP11-WINDOW-LINK session=$session scenario=$scenario round=$round link=$window_link"
            if ! pp11_wait_link_metric_exact "$window_link" tx-data 20 200; then
                echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=pp11-window-limit round=$round link=$window_link"
                exit 1
            fi
            echo "DNIV-INTEROP-PP11-WINDOW-LIMIT session=$session scenario=$scenario round=$round link=$window_link count=20"
            if ! pp11_require_seq_live "$seq_pid" "$seq_log" "$seq_lines" "$round" window; then
                echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=pp11-window-mirror round=$round"
                exit 1
            fi
            if ! wait "$window_pid"; then
                echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=pp11-window-client round=$round"
                exit 1
            fi

            seq_lines=$(wc -l < "$seq_log")
            int_before="/run/dniv-pp11-int-before-$round"
            pp11_snapshot_links "$int_before"
            echo "DNIV-INTEROP-PP11-INT-READY session=$session scenario=$scenario round=$round"
            sleep 2
            /usr/local/sbin/dnintflow "$peer_node" "$session" "$scenario" pressure "$round" &
            int_pid=$!
            int_link=$(pp11_wait_new_link "$int_before" 100) || {
                echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=pp11-int-link round=$round"
                exit 1
            }
            echo "DNIV-INTEROP-PP11-INT-LINK session=$session scenario=$scenario round=$round link=$int_link"
            if ! pp11_wait_link_metric_exact "$int_link" tx-other 64 200; then
                echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=pp11-retransmit-limit round=$round link=$int_link"
                exit 1
            fi
            echo "DNIV-INTEROP-PP11-RETRANSMIT-LIMIT session=$session scenario=$scenario round=$round link=$int_link count=64"
            if ! pp11_require_seq_live "$seq_pid" "$seq_log" "$seq_lines" "$round" retransmit; then
                echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=pp11-retransmit-mirror round=$round"
                exit 1
            fi
            if ! wait "$int_pid"; then
                echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=pp11-retransmit-client round=$round"
                exit 1
            fi

            if ! wait "$seq_pid"; then
                cat "$seq_log" || true
                echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=pp11-seqwrap round=$round"
                exit 1
            fi
            cat "$seq_log"
            if ! pp11_wait_round_recovery "$slab_baseline" "$round"; then
                echo "DNIV-INTEROP-FAIL session=$session scenario=$scenario node=$name reason=pp11-round-recovery round=$round"
                exit 1
            fi
            echo "DNIV-INTEROP-PP11-ROUND-PASS session=$session scenario=$scenario round=$round malformed_control=96 table=256 rx=32 backlog=64 window=20 retransmit=64"
            round=$((round + 1))
        done
        echo "DNIV-INTEROP-PP11-PRESSURE-PASS session=$session scenario=$scenario rounds=3"
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
