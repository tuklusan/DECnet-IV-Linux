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
echo 'vde2-bastion-probe: vde_switch process inventory:'
processes=$(ps -eo pid=,args= | grep '[v]de_switch' || true)
if [ -n "$processes" ]; then
    printf '%s\n' "$processes"
else
    echo 'vde2-bastion-probe: no vde_switch process visible'
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
        find /tmp -maxdepth 4 -type s -name ctl -print 2>/dev/null | sed 's#/ctl$##'
    } | awk 'NF && !seen[$0]++'
)
if [ -z "$candidates" ]; then
    echo 'vde2-bastion-probe: no VDE control socket candidate found'
    exit 3
fi
echo 'vde2-bastion-probe: VDE control candidates:'
printf '%s\n' "$candidates"
if ! command -v vde_plug >/dev/null 2>&1; then
    echo 'vde2-bastion-probe: vde_plug is unavailable on bastion'
    exit 4
fi
attached=0
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
[ "$attached" -eq 1 ] || exit 5
EOF_REMOTE
