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
- Compact evidence retention is at most 30 days. Transient VM overlays and QMP sockets are never uploaded as acceptance evidence.
- Candidate promotion is determined only by documented exact-SHA mechanical, build, VM, reference, protocol and interoperability gates.

## Phase status

### Phase 1

Foundation complete: UAPI v2, `decnet_iv.ko`, configurable identity, Routing Layer EtherType registration/counters, `dnctl`, centralized test addressing, unit tests and native x86_64/aarch64 build gates.

### Phase 2

Foundation complete: pinned Ubuntu Base 26.04.1 amd64/arm64 rootfs files and package snapshot `20260915T000000Z`, deterministic ext4/QCOW2 construction, exact guest kernel/module/userspace build, direct kernel/initrd boot, independent VMs, packet capture and serial evidence. Release-image integrity retains `qemu-img check` and logical RAW/QCOW2 equality.

### Phase 3

Implementation remains active. Router/endnode hello generation/parsing, periodic hello, per-interface adjacencies, 3.1x listen expiry, DR election, router-router INIT/UP behavior, endnode admission/router selection, L2 cross-area behavior, 33-router/interface admission, protocol source MACs, DECnet unicast filters and primary-MAC-change survival are implemented and covered by the E1/interop harnesses.

Exact-SHA acceptance on `3f41bec910b5b07520c23b05dcbb1996d091ef62` established that native builds and continuity gates were green but the VM/interoperability path was spending acceptance time in guest-image construction and mutation. The subsequent image-stability correction `102972a5e8a35e517ac65bd100a8d3f271f37720` made ext4 conversion deterministic, but protocol acceptance remained too tightly coupled to repeated image production.

`tests/lab/dniv_lab.py` remains the two-node virtualization controller. It launches QEMU directly, creates disposable qcow2 overlays per guest, uses TAP/bridge networking, records serial and DECnet packet evidence, and uses QMP for shutdown. Mutable inner-VM checkpoint/upload/restore/rebase/prune machinery remains retired.

The architecture persistence boundary is now explicit. Each architecture slot has one immutable outer base session for the exact candidate, identified as `outer-v1-<arch>-<source-sha>`. GitHub-hosted runner root filesystems are ephemeral, so the architecture disk session is persisted through the GitHub Actions cache and restored on later acceptance jobs for that same exact SHA. The cached session contains only `base.qcow2`, kernel/initrd, a session manifest and checksums. Every restore verifies architecture, exact source SHA, all SHA-256 sums and `qemu-img check` before use. A different architecture or source SHA cannot reuse the session.

Both the Python two-node gate and interoperability now consume that same architecture session. The first job for an architecture/SHA may build and save it; later jobs restore it instead of re-running Ubuntu Base extraction, package installation and base-image conversion. Interoperability then derives disposable candidate/reference images from the immutable session base. Prior-run interoperability evidence restore inputs are removed because they did not alter execution and only added transfer/lineage overhead.

Repository policy and acceptance dispatch remain isolated from lab-runner concurrency. Protocol jobs remain serialized by their architecture slots, which also prevents two jobs racing to create the same outer session.

Candidate `22fa6771250b5f46b68ac822fd9af38d82baba23` proved the first cache wiring was not workflow-valid: GitHub rejected `vm-lab.yml` before creating jobs because `runner.temp` is unavailable in job-level `env`. The correction uses `${{ github.workspace }}/scratch/outer/<arch>`, an ignored workspace path whose `github` context is valid at job scope. Results from `22fa677...` are historical and do not count toward acceptance.

## Test addressing

Ordinary lab addressing remains area 31, nodes 70 through 79, names DN70 through DN79. The live L2 interoperability case deliberately uses an independent peer in area 32.

## Pre-production acceptance

`docs/PRE_PRODUCTION_TEST.md` is the consolidated production procedure. Required tests must execute with complete evidence; documentation alone is never green. Long campaigns should reuse immutable architecture sessions while keeping guest writable state disposable.

## Resume point

Phase 3 remains active. The current candidate combines the Python QEMU/QMP disposable-overlay controller with exact-SHA persistent architecture base sessions shared by E1 and interoperability. No protocol promotion is implied until the unchanged candidate passes build, continuity, reference, E1 and interoperability gates.

## Next action

Run fresh exact-head acceptance. The first amd64 and arm64 lab jobs should create or restore their `outer-v1-<arch>-<sha>` sessions; subsequent jobs for the same SHA must report cache hits and skip base construction. Then evaluate E1 and interoperability protocol results independently of image-preparation overhead.
