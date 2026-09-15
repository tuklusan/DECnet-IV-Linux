#!/bin/sh
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

adjacency_state() {
    peer_address=$1
    expected_state=$2
    output=$(/usr/local/sbin/dnctl adjacencies 2>/dev/null || true)
    printf '%s\n' "$output"
    printf '%s\n' "$output" | grep -F "$peer_address via " | \
        grep -Fq " L1 router $expected_state "
}

wait_adjacency_state() {
    peer_address=$1
    expected_state=$2
    tries=$3
    i=0
    while [ "$i" -lt "$tries" ]; do
        if adjacency_state "$peer_address" "$expected_state"; then
            return 0
        fi
        i=$((i + 1))
        sleep 0.25
    done
    return 1
}

stat_value() {
    label=$1
    /usr/local/sbin/dnctl stats | sed -n "s/^$label = //p"
}

poweroff_pass() {
    marker=$1
    sync
    echo "$marker"
    sleep 2
    poweroff -f
    exit 0
}

area=$(get_arg dniv.area || printf '31')
node=$(get_arg dniv.node || printf '70')
name=$(get_arg dniv.name || printf 'DN70')
peer=$(get_arg dniv.peer || true)
peer_node=$(get_arg dniv.peer_node || true)
role=$(get_arg dniv.role || printf 'A')
mode=$(get_arg dniv.mode || printf 'phase2')
session=$(get_arg dniv.session || printf 'local')

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
    if [ -z "$peer_node" ]; then
        echo "DNIV-E1-FAIL session=$session node=$name reason=missing-peer-node"
        exit 1
    fi
    case "$role" in
        A|B) ;;
        *) echo "DNIV-E1-FAIL session=$session node=$name reason=bad-role"; exit 1 ;;
    esac

    modprobe decnet_iv default_area="$area" default_node="$node" default_name="$name" \
        default_node_type=2 router_priority=64 hello_interval=2
    /usr/local/sbin/dnctl set "$area.$node" "$name"
    /usr/local/sbin/dnctl reset-stats
    ip link set "$iface" up

    if ! wait_adjacency_state "$peer_node" INIT 80; then
        echo "DNIV-E1-FAIL session=$session node=$name reason=no-initial-init"
        exit 1
    fi
    echo "DNIV-E1-INIT session=$session node=$name peer=$peer_node"
    if ! wait_adjacency_state "$peer_node" UP 120; then
        echo "DNIV-E1-FAIL session=$session node=$name reason=initial-adjacency"
        exit 1
    fi

    hello_rx=$(stat_value 'Hello frames received')
    hello_tx=$(stat_value 'Hello frames sent')
    case "$hello_rx:$hello_tx" in
        *[!0-9:]*|:*|*:) echo "DNIV-E1-FAIL session=$session node=$name reason=bad-hello-stats"; exit 1 ;;
    esac
    if [ "$hello_rx" -eq 0 ] || [ "$hello_tx" -eq 0 ]; then
        echo "DNIV-E1-FAIL session=$session node=$name reason=no-hello-traffic"
        exit 1
    fi
    echo "DNIV-E1-INITIAL session=$session node=$name peer=$peer_node"

    if [ "$role" = A ]; then
        sleep 1
        modprobe -r decnet_iv
        echo "DNIV-E1-SILENT session=$session node=$name"
        sleep 9
        modprobe decnet_iv default_area="$area" default_node="$node" default_name="$name" \
            default_node_type=2 router_priority=64 hello_interval=2
        ip link set "$iface" up
        if ! wait_adjacency_state "$peer_node" INIT 80; then
            echo "DNIV-E1-FAIL session=$session node=$name reason=no-restart-init"
            exit 1
        fi
        echo "DNIV-E1-RESTART-INIT session=$session node=$name peer=$peer_node"
        if ! wait_adjacency_state "$peer_node" UP 120; then
            echo "DNIV-E1-FAIL session=$session node=$name reason=recovery-adjacency"
            exit 1
        fi
        echo "DNIV-E1-RECOVERED session=$session node=$name peer=$peer_node"
        sleep 5
        poweroff_pass "DNIV-E1-PASS session=$session node=$name"
    fi

    seen_expired=0
    i=0
    while [ "$i" -lt 160 ]; do
        output=$(/usr/local/sbin/dnctl adjacencies 2>/dev/null || true)
        printf '%s\n' "$output"
        if printf '%s\n' "$output" | grep -Fq "$peer_node via "; then
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

*)
    echo "DNIV-LAB-FAIL session=$session node=$name reason=bad-mode"
    exit 1
    ;;
esac

sync
sleep 1
poweroff -f
exit 1
