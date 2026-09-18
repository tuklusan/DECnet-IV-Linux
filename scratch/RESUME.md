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

# Scratch Resume Index

## Current checkpoint

Phase 4 is active on `main`. Phase 3 is frozen at tag `PHASE-3-COMPLETE` on commit `ae1bcb82a1539ccadda0661664205e360bd760b7`; its accepted protocol candidate was `608ed2077e9651d6c050f4fc790d538b2d8ee529`.

The final Phase 3 acceptance set was green: Repository Policy `35343324826`, Build Bootstrap `35343357536`, Project State Gate `35343359444`, External Reference Baselines `35343361139`, Python QEMU VM Lab `35343362922`, and Independent Ethernet Interoperability run `35343364812`. The interoperability matrix passed all eight amd64/ARM64 Route20/PyDECnet routing/endnode role jobs.

Temporary Phase 3 Route20 crash instrumentation and the temporary tagging workflow are gone. Only reusable infrastructure remains: the fixed Route20 pin, PyDECnet peer, exact-source candidate/reference image derivation, direct-QEMU lab, 60-second post-boot reference settle policy, bounded readiness/failure handling, packet capture and compact evidence.

## Stable infrastructure

- Route20: `ea144b2e9978c7d216bc7c171b22fe47ca555567`.
- PyDECnet live: `a7194be8d72dea6f9eb4f77083f056f53e80df58`.
- PyDECnet tests: `9a844987bf3a1450632dee8d37e60a23a453bad3`.
- LinuxDECnet: `ff39eef045d1e4b7b72a3d40111e89c07a473398`.
- SIMH: `5b73b1032b52d19bf80752ea4d9cbbdc92e7b5e0`.
- Foundations: `outer-v2-<arch>-<foundation-fingerprint>`.
- VM runtime: fresh disposable qcow2 overlays under short `/tmp/dniv-*` paths.
- Ordinary lab addressing: area 31, nodes 70-79.
- Reference guests: reach `multi-user.target`, idle 60 seconds, then start the peer.
- READY bounds: amd64 180s, ARM64 360s.
- E1 controller bounds: amd64 300s, ARM64 360s.
- Remote branch invariant: only `refs/heads/main`.

## Phase 4 entry

Routing codecs, route state, update ingestion and Ethernet forwarding are implemented. Route insertion is race-safe under concurrent withdrawal without allocating on ordinary updates; peer hellos refresh all candidate expiries for that adjacency, while adjacency loss still withdraws every candidate. Short and long Phase IV data headers are parsed with deterministic vectors and reject reserved flag/visit bits, nonzero reserved long-header fields, and invalid long-header address prefixes. Routers forward by L1 node or L2 area lookup, require the incoming link source to be an UP adjacency, rewrite only the Ethernet next hop, preserve the Routing Layer source/destination, increment visit count, and refuse forwarding at visit 31. The E2 harness now runs endnode 31.70 -- router 31.72 -- endnode 31.71 across two isolated LANs, checks bidirectional forwarding with forwarded visit=1, and proves visit=31 packets do not cross the router. Exact-head acceptance dispatch now includes both E1 and E2 VM runs; the workflow retains the policy-required explicit E1 lab invocation while selecting E2 directly.

## Next action

Candidate `f3035cfd1e994764c1983dc7419ccc12e726ef12` passed build/project-state/reference gates and amd64 E1. ARM64 E1 guest behavior passed through restart/recovery, but the controller missed the very short initial INIT in its 250 ms polling; PCAP independently recorded a router hello omitting the peer from the RS list. The controller now treats either guest-observed INIT or an unlisted-then-listed router-hello sequence as valid evidence; unlisted-only bootstrap traffic is explicitly insufficient. Route insertion and learned-route lifetime were hardened after review; insertion uses a lock/recheck path and hello refresh extends all routes through the live peer. Rerun exact-head E1/E2 acceptance on the new main, then proceed to E3 alternate-path convergence. Do not reopen Phase 3 behavior without concrete regression evidence.
