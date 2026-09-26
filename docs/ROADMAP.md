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

# Implementation Roadmap

This is the execution order for DECnet-IV-Linux. Later phases do not replace earlier acceptance gates.

## Phase 0 - repository continuity and reference discipline

Exit criteria: repository policy/continuity gates are active; every substantive commit refreshes both `docs/PROJECT_STATE.md` and `scratch/RESUME.md` in the same commit; preferred reference roles and license boundaries are documented; the removed legacy Linux DECnet stack is not the implementation base; substantive work is committed directly to `main`, and acceptance applies only to the exact unchanged green `main` commit.

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

The E1 acceptance harness must prove generated/parsed hello traffic, observable INIT evidence during initial convergence and restart, both router adjacencies reaching UP, listener expiry after peer silence, clean module restart/recovery, correct DECnet multicast/source-MAC evidence, and unicast delivery to the DECnet node MAC when it differs from the device MAC on both native CPU architectures before Phase 3 can advance.

## Phase 4 - Phase IV routing

Deliver endnode behavior, Level 1 and Level 2 routing, routing/forwarding databases, metrics, visit count, route aging, convergence and multi-LAN VM topologies.

Exit criteria: traffic crosses forced router paths, failures converge, loops are prevented and independent interoperability works.

Status: complete on exact protocol candidate `6c185b6d01f8a57ee9f0ea6a6c37d7112ddb77d2`; amd64/ARM64 E1-E4 and independent Route20/PyDECnet routing interoperability are green.

## Phase 5 - NSP transport and DECnet socket ABI

Deliver NSP connection state, flow control, sequencing, retransmission, timers and native socket/UAPI integration.

Exit criteria: reliable bidirectional logical links pass stress, reconnect and loss tests against an independent peer.

Status: complete on exact protocol candidate `2d54dbf252120b42a5c2a60fa202371382af5dc9`; full promotion acceptance passed x86_64/ARM64 E1-E4 plus the full Route20/PyDECnet interoperability matrix.

## Phase 6 - Session Control and network management

Deliver Session Control object dispatch plus the NICE/NML state and operations needed for useful local and remote management.

Exit criteria: scripted and interactive management queries work locally and against independent DECnet peers.

Status: complete on exact protocol candidate `c11045a70e7deb59870fff5f8bc22213e0df2bc0`; full promotion acceptance passed x86_64/ARM64 VM coverage and all 14 Route20/PyDECnet interoperability jobs.

## Phase 7 - useful DECnet/Linux userspace

Implement as protocol dependencies become ready: `ncp`; `sethost`/`dnlogin`; DAP/FAL/RMS copy/type/directory tools; PHONE; mail; task/object access; daemons; libraries; diagnostics and administration tools. Application-level experiments such as a DECnet-native `dnlynx` client may be added after the standard Session/object and management interfaces they depend on are stable; they are not substitutes for the standard tool set.

Exit criteria: the useful DECnet/Linux command environment works on the new kernel stack and against independent peers.

Phase 7 also includes a small DECnet-native web server. Prefer a clean, license-compatible port/adaptation of tinyhttpd or a similarly small auditable HTTP daemon, using native DECnet sockets to serve static websites. Pin imported upstream source and preserve its license.

Status: complete on exact userspace candidate `a967af2787638ab49bf1a929a27ef9f7ab8564e9`; full promotion acceptance passed Repository Policy `35954451490`, Build Bootstrap `35954483756`, Project State Gate `35954485477`, External Reference Baselines `35954487274`, x86_64/aarch64 E1-E4 VM runs `35954489283`, `35954491199`, `35954492983`, `35954494765`, and the full 14-job Route20/PyDECnet interoperability matrix `35954497878`.

## Phase 8 - distributed VDE2, MULTINET and HECnet interoperability

Deliver:

- rootless VDE2 Ethernet fabrics for local and cross-runner labs, including an actual two-host switch-to-switch join rather than assuming the documented SSH design works;
- a configurable user-space MULTINET TCP gateway based on the proven PyDECnet implementation;
- a repository-tracked Area-31 client workflow that consumes `MULTINET_REMOTE_HOST`, `MULTINET_REMOTE_PORT`, `VAX_ADDR`, `VAX_USERNAME` and `VAX_PASSWORD` only at runtime, checks that all required secrets are present before network activity, reports missing prerequisites clearly, and never logs secret values;
- controlled routing through the MULTINET-connected Area-31 area router to the second Area-31 router at `VAX_ADDR`;
- persistent paired Linux/VAX tests under `tests/lab` for routing/NICE information and counters, NSP/Session/object access and, as Phase 7 tools mature, login, DAP/FAL, PHONE, mail, task access and application-level experiments.

Exit criteria: VDE2 and MULTINET pass separate positive, negative, restart and stress proofs; cross-runner VDE2 is demonstrated; then an exact candidate routes successfully between local VDE lab nodes, the MULTINET-facing Area-31 router and the VAX area router without one-off protocol patches or credential leakage.

Status: complete on exact candidate `9b73e61bbd0f95b82410276f7b5dc3db94e219ba`. Full acceptance from Repository Policy run `36258507655` passed Build Bootstrap `36258543209`, Project State Gate `36258553606`, Cross-runner VDE2 `36258564105`, External Reference Baselines `36258573270`, x86_64/aarch64 E1-E4 VM runs `36258584817`, `36258594905`, `36258607144`, `36258617814`, Independent Ethernet Interoperability `36258627216`, VDE2 Transport Proof `36258635481`, MULTINET Transport Proof `36258643588`, and Area-31 Interoperability `36258654316`. The cross-runner proof passed on both hosted architectures with three marked frames, hard transport loss, adjacency expiry/recovery, bridge reconnect and client switch restart using pinned `tuklusan/vde-2`. Credentials/endpoints remain GitHub Actions secrets. Phase 9 may proceed from this unchanged green protocol candidate.

## Phase 9 - scale, portability, real peers and release images

Deliver 4/8/16-node routed topologies across one or more runners, both CPU architectures and mixed directions, maintained distro portability, HECnet and real DEC peers, physical mixed-CPU testing, self-booting QCOW2/RAW images, checksums and reproducible manifests.

Exit criteria: the release candidate passes `docs/PRE_PRODUCTION_TEST.md`, including all applicable external conformance, virtual/distributed topology, VDE2/MULTINET transport, positive/negative, stress/endurance, false-green, real-peer and upgrade/rollback gates.

Status: active. Phase 8 closed fully green on `9b73e61bbd0f95b82410276f7b5dc3db94e219ba`. The first Phase 9 increment adds an exact-candidate 4/8/16 routed-scale controller and promotes the 4-node x86_64/aarch64 topology into full acceptance; 8/16-node promotion follows only after the 4-node gate is green.
