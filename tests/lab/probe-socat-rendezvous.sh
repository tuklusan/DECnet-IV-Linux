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

if [[ "$mode" == "--server" ]]; then
    python3 - "$ssh_config" "$remote_sock" "$run_id" <<'PY'
import select
import subprocess
import sys

cfg, sock, run_id = sys.argv[1:]
cmd = ["ssh", "-F", cfg, "dniv-bastion",
       f"exec socat UNIX-LISTEN:{sock},unlink-early STDIO"]
p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                     stderr=subprocess.PIPE, text=True, bufsize=1)
try:
    p.stdin.write(f"DNIV-SOCAT-SERVER {run_id}\\n")
    p.stdin.flush()
    r, _, _ = select.select([p.stdout], [], [], 75)
    if not r:
        rc = p.poll()
        err = p.stderr.read().strip() if rc is not None else ""
        detail = f" rc={rc}" if rc is not None else ""
        if err:
            detail += f" stderr={err}"
        raise SystemExit("socat-rendezvous: server timed out waiting for client marker" + detail)
    line = p.stdout.readline().rstrip("\\n")
    if line != f"DNIV-SOCAT-CLIENT {run_id}":
        rc = p.poll()
        err = p.stderr.read().strip() if rc is not None else ""
        raise SystemExit(f"socat-rendezvous: server marker mismatch: {line!r} rc={rc} stderr={err}")
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
    exit 0
fi

sleep 6
python3 - "$ssh_config" "$remote_sock" "$run_id" <<'PY'
import select
import subprocess
import sys
import time

cfg, sock, run_id = sys.argv[1:]

last = ""
for attempt in range(2):
    cmd = ["ssh", "-F", cfg, "dniv-bastion",
           f"exec socat UNIX-CONNECT:{sock} STDIO"]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE, text=True, bufsize=1)
    try:
        p.stdin.write(f"DNIV-SOCAT-CLIENT {run_id}\\n")
        p.stdin.flush()
        r, _, _ = select.select([p.stdout], [], [], 20)
        if r:
            line = p.stdout.readline().rstrip("\\n")
            if line == f"DNIV-SOCAT-SERVER {run_id}":
                print("socat-rendezvous: client pass")
                raise SystemExit(0)
            last = f"marker mismatch: {line!r}"
        else:
            rc = p.poll()
            err = p.stderr.read().strip() if rc is not None else ""
            last = f"timeout rc={rc} stderr={err}"
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
    if attempt == 0:
        time.sleep(4)

raise SystemExit("socat-rendezvous: client failed: " + last)
PY

