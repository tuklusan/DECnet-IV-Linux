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

Build a complete native DECnet Phase IV stack for maintained Linux as a fresh out-of-tree kernel module plus useful DECnet/Linux userspace. Deliver reproducible x86_64/aarch64 VM images and prove behavior against independent implementations and later real DEC systems.

## References and licensing

Preferred references and exact pins remain:

- Route20 `b94115b2615c6463d1f006924ceeadde8e2d4367`
- PyDECnet live `a7194be8d72dea6f9eb4f77083f056f53e80df58`
- PyDECnet tests `9a844987bf3a1450632dee8d37e60a23a453bad3`
- LinuxDECnet `ff39eef045d1e4b7b72a3d40111e89c07a473398`
- SIMH `5b73b1032b52d19bf80752ea4d9cbbdc92e7b5e0`

The live PyDECnet pin has a pre-existing `Macaddr("1.24")` self-test contradiction, so the immediately preceding internally consistent revision remains the unmodified unit-test baseline. Route20 remains the independent oracle for dedicated All-Level-2-Routers multicast behavior. The product license is the canonical root `LICENSE`, blob `c6dabab19a2d36bffddabe7584a932c72fa272c3`; the kernel reports `MODULE_LICENSE("Proprietary")`.

## Repository discipline

- Work directly on `main`; do not create or use feature branches.
- The remote branch invariant is exactly `refs/heads/main`.
- Every substantive commit updates this file and `scratch/RESUME.md` in the same commit.
- Acceptance applies only to one exact unchanged `main` commit.
- Acceptance children are bound to the parent run ID plus exact expected SHA.
- Every hosted job has an explicit timeout of at most 75 minutes and every workflow/job concurrency block uses `queue: max` with `cancel-in-progress: false`.
- GitHub-owned workflow actions remain pinned to immutable full SHAs.
- Compact evidence retention is at most 30 days. Two-node resumable QCOW2 checkpoints are retained for 3 days and stale successful same-architecture checkpoints are pruned with paginated artifact enumeration.
- Interoperability jobs start fresh VMs and retain evidence, not transient overlays.
- Candidate promotion is determined only by the documented exact-SHA mechanical, build, VM, reference, protocol and interoperability gates.

## Phase status

### Phase 1

Foundation complete: UAPI v2, `decnet_iv.ko`, configurable identity, Routing Layer EtherType registration/counters, `dnctl`, centralized test addressing, unit tests and native x86_64/aarch64 build gates.

### Phase 2

Foundation complete: pinned Ubuntu Base 26.04.1 amd64/arm64 rootfs files and package snapshot `20260915T000000Z`, deterministic ext4/QCOW2 construction, exact guest kernel/module/userspace build, direct kernel/initrd boot, two independent one-NIC VMs, packet capture and serial evidence. Acceptance QCOW2 integrity uses `qemu-img compare`.

The arm64 direct-boot path peels one outer gzip layer when present. Current raw AArch64 Images are recognized by `ARM\x64` metadata. Exact EFI-zboot wrappers are structurally validated, their bounded gzip payload is expanded to a raw AArch64 Image for QEMU direct boot, and other nonempty artifacts remain eligible for QEMU raw-image fallback. Actual VM boot remains executable proof.

The image builder installs and verifies the VM smoke entry point, enables it with systemd's offline enable operation, and verifies the resulting `multi-user.target` dependency before image conversion.

### Phase 3

Implementation remains active. UAPI v2 provides standard Phase IV node MAC derivation, router/endnode hello generation and parsing, periodic hello transmission, per-interface adjacency state, 3.1x listen expiry, designated-router election, counters and `dnctl adjacencies`. Router-router INIT/UP behavior, endnode admission, endnode router selection, L2 cross-area behavior, 33-router/interface admission, protocol source MACs, DECnet unicast filters and primary-MAC-change survival are implemented and covered by the current E1/interop harnesses.

The current kernel includes the per-interface designated-router candidacy timer correction: when the local router first becomes the best candidate, a fresh five-second DRDELAY starts; the pending transition is cancelled while a better router is present; interface-down and identity changes reset the timer state. E1 includes a wire-level regression that silences DN71 long enough for listener expiry but not long enough for DN70 to complete DRDELAY, so DN70 must not emit an All-Endnodes hello during that gap.

Exact-SHA acceptance parent `35228747062` ran on candidate `3582b7ab3b0336f8b28cec6e8c1a68d02514d440`. Native build child `35228787667`, project-state child `35228789830`, and pinned reference-baseline child `35228792392` completed green. E1 child `35228794763` failed before protocol acceptance: arm64 produced no serial output from the direct-boot artifact, while amd64 booted normally but the smoke unit was absent from the boot transaction and emitted no acceptance markers. The corrective image path expands an exact validated EFI-zboot payload to raw Image and uses systemd offline enable plus enabled-link verification for the smoke unit.

Interop child `35228796950` exposed a separate harness defect before independent protocol assertions: Route20 reference startup failed on both architectures because the read-only vvfat bundle backend was attached to a writable virtio block frontend, and QEMU rejected it with `Block node is read-only`. The corrective harness marks that frontend `readonly=on`.

All results from `3582b7ab3b0336f8b28cec6e8c1a68d02514d440` are historical evidence after this correction. Phase 3 remains unaccepted until a fresh exact-head lineage is green.

The repository-policy helpers are `tools/workflow_guard.sh` and `tools/integrity_scan.py`; workflow evidence is stored below `integrity/`.

## Test addressing

Ordinary lab addressing remains area 31, nodes 70 through 79, names DN70 through DN79. The live L2 interoperability case deliberately uses an independent peer in area 32.

## Pre-production acceptance

`docs/PRE_PRODUCTION_TEST.md` is the consolidated production procedure. Required tests must execute with complete evidence; documentation alone is never green. Long campaigns are checkpointed across hosted jobs, while any genuinely uninterrupted run beyond the hosted-job ceiling requires a persistent controller.

## Resume point

Phase 3 remains active. The current candidate contains corrections for the arm64 direct-boot wrapper, deterministic smoke-unit enablement, and read-only interop bundle attachment. None of those corrections is accepted until the fresh exact-SHA child gates execute successfully.

## Next action

Dispatch fresh exact-head native x86_64/aarch64 build, project-state/continuity, pinned reference, E1 and bounded Route20/PyDECnet interoperability gates on the new `main` candidate. Phase 4 begins only after that unchanged Phase 3 candidate is green.
