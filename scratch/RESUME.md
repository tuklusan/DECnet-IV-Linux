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

Annotated tag `PHASE-4-COMPLETE` is verified on closure commit `571333bfd7aaa8b2fcc88715c1d61442af151f3c`; the temporary tag workflow has been removed.

Phase 4 is complete on exact protocol candidate `6c185b6d01f8a57ee9f0ea6a6c37d7112ddb77d2`; Phase 5 is active on `main`. Phase 3 remains frozen at tag `PHASE-3-COMPLETE` on commit `ae1bcb82a1539ccadda0661664205e360bd760b7`.

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

## Phase 4 closure

Exact protocol candidate `6c185b6d01f8a57ee9f0ea6a6c37d7112ddb77d2` closed Phase 4 on 2026-09-18. Repository Policy `35393330920`, Build Bootstrap `35393363966`, Project State Gate `35393366433`, External Reference Baselines `35393368425`, E1 `35393370633`, E2 `35393372626`, E3 `35393374453`, E4 `35393376465`, and Independent Ethernet Interoperability `35393378666` all completed successfully. E1-E4 passed on amd64 and ARM64 and the Route20/PyDECnet interoperability matrix was green.

Phase 4 delivered routing codecs/checksums, adjacency-backed L1/L2 route state, metrics/aging, triggered and periodic routing advertisements, deterministic best-route selection, short/long data forwarding, visit-count loop prevention, return-to-sender behavior, L1 destination-0 attached-area semantics, multi-LAN convergence and multi-area forwarding.

## Next action

Phase 5 is active. NSP wire/state primitives are now present with canonical project headers: ACK Data/Other/Connect, Data, Interrupt, Link Service, CI/RCI, CC, DI/DC parsing/building, optional ACK qualifiers, 12-bit sequence wrap/order helpers and baseline NSP timer constants, all tied to exact PyDECnet packet vectors. Next implement kernel connection allocation/state transitions and retransmit queues, then flow control and native socket/UAPI integration. Do not reopen Phase 4 without concrete regression evidence.
