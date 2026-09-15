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

area=$(get_arg dniv.area || printf '31')
node=$(get_arg dniv.node || printf '70')
name=$(get_arg dniv.name || printf 'DN70')
peer=$(get_arg dniv.peer || true)
session=$(get_arg dniv.session || printf 'local')

if [ -z "$peer" ]; then
    echo "DNIV-LAB-FAIL session=$session node=$name reason=missing-peer"
    exit 1
fi

modprobe decnet_iv default_area="$area" default_node="$node" default_name="$name"
/usr/local/sbin/dnctl set "$area.$node" "$name"
/usr/local/sbin/dnctl reset-stats

iface=''
i=0
while [ "$i" -lt 50 ]; do
    for path in /sys/class/net/*; do
        candidate=${path##*/}
        if [ "$candidate" != lo ]; then
            iface=$candidate
            break 2
        fi
    done
    i=$((i + 1))
    sleep 0.1
done
if [ -z "$iface" ]; then
    echo "DNIV-LAB-FAIL session=$session node=$name reason=no-interface"
    exit 1
fi
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
        echo "DNIV-LAB-PASS session=$session node=$name frames=$count"
        sync
        sleep 1
        poweroff -f
        exit 0
    fi
    sleep 0.5
done

echo "DNIV-LAB-FAIL session=$session node=$name reason=no-routing-rx"
sync
sleep 1
poweroff -f
exit 1
