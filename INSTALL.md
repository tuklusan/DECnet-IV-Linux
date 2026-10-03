<!-- ============================================================================ -->
<!-- Copyright (c) 2026 Supratim Sanyal of SANYALnet Labs. -->
<!-- Proprietary rights reserved except as expressly licensed herein. -->
<!-- -->
<!-- DECnet-IV-Linux -->
<!-- This file is governed by the SANYALnet Labs Non-Commercial License in the -->
<!-- root LICENSE file. Non-Commercial use is permitted; Commercial Use and use -->
<!-- for AI/ML model training are prohibited unless separately authorized. -->
<!-- -->
<!-- Attribution is required: "Based on original work by Supratim Sanyal of -->
<!-- SANYALnet Labs." See LICENSE for full terms, warranty disclaimer, termination, -->
<!-- patent, trademark, and governing-law provisions. -->
<!-- ============================================================================ -->

# Build and Installation Manual

This manual installs DECnet-IV-Linux from the production source tarball onto an existing Linux system.

## 1. Supported machines and kernel

Supported CPU architectures are x86_64 and aarch64. The production kernel floor is Linux 6.12 or later.

The selected kernel must have a matching external-module build tree. For the running kernel:

```sh
test -r /lib/modules/"$(uname -r)"/build/Makefile
```

To target another installed kernel, set both `KERNEL_RELEASE` and `KDIR`.

## 2. Required software

Core build requirements:

- Linux 6.12+ with matching kernel headers/development tree;
- GNU make 4.0+;
- GCC 12+ or Clang 16+;
- binutils and libc development environment;
- Bash 5.0+;
- Python 3.10+;
- standard `install`, `ln`, `rm`, `find`, `sort`, `grep`, and `sed`;
- `kmod` utilities for live installation/loading.

The tarball needs tar with xz support for extraction.

### Debian/Ubuntu example

```sh
sudo apt-get update
sudo apt-get install build-essential python3 kmod linux-headers-"$(uname -r)" xz-utils
```

### Fedora/RHEL-family example

```sh
sudo dnf install gcc make python3 kmod kernel-devel libstdc++-devel xz
```

The installed kernel development package must match the kernel being targeted.

## 3. Optional runtime integrations

The native stack and C userspace do not require PyDECnet, Route20, SIMH, QEMU or VDE2.

- `dnmultinet`: Python 3.10+, compatible PyDECnet, and the VDE/libvdeplug environment used by the selected PyDECnet Ethernet circuit.
- `dnmaild --sendmail`: a sendmail-compatible executable.
- `dnmaild --smtp`: a reachable SMTP service.
- VDE2/MULTINET/HECnet laboratory integration is optional; see `docs/HECNET_LAB.md`.
- SIMH, Route20 and independent PyDECnet trees are acceptance dependencies unless separately deployed by the administrator.

## 4. Verify and extract

```sh
sha256sum -c DECnet-IV-Linux-<version>.tar.xz.sha256
tar -xJf DECnet-IV-Linux-<version>.tar.xz
cd DECnet-IV-Linux-<version>
```

Read `SOURCE-METADATA` and `LICENSE`.

## 5. Build

```sh
./build.sh
```

Clang:

```sh
CC=clang ./build.sh
```

Another installed kernel:

```sh
KERNEL_RELEASE=<kernel-release> \
KDIR=/lib/modules/<kernel-release>/build \
./build.sh
```

A successful build produces userspace programs/libraries and `kernel/decnet/decnet_iv.ko`.

## 6. Staged install

```sh
rm -rf /tmp/dniv-stage
DESTDIR=/tmp/dniv-stage ./install.sh
```

This requires no root privilege and is the supported packaging/release-validation path.

## 7. Live install

```sh
sudo ./install.sh
```

The default userspace prefix is `/usr/local`. The module installs under `/lib/modules/<kernel-release>/extra/`. The manifest is `/usr/local/share/decnet-iv-linux/install-manifest.txt`. The installer refreshes `depmod` and `ldconfig` when available.

A different userspace prefix may be selected with `PREFIX=/opt/decnet`.

## 8. Load and establish identity

```sh
sudo modprobe decnet_iv
sudo /usr/local/sbin/dnctl set 1.10 LINUX
/usr/local/sbin/dnctl show
/usr/local/sbin/dnctl adjacencies
/usr/local/sbin/dnctl routes
/usr/local/sbin/dnctl links
/usr/local/sbin/dnctl stats
```

## 9. Services

The release does not silently enable network-facing daemons. Delivered servers include `dnetd`, `dnfald`, `dnnml`, `dnphoned`, `dnmaild` and `dnhttpd`. `dnetd` defaults to `/etc/dnetd.conf`. Use the host's service manager if persistent services are desired.

## 10. Client environment

Installed clients include `ncp`, `dnlogin`/`sethost`, `dncopy` plus its DAP command aliases, `dntask`, `dnping`, `dnnice`, `dnmirror`, `dnobject`, `phone`, `dnmail` and `dnlynx`.

See `docs/FEATURES.md` and `docs/COMPONENTS.md`.

## 11. Uninstall

```sh
sudo ./uninstall.sh
```

For staged installation:

```sh
DESTDIR=/tmp/dniv-stage ./uninstall.sh
```

Uninstall is manifest-driven and refuses unsafe manifest paths.

## 12. Kernel upgrades

After installing a new kernel:

1. install matching headers;
2. use a clean copy of the accepted source release;
3. set `KERNEL_RELEASE` and `KDIR`;
4. run `./build.sh`;
5. run `sudo ./install.sh`;
6. after booting that kernel, load `decnet_iv` and verify identity, adjacencies and required services.

Never reuse a `decnet_iv.ko` on a kernel for which it was not built.
