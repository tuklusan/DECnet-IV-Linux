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
cleanup() {
    set +e
    [ -z "${a_pid:-}" ] || kill "$a_pid" 2>/dev/null
    [ -z "${b_pid:-}" ] || kill "$b_pid" 2>/dev/null
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

port=$((31000 + ($$ % 2000)))
cat >"$work/a.conf" <<EOF
routing 31.78 --type l1router
node 31.78 MNA78
node 31.79 MNB79
circuit MUL-0 Multinet --mode listen --local-address 127.0.0.1 --local-port $port --cost 3 --t3 2
logging console --events 4.8,4.10
EOF
cat >"$work/b.conf" <<EOF
routing 31.79 --type l1router
node 31.78 MNA78
node 31.79 MNB79
circuit MUL-0 Multinet --mode connect --remote-address 127.0.0.1 --remote-port $port --cost 3 --t3 2
logging console --events 4.8,4.10
EOF

start_a() {
    (
        cd "$work/pydecnet/pydecnet"
        exec "$work/venv/bin/python" -u -m decnet.main "$work/a.conf"
    ) >>"$work/a.log" 2>&1 &
    a_pid=$!
}
start_b() {
    (
        cd "$work/pydecnet/pydecnet"
        exec "$work/venv/bin/python" -u -m decnet.main "$work/b.conf"
    ) >>"$work/b.log" 2>&1 &
    b_pid=$!
}

start_a
sleep 1
start_b

for _ in $(seq 1 120); do
    if grep -Fq "Circuit up" "$work/a.log" && grep -Fq "31.79" "$work/a.log" &&
       grep -Fq "Circuit up" "$work/b.log" && grep -Fq "31.78" "$work/b.log"; then
        break
    fi
    kill -0 "$a_pid" 2>/dev/null || { cat "$work/a.log" >&2; exit 1; }
    kill -0 "$b_pid" 2>/dev/null || { cat "$work/b.log" >&2; exit 1; }
    sleep 0.5
done
grep -Fq "Circuit up" "$work/a.log" || { cat "$work/a.log" >&2; exit 1; }
grep -Fq "Circuit up" "$work/b.log" || { cat "$work/b.log" >&2; exit 1; }

kill "$b_pid"
wait "$b_pid" 2>/dev/null || true
b_pid=
for _ in $(seq 1 80); do
    grep -Fq "Circuit down" "$work/a.log" && break
    sleep 0.5
done

start_b
for _ in $(seq 1 160); do
    ups=$(grep -Fc "Circuit up" "$work/a.log" || true)
    if [ "$ups" -ge 2 ]; then
        echo "multinet-proof: pass"
        exit 0
    fi
    kill -0 "$a_pid" 2>/dev/null || { cat "$work/a.log" >&2; exit 1; }
    kill -0 "$b_pid" 2>/dev/null || { cat "$work/b.log" >&2; exit 1; }
    sleep 0.5
done
cat "$work/a.log" >&2
cat "$work/b.log" >&2
echo "multinet-proof: reconnect adjacency did not recover" >&2
exit 1
