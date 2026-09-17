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

The delivery SoP is a complete semantic/manual review of the latest exact tracked tree. Diff manifests and policy gates are support evidence only.

1. Read the complete latest disk copy byte-for-byte and line-by-line, without truncation, and identify defects or gaps. Fix every defect or gap found.
2. Any fix changes the candidate and resets the sequence. Restart Step 1 from the new latest disk copy.
3. Delivery requires three consecutive clean complete-tree Step-1 passes on one exact unchanged candidate.
4. Any later substantive change resets the sequence to Step 1 again.

`tools/sop_scan.py` records machine-readable candidate identity, changed paths/blob hashes and optional full-tree manifests. `tools/workflow_sop.sh` runs policy/regression gates and records a bounded baseline diff manifest which workflow final scans use to detect checkout drift. Those machine checks never replace the complete semantic/manual delivery passes.

Domain-specific policy gates may inspect broader files when their own invariant requires it; those checks are validators, not semantic SoP passes.

## Phase status

### Phase 1

Foundation complete: UAPI v2, `decnet_iv.ko`, configurable identity, Routing Layer EtherType registration/counters, `dnctl`, centralized test addressing, unit tests and native x86_64/aarch64 build gates.

### Phase 2

Foundation complete: pinned Ubuntu Base 26.04.1 amd64/arm64 rootfs files and package snapshot `20260915T000000Z`, deterministic ext4/QCOW2 construction, exact guest kernel/module/userspace build, direct kernel/initrd boot, two independent one-NIC VMs, packet capture and serial evidence. The image builder explicitly installs `initramfs-tools`, verifies its generated initrd, archives the exact tracked source commit into the guest, validates the installed smoke unit/script, leaves acceptance QCOW2 uncompressed, and verifies guest-visible RAW/QCOW2 logical equality with `qemu-img compare`. The arm64 direct-boot path strips one outer gzip layer when present and follows QEMU AArch64 loader semantics: current `ARM\x64` images are recognized for metadata, exact EFI-zboot headers receive structural validation, and other nonempty images remain eligible for QEMU's raw-image fallback and must prove themselves by actually booting.

### Phase 3

Implementation remains active. UAPI v2 provides standard Phase IV node MAC derivation, router/endnode hello generation and parsing, periodic hello transmission, per-interface adjacency state, 3.1x listen expiry, designated-router election, counters and `dnctl adjacencies`. Router-router INIT/UP behavior, endnode admission, endnode router selection, L2 cross-area behavior, 33-router/interface admission, protocol source MACs, DECnet unicast filters and primary-MAC-change survival are implemented and covered by the current E1/interop harnesses.

Candidate `6d4ef7b364392d1a999c1bf433d833aed86c6eef` completed three scoped clean passes and acceptance parent `35192508159` dispatched exact-SHA-bound children. Repository/continuity, native x86_64/aarch64 builds and external reference baselines completed green, but E1 and interoperability exposed base-image verification defects before protocol assertions. Candidate `3af6da37274006fbd2b0cbe9682821f30bd5f7ba` corrected those defects, completed three new clean scoped passes and acceptance parent `35195064164` dispatched fresh exact-SHA-bound children.

For candidate `3af6da37274006fbd2b0cbe9682821f30bd5f7ba`, repository policy, project-state/continuity, native x86_64/aarch64 builds and external reference baselines completed green. E1 child `35195101815` and independent-interoperability child `35195103898` again failed before protocol assertions in base-image construction. amd64 reached successful uncompressed QCOW2 construction and `qemu-img check`, but host-file `cmp` rejected the raw-to-QCOW2 round trip because sparse/allocation representation is not a guest-visible content invariant. arm64 progressed past the previous ownership defect but rejected Ubuntu 26.04's EFI-zboot kernel wrapper because the builder required raw `ARM\x64` Image magic after only an outer-gzip check. No result from that candidate is promotable.

Candidate `c33241a984b6f1c61c0a7aa83b89945dd60a4fb6` corrects both deeper image-validation defects. Base and derived image builders use `qemu-img compare` across RAW and QCOW2, which compares logical disk content while treating unallocated zero sectors as equivalent. The arm64 path keeps its outer-gzip peel, then validates either raw AArch64 Image magic or the EFI-zboot `MZ`/`zimg`/Linux header, requires the gzip compression type supported by the deployed QEMU 8.x loader, and checks payload bounds. The image-builder policy gate requires these safeguards and explicitly forbids host RAW `cmp` and strict allocation-sensitive image comparison.

Commit `f18465c08fd5c6fe2fb72a12875781a3c874bff3` accidentally created an empty top-level `NONEXISTENT` path during repository tooling. Candidate `c33241a984b6f1c61c0a7aa83b89945dd60a4fb6` deleted that path and no acceptance result was associated with the accidental state. A subsequent unintended non-main ref was automatically deleted by cleanup run `35219630482`; deletion and the one-branch invariant succeeded, but the cleanup job then exposed a workflow contradiction: `workflow_sop.sh` treated its `main` scope as acceptance-only and rejected the immutable create-event `GITHUB_REF` even after checkout had switched to the exact current `main` tree. Candidate `57f123d43760554a333772755da9d196c6444614` added an explicit maintenance scope that verifies current remote `main` without requiring acceptance-event ref metadata, and the branch-policy regression test requires the cleanup workflow to use it.

The first complete-tree review of `57f123d43760554a333772755da9d196c6444614` found stale continuity/policy text. `docs/TEST_LAB.md` still described three automatic pre-work exact-tree scans although current workflows use one bounded baseline plus a matching final manifest, and it claimed the repository workflow did not run on `create` even though non-main branch creation deliberately triggers automatic cleanup. `docs/HANDOVER.md` and `docs/PROJECT_STATE.md` also still described the semantic/manual SoP as diff-scoped, conflicting with the governing complete-tree rule. Candidate `c71bc79a176bbac367a910567160e8809283c051` corrected those statements.

The first complete-tree pass on `c71bc79a176bbac367a910567160e8809283c051` then found the same obsolete machine-scan description in `scratch/README.md`, which still claimed three automatic complete scans and a three-scan `workflow_sop.sh` gate. Candidate `f2bab342389ce8da8c8696c222c37c35326ceefe` corrected the scratch workspace contract to describe the actual bounded baseline/final machine checks while preserving the separate three-pass complete semantic/manual delivery SoP.

The complete-tree pass on `f2bab342389ce8da8c8696c222c37c35326ceefe` found a Phase IV designated-router timing defect. The kernel used one module-start timestamp for DRDELAY, so a lower-priority router could become DR immediately after a better router expired once the module had been loaded for more than five seconds. The pinned PyDECnet live reference starts a fresh five-second DRDELAY when the local router first becomes the best candidate and cancels it when a better router is present. The current candidate tracks that candidacy per interface, resets it on interface-down and identity changes, and restarts DRDELAY after a better router disappears. E1 now deliberately silences DN71, the equal-priority higher-address DR, for longer than listener expiry but less than listener expiry plus DRDELAY; DN70 must expire DN71 but must never emit an All-Endnodes hello before DN71 returns. This is both the regression and the normal E1 failover/recovery proof.

During repository tooling for that correction, commit `f2147d83c4063a461bc732f3e017608bd5ba675c` accidentally created tracked `scratch/SHOULD_NOT_CREATE`. No acceptance evidence is associated with that state. Candidate `2e23adcacad4945b2495c3704d07cb1a2860a04a` deletes that path in the same forward correction that contains the DRDELAY fix and refreshed continuity records. Candidate `6f4baf02029c3ac9e0c44885a85add79564017df` then removed the pending SoP-pass action from the tracked next-action markers while retaining the recorded pass/progress fields.

Branch-cleanup maintenance run `35224985329` on `6f4baf02029c3ac9e0c44885a85add79564017df` confirmed the one-branch invariant and exact tree, then failed in `test_repo_policy_branch.py`: its stale `main`-scope detector used substring matching, so the valid `maintenance` invocation was misclassified because `maintenance` begins with `main`. Candidate `b47b11dd513c4bcb4acb66594c1d96aa6c071a4a` makes that detector line-exact. Maintenance verification `35225226843` completed green on that exact candidate.

Fresh Phase 3 acceptance was then dispatched on `b47b11dd513c4bcb4acb66594c1d96aa6c071a4a`. Native build `35225302832` and project-state `35225305452` completed green. E1 run `35225310434` exposed a further arm64 image-gate false rejection before protocol assertions: Ubuntu's installed arm64 kernel did not match either magic pattern required by the builder, although QEMU's AArch64 loader intentionally accepts non-zboot images through a raw-image fallback and treats `ARM\x64` magic as optional metadata. The current correction mirrors QEMU's actual loader contract: retain outer-gzip handling, recognize and structurally validate exact zboot headers, but preserve any other nonempty artifact for QEMU raw loading and require the VM boot gate to be the executable proof. The image-builder policy gate now rejects reintroduction of the obsolete hard magic requirement. This substantive correction resets the delivery SoP count to zero; no result from `b47b11dd513c4bcb4acb66594c1d96aa6c071a4a` can promote Phase 3.

## Test addressing

Ordinary lab addressing remains area 31, nodes 70 through 79, names DN70 through DN79. The live L2 interoperability case deliberately uses an independent peer in area 32.

## Pre-production acceptance

`docs/PRE_PRODUCTION_TEST.md` remains the consolidated production procedure. Required tests must execute with complete evidence; documentation alone is never green. Long campaigns are checkpointed across hosted jobs, while any genuinely uninterrupted run beyond the hosted-job ceiling requires a persistent controller.

## Resume point

Phase 3 remains active. Maintenance verification is green, but fresh acceptance found an arm64 base-image validator stricter than QEMU's actual AArch64 direct-loader semantics. The current candidate removes that false rejection while keeping exact EFI-zboot structural checks and logical QCOW2 integrity checks. The protocol correction for per-interface designated-router DRDELAY/handoff remains unchanged and still awaits executable E1/independent-peer proof on the corrected image path.

## Next action

Run the complete-tree delivery SoP from zero on the exact current candidate. After three consecutive clean complete semantic/manual passes, dispatch fresh exact-head native x86_64/aarch64 build, project-state/continuity, pinned reference, E1 and bounded Route20/PyDECnet interoperability gates. Phase 4 begins only after that unchanged Phase 3 candidate is green.
