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

This is the authoritative continuity record for DECnet-IV-Linux. Read `docs/HANDOVER.md`, this file, `docs/ROADMAP.md`, `docs/ARCHITECTURE.md`, `docs/TEST_LAB.md` and `docs/PRE_PRODUCTION_TEST.md` before changing protocol, image or acceptance behavior. Commit history retains prior state records; this file intentionally describes the current tree rather than repeating the full historical diary.

## Goal

Build a complete native DECnet Phase IV stack for maintained Linux as a fresh out-of-tree kernel module plus useful DECnet/Linux userspace. Deliver reproducible x86_64/aarch64 VM images and prove behavior against independent implementations and, later, real DEC systems.

## Architecture

- Base image: pinned Ubuntu Base 26.04.1 LTS for amd64 and arm64.
- Kernel target: native Ethernet; endnode/Level 1/Level 2 routing; NSP; sockets/UAPI; Session Control; NICE/NML state/hooks; DDCMP.
- Routing, NSP and DDCMP state machines remain in kernel space.
- Userspace target: `ncp`, `sethost`/`dnlogin`, DAP/FAL/RMS tools, PHONE, mail, task/object access, daemons, libraries, diagnostics and administration tools.
- Primary VM artifact: QCOW2; RAW and conversion formats follow for release.
- Acceptance nodes are independent VMs, not containers or namespaces sharing one kernel.

## References and licensing

Preferred references are the project forks `tuklusan/Route20`, `tuklusan/pydecnet`, `tuklusan/LinuxDECnet` and `tuklusan/simh`. Upstreams are comparison/provenance sources only. Direct reuse requires compatible licensing and retained notices; otherwise use documented protocol behavior and independent implementation.

Pinned revisions in `tests/reference/refs.env`:

- Route20: `b94115b2615c6463d1f006924ceeadde8e2d4367`
- PyDECnet behavior/live: `a7194be8d72dea6f9eb4f77083f056f53e80df58`
- PyDECnet tests: `9a844987bf3a1450632dee8d37e60a23a453bad3`
- LinuxDECnet comparison: `ff39eef045d1e4b7b72a3d40111e89c07a473398`
- SIMH: `5b73b1032b52d19bf80752ea4d9cbbdc92e7b5e0`

The live PyDECnet pin has a pre-existing `Macaddr("1.24")` self-test contradiction, so its immediately preceding internally consistent revision is the unmodified unit-test baseline. Route20 is the independent oracle for dedicated All-Level-2-Routers multicast behavior; the live PyDECnet pin interoperates as an L2 router through All-Routers and is not required to emit that dedicated multicast.

The product license is the canonical root `LICENSE`, blob `c6dabab19a2d36bffddabe7584a932c72fa272c3`. It applies to project-owned material only; third-party material remains under its original license. `tools/license_monkey.py` pins that exact license and canonical project header. The kernel module reports `MODULE_LICENSE("Proprietary")`, matching the product license.

Self-to-self success is never sufficient for final interoperability claims.

## Repository discipline

- Perform substantive work directly on `main`; do not create or use feature branches for project work.
- Every substantive commit updates this file in the same commit.
- Acceptance applies only to the exact unchanged `main` commit that satisfies the required SoP and gates.
- `tools/project_state_gate.py`, `tools/license_monkey.py` and `tools/repo_policy.py` enforce continuity, licensing/header and repository word policy.
- Ordinary source/document pushes do not automatically consume hosted runners. Acceptance workflows are demand-driven; an owner-opened issue titled exactly `DNIV acceptance gates` is the controlled dispatcher after repository policy succeeds and the event revision still equals `main`.
- Runner jobs share repository-wide x64 and arm64 concurrency slots and queue rather than replacing pending work.
- Generated VM evidence remains under ignored `tests/lab/artifacts/` and workflow artifacts.

## SoP delivery rule

1. Read the complete latest repository copy byte-for-byte and line-by-line without truncation; find and fix defects/gaps.
2. Any fix resets the sequence to Step 1 on the new latest copy.
3. Delivery requires three consecutive clean complete Step-1 passes.
4. Any later change resets the sequence.

Automated tests, diffs, excerpts and previous reviews do not replace this rule.

## Phase status

### Phase 1

Foundation complete: versioned UAPI, `decnet_iv.ko`, configurable identity, `/dev/decnet_iv`, Routing Layer EtherType registration/counters, `dnctl`, centralized test addressing, unit tests and native x86_64/aarch64 build gates.

### Phase 2

Foundation complete: pinned Ubuntu Base 26.04.1 amd64/arm64 rootfs files, pinned package snapshot `20260915T000000Z`, deterministic ext4/QCOW2 assembly, exact guest kernel/module build, direct kernel/initrd boot, two independent one-NIC VMs, packet capture and serial evidence.

Ubuntu Base initially lacks usable certificate trust for the snapshot service. Image construction bootstraps only signed `ca-certificates` with TLS peer verification temporarily disabled, refreshes package-owned trust, then requires ordinary verified snapshot access for all remaining packages. The sparse root filesystem floor is 4 GiB after the earlier 2 GiB arm64 build exhausted ext4 space while unpacking virtual-kernel modules.

The retained `phase2` smoke gate exchanges deliberately generated standard DECnet Routing Layer Ethernet frames. VM checkpoints contain base image, portable overlays, exact kernel/initrd, checksums, session metadata, logs and packet capture and may resume only for matching architecture/source revision/mode.

### Phase 3

Implementation is in progress. UAPI v2 provides standard Phase IV node MAC derivation, router/endnode hello generation and parsing, periodic hello transmission, per-interface adjacency state, 3.1x listen-time expiry, designated-router election, extended counters and `dnctl adjacencies`.

Implemented corrections include the two-byte little-endian Ethernet Routing Layer payload length, legal trailing Ethernet padding handling, dedicated All-Level-2-Routers membership/transmission for Linux L2 routers, transactional filter installation, runtime identity-change serialization with adjacency processing, software destination-class validation, and the 128-byte maximum accepted Phase IV endnode hello test-data image.

Router-router adjacencies begin INIT and become UP when the peer router hello lists the local router with the expected priority. Loss of that listing returns an UP adjacency to INIT; listen expiry removes it. Routers accept valid endnode hellos as UP. Endnodes select one router adjacency. Same-area rules apply except that L2 routers may form L2 adjacencies across areas. Router admission is capped at 33 per interface and retains the highest `(priority, node address)` set.

The E1 self-to-self harness covers L1 hello exchange, observable INIT/UP behavior, listener expiry, module restart/recovery, designated-router behavior, protocol source MACs, DECnet unicast-filter ownership and survival of a post-install primary device-MAC change.

The independent-peer harness boots candidate and reference in separate VMs and runs same-area L1, cross-area L2 and endnode scenarios against exact pinned Route20 and PyDECnet on both native architectures. It requires standard framing, protocol-derived source MACs, two-way router-list evidence where applicable, endnode hello test data, hardware-MAC change survival, protocol-unicast reception, hard peer loss/listen expiry, fresh-peer recovery and retained packet/serial evidence. The reference image never loads `decnet_iv`.

The latest full-tree SoP pass found a harness process-lifetime defect in `tests/lab/run-interop.sh`: asynchronous shell functions launched QEMU without `exec`, so the recorded background PID could be the shell wrapper rather than QEMU itself. Hard-killing the recorded reference PID could therefore leave the actual VM alive and invalidate the listener-expiry/recovery test. Candidate and reference launch paths now `exec` QEMU on both architectures so recorded PIDs are the VM processes themselves. This fix resets the SoP sequence; no earlier acceptance result carries forward.

## Test addressing

Ordinary lab addressing is centralized in `tests/lab/test-addresses.env`: area 31, nodes 70 through 79, names DN70 through DN79. Larger and inter-area tests extend this deliberately. The live L2 interoperability scenario deliberately places the independent peer in area 32.

## Pre-production acceptance

`docs/PRE_PRODUCTION_TEST.md` is the single consolidated production acceptance procedure. It de-duplicates E0-E4/D0-D5 with applicable pinned-reference coverage and adds Linux-kernel lifecycle/concurrency, malformed-input, resource, evidence, security, performance, stress, soak, endurance, real-peer and upgrade/rollback coverage. Documentation alone is never green; required tests must execute with complete evidence.

## Resume point

The current `main` candidate combines the Phase 1/2 foundation, Phase 3 Ethernet initialization/adjacency implementation, self-to-self E1 harness, live Route20/PyDECnet two-VM interoperability harness, signed-snapshot certificate bootstrap, 4 GiB sparse image workspace, framing/filter/multicast/concurrency fixes, endnode test-data bound, repository policy, license/header enforcement and exact-QEMU-PID process control for independent-peer hard-stop testing. The protocol phase remains Phase 3.

## Next action

Restart the SoP sequence on the exact current `main` commit and require three consecutive clean complete full-repository passes. Then run exact-head repository policy/continuity, native x86_64/aarch64 build, pinned reference baselines, E1 self-to-self and live Route20/PyDECnet interoperability on both architectures. Accept only that unchanged `main` commit after every required Phase 3 gate is green. Any defect, evidence gap or later edit resets SoP. Phase 4 routing begins only after the Phase 3 gates are green.
