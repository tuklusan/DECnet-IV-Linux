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
stop_switch() {
    if [ -n "${switch_pid:-}" ]; then
        kill "$switch_pid" 2>/dev/null || true
        for _ in $(seq 1 50); do
            kill -0 "$switch_pid" 2>/dev/null || break
            sleep 0.1
        done
        switch_pid=
    fi
    rm -rf "$sock"
}

cleanup() {
    set +e
    [ -z "${py_pid:-}" ] || kill "$py_pid" 2>/dev/null
    if [ -r /var/run/route20.pid ]; then
        rpid=$(cat /var/run/route20.pid 2>/dev/null)
        [ -z "$rpid" ] || sudo kill "$rpid" 2>/dev/null
        sudo rm -f /var/run/route20.pid
    fi
    stop_switch
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

start_switch() {
    rm -rf "$sock"
    : >"$work/vde-switch.log"
    vde_switch -daemon -sock "$sock" >>"$work/vde-switch.log" 2>&1
    switch_pid=
    for _ in $(seq 1 50); do
        switch_pid=$(pgrep -f "vde_switch.*-sock $sock" | head -n1 || true)
        [ -n "$switch_pid" ] && break
        sleep 0.1
    done
    [ -n "$switch_pid" ] || { echo "vde2-proof: daemon pid absent" >&2; exit 1; }
    for _ in $(seq 1 100); do
        [ -e "$sock" ] && break
        kill -0 "$switch_pid" 2>/dev/null || { cat "$work/vde-switch.log" >&2; exit 1; }
        sleep 0.1
    done
    [ -e "$sock" ] || { echo "vde2-proof: switch endpoint absent" >&2; exit 1; }
    [ -S "$sock/ctl" ] || { echo "vde2-proof: switch control socket absent" >&2; find "$sock" -maxdepth 2 -ls >&2 || true; exit 1; }
}

start_switch
url="vde://$sock"
badurl="vde://$work/no-such-switch"

cat >"$work/vde-native.c" <<'EOF_C'
#include <errno.h>
#include <libvdeplug.h>
#include <stdio.h>
#include <string.h>
#include <sys/select.h>
#include <unistd.h>

static int receive_frame(VDECONN *conn, const unsigned char *expected,
                         size_t expected_len)
{
    unsigned char got[2048];
    fd_set rfds;
    struct timeval tv = {2, 0};
    int fd = vde_datafd(conn);
    ssize_t n;

    if (fd < 0)
        return -1;
    FD_ZERO(&rfds);
    FD_SET(fd, &rfds);
    if (select(fd + 1, &rfds, NULL, NULL, &tv) != 1)
        return -1;
    n = vde_recv(conn, got, sizeof(got), 0);
    if (n != (ssize_t)expected_len ||
        memcmp(expected, got, expected_len) != 0)
        return -1;
    return 0;
}

int main(int argc, char **argv)
{
    VDECONN *a = NULL, *b = NULL, *c = NULL, *bad;
    unsigned char frame[60] = {0xab,0x00,0x00,0x04,0x00,0x00,
                               0x02,0x00,0x00,0x00,0x00,0x01,
                               0x60,0x03,0x2e,0x00};
    unsigned int i;
    int rc = 1;

    if (argc != 3)
        return 2;

    errno = 0;
    bad = vde_open(argv[2], (char *)"dniv-vde-negative", NULL);
    if (bad) {
        fprintf(stderr, "vde native proof: invalid endpoint unexpectedly opened\n");
        vde_close(bad);
        return 1;
    }

    a = vde_open(argv[1], (char *)"dniv-vde-a", NULL);
    b = vde_open(argv[1], (char *)"dniv-vde-b", NULL);
    c = vde_open(argv[1], (char *)"dniv-vde-c", NULL);
    if (!a || !b || !c) {
        perror("vde_open");
        goto out;
    }

    for (i = 0; i < 256U; i++) {
        frame[16] = (unsigned char)(i & 0xffU);
        frame[17] = (unsigned char)((i >> 8) & 0xffU);
        frame[18] = (unsigned char)(i ^ 0xa5U);
        if (vde_send(a, frame, sizeof(frame), 0) != (ssize_t)sizeof(frame) ||
            receive_frame(b, frame, sizeof(frame)) ||
            receive_frame(c, frame, sizeof(frame))) {
            fprintf(stderr, "vde native proof: stress frame %u failed\n", i);
            goto out;
        }

        if (i == 127U) {
            vde_close(b);
            b = vde_open(argv[1], (char *)"dniv-vde-b-restart", NULL);
            if (!b) {
                perror("vde reopen b");
                goto out;
            }
        }
    }

    rc = 0;
out:
    if (c)
        vde_close(c);
    if (b)
        vde_close(b);
    if (a)
        vde_close(a);
    return rc;
}
EOF_C
cc -std=c11 -Wall -Wextra -Werror "$work/vde-native.c" -lvdeplug -o "$work/vde-native"
"$work/vde-native" "$url" "$badurl"

# Recreate the switch at the same endpoint and re-run the native multi-peer
# stress proof so switch lifecycle is part of the transport acceptance.
stop_switch
start_switch
"$work/vde-native" "$url" "$badurl"

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

start_py() {
    (
        cd "$work/pydecnet/pydecnet"
        exec "$work/venv/bin/python" -u -m decnet.main "$work/pydecnet.conf"
    ) >>"$work/pydecnet.log" 2>&1 &
    py_pid=$!
}

: >"$work/pydecnet.log"
start_py
for _ in $(seq 1 120); do
    if grep -Fq "Adjacency up" "$work/pydecnet.log" &&
       grep -Fq "31.77" "$work/pydecnet.log"; then
        break
    fi
    kill -0 "$py_pid" 2>/dev/null || { cat "$work/pydecnet.log" >&2; exit 1; }
    sleep 0.5
done
grep -Fq "Adjacency up" "$work/pydecnet.log" || {
    cat "$work/pydecnet.log" >&2
    echo "vde2-proof: initial Route20/PyDECnet VDE adjacency did not form" >&2
    exit 1
}

kill "$py_pid"
wait "$py_pid" 2>/dev/null || true
py_pid=
sleep 8
start_py
for _ in $(seq 1 160); do
    ups=$(grep -Fc "Adjacency up" "$work/pydecnet.log" || true)
    if [ "$ups" -ge 2 ]; then
        echo "vde2-proof: pass stress_frames=512 peers=3 switch_restart=1 peer_restart=1"
        exit 0
    fi
    kill -0 "$py_pid" 2>/dev/null || { cat "$work/pydecnet.log" >&2; exit 1; }
    sleep 0.5
done
cat "$work/pydecnet.log" >&2
echo "vde2-proof: adjacency did not recover after peer restart" >&2
exit 1
