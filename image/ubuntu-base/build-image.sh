#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 4 ]]; then
    echo "usage: $0 ARCH BASE-TARBALL OUTPUT-QCOW2 BOOT-DIR" >&2
    exit 2
fi

arch=$1
base_tar=$2
output=$3
boot_dir=$4
case "$arch" in
    amd64|arm64) ;;
    *) echo "build-image: unsupported architecture: $arch" >&2; exit 2 ;;
esac

script_dir=$(cd "$(dirname "$0")" && pwd)
repo_root=$(cd "$script_dir/../.." && pwd)
# shellcheck disable=SC1091
. "$script_dir/images.env"
snapshot=${UBUNTU_APT_SNAPSHOT:?images.env must pin UBUNTU_APT_SNAPSHOT}
disk_bytes=${DNIV_DISK_BYTES:-2147483648}
if [[ ! "$disk_bytes" =~ ^[0-9]+$ ]] || (( disk_bytes < 1073741824 )); then
    echo "build-image: DNIV_DISK_BYTES must be an integer >= 1073741824" >&2
    exit 2
fi
if [[ ! -f "$base_tar" ]]; then
    echo "build-image: base tarball not found: $base_tar" >&2
    exit 2
fi

work=$(mktemp -d)
raw="$work/root.raw"
mnt="$work/root"
mkdir -p "$mnt" "$boot_dir" "$(dirname "$output")"

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

truncate -s "$disk_bytes" "$raw"
mkfs.ext4 -q -F -L dniv-root "$raw"
sudo mount -o loop "$raw" "$mnt"
mounted=1
sudo tar --numeric-owner --xattrs --acls -xpf "$base_tar" -C "$mnt"

sudo mkdir -p "$mnt/usr/src/decnet-iv-linux" "$mnt/usr/local/sbin" \
    "$mnt/etc/systemd/system/multi-user.target.wants"
sudo tar -C "$repo_root" --exclude=.git --exclude=out -cf - . | \
    sudo tar -C "$mnt/usr/src/decnet-iv-linux" -xf -

sudo cp -L /etc/resolv.conf "$mnt/etc/resolv.conf"
printf 'LABEL=dniv-root / ext4 defaults 0 1\n' | sudo tee "$mnt/etc/fstab" >/dev/null
printf 'dniv\n' | sudo tee "$mnt/etc/hostname" >/dev/null

sudo mount -t proc proc "$mnt/proc"
sudo mount -t sysfs sysfs "$mnt/sys"
sudo mount --rbind /dev "$mnt/dev"
sudo mount --make-rslave "$mnt/dev"
chroot_mounted=1

sudo tee "$mnt/usr/sbin/policy-rc.d" >/dev/null <<'EOF_POLICY'
#!/bin/sh
exit 101
EOF_POLICY
sudo chmod 0755 "$mnt/usr/sbin/policy-rc.d"

sudo chroot "$mnt" /usr/bin/env UBUNTU_APT_SNAPSHOT="$snapshot" /bin/bash -euxc '
export DEBIAN_FRONTEND=noninteractive
apt-get --snapshot "$UBUNTU_APT_SNAPSHOT" update
apt-get --snapshot "$UBUNTU_APT_SNAPSHOT" install -y --no-install-recommends \
    systemd-sysv kmod iproute2 ca-certificates build-essential \
    linux-image-virtual-hwe-26.04 linux-headers-virtual-hwe-26.04
krel=$(ls -1 /lib/modules | sort -V | tail -1)
test -n "$krel"
make -C /usr/src/decnet-iv-linux/userspace/dnctl clean all
install -m 0755 /usr/src/decnet-iv-linux/userspace/dnctl/dnctl /usr/local/sbin/dnctl
cc -O2 -std=c11 -Wall -Wextra -Werror \
    -o /usr/local/sbin/dnraw /usr/src/decnet-iv-linux/tests/lab/dnraw.c
make -C /usr/src/decnet-iv-linux/kernel/decnet KDIR="/lib/modules/$krel/build" clean all
install -D -m 0644 /usr/src/decnet-iv-linux/kernel/decnet/decnet_iv.ko \
    "/lib/modules/$krel/extra/decnet_iv.ko"
depmod "$krel"
apt-get purge -y build-essential linux-headers-virtual-hwe-26.04 || true
apt-get autoremove -y --purge || true
apt-get clean
rm -rf /var/lib/apt/lists/*
rm -f /usr/sbin/policy-rc.d
'

sudo install -m 0755 "$repo_root/tests/lab/dniv-smoke.sh" "$mnt/usr/local/sbin/dniv-smoke"
sudo install -m 0644 "$repo_root/tests/lab/dniv-smoke.service" \
    "$mnt/etc/systemd/system/dniv-smoke.service"
sudo ln -sf ../dniv-smoke.service \
    "$mnt/etc/systemd/system/multi-user.target.wants/dniv-smoke.service"

kernel=$(find "$mnt/boot" -maxdepth 1 -type f -name 'vmlinuz-*' | sort -V | tail -1)
initrd=$(find "$mnt/boot" -maxdepth 1 -type f -name 'initrd.img-*' | sort -V | tail -1)
if [[ -z "$kernel" || -z "$initrd" ]]; then
    echo "build-image: installed kernel or initrd not found" >&2
    exit 1
fi
sudo cp "$kernel" "$boot_dir/vmlinuz"
sudo cp "$initrd" "$boot_dir/initrd.img"
sudo chown "$(id -u):$(id -g)" "$boot_dir/vmlinuz" "$boot_dir/initrd.img"

sudo umount -R "$mnt/dev"
sudo umount "$mnt/sys"
sudo umount "$mnt/proc"
chroot_mounted=0
sudo umount "$mnt"
mounted=0

qemu-img convert -f raw -O qcow2 -c "$raw" "$output"
qemu-img info "$output"
echo "build-image: created $output with direct-boot kernel artifacts in $boot_dir"
