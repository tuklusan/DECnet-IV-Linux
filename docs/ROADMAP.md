# Implementation Roadmap

This is the execution order for DECnet-IV-Linux. Later phases do not replace the acceptance gates of earlier phases.

## Phase 0 - repository continuity and reference discipline

Exit criteria:

- repository policy gate is active;
- every substantive commit refreshes `docs/PROJECT_STATE.md`;
- every substantive commit carries an exact-snapshot independent paranoid-review receipt after the required dual manual read and triple clean SoP pass;
- Route20 and PyDECnet are documented as external conformance peers;
- no legacy Linux DECnet kernel implementation is used as the implementation base;
- protocol/reference licensing boundaries are documented before source reuse is considered.

Status: substantially complete.

## Phase 1 - buildable kernel and userspace bootstrap

Deliver:

- versioned UAPI header;
- out-of-tree `decnet_iv.ko`;
- configurable local DECnet identity, defaulting to 31.70 / DN70;
- Routing Layer EtherType receive registration and counters;
- small `dnctl` diagnostic/configuration program;
- native x86_64 and ARM64 compile gates;
- unit tests for address encoding and UAPI constants.

Exit criteria: module, userspace, and unit tests build cleanly on both required architectures.

## Phase 2 - reproducible tiny VM image and two-node lab

Deliver:

- pinned Alpine reference image build;
- module and userspace installed into the image;
- DN70 and DN71 boot as separate VMs on one raw Ethernet LAN;
- packet capture and per-node logs retained on failure;
- KVM when available, software emulation fallback otherwise.

Exit criteria: two images boot independently and exchange deliberately generated DECnet Routing Layer frames on the isolated LAN.

## Phase 3 - Ethernet Phase IV initialization and adjacency

Deliver:

- DECnet Ethernet address handling;
- endnode/router hello parsing and generation as required by node role;
- adjacency state and expiry timers;
- packet parsing cross-checked against protocol documentation and PyDECnet vectors.

Exit criteria: DN70/DN71 form and age adjacencies correctly, then repeat with a PyDECnet peer and a Route20 peer where applicable.

## Phase 4 - Phase IV routing

Deliver:

- endnode routing behavior;
- Level 1 routing;
- Level 2/area routing;
- routing database, forwarding database, metrics, visit count, route aging and convergence;
- multi-LAN VM topologies.

Exit criteria: traffic crosses forced one-router and two-router paths, failures converge, loops are prevented, and live interoperability works with Route20 and PyDECnet.

## Phase 5 - NSP transport and DECnet socket ABI

Deliver:

- NSP connection state machine, flow control, sequencing, retransmission and timers;
- native socket family integration using the reserved DECnet protocol family number;
- compatibility-oriented socket structures only where they are still technically sound.

Exit criteria: reliable bidirectional logical links pass stress, reconnect and loss tests against an independent peer.

## Phase 6 - Session Control and network management

Deliver:

- Session Control object dispatch;
- NICE/NML subset required for useful local and remote management;
- executor, node, circuit, line and counters needed by the planned `ncp` experience.

Exit criteria: scripted and interactive management queries work locally and against independent DECnet peers.

## Phase 7 - familiar user-mode tools

Implement tools only when their underlying protocol layer is ready:

1. `ncp` on NICE/NML;
2. `sethost` on Session Control plus CTERM;
3. `dncopy`/`dntype` on DAP/FAL;
4. `phone` and `phoned` on the PHONE protocol;
5. related query, directory, login and task utilities as useful.

Exit criteria: command names, common syntax and interaction remain familiar to DECnet/Linux users while using the new kernel stack.

## Phase 8 - DDCMP

Deliver:

- kernel DDCMP framing/state machine;
- CRC, ACK/NAK/REP, sequencing, retransmission, timers and restart handling;
- test byte-stream carriage over TCP/UDP for CI without moving DDCMP logic out of the kernel;
- PyDECnet DDCMP interoperability;
- Route20 DDCMP interoperability where its supported mode applies;
- later asynchronous serial and synchronous hardware tests.

Exit criteria: normal and fault-injected DDCMP links recover correctly and expose correct counters.

## Phase 9 - mixed-media routing

Required topology includes:

Ethernet -> DECnet router -> DDCMP -> DECnet router -> Ethernet.

Exercise routing, NSP, Session Control, NICE, CTERM, PHONE and DAP across the mixed path as those layers become available.

Exit criteria: application traffic traverses mixed media in both directions and survives link failure/recovery.

## Phase 10 - scale, physical hardware and release images

Deliver:

- 4, 8 and 16-node virtual topologies;
- x86_64-to-x86_64, ARM64-to-ARM64 and mixed-architecture cases;
- small physical lab with x86_64 and ARM64 hosts on a managed switch;
- QCOW2 and RAW release images, checksums, manifest and reproducible build metadata.

Exit criteria: release candidate passes all applicable external conformance, virtual topology, mixed-media and physical-hardware gates.
