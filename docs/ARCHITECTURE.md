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

# Architecture

## Kernel

DECnet Phase IV is implemented as a fresh out-of-tree Linux kernel module. The distribution tracks maintained kernels without carrying a permanent kernel fork or reviving the removed legacy Linux DECnet stack.

Kernel scope grows in dependency order:

1. native Ethernet and DECnet address/MAC handling;
2. endnode, Level 1 and Level 2 routing plus adjacency/timers;
3. NSP transport and native DECnet socket/UAPI support;
4. Session Control support and NICE/NML management hooks/state.

Core routing and NSP state machines stay in kernel space. The versioned management UAPI is kept intentionally small. Phase 5 additionally provides the classic DECnet/Linux socket-facing `linux/dn.h` data structures, protocol numbers and socket-option constants so existing DECnet userspace can target the new implementation without reviving the historical kernel stack.

## Userspace

Userspace is built against the new kernel ABI. The target is the useful DECnet/Linux environment: `ncp`, `sethost`/`dnlogin`, DAP/FAL/RMS copy/type/directory tools, PHONE, mail, task/object access, daemons, libraries, diagnostics and administration tools.

Historical behavior is implemented, replaced by a documented modern equivalent, explicitly retired with justification, or deferred behind a tracked protocol dependency. Point-to-point Internet lab connectivity is a userspace concern: the supported path is PyDECnet-derived MULTINET TCP, normally fronting a VDE Ethernet segment.

## Source distribution and target systems

The production deliverable is a source tarball, not a Linux distribution image. It targets existing x86_64 and aarch64 Linux systems with Linux 6.12 or later, matching external-module kernel headers/build tree, a supported C compiler and the dependencies listed in `INSTALL.md`. The kernel module is built on the target for the selected kernel; no prebuilt project kernel or `decnet_iv.ko` is required.

Forward compatibility is maintained by portability/compatibility gates against maintained distro kernels and current validated upstream kernel lines. Unknown future kernel API changes are corrected when published and retained as compatibility regressions.

The Ubuntu/QEMU disk machinery under `image/` and `tests/lab/` exists only to create independent disposable acceptance nodes. QCOW2/RAW/IMG/ISO files are not production deliverables.

## Testing

Acceptance nodes are independent VMs with independent kernels. Network namespaces or containers that share one kernel do not satisfy the VM gate.

The test ladder grows from 2 to 4, 8 and 16 nodes and covers x86_64, aarch64, both mixed directions, routed multi-LAN topologies, deterministic faults, stress, independent Route20/PyDECnet peers, later SIMH-hosted real DEC systems, plus rootless/distributed VDE2 Ethernet fabrics, MULTINET-backed Internet lab gateways, HECnet Area-31 interoperability, a real VAX area router, and physical hardware. The MULTINET-facing Area-31 router and the reachable VAX router are interoperability peers, not implementation dependencies.

Self-to-self success is useful for development but never sufficient for final interoperability claims.
