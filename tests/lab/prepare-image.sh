#!/bin/sh
set -eu

if [ "$#" -ne 5 ]; then
    echo "usage: $0 BASE-IMAGE OUTPUT-IMAGE AREA.NODE NAME PEER-MAC" >&2
    exit 2
fi

base=$1
out=$2
node_addr=$3
node_name=$4
peer_mac=$5
repo_root=$(CDPATH= cd -- "$(dirname "$0")/../.." && pwd)
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT INT TERM

cp --reflink=auto "$base" "$out"

tar -C "$repo_root" \
    --exclude=.git \
    --exclude='*.qcow2' \
    --exclude='tests/lab/artifacts' \
    -czf "$tmp/source.tgz" .

cat >"$tmp/decnet-lab.env" <<EOF_ENV
NODE_ADDR=${node_addr}
NODE_NAME=${node_name}
PEER_MAC=${peer_mac}
IFACE=eth0
EOF_ENV

# Build against the same Alpine linux-virt package that the guest will boot.
# Build-only packages are removed after installing the module and tiny test tools.
LIBGUESTFS_BACKEND=direct virt-customize -a "$out" --network \
    --upload "$tmp/source.tgz:/tmp/decnet-source.tgz" \
    --upload "$tmp/decnet-lab.env:/etc/decnet-lab.env" \
    --upload "$repo_root/tests/lab/decnet-lab.start:/etc/local.d/decnet-lab.start" \
    --run-command 'apk update' \
    --run-command 'apk add --no-cache linux-virt kmod' \
    --run-command 'apk add --no-cache --virtual .dniv-build build-base linux-virt-dev' \
    --run-command 'mkdir -p /opt/decnet-src && tar -xzf /tmp/decnet-source.tgz -C /opt/decnet-src' \
    --run-command 'kmoddir=$(find /lib/modules -mindepth 1 -maxdepth 1 -type d -name "*-virt" | head -1); test -n "$kmoddir"; test -d "$kmoddir/build"; make -C /opt/decnet-src/kernel/decnet KDIR="$kmoddir/build"' \
    --run-command 'cc -O2 -Wall -Wextra -Werror -I/opt/decnet-src/include/uapi -o /usr/local/sbin/dnctl /opt/decnet-src/userspace/dnctl/dnctl.c' \
    --run-command 'cc -O2 -Wall -Wextra -Werror -o /usr/local/sbin/dnraw /opt/decnet-src/tests/lab/dnraw.c' \
    --run-command 'kmoddir=$(find /lib/modules -mindepth 1 -maxdepth 1 -type d -name "*-virt" | head -1); install -Dm644 /opt/decnet-src/kernel/decnet/decnet_iv.ko "$kmoddir/extra/decnet_iv.ko"; depmod -a "$(basename "$kmoddir")"' \
    --run-command 'chmod 0755 /etc/local.d/decnet-lab.start' \
    --run-command 'rc-update add local default' \
    --run-command 'apk del .dniv-build && rm -rf /opt/decnet-src /tmp/decnet-source.tgz /var/cache/apk/*'
