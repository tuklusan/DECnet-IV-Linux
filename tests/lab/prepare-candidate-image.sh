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

if [[ $# -ne 2 ]]; then
    echo "usage: $0 FOUNDATION-QCOW2 OUTPUT-QCOW2" >&2
    exit 2
fi
foundation=$1
output=$2
[[ -r "$foundation" ]] || { echo "prepare-candidate-image: missing $foundation" >&2; exit 2; }

script_dir=$(cd "$(dirname "$0")" && pwd)
repo_root=$(cd "$script_dir/../.." && pwd)
source_commit=$(git -C "$repo_root" rev-parse --verify 'HEAD^{commit}')
[[ "$source_commit" =~ ^[0-9a-f]{40}$ ]] || {
    echo "prepare-candidate-image: invalid source commit" >&2
    exit 1
}

work=$(mktemp -d)
raw="$work/candidate.raw"
mnt="$work/root"
mkdir -p "$mnt" "$(dirname "$output")"
mounted=0
chroot_mounted=0
cleanup() {
    set +e
    if (( chroot_mounted )); then
        sudo umount -R "$mnt/dev" 2>/dev/null || true
        sudo umount "$mnt/sys" 2>/dev/null || true
        sudo umount "$mnt/proc" 2>/dev/null || true
    fi
    if (( mounted )); then
        sudo umount "$mnt" 2>/dev/null || true
    fi
    rm -rf "$work"
}
trap cleanup EXIT INT TERM

normalize_ext4() {
    local image=$1 rc
    sync
    set +e
    sudo e2fsck -fy "$image"
    rc=$?
    set -e
    if (( rc > 1 )); then
        echo "prepare-candidate-image: ext4 normalization failed with status $rc" >&2
        return "$rc"
    fi
}

qemu-img convert -q -f qcow2 -O raw "$foundation" "$raw"
sudo mount -o loop "$raw" "$mnt"
mounted=1

sudo rm -rf "$mnt/usr/src/decnet-iv-linux"
sudo mkdir -p "$mnt/usr/src/decnet-iv-linux" "$mnt/usr/local/sbin" \
    "$mnt/etc/systemd/system/multi-user.target.wants"
git -C "$repo_root" archive --format=tar "$source_commit" | \
    sudo tar -C "$mnt/usr/src/decnet-iv-linux" -xf -
printf '%s\n' "$source_commit" | \
    sudo tee "$mnt/usr/src/decnet-iv-linux/.source-commit" >/dev/null

sudo mount -t proc proc "$mnt/proc"
sudo mount -t sysfs sysfs "$mnt/sys"
sudo mount --rbind /dev "$mnt/dev"
sudo mount --make-rslave "$mnt/dev"
chroot_mounted=1
sudo chroot "$mnt" /bin/bash -euxc '
source_commit=$(cat /usr/src/decnet-iv-linux/.source-commit)
krel=$(ls -1 /lib/modules | sort -V | tail -1)
test -n "$krel"
test -d "/lib/modules/$krel/build"
make -C /usr/src/decnet-iv-linux/userspace/dnctl clean all
install -m 0755 /usr/src/decnet-iv-linux/userspace/dnctl/dnctl /usr/local/sbin/dnctl
make -C /usr/src/decnet-iv-linux/userspace/ncp clean all
install -m 0755 /usr/src/decnet-iv-linux/userspace/ncp/ncp /usr/local/sbin/ncp
make -C /usr/src/decnet-iv-linux/userspace/dnlogin clean all
install -m 0755 /usr/src/decnet-iv-linux/userspace/dnlogin/dnlogin /usr/local/sbin/dnlogin
ln -sf ../sbin/dnlogin /usr/local/bin/sethost
make -C /usr/src/decnet-iv-linux/userspace/dncopy clean all
install -m 0755 /usr/src/decnet-iv-linux/userspace/dncopy/dncopy /usr/local/bin/dncopy
ln -sf dncopy /usr/local/bin/dntype
ln -sf dncopy /usr/local/bin/dndir
ln -sf dncopy /usr/local/bin/dndel
ln -sf dncopy /usr/local/bin/dnrename
ln -sf dncopy /usr/local/bin/dnsubmit
ln -sf dncopy /usr/local/bin/dnprint
make -C /usr/src/decnet-iv-linux/userspace/dntask clean all
install -m 0755 /usr/src/decnet-iv-linux/userspace/dntask/dntask /usr/local/bin/dntask
make -C /usr/src/decnet-iv-linux/userspace/dnfald clean all
install -m 0755 /usr/src/decnet-iv-linux/userspace/dnfald/dnfald /usr/local/sbin/dnfald
make -C /usr/src/decnet-iv-linux/userspace/dnnml clean all
install -m 0755 /usr/src/decnet-iv-linux/userspace/dnnml/dnnml /usr/local/sbin/dnnml
make -C /usr/src/decnet-iv-linux/userspace/dnnice clean all
install -m 0755 /usr/src/decnet-iv-linux/userspace/dnnice/dnnice /usr/local/sbin/dnnice
make -C /usr/src/decnet-iv-linux/userspace/dnmirror clean all
install -m 0755 /usr/src/decnet-iv-linux/userspace/dnmirror/dnmirror /usr/local/sbin/dnmirror
make -C /usr/src/decnet-iv-linux/userspace/dnobject clean all
install -m 0755 /usr/src/decnet-iv-linux/userspace/dnobject/dnobject /usr/local/sbin/dnobject
make -C /usr/src/decnet-iv-linux/userspace/dnhttpd clean all
install -m 0755 /usr/src/decnet-iv-linux/userspace/dnhttpd/dnhttpd /usr/local/sbin/dnhttpd
make -C /usr/src/decnet-iv-linux/userspace/dnphone clean all
install -m 0755 /usr/src/decnet-iv-linux/userspace/dnphone/dnphoned /usr/local/sbin/dnphoned
install -m 0755 /usr/src/decnet-iv-linux/userspace/dnphone/phone /usr/local/bin/phone
make -C /usr/src/decnet-iv-linux/userspace/dnmail clean all
install -m 0755 /usr/src/decnet-iv-linux/userspace/dnmail/dnmail /usr/local/bin/dnmail
install -m 0755 /usr/src/decnet-iv-linux/userspace/dnmail/dnmaild /usr/local/sbin/dnmaild
make -C /usr/src/decnet-iv-linux/userspace/libdnet clean all
install -d /usr/local/lib /usr/local/include/netdnet
install -m 0644 /usr/src/decnet-iv-linux/userspace/libdnet/libdnet.a /usr/local/lib/libdnet.a
install -m 0755 /usr/src/decnet-iv-linux/userspace/libdnet/libdnet.so.1.0 /usr/local/lib/libdnet.so.1.0
ln -sf libdnet.so.1.0 /usr/local/lib/libdnet.so.1
ln -sf libdnet.so.1 /usr/local/lib/libdnet.so
install -m 0644 /usr/src/decnet-iv-linux/userspace/libdnet/include/netdnet/dn.h /usr/local/include/netdnet/dn.h
install -m 0644 /usr/src/decnet-iv-linux/userspace/libdnet/include/netdnet/dnetdb.h /usr/local/include/netdnet/dnetdb.h
cc -I/usr/src/decnet-iv-linux/userspace/libdnet/include \
    -I/usr/src/decnet-iv-linux/include/uapi -O2 -std=c11 -Wall -Wextra -Werror \
    -o /usr/local/sbin/dnetlib-mirror /usr/src/decnet-iv-linux/tests/lab/dnetlib-mirror.c \
    /usr/src/decnet-iv-linux/userspace/libdnet/libdnet.a
cc -O2 -std=c11 -Wall -Wextra -Werror \
    -o /usr/local/sbin/dnsmtpfake /usr/src/decnet-iv-linux/tests/lab/dnsmtpfake.c
cc -O2 -std=c11 -Wall -Wextra -Werror \
    -o /usr/local/sbin/dnraw /usr/src/decnet-iv-linux/tests/lab/dnraw.c
cc -I/usr/src/decnet-iv-linux/include/uapi -O2 -std=c11 -Wall -Wextra -Werror \
    -o /usr/local/sbin/dnmrr /usr/src/decnet-iv-linux/tests/lab/dnmrr.c
cc -I/usr/src/decnet-iv-linux/include/uapi -O2 -std=c11 -Wall -Wextra -Werror \
    -o /usr/local/sbin/dnloss /usr/src/decnet-iv-linux/tests/lab/dnloss.c
cc -I/usr/src/decnet-iv-linux/include/uapi -O2 -std=c11 -Wall -Wextra -Werror \
    -o /usr/local/sbin/dndrain /usr/src/decnet-iv-linux/tests/lab/dndrain.c
cc -I/usr/src/decnet-iv-linux/include/uapi -O2 -std=c11 -Wall -Wextra -Werror \
    -o /usr/local/sbin/dnflow /usr/src/decnet-iv-linux/tests/lab/dnflow.c
cc -I/usr/src/decnet-iv-linux/include/uapi -O2 -std=c11 -Wall -Wextra -Werror \
    -o /usr/local/sbin/dnackrange /usr/src/decnet-iv-linux/tests/lab/dnackrange.c
cc -I/usr/src/decnet-iv-linux/include/uapi -O2 -std=c11 -Wall -Wextra -Werror \
    -o /usr/local/sbin/dnseqwrap /usr/src/decnet-iv-linux/tests/lab/dnseqwrap.c
cc -I/usr/src/decnet-iv-linux/include/uapi -O2 -std=c11 -Wall -Wextra -Werror \
    -o /usr/local/sbin/dnintloss /usr/src/decnet-iv-linux/tests/lab/dnintloss.c
cc -I/usr/src/decnet-iv-linux/include/uapi -O2 -std=c11 -Wall -Wextra -Werror \
    -o /usr/local/sbin/dnintflow /usr/src/decnet-iv-linux/tests/lab/dnintflow.c
cc -I/usr/src/decnet-iv-linux/include/uapi -O2 -std=c11 -Wall -Wextra -Werror \
    -o /usr/local/sbin/dnccretry /usr/src/decnet-iv-linux/tests/lab/dnccretry.c
cc -I/usr/src/decnet-iv-linux/include/uapi -O2 -std=c11 -Wall -Wextra -Werror \
    -o /usr/local/sbin/dndiloss /usr/src/decnet-iv-linux/tests/lab/dndiloss.c
cc -I/usr/src/decnet-iv-linux/include/uapi -O2 -std=c11 -Wall -Wextra -Werror \
    -o /usr/local/sbin/dndiexhaust /usr/src/decnet-iv-linux/tests/lab/dndiexhaust.c
cc -I/usr/src/decnet-iv-linux/include/uapi -O2 -std=c11 -Wall -Wextra -Werror \
    -o /usr/local/sbin/dnkeepalive /usr/src/decnet-iv-linux/tests/lab/dnkeepalive.c
cc -I/usr/src/decnet-iv-linux/include/uapi -O2 -std=c11 -Wall -Wextra -Werror \
    -o /usr/local/sbin/dnwindow /usr/src/decnet-iv-linux/tests/lab/dnwindow.c
cc -I/usr/src/decnet-iv-linux/include/uapi -O2 -std=c11 -Wall -Wextra -Werror \
    -o /usr/local/sbin/dnexhaust /usr/src/decnet-iv-linux/tests/lab/dnexhaust.c
cc -I/usr/src/decnet-iv-linux/include/uapi -O2 -std=c11 -Wall -Wextra -Werror \
    -o /usr/local/sbin/dnconnectloss /usr/src/decnet-iv-linux/tests/lab/dnconnectloss.c
cc -I/usr/src/decnet-iv-linux/include/uapi -O2 -std=c11 -Wall -Wextra -Werror \
    -o /usr/local/sbin/dntimeout /usr/src/decnet-iv-linux/tests/lab/dntimeout.c
cc -I/usr/src/decnet-iv-linux/include/uapi -O2 -std=c11 -Wall -Wextra -Werror \
    -o /usr/local/sbin/dnaccept /usr/src/decnet-iv-linux/tests/lab/dnaccept.c
cc -I/usr/src/decnet-iv-linux/include/uapi -O2 -std=c11 -Wall -Wextra -Werror \
    -o /usr/local/sbin/dnstream /usr/src/decnet-iv-linux/tests/lab/dnstream.c
cc -I/usr/src/decnet-iv-linux/include/uapi -O2 -std=c11 -Wall -Wextra -Werror \
    -o /usr/local/sbin/dnsocklife /usr/src/decnet-iv-linux/tests/lab/dnsocklife.c
cc -I/usr/src/decnet-iv-linux/include/uapi -O2 -std=c11 -Wall -Wextra -Werror \
    -o /usr/local/sbin/dnsockstress /usr/src/decnet-iv-linux/tests/lab/dnsockstress.c
cc -I/usr/src/decnet-iv-linux/include/uapi -O2 -std=c11 -Wall -Wextra -Werror \
    -o /usr/local/sbin/dnsignal /usr/src/decnet-iv-linux/tests/lab/dnsignal.c
cc -I/usr/src/decnet-iv-linux/include/uapi -O2 -std=c11 -Wall -Wextra -Werror \
    -o /usr/local/sbin/dnfair /usr/src/decnet-iv-linux/tests/lab/dnfair.c
cc -I/usr/src/decnet-iv-linux/include/uapi -O2 -std=c11 -Wall -Wextra -Werror \
    -o /usr/local/sbin/dnbacklog /usr/src/decnet-iv-linux/tests/lab/dnbacklog.c
cc -I/usr/src/decnet-iv-linux/include/uapi -O2 -std=c11 -Wall -Wextra -Werror \
    -o /usr/local/sbin/dnreset /usr/src/decnet-iv-linux/tests/lab/dnreset.c
cc -I/usr/src/decnet-iv-linux/include/uapi -O2 -std=c11 -Wall -Wextra -Werror \
    -o /usr/local/sbin/dntermrace /usr/src/decnet-iv-linux/tests/lab/dntermrace.c
make -C /usr/src/decnet-iv-linux/kernel/decnet KDIR="/lib/modules/$krel/build" clean all
install -D -m 0644 /usr/src/decnet-iv-linux/kernel/decnet/decnet_iv.ko \
    "/lib/modules/$krel/extra/decnet_iv.ko"
depmod "$krel"
printf "%s\n" "$source_commit" > /etc/dniv-candidate-sha
'

sudo install -m 0755 "$mnt/usr/src/decnet-iv-linux/tests/lab/dniv-smoke.sh" \
    "$mnt/usr/local/sbin/dniv-smoke"
sudo install -m 0644 "$mnt/usr/src/decnet-iv-linux/tests/lab/dniv-smoke.service" \
    "$mnt/etc/systemd/system/dniv-smoke.service"
sudo ln -sf ../dniv-smoke.service \
    "$mnt/etc/systemd/system/multi-user.target.wants/dniv-smoke.service"

sudo install -m 0755 "$mnt/usr/src/decnet-iv-linux/tests/lab/dniv-interop-smoke.sh" \
    "$mnt/usr/local/sbin/dniv-interop-smoke"
sudo tee "$mnt/etc/systemd/system/dniv-interop-smoke.service" >/dev/null <<'EOF_SERVICE'
[Unit]
Description=DECnet Phase IV independent-peer interoperability test
After=systemd-udev-settle.service
ConditionKernelCommandLine=dniv.interop=1

[Service]
Type=oneshot
ExecStart=/usr/local/sbin/dniv-interop-smoke
StandardOutput=journal+console
StandardError=journal+console

[Install]
WantedBy=multi-user.target
EOF_SERVICE
sudo ln -sf ../dniv-interop-smoke.service \
    "$mnt/etc/systemd/system/multi-user.target.wants/dniv-interop-smoke.service"

sudo test "$(sudo cat "$mnt/usr/src/decnet-iv-linux/.source-commit")" = "$source_commit"
sudo test "$(sudo cat "$mnt/etc/dniv-candidate-sha")" = "$source_commit"
sudo test -s "$mnt/usr/local/sbin/dnctl"
sudo test -s "$mnt/usr/local/sbin/ncp"
sudo test -s "$mnt/usr/local/sbin/dnlogin"
sudo test -L "$mnt/usr/local/bin/sethost"
sudo test -s "$mnt/usr/local/bin/dncopy"
sudo test -L "$mnt/usr/local/bin/dntype"
sudo test -L "$mnt/usr/local/bin/dndir"
sudo test -L "$mnt/usr/local/bin/dndel"
sudo test -L "$mnt/usr/local/bin/dnsubmit"
sudo test -L "$mnt/usr/local/bin/dnprint"
sudo test -s "$mnt/usr/local/bin/dntask"
sudo test -s "$mnt/usr/local/sbin/dnnml"
sudo test -s "$mnt/usr/local/sbin/dnnice"
sudo test -s "$mnt/usr/local/sbin/dnmirror"
sudo test -s "$mnt/usr/local/sbin/dnobject"
sudo test -s "$mnt/usr/local/sbin/dnraw"
sudo test -s "$mnt/usr/local/sbin/dnmrr"
sudo test -s "$mnt/usr/local/sbin/dnloss"
sudo test -s "$mnt/usr/local/sbin/dndrain"
sudo test -s "$mnt/usr/local/sbin/dnflow"
sudo test -s "$mnt/usr/local/sbin/dnackrange"
sudo test -s "$mnt/usr/local/sbin/dnseqwrap"
sudo test -s "$mnt/usr/local/sbin/dnintloss"
sudo test -s "$mnt/usr/local/sbin/dnintflow"
sudo test -s "$mnt/usr/local/sbin/dnccretry"
sudo test -s "$mnt/usr/local/sbin/dndiloss"
sudo test -s "$mnt/usr/local/sbin/dndiexhaust"
sudo test -s "$mnt/usr/local/sbin/dnkeepalive"
sudo test -s "$mnt/usr/local/sbin/dnwindow"
sudo test -s "$mnt/usr/local/sbin/dnexhaust"
sudo test -s "$mnt/usr/local/sbin/dnconnectloss"
sudo test -s "$mnt/usr/local/sbin/dntimeout"
sudo test -s "$mnt/usr/local/sbin/dnaccept"
sudo test -s "$mnt/usr/local/sbin/dnstream"
sudo test -s "$mnt/usr/local/sbin/dnsocklife"
sudo test -s "$mnt/usr/local/sbin/dnsockstress"
sudo test -s "$mnt/usr/local/sbin/dnsignal"
sudo test -s "$mnt/usr/local/sbin/dnfair"
sudo test -s "$mnt/usr/local/sbin/dnbacklog"
sudo test -s "$mnt/usr/local/sbin/dnreset"
sudo test -s "$mnt/usr/local/sbin/dntermrace"
sudo test -s "$mnt/usr/local/lib/libdnet.a"
sudo test -s "$mnt/usr/local/lib/libdnet.so.1.0"
sudo test -L "$mnt/usr/local/lib/libdnet.so.1"
sudo test -L "$mnt/usr/local/lib/libdnet.so"
sudo test -s "$mnt/usr/local/include/netdnet/dn.h"
sudo test -s "$mnt/usr/local/include/netdnet/dnetdb.h"
sudo test -s "$mnt/usr/local/sbin/dnetlib-mirror"
sudo test -s "$mnt/usr/local/sbin/dniv-smoke"
sudo test -s "$mnt/usr/local/sbin/dniv-interop-smoke"

sudo umount -R "$mnt/dev"
sudo umount "$mnt/sys"
sudo umount "$mnt/proc"
chroot_mounted=0
sudo umount "$mnt"
mounted=0
normalize_ext4 "$raw"

qemu-img convert -q -f raw -O qcow2 "$raw" "$output"
qemu-img check -q -f qcow2 "$output"
qemu-img compare -q -f raw -F qcow2 "$raw" "$output"
echo "prepare-candidate-image: created $output from exact source $source_commit"
