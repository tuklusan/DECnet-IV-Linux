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

Foundation complete: pinned Ubuntu Base 26.04.1 amd64/arm64 rootfs files and package snapshot `20260915T000000Z`, deterministic ext4/QCOW2 construction, exact guest kernel/module/userspace build, direct kernel/initrd boot, two independent one-NIC VMs, packet capture and serial evidence. The image builder explicitly installs `initramfs-tools`, verifies its generated initrd, archives the exact tracked source commit into the guest, validates the installed smoke unit/script, leaves acceptance QCOW2 uncompressed, round-trips it to raw for complete byte-for-byte disk comparison, and decompresses/checks arm64 kernel Image format for direct boot.

### Phase 3

Implementation remains active. UAPI v2 provides standard Phase IV node MAC derivation, router/endnode hello generation and parsing, periodic hello transmission, per-interface adjacency state, 3.1x listen expiry, designated-router election, counters and `dnctl adjacencies`. Router-router INIT/UP behavior, endnode admission, endnode router selection, L2 cross-area behavior, 33-router/interface admission, protocol source MACs, DECnet unicast filters and primary-MAC-change survival are implemented and covered by the current E1/interop harnesses.

Candidate `a122e8e82541a9499b9b514568b70e77de97ca4b` completed the former full-tree review sequence and exact-head acceptance parent `35184898090` dispatched bound children. Repository/continuity, native builds and pinned reference baselines were green. E1 child run `35184925391` failed before protocol assertions: amd64 exposed corruption/misinstallation of the guest smoke service and arm64 produced no serial output because the packaged kernel image was unsuitable for direct QEMU boot. Commit `d3416e1ad9d2a5e057c6c49e9407cec92683dc86` hardened the base-image path against both failure classes.

Candidate `6d4ef7b364392d1a999c1bf433d833aed86c6eef` then completed three scoped clean passes and acceptance parent `35192508159` dispatched exact-SHA-bound children. Repository/continuity, native x86_64/aarch64 builds and external reference baselines completed green; the PyDECnet baseline needed one isolated rerun after its known timing-sensitive DDCMP UDP queue test missed by one packet. E1 child `35192540407` and independent-interoperability child `35192542464` failed before protocol assertions while building the exact candidate image. On arm64, the copied/decompressed direct-boot kernel remained root-owned when the builder performed a non-root Image-header read, producing `Permission denied`. On amd64, the uncompressed QCOW2 passed `qemu-img check` and round-tripped to a mountable raw image, but the `ro,noload` verification mount did not expose the already-validated smoke entry point. No result from that candidate is promotable.

The current candidate corrects both image-builder defects without weakening the image contract. The arm64 boot artifact is handed to the invoking user before the non-root header probe. The base-image conversion proof now matches the stronger derived-image proof: smoke script/unit bytes and systemd syntax are validated before conversion, the final QCOW2 is structurally checked and converted back to RAW, and every logical RAW disk byte is compared against the intended source image. `tests/policy/test_image_builder_gate.py` requires the ownership-before-probe ordering and the whole-RAW comparison. All scoped passes and acceptance evidence reset on this change.

## Test addressing

Ordinary lab addressing remains area 31, nodes 70 through 79, names DN70 through DN79. The live L2 interoperability case deliberately uses an independent peer in area 32.

## Pre-production acceptance

`docs/PRE_PRODUCTION_TEST.md` remains the consolidated production procedure. Required tests must execute with complete evidence; documentation alone is never green. Long campaigns are checkpointed across hosted jobs, while any genuinely uninterrupted run beyond the hosted-job ceiling requires a persistent controller.

## Resume point

Phase 3 remains active. The latest exact-head acceptance exposed two base-image construction/verification defects before any DECnet protocol assertion. The current candidate contains the bounded correction and its policy regression; no clean scoped pass carries forward, so the pass count starts at zero on this exact first-parent-to-candidate diff.

## Next action

Perform three consecutive clean semantic/manual passes over the exact first-parent-to-candidate diff with three context lines, using only directly necessary local/dependency context. Any fix restarts the sequence on the new candidate. After three clean passes on the unchanged candidate, dispatch fresh exact-head repository/continuity, native x86_64/aarch64 build, pinned reference, E1 and bounded Route20/PyDECnet interoperability gates. Phase 4 begins only after the unchanged Phase 3 candidate is green.
