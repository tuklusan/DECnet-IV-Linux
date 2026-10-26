#!/usr/bin/env bash
# DECnet-IV-Linux minimal source uninstaller.
# Copyright (c) 2026 Supratim Sanyal of SANYALnet Labs.
# Governed by the root LICENSE file; required attribution applies.
set -euo pipefail
umask 077
stage=${DESTDIR:-}
prefix=/usr/local
manifest=/var/lib/decnet-iv-linux/manifest
fail() { echo "uninstall: $*" >&2; exit 1; }
[[ -z $stage || ( $stage == /* && $stage != / && $stage != *[[:space:]]* && $stage != *'//'*
    && $stage != *'/../'* && $stage != */.. && $stage != *'/./'* && $stage != */. ) ]] || fail 'unsafe DESTDIR'
[[ -n $stage || $EUID == 0 ]] || fail 'run sudo ./uninstall.sh or specify DESTDIR'
for program in stat python3 sha256sum cut readlink rm; do
    command -v "$program" >/dev/null || fail "required tool missing: $program"
done
if [[ -z $stage ]]; then
    command -v depmod >/dev/null || fail 'depmod is required for live uninstall'
fi
check_parents() {
    local path=$1 current=/ part i
    local -a pieces
    IFS=/ read -r -a pieces <<<"${path#/}"
    for ((i=0; i+1<${#pieces[@]}; i++)); do
        part=${pieces[i]}
        [[ -n $part && $part != . && $part != .. ]] || return 1
        current="${current%/}/$part"
        if [[ -L $current ]]; then
            if [[ -z $stage && $current == /lib ]]; then
                case $(readlink -- /lib) in usr/lib|/usr/lib) continue;; esac
            fi
            return 1
        fi
        [[ ! -e $current || -d $current ]] || return 1
    done
}
if [[ -n $stage ]]; then
    check_parents "$stage/_check" || fail 'symlink or non-directory in DESTDIR path'
    [[ ! -L $stage && -d $stage ]] || fail 'unsafe DESTDIR'
fi
check_parents "$stage$manifest" || fail 'unsafe installation state path'
[[ -f $stage$manifest && ! -L $stage$manifest ]] || fail 'installation manifest not found'
[[ $(stat -c %h -- "$stage$manifest") == 1 ]] || fail 'unsafe manifest hard link'
# Bash read silently drops NUL bytes. Reject damaged manifests byte-for-byte.
python3 - "$stage$manifest" <<'PYVALID' || fail 'invalid manifest bytes'
from pathlib import Path
import sys
raw = Path(sys.argv[1]).read_bytes()
if not raw or not raw.endswith(b'\n') or len(raw) > 16384 or any(
    c not in (10,) and not (32 <= c <= 126) for c in raw
):
    raise SystemExit('invalid manifest bytes')
PYVALID

allowed() {
    case $1 in
        /etc/decnet.conf|/etc/dnetd.conf|/etc/modules-load.d/decnet-iv-linux.conf|\
        /etc/modprobe.d/decnet-iv-linux.conf|\
                /etc/systemd/system/decnet-iv-nml.service|\
        /etc/systemd/system/decnet-iv-fal.service|\
        /etc/systemd/system/decnet-iv-phone.service|\
        /etc/systemd/system/decnet-iv-mail.service|\
        /etc/systemd/system/decnet-iv-http.service) return 0;;
        /lib/modules/*/extra/decnet_iv.ko)
            local version=${1#/lib/modules/}; version=${version%/extra/decnet_iv.ko}
            [[ $version =~ ^[A-Za-z0-9._+-]+$ && $version != . && $version != .. ]] && return 0;;
        /usr/local/sbin/*)
            [[ ${1#/usr/local/sbin/} != */* ]] || return 1
            case ${1##*/} in dnctl|dnetd|dnfald|dnnml|dnphoned|dnmaild|dnhttpd|dnmultinet) return 0;; esac;;
        /usr/local/bin/*)
            [[ ${1#/usr/local/bin/} != */* ]] || return 1
            case ${1##*/} in ncp|dnlogin|sethost|dncopy|dntype|dndir|dndel|dnrename|dnsubmit|dnprint|dntask|dnnice|dnmirror|dnobject|phone|dnmail|dnlynx|dnping) return 0;; esac;;
        /usr/local/lib/*)
            [[ ${1#/usr/local/lib/} != */* ]] || return 1
            case ${1##*/} in libdnet.a|libdnet.so.1.0|libdnet.so.1|libdnet.so|libdnet_daemon.a|libdnet_daemon.so.1.0|libdnet_daemon.so.1|libdnet_daemon.so) return 0;; esac;;
        /usr/local/include/netdnet/dn.h|/usr/local/include/netdnet/dnetdb.h|\
        /usr/local/include/linux/dn.h|/usr/local/include/linux/decnet_iv.h) return 0;;
    esac
    return 1
}
valid_record() {
    local kind=$1 data=$2 path=$3
    allowed "$path" || return 1
    if [[ $kind == F ]]; then
        [[ $data =~ ^[0-9a-f]{64}$ ]]
    elif [[ $kind == L ]]; then
        case $path:$data in
            /usr/local/bin/sethost:dnlogin|\
            /usr/local/bin/dntype:dncopy|/usr/local/bin/dndir:dncopy|\
            /usr/local/bin/dndel:dncopy|/usr/local/bin/dnrename:dncopy|\
            /usr/local/bin/dnsubmit:dncopy|/usr/local/bin/dnprint:dncopy|\
            /usr/local/lib/libdnet.so.1:libdnet.so.1.0|\
            /usr/local/lib/libdnet.so:libdnet.so.1|\
            /usr/local/lib/libdnet_daemon.so.1:libdnet_daemon.so.1.0|\
            /usr/local/lib/libdnet_daemon.so:libdnet_daemon.so.1) return 0;;
        esac
        return 1
    else
        return 1
    fi
}
records=(); modules=(); declare -A seen=()
while IFS='|' read -r kind data path; do
    valid_record "$kind" "$data" "$path" || fail "unsafe manifest entry: $path"
    check_parents "$stage$path" || fail "unsafe managed-file parent: $path"
    [[ -z ${seen[$path]+x} ]] || fail 'duplicate manifest entry'
    seen[$path]=1
    # Saved as a flat list to avoid executing or sourcing any manifest text.
    records+=("$kind|$data|$path")
    if [[ $path == /lib/modules/*/extra/decnet_iv.ko ]]; then
        version=${path#/lib/modules/}; modules+=("${version%/extra/decnet_iv.ko}")
    fi
done <"$stage$manifest"

if [[ -z $stage ]]; then
    if command -v systemctl >/dev/null && [[ -d /run/systemd/system ]]; then
        for service in nml fal phone mail http; do
            unit=/etc/systemd/system/decnet-iv-$service.service
            for record in "${records[@]}"; do
                [[ ${record##*|} == "$unit" ]] || continue
                # Do not operate on a unit replaced or edited by an administrator.
                IFS='|' read -r kind expected stored <<<"$record"
                [[ $kind == F && -f $unit && ! -L $unit &&
                   $(sha256sum "$unit" | cut -d' ' -f1) == "$expected" ]] ||
                    fail "systemd unit was modified; stop it manually first: $unit"
                systemctl disable --now "decnet-iv-$service.service" ||
                    fail "cannot disable DECnet service: $service"
                break
            done
        done
    fi
    if command -v modprobe >/dev/null; then
        if [[ -d /sys/module/decnet_iv ]]; then
            modprobe -r decnet_iv || fail 'module still in use; stop DECnet clients before removal'
        fi
    fi
fi

preserved=0 removed=0
for record in "${records[@]}"; do
    IFS='|' read -r kind expected path <<<"$record"
    dest=$stage$path
    if [[ $kind == L ]]; then
        [[ -L $dest ]] || continue
        [[ $(readlink -- "$dest") == "$expected" ]] || { echo "Preserving modified link: $path"; ((preserved+=1)); continue; }
    else
        [[ -f $dest && ! -L $dest ]] || continue
        [[ $(stat -c %h -- "$dest") == 1 ]] || { echo "Preserving hardlinked file: $path"; ((preserved+=1)); continue; }
        [[ $(sha256sum "$dest" | cut -d' ' -f1) == "$expected" ]] || { echo "Preserving modified file: $path"; ((preserved+=1)); continue; }
    fi
    rm -f -- "$dest"; ((removed+=1))
done
rm -f -- "$stage$manifest"
for dir in /var/lib/decnet-iv-linux /usr/local/include/netdnet /usr/local/include/linux \
           /lib/modules/${modules[0]:-unused}/extra; do
    rmdir -- "$stage$dir" 2>/dev/null || true
done
if [[ -z $stage ]]; then
    for version in "${modules[@]}"; do depmod -a "$version"; done
    if command -v ldconfig >/dev/null; then ldconfig; fi
    if command -v systemctl >/dev/null && [[ -d /run/systemd/system ]]; then
        systemctl daemon-reload
    fi
fi
printf 'Removed %s files/links; retained %s locally modified files/links.\n' "$removed" "$preserved"
echo 'Data directories and user files were left untouched.'
