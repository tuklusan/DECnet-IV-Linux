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

The arm64 direct-boot path peels one outer gzip layer when present. Current raw AArch64 Images are recognized by `ARM\x64` metadata. Exact EFI-zboot wrappers are structurally validated and their bounded gzip payload is expanded to a raw AArch64 Image for QEMU direct boot. Other nonempty artifacts remain eligible for QEMU raw-image fallback; actual VM boot remains executable proof.

Acceptance image filesystems are now made stable before RAW-to-QCOW2 conversion. The base ext4 image disables lazy inode-table and journal initialization. Every base or derived RAW image is synchronized after its final unmount and checked with `e2fsck -fy`; only normal or repaired-clean statuses are accepted before conversion and logical comparison. This prevents late ext4 metadata writes from making the QCOW2 differ from the intended final RAW image.

### Phase 3

Implementation remains active. UAPI v2 provides standard Phase IV node MAC derivation, router/endnode hello generation and parsing, periodic hello transmission, per-interface adjacency state, 3.1x listen expiry, designated-router election, counters and `dnctl adjacencies`. Router-router INIT/UP behavior, endnode admission, endnode router selection, L2 cross-area behavior, 33-router/interface admission, protocol source MACs, DECnet unicast filters and primary-MAC-change survival are implemented and covered by the current E1/interop harnesses.

The kernel includes the per-interface designated-router candidacy timer correction: when the local router first becomes the best candidate, a fresh five-second DRDELAY starts; pending promotion is cancelled while a better router is known; interface-down and identity changes reset the timer state. E1 includes a wire-level regression that silences DN71 long enough for listener expiry but not long enough for DN70 to complete DRDELAY, so DN70 must not emit an All-Endnodes hello during that gap.

Exact-SHA acceptance parent `35232209976` ran on candidate `3f41bec910b5b07520c23b05dcbb1996d091ef62`. Native build child `35232466634` and project-state child `35232469698` completed green. E1 child `35232475152` failed before protocol acceptance: arm64 detected a RAW/QCOW2 content mismatch after image construction, while amd64 booted both guests but the smoke service dependency created immediately before conversion was absent from the boot transaction and no acceptance markers appeared. Those two observations are consistent with an image-stability defect: late backing-file metadata writes after unmount could race conversion and make the converted image represent an earlier filesystem state.

Interop child `35232477599` failed before independent protocol assertions on both architectures while creating the mutated reference image after package installation. The base and candidate image path could complete first, then the reference-image mutation failed during its final image-integrity sequence. This is the same class of RAW filesystem quiescence defect and is corrected in the base and both derived image builders rather than hidden by weakening `qemu-img compare`.

All acceptance results from `3f41bec910b5b07520c23b05dcbb1996d091ef62` are historical evidence after this correction. Phase 3 remains unaccepted until a fresh exact-head lineage is green.

The repository-policy helpers are `tools/workflow_guard.sh` and `tools/integrity_scan.py`; workflow evidence is stored below `integrity/`.

## Test addressing

Ordinary lab addressing remains area 31, nodes 70 through 79, names DN70 through DN79. The live L2 interoperability case deliberately uses an independent peer in area 32.

## Pre-production acceptance

`docs/PRE_PRODUCTION_TEST.md` is the consolidated production procedure. Required tests must execute with complete evidence; documentation alone is never green. Long campaigns are checkpointed across hosted jobs, while any genuinely uninterrupted run beyond the hosted-job ceiling requires a persistent controller.

## Resume point

Phase 3 remains active. The current correction stabilizes ext4 RAW images before conversion in the base, interoperability-candidate and reference-image builders while retaining structural QCOW2 checks and logical RAW/QCOW2 equality. No protocol promotion is implied by this image-path repair.

## Next action

Dispatch fresh exact-head native x86_64/aarch64 build, project-state/continuity, pinned reference, E1 and bounded Route20/PyDECnet interoperability gates on the new `main` candidate. Phase 4 begins only after that unchanged Phase 3 candidate is green.
