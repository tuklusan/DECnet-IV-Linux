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
- Hosted jobs are bounded; protocol jobs use architecture-specific runner serialization.
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
5. E2 two-LAN forced-router topology — harness implemented, acceptance pending;
6. E3 alternate-path convergence;
7. E4 multi-area L1/L2 behavior;
8. independent Route20/PyDECnet routing interoperability on amd64 and ARM64.

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

Phase 4 is active on main. Routing codecs, route-state primitives, adjacency-backed routing update ingestion, native Ethernet forwarding, visit-count enforcement and the E2 forced-router harness are implemented. E2 exact-SHA amd64/ARM64 acceptance is the current gate.

## Next action

Phase 4 routing codecs, route state, adjacency-backed update ingestion and native Ethernet data forwarding are implemented. Short/long data headers are validated, forwarding uses L1/L2 route lookup, only UP-adjacency link sources are accepted, and visit count 31 is the loop-prevention ceiling. The E2 three-VM/two-LAN forced-router harness is implemented with bidirectional payload evidence, exact forwarded visit=1 checks and max-visit negative checks. The exact-head acceptance dispatcher now runs both E1 regression and E2; exact amd64/ARM64 E2 acceptance is still pending. The VM workflow keeps the existing source-independent foundation guard path explicit for both E1 and E2.
