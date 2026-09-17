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
- Hosted jobs have explicit timeouts of at most 75 minutes; concurrency uses `queue: max` with `cancel-in-progress: false` where a concurrency block is needed.
- Repository-policy/control runs are isolated by exact candidate SHA and do not consume the protocol-lab `dniv-runner-*` serialization slots.
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

Exact-SHA acceptance on `3f41bec910b5b07520c23b05dcbb1996d091ef62` established that native builds and continuity gates were green but the VM/interoperability path was spending acceptance time in guest-image construction and mutation. Image-stability correction `102972a5e8a35e517ac65bd100a8d3f271f37720` made ext4 conversion deterministic. The subsequent Python-QEMU work removed writable inner-VM checkpoint/upload/restore/rebase/prune machinery and proved that architecture images can be cached/restored between jobs.

The final persistence boundary remains source-independent architecture foundations plus disposable exact-candidate/reference layers. `image/ubuntu-base/build-foundation.sh` creates an amd64/arm64 foundation containing Ubuntu userspace, the pinned guest kernel/initrd, headers/compiler and independent-reference runtime dependencies. Its stable session ID is `outer-v2-<arch>-<foundation-fingerprint>`, where the fingerprint derives from the pinned image metadata and foundation recipe. The manifest contains no source SHA. Ordinary project commits therefore reuse the same architecture foundation instead of repeating package installation and full image construction.

`tests/lab/prepare-candidate-image.sh` derives a disposable image from that verified foundation, archives the exact checked-out commit, builds and installs `decnet_iv.ko`, `dnctl`, `dnraw` and the smoke entry points, and records exact candidate provenance. It performs no package installation. `tests/lab/prepare-reference-image.sh` similarly derives a disposable reference runtime without package installation. Route20/PyDECnet remain independently pinned and attached separately.

`tests/lab/dniv_lab.py` is the two-node virtualization controller. It launches QEMU directly, creates disposable qcow2 overlays per guest, uses TAP/bridge networking, records serial and DECnet packet evidence, and uses QMP for shutdown. Runtime/evidence is placed below a short `/tmp/dniv-*` path so QMP UNIX socket names remain bounded; compact logs/pcaps are copied back to `scratch/runtime/` and disposable disks/sockets are removed. ARM64 direct boot uses 1 GiB, explicit GIC selection and the PL011 early console; x86_64 remains at the smaller proven footprint.

Acceptance candidate `5f4fdc5b3d1bcef87e56ac64b8c3b287f504eddb` proved that this persistence architecture is no longer the blocker. Repository policy, project-state and native amd64/arm64 builds were green. The amd64 Python two-node E1 VM gate was fully green using a restored `outer-v2` foundation and disposable exact-candidate image. ARM64 restored and injected the exact candidate successfully but produced no serial output while QEMU remained alive for the full gate, isolating the failure to the direct-boot kernel artifact/loader boundary rather than DECnet or foundation persistence.

The same acceptance moved independent interoperability farther. The vvfat partition correction worked. Route20 then failed because the copied executable was launched from `/run`, which is not an executable location in this guest; the harness now installs the verified Route20 binary on the normal root filesystem while retaining transient configuration under `/run`. PyDECnet reached its ready marker and then exited because its exact pinned `version.py` invokes `git`; `git` is therefore added as a legitimate foundation reference-runtime dependency instead of modifying the reference implementation.

The ARM64 kernel artifact is now normalized explicitly. `image/ubuntu-base/normalize-arm64-kernel.sh` accepts a raw Linux Image or recognized gzip/Zstd EFI-zboot payload, extracts it to a raw Image, validates the `ARM\x64` header, and rejects unknown formats. Both the foundation and release-image builders are bound to the exact helper SHA-256. This changes the foundation recipe and therefore intentionally creates a new `outer-v2` fingerprint; one foundation rebuild per architecture is expected, after which ordinary cache reuse resumes. No protocol assertion has been weakened.

Repository policy and acceptance dispatch remain isolated from lab-runner concurrency. Protocol jobs remain serialized by architecture slot. Release-image construction remains a separate exact-source gate and is not inferred from the cached protocol foundation.

## Test addressing

Ordinary lab addressing remains area 31, nodes 70 through 79, names DN70 through DN79. The live L2 interoperability case deliberately uses an independent peer in area 32.

## Pre-production acceptance

`docs/PRE_PRODUCTION_TEST.md` is the consolidated production procedure. Required tests must execute with complete evidence; documentation alone is never green. Long campaigns reuse immutable source-independent architecture foundations while keeping exact-candidate and writable guest state disposable.

## Resume point

Phase 3 is the active workstream. The architecture of the test infrastructure is closed; the current changes are correctness fixes to the ARM64 direct-boot artifact and independent-reference runtime. Acceptance lineage for `5f4fdc5b3d1bcef87e56ac64b8c3b287f504eddb` is parent `35256346698`, native build `35256391400`, project-state `35256393889`, Python VM `35256398678`, and interoperability `35256400954`. The next candidate must intentionally rebuild the changed foundation fingerprint, prove ARM64 raw-Image boot, and clear the Route20/PyDECnet runtime blockers.

## Next action

Run exact-head acceptance for the ARM64 kernel-normalization/reference-runtime correction. Expect a one-time `outer-v2` cache miss because the foundation recipe changed. Verify amd64 E1 remains green, ARM64 reaches serial and DECnet execution, Route20 executes from the root filesystem, and PyDECnet remains alive with `git` available. Once those harness/runtime checks clear, continue Phase 3 immediately from the first substantive DECnet interoperability failure; do not return to infrastructure redesign without concrete evidence against the persistence mechanism itself.
