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
    while [ "$i" -lt 50 ]; do
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

wait_adjacency_up() {
    peer_address=$1
    init_marker=$2
    tries=$3
    init_seen=0
    i=0
    while [ "$i" -lt "$tries" ]; do
        output=$(/usr/local/sbin/dnctl adjacencies 2>/dev/null || true)
        printf '%s\n' "$output"
        if [ "$init_seen" -eq 0 ] && \
           printf '%s\n' "$output" | grep -F "$peer_address via " | \
               grep -Fq ' L1 router INIT '; then
            init_seen=1
            echo "$init_marker session=$session node=$name peer=$peer_address"
        fi
        if printf '%s\n' "$output" | grep -F "$peer_address via " | \
           grep -Fq ' L1 router UP '; then
            return 0
        fi
        i=$((i + 1))
        sleep 0.25
    done
    return 1
}

wait_any_adjacency_up() {
    peer_address=$1
    tries=$2
    i=0
    while [ "$i" -lt "$tries" ]; do
        output=$(/usr/local/sbin/dnctl adjacencies 2>/dev/null || true)
        printf '%s\n' "$output"
        if printf '%s\n' "$output" | grep -F "$peer_address via " | grep -Fq ' UP '; then
            return 0
        fi
        i=$((i + 1))
        sleep 0.25
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
        hello_rx=$(printf '%s\n' "$stats" | sed -n 's/^Hello frames received[[:space:]]*=[[:space:]]*//p')
        hello_tx=$(printf '%s\n' "$stats" | sed -n 's/^Hello frames sent[[:space:]]*=[[:space:]]*//p')
        valid=1
        for value in "$routing" "$hello_rx" "$hello_tx"; do
            case "$value" in
                ''|*[!0-9]*) valid=0 ;;
            esac
        done
        if [ "$valid" -eq 1 ] && [ "$routing" -ge "$hello_rx" ]; then
            printf '%s %s %s\n' "$routing" "$hello_rx" "$hello_tx"
            return 0
        fi
        i=$((i + 1))
        sleep 0.02
    done
    return 1
}

wait_post_change_hello() {
    peer_address=$1
    hello_baseline=$2
    tries=$3
    i=0
    while [ "$i" -lt "$tries" ]; do
        output=$(/usr/local/sbin/dnctl adjacencies 2>/dev/null || true)
        snapshot=$(stats_snapshot 8) || return 1
        set -- $snapshot
        hello_now=$2
        if [ "$hello_now" -gt "$hello_baseline" ] && \
           printf '%s\n' "$output" | grep -F "$peer_address via " | \
               grep -Fq ' L1 router UP '; then
            echo "DNIV-E1-CHANGEADDR-RX session=$session node=$name peer=$peer_address hellos=$hello_now"
            return 0
        fi
        i=$((i + 1))
        sleep 0.25
    done
    return 1
}

poweroff_pass() {
    marker=$1
    sync
    echo "$marker"
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
peer=$(get_arg dniv.peer || true)
peer_node=$(get_arg dniv.peer_node || true)
role=$(get_arg dniv.role || printf 'A')
mode=$(get_arg dniv.mode || printf 'phase2')
session=$(get_arg dniv.session || printf 'local')
dest_node=$(get_arg dniv.dest_node || true)
alt_peer=$(get_arg dniv.alt_peer || true)
alt_peer_node=$(get_arg dniv.alt_peer_node || true)

iface=$(find_iface || true)
if [ -z "$iface" ]; then
    echo "DNIV-LAB-FAIL session=$session node=$name reason=no-interface"
    exit 1
fi

case "$mode" in
phase2)
    if [ -z "$peer" ]; then
        echo "DNIV-LAB-FAIL session=$session node=$name reason=missing-peer"
        exit 1
    fi

    # Keep the retained Phase 2 EtherType gate independent of Phase 3 router
    # hellos: two endnodes do not subscribe to the all-routers multicast group.
    modprobe decnet_iv default_area="$area" default_node="$node" default_name="$name" \
        default_node_type=3
    /usr/local/sbin/dnctl set "$area.$node" "$name"
    /usr/local/sbin/dnctl reset-stats
    ip link set "$iface" up

    i=0
    while [ "$i" -lt 180 ]; do
        i=$((i + 1))
        /usr/local/sbin/dnraw "$iface" "$peer" "DNIV-$session-$name-$i" || true
        stats=$(/usr/local/sbin/dnctl stats)
        printf '%s\n' "$stats"
        count=$(printf '%s\n' "$stats" | sed -n 's/^Routing frames received = //p')
        case "$count" in
            ''|*[!0-9]*) count=0 ;;
        esac
        if [ "$count" -gt 0 ]; then
            /usr/local/sbin/dnraw "$iface" "$peer" "DNIV-$session-$name-final-1" || true
            sleep 1
            /usr/local/sbin/dnraw "$iface" "$peer" "DNIV-$session-$name-final-2" || true
            poweroff_pass "DNIV-LAB-PASS session=$session node=$name frames=$count"
        fi
        sleep 0.5
    done

    echo "DNIV-LAB-FAIL session=$session node=$name reason=no-routing-rx"
    ;;

e1)
    if [ -z "$peer" ] || [ -z "$peer_node" ]; then
        echo "DNIV-E1-FAIL session=$session node=$name reason=missing-peer"
        exit 1
    fi
    case "$role" in
        A|B) ;;
        *) echo "DNIV-E1-FAIL session=$session node=$name reason=bad-role"; exit 1 ;;
    esac

    if [ "$role" = A ]; then
        modprobe decnet_iv default_area="$area" default_node="$node" default_name="$name" \
            default_node_type=3 hello_interval=2
        /usr/local/sbin/dnctl set "$area.$node" "$name"
        /usr/local/sbin/dnctl reset-stats
        ip link set "$iface" up
        if ! wait_adjacency_up "$peer_node" DNIV-E1-BOOTSTRAP 120; then
            echo "DNIV-E1-FAIL session=$session node=$name reason=bootstrap-peer"
            exit 1
        fi
        modprobe -r decnet_iv
    fi

    modprobe decnet_iv default_area="$area" default_node="$node" default_name="$name" \
        default_node_type=2 router_priority=64 hello_interval=2
    /usr/local/sbin/dnctl set "$area.$node" "$name"
    /usr/local/sbin/dnctl reset-stats
    ip link set "$iface" up

    if ! wait_adjacency_up "$peer_node" DNIV-E1-INIT 120; then
        echo "DNIV-E1-FAIL session=$session node=$name reason=initial-adjacency"
        exit 1
    fi

    snapshot=$(stats_snapshot 8) || {
        echo "DNIV-E1-FAIL session=$session node=$name reason=bad-changeaddr-stats"
        exit 1
    }
    set -- $snapshot
    change_hello_before=$2
    address=$((area * 1024 + node))
    changed_mac=$(printf '52:54:01:00:%02x:%02x' \
        "$((address & 255))" "$(((address >> 8) & 255))")
    ip link set dev "$iface" down
    ip link set dev "$iface" address "$changed_mac"
    ip link set dev "$iface" up
    echo "DNIV-E1-CHANGEADDR session=$session node=$name mac=$changed_mac"
    if ! wait_post_change_hello "$peer_node" "$change_hello_before" 80; then
        echo "DNIV-E1-FAIL session=$session node=$name reason=changeaddr-hello"
        exit 1
    fi

    snapshot=$(stats_snapshot 8) || {
        echo "DNIV-E1-FAIL session=$session node=$name reason=bad-stats"
        exit 1
    }
    set -- $snapshot
    routing_before=$1
    hello_before=$2

    i=0
    while [ "$i" -lt 40 ]; do
        i=$((i + 1))
        /usr/local/sbin/dnraw "$iface" "$peer" "DNIV-E1-UCAST-$session-$name-$i"
        sleep 0.25
    done
    sleep 1

    snapshot=$(stats_snapshot 8) || {
        echo "DNIV-E1-FAIL session=$session node=$name reason=bad-stats"
        exit 1
    }
    set -- $snapshot
    routing_after=$1
    hello_after=$2
    hello_tx=$3
    nonhello_before=$((routing_before - hello_before))
    nonhello_after=$((routing_after - hello_after))
    unicast_delta=$((nonhello_after - nonhello_before))
    if [ "$hello_after" -eq 0 ] || [ "$hello_tx" -eq 0 ]; then
        echo "DNIV-E1-FAIL session=$session node=$name reason=no-hello-traffic"
        exit 1
    fi
    if [ "$unicast_delta" -lt 3 ]; then
        echo "DNIV-E1-FAIL session=$session node=$name reason=no-decnet-unicast-rx delta=$unicast_delta"
        exit 1
    fi
    echo "DNIV-E1-UCAST session=$session node=$name peer=$peer_node delta=$unicast_delta"
    echo "DNIV-E1-INITIAL session=$session node=$name peer=$peer_node"

    # DN71 has the higher node address at equal priority, so it is the DR.
    # Silence that router long enough for DN70 to expire it, but for less than
    # listener expiry plus DRDELAY. A correct DN70 must therefore never emit an
    # All-Endnodes hello before DN71 returns.
    if [ "$role" = B ]; then
        sleep 1
        modprobe -r decnet_iv
        echo "DNIV-E1-SILENT session=$session node=$name"
        sleep 7
        modprobe decnet_iv default_area="$area" default_node="$node" default_name="$name" \
            default_node_type=2 router_priority=64 hello_interval=2
        /usr/local/sbin/dnctl set "$area.$node" "$name"
        /usr/local/sbin/dnctl reset-stats
        ip link set "$iface" up
        if ! wait_adjacency_up "$peer_node" DNIV-E1-RESTART-INIT 120; then
            echo "DNIV-E1-FAIL session=$session node=$name reason=recovery-adjacency"
            exit 1
        fi
        echo "DNIV-E1-RECOVERED session=$session node=$name peer=$peer_node"
        sleep 5
        poweroff_pass "DNIV-E1-PASS session=$session node=$name"
    fi

    seen_expired=0
    restart_init_reported=0
    i=0
    while [ "$i" -lt 240 ]; do
        output=$(/usr/local/sbin/dnctl adjacencies 2>/dev/null || true)
        printf '%s\n' "$output"
        if printf '%s\n' "$output" | grep -Fq "$peer_node via "; then
            if [ "$seen_expired" -eq 1 ] && [ "$restart_init_reported" -eq 0 ] && \
               printf '%s\n' "$output" | grep -F "$peer_node via " | \
                   grep -Fq ' L1 router INIT '; then
                restart_init_reported=1
                echo "DNIV-E1-RESTART-INIT session=$session node=$name peer=$peer_node"
            fi
            if [ "$seen_expired" -eq 1 ] && \
               printf '%s\n' "$output" | grep -F "$peer_node via " | \
                   grep -Fq ' L1 router UP '; then
                echo "DNIV-E1-RECOVERED session=$session node=$name peer=$peer_node"
                poweroff_pass "DNIV-E1-PASS session=$session node=$name"
            fi
        elif [ "$seen_expired" -eq 0 ]; then
            seen_expired=1
            echo "DNIV-E1-EXPIRED session=$session node=$name peer=$peer_node"
        fi
        i=$((i + 1))
        sleep 0.25
    done
    echo "DNIV-E1-FAIL session=$session node=$name reason=no-expire-recover"
    ;;

e2)
    case "$role" in
        A|B)
            if [ -z "$peer" ] || [ -z "$peer_node" ] || [ -z "$dest_node" ]; then
                echo "DNIV-E2-FAIL session=$session node=$name reason=missing-args"
                exit 1
            fi
            modprobe decnet_iv default_area="$area" default_node="$node" default_name="$name" \
                default_node_type=3 hello_interval=2
            /usr/local/sbin/dnctl set "$area.$node" "$name"
            ip link set "$iface" up
            if ! wait_any_adjacency_up "$peer_node" 160; then
                echo "DNIV-E2-FAIL session=$session node=$name reason=no-router"
                exit 1
            fi
            sleep 3
            i=0
            while [ "$i" -lt 5 ]; do
                i=$((i + 1))
                /usr/local/sbin/dnraw --short "$iface" "$peer" "$area.$node" "$dest_node" 0 \
                    "DNIV-E2-$session-$name-$i"
                sleep 0.2
            done
            /usr/local/sbin/dnraw --short "$iface" "$peer" "$area.$node" "$dest_node" 31 \
                "DNIV-E2-MAXVISIT-$session-$name"
            sleep 5
            poweroff_pass "DNIV-E2-PASS session=$session node=$name"
            ;;
        R)
            modprobe decnet_iv default_area="$area" default_node="$node" default_name="$name" \
                default_node_type=2 router_priority=64 hello_interval=2 ethernet_cost=4
            /usr/local/sbin/dnctl set "$area.$node" "$name"
            for path in /sys/class/net/*; do
                candidate=${path##*/}
                [ "$candidate" = lo ] || ip link set "$candidate" up
            done
            sleep 20
            poweroff_pass "DNIV-E2-PASS session=$session node=$name"
            ;;
        *)
            echo "DNIV-E2-FAIL session=$session node=$name reason=bad-role"
            exit 1
            ;;
    esac
    ;;


e3)
    case "$role" in
        A|B)
            if [ -z "$peer" ] || [ -z "$peer_node" ] ||
               [ -z "$alt_peer" ] || [ -z "$alt_peer_node" ] ||
               [ -z "$dest_node" ]; then
                echo "DNIV-E3-FAIL session=$session node=$name reason=missing-args"
                exit 1
            fi
            modprobe decnet_iv default_area="$area" default_node="$node" default_name="$name" \
                default_node_type=3 hello_interval=2
            /usr/local/sbin/dnctl set "$area.$node" "$name"
            ip link set "$iface" up
            if ! wait_any_adjacency_up "$peer_node" 320; then
                echo "DNIV-E3-FAIL session=$session node=$name reason=no-primary"
                exit 1
            fi
            echo "DNIV-E3-PRIMARY session=$session node=$name router=$peer_node"
            i=0
            while [ "$i" -lt 5 ]; do
                i=$((i + 1))
                /usr/local/sbin/dnraw --short "$iface" "$peer" "$area.$node" "$dest_node" 0 \
                    "DNIV-E3-PRE-$session-$name-$i"
                sleep 0.2
            done

            switched=0
            i=0
            while [ "$i" -lt 480 ]; do
                output=$(/usr/local/sbin/dnctl adjacencies 2>/dev/null || true)
                printf '%s\n' "$output"
                if ! printf '%s\n' "$output" | grep -Fq "$peer_node via " &&
                   printf '%s\n' "$output" | grep -F "$alt_peer_node via " | grep -Fq ' UP '; then
                    switched=1
                    break
                fi
                i=$((i + 1))
                sleep 0.25
            done
            if [ "$switched" -ne 1 ]; then
                echo "DNIV-E3-FAIL session=$session node=$name reason=no-alternate"
                exit 1
            fi
            echo "DNIV-E3-ALTERNATE session=$session node=$name router=$alt_peer_node"
            i=0
            while [ "$i" -lt 5 ]; do
                i=$((i + 1))
                /usr/local/sbin/dnraw --short "$iface" "$alt_peer" "$area.$node" "$dest_node" 0 \
                    "DNIV-E3-POST-$session-$name-$i"
                sleep 0.2
            done
            sleep 3
            poweroff_pass "DNIV-E3-PASS session=$session node=$name"
            ;;
        R1)
            modprobe decnet_iv default_area="$area" default_node="$node" default_name="$name" \
                default_node_type=2 router_priority=64 hello_interval=2 ethernet_cost=4
            /usr/local/sbin/dnctl set "$area.$node" "$name"
            for path in /sys/class/net/*; do
                candidate=${path##*/}
                [ "$candidate" = lo ] || ip link set "$candidate" up
            done
            sleep 65
            poweroff_pass "DNIV-E3-PASS session=$session node=$name"
            ;;
        R2)
            modprobe decnet_iv default_area="$area" default_node="$node" default_name="$name" \
                default_node_type=2 router_priority=96 hello_interval=2 ethernet_cost=4
            /usr/local/sbin/dnctl set "$area.$node" "$name"
            for path in /sys/class/net/*; do
                candidate=${path##*/}
                [ "$candidate" = lo ] || ip link set "$candidate" up
            done
            sleep 25
            echo "DNIV-E3-PRIMARY-DOWN session=$session node=$name"
            poweroff_pass "DNIV-E3-PASS session=$session node=$name"
            ;;
        *)
            echo "DNIV-E3-FAIL session=$session node=$name reason=bad-role"
            exit 1
            ;;
    esac
    ;;

*)
    echo "DNIV-LAB-FAIL session=$session node=$name reason=bad-mode"
    exit 1
    ;;
esac

sync
sleep 1
