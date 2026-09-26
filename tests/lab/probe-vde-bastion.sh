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

required=(VDE_SSH_HOST VDE_SSH_PORT VDE_SSH_USER VDE_SSH_KEY VDE_SSH_KNOWN_HOSTS)
missing=()
for name in "${required[@]}"; do
    [[ -n "${!name:-}" ]] || missing+=("$name")
done
if (( ${#missing[@]} )); then
    printf 'vde2-bastion-probe: missing required secret: %s\n' "${missing[@]}" >&2
    exit 2
fi

work=$(mktemp -d /tmp/dniv-vde-bastion-probe.XXXXXX)
trap 'rm -rf "$work"' EXIT
key_file="$work/bastion.key"
known_hosts="$work/known_hosts"
ssh_config="$work/ssh_config"

umask 077
printf '%s\n' "$VDE_SSH_KEY" >"$key_file"
printf '%s\n' "$VDE_SSH_KNOWN_HOSTS" >"$known_hosts"
chmod 600 "$key_file" "$known_hosts"
cat >"$ssh_config" <<EOF_CONFIG
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
EOF_CONFIG
chmod 600 "$ssh_config"

echo 'vde2-bastion-probe: SSH login probe start'
ssh -F "$ssh_config" dniv-bastion 'sh -s' <<'EOF_REMOTE'
set -eu
echo 'vde2-bastion-probe: SSH login pass'
for tool in socat nc netcat ncat; do
    if path=$(command -v "$tool" 2>/dev/null); then
        echo "vde2-bastion-probe: tool available name=$tool path=$path"
    else
        echo "vde2-bastion-probe: tool unavailable name=$tool"
    fi
done
echo 'vde2-bastion-probe: vde_switch process inventory:'
processes=$(ps -eo pid=,args= | grep '[v]de_switch' || true)
if [ -n "$processes" ]; then
    printf '%s\n' "$processes"
else
    echo 'vde2-bastion-probe: no vde_switch process visible'
fi
if command -v vde_switch >/dev/null 2>&1; then
    echo 'vde2-bastion-probe: vde_switch available'
    have_switch=1
else
    echo 'vde2-bastion-probe: vde_switch unavailable'
    have_switch=0
fi
if command -v vde_plug >/dev/null 2>&1; then
    echo 'vde2-bastion-probe: vde_plug available'
    have_plug=1
else
    echo 'vde2-bastion-probe: vde_plug unavailable'
    have_plug=0
fi
candidates=$(
    {
        ps -eo args= | awk '
            /[v]de_switch/ {
                for (i = 1; i <= NF; i++) {
                    if (($i == "-sock" || $i == "--sock") && i < NF) print $(i + 1)
                    if ($i ~ /^--sock=/) { sub(/^--sock=/, "", $i); print $i }
                }
            }'
        for search_root in /tmp /run /var/run "$HOME"; do
            [ -d "$search_root" ] || continue
            find "$search_root" -maxdepth 5 -type s -name ctl -print 2>/dev/null | sed 's#/ctl$##'
        done
    } | awk 'NF && !seen[$0]++'
)
attached=0
if [ -n "$candidates" ]; then
    echo 'vde2-bastion-probe: VDE control candidates:'
    printf '%s\n' "$candidates"
    if [ "$have_plug" -eq 1 ]; then
        for socket_dir in $candidates; do
            vde_plug "vde://$socket_dir" </dev/null >/dev/null 2>&1 &
            plug_pid=$!
            sleep 1
            if kill -0 "$plug_pid" 2>/dev/null; then
                echo "vde2-bastion-probe: attach pass socket=$socket_dir"
                attached=1
                kill "$plug_pid" 2>/dev/null || true
                wait "$plug_pid" 2>/dev/null || true
            else
                if wait "$plug_pid"; then
                    echo "vde2-bastion-probe: attach pass socket=$socket_dir"
                    attached=1
                else
                    echo "vde2-bastion-probe: attach fail socket=$socket_dir"
                fi
            fi
        done
    fi
else
    echo 'vde2-bastion-probe: no existing VDE control socket candidate found'
fi
if [ "$attached" -eq 1 ]; then
    exit 0
fi
[ "$have_switch" -eq 1 ] || exit 6
[ "$have_plug" -eq 1 ] || exit 4

probe_root=$(mktemp -d /tmp/dniv-vde-bastion-switch.XXXXXX)
probe_sock="$probe_root/switch.ctl"
switch_pid=
plug_pid=
cleanup_probe_switch() {
    set +e
    [ -z "${plug_pid:-}" ] || kill "$plug_pid" 2>/dev/null || true
    [ -z "${plug_pid:-}" ] || wait "$plug_pid" 2>/dev/null || true
    [ -z "${switch_pid:-}" ] || kill "$switch_pid" 2>/dev/null || true
    [ -z "${switch_pid:-}" ] || wait "$switch_pid" 2>/dev/null || true
    rm -rf "$probe_root"
}
trap cleanup_probe_switch EXIT HUP INT TERM
vde_switch -sock "$probe_sock" >/dev/null 2>&1 &
switch_pid=$!
for _ in $(seq 1 50); do
    [ -S "$probe_sock/ctl" ] && break
    kill -0 "$switch_pid" 2>/dev/null || break
    sleep 0.1
done
if [ ! -S "$probe_sock/ctl" ]; then
    echo 'vde2-bastion-probe: ephemeral vde_switch could not create a control socket'
    exit 7
fi
vde_plug "vde://$probe_sock" </dev/null >/dev/null 2>&1 &
plug_pid=$!
sleep 1
if kill -0 "$plug_pid" 2>/dev/null; then
    echo 'vde2-bastion-probe: ephemeral switch create/attach pass'
    exit 0
fi
if wait "$plug_pid"; then
    plug_pid=
    echo 'vde2-bastion-probe: ephemeral switch create/attach pass'
    exit 0
fi
plug_pid=
echo 'vde2-bastion-probe: ephemeral switch attach failed'
exit 8
EOF_REMOTE
