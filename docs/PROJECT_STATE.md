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

Build a complete native DECnet Phase IV stack for maintained Linux as an out-of-tree kernel module plus DECnet/Linux userspace. Deliver reproducible x86_64/aarch64 images and prove behavior against independent implementations and later real DEC systems.

## References and licensing

Preferred exact reference pins remain Route20 `b94115b2615c6463d1f006924ceeadde8e2d4367`, PyDECnet live `a7194be8d72dea6f9eb4f77083f056f53e80df58`, PyDECnet tests `9a844987bf3a1450632dee8d37e60a23a453bad3`, LinuxDECnet `ff39eef045d1e4b7b72a3d40111e89c07a473398`, and SIMH `5b73b1032b52d19bf80752ea4d9cbbdc92e7b5e0`. The product license is the canonical root `LICENSE`; the kernel reports `MODULE_LICENSE("Proprietary")`.

## Repository discipline

- Work directly on `main`; do not create or use feature branches.
- The remote branch invariant is exactly `refs/heads/main`.
- Every substantive commit updates this file and `scratch/RESUME.md` in the same commit.
- Acceptance applies only to one exact unchanged `main` commit and children are bound to parent run ID plus exact expected SHA.
- Hosted jobs have explicit timeouts of at most 75 minutes; protocol concurrency uses architecture-specific `dniv-runner-*` slots with `queue: max` and `cancel-in-progress: false`.
- GitHub-owned actions remain pinned to immutable full SHAs.
- Compact evidence retention is at most 30 days. Transient candidate images, VM overlays and QMP sockets are never acceptance state.
- Candidate promotion is determined only by documented exact-SHA mechanical, build, VM, reference, protocol and interoperability gates.

## Phase status

### Phase 1

Foundation complete: UAPI v2, `decnet_iv.ko`, configurable identity, Routing Layer EtherType registration/counters, `dnctl`, centralized test addressing, unit tests and native x86_64/aarch64 build gates.

### Phase 2

Foundation complete: pinned Ubuntu Base 26.04.1 amd64/arm64 rootfs files and package snapshot `20260915T000000Z`, deterministic ext4/QCOW2 construction, exact guest kernel/module/userspace build, direct kernel/initrd boot, independent VMs, packet capture and serial evidence. Release-image integrity retains `qemu-img check` and logical RAW/QCOW2 equality.

### Phase 3

Implementation remains active. Router/endnode hello generation/parsing, periodic hello, per-interface adjacencies, 3.1x listen expiry, DR election, router-router INIT/UP behavior, endnode admission/router selection, L2 cross-area behavior, 33-router/interface admission, protocol source MACs, DECnet unicast filters and primary-MAC-change survival are implemented and covered by the E1/interop harnesses.

The VM persistence architecture is closed. Source-independent `outer-v2-<arch>-<foundation-fingerprint>` foundations contain Ubuntu userspace, the pinned guest kernel/initrd, headers/compiler and independent-reference runtime dependencies, but no candidate source or SHA. `tests/lab/prepare-candidate-image.sh` and `tests/lab/prepare-reference-image.sh` derive disposable exact-candidate/reference images without package installation. `tests/lab/dniv_lab.py` launches direct QEMU guests, TAP/bridge networking, packet capture and serial evidence, and removes disposable disks and sockets after each run.

Exact-head candidate `5f4fdc5b3d1bcef87e56ac64b8c3b287f504eddb` proved the persistence architecture was no longer the blocker: repository policy, project state and native amd64/arm64 builds were green, and amd64 Python E1 passed from a restored foundation. ARM64 restored and injected the candidate but produced no serial output while QEMU remained alive, isolating the fault to the direct-boot kernel artifact/loader boundary. That run also exposed two reference-runtime defects: Route20 could not execute from `/run`, and pinned PyDECnet required `git` at startup. Route20 is now installed under `/usr/local/libexec`; `git` is a legitimate foundation dependency.

Candidate `317deebe5a916ca28e576074fab7e310b15b5d37` then passed repository policy, project state, native builds and reference baselines. Its ARM64 VM path failed while normalizing Ubuntu 26.04's `7.0.0-31-generic` boot artifact because the helper recognized raw Image and EFI-zboot but not the additional wrapper presented by that package. The amd64 Route20 L1 interoperability job advanced far enough to prove the reference emitted a valid router INIT for node 31.71 and the candidate parsed it, but Route20 exited about 3.5 seconds after its READY marker before a stable adjacency formed. The captured LAN trace shows the Route20 INIT followed by loss of reference traffic; this is reference-runtime evidence, not yet a candidate adjacency defect.

The ARM64 normalizer now treats the kernel artifact as a bounded chain of recognized containers. It accepts a raw ARM64 Linux Image, whole-file gzip or Zstd, EFI-zboot gzip/Zstd, and a structurally valid PE/COFF wrapper with exactly one bounded `.linux` section. Each extracted layer is re-evaluated, nesting is bounded, and success still requires the raw Linux `ARM\x64` magic at offset 56. Unknown or malformed wrappers are rejected. Both image builders remain bound to the exact helper SHA-256, so changing the helper intentionally changes the foundation fingerprint and forces one foundation rebuild per architecture.

The Route20 reference launcher now preserves failure evidence instead of merely reporting `reference-exited`: on an unexpected Route20 death it emits the Route20 syslog tail and relevant kernel crash lines into the serial log. It does not patch, wrap or otherwise alter the pinned Route20 implementation. The next interoperability run must use that evidence to distinguish a Route20/runtime crash from any candidate protocol defect before changing DECnet behavior.

Exact-head candidate `a04d2a4ec8687f21fafce1950d339b983f15c973` cleared the ARM64 boot boundary in VM run `35262769735`: the real Ubuntu 26.04 kernel normalized through `pe-linux+efi-zboot:zstd+raw`, the foundation and candidate injection completed, and both routers reached UP adjacency after the runtime primary-MAC change. The amd64 E1 job passed. ARM64 then failed in the harness because `Routing frames received` and `Hello frames received` were sampled by separate `dnctl stats` calls; a hello arriving between calls manufactured `hello > routing` and DN70 exited before its unicast transmit loop, after which DN71 correctly observed zero unicast receive delta. The fix is therefore confined to coherent, bounded-retry harness sampling; kernel and wire behavior remain unchanged.

Repository policy and acceptance dispatch remain isolated from protocol-lab runner concurrency. Release-image construction remains a separate exact-source gate and is not inferred from the cached protocol foundation.

## Test addressing

Ordinary lab addressing remains area 31, nodes 70 through 79, names DN70 through DN79. The live L2 interoperability case deliberately uses an independent peer in area 32.

## Pre-production acceptance

`docs/PRE_PRODUCTION_TEST.md` is the consolidated production procedure. Required tests must execute with complete evidence; documentation alone is never green. Long campaigns reuse immutable source-independent architecture foundations while keeping exact-candidate and writable guest state disposable.

## Resume point

Phase 3 is the active workstream. Infrastructure architecture and ARM64 direct boot are closed. The current candidate changes only E1 counter sampling and its regression coverage: each logical sample comes from one `dnctl stats` invocation, internally inconsistent `rx_frames < hello_rx` snapshots are retried within a strict bound, and persistent inconsistency remains a hard failure. No kernel, UAPI, routing, hello, adjacency or reference implementation behavior is changed.

The remaining runtime questions are Route20 stability/interoperability and whatever genuine protocol failure appears after the ARM64 E1 harness can complete its unicast and expire/recover stages.

## Next action

Run exact-head acceptance on `main`, with ARM64 E1 as the first runtime discriminator. Require the new host-side counter-snapshot regression, repository policy, native amd64/arm64 builds and project-state gates to be green. If ARM64 E1 passes, confirm amd64 E1 remains green and continue the full reference/interoperability set on the same exact SHA. For any Route20 `reference-exited` result, use the captured syslog/kernel diagnostics before changing DECnet protocol code.
