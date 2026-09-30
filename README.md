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

A minimal modern Linux distribution with native DECnet Phase IV networking.

Based on original work by Supratim Sanyal of SANYALnet Labs. See `LICENSE` for the governing terms.

## Project goals

- Build DECnet Phase IV as a fresh out-of-tree Linux kernel module, not the removed legacy stack.
- Provide a versioned kernel/userspace ABI and the useful DECnet/Linux tool environment.
- Build reproducible x86_64 and aarch64 images.
- Test on independent VMs, independent peers, routed/distributed VDE2 and MULTINET topologies, faults and stress.

## Current baseline

Phases 1-4 are complete. The kernel stack has native DECnet Ethernet initialization, endnode/L1/L2 routing, convergence and multi-area forwarding on amd64 and ARM64.

Phase 5 is active. NSP transport and native `AF_DECnet` / `SOCK_SEQPACKET` support include outbound connections, record segmentation/reassembly, inbound listener/backlog/accept handling and independent PyDECnet MIRROR/listener interoperability. Exact-SHA acceptance is green through `6aa5eec808e45c0477bb7ea87b9ff76e0bc0859b`.

Local/rootless VDE2 and MULTINET TCP transports have separate green proofs. Cross-runner VDE2 joining and secret-backed Area-31 integration remain planned distributed-lab work; they do not replace exact-SHA local acceptance.

## Layout

- `include/uapi/` — versioned kernel/userspace ABI
- `kernel/decnet/` — native DECnet Phase IV kernel module
- `userspace/` — DECnet command-line tools and libraries
- `image/ubuntu-base/` — pinned rootfs metadata and deterministic image builder
- `tests/` — unit and interoperability tests
- `docs/` — architecture, roadmap, test lab, handover and continuity state
- `references/` — normative DECnet specifications, pinned implementation references and source-of-truth rules
- `.github/workflows/` — repository, build, reference, continuity and VM gates

Start with `docs/HANDOVER.md` when resuming work. It points to the authoritative project state and ordered roadmap.
