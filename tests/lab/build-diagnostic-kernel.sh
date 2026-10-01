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

if [[ $# -ne 4 ]]; then
    echo "usage: $0 ARCH PROFILE BASE-CONFIG OUTPUT-DIR" >&2
    exit 2
fi

arch=$1
profile=$2
base_config=$3
output=$4

case "$arch" in
    amd64) karch=x86; image_target=bzImage; image_rel=arch/x86/boot/bzImage ;;
    arm64) karch=arm64; image_target=Image; image_rel=arch/arm64/boot/Image ;;
    *) echo "build-diagnostic-kernel: unsupported architecture: $arch" >&2; exit 2 ;;
esac
case "$profile" in
    kasan|kcsan|lockdebug) ;;
    *) echo "build-diagnostic-kernel: unsupported profile: $profile" >&2; exit 2 ;;
esac
[[ -r "$base_config" ]] || {
    echo "build-diagnostic-kernel: missing base config: $base_config" >&2
    exit 2
}

linux_repo=https://github.com/torvalds/linux.git
linux_commit=028ef9c96e96197026887c0f092424679298aae8
rm -rf "$output"
mkdir -p "$output/src" "$output/build"

git -C "$output/src" init -q
git -C "$output/src" remote add origin "$linux_repo"
git -C "$output/src" fetch --depth=1 origin "$linux_commit"
git -C "$output/src" checkout -q --detach FETCH_HEAD
test "$(git -C "$output/src" rev-parse HEAD)" = "$linux_commit"

# The exact source commit is verified above. Drop SCM metadata before invoking
# Kbuild so scripts/setlocalversion cannot append an environment-dependent '+'
# merely because the shallow pinned checkout does not contain the v7.0 tag.
rm -rf "$output/src/.git"

cp "$base_config" "$output/build/.config"
make -s -C "$output/src" O="$output/build" ARCH="$karch" olddefconfig

# This diagnostic kernel boots a fixed QEMU device set and loads only the
# candidate DECnet module. Drop inherited distro =m selections so a bounded
# in-tree modules pass can emit Module.symvers without compiling the distro's
# entire module catalog; required boot paths are forced built-in below.
sed -Ei 's/^(CONFIG_[A-Za-z0-9_]+)=m$/# \1 is not set/' "$output/build/.config"

config="$output/src/scripts/config"
"$config" --file "$output/build/.config" --set-str LOCALVERSION "-dniv-$profile"
"$config" --file "$output/build/.config" --disable LOCALVERSION_AUTO
"$config" --file "$output/build/.config" --disable MODVERSIONS
"$config" --file "$output/build/.config" --disable MODULE_SIG
"$config" --file "$output/build/.config" --disable MODULE_SIG_ALL
"$config" --file "$output/build/.config" --disable MODULE_SIG_FORCE
"$config" --file "$output/build/.config" --set-str SYSTEM_TRUSTED_KEYS ""
"$config" --file "$output/build/.config" --set-str SYSTEM_REVOCATION_KEYS ""
"$config" --file "$output/build/.config" --disable DEBUG_INFO
"$config" --file "$output/build/.config" --enable DEBUG_INFO_NONE
"$config" --file "$output/build/.config" --disable DEBUG_INFO_BTF
"$config" --file "$output/build/.config" --enable MODULES
"$config" --file "$output/build/.config" --enable MODULE_UNLOAD
"$config" --file "$output/build/.config" --enable DEVTMPFS
"$config" --file "$output/build/.config" --enable DEVTMPFS_MOUNT
"$config" --file "$output/build/.config" --enable BLK_DEV
"$config" --file "$output/build/.config" --enable PCI
"$config" --file "$output/build/.config" --enable VIRTIO
"$config" --file "$output/build/.config" --enable VIRTIO_PCI
"$config" --file "$output/build/.config" --enable VIRTIO_BLK
"$config" --file "$output/build/.config" --enable VIRTIO_NET
"$config" --file "$output/build/.config" --enable EXT4_FS
"$config" --file "$output/build/.config" --enable TMPFS
"$config" --file "$output/build/.config" --enable PROC_FS
"$config" --file "$output/build/.config" --enable SYSFS
"$config" --file "$output/build/.config" --enable NET
"$config" --file "$output/build/.config" --enable PACKET
if [[ "$arch" == amd64 ]]; then
    "$config" --file "$output/build/.config" --enable SERIAL_8250
    "$config" --file "$output/build/.config" --enable SERIAL_8250_CONSOLE
else
    "$config" --file "$output/build/.config" --enable PCI_HOST_GENERIC
    "$config" --file "$output/build/.config" --enable SERIAL_AMBA_PL011
    "$config" --file "$output/build/.config" --enable SERIAL_AMBA_PL011_CONSOLE
fi
case "$profile" in
    kasan)
        "$config" --file "$output/build/.config" --disable KCSAN
        "$config" --file "$output/build/.config" --enable KASAN
        "$config" --file "$output/build/.config" --enable KASAN_GENERIC
        "$config" --file "$output/build/.config" --enable KASAN_OUTLINE
        "$config" --file "$output/build/.config" --enable KASAN_VMALLOC
        ;;
    kcsan)
        "$config" --file "$output/build/.config" --disable KASAN
        "$config" --file "$output/build/.config" --enable DEBUG_KERNEL
        "$config" --file "$output/build/.config" --enable KCSAN
        "$config" --file "$output/build/.config" --enable KCSAN_EARLY_ENABLE
        "$config" --file "$output/build/.config" --enable KCSAN_SELFTEST
        "$config" --file "$output/build/.config" --enable KCSAN_INTERRUPT_WATCHER
        # Virtio device DMA is intentionally not compiler-instrumented and
        # generates unknown-origin KCSAN reports in the generic virtqueue
        # core.  Keep two-sided instrumented race detection strict while
        # excluding that non-candidate device-noise class.
        "$config" --file "$output/build/.config" --disable KCSAN_REPORT_RACE_UNKNOWN_ORIGIN
        ;;
    lockdebug)
        "$config" --file "$output/build/.config" --disable KASAN
        "$config" --file "$output/build/.config" --disable KCSAN
        "$config" --file "$output/build/.config" --enable DEBUG_KERNEL
        # Full PROVE_LOCKING selects DEBUG_LOCK_ALLOC, which maps mutex_lock()
        # to GPL-only mutex_lock_nested() in the pinned kernel. The candidate
        # module is correctly non-GPL under the project license, so use the
        # strongest locking-debug subset that does not cross GPL-only exports.
        "$config" --file "$output/build/.config" --disable PROVE_LOCKING
        "$config" --file "$output/build/.config" --disable DEBUG_WW_MUTEX_SLOWPATH
        "$config" --file "$output/build/.config" --disable LOCK_STAT
        "$config" --file "$output/build/.config" --disable DEBUG_LOCK_ALLOC
        "$config" --file "$output/build/.config" --disable LOCKDEP
        "$config" --file "$output/build/.config" --enable DEBUG_SPINLOCK
        "$config" --file "$output/build/.config" --enable DEBUG_MUTEXES
        "$config" --file "$output/build/.config" --enable DEBUG_RWSEMS
        "$config" --file "$output/build/.config" --enable DEBUG_ATOMIC_SLEEP
        ;;
esac

make -s -C "$output/src" O="$output/build" ARCH="$karch" olddefconfig
case "$profile" in
    kasan)
        grep -q '^CONFIG_KASAN=y$' "$output/build/.config"
        grep -q '^CONFIG_KASAN_GENERIC=y$' "$output/build/.config"
        ;;
    kcsan)
        grep -q '^CONFIG_KCSAN=y$' "$output/build/.config"
        grep -q '^CONFIG_KCSAN_EARLY_ENABLE=y$' "$output/build/.config"
        grep -q '^CONFIG_KCSAN_SELFTEST=y$' "$output/build/.config"
        grep -q '^CONFIG_KCSAN_INTERRUPT_WATCHER=y$' "$output/build/.config"
        grep -q '^# CONFIG_KCSAN_REPORT_RACE_UNKNOWN_ORIGIN is not set$' "$output/build/.config"
        ;;
    lockdebug)
        grep -q '^CONFIG_DEBUG_SPINLOCK=y$' "$output/build/.config"
        grep -q '^CONFIG_DEBUG_MUTEXES=y$' "$output/build/.config"
        grep -q '^CONFIG_DEBUG_RWSEMS=y$' "$output/build/.config"
        grep -q '^CONFIG_DEBUG_ATOMIC_SLEEP=y$' "$output/build/.config"
        grep -q '^# CONFIG_PROVE_LOCKING is not set$' "$output/build/.config"
        grep -q '^# CONFIG_DEBUG_LOCK_ALLOC is not set$' "$output/build/.config"
        grep -q '^# CONFIG_LOCKDEP is not set$' "$output/build/.config"
        ;;
esac
grep -q '^CONFIG_MODULES=y$' "$output/build/.config"
grep -q '^# CONFIG_MODVERSIONS is not set$' "$output/build/.config"
grep -q '^CONFIG_VIRTIO_BLK=y$' "$output/build/.config"
grep -q '^CONFIG_VIRTIO_NET=y$' "$output/build/.config"
grep -q '^CONFIG_EXT4_FS=y$' "$output/build/.config"

jobs=$(getconf _NPROCESSORS_ONLN 2>/dev/null || printf '2')
if (( jobs > 4 )); then
    jobs=4
fi
export KBUILD_BUILD_USER=dniv
export KBUILD_BUILD_HOST=diagnostic
export KBUILD_BUILD_VERSION=1
export KBUILD_BUILD_TIMESTAMP="Sun Apr 12 20:48:06 UTC 2026"
make -C "$output/src" O="$output/build" ARCH="$karch" -j"$jobs" "$image_target"
make -C "$output/src" O="$output/build" ARCH="$karch" -j"$jobs" modules
[[ -s "$output/build/Module.symvers" ]] || {
    echo "build-diagnostic-kernel: missing Module.symvers after bounded modules pass" >&2
    exit 1
}

# A complete kernel image build already produces the generated headers and
# symbol state required for external-module builds. Re-running modules_prepare
# after the full KASAN build is redundant and returned a non-zero status on
# both hosted architectures despite the completed kernel image.
krel=$(make -s -C "$output/src" O="$output/build" ARCH="$karch" kernelrelease)
echo "build-diagnostic-kernel: kernelrelease=$krel"
[[ "$krel" == "7.0.0-dniv-$profile" ]] || {
    echo "build-diagnostic-kernel: unexpected kernel release: $krel" >&2
    exit 1
}
cp "$output/build/$image_rel" "$output/vmlinuz"
cp "$output/build/.config" "$output/config"
printf '%s\n' "$krel" > "$output/kernelrelease"
printf '%s\n' "$linux_commit" > "$output/linux-commit"
test -s "$output/vmlinuz"

echo "build-diagnostic-kernel: arch=$arch profile=$profile release=$krel source=$linux_commit"
