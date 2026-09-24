#!/usr/bin/env bash
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

set -euo pipefail

root=$(cd "$(dirname "$0")/../.." && pwd)
. "$root/tests/reference/refs.env"

for cmd in git python3; do
    command -v "$cmd" >/dev/null || { echo "multinet-proof: missing $cmd" >&2; exit 2; }
done

work=$(mktemp -d /tmp/dniv-multinet.XXXXXX)
a_pid=
b_pid=
c_pid=
bad_pid=

stop_pid() {
    local pid=${1:-}
    [ -z "$pid" ] || kill "$pid" 2>/dev/null || true
    [ -z "$pid" ] || wait "$pid" 2>/dev/null || true
}

cleanup() {
    set +e
    stop_pid "${bad_pid:-}"
    stop_pid "${c_pid:-}"
    stop_pid "${b_pid:-}"
    stop_pid "${a_pid:-}"
    rm -rf "$work"
}
trap cleanup EXIT INT TERM

git init -q "$work/pydecnet"
git -C "$work/pydecnet" remote add origin https://github.com/tuklusan/pydecnet.git
git -C "$work/pydecnet" fetch -q --depth=1 origin "$PYDECNET_REF"
git -C "$work/pydecnet" checkout -q --detach FETCH_HEAD
test "$(git -C "$work/pydecnet" rev-parse HEAD)" = "$PYDECNET_REF"

python3 -m venv "$work/venv"
"$work/venv/bin/python" -m pip install -q --upgrade pip setuptools
"$work/venv/bin/python" -m pip install -q "$work/pydecnet/pydecnet"

(
    cd "$work/pydecnet/pydecnet"
    PYTHONPATH=. "$work/venv/bin/python" -m unittest -v tests.test_multinet
)

base_port=$((31000 + (($$ % 1500) * 3)))
port_b=$base_port
port_c=$((base_port + 1))
port_bad=$((base_port + 2))

cat >"$work/a.conf" <<EOF
routing 31.78 --type l2router
node 31.78 MNA78
node 31.79 MNB79
node 31.80 MNC80
circuit MUL-1 Multinet --mode listen --local-address 127.0.0.1 --local-port $port_b --cost 3 --t3 2
circuit MUL-2 Multinet --mode listen --local-address 127.0.0.1 --local-port $port_c --cost 3 --t3 2
logging console --events 4.8,4.10
EOF
cat >"$work/b.conf" <<EOF
routing 31.79 --type l1router
node 31.78 MNA78
node 31.79 MNB79
node 31.80 MNC80
circuit MUL-0 Multinet --mode connect --remote-address 127.0.0.1 --remote-port $port_b --cost 3 --t3 2
logging console --events 4.8,4.10
EOF
cat >"$work/c.conf" <<EOF
routing 31.80 --type l1router
node 31.78 MNA78
node 31.79 MNB79
node 31.80 MNC80
circuit MUL-0 Multinet --mode connect --remote-address 127.0.0.1 --remote-port $port_c --cost 3 --t3 2
logging console --events 4.8,4.10
EOF
cat >"$work/bad.conf" <<EOF
routing 31.81 --type l1router
node 31.81 MND81
circuit MUL-0 Multinet --mode connect --remote-address 127.0.0.1 --remote-port $port_bad --cost 3 --t3 2
logging console --events 4.8,4.10
EOF

start_node() {
    local config=$1 log=$2
    (
        cd "$work/pydecnet/pydecnet"
        exec "$work/venv/bin/python" -u -m decnet.main "$config"
    ) >>"$log" 2>&1 &
    printf '%s\n' "$!"
}

wait_count() {
    local file=$1 pattern=$2 minimum=$3
    shift 3
    local count pid
    for _ in $(seq 1 200); do
        count=$(grep -Fc "$pattern" "$file" 2>/dev/null || true)
        if [ "$count" -ge "$minimum" ]; then
            return 0
        fi
        for pid in "$@"; do
            [ -z "$pid" ] || kill -0 "$pid" 2>/dev/null || {
                cat "$file" >&2 || true
                return 1
            }
        done
        sleep 0.25
    done
    cat "$file" >&2 || true
    return 1
}

: >"$work/bad.log"
bad_pid=$(start_node "$work/bad.conf" "$work/bad.log")
sleep 3
if grep -Fq "Circuit up" "$work/bad.log"; then
    cat "$work/bad.log" >&2
    echo "multinet-proof: unopened remote port false-positive" >&2
    exit 1
fi
stop_pid "$bad_pid"
bad_pid=

: >"$work/a.log"
: >"$work/b.log"
: >"$work/c.log"
a_pid=$(start_node "$work/a.conf" "$work/a.log")
sleep 1
b_pid=$(start_node "$work/b.conf" "$work/b.log")
c_pid=$(start_node "$work/c.conf" "$work/c.log")

wait_count "$work/a.log" "Circuit up" 2 "$a_pid" "$b_pid" "$c_pid"
wait_count "$work/b.log" "Circuit up" 1 "$a_pid" "$b_pid" "$c_pid"
wait_count "$work/c.log" "Circuit up" 1 "$a_pid" "$b_pid" "$c_pid"

for cycle in $(seq 1 5); do
    up_before=$(grep -Fc "Circuit up" "$work/a.log" || true)
    stop_pid "$b_pid"
    b_pid=
    sleep 0.5
    b_pid=$(start_node "$work/b.conf" "$work/b.log")
    wait_count "$work/a.log" "Circuit up" $((up_before + 1)) "$a_pid" "$b_pid" "$c_pid"
    kill -0 "$c_pid"
done

b_up_before=$(grep -Fc "Circuit up" "$work/b.log" || true)
c_up_before=$(grep -Fc "Circuit up" "$work/c.log" || true)
stop_pid "$a_pid"
a_pid=
sleep 1
a_pid=$(start_node "$work/a.conf" "$work/a.log")
wait_count "$work/b.log" "Circuit up" $((b_up_before + 1)) "$a_pid" "$b_pid" "$c_pid"
wait_count "$work/c.log" "Circuit up" $((c_up_before + 1)) "$a_pid" "$b_pid" "$c_pid"

echo "multinet-proof: pass peers=3 connector_restarts=5 listener_restart=1 negative_unopened_port=1"
