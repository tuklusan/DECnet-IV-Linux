#!/usr/bin/env bash
# DECnet-IV-Linux minimal source installer.
# Copyright (c) 2026 Supratim Sanyal of SANYALnet Labs.
# Governed by the root LICENSE file; required attribution applies.
set -euo pipefail
umask 077
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
root=$PWD
prefix=/usr/local
stage=${DESTDIR:-}
release=${KERNEL_RELEASE:-$(uname -r)}
kdir=${KDIR:-/lib/modules/$release/build}
cc=${CC:-cc}
ar=${AR:-ar}
manifest=/var/lib/decnet-iv-linux/manifest

fail() { printf 'install: %s\n' "$*" >&2; exit 1; }
need() { command -v "$1" >/dev/null || fail "missing command: $1"; }
valid_path() {
    [[ $1 == /* && $1 != / && $1 != *[[:space:]]* && $1 != *'//'*
       && $1 != *'/../'* && $1 != */.. && $1 != *'/./'* && $1 != */. ]]
}
valid_address() {
    [[ $1 =~ ^([0-9]{1,2})\.([0-9]{1,4})$ ]] || return 1
    local a=$((10#${BASH_REMATCH[1]})) n=$((10#${BASH_REMATCH[2]}))
    ((a>=1 && a<=63 && n>=1 && n<=1023))
}
valid_name() { [[ $1 =~ ^[A-Za-z][A-Za-z0-9]{0,5}$ ]]; }
# Read actual terminal bytes rather than Bash's `read`, which silently drops NULs.
# Reject control bytes, oversized answers and non-ASCII input before validation.
# Return 2 for a rejected line; EOF and a missing TTY terminate installation.
tty_answer() {
    local reply
    printf '%s\n' "$1" >&"${DNIV_TTY[1]}" || fail 'terminal prompt transport failed'
    IFS= read -r reply <&"${DNIV_TTY[0]}" || fail 'terminal input required (EOF or interrupt)'
    case $reply in
        OK:*) REPLY=${reply#OK:}; return 0;;
        BAD) return 2;;
        *) fail 'terminal input required (EOF or interrupted)' ;;
    esac
}

ask() {
    local reply
    while :; do
        tty_answer "$1" || continue
        reply=$REPLY
        if "$2" "$reply"; then REPLY=$reply; return; fi
        printf 'Invalid answer; please try again.\n' >&2
    done
}
yes_no() {
    local reply
    while :; do
        tty_answer "$1" || continue
        reply=$REPLY
        case "${reply,,}" in y|yes) REPLY=y; return;; n|no|'') REPLY=n; return;; esac
        echo 'Enter y or n.' >&2
    done
}
valid_user() {
    [[ $1 =~ ^[a-z_][a-z0-9_-]*$ ]] || return 1
    local uid
    uid=$(id -u "$1" 2>/dev/null) || return 1
    (( uid > 0 ))
}
valid_data_path() {
    valid_path "$1" && [[ $1 =~ ^/(var|srv|opt|home)/[a-zA-Z0-9_./+-]+$ && $1 != */ ]]
}
# Reject symlinked path parents: DESTDIR must never redirect into host paths.
# A live /lib -> /usr/lib link is the one expected merged-/usr exception.
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

[[ -z $stage ]] || valid_path "$stage" || fail 'DESTDIR must be an absolute, normalized non-root path'
if [[ -n $stage ]]; then
    check_parents "$stage/_check" || fail 'symlink or non-directory in DESTDIR path'
    [[ ! -L $stage && ( ! -e $stage || -d $stage ) ]] || fail 'unsafe DESTDIR'
fi
[[ $release =~ ^[A-Za-z0-9._+-]+$ && $release != . && $release != .. ]] || fail 'invalid kernel release'
[[ -r $kdir/Makefile ]] || fail "matching kernel headers not found: $kdir"
version=$(make -s -C "$kdir" kernelversion)
[[ $(printf '%s\n6.8\n' "$version" | sort -V | head -1) == 6.8 ]] || fail 'Linux kernel 6.8+ required'
# The external module build must use a compiler compatible with the selected kernel.
if [[ -r $kdir/include/config/auto.conf ]]; then
    if [[ "${LLVM:-0}" == 1 ]]; then
        grep -Fxq 'CONFIG_CC_IS_GCC=y' "$kdir/include/config/auto.conf" && fail 'GCC-built kernel; LLVM mismatch'
    else
        grep -Fxq 'CONFIG_CC_IS_CLANG=y' "$kdir/include/config/auto.conf" && fail 'Clang-built kernel; set CC=clang LLVM=1'
    fi
fi
[[ -r LICENSE && -r kernel/decnet/Makefile && -r include/uapi/linux/dn.h && -r userspace/dnctl/dnctl.c ]] || fail 'run this from the complete minimal source ZIP'
[[ -n $stage || $EUID == 0 ]] || fail 'run sudo ./install.sh, or set DESTDIR for staging'
for prog in make "$cc" "$ar" install sha256sum cut ln modinfo sort head grep cat; do need "$prog"; done
compiler_major=$($cc -dumpfullversion -dumpversion 2>/dev/null | cut -d. -f1)
[[ $compiler_major =~ ^[0-9]+$ ]] || fail 'cannot identify compiler version'
compiler_line=$("$cc" --version | head -1 || true)
if [[ ${compiler_line,,} == *clang* ]]; then
    ((compiler_major>=16)) || fail 'Clang 16+ required'
    [[ ${LLVM:-0} == 1 ]] || fail 'Clang kernel builds require LLVM=1'
else
    ((compiler_major>=12)) || fail 'GCC 12+ required'
    [[ ${LLVM:-0} != 1 ]] || fail 'LLVM=1 requires CC=clang'
fi
[[ $(uname -m) == x86_64 || $(uname -m) == aarch64 ]] || fail 'supported CPUs: x86_64 or aarch64'
if command -v python3 >/dev/null; then
    python3 -c 'import sys;sys.exit(sys.version_info<(3,10))' || fail 'Python 3.10+ needed for dnmultinet'
else fail 'Python 3.10+ required'; fi
# Keep one terminal reader alive for the entire questionnaire. It reads
# byte-for-byte from the controlling TTY and rejects NUL/control input.
# Python 3 is already a required production dependency for dnmultinet.
tty_reader_code=$(cat <<'PYTTY'
import os
import signal
import sys
# Background coprocesses may inherit SIGINT ignored from Bash.
# Restore Ctrl-C handling so the parent never hangs waiting for a reply.
signal.signal(signal.SIGINT, signal.default_int_handler)
try:
    with open('/dev/tty', 'rb', buffering=0) as tty:
        for prompt in sys.stdin.buffer:
            os.write(2, prompt.rstrip(b'\n'))
            buf = bytearray()
            invalid = False
            while True:
                ch = tty.read(1)
                if not ch:
                    sys.stdout.buffer.write(b'EOF\n')
                    sys.stdout.buffer.flush()
                    raise SystemExit(3)
                if ch in (b'\n', b'\r'):
                    break
                if ch[0] < 32 or ch[0] > 126 or len(buf) >= 255:
                    invalid = True
                elif not invalid:
                    buf.extend(ch)
            if invalid:
                print('Invalid terminal input (control, non-ASCII or too long).', file=sys.stderr)
                sys.stdout.buffer.write(b'BAD\n')
            else:
                sys.stdout.buffer.write(b'OK:' + bytes(buf) + b'\n')
            sys.stdout.buffer.flush()
except OSError as exc:
    print(f'Could not read terminal: {exc}', file=sys.stderr)
    sys.stdout.buffer.write(b'EOF\n')
    sys.stdout.buffer.flush()
    raise SystemExit(3)
PYTTY
)
if [[ -z $stage ]]; then
    need modprobe; need depmod
    [[ ! -d /sys/module/decnet_iv ]] || fail 'DECnet module is already loaded; stop services and unload it before reinstalling'
fi
check_parents "$stage$manifest" || fail 'unsafe installation state path'
[[ ! -e "$stage$manifest" && ! -L "$stage$manifest" ]] || fail 'installation exists; uninstall before reinstalling'

coproc DNIV_TTY { python3 -u -c "$tty_reader_code"; }
tty_pid=$DNIV_TTY_PID
cleanup_tty() {
    [[ -z ${tty_pid:-} ]] || kill "$tty_pid" 2>/dev/null || true
}
trap cleanup_tty EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
trap 'exit 129' HUP
printf '\nDECnet-IV-Linux first-time configuration\n' 
ask 'Local DECnet address (AREA.NODE, e.g. 1.10): ' valid_address
address=$REPLY
area=${address%%.*}; node=${address#*.}
area=$((10#$area)); node=$((10#$node)); address=$area.$node
ask 'Local node name (1-6 letters/digits, beginning with a letter): ' valid_name
name=${REPLY^^}
while :; do
    tty_answer 'Primary Ethernet interface for the node database (optional; blank for none): ' || continue
    interface=$REPLY
    [[ -z $interface ]] && break
    if [[ $interface =~ ^[A-Za-z0-9_.:-]{1,15}$ && -d /sys/class/net/$interface ]] &&
       [[ $(cat "/sys/class/net/$interface/type") == 1 ]]; then
        break
    fi
    echo 'Interface must exist and be Ethernet (sysfs type 1).' >&2
done
while :; do
    tty_answer 'Node role: 1=L2 router, 2=L1 router, 3=endnode [2]: ' || continue
    role=$REPLY
    role=${role:-2}
    [[ $role =~ ^[123]$ ]] && break
    echo 'Choose 1, 2 or 3.' >&2
done
router_priority=64; hello_interval=10; ethernet_cost=4
yes_no 'Customize router priority, hello interval and circuit cost? [y/N]: '
if [[ $REPLY == y ]]; then
    while :; do
        tty_answer 'Router priority (0-127) [64]: ' || continue
        x=$REPLY
        x=${x:-64}; [[ $x =~ ^[0-9]{1,3}$ ]] && ((10#$x<=127)) && break
        echo 'Enter a number from 0 to 127.' >&2
    done
    router_priority=$((10#$x))
    while :; do
        tty_answer 'Hello interval in seconds (1-65535) [10]: ' || continue
        x=$REPLY
        x=${x:-10}; [[ $x =~ ^[0-9]{1,5}$ ]] && ((10#$x>=1 && 10#$x<=65535)) && break
        echo 'Enter a number from 1 to 65535.' >&2
    done
    hello_interval=$((10#$x))
    while :; do
        tty_answer 'Ethernet circuit cost (1-1022) [4]: ' || continue
        x=$REPLY
        x=${x:-4}; [[ $x =~ ^[0-9]{1,4}$ ]] && ((10#$x>=1 && 10#$x<=1022)) && break
        echo 'Enter a number from 1 to 1022.' >&2
    done
    ethernet_cost=$((10#$x))
fi
peers=()
peer_addresses=()
while :; do
    tty_answer 'Peer address (AREA.NODE; Enter if none/more): ' || continue
    peer=$REPLY
    [[ -n $peer ]] || break
    valid_address "$peer" || { echo 'Invalid address.' >&2; continue; }
    pa=${peer%%.*}; pn=${peer#*.}
    peer="$((10#$pa)).$((10#$pn))"
    [[ $peer != "$address" ]] || { echo 'That is your local node.' >&2; continue; }
    [[ " ${peer_addresses[*]} " != *" $peer "* ]] || { echo 'Duplicate peer address.' >&2; continue; }
    ask 'Peer name (1-6 letters/digits): ' valid_name
    peer_name=${REPLY^^}
    if [[ $peer_name == "$name" || " ${peers[*]} " == *" name $peer_name "* ]]; then
        echo 'Duplicate peer name.' >&2; continue
    fi
    peers+=("node $peer name $peer_name")
    peer_addresses+=("$peer")
done

yes_no 'Load the module and start this node automatically at boot? [y/N]: '
autostart=$REPLY
if [[ $autostart == y && -z $stage ]]; then
    [[ -d /run/systemd/system ]] || fail 'automatic boot loading needs systemd'
    [[ $release == "$(uname -r)" ]] || fail 'cannot automatically load a module for a different running kernel'
fi
services=()
for service in nml fal phone mail http; do
    yes_no "Configure DECnet $service server (network-facing)? [y/N]: "
    [[ $REPLY == y ]] && services+=("$service")
done
if ((${#services[@]})); then
    [[ -n $stage ]] || need systemctl
fi
for service in "${services[@]}"; do
    case $service in
        nml) ;; # Needs kernel control permissions; runs as root.
        fal|mail|http)
            while :; do
                ask "Existing/new $service data directory (under /var, /srv, /opt or /home): " valid_data_path
                dir=$REPLY
                if check_parents "$dir/_check" &&
                   [[ ( ! -e $dir || -d $dir ) && ! -L $dir ]]; then
                    break
                fi
                echo 'Path must be a directory, not a symlink.' >&2
            done
            ask "Unprivileged Unix account to run $service: " valid_user
            printf -v "${service}_dir" '%s' "$dir"
            printf -v "${service}_user" '%s' "$REPLY"
            ;;
        phone)
            ask 'Unix account for PHONE sessions: ' valid_user
            phone_user=$REPLY
            ;;
    esac
    if [[ $service == fal ]]; then
        echo 'Warning: FAL authentication is not configured; the chosen data root will be reachable by DECnet peers.'
        tty_answer 'Type OPEN-FAL to confirm intentional sharing: ' || fail 'FAL enablement cancelled'
        confirm=$REPLY
        [[ $confirm == OPEN-FAL ]] || fail 'FAL enablement cancelled'
    fi
    if [[ $service == mail ]]; then
        while :; do
            tty_answer 'MAIL-11 delivery: 1=local spool only, 2=sendmail, 3=SMTP [1]: ' || continue
            mail_mode=$REPLY
            mail_mode=${mail_mode:-1}
            [[ $mail_mode =~ ^[123]$ ]] && break
            echo 'Choose 1, 2 or 3.' >&2
        done
        case $mail_mode in
            2)
                while :; do
                    tty_answer 'Absolute path of sendmail-compatible executable: ' || continue
                    sendmail_bin=$REPLY
                    valid_path "$sendmail_bin" && [[ $sendmail_bin =~ ^/[a-zA-Z0-9_./+-]+$ ]] && [[ -x $sendmail_bin ]] && break
                    echo 'Must be an existing executable at an absolute path.' >&2
                done;;
            3)
                while :; do
                    tty_answer 'SMTP hostname or IPv4 address: ' || continue
                    smtp_host=$REPLY
                    [[ $smtp_host =~ ^[A-Za-z0-9][A-Za-z0-9.-]{0,252}$ && $smtp_host != *..* ]] && break
                    echo 'Invalid SMTP host.' >&2
                done
                while :; do
                    tty_answer 'SMTP TCP port [25]: ' || continue
                    smtp_port=$REPLY
                    smtp_port=${smtp_port:-25}
                    [[ $smtp_port =~ ^[0-9]{1,5}$ ]] && ((10#$smtp_port>=1 && 10#$smtp_port<=65535)) && break
                    echo 'Port must be 1-65535.' >&2
                done
                smtp_port=$((10#$smtp_port))
                while :; do
                    tty_answer 'SMTP envelope sender address: ' || continue
                    smtp_from=$REPLY
                    [[ $smtp_from =~ ^[A-Za-z0-9_.+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$ ]] && break
                    echo 'Enter a plain mailbox address (no spaces).' >&2
                done;;
        esac
    fi
done
printf '\nNode: %s (%s); role: %s; priority: %s; hello: %ss; cost: %s\n' \
    "$address" "$name" "$role" "$router_priority" "$hello_interval" "$ethernet_cost"
printf 'Named peers: %s; boot: %s; servers: %s\n' "${#peers[@]}" "$autostart" "${services[*]:-none}"
yes_no 'Proceed with build and installation? [y/N]: '
[[ $REPLY == y ]] || fail 'cancelled; no files installed'

# Fail before replacing any existing system file.
paths=("/lib/modules/$release/extra/decnet_iv.ko" /etc/decnet.conf /etc/dnetd.conf /etc/modprobe.d/decnet-iv-linux.conf)
for bin in dnctl dnetd dnfald dnnml dnphoned dnmaild dnhttpd dnmultinet; do paths+=("$prefix/sbin/$bin"); done
for bin in ncp dnlogin sethost dncopy dntype dndir dndel dnrename dnsubmit dnprint dntask dnnice dnmirror dnobject phone dnmail dnlynx dnping; do paths+=("$prefix/bin/$bin"); done
for lib in libdnet.a libdnet.so.1.0 libdnet.so.1 libdnet.so libdnet_daemon.a libdnet_daemon.so.1.0 libdnet_daemon.so.1 libdnet_daemon.so; do paths+=("$prefix/lib/$lib"); done
for hdr in netdnet/dn.h netdnet/dnetdb.h linux/dn.h linux/decnet_iv.h; do paths+=("$prefix/include/$hdr"); done
if [[ $autostart == y ]]; then
    paths+=(/etc/modules-load.d/decnet-iv-linux.conf)
fi
for service in "${services[@]}"; do paths+=("/etc/systemd/system/decnet-iv-$service.service"); done
for path in "${paths[@]}"; do
    check_parents "$stage$path" || fail "unsafe parent of install target: $stage$path"
    [[ ! -e "$stage$path" && ! -L "$stage$path" ]] || fail "existing file will not be overwritten: $stage$path"
done
# Existing data roots must be usable before the first installed file is written.
if [[ -z $stage ]]; then
    for service in "${services[@]}"; do
        case $service in
            fal|mail|http)
                v="${service}_dir"; u="${service}_user"
                if [[ -e ${!v} ]]; then
                    need runuser
                    check_parents "${!v}/_check" || fail "unsafe $service directory"
                    if [[ $service == http ]]; then
                        runuser -u "${!u}" -- test -r "${!v}" &&
                        runuser -u "${!u}" -- test -x "${!v}" || fail "$service account cannot read/traverse: ${!v}"
                    else
                        runuser -u "${!u}" -- test -w "${!v}" &&
                        runuser -u "${!u}" -- test -x "${!v}" || fail "$service account cannot write/traverse: ${!v}"
                    fi
                fi
                ;;
        esac
    done
fi

printf '\nBuilding user-space programs and kernel module...\n'
for work in out out/bin out/lib out/obj; do
    [[ ! -L $work && ( ! -e $work || -d $work ) ]] || fail "unsafe build path: $work"
done
mkdir -p out/bin out/lib out/obj
flags=(-O2 -Wall -Wextra -Werror -Iinclude/uapi -Iinclude -Iuserspace/libdnet/include)
while read -r src bin; do
    "$cc" "${flags[@]}" "userspace/$src" -o "out/bin/$bin"
done <<'SOURCES'
dnctl/dnctl.c dnctl
ncp/ncp.c ncp
dnlogin/dnlogin.c dnlogin
dncopy/dncopy.c dncopy
dntask/dntask.c dntask
dnfald/dnfald.c dnfald
dnnml/dnnml.c dnnml
dnnice/dnnice.c dnnice
dnmirror/dnmirror.c dnmirror
dnobject/dnobject.c dnobject
dnhttpd/dnhttpd.c dnhttpd
dnlynx/dnlynx.c dnlynx
dnphone/dnphoned.c dnphoned
dnphone/phone.c phone
dnmail/dnmail.c dnmail
dnmail/dnmaild.c dnmaild
dnetd/dnetd.c dnetd
SOURCES
for src in libdnet dnetdb compat daemon; do
    "$cc" "${flags[@]}" -std=c11 -fPIC -c "userspace/libdnet/$src.c" -o "out/obj/$src.o"
done
arobjs=(out/obj/libdnet.o out/obj/dnetdb.o out/obj/compat.o)
"$ar" rcs out/lib/libdnet.a "${arobjs[@]}"
"$cc" -shared -Wl,-soname,libdnet.so.1 -o out/lib/libdnet.so.1.0 "${arobjs[@]}"
"$ar" rcs out/lib/libdnet_daemon.a out/obj/daemon.o
"$cc" -shared -Wl,-soname,libdnet_daemon.so.1 -o out/lib/libdnet_daemon.so.1.0 out/obj/daemon.o
"$cc" "${flags[@]}" -std=c11 userspace/dnping/dnping.c out/lib/libdnet.a -o out/bin/dnping
kopts=(); [[ ${LLVM:-0} == 1 ]] && kopts+=(LLVM=1)
make -C "$kdir" M="$root/kernel/decnet" "CC=$cc" "${kopts[@]}" modules
[[ -s kernel/decnet/decnet_iv.ko ]] || fail 'module build missing'
vermagic=$(modinfo -F vermagic kernel/decnet/decnet_iv.ko)
[[ ${vermagic%% *} == "$release" ]] || fail 'module kernel release mismatch'

# All records in the manifest identify only files created by this invocation.
# On a failed or interrupted install, use the checked uninstaller to undo
# recorded files.  Successful installs leave their manifest in place.
created_data_dirs=()
rollback_incomplete() {
    local rc=$?
    trap - EXIT
    cleanup_tty
    if (( rc != 0 )); then
        echo 'install: rolling back incomplete installation' >&2
        if [[ -f $stage$manifest && ! -L $stage$manifest ]]; then
            if ! DESTDIR="$stage" bash "$root/uninstall.sh" >&2; then
                echo 'install: rollback incomplete; inspect the installation manifest before retrying' >&2
            fi
        fi
        local dir
        for dir in "${created_data_dirs[@]}"; do
            rmdir -- "$dir" 2>/dev/null || true
        done
    fi
    exit "$rc"
}
mkdir -p "$stage$(dirname "$manifest")"
( set -C; : >"$stage$manifest" ) || fail 'cannot safely create install manifest'
trap rollback_incomplete EXIT
chmod 600 "$stage$manifest"
record_file() { printf 'F|%s|%s\n' "$(sha256sum "$1" | cut -d' ' -f1)" "$2" >>"$stage$manifest"; }
put() {
    local src=$1 dst=$2 mode=${3:-755}
    check_parents "$stage$dst" || fail "unsafe parent: $dst"
    [[ ! -e $stage$dst && ! -L $stage$dst ]] || fail "unexpected target exists: $dst"
    mkdir -p "$stage$(dirname "$dst")"
    # Record first, so interrupted installs can be cleaned with uninstall.sh.
    record_file "$src" "$dst"
    install -m "$mode" -- "$src" "$stage$dst"
}
put_text() {
    local dest=$1 content=$2 mode=${3:-644} tmp
    tmp=$(mktemp) || fail 'cannot create temporary configuration file'
    printf '%s\n' "$content" >"$tmp"
    put "$tmp" "$dest" "$mode"
    rm -f -- "$tmp"
}
link_to() {
    local target=$1 dest=$2
    check_parents "$stage$dest" || fail "unsafe symlink parent: $dest"
    [[ ! -e $stage$dest && ! -L $stage$dest ]] || fail "unexpected link target exists: $dest"
    mkdir -p "$stage$(dirname "$dest")"
    printf 'L|%s|%s\n' "$target" "$dest" >>"$stage$manifest"
    ln -s -- "$target" "$stage$dest"
}
put kernel/decnet/decnet_iv.ko "/lib/modules/$release/extra/decnet_iv.ko" 644
for bin in dnctl dnetd dnfald dnnml dnphoned dnmaild dnhttpd; do put "out/bin/$bin" "$prefix/sbin/$bin"; done
put userspace/dnmultinet/dnmultinet.py "$prefix/sbin/dnmultinet"
for bin in ncp dnlogin dncopy dntask dnnice dnmirror dnobject phone dnmail dnlynx dnping; do put "out/bin/$bin" "$prefix/bin/$bin"; done
link_to dnlogin "$prefix/bin/sethost"
for bin in dntype dndir dndel dnrename dnsubmit dnprint; do link_to dncopy "$prefix/bin/$bin"; done
for lib in libdnet libdnet_daemon; do
    put "out/lib/$lib.a" "$prefix/lib/$lib.a" 644
    put "out/lib/$lib.so.1.0" "$prefix/lib/$lib.so.1.0" 755
    link_to "$lib.so.1.0" "$prefix/lib/$lib.so.1"
    link_to "$lib.so.1" "$prefix/lib/$lib.so"
done
put userspace/libdnet/include/netdnet/dn.h "$prefix/include/netdnet/dn.h" 644
put userspace/libdnet/include/netdnet/dnetdb.h "$prefix/include/netdnet/dnetdb.h" 644
put include/uapi/linux/dn.h "$prefix/include/linux/dn.h" 644
put include/uapi/linux/decnet_iv.h "$prefix/include/linux/decnet_iv.h" 644
node_config="executor $address name $name"
[[ -z $interface ]] || node_config+=" line $interface"
for peer in "${peers[@]}"; do node_config+=$'\n'"$peer"; done
put_text /etc/decnet.conf "$node_config"
put_text /etc/dnetd.conf '# No custom objects configured. dnetd is not started automatically.'
put_text /etc/modprobe.d/decnet-iv-linux.conf \
    "options decnet_iv default_area=$area default_node=$node default_name=$name default_node_type=$role router_priority=$router_priority hello_interval=$hello_interval ethernet_cost=$ethernet_cost"
if [[ $autostart == y ]]; then
    put_text /etc/modules-load.d/decnet-iv-linux.conf 'decnet_iv'
fi
for service in "${services[@]}"; do
    case $service in
        nml) exe=dnnml; args=''; user=root;;
        fal) exe=dnfald; args="--root $fal_dir"; user=$fal_user;;
        phone) exe=dnphoned; args="--user $phone_user"; user=$phone_user;;
        mail)
            exe=dnmaild; args="--root $mail_dir"; user=$mail_user
            case $mail_mode in
                2) args+=" --sendmail $sendmail_bin";;
                3) args+=" --smtp $smtp_host --smtp-port $smtp_port --smtp-from $smtp_from";;
            esac;;
        http) exe=dnhttpd; args="--root $http_dir"; user=$http_user;;
    esac
    unit="[Unit]
Description=DECnet-IV-Linux $service service
After=systemd-modules-load.service
Wants=systemd-modules-load.service
[Service]
Type=simple
User=$user
ExecStart=$prefix/sbin/$exe $args
Restart=on-failure
[Install]
WantedBy=multi-user.target"
    put_text "/etc/systemd/system/decnet-iv-$service.service" "$unit"
done

if [[ -z $stage ]]; then
    for service in "${services[@]}"; do
        case $service in fal|mail|http)
            v="${service}_dir"; u="${service}_user"
            if [[ -e ${!v} ]]; then
                [[ -d ${!v} && ! -L ${!v} ]] || fail "unsafe $service data directory: ${!v}"
                command -v runuser >/dev/null || fail 'runuser needed to verify service directories'
                if [[ $service == http ]]; then
                    runuser -u "${!u}" -- test -r "${!v}" || fail "$service account cannot read: ${!v}"
                    runuser -u "${!u}" -- test -x "${!v}" || fail "$service account cannot traverse: ${!v}"
                else
                    runuser -u "${!u}" -- test -w "${!v}" || fail "$service account cannot write: ${!v}"
                fi
            else
                install -d -m 0750 -o "${!u}" -g "$(id -gn "${!u}")" -- "${!v}"
                created_data_dirs+=("${!v}")
            fi
            if [[ $service == fal ]]; then
                runuser -u "${!u}" -- python3 - "${!v}" <<'PYFAL' || fail 'FAL directory lacks O_TMPFILE or user extended-attribute support'
import os, sys
fd = os.open(sys.argv[1], os.O_RDWR | os.O_TMPFILE, 0o600)
try:
    os.setxattr(fd, "user.decnet.setup-check", b"1")
finally:
    os.close(fd)
PYFAL
            fi
            ;; esac
    done
    depmod -a "$release"
    if command -v ldconfig >/dev/null; then ldconfig; fi
    if [[ $autostart == y ]]; then
        modprobe decnet_iv || fail 'module load failed (check kernel signatures and dmesg)'
        if ((${#services[@]})); then
            systemctl daemon-reload
            for service in "${services[@]}"; do systemctl enable --now "decnet-iv-$service.service"; done
        fi
        identity=$($prefix/sbin/dnctl show)
        grep -Fxq "Executor node = $address ($name)" <<<"$identity" || fail "loaded node identity does not match configuration: $identity"
        echo "$identity"
    else
        echo "To start manually: modprobe decnet_iv (node identity is set by /etc/modprobe.d/decnet-iv-linux.conf)"
        if ((${#services[@]})); then
            echo "Configured servers are not running. Start selected units with: systemctl start decnet-iv-SERVICE.service"
        fi
    fi
else
    echo "Staged installation at $stage; no host configuration or services started."
fi
echo 'DECnet-IV-Linux build, install and initial configuration complete.'
