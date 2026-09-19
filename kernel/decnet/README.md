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

This directory contains the fresh out-of-tree DECnet Phase IV kernel implementation.

The retained bootstrap provides:

- load/unload as `decnet_iv.ko`;
- default identity 31.70 / DN70, configurable through module parameters and the versioned control UAPI;
- receive registration for DEC DNA Routing EtherType `0x6003`;
- receive frame/byte counters;
- `/dev/decnet_iv` as a bootstrap diagnostic/control endpoint.

Phase 3 adds native DECnet Ethernet initialization: standard Phase IV address/MAC handling, router and endnode hello parsing/generation, periodic hello transmission, per-interface adjacency state and listen-time expiry, designated-router selection, extended counters and adjacency inspection through UAPI version 2.

Phase 5 registers a native `AF_DECnet` / `SOCK_SEQPACKET` family backed by the in-kernel NSP connection table. The first socket boundary supports bind/getname, outbound connect by DECnet node plus object number/name, blocking and nonblocking connect, record send/receive with NSP segmentation/reassembly, poll wakeups, full shutdown and orderly close. Listener/accept, interrupt/OOB delivery, classic DECnet socket options and stream mode remain ordered Phase 5 follow-up work.

The character device remains the diagnostic/control endpoint; DECnet applications use the native socket interface.
