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

# Delivered Components

## Kernel and UAPI

| Component | Role |
| --- | --- |
| `kernel/decnet/decnet_iv.ko` | Out-of-tree native DECnet Phase IV Ethernet/routing/NSP/socket/Session kernel module. |
| `include/uapi/linux/dn.h` | Classic-compatible socket-facing UAPI definitions. |
| `include/uapi/linux/decnet_iv.h` | Management/state UAPI. |

Kernel source responsibilities:

| Source | Responsibility |
| --- | --- |
| `decnet_iv_main.c` | Module lifecycle, node identity and management/control integration. |
| `decnet_iv_ethernet.c` | Native Ethernet framing, logical DECnet MAC handling, hello traffic and adjacency-facing link behavior. |
| `decnet_iv_route.c` | Endnode/L1/L2 routing state, route selection, forwarding and convergence. |
| `decnet_iv_nsp.c` | NSP logical links, sequencing, flow control, retransmission, timers and receive queues. |
| `decnet_iv_socket.c` | Native `AF_DECnet` socket/UAPI boundary and Session Control object dispatch. |

## Libraries

| Source directory | Installed result | Purpose |
| --- | --- | --- |
| `userspace/libdnet` | `libdnet.so.1.0`, `libdnet.a`, `netdnet` headers | DECnet/Linux compatibility and node/address API. |
| `userspace/libdnet` | `libdnet_daemon.so.1.0`, `libdnet_daemon.a` | Daemon helpers. |

## Administration and management

| Source directory | Executable | Purpose |
| --- | --- | --- |
| `userspace/dnctl` | `dnctl` | Native identity, statistics, adjacency, route and link administration. |
| `userspace/ncp` | `ncp` | NCP-style local/remote management front end. |
| `userspace/dnnice` | `dnnice` | NICE client. |
| `userspace/dnnml` | `dnnml` | NML object 19 server. |

## Terminal, diagnostics and object access

| Source directory | Executable | Purpose |
| --- | --- | --- |
| `userspace/dnlogin` | `dnlogin`, `sethost` | Remote terminal client and alias. |
| `userspace/dnping` | `dnping` | Connectivity probe. |
| `userspace/dnmirror` | `dnmirror` | MIRROR utility. |
| `userspace/dnobject` | `dnobject` | Named/numbered object client. |
| `userspace/dntask` | `dntask` | Task/object client. |

## DAP/FAL

| Source directory | Executable | Purpose |
| --- | --- | --- |
| `userspace/dncopy` | `dncopy`, `dntype`, `dndir`, `dndel`, `dnrename`, `dnsubmit`, `dnprint` | DAP/FAL client operations. |
| `userspace/dnfald` | `dnfald` | FAL object 17 server. |

## PHONE, mail and web

| Source directory | Executable | Purpose |
| --- | --- | --- |
| `userspace/dnphone` | `phone`, `dnphoned` | PHONE client and object 29 server. |
| `userspace/dnmail` | `dnmail`, `dnmaild` | Mail client and object 27 service. |
| `userspace/dnhttpd` | `dnhttpd` | DECnet-native HTTP server. |
| `userspace/dnlynx` | `dnlynx` | DECnet-native HTTP client. |

## Dispatch and integration

| Source directory | Executable | Purpose |
| --- | --- | --- |
| `userspace/dnetd` | `dnetd` | Object-to-program service dispatcher. |
| `userspace/dnmultinet` | `dnmultinet` | Python launcher/config generator for optional PyDECnet VDE-to-MULTINET routing. |

## Build and release support

`build.sh`, `install.sh`, `uninstall.sh`, `tools/build-source-release.sh`, `INSTALL.md`, `docs/DELIVERY.md`, and `docs/FEATURES.md` define the portable source-release path.

## Pending project-goal component

Native DDCMP is part of the standing project goal but has no implementation component in the current tracked tree. It is deliberately listed here as pending rather than being silently omitted or falsely described as delivered.

## Lab-only content

`tests/`, `image/ubuntu-base/`, acceptance workflows and pinned independent-reference metadata remain in the source tree for reproducibility. QEMU/QCOW2 files they create are temporary acceptance infrastructure, not installed components and not release artifacts.
