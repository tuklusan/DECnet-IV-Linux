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

is_outer_connect_timeout() {
    grep -Eq "^(ssh: connect to host .+ port .+: Connection timed out|Connection timed out during banner exchange)$" "$1"
}

collect_process_descendants() {
    local parent=$1 child
    [[ -r "/proc/$parent/task/$parent/children" ]] || return 0
    for child in $(cat "/proc/$parent/task/$parent/children" 2>/dev/null || true); do
        collect_process_descendants "$child"
        process_tree+=("$child")
    done
}

stop_process_tree() {
    local root=$1 pid
    local -a process_tree=()
    collect_process_descendants "$root"
    kill -TERM -- "-$root" 2>/dev/null || true
    for pid in "${process_tree[@]}"; do
        kill -TERM "$pid" 2>/dev/null || true
    done
    sleep 0.2
    kill -KILL -- "-$root" 2>/dev/null || true
    for pid in "${process_tree[@]}"; do
        kill -KILL "$pid" 2>/dev/null || true
    done
    wait "$root" 2>/dev/null || true
}

if [[ "${1:-}" == "--classifier-selftest" ]]; then
    selftest_err=$(mktemp /tmp/dniv-vde-classifier.XXXXXX)
    trap 'rm -f "$selftest_err"' EXIT
    printf '%s\n' 'ssh: connect to host *** port ***: Connection timed out' >"$selftest_err"
    is_outer_connect_timeout "$selftest_err" || {
        echo "vde2-cross: masked outer-timeout classifier selftest failed" >&2
        exit 1
    }
    printf '%s\n' 'Connection timed out during banner exchange' >"$selftest_err"
    is_outer_connect_timeout "$selftest_err" || {
        echo "vde2-cross: outer-banner-timeout classifier selftest failed" >&2
        exit 1
    }
    printf '%s\n' 'channel 2: open failed: connect failed: Connection timed out' >"$selftest_err"
    if is_outer_connect_timeout "$selftest_err"; then
        echo "vde2-cross: forwarded-target timeout classifier false positive" >&2
        exit 1
    fi
    echo "vde2-cross: timeout classifier selftest pass"
    exit 0
fi

if [[ "${1:-}" == "--bridge-stop-selftest" ]]; then
    selftest_dir=$(mktemp -d /tmp/dniv-vde-stop.XXXXXX)
    child_file="$selftest_dir/child"
    trap 'rm -rf "$selftest_dir"' EXIT
    setsid sh -c 'setsid sleep 30 & echo $! >"$1"; wait' sh "$child_file" &
    tree_root=$!
    for _ in $(seq 1 50); do
        [[ -s "$child_file" ]] && break
        sleep 0.02
    done
    [[ -s "$child_file" ]] || {
        echo "vde2-cross: bridge-stop selftest did not create child" >&2
        exit 1
    }
    tree_child=$(cat "$child_file")
    stop_process_tree "$tree_root"
    for pid in "$tree_root" "$tree_child"; do
        if [[ -r "/proc/$pid/stat" ]]; then
            state=$(awk '{print $3}' "/proc/$pid/stat" 2>/dev/null || true)
            [[ "$state" == "Z" ]] || {
                echo "vde2-cross: bridge-stop selftest left live process" >&2
                exit 1
            }
        fi
    done
    echo "vde2-cross: bridge-stop selftest pass"
    exit 0
fi

root=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
. "$root/tests/reference/refs.env"

required=(VDE_SSH_HOST VDE_SSH_PORT VDE_SSH_USER VDE_SSH_KEY VDE_SSH_KNOWN_HOSTS DNIV_VDE_REVERSE_PORT)
missing=()
for name in "${required[@]}"; do
    [[ -n "${!name:-}" ]] || missing+=("$name")
done
if (( ${#missing[@]} )); then
    printf 'vde2-cross: missing required secret/input: %s\n' "${missing[@]}" >&2
    exit 2
fi
for name in VDE_SSH_PORT DNIV_VDE_REVERSE_PORT; do
    value=${!name}
    [[ "$value" =~ ^[0-9]+$ ]] || { echo "vde2-cross: $name must be numeric" >&2; exit 2; }
done
banner_attempts=${DNIV_VDE_BANNER_ATTEMPTS:-30}
[[ "$banner_attempts" =~ ^[0-9]+$ ]] && (( banner_attempts >= 1 && banner_attempts <= 60 )) || {
    echo "vde2-cross: DNIV_VDE_BANNER_ATTEMPTS must be 1..60" >&2
    exit 2
}
(( VDE_SSH_PORT >= 1 && VDE_SSH_PORT <= 65535 )) || {
    echo "vde2-cross: VDE_SSH_PORT is invalid" >&2
    exit 2
}
(( DNIV_VDE_REVERSE_PORT >= 1024 && DNIV_VDE_REVERSE_PORT <= 65535 )) || {
    echo "vde2-cross: DNIV_VDE_REVERSE_PORT must be 1024..65535" >&2
    exit 2
}
[[ "$VDE_SSH_HOST" != *[[:space:]]* && "$VDE_SSH_USER" != *[[:space:]]* ]] || {
    echo "vde2-cross: SSH host/user syntax is invalid" >&2
    exit 2
}

write_remote_wrapper() {
    local path=$1 ready=$2 sock=$3 done=$4
    cat >"$path" <<EOF
#!/usr/bin/env bash
set -euo pipefail
case "\${SSH_ORIGINAL_COMMAND:-}" in
    "test -f $ready") test -f "$ready" ;;
    "vde_plug vde://$sock") exec vde_plug "vde://$sock" ;;
    "touch $done") : >"$done" ;;
    *) exit 126 ;;
esac
EOF
    chmod 700 "$path"
}

if [[ "${1:-}" == "--preflight-only" ]]; then
    echo "vde2-cross: preflight pass"
    exit 0
fi
if [[ "${1:-}" == "--wrapper-selftest" ]]; then
    selftest_dir=$(mktemp -d /tmp/dniv-vde-wrapper.XXXXXX)
    trap 'rm -rf "$selftest_dir"' EXIT
    selftest_ready="$selftest_dir/ready"
    selftest_done="$selftest_dir/done"
    selftest_sock="$selftest_dir/switch.ctl"
    selftest_wrapper="$selftest_dir/remote-command.sh"
    : >"$selftest_ready"
    write_remote_wrapper "$selftest_wrapper" "$selftest_ready" "$selftest_sock" "$selftest_done"
    SSH_ORIGINAL_COMMAND="test -f $selftest_ready" "$selftest_wrapper"
    if SSH_ORIGINAL_COMMAND="not-allowed" "$selftest_wrapper"; then
        echo "vde2-cross: wrapper accepted an unlisted command" >&2
        exit 1
    else
        rc=$?
        [[ "$rc" -eq 126 ]] || {
            echo "vde2-cross: wrapper returned the wrong rejection status" >&2
            exit 1
        }
    fi
    echo "vde2-cross: wrapper selftest pass"
    exit 0
fi
if [[ "${1:-}" != "--server" && "${1:-}" != "--client" ]]; then
    echo "usage: $0 --preflight-only|--classifier-selftest|--bridge-stop-selftest|--wrapper-selftest|--server|--client" >&2
    exit 2
fi

for cmd in cc git make python3 setsid ssh ssh-keygen vde_plug vde_switch dpipe; do
    command -v "$cmd" >/dev/null || { echo "vde2-cross: missing $cmd" >&2; exit 2; }
done

run_id=${GITHUB_RUN_ID:-manual}
run_id=${run_id//[^A-Za-z0-9_.-]/_}
server_sock="/tmp/dniv-vde-cross-${run_id}.ctl"
relay_sock="/tmp/dniv-vde-relay-${run_id}.sock"
work=$(mktemp -d /tmp/dniv-vde-cross.XXXXXX)
key_file="$work/bastion.key"
known_hosts="$work/known_hosts"
ssh_config="$work/ssh_config"
switch_pid=
bridge_pid=
py_pid=
echo_pid=
current_bridge_log=

stop_pid() {
    local pid=${1:-}
    [[ -z "$pid" ]] || kill "$pid" 2>/dev/null || true
    [[ -z "$pid" ]] || wait "$pid" 2>/dev/null || true
}

cleanup() {
    set +e
    stop_pid "${py_pid:-}"
    if [[ -n "${bridge_pid:-}" ]]; then
        stop_process_tree "$bridge_pid"
    fi
    stop_pid "${echo_pid:-}"
    if [[ -r /var/run/route20.pid ]]; then
        rpid=$(cat /var/run/route20.pid 2>/dev/null)
        [[ -z "$rpid" ]] || sudo kill "$rpid" 2>/dev/null || true
        sudo rm -f /var/run/route20.pid
    fi
    if [[ -n "${switch_pid:-}" ]]; then
        kill "$switch_pid" 2>/dev/null || true
    fi
    rm -rf "$server_sock" "$work"
}
trap cleanup EXIT INT TERM

umask 077
printf '%s\n' "$VDE_SSH_KEY" >"$key_file"
printf '%s\n' "$VDE_SSH_KNOWN_HOSTS" >"$known_hosts"
chmod 600 "$key_file" "$known_hosts"
ssh-keygen -y -P '' -f "$key_file" >/dev/null 2>&1 || {
    echo "vde2-cross: VDE_SSH_KEY must be a usable noninteractive private key" >&2
    exit 2
}
cat >"$ssh_config" <<EOF
Host dniv-bastion
    HostName $VDE_SSH_HOST
    User $VDE_SSH_USER
    Port $VDE_SSH_PORT
    IdentityFile $key_file
    IdentitiesOnly yes
    BatchMode yes
    UserKnownHostsFile $known_hosts
    StrictHostKeyChecking yes
    LogLevel ERROR
    ConnectTimeout 8
    ConnectionAttempts 1
    ServerAliveInterval 15
    ServerAliveCountMax 3
EOF
chmod 600 "$ssh_config"

cc -std=c11 -Wall -Wextra -Werror "$root/tests/lab/vde-frame-echo.c" -lvdeplug -o "$work/vde-frame-echo"

start_switch() {
    local sock=$1
    rm -rf "$sock"
    vde_switch -daemon -sock "$sock" >/dev/null 2>&1
    switch_pid=
    for _ in $(seq 1 80); do
        switch_pid=$(pgrep -f "vde_switch.*-sock $sock" | head -n1 || true)
        [[ -n "$switch_pid" && -S "$sock/ctl" ]] && return 0
        sleep 0.1
    done
    echo "vde2-cross: VDE switch did not start" >&2
    exit 1
}

if [[ "$1" == "--server" ]]; then
    start_switch "$server_sock"
    "$work/vde-frame-echo" server "vde://$server_sock" >/dev/null 2>&1 &
    echo_pid=$!

    git init -q "$work/route20"
    git -C "$work/route20" remote add origin https://github.com/tuklusan/Route20.git
    git -C "$work/route20" fetch -q --depth=1 origin "$ROUTE20_REF"
    git -C "$work/route20" checkout -q --detach FETCH_HEAD
    test "$(git -C "$work/route20" rev-parse HEAD)" = "$ROUTE20_REF"
    make -C "$work/route20/Route20" >/dev/null
    cat >"$work/route20.ini" <<EOF
[node]
name=VDR77
level=1
address=31.77
priority=64

[ethernet]
interface=vde://$server_sock
cost=3

[nsp]
InactivityTimer=30

[session]
InactivityTimer=60
EOF
    sudo rm -f /var/run/route20.pid
    sudo "$work/route20/Route20/route20" "$work/route20.ini"
    for _ in $(seq 1 100); do
        [[ -s /var/run/route20.pid ]] && break
        sleep 0.1
    done
    [[ -s /var/run/route20.pid ]] || {
        echo "vde2-cross: Route20 did not start" >&2
        exit 1
    }

    for session in 1 2 3; do
        log="$work/server-bridge-${session}.log"
        : >"$log"
        started=$SECONDS
        setsid timeout -k 5 300 dpipe vde_plug "vde://$server_sock" = \
            ssh -F "$ssh_config" dniv-bastion socat \
            "UNIX-LISTEN:$relay_sock,unlink-early,unlink-close" STDIO \
            >>"$log" 2>&1 &
        bridge_pid=$!
        set +e
        wait "$bridge_pid"
        rc=$?
        set -e
        bridge_pid=
        elapsed=$((SECONDS - started))
        if (( elapsed < 2 )); then
            cat "$log" >&2 || true
            echo "vde2-cross: socat server bridge session $session exited before client attachment rc=$rc" >&2
            exit 1
        fi
        if grep -Eqi 'Permission denied|Authentication failed|Host key verification failed|REMOTE HOST IDENTIFICATION HAS CHANGED' "$log"; then
            cat "$log" >&2 || true
            echo "vde2-cross: socat server bridge session $session failed SSH authentication/verification" >&2
            exit 1
        fi
        if (( rc == 124 || rc == 137 )); then
            cat "$log" >&2 || true
            echo "vde2-cross: socat server bridge session $session timed out" >&2
            exit 1
        fi
        kill -0 "$echo_pid" 2>/dev/null || {
            echo "vde2-cross: frame echo server exited during relay session $session" >&2
            exit 1
        }
        echo "vde2-cross: socat server relay session $session complete rc=$rc elapsed=${elapsed}s"
        sleep 1
    done

    [[ -r /var/run/route20.pid ]] || {
        echo "vde2-cross: Route20 pid disappeared" >&2
        exit 1
    }
    rpid=$(cat /var/run/route20.pid)
    kill -0 "$rpid" 2>/dev/null || {
        echo "vde2-cross: Route20 exited during socat relay proof" >&2
        exit 1
    }
    echo "vde2-cross: server pass socat_sessions=3"
    exit 0
fi

local_sock="$work/client.ctl"
start_switch "$local_sock"
bridge_generation=0

start_bridge() {
    local attempt rc log
    bridge_generation=$((bridge_generation + 1))
    for attempt in $(seq 1 8); do
        log="$work/client-bridge-${bridge_generation}-${attempt}.log"
        : >"$log"
        setsid dpipe vde_plug "vde://$local_sock" = \
            ssh -F "$ssh_config" dniv-bastion socat \
            "UNIX-CONNECT:$relay_sock" STDIO >>"$log" 2>&1 &
        bridge_pid=$!
        sleep 1
        if kill -0 "$bridge_pid" 2>/dev/null; then
            current_bridge_log=$log
            return 0
        fi
        set +e
        wait "$bridge_pid"
        rc=$?
        set -e
        bridge_pid=
        if is_outer_connect_timeout "$log"; then
            cat "$log" >&2 || true
            echo "vde2-cross: direct socat bridge outer SSH connection timed out" >&2
            return 75
        fi
        if grep -Eqi 'Permission denied|Authentication failed|Host key verification failed|REMOTE HOST IDENTIFICATION HAS CHANGED' "$log"; then
            cat "$log" >&2 || true
            echo "vde2-cross: direct socat bridge SSH authentication/verification failed" >&2
            return 1
        fi
        sleep 2
    done
    cat "$log" >&2 || true
    echo "vde2-cross: socat VDE bridge did not attach after retries" >&2
    return 1
}

stop_bridge() {
    if [[ -n "${bridge_pid:-}" ]]; then
        stop_process_tree "$bridge_pid"
        bridge_pid=
    fi
}

wait_bridge_frame() {
    local token=$1
    for _ in $(seq 1 3); do
        if "$work/vde-frame-echo" client "vde://$local_sock" "$token" >/dev/null; then
            return 0
        fi
        kill -0 "$bridge_pid" 2>/dev/null || {
            cat "$current_bridge_log" >&2 || true
            echo "vde2-cross: socat VDE bridge exited during frame readiness" >&2
            return 1
        }
        sleep 1
    done
    cat "$current_bridge_log" >&2 || true
    echo "vde2-cross: socat VDE bridge did not become frame-ready" >&2
    return 1
}

start_bridge
wait_bridge_frame 1

git init -q "$work/pydecnet"
git -C "$work/pydecnet" remote add origin https://github.com/tuklusan/pydecnet.git
git -C "$work/pydecnet" fetch -q --depth=1 origin "$PYDECNET_REF"
git -C "$work/pydecnet" checkout -q --detach FETCH_HEAD
test "$(git -C "$work/pydecnet" rev-parse HEAD)" = "$PYDECNET_REF"
python3 -m venv "$work/venv"
"$work/venv/bin/python" -m pip install -q --upgrade pip setuptools
"$work/venv/bin/python" -m pip install -q "$work/pydecnet/pydecnet"
cat >"$work/pydecnet.conf" <<EOF
routing 31.78 --type l1router
node 31.77 VDR77
node 31.78 VDP78
circuit ETH-0 Ethernet vde://$local_sock --mode vde --cost 3 --t3 2 --priority 64
logging console --events 4.15,4.18
EOF

start_py() {
    (
        cd "$work/pydecnet/pydecnet"
        exec "$work/venv/bin/python" -u -m decnet.main "$work/pydecnet.conf"
    ) >>"$work/pydecnet.log" 2>&1 &
    py_pid=$!
}

wait_ups() {
    local want=$1
    for _ in $(seq 1 160); do
        count=$(grep -Fc "Adjacency up" "$work/pydecnet.log" 2>/dev/null || true)
        (( count >= want )) && return 0
        kill -0 "$py_pid" 2>/dev/null || {
            cat "$work/pydecnet.log" >&2 || true
            return 1
        }
        sleep 0.5
    done
    cat "$work/pydecnet.log" >&2 || true
    return 1
}

wait_downs() {
    local want=$1
    for _ in $(seq 1 240); do
        count=$(grep -Fc "Adjacency down" "$work/pydecnet.log" 2>/dev/null || true)
        (( count >= want )) && return 0
        kill -0 "$py_pid" 2>/dev/null || {
            cat "$work/pydecnet.log" >&2 || true
            return 1
        }
        sleep 0.5
    done
    cat "$work/pydecnet.log" >&2 || true
    return 1
}

: >"$work/pydecnet.log"
start_py
wait_ups 1

up_before=$(grep -Fc "Adjacency up" "$work/pydecnet.log" || true)
down_before=$(grep -Fc "Adjacency down" "$work/pydecnet.log" || true)
stop_bridge
if "$work/vde-frame-echo" client "vde://$local_sock" 90 >/dev/null 2>&1; then
    echo "vde2-cross: transport stop left cross-runner frame path alive" >&2
    exit 1
fi
wait_downs $((down_before + 1))
start_bridge
wait_bridge_frame 2
wait_ups $((up_before + 1))

stop_pid "$py_pid"
py_pid=
stop_bridge
if [[ -n "${switch_pid:-}" ]]; then
    kill "$switch_pid" 2>/dev/null || true
    for _ in $(seq 1 50); do
        kill -0 "$switch_pid" 2>/dev/null || break
        sleep 0.1
    done
    switch_pid=
fi
rm -rf "$local_sock"
start_switch "$local_sock"
start_bridge
up_before=$(grep -Fc "Adjacency up" "$work/pydecnet.log" || true)
start_py
wait_ups $((up_before + 1))
"$work/vde-frame-echo" client "vde://$local_sock" 3 >/dev/null
stop_bridge
sleep 1

echo "vde2-cross: client pass transport=socat frames=3 bridge_reconnect=1 switch_restart=1 adjacency_recoveries=2"
