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
- Acceptance concurrency is isolated by run/scenario instead of globally by architecture: E1-E4, independent references and interop suites can use separate hosted runners concurrently. Exact-SHA and parent-run binding are unchanged, so parallelism does not weaken candidate identity.

## Phase 4 entry

Routing codecs, route state, update ingestion, routing update transmission and Ethernet forwarding are implemented. Route insertion is race-safe under concurrent withdrawal without allocating on ordinary updates; peer hellos refresh all candidate expiries for that adjacency, while adjacency loss still withdraws every candidate. Short and long Phase IV data headers are parsed with deterministic vectors. Routing V2.0 reserved fields are ignored on receive and preserved when a long data packet is forwarded without format translation; the future-version bit and invalid long-header address prefixes are rejected. Routers forward by L1 node or L2 area lookup, require the incoming link source to be an UP adjacency, emit canonical Ethernet long-data headers, preserve RQR/RTS on successful forwarding, increment visit count, refuse ordinary forwarding at visit 31, and allow RTS traffic through visit 62. Unreachable or aged RQR traffic is converted to RTS with swapped Routing Layer endpoints, forced IE=0, and routed back toward the source. Ordinary forwarding preserves IE only for same-circuit long-data traffic; short-data conversion and cross-circuit forwarding clear it. Routers advertise current L1/L2 best-route vectors after a one-second change holdoff and every 180 seconds; L1 uses 64-node batches and L2 advertises areas 1-63 to the Phase IV broadcast groups. L2 attachment is reflected in L1 destination 0, and L1 routers forward cross-area traffic through the learned destination-0 route. The independent interop PCAP gate validates emitted candidate routing packets, including checksum, segment ranges, source, multicast target and self metric, while tolerating reserved fields on receive per Routing V2.0 section 10.2. Routing receive dispatch now classifies L1/L2 packets by the defined low flag nibble so reserved upper control bits do not suppress otherwise valid updates. L2 input accepts both All-Routers and All-Level-2-Routers, matching pinned Route20/PyDECnet behavior, and candidate L2 output is gated on both multicast targets. The E2 harness runs endnode 31.70 -- router 31.72 -- endnode 31.71 across two isolated LANs, checks bidirectional short-to-long forwarding with forwarded visit=1, proves visit=31 packets do not cross the router, and requires bidirectional unreachable RQR packets to return as canonical RTS long-data packets. E3 adds routers 31.72/31.73 on both LANs: 31.73 wins DR at higher priority, is deliberately shut down, endnodes must converge to 31.72, and packet captures distinguish pre-failure forwarding through 31.73 from post-failure forwarding through 31.72. Exact-head acceptance dispatch now includes both E1 and E2 VM runs; the workflow retains the policy-required explicit E1 lab invocation while selecting E2 directly.

## Next action

Candidate `f3035cfd1e994764c1983dc7419ccc12e726ef12` passed build/project-state/reference gates and amd64 E1. ARM64 E1 guest behavior passed through restart/recovery, but the controller missed the very short initial INIT in its 250 ms polling; PCAP independently recorded a router hello omitting the peer from the RS list. The controller now treats either guest-observed INIT or an unlisted-then-listed router-hello sequence as valid evidence; unlisted-only bootstrap traffic is explicitly insufficient. Route insertion and learned-route lifetime were hardened after review; insertion uses a lock/recheck path and hello refresh extends all routes through the live peer. E4 adds a six-VM/three-LAN two-area path: endnode -> preferred L1 -> local L2 -> remote L2 -> remote endnode, proving learned L1 destination 0 and L2 area routing in both directions. Run exact-head E1/E2/E3/E4 acceptance and emitted-routing interop on amd64/ARM64. Retained ARM64 E3 evidence showed only DN70 pre-failure traffic raced DN71 boot; DN71 pre-failure and both post-failure directions were already correct. E3 now waits 20 seconds after primary attachment before endpoint probes and holds the preferred router 30 seconds after both endpoint adjacencies exist. E3 now stages both routers before endpoints, waits explicit router READY markers and uses a 600-second minimum controller window with ten pre/post probes. E4 READY markers are emitted by both L1 and L2 router roles. ARM64 E4 retained evidence showed endpoint probes preceding L2 router readiness; E4 now stages router boot first, waits explicit per-router READY markers plus ten seconds of route convergence, then starts endpoints. ARM64 E2/E4 controller semantics were corrected from waiting for router self-PASS to endpoint-evidence completion with routers required alive; E2/E4 minimum controller windows are 480/720 seconds and router teardown is controller-owned. E3 failure timing is adjacency-driven rather than wall-clock driven; E4 router lifetimes are 120 seconds so six-guest boot skew cannot remove the path before endpoint probes. The prior amd64 E2 failure was a concrete harness race: DN72 shut down almost simultaneously with DN70 reaching adjacency UP, so DN70's probes had no live router. DN72 now remains alive 120 seconds. E2 endpoints emit ten probes because the retained failure PCAP showed DN71 probes 1-2 occurring before DN70's direct route existed; acceptance still requires at least five forwarded packets in each direction. The L1/L2 route-update snapshots are module-static rather than a >2KB workqueue stack frame. Do not reopen Phase 3 behavior without concrete regression evidence.
