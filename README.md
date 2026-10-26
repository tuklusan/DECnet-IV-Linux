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

Native DECnet Phase IV for maintained Linux, built from portable source. Ethernet, routing, NSP, sockets, management, and classic DECnet applications—without needing a vintage kernel or a ready-made disk image. The protocol may be old; the kernel does not have to be.

This repository contains the complete source tree for **x86_64 and aarch64**. Build it against the target machine's own Linux **6.8+** kernel headers.

## Supported target

Linux 6.8 or newer on x86_64 or aarch64 with a matching configured kernel build/header tree. Build prerequisites include GNU make, Bash, and a compatible GCC or Clang. The module must be rebuilt for each target kernel; future kernel API compatibility is verified, not assumed.

## Build and install

```sh
sudo ./install.sh
```

The installer builds the kernel module and installs the userspace tools. For a non-root package-style installation, use `DESTDIR=/tmp/dniv-stage ./install.sh`. Network-facing daemons remain disabled unless explicitly configured.

## The DECNET-IV-LINUX Kernel Module

One out-of-tree module, `decnet_iv.ko`; native protocol handling is in the Linux kernel, not a userspace routing substitute.

| Feature | What it delivers |
| --- | --- |
| Phase IV Ethernet | Native packet framing, DECnet address/MAC handling, node identity and hello traffic. |
| Endnode + L1/L2 router | All three roles; router discovery, adjacency expiry/recovery and designated-router behavior. |
| Real routing | L1/L2 databases, costs and metrics, next-hop selection, aging, convergence, multi-LAN/multi-area forwarding and hop/visit limits. |
| NSP transport | Connect/disconnect, logical links, segmentation, reassembly, sequencing, ACKs, retries, timers and bounded flow control. |
| Normal + urgent data | Regular and interrupt/out-of-band NSP records with independent poll/epoll readiness. |
| Linux DECnet sockets | Native `AF_DECnet` with `SOCK_SEQPACKET` record boundaries and `SOCK_STREAM` byte-stream behavior, including partial reads and `MSG_WAITALL`. |
| Classic socket controls | `DNPROTO_NSP` access/connect/accept/disconnect data, link info, deferred accept/reject and explicit accept/reject. |
| Session Control | Object selection and dispatch, connection initiation, access-data handling and accept/reject semantics. |
| Kernel management API | Versioned UAPI, `/dev/decnet_iv`, identity, route/adjacency/NSP-link snapshots and counters. |
| Defensive protocol handling | Strict wire/menu parsing, record-size limits, overflow checks, retransmission ownership and orderly teardown/EOF behavior. |

## Userland features and tools

| Feature / commands | What it delivers |
| --- | --- |
| `dnctl` | Set and inspect node identity; view status, statistics, neighbors, routes and NSP links. |
| `ncp`, `dnnice`, `dnnml` | NCP-style local/remote management, NICE client and NML management service (object 19). |
| `libdnet`, `libdnet_daemon` | Shared/static DECnet API and daemon helpers; node/object lookup, `/etc/decnet.conf` compatibility, installed `netdnet` and Linux UAPI headers. |
| `dnlogin`, `sethost` | CTERM/Foundation remote terminal sessions with access data and interactive terminal control. |
| `dnping`, `dnmirror` | MIRROR connectivity tests, timing/packet statistics and MIRROR service/utility behavior. |
| `dnobject`, `dntask` | Connect to named or numbered objects and remote task services. |
| `dncopy` | DAP file upload/download; text-record and binary-block transfer modes. |
| `dntype`, `dndir`, `dndel` | Remote file display, directory listing and deletion over DAP. |
| `dnrename`, `dnsubmit`, `dnprint` | Remote rename, batch submission and printing via DAP. |
| `dnfald` | FAL server (object 17): file/directory access, create/get/delete/rename/submit/print and optional Session credentials. |
| `phone`, `dnphoned` | Classic PHONE client and object 29 server: connect, dial, text, directory and goodbye. |
| `dnmail`, `dnmaild` | MAIL-11 client/service (object 27): multiple recipients, legacy/v3 negotiation, spool, sendmail or SMTP delivery. |
| `dnlynx`, `dnhttpd` | Small native DECnet HTTP/1.0 client and bounded static-file server. |
| `dnetd` | Configurable numbered/named DECnet object-to-program dispatcher with listener policy and optional privilege drop. |
| `dnmultinet` | Optional PyDECnet/VDE Ethernet-to-MULTINET **IPv4 TCP** router launcher: connect/listen, routing roles, costs, priority and runtime peer settings. |

## Miscellaneous Features

| Area | Why it matters |
| --- | --- |
| Portable source delivery | Versioned full-source ZIP with an independently verified SHA-256 checksum; no prebuilt module, kernel, initramfs or disk image required. |
| Build compatibility | `install.sh` builds against a matching Linux 6.8+ kernel tree on x86_64/aarch64 with a kernel-compatible GCC or Clang toolchain; kernel upgrades require a fresh target build. |
| Install and remove | `install.sh` / `uninstall.sh` support live and `DESTDIR` staged installs, tracked ownership manifests, conflict checks and dependency-cache refresh. |
| Module signing | Uses the host's normal Secure Boot module-signing/MOK process; does not bypass kernel policy. |
| Safe DAP writes | Staged and atomic download publication; FAL exclusive create; reject unsafe symlinks, hard links, special files and partial uploads. |
| Faithful DAP records | VAR/VFC record preservation, stream/CRLF handling, bounded attribute parsing and file-format metadata checks. |
| Hardened services | Bounded record input, NUL/hidden-command rejection, guarded file roots, failure cleanup, persistent server isolation and child reaping. |
| Controlled interoperability | Independent Route20, PyDECnet, LinuxDECnet and SIMH/DEC-peer references; distributed VDE2, MULTINET and constrained HECnet Area-31 labs. |
| Repeatable acceptance | Unit, policy, negative, VM, routing/scale, real-peer, fault, endurance, portability and diagnostic-kernel test infrastructure. |
| Clear scope | **DDCMP and IPv6 are not implemented release targets.** MULTINET release acceptance is IPv4 TCP only. Lab images are never shipped in the production package. |

## Userland command examples

The examples below use DECnet node `1.20`. Replace it with a reachable node in your network. Run commands as the account that owns the installed tools, and supply access data only when the remote service requires it.

```sh
# Inspect the local node and its current DECnet state.
dnctl show
dnctl stats

# Query a remote node and measure a short run of MIRROR exchanges.
dnnice 1.20 summary
dnping -c 5 -w 5 1.20

# Copy a text file from a remote FAL service and list a remote directory.
dncopy --get 1.20 README.TXT
dndir 1.20 '[PUBLIC]'

# Open a remote terminal or connect to a remote task service.
dnlogin 1.20
dntask '1.20::TASK'
```

The exact installed option set is shown by each program's usage output. Test file transfers and remote commands against a project-controlled peer before using them on a protected system.

## Testing before release

The release candidate was exercised through a layered lab. Independent virtual machines ran on x86_64 and aarch64 in two-, four-, eight-, and sixteen-node routed topologies.

The lab covered multiple LANs, endnodes, L1/L2 routers, packet capture, deterministic faults, reloads, restarts, malformed input, resource pressure, and long-running traffic. It also tested native sockets, NSP sequencing and retransmission, routing convergence, Session Control, NICE/NML management, DAP/FAL transfers, terminal access, PHONE, mail, task services, and the HTTP tools.

Interoperability runs used independent Route20 and PyDECnet peers, SIMH-hosted DEC systems where applicable, local and distributed VDE2 Ethernet, and the IPv4 TCP MULTINET path.

Separate HECnet Area-31 tests exercised a controlled gateway and a reachable VAX area router. They covered adjacency, routing, native management traffic, and MIRROR traffic while preserving the safety boundary around remote systems.

## Acknowledgements

DECnet-IV-Linux was informed by Digital's published **Digital Network Architecture Phase IV** specifications and by the independent work below. Thanks to the people who built, maintained and documented these projects:

| Project | How it helped |
| --- | --- |
| [Route20](https://github.com/tuklusan/Route20) | Phase IV Ethernet, adjacency and L1/L2 routing reference. |
| [PyDECnet](https://github.com/tuklusan/pydecnet) | Broad independent stack behavior and MULTINET interoperability reference. |
| [LinuxDECnet](https://github.com/tuklusan/LinuxDECnet) | Linux socket interface, classic utilities and compatibility reference. |
| [SIMH](https://github.com/tuklusan/simh) | Emulated DEC hardware for testing against DEC operating systems. |
| [VDE2](https://github.com/tuklusan/vde-2) | Virtual distributed Ethernet for network and transport labs. |

These projects helped shape the implementation and the test plan. Their source is not included here, and their appearance in this list does not imply endorsement. The project records its implementation references, protocol sources, and licensing notes separately.

## LICENSE ##

Copyright (c) 2026 Supratim Sanyal of SANYALnet Labs.
Proprietary rights reserved except as expressly licensed.

Attribution is required: "Based on original work by Supratim Sanyal of
SANYALnet Labs."

See [LICENSE](LICENSE) for full terms, warranty disclaimer, termination, patent,
trademark, and governing-law provisions.
