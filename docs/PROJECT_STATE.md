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

## SoP delivery rule

Routine SoP is now deliberately bounded. Full-repository semantic rereads and automatic repeated full-tree scans are disabled for normal development and acceptance work.

1. Review the exact first-parent-to-candidate unified diff with three context lines. The semantic review scope is changed hunks plus only the local file context or directly affected dependency needed to validate those hunks; untouched repository areas are not reread merely to satisfy SoP.
2. If a defect is found and fixed, the candidate changes. Recompute the parent-to-candidate diff and restart the scoped review on that new diff.
3. Delivery still requires three consecutive clean semantic/manual passes, but all three operate on the same bounded candidate diff rather than the entire repository.
4. Any later substantive change creates a new candidate and resets those scoped passes.

`tools/sop_scan.py` now defaults to the same bounded parent-to-candidate diff. It records the exact base, candidate, unified-diff hash, changed paths and changed-file blob hashes while rejecting tracked working-tree drift. A complete tracked-tree scan remains available only through explicit `--full-tree`; routine workflows do not request it. `tools/workflow_sop.sh` runs the ordinary policy/regression gates and records one bounded baseline diff manifest. Existing workflow final scans compare against that baseline, so normal CI performs no automatic three-pass full-repository SoP.

Domain-specific policy gates may still inspect broader files when their own invariant requires it; those checks are validators, not semantic SoP passes.

## Phase status

### Phase 1

Foundation complete: UAPI v2, `decnet_iv.ko`, configurable identity, Routing Layer EtherType registration/counters, `dnctl`, centralized test addressing, unit tests and native x86_64/aarch64 build gates.

### Phase 2

Foundation complete: pinned Ubuntu Base 26.04.1 amd64/arm64 rootfs files and package snapshot `20260915T000000Z`, deterministic ext4/QCOW2 construction, exact guest kernel/module/userspace build, direct kernel/initrd boot, two independent one-NIC VMs, packet capture and serial evidence. The image builder explicitly installs `initramfs-tools`, verifies its generated initrd, archives the exact tracked source commit into the guest, validates the installed smoke unit/script, leaves acceptance QCOW2 uncompressed, and verifies guest-visible RAW/QCOW2 logical equality with `qemu-img compare`. The arm64 direct-boot path strips one outer gzip layer when present and accepts either a raw AArch64 Image or a validated gzip EFI-zboot wrapper supported by QEMU 8.x.

### Phase 3

Implementation remains active. UAPI v2 provides standard Phase IV node MAC derivation, router/endnode hello generation and parsing, periodic hello transmission, per-interface adjacency state, 3.1x listen expiry, designated-router election, counters and `dnctl adjacencies`. Router-router INIT/UP behavior, endnode admission, endnode router selection, L2 cross-area behavior, 33-router/interface admission, protocol source MACs, DECnet unicast filters and primary-MAC-change survival are implemented and covered by the current E1/interop harnesses.

Candidate `6d4ef7b364392d1a999c1bf433d833aed86c6eef` completed three scoped clean passes and acceptance parent `35192508159` dispatched exact-SHA-bound children. Repository/continuity, native x86_64/aarch64 builds and external reference baselines completed green, but E1 and interoperability exposed base-image verification defects before protocol assertions. Candidate `3af6da37274006fbd2b0cbe9682821f30bd5f7ba` corrected those defects, completed three new clean scoped passes and acceptance parent `35195064164` dispatched fresh exact-SHA-bound children.

For candidate `3af6da37274006fbd2b0cbe9682821f30bd5f7ba`, repository policy, project-state/continuity, native x86_64/aarch64 builds and external reference baselines completed green. E1 child `35195101815` and independent-interoperability child `35195103898` again failed before protocol assertions in base-image construction. amd64 reached successful uncompressed QCOW2 construction and `qemu-img check`, but host-file `cmp` rejected the raw-to-QCOW2 round trip because sparse/allocation representation is not a guest-visible content invariant. arm64 progressed past the previous ownership defect but rejected Ubuntu 26.04's EFI-zboot kernel wrapper because the builder required raw `ARM\x64` Image magic after only an outer-gzip check. No result from that candidate is promotable.

The current candidate corrects both deeper image-validation defects. Base and derived image builders use `qemu-img compare` across RAW and QCOW2, which compares logical disk content while treating unallocated zero sectors as equivalent. The arm64 path keeps its outer-gzip peel, then validates either raw AArch64 Image magic or the EFI-zboot `MZ`/`zimg`/Linux header, requires the gzip compression type supported by the deployed QEMU 8.x loader, and checks payload bounds. The image-builder policy gate requires these safeguards and explicitly forbids host RAW `cmp` and strict allocation-sensitive image comparison. All scoped passes and acceptance evidence reset on this change.

Commit `f18465c08fd5c6fe2fb72a12875781a3c874bff3` accidentally created an empty top-level `NONEXISTENT` path during repository tooling. It contains no protocol or build content. The current candidate deletes that path in the same correction commit and no acceptance result is associated with the accidental state.

## Test addressing

Ordinary lab addressing remains area 31, nodes 70 through 79, names DN70 through DN79. The live L2 interoperability case deliberately uses an independent peer in area 32.

## Pre-production acceptance

`docs/PRE_PRODUCTION_TEST.md` remains the consolidated production procedure. Required tests must execute with complete evidence; documentation alone is never green. Long campaigns are checkpointed across hosted jobs, while any genuinely uninterrupted run beyond the hosted-job ceiling requires a persistent controller.

## Resume point

Phase 3 remains active. The latest exact-head acceptance reached all static/native/reference gates but failed in image construction on both architectures before any DECnet protocol assertion. The current candidate contains the bounded arm64 EFI-zboot and logical image-comparison correction with policy coverage, plus removal of the accidental empty top-level path. No clean scoped pass carries forward, so the pass count starts at zero on this exact first-parent-to-candidate diff.

## Next action

Perform three consecutive clean semantic/manual passes over the exact first-parent-to-candidate diff with three context lines, using only directly necessary local/dependency context. Any fix restarts the sequence on the new candidate. After three clean passes on the unchanged candidate, dispatch fresh exact-head repository/continuity, native x86_64/aarch64 build, pinned reference, E1 and bounded Route20/PyDECnet interoperability gates. Phase 4 begins only after the unchanged Phase 3 candidate is green.
