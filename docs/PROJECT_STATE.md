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

Preferred exact reference pins are Route20 `a9ef7c0b7f875f0dd2e8abaf11213798a8e4474c`, PyDECnet live `295938c76c956a70957f4cf96b05685f555b2a18`, PyDECnet tests `9a844987bf3a1450632dee8d37e60a23a453bad3`, LinuxDECnet `ff39eef045d1e4b7b72a3d40111e89c07a473398`, and SIMH `5b73b1032b52d19bf80752ea4d9cbbdc92e7b5e0`.

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
| Route20 pin | `a9ef7c0b7f875f0dd2e8abaf11213798a8e4474c` |
| PyDECnet live pin | `295938c76c956a70957f4cf96b05685f555b2a18` |
| VM lifecycle | direct QEMU/QMP |
| Persistent VM state | source-independent amd64/arm64 foundations |
| Candidate/reference images | disposable |
| Reference settle interval | 60 seconds after `multi-user.target` |
| Reference READY bounds | amd64 180s; ARM64 600s |
| E1 controller budget | amd64 300s; ARM64 360s |
| Compact evidence retention | 30 days maximum |

## Resume point

Annotated tag `PHASE-4-COMPLETE` is verified on closure commit `571333bfd7aaa8b2fcc88715c1d61442af151f3c`. The temporary tag workflow has been removed.

Phase 4 is closed on exact protocol candidate `6c185b6d01f8a57ee9f0ea6a6c37d7112ddb77d2`. Its exact-SHA acceptance completed green on 2026-09-18: Repository Policy `35393330920`, Build Bootstrap `35393363966`, Project State Gate `35393366433`, External Reference Baselines `35393368425`, E1 `35393370633`, E2 `35393372626`, E3 `35393374453`, E4 `35393376465`, and Independent Ethernet Interoperability `35393378666`. E1-E4 passed amd64 and ARM64; the interoperability run completed the full Route20/PyDECnet routing matrix successfully.

### Phase 5

Active. Implement NSP transport and the DECnet socket ABI without reopening Phase 4 unless concrete regression evidence requires it.

Initial NSP foundation is implemented and repository-policy headers are canonical: deterministic Phase IV NSP packet codecs for ACK Data/Other/Connect, data segments, interrupt, Link Service, CI/RCI, CC, DI and DC; optional ACK/NAK/XACK/XNAK decoding; 12-bit sequence arithmetic; malformed-input rejection; and baseline response/connect/inactivity timer constants.

## Next action

NSP wire/state primitives, validated connection-state transitions, a bounded kernel connection table, generation-spaced local link allocation and bounded retransmit queues are implemented. Local Routing Layer delivery now enters NSP on both endnodes and routers; CI/RCI allocates or matches incoming links, established packets are bound to remote node/link identity, basic CI/CD/CR/CC/RUN/DI receive transitions are enforced, expected receive sequence advances modulo 4096, and retransmit queues require contiguous transmit sequence with cumulative prefix ACK retirement. Outbound NSP now has a local Routing Layer path: deterministic locally-originated long-data encapsulation, router route-table selection, endnode router-adjacency selection, loopback delivery, and a validated NSP transmit entry point. NSP receive mapping now also follows the Phase IV CI/CD rule that learns the remote link identifier from CC/reject traffic, starts data/other sequence space at one, rejects acknowledgements outside the outstanding contiguous window and never treats NAK as a positive cumulative ACK. NSP data and other-data subchannels now have independent transmit/receive sequence spaces, retransmit selection and cumulative ACK handling, including cross-subchannel XACK retirement regardless of which optional ACK field carries it. The follow-up build regression from stale local cross-channel temporaries is corrected on main. Kernel NSP timers now enforce the 30-second connection-establishment bound, drive five-attempt response retransmission at the baseline response interval, and emit Phase IV no-change Link Service keepalives after the 300-second inactivity interval; valid RUN traffic rearms inactivity. Outbound logical-link operations now include CI generation with RCI retry, new/duplicate incoming CI connection acknowledgment, CC accept, DI reject/disconnect with disconnect confirmation, immediate data/other acknowledgments and sequenced data transmission with retransmission. NSP now has bounded per-link out-of-order and ready receive queues, contiguous reorder drain, data-window backpressure, Link Service XON/XOFF/interrupt-credit handling, interrupt transmission and dequeue metadata for upper layers. The Phase 5 logical-link/receive-queue build follow-up removes a userspace unit assertion against the kernel-private MSS constant; protocol behavior is unchanged. NSP negative acknowledgements now follow the Digital NSP 4.0.1 rules: a valid data NAK cumulatively acknowledges NUMBER and immediately retransmits from NUMBER+1, while an other-data NAK for the outstanding other-data sequence retransmits that message without retiring it. Cross-subchannel XNAK uses the same rules after channel selection. Phase IV delayed acknowledgement is implemented with the NSP 4.0.1 suggested 3-second ACK delay for in-order packets that permit delay; duplicates force an immediate cumulative ACK, while future out-of-order packets stay cached without acknowledging missing sequence space. The Linux-facing socket compatibility UAPI is now defined with classic DECnet protocol numbers, sockaddr_dn, connect/disconnect/access/link option layouts and DSO constants, with host unit coverage. A bounded NSP normal-data reassembly API now preserves BOM/EOM message boundaries, sequence-ordered segments and the 65023-byte DECnet/Linux message ceiling while keeping interrupt delivery independent. Exact-SHA acceptance of the E4 convergence-race fix at `c96b715a1e4adcfb8d36f2675d4538c98ffe2e94` is green: Repository Policy `35417101451`, Build Bootstrap `35417116930`, Project State Gate `35417117771`, External Reference Baselines `35417118818`, E1 `35417119749`, E2 `35417120797`, E3 `35417121525`, E4 `35417122358`, and Independent Ethernet Interoperability `35417123229`; all eight interop jobs completed successfully. Phase 5 now registers the native `AF_DECnet` / `SOCK_SEQPACKET` family against NSP. The initial boundary validates classic `sockaddr_dn` addresses, supports local bind/getname, emits outbound Session end-user selectors for object number/name, drives blocking or nonblocking NSP connect, segments record writes, reassembles normal-data records, reports poll readiness, and wakes socket waiters from NSP state/data/ACK events. Listener/accept, interrupt/OOB delivery, classic DECnet socket options/access/connect data, stream mode and dedicated independent NSP socket interoperability remain next. The first socket-family build exposed a Linux 6.8 iterator API mismatch in receive copyout; the follow-up uses the supported `copy_to_iter` byte-count contract. A second build caught that the cleanup removed the sequence-order local from the wrong NSP helper; this follow-up restores it in `dniv_nsp_rx_sequence_locked` and removes only the truly unused receive local. Exact-SHA acceptance of the socket-family build follow-up at `dff43abd34cb77cb65fd03d92c1e49fab1e55304` is green: Repository Policy `35420342660`, Build Bootstrap `35420378234`, Project State Gate `35420379715`, External Reference Baselines `35420380754`, E1 `35420381818`, E2 `35420382772`, E3 `35420383606`, E4 `35420384814`, and Independent Ethernet Interoperability `35420385869`; all amd64/ARM64 jobs passed. The next candidate adds direct independent NSP/socket proof: every PyDECnet interoperability role now drives native `AF_DECnet` / `SOCK_SEQPACKET` through built-in object 25 (MIRROR) with records spanning single-segment, MSS-boundary and multi-segment sizes, and packet-capture validation requires bidirectional NSP traffic. The first MIRROR-test commit preserved the intended content but accidentally cleared executable bits on the lab entry scripts; Repository Policy run `35422200657` caught the mode regression before acceptance dispatch. This follow-up restores the executable modes without changing protocol behavior. Exact-SHA acceptance of `5f8fbac5311dc160365a08020be7bce3f681cf4e` exposed one ARM64 PyDECnet false-readiness race in interop job `105842036682`: the candidate had an UP routing adjacency, but the reference harness had emitted `DNIV-REF-READY` while PyDECnet was still importing/initializing, so the first MIRROR socket connect returned `ENOENT`. The reference harness now captures PyDECnet startup output and does not publish READY until the pinned peer itself logs `DECnet/Python is running`; timeout/exit paths preserve the captured PyDECnet diagnostics. Candidate protocol behavior is unchanged. The first exact-SHA rerun of this readiness fix showed the ARM64 controller still cut the reference VM off before PyDECnet could reach that application-ready marker: prior evidence places the marker near guest uptime 435 seconds, while the harness still allowed only 360 wall-clock seconds for reference readiness. The ARM64 independent-reference READY bound is therefore raised to a bounded 600 seconds; amd64 remains 180 seconds. This changes only the TCG startup allowance, not protocol behavior or candidate-side convergence limits. Repository Policy run `35424062828` correctly rejected that harness-only bound change because its dedicated readiness regression still encoded the previous 360-second ARM64 contract. The regression is updated with the new 600-second value and a 660-second excessive-bound ceiling, preserving a narrow bounded allowance around the observed application-ready time. Preserve the exact-green Phase 4 candidate and extend independent interoperability as NSP-capable peer coverage becomes available.

Exact-SHA acceptance of `7d5be13d35d4cc15e06511ad4fedf99f483f1034` proved the raised ARM64 PyDECnet readiness bound and its regression guard, and the E1 ARM64 retry completed green. Independent Ethernet Interoperability run `35424157142` then exposed a real candidate routing defect in ARM64 PyDECnet L1 job `105847098820`: after the broadcast-router adjacency reached UP, PyDECnet's initial self-destination L1 vector entry was infinity, and the coalesced route key treated that learned entry as the separately maintained direct adjacency route, withdrawing the direct path to 31.71. The native MIRROR connect therefore returned `ENOENT` before NSP could transmit. Packet-capture ordering confirms the self-infinity vector arrived after two-way adjacency formation and before PyDECnet later advertised its self metric as zero. This follow-up preserves the direct adjacent-router path by ignoring the advertising router's own destination slot in learned L1/L2 vector processing; focused route-metric unit coverage locks the rule.

Exact-SHA acceptance of `5a79c95bbddcdce27507acc55d211c5f70fa7ce4` passed Repository Policy `35425709413`, Build Bootstrap `35425725762`, Project State Gate `35425726876`, External Reference Baselines `35425728144`, and E1-E4 on amd64/ARM64. Independent Ethernet Interoperability `35425733618` failed only ARM64 PyDECnet routing on both attempts. PCAP proves the direct-route correction works: the native socket emits a valid MIRROR CI to 31.71. The remaining failure is a slow-reference convergence race: immediately after two-way adjacency formation the pinned PyDECnet peer is frame-silent for about 33 seconds while processing the candidate's initial full routing-vector burst, longer than the lab MIRROR client's 20-second timeout. Candidate protocol behavior is unchanged. The PyDECnet NSP proof now requires the peer adjacency to remain continuously UP for eight seconds before MIRROR connect; an initial UP followed by that processing blackout resets readiness. The bounded readiness regression locks this ordering and duration.

Repository Policy run `35434792500` rejected the first stable-readiness follow-up before acceptance dispatch because the policy test source contained a literal `\\n` between two Python assignments. This is a test-source formatting defect only; the lab readiness logic and candidate protocol behavior are unchanged. The follow-up replaces that literal escape with a real newline and preserves the exact eight-second stable-adjacency guard before MIRROR.

Independent Ethernet Interoperability run `35434888383` showed that an eight-second continuously-UP adjacency was still insufficient on ARM64 PyDECnet: MIRROR CI was emitted after the guard but the reference remained busy long enough for the 20-second NSP client timeout to expire. The readiness guard is therefore tightened to forty continuous seconds, exceeding the observed roughly 33-second reference processing blackout while remaining bounded to 240 seconds. Candidate protocol behavior remains unchanged; this is an independent-reference scheduling/convergence guard only.

Per the lab settle requirement, the independent PyDECnet NSP proof now waits a full 60 seconds of continuously-UP adjacency before MIRROR rather than forty seconds. This remains a harness-only reference-settling allowance; candidate protocol behavior is unchanged. VDE2 and MULTINET are explicitly separate validation tracks: each must pass its own positive, negative, restart, fault, stress and multi-peer proof before it may be used as a scale/remote-lab transport.

The project transport scope is reconciled: serial/synchronous datalink work has been removed from the roadmap and release gate. Distributed lab scale now uses rootless VDE2 Ethernet plus a separately proven MULTINET TCP gateway. The Route20 fork pin above adds native libvdeplug Ethernet; the PyDECnet live pin adds native VDE Ethernet while retaining its mature MULTINET implementation. Their original accepted routing/NSP roles remain independent references, and the transport extensions require their own proof before scale tests depend on them.

VDE2 and MULTINET have separate proof scripts and workflows: `tests/lab/prove-vde2.sh` validates real VDE frame delivery and Route20/PyDECnet adjacency, while `tests/lab/prove-multinet.sh` runs the PyDECnet MULTINET test module plus live TCP adjacency/reconnect. `userspace/dnmultinet/dnmultinet.py` exposes the proven PyDECnet MULTINET engine as a configurable VDE-to-MULTINET Area-31 gateway. External HECnet peer endpoints are runtime-only and are not committed.

Next sequence: finish exact-SHA acceptance of the current Phase 5 socket/routing candidate; prove VDE2; prove MULTINET separately; then resume Phase 5 socket work with inbound listen/accept, interrupt/OOB, classic socket options/access/connect data, stream mode and lifecycle negatives. HECnet Area-31 is an additional interoperability surface, not a replacement for local exact-SHA acceptance.

Repository Policy run `35436873179` rejected the initial distributed-transport integration because both new proof workflows omitted the required `queue: max` concurrency policy. No protocol or transport code executed under that failed gate. The follow-up adds the required bounded queue declaration to both VDE2 and MULTINET proof workflows; transport semantics are unchanged.

VDE2 proof run `35436873611` reached the transport harness after successfully installing dependencies, fetching both exact forks and building the VDE-enabled Route20 fork, but foreground `vde_switch` consumed EOF from the noninteractive runner console and exited before frame proof. The harness now starts `vde_switch` in daemon mode, discovers the unique per-run daemon by its private socket path and retains explicit cleanup. This is a VDE harness lifecycle fix, not protocol behavior.

VDE2 proof rerun `35436975623` confirmed daemon startup but exposed a harness assumption about VDE2's `-sock` pathname: VDE2 2.3.2 creates a communication endpoint directory at that path rather than a UNIX socket at the path itself. The proof now waits for the endpoint path to exist and lets libvdeplug resolve its internal control socket. No VDE or DECnet behavior is changed.

VDE2 proof run `35437051337` reached the real libvdeplug API and exposed an ABI mistake in both new reference adapters: Ubuntu 24.04's libvdeplug exports `vde_open_real` while `vde_open` is a source-level macro. The pinned PyDECnet and Route20 forks now support `vde_open_real` interface version 1 with legacy `vde_open` fallback. External Reference Baselines run `35437068303` also exposed an out-of-scope legacy transport test in the old complete-discovery baseline; the reference gate now executes an explicit repository-maintained in-scope PyDECnet module list instead. No candidate DECnet protocol behavior changes in this follow-up.

VDE2 proof `35440198290` showed that symbol selection was fixed but both adapters still supplied a zeroed open-arguments structure to libvdeplug, which returned `EINVAL` before frame traffic. Neither project path needs a VDE port/group/mode override. The reference forks now pass NULL open arguments so libvdeplug keeps its own defaults. The VDE proof additionally requires the real `ctl` socket and executes a native C/libvdeplug two-endpoint frame round trip before the PyDECnet adapter test, separating switch/URL failures from language binding failures. Candidate DECnet protocol behavior remains unchanged.

Repository Policy run `35440503013` correctly rejected the new PyDECnet in-scope module-list artifact because the text file lacked the canonical project header. The list now carries the required header; its module contents and transport scope are unchanged.

VDE2 transport proof `35440502997` completed green on `a6fd0eb5303eee911785c2699c4778977cb56990`: native C/libvdeplug frame round-trip, the PyDECnet VDE adapter and Route20/PyDECnet VDE adjacency all passed against the pinned VDE-enabled forks. VDE2 is therefore proven independently for the local/rootless transport track. MULTINET remains a separate proof and must run independently before any combined Area-31 path is trusted.

MULTINET proof `35440600180` ran all 40 pinned PyDECnet MULTINET unit tests green, including TCP connect/listen, fragmented/coalesced framing, late listener, restart/reconnect and the upstream UDP cases. Its live two-router proof then false-failed because the harness watched broadcast-adjacency events 4.15/4.16; PyDECnet point-to-point circuits report Routing event 4.10 `Circuit up` and 4.8 `Circuit down`. The live proof is corrected to those point-to-point events. MULTINET protocol/transport behavior is unchanged.

MULTINET transport proof `35440787624` completed green on `24e4e462a4ed1e525cb7011a6f344c447282168d`. The proof ran the pinned PyDECnet MULTINET module suite and a live two-router TCP listen/connect circuit with point-to-point Circuit up/down detection and reconnect recovery. VDE2 `35440502997` and MULTINET are now independently green; they may be combined in later controlled Area-31 distributed-lab tests, but remain separate acceptance evidence sets.

Exact-SHA acceptance of `d097dee8e09e6a5645e44cf596a46cc3a49d89e9` reached External Reference Baselines `35440924133`; Route20 built green, but the PyDECnet job failed before running tests because the canonical project header and blank line in `pydecnet-in-scope-tests.txt` were passed to `unittest` as module names. The workflow now filters comments/blank lines and asserts a non-empty module set before invocation. Reference scope and protocol behavior are unchanged.

Exact-SHA acceptance of `47c95e028485e5bbebc2d54778789cb67b68551b` passed policy, build, state, reference baseline, E1-E4 except the independent ARM64 PyDECnet interop jobs. Artifacts show both failures are harness time-budget exhaustion, not protocol failure: the reference reaches application READY, the candidate reaches adjacency UP, and the controller then expires its fixed 420-second candidate-ready budget while the required 60-second stability proof is still executing under ARM64 TCG. No `DNIV-INTEROP-FAIL` marker is emitted and no MIRROR attempt occurs. The default candidate-ready bound is therefore 720 seconds on ARM64 while remaining 420 seconds on amd64; an explicit `DNIV_INTEROP_TIMEOUT_SECONDS` override still wins. The full-minute stability requirement itself is unchanged.
