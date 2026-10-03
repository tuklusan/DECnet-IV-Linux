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

# DECnet Phase IV kernel module

This directory contains the out-of-tree native DECnet Phase IV kernel implementation.

The current module provides:

- load/unload as `decnet_iv.ko`, configurable node identity and the versioned management/control UAPI;
- native DEC DNA Routing Ethernet framing, Phase IV logical MAC handling, router/endnode hello generation and parsing, per-interface adjacency state, expiry/recovery and designated-router behavior;
- endnode, Level 1 and Level 2 route selection/forwarding with route aging, metrics, multi-area forwarding and visit/hop protection;
- NSP connection establishment/teardown, segmentation/reassembly, independent data/other-data sequencing, ACK/NAK handling, retransmission/timers, flow control, interrupts/OOB and bounded connection/queue resources;
- native `AF_DECnet` sockets for `SOCK_SEQPACKET` and `SOCK_STREAM`, including blocking/nonblocking connect, bind/getname, listener/backlog/accept, poll wakeups, orderly/aborted close and stream short-read/`MSG_WAITALL` compatibility;
- classic `DNPROTO_NSP` options used by DECnet/Linux applications: `DSO_CONACCESS`, `DSO_CONDATA`, `DSO_DISDATA`, `DSO_LINKINFO`, `DSO_ACCEPTMODE`, `DSO_CONACCEPT` and `DSO_CONREJECT`;
- Session Control object-number/name dispatch and connect/accept/reject optional-data handling;
- `/dev/decnet_iv` as the diagnostic/control endpoint.

DECnet applications use the native socket interface; the character device is for diagnostics/control.

