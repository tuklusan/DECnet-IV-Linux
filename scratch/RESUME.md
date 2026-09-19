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

Phase 5 is active. NSP wire/state primitives now have a kernel connection foundation: validated CI/CD/CR/CC/RUN/DI transitions, bounded connection allocation with generation-spaced local link IDs, bounded retransmit queues, contiguous transmit sequencing, cumulative prefix ACK retirement and due-retransmit lookup. Local Routing Layer delivery now enters NSP on endnodes and routers; CI/RCI creates or matches incoming links, remote node/link identity is checked, and expected receive sequence advances modulo 4096. Outbound NSP now has deterministic local long-data encapsulation, router route-table selection, endnode router-adjacency selection, loopback delivery and a validated NSP transmit entry point. CI/CD receive mapping now learns the remote link identifier from CC/reject traffic; data/other sequence space starts at one; cumulative ACK retirement is restricted to the outstanding contiguous window and NAK is not retired as ACK. NSP data and other-data subchannels now have independent transmit/receive sequence spaces, retransmit selection and cumulative ACK handling, including cross-subchannel XACK retirement regardless of optional ACK-field position. The follow-up build regression from stale local cross-channel temporaries is corrected on main. Kernel NSP timers now enforce connection-establishment expiry, response retransmission limits and inactivity keepalive generation; valid RUN traffic rearms inactivity. Outbound logical-link operations now include CI generation with RCI retry, new/duplicate incoming CI acknowledgment, CC accept, DI reject/disconnect with disconnect confirmation, immediate data/other ACKs and sequenced data transmission. NSP now has bounded per-link out-of-order and ready receive queues, contiguous reorder drain, data-window backpressure, Link Service XON/XOFF/interrupt-credit handling, interrupt transmission and dequeue metadata for upper layers. The Phase 5 logical-link/receive-queue build follow-up removes a userspace unit assertion against the kernel-private MSS constant; protocol behavior is unchanged. NSP negative acknowledgements now follow the Digital NSP 4.0.1 rules: a valid data NAK cumulatively acknowledges NUMBER and immediately retransmits from NUMBER+1, while an other-data NAK for the outstanding other-data sequence retransmits that message without retiring it. Cross-subchannel XNAK uses the same rules after channel selection. Phase IV delayed acknowledgement is implemented with the NSP 4.0.1 suggested 3-second ACK delay for in-order packets that permit delay; duplicates force an immediate cumulative ACK, while future out-of-order packets stay cached without acknowledging missing sequence space. The Linux-facing socket compatibility UAPI is now defined with classic DECnet protocol numbers, sockaddr_dn, connect/disconnect/access/link option layouts and DSO constants, with host unit coverage. A bounded NSP normal-data reassembly API now preserves BOM/EOM message boundaries, sequence-ordered segments and the 65023-byte DECnet/Linux message ceiling while keeping interrupt delivery independent. Exact-SHA acceptance of the E4 convergence-race fix at `c96b715a1e4adcfb8d36f2675d4538c98ffe2e94` completed green: Repository Policy `35417101451`, Build Bootstrap `35417116930`, Project State Gate `35417117771`, External Reference Baselines `35417118818`, E1 `35417119749`, E2 `35417120797`, E3 `35417121525`, E4 `35417122358`, and Independent Ethernet Interoperability `35417123229`; all eight interop jobs passed. The native `AF_DECnet` / `SOCK_SEQPACKET` family is now registered against NSP with validated `sockaddr_dn` bind/getname, outbound object-number/name connect selectors, blocking/nonblocking connect, record segmentation/reassembly, poll readiness and NSP-to-socket waiter notification. Linux 6.8 build of the initial socket-family commit exposed an unavailable `copy_to_iter_full` helper; the follow-up uses the supported `copy_to_iter` byte-count contract and removes the now-unused NSP receive local. Next rerun exact-SHA acceptance, then complete inbound listen/accept, interrupt/OOB delivery, classic DECnet socket options/access/connect data, stream mode, socket lifecycle negatives and dedicated independent NSP socket interoperability. Do not reopen Phase 4 without concrete regression evidence.
