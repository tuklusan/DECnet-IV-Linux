# Implementation Roadmap

This is the execution order for DECnet-IV-Linux. Later phases do not replace earlier acceptance gates.

## Phase 0 - repository continuity and reference discipline

Exit criteria:

- repository policy and continuity gates are active;
- every substantive commit refreshes `docs/PROJECT_STATE.md`;
- Route20, PyDECnet, LinuxDECnet and SIMH reference roles are documented;
- no legacy Linux DECnet kernel implementation is used as the implementation base;
- protocol/reference licensing boundaries are checked before source reuse;
- development stays on one maintained `main` line.

## Phase 1 - buildable kernel and userspace bootstrap

Deliver:

- versioned UAPI header;
- out-of-tree `decnet_iv.ko`;
- configurable local DECnet identity, defaulting to 31.70 / DN70;
- Routing Layer EtherType receive registration and counters;
- small `dnctl` diagnostic/configuration program;
- native x86_64 and aarch64 compile gates;
- unit tests for address encoding and UAPI constants.

Exit criteria: module, userspace and unit tests build cleanly on both required architectures.

Status: complete foundation retained on `main`.

## Phase 2 - reproducible small VM image and two-node lab

Deliver:

- select and pin one small maintained non-cloud Linux base with x86_64 and aarch64 support;
- build a deterministic minimal image without unnecessary provisioning layers;
- install the module and current userspace tools;
- boot DN70 and DN71 as separate VMs on one raw Ethernet LAN;
- retain packet capture and per-node logs on failure;
- use hardware virtualization when available and software emulation only as fallback.

Exit criteria: two independent images boot reliably and exchange deliberately generated DECnet Routing Layer frames on the isolated LAN.

## Phase 3 - Ethernet Phase IV initialization and adjacency

Deliver DECnet Ethernet address handling, endnode/router hello parsing and generation, adjacency state and expiry timers, and independent vectors/interoperability checks.

Exit criteria: DN70/DN71 form and age adjacencies correctly and repeat against independent peers where their roles apply.

## Phase 4 - Phase IV routing

Deliver endnode behavior, Level 1 and Level 2 routing, routing/forwarding databases, metrics, visit count, route aging, convergence and multi-LAN VM topologies.

Exit criteria: traffic crosses forced router paths, failures converge, loops are prevented and independent interoperability works.

## Phase 5 - NSP transport and DECnet socket ABI

Deliver NSP connection state, flow control, sequencing, retransmission, timers and native socket/UAPI integration.

Exit criteria: reliable bidirectional logical links pass stress, reconnect and loss tests against an independent peer.

## Phase 6 - Session Control and network management

Deliver Session Control object dispatch plus the NICE/NML state and operations needed for useful local and remote management.

Exit criteria: scripted and interactive management queries work locally and against independent DECnet peers.

## Phase 7 - useful DECnet/Linux userspace

Implement as protocol dependencies become ready: `ncp`; `sethost`/`dnlogin`; DAP/FAL/RMS copy/type/directory tools; PHONE; mail; task/object access; daemons; libraries; diagnostics and administration tools.

Exit criteria: the useful DECnet/Linux command environment works on the new kernel stack and against independent peers.

## Phase 8 - DDCMP

Deliver kernel DDCMP framing/state, CRC, ACK/NAK/REP, sequencing, retransmission, timers, restart handling, CI byte-stream transport plumbing and later physical serial/synchronous testing.

Exit criteria: normal and fault-injected links recover correctly and expose correct counters.

## Phase 9 - mixed-media routing

Required topology includes `Ethernet -> DECnet router -> DDCMP -> DECnet router -> Ethernet`.

Exercise routing, NSP, Session Control, NICE, terminal access, PHONE and DAP across the path as those layers become available.

## Phase 10 - scale, portability, real peers and release images

Deliver 4/8/16-node routed topologies, both CPU architectures and mixed directions, maintained distro portability, real DEC peers, physical mixed-CPU testing, QCOW2/RAW images, checksums and reproducible manifests.

Exit criteria: the release candidate passes all applicable external conformance, virtual topology, mixed-media, fault/stress and physical-hardware gates.
