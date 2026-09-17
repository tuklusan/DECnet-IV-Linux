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

The final infrastructure boundary is now explicit. `image/ubuntu-base/build-foundation.sh` creates a source-independent amd64/arm64 foundation containing Ubuntu userspace, pinned guest kernel/initrd, headers/compiler and reference-runtime dependencies. Its stable session ID is `outer-v2-<arch>-<foundation-fingerprint>`, where the fingerprint derives only from the pinned image metadata and foundation recipe. The manifest contains no source SHA. Therefore ordinary project commits reuse the same architecture foundation instead of repeating package installation and full image construction.

`tests/lab/prepare-candidate-image.sh` derives a disposable image from that verified foundation, archives the exact checked-out commit, builds and installs `decnet_iv.ko`, `dnctl`, `dnraw` and the smoke entry points, and records exact candidate provenance. It performs no package installation. `tests/lab/prepare-reference-image.sh` similarly derives a disposable reference runtime without package installation. Route20/PyDECnet remain independently pinned and attached separately.

`tests/lab/dniv_lab.py` remains the two-node virtualization controller. It launches QEMU directly, creates disposable qcow2 overlays per guest, uses TAP/bridge networking, records serial and DECnet packet evidence, and uses QMP for shutdown. Its runtime/evidence root is now placed under a short `/tmp/dniv-*` path by the workflow so QMP UNIX socket names cannot exceed the Linux pathname limit; compact logs/pcaps are copied back to `scratch/runtime/` and all disposable disks/sockets are removed.

Repository policy and acceptance dispatch remain isolated from lab-runner concurrency. Protocol jobs remain serialized by architecture slot, preventing foundation creation races. Release-image construction remains a separate exact-source gate and is not inferred from the cached protocol foundation.

## Test addressing

Ordinary lab addressing remains area 31, nodes 70 through 79, names DN70 through DN79. The live L2 interoperability case deliberately uses an independent peer in area 32.

## Pre-production acceptance

`docs/PRE_PRODUCTION_TEST.md` is the consolidated production procedure. Required tests must execute with complete evidence; documentation alone is never green. Long campaigns reuse immutable source-independent architecture foundations while keeping exact-candidate and writable guest state disposable.

## Resume point

Phase 3 remains active. Infrastructure work is considered closed after one exact-head acceptance exercise proves the `outer-v2` foundation path parses, creates/restores foundations, injects the exact candidate, and reaches E1/interoperability execution without the previous QMP pathname failure. No protocol promotion is implied until the unchanged candidate passes the documented gates.

## Next action

Run one fresh exact-head acceptance for the infrastructure-finalization candidate. If the foundation/cache/candidate-injection path works, stop infrastructure work and resume Phase 3 protocol/interoperability debugging from the first substantive protocol failure, following `docs/ROADMAP.md`.
