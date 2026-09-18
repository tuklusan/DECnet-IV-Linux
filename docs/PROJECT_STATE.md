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

Complete on exact protocol candidate `6c185b6d01f8a57ee9f0ea6a6c37d7112ddb77d2`. Endnode behavior, Level 1/Level 2 routing, routing/forwarding databases, metrics, route aging, triggered/periodic routing updates, visit-count enforcement, return-to-sender handling, convergence, forced-router, alternate-path and multi-area topologies are implemented and accepted on amd64 and ARM64.

Implementation order:

1. deterministic routing-packet codecs, checksums and malformed-input rejection — complete;
2. kernel route-state primitives, metrics and aging — complete;
3. adjacency-backed routing update ingestion — complete;
4. forwarding and visit-count/loop prevention — complete;
5. L1/L2 routing update transmission — complete baseline: one-second triggered full vectors plus 180-second broadcast refresh;
6. E2 two-LAN forced-router topology — complete;
7. E3 alternate-path convergence — complete;
8. E4 multi-area L1/L2 behavior — complete;
9. independent Route20/PyDECnet routing interoperability on amd64 and ARM64 — complete.

## Current infrastructure

| Field | Current value |
| --- | --- |
| Protocol phase | Phase 5 |
| Working ref | `main` only |
| Remote branches | only `refs/heads/main` |
| Phase 3 tag | `PHASE-3-COMPLETE` |
| Phase 3 tag commit | `ae1bcb82a1539ccadda0661664205e360bd760b7` |
| Phase 4 accepted protocol candidate | `6c185b6d01f8a57ee9f0ea6a6c37d7112ddb77d2` |
| Phase 4 closure commit | `571333bfd7aaa8b2fcc88715c1d61442af151f3c` |
| Phase 4 tag | `PHASE-4-COMPLETE` |
| Route20 pin | `ea144b2e9978c7d216bc7c171b22fe47ca555567` |
| VM lifecycle | direct QEMU/QMP |
| Persistent VM state | source-independent amd64/arm64 foundations |
| Candidate/reference images | disposable |
| Reference settle interval | 60 seconds after `multi-user.target` |
| Reference READY bounds | amd64 180s; ARM64 360s |
| E1 controller budget | amd64 300s; ARM64 360s |
| Compact evidence retention | 30 days maximum |

## Resume point

Annotated tag `PHASE-4-COMPLETE` is verified on closure commit `571333bfd7aaa8b2fcc88715c1d61442af151f3c`. The temporary tag workflow has been removed.

Phase 4 is closed on exact protocol candidate `6c185b6d01f8a57ee9f0ea6a6c37d7112ddb77d2`. Its exact-SHA acceptance completed green on 2026-09-18: Repository Policy `35393330920`, Build Bootstrap `35393363966`, Project State Gate `35393366433`, External Reference Baselines `35393368425`, E1 `35393370633`, E2 `35393372626`, E3 `35393374453`, E4 `35393376465`, and Independent Ethernet Interoperability `35393378666`. E1-E4 passed amd64 and ARM64; the interoperability run completed the full Route20/PyDECnet routing matrix successfully.

### Phase 5

Active. Implement NSP transport and the DECnet socket ABI without reopening Phase 4 unless concrete regression evidence requires it.

Initial NSP foundation is implemented and repository-policy headers are canonical: deterministic Phase IV NSP packet codecs for ACK Data/Other/Connect, data segments, interrupt, Link Service, CI/RCI, CC, DI and DC; optional ACK/NAK/XACK/XNAK decoding; 12-bit sequence arithmetic; malformed-input rejection; and baseline response/connect/inactivity timer constants.

## Next action

NSP wire/state primitives, validated connection-state transitions, a bounded kernel connection table, generation-spaced local link allocation and bounded retransmit queues are implemented. Local Routing Layer delivery now enters NSP on both endnodes and routers; CI/RCI allocates or matches incoming links, established packets are bound to remote node/link identity, basic CI/CD/CR/CC/RUN/DI receive transitions are enforced, expected receive sequence advances modulo 4096, and retransmit queues require contiguous transmit sequence with cumulative prefix ACK retirement. Next add outbound Routing Layer transmission for NSP control/data, response/connect/inactivity timers and complete data/interrupt flow control, then expose the native socket/UAPI boundary. Preserve the exact-green Phase 4 candidate and extend independent interoperability only as NSP-capable peer coverage becomes available.
