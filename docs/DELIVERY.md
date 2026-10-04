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

The source tarball itself contains the complete in-scope kernel/userspace source, `build.sh`, `install.sh`, `uninstall.sh`, and the detailed step-by-step `INSTALL.md` manual. `INSTALL.md` is part of the release contract, not optional project prose: it must identify prerequisites, supported kernel/compiler/Python floors, matching kernel-header requirements, build commands, staged/live installation, configuration, module loading/unloading, Secure Boot considerations, verification, upgrades and uninstall behavior.

Disk images are not release artifacts. No QCOW2, RAW, IMG, ISO, prebuilt kernel, initrd or prebuilt `decnet_iv.ko` is a production deliverable. VM disk files created by the acceptance lab are disposable test infrastructure only.

The tarball is generated from one exact accepted source commit, contains no `.git` directory and no generated object/module/disk-image payloads, and carries `SOURCE-METADATA` with release version, source SHA and source-date epoch.

## Target systems

The production target is an existing modern Linux installation on x86_64 or aarch64. The initial compatibility floor is Linux 6.8 or later. The target kernel must expose an external-module build tree matching the kernel for which `decnet_iv.ko` will be loaded, normally `/lib/modules/$(uname -r)/build`.

The release is distribution-neutral. Debian/Ubuntu and Fedora/RHEL-family package names in `INSTALL.md` are examples; the real requirements are a supported compiler, libc development environment, GNU make, matching kernel development tree, Python where applicable, and standard module-management utilities.

Forward compatibility is an active maintenance requirement. Full release acceptance compiles the exact packaged source archive against the oldest supported floor, maintained distro kernels, the current validated upstream kernel line and both supported C compiler families where the selected kernel build tree permits them. The module compiler must be compatible with the kernel's configured compiler family; userspace is checked independently with both GCC and Clang. Future published kernel API changes are fixed in source and retained as compatibility regressions. The synthetic current-upstream Clang compatibility tree has no distribution `Module.symvers`; that compile-only/staged-install gate therefore uses the kernel-supported `KBUILD_MODPOST_WARN=1` mode after disabling symbol-version enforcement. This exception is confined to non-loadable forward-compile proof; production installation against an actual target kernel requires that kernel's complete external-module development tree and normal modpost success.

## Build and installation model

- `build.sh` validates end-user prerequisites and builds all delivered userspace plus the kernel module without requiring lab-only VDE2/Area-31 test infrastructure.
- `install.sh` installs the module, commands, daemons, libraries, development headers and documentation. `DESTDIR` is supported. It records managed paths before writing them and refuses unmanaged target collisions, so a failed or interrupted install remains manifest-cleanable rather than silently untracked.
- `uninstall.sh` removes only paths recorded by a single-link regular installation manifest, rejects aliased/hard-linked manifest trust roots, requires `depmod` for the live kernel-module dependency cache, and refreshes the dynamic-library cache with `ldconfig` when the host provides that cache mechanism.

The module is always compiled for the selected target kernel. Copying a module built for another kernel is unsupported.

## Release completion sequence

Before final production delivery, the exact packaged source bytes must pass the owner-mandated manual fresh-disk audit: **three successive zero-defect scans (3/3)**. Each scan uses a freshly downloaded copy of the exact accepted artifact and records its tarball filename and SHA-256. Any new defect invalidates the candidate for this audit, keeps/resets the counter to 0/3, is repaired on `main`, and requires a new exact-SHA targeted/source-release acceptance artifact before scanning restarts.

Reaching 3/3 does not bypass pre-production testing. It closes the source-delivery conversion audit, after which the project resumes the remaining applicable `docs/PRE_PRODUCTION_TEST.md` dependency chain. Blocking PP-11 S1 pressure must close before S2. Final publication occurs only after the remaining applicable PP/release gates and final exact-SHA acceptance are green.

## Release acceptance

The canonical release object is the exact source tarball. The source-release gate must:

- create the archive twice from identical inputs and require byte-for-byte equality;
- reject generated binaries, modules, disk images and `.git` metadata in the archive;
- extract and build the archive with no repository metadata;
- stage-install every delivered component on amd64 and arm64;
- validate the installed component manifest;
- run uninstall and prove manifest-owned files are removed;
- exercise the exact same archive bytes through the maintained Debian/Fedora, amd64/arm64 and GCC/Clang portability matrix; every compiler-compatible kernel path must run the documented `build.sh` and staged install/uninstall path, not only a compile-only object probe;
- bind later protocol/real-peer evidence to the source SHA carried by that archive.

The VM lab may continue to create disposable disks internally to obtain independent kernels and destructive isolation. Those files are never release artifacts.

## Completeness gate

The production tarball must document every delivered project-goal surface in `docs/FEATURES.md` and every installed/source component in `docs/COMPONENTS.md`. A project-goal component cannot disappear merely because the delivery format changed.

DDCMP and IPv6 are explicitly outside the current project and release scope by owner decision. They are not claimed product features, are not release blockers, and do not generate PP/reference/device acceptance requirements. MULTINET project acceptance is IPv4-only.
