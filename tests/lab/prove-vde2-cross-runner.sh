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
    "vde_plug $sock") exec vde_plug "$sock" ;;
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
    echo "usage: $0 --preflight-only|--wrapper-selftest|--server|--client" >&2
    exit 2
fi

for cmd in cc git make python3 ssh ssh-keygen vde_plug vde_switch dpipe; do
    command -v "$cmd" >/dev/null || { echo "vde2-cross: missing $cmd" >&2; exit 2; }
done

run_id=${GITHUB_RUN_ID:-manual}
run_id=${run_id//[^A-Za-z0-9_.-]/_}
server_sock="/tmp/dniv-vde-cross-${run_id}.ctl"
ready_file="/tmp/dniv-vde-cross-${run_id}.ready"
done_file="/tmp/dniv-vde-cross-${run_id}.done"
work=$(mktemp -d /tmp/dniv-vde-cross.XXXXXX)
key_file="$work/bastion.key"
known_hosts="$work/known_hosts"
ssh_config="$work/ssh_config"
switch_pid=
bridge_pid=
py_pid=
echo_pid=
reverse_pid=
sshd_pid=

stop_pid() {
    local pid=${1:-}
    [[ -z "$pid" ]] || kill "$pid" 2>/dev/null || true
    [[ -z "$pid" ]] || wait "$pid" 2>/dev/null || true
}

cleanup() {
    set +e
    stop_pid "${py_pid:-}"
    if [[ -n "${bridge_pid:-}" ]]; then
        kill -- "-$bridge_pid" 2>/dev/null || true
        wait "$bridge_pid" 2>/dev/null || true
    fi
    stop_pid "${echo_pid:-}"
    stop_pid "${reverse_pid:-}"
    if [[ -n "${sshd_pid:-}" ]]; then
        sudo kill "$sshd_pid" 2>/dev/null || true
    fi
    if [[ -r /var/run/route20.pid ]]; then
        rpid=$(cat /var/run/route20.pid 2>/dev/null)
        [[ -z "$rpid" ]] || sudo kill "$rpid" 2>/dev/null || true
        sudo rm -f /var/run/route20.pid
    fi
    if [[ -n "${switch_pid:-}" ]]; then
        kill "$switch_pid" 2>/dev/null || true
    fi
    rm -rf "$server_sock" "$ready_file" "$done_file" "$work"
}
trap cleanup EXIT INT TERM

umask 077
printf '%s\n' "$VDE_SSH_KEY" >"$key_file"
printf '%s\n' "$VDE_SSH_KNOWN_HOSTS" >"$known_hosts"
chmod 600 "$key_file" "$known_hosts"
ssh-keygen -y -P '' -f "$key_file" >"$work/bastion.pub" 2>/dev/null || {
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
    ConnectTimeout 10
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
    server_user=$(id -un)
    rm -f "$ready_file" "$done_file"
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
    [[ -s /var/run/route20.pid ]] || { echo "vde2-cross: Route20 did not start" >&2; exit 1; }

    wrapper="$work/remote-command.sh"
    write_remote_wrapper "$wrapper" "$ready_file" "$server_sock" "$done_file"
    pub=$(cat "$work/bastion.pub")
    printf 'restrict,command="%s" %s\n' "$wrapper" "$pub" >"$work/authorized_keys"
    ssh-keygen -q -t ed25519 -N '' -f "$work/ssh_host_ed25519_key"
    cat >"$work/sshd_config" <<EOF
Port 22222
ListenAddress 127.0.0.1
HostKey $work/ssh_host_ed25519_key
PidFile $work/sshd.pid
AuthorizedKeysFile $work/authorized_keys
StrictModes no
PubkeyAuthentication yes
PasswordAuthentication no
KbdInteractiveAuthentication no
PermitRootLogin no
UsePAM yes
AllowUsers $server_user
PermitTTY no
X11Forwarding no
AllowAgentForwarding no
AllowTcpForwarding no
LogLevel VERBOSE
EOF
    sudo mkdir -p /run/sshd
    sudo /usr/sbin/sshd -E "$work/sshd.log" -f "$work/sshd_config"
    for _ in $(seq 1 50); do
        [[ -s "$work/sshd.pid" ]] && break
        sleep 0.1
    done
    [[ -s "$work/sshd.pid" ]] || { echo "vde2-cross: inner sshd did not start" >&2; exit 1; }
    sshd_pid=$(cat "$work/sshd.pid")
    : >"$ready_file"
    local_inner_opts=(
        -i "$key_file"
        -p 22222
        -o BatchMode=yes
        -o IdentitiesOnly=yes
        -o ConnectTimeout=5
        -o ConnectionAttempts=1
        -o StrictHostKeyChecking=no
        -o UserKnownHostsFile=/dev/null
        -o LogLevel=ERROR
    )
    local_inner_err="$work/local-inner.err"
    if ! timeout -k 2 8 ssh -vvv "${local_inner_opts[@]}" "$server_user@127.0.0.1" \
        test -f "$ready_file" >/dev/null 2>"$local_inner_err"; then
        tail -n 24 "$local_inner_err" >&2 || true
        tail -n 24 "$work/sshd.log" >&2 || true
        echo "vde2-cross: inner SSH selfcheck failed" >&2
        exit 1
    fi

    reverse_log="$work/reverse-ssh.log"
    ssh -vvv -E "$reverse_log" -F "$ssh_config" -NT -o ExitOnForwardFailure=yes \
        -o ConnectTimeout=10 -o ConnectionAttempts=1 \
        -R "127.0.0.1:${DNIV_VDE_REVERSE_PORT}:127.0.0.1:22222" dniv-bastion &
    reverse_pid=$!
    sleep 2
    kill -0 "$reverse_pid" 2>/dev/null || {
        echo "vde2-cross: reverse SSH rendezvous failed" >&2
        exit 1
    }

    reverse_banner_err="$work/reverse-banner.err"
    reverse_banner=
    for _ in $(seq 1 6); do
        : >"$reverse_banner_err"
        reverse_banner=$(timeout -k 2 8 ssh -F "$ssh_config" dniv-bastion \
            -W "127.0.0.1:${DNIV_VDE_REVERSE_PORT}" 2>"$reverse_banner_err" | head -c 8 || true)
        [[ "$reverse_banner" == "SSH-2.0-" ]] && break
        kill -0 "$reverse_pid" 2>/dev/null || break
        sleep 1
    done
    if [[ "$reverse_banner" != "SSH-2.0-" ]]; then
        if grep -qi 'administratively prohibited' "$reverse_banner_err"; then
            echo "vde2-cross: bastion denies client-side forwarding to the reverse listener" >&2
        elif grep -qi 'connection refused' "$reverse_banner_err"; then
            echo "vde2-cross: bastion reverse listener refused the selfcheck connection" >&2
        elif grep -q 'forwarded-tcpip' "$reverse_log"; then
            echo "vde2-cross: reverse listener reached the server runner but relayed no inner SSH banner" >&2
        else
            echo "vde2-cross: reverse listener delivered no forwarding channel to the server runner" >&2
        fi
        exit 1
    fi
    echo "vde2-cross: reverse SSH banner selfcheck pass"

    for _ in $(seq 1 600); do
        [[ -f "$done_file" ]] && {
            echo "vde2-cross: server pass"
            exit 0
        }
        kill -0 "$reverse_pid" 2>/dev/null || {
            echo "vde2-cross: reverse SSH rendezvous was lost" >&2
            exit 1
        }
        sleep 1
    done
    echo "vde2-cross: client completion marker timed out after 600s" >&2
    exit 1
fi

remote_user=runner
proxy="ssh -F $ssh_config dniv-bastion -W 127.0.0.1:${DNIV_VDE_REVERSE_PORT}"
probe_proxy="timeout -k 2 8 ssh -F $ssh_config dniv-bastion -W 127.0.0.1:${DNIV_VDE_REVERSE_PORT}"
inner_opts=(
    -i "$key_file"
    -o "ProxyCommand=$proxy"
    -o BatchMode=yes
    -o IdentitiesOnly=yes
    -o ConnectTimeout=5
    -o ConnectionAttempts=1
    -o StrictHostKeyChecking=no
    -o UserKnownHostsFile=/dev/null
    -o LogLevel=ERROR
)
probe_inner_opts=(
    -i "$key_file"
    -o "ProxyCommand=$probe_proxy"
    -o BatchMode=yes
    -o IdentitiesOnly=yes
    -o ConnectTimeout=5
    -o ConnectionAttempts=1
    -o StrictHostKeyChecking=no
    -o UserKnownHostsFile=/dev/null
    -o LogLevel=ERROR
)
remote_host="$remote_user@dniv-vde-server"

banner_err="$work/server-banner.err"
banner=
for _ in $(seq 1 30); do
    : >"$banner_err"
    banner=$(timeout -k 2 8 ssh -F "$ssh_config" dniv-bastion \
        -W "127.0.0.1:${DNIV_VDE_REVERSE_PORT}" 2>"$banner_err" | head -c 8 || true)
    [[ "$banner" == "SSH-2.0-" ]] && break
    sleep 1
done
if [[ "$banner" != "SSH-2.0-" ]]; then
    sed -n '1,8p' "$banner_err" >&2 || true
    echo "vde2-cross: reverse endpoint did not present inner SSH banner" >&2
    exit 1
fi

ready_err="$work/server-ready.err"
ready=0
for _ in $(seq 1 20); do
    : >"$ready_err"
    if timeout -k 2 8 ssh "${probe_inner_opts[@]}" "$remote_host" test -f "$ready_file" \
        >/dev/null 2>"$ready_err"; then
        ready=1
        break
    fi
    sleep 1
done
if (( ! ready )); then
    sed -n '1,8p' "$ready_err" >&2 || true
    echo "vde2-cross: server rendezvous did not become ready" >&2
    exit 1
fi

local_sock="$work/client.ctl"
start_switch "$local_sock"

start_bridge() {
    setsid dpipe vde_plug "$local_sock" =         ssh "${inner_opts[@]}" "$remote_host" vde_plug "$server_sock"         >>"$work/bridge.log" 2>&1 &
    bridge_pid=$!
    sleep 1
    kill -0 "$bridge_pid" 2>/dev/null || {
        cat "$work/bridge.log" >&2 || true
        echo "vde2-cross: VDE-over-SSH bridge did not start" >&2
        exit 1
    }
}
stop_bridge() {
    if [[ -n "${bridge_pid:-}" ]]; then
        kill -- "-$bridge_pid" 2>/dev/null || true
        wait "$bridge_pid" 2>/dev/null || true
        bridge_pid=
    fi
}
start_bridge
"$work/vde-frame-echo" client "vde://$local_sock" 1 >/dev/null

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
logging console --events 4.15,4.16
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

: >"$work/pydecnet.log"
start_py
wait_ups 1

up_before=$(grep -Fc "Adjacency up" "$work/pydecnet.log" || true)
stop_bridge
sleep 8
start_bridge
wait_ups $((up_before + 1))
"$work/vde-frame-echo" client "vde://$local_sock" 2 >/dev/null

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

if ! timeout -k 2 8 ssh "${probe_inner_opts[@]}" "$remote_host" touch "$done_file" >/dev/null; then
    echo "vde2-cross: completion marker command failed" >&2
    exit 1
fi
echo "vde2-cross: client pass frames=3 bridge_reconnect=1 switch_restart=1 adjacency_recoveries=2"
