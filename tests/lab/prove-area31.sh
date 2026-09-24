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

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
repo_root=$(CDPATH= cd -- "$script_dir/../.." && pwd)

required=(
    MULTINET_REMOTE_HOST
    MULTINET_REMOTE_PORT
    VAX_ADDR
    VAX_USERNAME
    VAX_PASSWORD
)
missing=()
for name in "${required[@]}"; do
    [[ -n "${!name:-}" ]] || missing+=("$name")
done
if (( ${#missing[@]} )); then
    printf 'area31-proof: missing required secret: %s\n' "${missing[@]}" >&2
    exit 2
fi

if [[ ! "$MULTINET_REMOTE_PORT" =~ ^[0-9]+$ ]] ||
   (( MULTINET_REMOTE_PORT < 1 || MULTINET_REMOTE_PORT > 65535 )); then
    echo "area31-proof: MULTINET_REMOTE_PORT is invalid" >&2
    exit 2
fi
if [[ ! "$VAX_ADDR" =~ ^31\.([0-9]{1,4})$ ]] ||
   (( 10#${BASH_REMATCH[1]} < 1 || 10#${BASH_REMATCH[1]} > 1023 )); then
    echo "area31-proof: VAX_ADDR must identify an Area-31 node" >&2
    exit 2
fi

gateway_node=${DNIV_AREA31_GATEWAY_NODE:-}
gateway_name=${DNIV_AREA31_GATEWAY_NAME:-}
if [[ ! "$gateway_node" =~ ^31\.([0-9]{1,4})$ ]] ||
   (( 10#${BASH_REMATCH[1]} < 1 || 10#${BASH_REMATCH[1]} > 1023 )); then
    echo "area31-proof: DNIV_AREA31_GATEWAY_NODE must identify an assigned Area-31 node" >&2
    exit 2
fi
if [[ ! "$gateway_name" =~ ^[A-Za-z][A-Za-z0-9]{0,5}$ ]]; then
    echo "area31-proof: DNIV_AREA31_GATEWAY_NAME must be a 1..6 character DECnet name" >&2
    exit 2
fi

if [[ "${1:-}" == "--preflight-only" ]]; then
    echo "area31-proof: preflight pass"
    exit 0
fi
if (( $# != 0 )); then
    echo "usage: $0 [--preflight-only]" >&2
    exit 2
fi

source "$repo_root/tests/reference/refs.env"

work=$(mktemp -d /tmp/dniv-area31.XXXXXX)
gateway_pid=
switch_pid=

cleanup() {
    set +e
    [[ -z "${gateway_pid:-}" ]] || kill "$gateway_pid" 2>/dev/null || true
    [[ -z "${gateway_pid:-}" ]] || wait "$gateway_pid" 2>/dev/null || true
    [[ -z "${switch_pid:-}" ]] || kill "$switch_pid" 2>/dev/null || true
    rm -rf "$work"
}
trap cleanup EXIT INT TERM

git clone -q https://github.com/tuklusan/pydecnet.git "$work/pydecnet"
git -C "$work/pydecnet" checkout -q "$PYDECNET_REF"
test "$(git -C "$work/pydecnet" rev-parse HEAD)" = "$PYDECNET_REF"

python3 -m venv "$work/venv"
"$work/venv/bin/python" -m pip install -q --upgrade pip setuptools
"$work/venv/bin/python" -m pip install -q "$work/pydecnet/pydecnet"

sock="$work/vde.ctl"
vde_switch -daemon -sock "$sock" >/dev/null 2>&1
for _ in $(seq 1 50); do
    switch_pid=$(pgrep -f "vde_switch.*-sock $sock" | head -n1 || true)
    [[ -n "$switch_pid" && -S "$sock/ctl" ]] && break
    sleep 0.1
done
[[ -n "$switch_pid" && -S "$sock/ctl" ]] || {
    echo "area31-proof: VDE switch did not start" >&2
    exit 1
}

api_sock="$work/decnetapi.sock"
"$work/venv/bin/python" "$repo_root/userspace/dnmultinet/dnmultinet.py" \
    --node "$gateway_node" --name "$gateway_name" --type l2router \
    --vde "vde://$sock" --mode connect --runtime-peer-env \
    --api-socket "$api_sock" --pydecnet-dir "$work/pydecnet/pydecnet" \
    >/dev/null 2>&1 &
gateway_pid=$!

for _ in $(seq 1 300); do
    kill -0 "$gateway_pid" 2>/dev/null || {
        echo "area31-proof: gateway exited before remote routing became usable" >&2
        exit 1
    }
    if [[ -S "$api_sock" ]] &&
       env PYTHONPATH="$work/pydecnet/pydecnet" VAX_ADDR="$VAX_ADDR" \
           "$work/venv/bin/python" "$script_dir/area31-nice.py" \
           "$api_sock" "$gateway_name" >/dev/null 2>&1; then
        env PYTHONPATH="$work/pydecnet/pydecnet" VAX_ADDR="$VAX_ADDR" \
            "$work/venv/bin/python" "$script_dir/area31-nice.py" \
            "$api_sock" "$gateway_name"
        echo "area31-proof: remote MULTINET routing and VAX NICE reachability pass"
        exit 0
    fi
    sleep 1
done

echo "area31-proof: VAX NICE reachability did not converge" >&2
exit 1
