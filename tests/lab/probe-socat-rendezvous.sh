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

mode=${1:-}
case "$mode" in
    --server|--client) ;;
    *) echo "usage: $0 --server|--client" >&2; exit 2 ;;
esac

required=(VDE_SSH_HOST VDE_SSH_PORT VDE_SSH_USER VDE_SSH_KEY VDE_SSH_KNOWN_HOSTS GITHUB_RUN_ID)
missing=()
for name in "${required[@]}"; do
    [[ -n "${!name:-}" ]] || missing+=("$name")
done
if (( ${#missing[@]} )); then
    printf 'socat-rendezvous: missing required input: %s\n' "${missing[@]}" >&2
    exit 2
fi
[[ "$VDE_SSH_PORT" =~ ^[0-9]+$ ]] || { echo "socat-rendezvous: bad SSH port" >&2; exit 2; }
run_id=${GITHUB_RUN_ID//[^A-Za-z0-9_.-]/_}
remote_sock="/tmp/dniv-socat-${run_id}.sock"

work=$(mktemp -d /tmp/dniv-socat-rendezvous.XXXXXX)
trap 'rm -rf "$work"' EXIT
key_file="$work/bastion.key"
known_hosts="$work/known_hosts"
ssh_config="$work/ssh_config"

umask 077
printf '%s\n' "$VDE_SSH_KEY" >"$key_file"
printf '%s\n' "$VDE_SSH_KNOWN_HOSTS" >"$known_hosts"
chmod 600 "$key_file" "$known_hosts"
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

ssh_run() {
    ssh -F "$ssh_config" dniv-bastion "$@"
}

ssh_run 'command -v socat >/dev/null' || {
    echo "socat-rendezvous: socat unavailable on bastion" >&2
    exit 3
}

if [[ "$mode" == "--server" ]]; then
    ssh_run "rm -f '$remote_sock'"
    python3 - "$ssh_config" "$remote_sock" "$run_id" <<'PY'
import os
import select
import subprocess
import sys
import time

cfg, sock, run_id = sys.argv[1:]
cmd = ["ssh", "-F", cfg, "dniv-bastion",
       f"exec socat UNIX-LISTEN:'{sock}',unlink-early STDIO"]
p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                     stderr=subprocess.PIPE, text=True, bufsize=1)
try:
    ready = False
    for _ in range(60):
        q = subprocess.run(["ssh", "-F", cfg, "dniv-bastion", f"test -S '{sock}'"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if q.returncode == 0:
            ready = True
            break
        if p.poll() is not None:
            break
        time.sleep(0.5)
    if not ready:
        err = p.stderr.read() if p.poll() is not None else ""
        raise SystemExit("socat-rendezvous: server socket did not become ready" + (f": {err.strip()}" if err else ""))

    p.stdin.write(f"DNIV-SOCAT-SERVER {run_id}\n")
    p.stdin.flush()
    r, _, _ = select.select([p.stdout], [], [], 90)
    if not r:
        raise SystemExit("socat-rendezvous: server timed out waiting for client marker")
    line = p.stdout.readline().rstrip("\n")
    if line != f"DNIV-SOCAT-CLIENT {run_id}":
        raise SystemExit(f"socat-rendezvous: server marker mismatch: {line!r}")
    print("socat-rendezvous: server pass")
finally:
    try:
        p.stdin.close()
    except Exception:
        pass
    try:
        p.terminate()
        p.wait(timeout=3)
    except Exception:
        try:
            p.kill()
        except Exception:
            pass
PY
    ssh_run "rm -f '$remote_sock'" || true
    exit 0
fi

ready=0
for _ in $(seq 1 90); do
    if ssh_run "test -S '$remote_sock'" >/dev/null 2>&1; then
        ready=1
        break
    fi
    sleep 1
done
(( ready )) || {
    echo "socat-rendezvous: client did not see server socket" >&2
    exit 4
}

python3 - "$ssh_config" "$remote_sock" "$run_id" <<'PY'
import select
import subprocess
import sys

cfg, sock, run_id = sys.argv[1:]
cmd = ["ssh", "-F", cfg, "dniv-bastion",
       f"exec socat UNIX-CONNECT:'{sock}' STDIO"]
p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                     stderr=subprocess.PIPE, text=True, bufsize=1)
try:
    p.stdin.write(f"DNIV-SOCAT-CLIENT {run_id}\n")
    p.stdin.flush()
    r, _, _ = select.select([p.stdout], [], [], 30)
    if not r:
        raise SystemExit("socat-rendezvous: client timed out waiting for server marker")
    line = p.stdout.readline().rstrip("\n")
    if line != f"DNIV-SOCAT-SERVER {run_id}":
        raise SystemExit(f"socat-rendezvous: client marker mismatch: {line!r}")
    print("socat-rendezvous: client pass")
finally:
    try:
        p.stdin.close()
    except Exception:
        pass
    try:
        p.terminate()
        p.wait(timeout=3)
    except Exception:
        try:
            p.kill()
        except Exception:
            pass
PY
