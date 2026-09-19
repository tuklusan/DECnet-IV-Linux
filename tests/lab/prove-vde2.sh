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

for cmd in git make python3 vde_switch; do
    command -v "$cmd" >/dev/null || { echo "vde2-proof: missing $cmd" >&2; exit 2; }
done

work=$(mktemp -d /tmp/dniv-vde2.XXXXXX)
sock="$work/switch.ctl"
switch_pid=
py_pid=
cleanup() {
    set +e
    [ -z "${py_pid:-}" ] || kill "$py_pid" 2>/dev/null
    if [ -r /var/run/route20.pid ]; then
        rpid=$(cat /var/run/route20.pid 2>/dev/null)
        [ -z "$rpid" ] || sudo kill "$rpid" 2>/dev/null
        sudo rm -f /var/run/route20.pid
    fi
    [ -z "${switch_pid:-}" ] || kill "$switch_pid" 2>/dev/null
    rm -rf "$work"
}
trap cleanup EXIT INT TERM

git init -q "$work/pydecnet"
git -C "$work/pydecnet" remote add origin https://github.com/tuklusan/pydecnet.git
git -C "$work/pydecnet" fetch -q --depth=1 origin "$PYDECNET_REF"
git -C "$work/pydecnet" checkout -q --detach FETCH_HEAD
test "$(git -C "$work/pydecnet" rev-parse HEAD)" = "$PYDECNET_REF"

git init -q "$work/route20"
git -C "$work/route20" remote add origin https://github.com/tuklusan/Route20.git
git -C "$work/route20" fetch -q --depth=1 origin "$ROUTE20_REF"
git -C "$work/route20" checkout -q --detach FETCH_HEAD
test "$(git -C "$work/route20" rev-parse HEAD)" = "$ROUTE20_REF"
make -C "$work/route20/Route20" >/dev/null

python3 -m venv "$work/venv"
"$work/venv/bin/python" -m pip install -q --upgrade pip setuptools
"$work/venv/bin/python" -m pip install -q "$work/pydecnet/pydecnet"

vde_switch -daemon -sock "$sock" >"$work/vde-switch.log" 2>&1
for _ in $(seq 1 50); do
    switch_pid=$(pgrep -f "vde_switch.*-sock $sock" | head -n1 || true)
    [ -n "$switch_pid" ] && break
    sleep 0.1
done
[ -n "$switch_pid" ] || { echo "vde2-proof: daemon pid absent" >&2; exit 1; }
for _ in $(seq 1 100); do
    [ -S "$sock" ] && break
    kill -0 "$switch_pid" 2>/dev/null || { cat "$work/vde-switch.log" >&2; exit 1; }
    sleep 0.1
done
[ -S "$sock" ] || { echo "vde2-proof: switch socket absent" >&2; exit 1; }
url="vde://$sock"

PYTHONPATH="$work/pydecnet/pydecnet" "$work/venv/bin/python" - "$url" <<'PY'
import select
import sys
from decnet.ethernet import _VdeApi

url = sys.argv[1]
api = _VdeApi()
a = api.open(url)
b = api.open(url)
try:
    frame = bytes.fromhex(
        "ab0000040000"          # DECnet all routers multicast
        "020000000001"
        "6003"
        "2e00"
    ) + bytes(range(46))
    api.send(a, frame)
    ready, _, _ = select.select([api.datafd(b)], [], [], 3)
    if not ready:
        raise SystemExit("vde2-proof: no frame delivered")
    got = api.recv(b, 2048)
    if got != frame:
        raise SystemExit("vde2-proof: frame mismatch")
finally:
    api.close(a)
    api.close(b)
PY

cat >"$work/route20.ini" <<EOF
[node]
name=VDR77
level=1
address=31.77
priority=64

[ethernet]
interface=$url
cost=3

[nsp]
InactivityTimer=30

[session]
InactivityTimer=60
EOF

cat >"$work/pydecnet.conf" <<EOF
routing 31.78 --type l1router
node 31.77 VDR77
node 31.78 VDP78
circuit ETH-0 Ethernet $url --mode vde --cost 3 --t3 2 --priority 64
logging console --events 4.15,4.16
EOF

sudo rm -f /var/run/route20.pid
sudo "$work/route20/Route20/route20" "$work/route20.ini"
for _ in $(seq 1 100); do
    [ -s /var/run/route20.pid ] && break
    sleep 0.1
done
[ -s /var/run/route20.pid ] || { echo "vde2-proof: Route20 did not start" >&2; exit 1; }

(
    cd "$work/pydecnet/pydecnet"
    exec "$work/venv/bin/python" -u -m decnet.main "$work/pydecnet.conf"
) >"$work/pydecnet.log" 2>&1 &
py_pid=$!

for _ in $(seq 1 120); do
    if grep -Fq "Adjacency up" "$work/pydecnet.log" && grep -Fq "31.77" "$work/pydecnet.log"; then
        echo "vde2-proof: pass"
        exit 0
    fi
    kill -0 "$py_pid" 2>/dev/null || { cat "$work/pydecnet.log" >&2; exit 1; }
    sleep 0.5
done
cat "$work/pydecnet.log" >&2
echo "vde2-proof: Route20/PyDECnet VDE adjacency did not form" >&2
exit 1
