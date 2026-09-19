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

NSP wire/state primitives, validated connection-state transitions, a bounded kernel connection table, generation-spaced local link allocation and bounded retransmit queues are implemented. Local Routing Layer delivery now enters NSP on both endnodes and routers; CI/RCI allocates or matches incoming links, established packets are bound to remote node/link identity, basic CI/CD/CR/CC/RUN/DI receive transitions are enforced, expected receive sequence advances modulo 4096, and retransmit queues require contiguous transmit sequence with cumulative prefix ACK retirement. Outbound NSP now has a local Routing Layer path: deterministic locally-originated long-data encapsulation, router route-table selection, endnode router-adjacency selection, loopback delivery, and a validated NSP transmit entry point. NSP receive mapping now also follows the Phase IV CI/CD rule that learns the remote link identifier from CC/reject traffic, starts data/other sequence space at one, rejects acknowledgements outside the outstanding contiguous window and never treats NAK as a positive cumulative ACK. NSP data and other-data subchannels now have independent transmit/receive sequence spaces, retransmit selection and cumulative ACK handling, including cross-subchannel XACK retirement regardless of which optional ACK field carries it. The follow-up build regression from stale local cross-channel temporaries is corrected on main. Kernel NSP timers now enforce the 30-second connection-establishment bound, drive five-attempt response retransmission at the baseline response interval, and emit Phase IV no-change Link Service keepalives after the 300-second inactivity interval; valid RUN traffic rearms inactivity. Outbound logical-link operations now include CI generation with RCI retry, new/duplicate incoming CI connection acknowledgment, CC accept, DI reject/disconnect with disconnect confirmation, immediate data/other acknowledgments and sequenced data transmission with retransmission. NSP now has bounded per-link out-of-order and ready receive queues, contiguous reorder drain, data-window backpressure, Link Service XON/XOFF/interrupt-credit handling, interrupt transmission and dequeue metadata for upper layers. The Phase 5 logical-link/receive-queue build follow-up removes a userspace unit assertion against the kernel-private MSS constant; protocol behavior is unchanged. NSP negative acknowledgements now follow the Digital NSP 4.0.1 rules: a valid data NAK cumulatively acknowledges NUMBER and immediately retransmits from NUMBER+1, while an other-data NAK for the outstanding other-data sequence retransmits that message without retiring it. Cross-subchannel XNAK uses the same rules after channel selection. Phase IV delayed acknowledgement is implemented with the NSP 4.0.1 suggested 3-second ACK delay for in-order packets that permit delay; duplicates force an immediate cumulative ACK, while future out-of-order packets stay cached without acknowledging missing sequence space. The Linux-facing socket compatibility UAPI is now defined with classic DECnet protocol numbers, sockaddr_dn, connect/disconnect/access/link option layouts and DSO constants, with host unit coverage. A bounded NSP normal-data reassembly API now preserves BOM/EOM message boundaries, sequence-ordered segments and the 65023-byte DECnet/Linux message ceiling while keeping interrupt delivery independent. Exact-SHA acceptance of the E4 convergence-race fix at `c96b715a1e4adcfb8d36f2675d4538c98ffe2e94` is green: Repository Policy `35417101451`, Build Bootstrap `35417116930`, Project State Gate `35417117771`, External Reference Baselines `35417118818`, E1 `35417119749`, E2 `35417120797`, E3 `35417121525`, E4 `35417122358`, and Independent Ethernet Interoperability `35417123229`; all eight interop jobs completed successfully. Phase 5 now registers the native `AF_DECnet` / `SOCK_SEQPACKET` family against NSP. The initial boundary validates classic `sockaddr_dn` addresses, supports local bind/getname, emits outbound Session end-user selectors for object number/name, drives blocking or nonblocking NSP connect, segments record writes, reassembles normal-data records, reports poll readiness, and wakes socket waiters from NSP state/data/ACK events. Listener/accept, interrupt/OOB delivery, classic DECnet socket options/access/connect data, stream mode and dedicated independent NSP socket interoperability remain next. The first socket-family build exposed a Linux 6.8 iterator API mismatch in receive copyout; the follow-up uses the supported `copy_to_iter` byte-count contract. A second build caught that the cleanup removed the sequence-order local from the wrong NSP helper; this follow-up restores it in `dniv_nsp_rx_sequence_locked` and removes only the truly unused receive local. Exact-SHA acceptance of the socket-family build follow-up at `dff43abd34cb77cb65fd03d92c1e49fab1e55304` is green: Repository Policy `35420342660`, Build Bootstrap `35420378234`, Project State Gate `35420379715`, External Reference Baselines `35420380754`, E1 `35420381818`, E2 `35420382772`, E3 `35420383606`, E4 `35420384814`, and Independent Ethernet Interoperability `35420385869`; all amd64/ARM64 jobs passed. The next candidate adds direct independent NSP/socket proof: every PyDECnet interoperability role now drives native `AF_DECnet` / `SOCK_SEQPACKET` through built-in object 25 (MIRROR) with records spanning single-segment, MSS-boundary and multi-segment sizes, and packet-capture validation requires bidirectional NSP traffic. The first MIRROR-test commit preserved the intended content but accidentally cleared executable bits on the lab entry scripts; Repository Policy run `35422200657` caught the mode regression before acceptance dispatch. This follow-up restores the executable modes without changing protocol behavior. Preserve the exact-green Phase 4 candidate and extend independent interoperability as NSP-capable peer coverage becomes available.
