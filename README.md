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

# DECnet-IV-Linux

DECnet Phase IV for modern Linux, delivered as portable source.

The production deliverable is a versioned source tarball. It builds the out-of-tree kernel module and the complete DECnet/Linux userspace directly on the target x86_64 or aarch64 Linux system against that system's installed kernel headers. Disk images are not release artifacts.

Based on original work by Supratim Sanyal of SANYALnet Labs. See `LICENSE` for the governing terms.

## Delivered stack

The source release contains the native Ethernet endnode/L1/L2 routing stack, NSP transport, native `AF_DECnet` / `SOCK_SEQPACKET` socket ABI, Session Control, NICE/NML management, UAPI headers, libraries, administration tools, DAP/FAL utilities and service, login, task/object access, PHONE, mail, MIRROR, DECnet HTTP client/server tools, and the MULTINET integration launcher.

See `docs/FEATURES.md`, `docs/COMPONENTS.md`, `docs/DELIVERY.md`, and `INSTALL.md`.

## Supported target

The current production compatibility floor is Linux 6.12 or later on x86_64 or aarch64, with a matching configured kernel build/header tree. GCC or Clang may be used. Python 3.10 or later is required for the delivered `dnmultinet` launcher.

Forward compatibility is maintained by continuously compiling against maintained distro kernels and current upstream kernel lines. Unknown future kernel API changes cannot be guaranteed in advance; compatibility defects discovered by the forward build gates are blocking until corrected.

## Build

```sh
./build.sh
sudo ./install.sh
```

The build compiles userspace and `decnet_iv.ko` against the selected target kernel. Installation never requires a prebuilt project kernel or project disk image.

## Repository layout

- `include/uapi/` — versioned kernel/userspace ABI.
- `kernel/decnet/` — native DECnet Phase IV out-of-tree kernel module.
- `userspace/` — commands, daemons and libraries.
- `docs/` — architecture, feature, component, delivery and acceptance documentation.
- `tests/` — unit, VM, interoperability, fault and stress tests.
- `image/ubuntu-base/` — lab-only disposable VM construction support; not a product deliverable.
- `references/` — normative specification and pinned independent-reference metadata.
- `.github/workflows/` — exact-source build, portability and acceptance gates.

Start with `docs/HANDOVER.md` when resuming project work.
