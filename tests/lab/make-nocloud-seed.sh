#!/bin/sh
set -eu

if [ "$#" -ne 7 ]; then
    echo "usage: $0 OUTPUT-ISO SESSION-ID AREA.NODE NAME LAN-MAC PEER-MAC MGMT-MAC" >&2
    exit 2
fi

out=$1
case "$out" in
    /*) ;;
    *) out="$(pwd)/$out" ;;
esac
session_id=$2
node_addr=$3
node_name=$4
lan_mac=$5
peer_mac=$6
mgmt_mac=$7
repo_root=$(CDPATH= cd -- "$(dirname "$0")/../.." && pwd)
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT INT TERM

case "$session_id" in
    *[!A-Za-z0-9._-]*|'')
        echo "invalid session id: $session_id" >&2
        exit 2
        ;;
esac

mkdir -p "$(dirname "$out")"

tar -C "$repo_root" \
    --exclude=.git \
    --exclude='*.qcow2' \
    --exclude='*.seed.iso' \
    --exclude='tests/lab/artifacts' \
    -czf "$tmp/source.tgz" .

cat >"$tmp/meta-data" <<EOF_META
instance-id: dniv-${session_id}-${node_name}
local-hostname: $(printf '%s' "$node_name" | tr '[:upper:]' '[:lower:]')
EOF_META

cat >"$tmp/user-data" <<'EOF_HEAD'
#!/bin/sh
set -eu
exec >/dev/ttyS0 2>&1

state=/var/lib/decnet-lab
mkdir -p "$state"

if [ -e "$state/provisioned" ]; then
    echo "DNIV-PROVISION already complete"
    exit 0
fi
EOF_HEAD

cat >>"$tmp/user-data" <<EOF_NODE
LAB_SESSION_ID='$session_id'
NODE_ADDR='$node_addr'
NODE_NAME='$node_name'
LAN_MAC='$lan_mac'
PEER_MAC='$peer_mac'
MGMT_MAC='$mgmt_mac'
EOF_NODE

cat >>"$tmp/user-data" <<'EOF_BODY'

find_iface_by_mac() {
    target=$(printf '%s' "$1" | tr '[:upper:]' '[:lower:]')
    for address_file in /sys/class/net/*/address; do
        [ -r "$address_file" ] || continue
        if [ "$(cat "$address_file")" = "$target" ]; then
            basename "$(dirname "$address_file")"
            return 0
        fi
    done
    return 1
}

echo "DNIV-PROVISION session=${LAB_SESSION_ID} node=${NODE_NAME} address=${NODE_ADDR} start"
mgmt_iface=$(find_iface_by_mac "$MGMT_MAC")
ip link set "$mgmt_iface" up
udhcpc -q -n -t 10 -i "$mgmt_iface"

apk update
apk add --no-cache linux-virt linux-virt-dev kmod akms build-base

src_root=/opt/decnet-src
rm -rf "$src_root"
mkdir -p "$src_root"

base64 -d "$state/source.tgz.b64" | tar -xzf - -C "$src_root"

akms_src=/usr/src/decnet_iv-0.1.0
rm -rf "$akms_src"
mkdir -p "$akms_src"
cp -R "$src_root/kernel" "$akms_src/"
cp -R "$src_root/include" "$akms_src/"
install -m 0644 "$src_root/packaging/akms/AKMBUILD" "$akms_src/AKMBUILD"
akms install "$akms_src"

cc -O2 -Wall -Wextra -Werror \
    -I"$src_root/include/uapi" \
    -o /usr/local/sbin/dnctl "$src_root/userspace/dnctl/dnctl.c"
cc -O2 -Wall -Wextra -Werror \
    -o /usr/local/sbin/dnraw "$src_root/tests/lab/dnraw.c"

install -m 0755 "$src_root/tests/lab/decnet-lab.start" /etc/local.d/decnet-lab.start
cat >/etc/decnet-lab.env <<EOF_ENV
LAB_SESSION_ID=${LAB_SESSION_ID}
NODE_ADDR=${NODE_ADDR}
NODE_NAME=${NODE_NAME}
LAN_MAC=${LAN_MAC}
PEER_MAC=${PEER_MAC}
EOF_ENV
rc-update add local default

# Future AKMS rebuilds install build requirements in a disposable overlay.
apk del build-base linux-virt-dev
rm -rf "$src_root"

touch "$state/provisioned"
sync
echo "DNIV-PROVISION session=${LAB_SESSION_ID} node=${NODE_NAME} complete; rebooting into installed kernel"
reboot -f
EOF_BODY

printf '%s\n' "cat >\"\$state/source.tgz.b64\" <<'EOF_SOURCE'" >>"$tmp/user-data"
base64 "$tmp/source.tgz" >>"$tmp/user-data"
printf '%s\n' 'EOF_SOURCE' >>"$tmp/user-data"

# The payload must exist before the provisioning body uses it. Move it just after
# the variable block while keeping the executable script readable in artifacts.
python3 - "$tmp/user-data" <<'EOF_PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
text = path.read_text()
marker = "\nfind_iface_by_mac() {\n"
payload_marker = "\ncat >\"$state/source.tgz.b64\" <<'EOF_SOURCE'\n"
payload = text.index(payload_marker)
payload_text = text[payload:]
text = text[:payload]
insert = text.index(marker)
text = text[:insert] + payload_text + "\n" + text[insert:]
path.write_text(text)
EOF_PY

(
    cd "$tmp"
    genisoimage -quiet -output "$out" -volid CIDATA -joliet -rock user-data meta-data
)

echo "nocloud seed: session=${session_id} node=${node_name} -> ${out}"
