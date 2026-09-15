# Implementation Roadmap

This is the execution order for DECnet-IV-Linux. Later phases do not replace earlier acceptance gates.

## Phase 0 - repository continuity and reference discipline

Exit criteria: repository policy/continuity gates are active; every substantive commit refreshes `docs/PROJECT_STATE.md`; preferred reference roles and license boundaries are documented; the removed legacy Linux DECnet stack is not the implementation base; development uses feature branches and only exact green reviewed commits are promoted to the maintained `main` line.

## Phase 1 - buildable kernel and userspace bootstrap

Deliver versioned UAPI, out-of-tree `decnet_iv.ko`, configurable identity, Routing Layer EtherType receive counters, `dnctl`, native x86_64/aarch64 builds and unit tests.

Exit criteria: module, userspace and unit tests build cleanly on both required architectures.

Status: complete foundation retained on `main`.

## Phase 2 - reproducible Ubuntu Base image and two-node lab

Deliver:

- pinned Ubuntu Base 26.04.1 amd64 and arm64 rootfs tarballs;
- deterministic ext4/QCOW2 test image construction;
- exact image kernel, headers, module and current userspace tools;
- direct QEMU kernel/initrd boot with no installer or runtime provisioning layer;
- DN70 and DN71 as separate VMs on one raw Ethernet LAN;
- packet capture and per-node serial logs on failure;
- KVM when available, software emulation fallback otherwise.

Exit criteria: both native CPU cases boot two independent images reliably and exchange deliberately generated DECnet Routing Layer frames on the isolated LAN.

## Phase 3 - Ethernet Phase IV initialization and adjacency

Deliver DECnet Ethernet address handling, endnode/router hello parsing and generation, adjacency state and expiry timers, and independent vectors/interoperability checks.

Exit criteria: DN70/DN71 form and age adjacencies correctly and repeat against independent peers where their roles apply.

The E1 acceptance harness must prove an observable router INIT-to-UP transition, generated/parsed hello traffic, listener expiry after peer silence, clean module restart/recovery, and correct DECnet multicast/source-MAC evidence on both native CPU architectures before Phase 3 can advance.

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

Required topology includes `Ethernet -> DECnet router -> DDCMP -> DECnet router -> Ethernet`. Exercise higher layers across the path as they become available.

## Phase 10 - scale, portability, real peers and release images

Deliver 4/8/16-node routed topologies, both CPU architectures and mixed directions, maintained distro portability, real DEC peers, physical mixed-CPU testing, self-booting QCOW2/RAW images, checksums and reproducible manifests.

Exit criteria: the release candidate passes all applicable external conformance, virtual topology, mixed-media, fault/stress and physical-hardware gates.
