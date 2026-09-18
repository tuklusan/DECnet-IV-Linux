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

# Project State

This is the authoritative continuity record for DECnet-IV-Linux. Read `docs/HANDOVER.md`, this file, `scratch/RESUME.md`, `docs/ROADMAP.md`, `docs/ARCHITECTURE.md`, `docs/TEST_LAB.md` and `docs/PRE_PRODUCTION_TEST.md` before changing protocol, image or acceptance behavior.

## Goal

Build a complete native DECnet Phase IV stack for maintained Linux as an out-of-tree kernel module plus DECnet/Linux userspace. Deliver reproducible x86_64/aarch64 images and prove behavior against independent implementations and later real DEC systems.

## References and licensing

Preferred exact reference pins are Route20 `ea144b2e9978c7d216bc7c171b22fe47ca555567`, PyDECnet live `a7194be8d72dea6f9eb4f77083f056f53e80df58`, PyDECnet tests `9a844987bf3a1450632dee8d37e60a23a453bad3`, LinuxDECnet `ff39eef045d1e4b7b72a3d40111e89c07a473398`, and SIMH `5b73b1032b52d19bf80752ea4d9cbbdc92e7b5e0`.

Digital DNA Phase IV functional specifications are normative. PyDECnet and Route20 are independent implementation cross-checks; LinuxDECnet is the Linux ABI/userspace compatibility reference; SIMH plus genuine DEC operating systems are interoperability oracles. Third-party material retains its original license.

## Repository discipline

- Work directly on `main`; no feature branches.
- The remote branch invariant is exactly `refs/heads/main`.
- Every substantive commit updates this file and `scratch/RESUME.md` together.
- Acceptance applies only to one exact unchanged `main` commit.
- Hosted jobs are bounded and isolated per GitHub-hosted runner. Acceptance no longer serializes independent architectures/scenarios globally: E1-E4 modes may execute concurrently, all eight interop matrix jobs may execute concurrently, and independent reference jobs may execute concurrently. Exact-SHA/parent binding remains unchanged.
- Persistent VM input is limited to verified source-independent architecture foundations.
- Exact candidate/reference images, VM overlays and QMP sockets are disposable.
- Compact evidence retention is at most 30 days.

## Phase status

### Phase 1

Complete: UAPI v2, `decnet_iv.ko`, configurable identity, Routing Layer EtherType handling/counters, `dnctl`, centralized addressing, unit tests and native x86_64/aarch64 builds.

### Phase 2

Complete: pinned Ubuntu Base 26.04.1 amd64/arm64 foundations, deterministic image construction, exact guest kernel/module/userspace build, direct kernel/initrd boot, independent VMs, packet capture and serial evidence.

### Phase 3

Complete. The accepted Phase 3 baseline is tagged `PHASE-3-COMPLETE` at commit `ae1bcb82a1539ccadda0661664205e360bd760b7`. Its exact protocol candidate `608ed2077e9651d6c050f4fc790d538b2d8ee529` passed repository policy, native amd64/ARM64 builds, project state, pinned reference baselines, both E1 VM architectures and all eight amd64/ARM64 Route20/PyDECnet interoperability jobs in run `35343364812`.

Phase 3-only Route20 crash instrumentation has been removed. The fixed Route20 pin, independent-peer harness, post-boot 60-second reference settling, bounded readiness, failure logging, E1 coverage and source-independent VM foundations remain as reusable infrastructure.

### Phase 4

Active. Deliver endnode behavior, Level 1 and Level 2 routing, route/forwarding databases, metrics, visit-count enforcement, route aging, convergence and multi-LAN VM topologies.

Implementation order:

1. deterministic routing-packet codecs, checksums and malformed-input rejection — complete;
2. kernel route-state primitives, metrics and aging — complete;
3. adjacency-backed routing update ingestion — complete;
4. forwarding and visit-count/loop prevention — complete;
5. L1/L2 routing update transmission — complete baseline: one-second triggered full vectors plus 180-second broadcast refresh;
6. E2 two-LAN forced-router topology — harness implemented, acceptance pending;
7. E3 alternate-path convergence — harness implemented, acceptance pending;
8. E4 multi-area L1/L2 behavior — harness implemented, acceptance pending;
9. independent Route20/PyDECnet routing interoperability on amd64 and ARM64.

## Current infrastructure

| Field | Current value |
| --- | --- |
| Protocol phase | Phase 4 |
| Working ref | `main` only |
| Remote branches | only `refs/heads/main` |
| Phase 3 tag | `PHASE-3-COMPLETE` |
| Phase 3 tag commit | `ae1bcb82a1539ccadda0661664205e360bd760b7` |
| Route20 pin | `ea144b2e9978c7d216bc7c171b22fe47ca555567` |
| VM lifecycle | direct QEMU/QMP |
| Persistent VM state | source-independent amd64/arm64 foundations |
| Candidate/reference images | disposable |
| Reference settle interval | 60 seconds after `multi-user.target` |
| Reference READY bounds | amd64 180s; ARM64 360s |
| E1 controller budget | amd64 300s; ARM64 360s |
| Compact evidence retention | 30 days maximum |

## Resume point

Phase 4 is active on main. Routing codecs, route-state primitives, adjacency-backed routing update ingestion, L1/L2 routing update transmission, native Ethernet forwarding, visit-count enforcement and the E2 forced-router harness are implemented. Route candidate insertion is race-safe, existing candidates update without allocation, and every valid peer hello refreshes the expiry of all routes learned through that adjacency. E2 exact-SHA amd64/ARM64 acceptance is the current gate.

## Next action

Phase 4 routing codecs, route state, adjacency-backed update ingestion and native Ethernet data forwarding are implemented. Short/long data headers follow Routing V2.0 reserved-field semantics: reserved fields are ignored on receive, long-data reserved fields are preserved on long-to-long forwarding, short-format reserved fields dropped by translation are not propagated, while the version bit and required AA-00-04-00 long-header address prefixes remain validated; forwarding uses L1/L2 route lookup, only UP-adjacency link sources are accepted, and Ethernet forwarding emits canonical long-data headers. Normal traffic stops at visit 31; return-to-sender traffic uses the Phase IV doubled ceiling of 62. Unreachable or aged RQR packets are converted to RTS in-kernel by swapping Routing Layer source/destination, clearing RQR/IE, preserving payload/visit count, and forwarding back toward the source. Generated RTS packets force IE clear even when the return route exits the same Ethernet circuit. Ordinary forwarding preserves IE only when an incoming long-data packet remains on the same Ethernet circuit; short-data conversion and cross-circuit forwarding emit IE=0, matching the pinned PyDECnet behavior. The E2 three-VM/two-LAN forced-router harness is implemented with bidirectional payload evidence, canonical short-to-long forwarding, exact forwarded visit=1 checks, max-visit negative checks, and bidirectional unreachable RQR -> RTS wire evidence. ARM64 E1 on candidate `f3035cfd1e994764c1983dc7419ccc12e726ef12` completed the guest protocol sequence but missed the transient initial INIT in 250 ms guest polling; retained PCAP contained the router hello without the reciprocal RS entry. E1 now accepts direct wire evidence only when an unlisted router hello is followed later by a reciprocal listing, while retaining the guest marker path. A policy regression rejects unlisted-only and listed-only captures. A route-update concurrency race found during review is fixed with a lock/recheck insertion path. Existing candidates update without allocation, newly inserted candidates recheck after allocation, and peer hellos refresh every candidate learned through that adjacency so live routes do not age out while their neighbor remains live. Routers now advertise the selected L1/L2 vectors to UP router peers: route-state generation changes are coalesced to a one-second trigger, L1 is emitted in 64-node segments, L2 covers areas 1-63, and full broadcast refresh runs every 180 seconds. L2 routers advertise L1 destination 0 as reachable only while attached to another area; L1 routers use learned destination 0 as the next-area route for cross-area forwarding. Independent interop PCAP validation requires candidate L1/L2 updates with valid source IDs, checksum, segment bounds, multicast destination and zero self metric while accepting reserved control fields as Routing V2.0 requires. Receive classification masks routing control reserved flag bits before dispatch so such packets actually reach the routing parser; the future-version data flag remains unrecognized/dropped. L2 routing input accepts both Phase IV broadcast destinations used by the pinned references: All-Routers and All-Level-2-Routers; emitted L2 updates are required on both. E3 now has a four-VM/two-LAN convergence harness: endnodes first use the higher-priority router, that router is deliberately removed, both endnodes must converge to the surviving router, and pre/post payloads are wire-verified through the expected router. E4 now has a six-VM/three-LAN topology spanning areas 31 and 32: each area has an endnode, a preferred L1 router and an L2 router, with the L2 routers joined by a transit LAN. The wire gate requires the source L1 router to use learned destination 0, both L2 routers to carry the inter-area path, and destination delivery at visit count 3. Runtime identity change now quiesces both hello and routing-update workers before replacing Ethernet identity. Exact amd64/ARM64 E2/E3/E4 acceptance remains pending. E3 router teardown is now event-driven: the preferred router waits for both endnodes before its deliberate failure, while the standby waits for both endnodes plus preferred-router loss before its final convergence window. E4 L1/L2 routers remain alive 120 seconds to cover unsynchronized six-guest boot and route propagation. The first amd64 E2 execution on `32c5f0cf777f1832d9d74e053ef3210bcfd13ad0` exposed a harness lifetime race: the router powered off at ~67.6s while DN70 only reached router adjacency UP at ~67.3s, before DN70's forwarding probes. The E2 router lifetime is now 120 seconds, keeping the forwarding path alive through both endpoint evidence windows. The retained PCAP also showed DN71's first two probes preceded DN70 route availability; endpoints now emit ten probes while the host still requires at least five successfully forwarded packets per direction, making the gate prove steady-state forwarding without assuming simultaneous guest boot. The routing-update worker's L1/L2 snapshots moved from the kernel stack to static module storage, eliminating the observed 2360-byte stack-frame warning.
