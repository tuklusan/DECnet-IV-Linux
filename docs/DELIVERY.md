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

# Source Delivery Contract

## Release artifact

DECnet-IV-Linux is released as source, not as an operating-system or virtual-disk image.

A production release publishes:

1. `DECnet-IV-Linux-<version>.tar.xz`;
2. `DECnet-IV-Linux-<version>.tar.xz.sha256`;
3. release notes identifying the exact source commit and accepted compatibility matrix.

Disk images are not release artifacts. No QCOW2, RAW, IMG, ISO, prebuilt kernel, initrd or prebuilt `decnet_iv.ko` is a production deliverable. VM disk files created by the acceptance lab are disposable test infrastructure only.

The tarball is generated from one exact accepted source commit, contains no `.git` directory and no generated object/module/disk-image payloads, and carries `SOURCE-METADATA` with release version, source SHA and source-date epoch.

## Target systems

The production target is an existing modern Linux installation on x86_64 or aarch64. The initial compatibility floor is Linux 6.12 or later. The target kernel must expose an external-module build tree matching the kernel for which `decnet_iv.ko` will be loaded, normally `/lib/modules/$(uname -r)/build`.

The release is distribution-neutral. Debian/Ubuntu and Fedora/RHEL-family package names in `INSTALL.md` are examples; the real requirements are a supported compiler, libc development environment, GNU make, matching kernel development tree, Python where applicable, and standard module-management utilities.

Forward compatibility is an active maintenance requirement. Full release acceptance compiles against the oldest supported floor, maintained distro kernels, the current validated upstream kernel line and both supported C compiler families where the kernel build permits them. Future published kernel API changes are fixed in source and retained as compatibility regressions.

## Build and installation model

- `build.sh` validates prerequisites and builds all delivered userspace plus the kernel module.
- `install.sh` installs the module, commands, daemons, libraries, development headers and documentation. `DESTDIR` is supported.
- `uninstall.sh` removes only paths recorded by the installation manifest and refreshes module/library caches on a live system.

The module is always compiled for the selected target kernel. Copying a module built for another kernel is unsupported.

## Release acceptance

The canonical release object is the exact source tarball. The source-release gate must:

- create the archive twice from identical inputs and require byte-for-byte equality;
- reject generated binaries, modules, disk images and `.git` metadata in the archive;
- extract and build the archive with no repository metadata;
- stage-install every delivered component on amd64 and arm64;
- validate the installed component manifest;
- run uninstall and prove manifest-owned files are removed;
- exercise the same archive through the maintained distro portability matrix;
- bind later protocol/real-peer evidence to the source SHA carried by that archive.

The VM lab may continue to create disposable disks internally to obtain independent kernels and destructive isolation. Those files are never release artifacts.
