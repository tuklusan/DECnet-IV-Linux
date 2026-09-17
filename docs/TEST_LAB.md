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

# Test Lab

## Purpose

The lab proves protocol interoperability, not merely that two copies of the same implementation can talk to each other. Every protocol milestone is tested against independent peers and on both x86_64 and aarch64.

The default isolated DECnet test pool is area 31, nodes 70 through 79. Tests may override the pool when more nodes or multiple areas are required.

## Phase 2 boot rule

The basic VM gate uses the pinned Ubuntu Base rootfs and direct QEMU kernel/initrd boot. Images are assembled before boot. Acceptance VMs have one DECnet Ethernet NIC and no management NIC. Runtime installers and provisioning systems are deliberately absent from this path.

Each node is a separate VM with its own kernel. Network namespaces are not sufficient for acceptance tests because they share kernel/module state.

The two-node workflow keeps the retained Phase 2 raw-EtherType smoke gate as `phase2` mode and adds the Phase 3 E1 adjacency gate as `e1` mode. Successful workflow checkpoints are sealed as format 2 with `session.env` included in `SHA256SUMS`; legacy or otherwise unsealed format-1 checkpoints are not accepted for workflow resume. A format-2 checkpoint may be resumed only when its architecture, exact source commit and acceptance mode match the current run.

## Virtual lab

- Build x86_64 and aarch64 images natively where possible.
- Connect VM NICs to Linux bridges made by the test controller.
- Carry DECnet directly as Ethernet frames; IP is not required on the DECnet LAN.
- Give router VMs multiple NICs only when routing tests need them.
- Capture traffic on every bridge and retain per-node serial/kernel/application evidence on failure.
- Use KVM when available and QEMU software emulation only as fallback.

## Runner concurrency and resumable state

GitHub-hosted runner machines are ephemeral: a later job starts on a fresh host and cannot resume the prior host process, RAM or local filesystem. The repository-root `scratch/` namespace is therefore the standard staging area for all workflow state. Jobs write mutable state below ignored `scratch/runtime/<run-id>/<run-attempt>/<job>/`, upload that directory as a workflow artifact, and restore prior artifacts below ignored `scratch/restored/<run-id>/` when a resume input is supplied. This preserves explicit files and evidence across runner sessions without pretending that runner-local processes survive.

Every scratch state records exact source commit/tree identity, workflow/job, run ID/attempt, runner identity, architecture/mode, parent/resume lineage, milestones and status. Acceptance jobs also retain three byte-complete exact-tree scan manifests before substantive work and a matching final scan afterward. These machine scans prove byte completeness and immutability of the tracked candidate; they do not replace the required semantic/manual SoP review.

Build, continuity, reference and VM workflows are manual-dispatch only. The Repository Policy workflow does not run on ordinary `push`, branch/tag `create`, or `pull_request:synchronize` events; it may run only for the selected repository metadata events listed in its workflow or by manual dispatch. Merely editing or pushing source, documentation, policy or workflow files therefore does not consume a hosted runner. Every runner job enters one of two repository-wide job concurrency groups: `dniv-runner-x64` or `dniv-runner-arm64`. The groups queue rather than replace waiting jobs. This makes the hard repository ceiling one x64 runner job plus one arm64 runner job at a time; x64-only policy, continuity and reference gates all share the x64 slot. Matrix workflows additionally cap themselves at two parallel jobs.

The two-node VM workflow persists guest disk state inside its scratch run directory. After QEMU is stopped, the lab stores the exact base QCOW2, portable per-node QCOW2 deltas backed by that base, the exact kernel and initrd, checksums, a session manifest, serial logs and packet capture. The complete scratch run directory is uploaded as a per-architecture artifact retained for 90 days.

A manual `resume_run_id` restores the selected prior run's scratch artifacts under `scratch/restored/`. The VM job locates a sealed format-2 checkpoint for its architecture, verifies that `session.env` is covered by `SHA256SUMS`, verifies all recorded hashes, checks both overlays with `qemu-img`, and requires the architecture, exact source commit and acceptance mode to match. The restored node disks are copied before use, rebound to the restored base, and checkpointed again after the run. This is disk-state continuation across fresh hosts, not live CPU/RAM suspend-and-resume.

## Physical architecture lab

Later physical testing uses at least two x86_64 nodes, two aarch64 nodes, a test controller, a managed switch with port mirroring and an independent management path.

## Architecture matrix

Required cases are x86_64/x86_64, aarch64/aarch64 and both mixed directions. Independent peer implementations are substituted for either side as the corresponding protocol layers become available.

## Ethernet ladder

### E0 - wire vectors

Check address encoding, DECnet MAC derivation, routing header forms, checksums and packet decoders against independent vectors.

### E1 - two nodes on one LAN

Start with 31.70 and 31.71. Prove generated/parsed router hellos, observable INIT evidence during initial convergence, both adjacencies reaching UP, adjacency creation/expiry, all-routers and designated-router all-endnodes multicast behavior, correct DECnet source MACs, delivery to the DECnet unicast node MAC when it differs from the device MAC and after the device primary MAC changes while DECnet remains loaded, and clean module restart/recovery. Repeat with independent peers where supported.

The automated E1 self-to-self gate deliberately silences one router long enough to exceed the 3.1x listen timer, requires the peer adjacency to disappear, reloads the silent router, requires observable INIT evidence during restart convergence, and requires both sides to return to UP before accepting the run. Because the first hello from a peer can already list the local router, either side may move from its newly created initialising adjacency to UP within the same hello-processing cycle; the gate therefore requires INIT evidence from at least one side rather than assuming both INIT states remain externally visible. The E1 VMs deliberately start with emulated NIC MAC addresses that differ from their DECnet node MACs, so packet capture proves kernel-generated hello traffic uses the protocol-derived source address rather than merely inheriting the device address. After the router adjacency is established, each guest takes its Ethernet link down briefly, changes the primary NIC MAC to a second deterministic hardware address while the DECnet module remains loaded, brings the link back up, and requires both a fresh peer hello and an UP adjacency. The guests then exchange overlapping raw-unicast probe streams from those changed hardware MACs to the peer DECnet node MAC and verify a matching non-hello receive-counter increase, while host capture verifies the changed-source probes existed in both directions and that protocol hellos still use only the DECnet source MAC. The stream lasts long enough to avoid one guest taking its receive baseline after the other guest's probes have already finished. This is a prerequisite for, not a substitute for, independent-peer interoperability.

### E2 - router on two LANs

An endnode on each LAN communicates only through the router. Prove route installation, forwarding, visit-count handling, adjacency loss and reconvergence.

### E3 - multiple routers

Use alternate paths. Remove links and routers while traffic is active and verify convergence without loops.

### E4 - multiple areas

Use the normal area-31 pool plus a second configurable area for Level 2 tests.

## DDCMP ladder

Keep DDCMP framing/state in kernel space. Automated byte-stream transports are test plumbing only.

- D0: vectors for frames, CRCs, sequence wrap, ACK/NAK/REP and malformed input.
- D1: two fresh-kernel VMs over an emulated serial link.
- D2: independent peers.
- D3: deterministic loss, delay, duplication, corruption, disconnect and reconnect.
- D4: physical asynchronous serial.
- D5: physical synchronous DDCMP or compatible peer.

## Mixed-circuit tests

Required end state includes `Ethernet -> router -> DDCMP -> router -> Ethernet`, mixed CPU architectures and independent implementations. No topology is accepted solely on self-to-self success.

## Evidence retained for every failed test

Keep per-node console/kernel/application logs, DECnet counters/state, packet captures, DDCMP traces when enabled, topology/address allocation, exact source/kernel/module/reference revisions and fault seed.

## Scale plan

Grow deliberately through 2, 4, 8 and 16 independent VMs with real routed topologies. The default 31.70-31.79 pool may be extended by configuration for larger tests.
