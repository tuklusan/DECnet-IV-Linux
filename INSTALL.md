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

Supported CPU architectures are x86_64 and aarch64. The production kernel floor is Linux 6.8 or later.

The selected kernel must have a matching external-module build tree. For the running kernel:

```sh
test -r /lib/modules/"$(uname -r)"/build/Makefile
```

To target another installed kernel, set both `KERNEL_RELEASE` and `KDIR`.

## 2. Required software

Core build requirements:

- Linux 6.8+ with matching kernel headers/development tree;
- GNU make 4.0+;
- GCC 12+ or Clang 16+; for the kernel module, use the compiler family compatible with the selected kernel build tree;
- binutils (including `ar`) and libc development environment;
- Bash 5.0+;
- Python 3.10+;
- standard `cat`, `head`, `install`, `ln`, `mkdir`, `chmod`, `rm`, `mv`, `find`, `sort`, `stat`, `grep`, `sed`, `dirname`, `basename`, `mktemp`, `id`, `rmdir`, `uname`, and `sha256sum`;
- `kmod` utilities, including `modinfo`, `depmod` and `modprobe`, for module verification and live installation/loading;
- the host dynamic-loader mechanism for installed shared libraries. On glibc-style systems `ldconfig` is used when available; systems without an `ldconfig` cache must already search the selected library directory or be configured by the administrator.

The tarball needs `tar` with xz support for extraction. If Clang is selected instead of GCC, install the distribution's Clang/LLVM packages as well.

### Debian/Ubuntu example

```sh
sudo apt-get update
sudo apt-get install build-essential python3 kmod linux-headers-"$(uname -r)" xz-utils
```

### Fedora/RHEL-family example

```sh
sudo dnf install gcc make binutils python3 kmod kernel-devel libstdc++-devel xz
```

The installed kernel development package must match the kernel being targeted.

## 3. Optional runtime integrations

The native stack and C userspace do not require PyDECnet, Route20, SIMH, QEMU or VDE2. The end-user `build.sh` does not execute the lab-only Area-31/VDE2 integration selftests; those remain under the repository test targets.

- `dnmultinet`: Python 3.10+, a compatible PyDECnet installation providing `python3 -m decnet.main`, and libvdeplug/VDE2 for the required `vde://` Ethernet circuit. The project's acceptance references are PyDECnet `8d93c2a546317c67aba0adf9433f5f3efdf1f85c` and `tuklusan/vde-2` `7e7017b6308f3f81d5c922a32097137ceee13074`; they are external projects with their own licenses and are not vendored in this tarball.
- Before using `dnmultinet`, verify `python3 -c 'import decnet'` and the VDE commands required by the chosen deployment (normally `vde_switch` and `vde_plug`). The `--pydecnet-dir` option can point at an unpacked compatible PyDECnet tree without installing it system-wide. MULTINET configuration values are validated as single config tokens, `--local-address` is IPv4-only, and `--runtime-peer-env` refuses both `--dry-run` and `--config-out`; after the endpoint is copied into the memory-backed configuration, `MULTINET_REMOTE_HOST` and `MULTINET_REMOTE_PORT` are removed from the environment passed to PyDECnet.
- `dnmaild --sendmail`: a sendmail-compatible executable.
- `dnmaild --smtp`: a reachable SMTP service.
- VDE2/MULTINET/HECnet laboratory integration is optional; see `docs/HECNET_LAB.md`.
- SIMH and Route20 are project acceptance references only; normal installation does not require them.

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

Clang, when the target kernel build tree was configured for Clang:

```sh
CC=clang ./build.sh
```

Many distribution kernels are configured and built with GCC. Their exported external-module flags can be GCC-specific, so forcing Clang against such a `KDIR` is not supported. `build.sh` detects the common `CONFIG_CC_IS_GCC`/`CONFIG_CC_IS_CLANG` mismatch and fails with a clear diagnostic. Use the compiler family compatible with the target kernel; userspace itself is continuously checked with both GCC and Clang.

Another installed kernel:

```sh
target=<kernel-release>
KERNEL_RELEASE="$target" \
KDIR="/lib/modules/$target/build" \
./build.sh
```

A successful build produces userspace programs/libraries and `kernel/decnet/decnet_iv.ko`. `install.sh` reads the module vermagic and refuses a conflicting `KERNEL_RELEASE`, preventing a cross-kernel build from being installed into the wrong module tree.

## 6. Staged install

```sh
rm -rf /tmp/dniv-stage
DESTDIR=/tmp/dniv-stage ./install.sh
```

This requires no root privilege and is the supported packaging/release-validation path. `DESTDIR` must be a normalized absolute non-root path. For staged operations, `install.sh` and `uninstall.sh` reject existing symlinked parent components so file creation or removal cannot traverse outside the selected staging tree. `install.sh` records each managed target in the installation manifest before writing it, refuses to overwrite an existing target that is not already managed, and preserves the manifest on failure. If a staged or live install is interrupted or otherwise fails, rerun `uninstall.sh` with the same `DESTDIR`, `PREFIX` and `MODULE_ROOT` values to clean the tracked partial installation before retrying.

## 7. Live install

```sh
sudo ./install.sh
```

The default userspace prefix is `/usr/local`. The module installs under `/lib/modules/<kernel-release>/extra/`. By default the installer obtains `<kernel-release>` from the built module's vermagic; if `KERNEL_RELEASE` is supplied it must match that vermagic exactly. The manifest is `/usr/local/share/decnet-iv-linux/install-manifest.txt`. Live installation requires `depmod` and preflights it before creating or changing the manifest, so module dependency metadata cannot be silently left stale. With the default module root, standard `/lib/modules/<kernel-release>/extra/decnet_iv.ko` entries from earlier kernel builds remain valid managed entries, so installing for a new kernel can preserve an older tracked module for fallback. A full uninstall removes every such tracked standard module copy and refreshes their dependency caches. Custom `MODULE_ROOT` is supported only together with non-empty `DESTDIR` for staged/package layouts; live install always uses `/lib/modules/<kernel-release>` so the installed module and the dependency cache refreshed by `depmod` refer to the same kernel module tree. Existing files outside the manifest are never overwritten; resolve any collision explicitly rather than forcing the installer.

A different userspace prefix may be selected with `PREFIX=/opt/decnet`. The installer does not modify `/etc/ld.so.conf` or another system loader configuration: if the selected `PREFIX/lib` is not already on the host dynamic-loader search path, configure that path using the host's normal mechanism (for example an administrator-managed `ld.so.conf.d` entry plus `ldconfig` on glibc systems, an rpath, or an explicit runtime library path). Staged packaging may set a normalized absolute non-root `MODULE_ROOT` together with non-empty `DESTDIR`. `PREFIX`, `MODULE_ROOT` and non-empty `DESTDIR` reject CR/LF line breaks, `.`/`..` path components and repeated `//` separators; a trailing slash is normalized away. CR/LF is forbidden because the ownership manifest is deliberately line-oriented. Manifest rewrites use an atomically created `mktemp` file in the manifest directory so a pre-existing predictable temporary-name symlink cannot redirect the write. Both the temporary file and any pre-existing manifest must be single-link regular files; a hard-linked manifest is rejected before any managed target is changed. Reinstallation also refuses a managed regular-file target whose link count is not exactly one, so replacing an installed file with a hard link cannot redirect a later install write into another inode name.

### Secure Boot and module signing

`decnet_iv.ko` is an out-of-tree module. On systems enforcing kernel-module signatures (commonly Secure Boot), the kernel may reject an unsigned module even though it built correctly. Use the distribution's normal external-module signing/MOK procedure and sign the exact built `decnet_iv.ko`; DECnet-IV-Linux does not bypass signature enforcement. Verify the host policy with `mokutil --sb-state` when that tool is available and inspect `dmesg` if `modprobe` reports a signature/key error.

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

To request automatic module loading at boot on a conventional system, create an administrator-managed `/etc/modules-load.d/decnet-iv-linux.conf` containing `decnet_iv`. Node identity and user-space daemons still require site-specific startup configuration; the installer deliberately does not create or enable network-facing services.

## 9. Services

The release does not silently enable network-facing daemons. Delivered servers include `dnetd`, `dnfald`, `dnnml`, `dnphoned`, `dnmaild` and `dnhttpd`. `dnetd` defaults to `/etc/dnetd.conf`. Use the host's service manager if persistent services are desired.

For `dnfald` DAP CREATE, the directory supplied with `--root` must be writable by the service account on a Linux filesystem supporting `O_TMPFILE`, `linkat(AT_EMPTY_PATH)` and `user.*` extended attributes. Completed uploads are published under the requested name without overwriting an existing entry; aborted or failed pre-publication transfers do not expose incomplete files. On an unsupported filesystem CREATE fails closed. Explicit ERASE/RENAME operations are separate; apply the site's access and directory-permission policy before enabling network-facing FAL service.

Record-mode `dncopy` uploads (the classic default) accept bounded text records but reject embedded NUL bytes or overlong lines instead of silently truncating data. Use `-m block` or `--put` for binary files and verify hashes after transfer.

## 10. Client environment

Installed clients include `ncp`, `dnlogin`/`sethost`, `dncopy` plus its DAP command aliases, `dntask`, `dnping`, `dnnice`, `dnmirror`, `dnobject`, `phone`, `dnmail` and `dnlynx`.

See `docs/FEATURES.md` and `docs/COMPONENTS.md`.

## 11. Uninstall

Stop DECnet services and, when safe for the host, unload the module first:

```sh
sudo modprobe -r decnet_iv
sudo ./uninstall.sh
```

If the module is intentionally left loaded, removing the on-disk module does not remove the already-loaded kernel code; unload it or reboot before considering the running kernel reverted.

For staged installation:

```sh
DESTDIR=/tmp/dniv-stage ./uninstall.sh
```

Uninstall is manifest-driven, requires the manifest itself to be a single-link regular file, and refuses unsafe manifest paths. Live uninstall requires `depmod` and verifies it before removing any manifest-owned path, so the kernel module dependency cache cannot be silently skipped after module removal. When `ldconfig` exists, uninstall refreshes the host dynamic-library cache after removing libraries; systems without that cache mechanism use their normal loader-path rules. If installation used a non-default `PREFIX`, pass the same value to `uninstall.sh`. For staged/package installs that used custom `MODULE_ROOT`, pass the same `DESTDIR` and `MODULE_ROOT`; custom `MODULE_ROOT` is rejected for live uninstall for the same dependency-cache safety reason as live install.

## 12. Kernel upgrades

After installing a new kernel:

1. install matching headers;
2. use a clean copy of the accepted source release;
3. build for the exact target release, for example `KERNEL_RELEASE="$target" KDIR="/lib/modules/$target/build" ./build.sh`;
4. install the resulting module and userspace with `sudo KERNEL_RELEASE="$target" ./install.sh`; the installer independently checks the module vermagic before writing anything and preserves any older manifest-managed standard `/lib/modules/<release>/extra/decnet_iv.ko` copy;
5. after booting that kernel, load `decnet_iv` and verify identity, adjacencies and required services.

Never reuse a `decnet_iv.ko` on a kernel for which it was not built.
